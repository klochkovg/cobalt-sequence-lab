"""Runtime model of pipeline runs: a PipelineRun and the TaskRun of each of its tasks.

A run is persisted as a JSON manifest (see `PipelineRun.to_dict`); the definition classes
(`Pipeline`, `Task`) describe what to run, these classes describe what happened.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from cobalt.pipeline.model import Pipeline, PipelineInfo, Task

MANIFEST_VERSION = 1


class ManifestError(ValueError):
    """A run manifest with a missing or invalid value; the message names the key."""


class RunStatus(StrEnum):
    """Status of a pipeline run or of one of its tasks."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Statuses after which nothing changes any more
FINISHED = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})


def utc_now() -> datetime:
    """Return the current time, timezone-aware in UTC."""
    return datetime.now(UTC)


def new_run_id(now: datetime | None = None) -> str:
    """Return a new run id, `YYYYMMDD-HHMMSS-<8 hex>`.

    Ids sort by creation time and use only `[0-9a-f-]`, so they are safe as directory names.
    """
    stamp = (now or utc_now()).astimezone(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(4)}"


def _stamp(status: RunStatus, now: datetime | None) -> tuple[datetime | None, datetime | None]:
    """Return the (started_at, finished_at) to set for a change to `status`; None: keep."""
    when = now or utc_now()
    if status is RunStatus.RUNNING:
        return when, None
    if status in FINISHED:
        return None, when
    return None, None


@dataclass(slots=True)
class TaskRun:
    """One task of a pipeline run and its progress."""

    name: str
    type: str
    depends_on: list[str] = field(default_factory=list)
    status: RunStatus = RunStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None

    @classmethod
    def from_task(cls, task: Task) -> TaskRun:
        """Build the pending run of the task definition `task`."""
        return cls(name=task.name, type=task.type, depends_on=sorted(task.dependencies()))

    def set_status(
        self, status: RunStatus, error: str | None = None, now: datetime | None = None
    ) -> None:
        """Change the status; `running` stamps started_at, a finished status finished_at."""
        self.status = status
        self.error = error
        started, finished = _stamp(status, now)
        if started is not None:
            self.started_at = started
        if finished is not None:
            self.finished_at = finished

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-ready values, timestamps as ISO 8601."""
        return {
            "name": self.name,
            "type": self.type,
            "depends_on": list(self.depends_on),
            "status": str(self.status),
            "started_at": _format_time(self.started_at),
            "finished_at": _format_time(self.finished_at),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: object) -> TaskRun:
        """Build a TaskRun from `to_dict` output; unknown keys are ignored.

        Raises ManifestError for a missing or invalid value.
        """
        values = _require_mapping(data, "task")
        return cls(
            name=_require_str(values, "name"),
            type=_require_str(values, "type"),
            depends_on=_str_list(values.get("depends_on", []), "depends_on"),
            status=_status(values.get("status")),
            started_at=_parse_time(values.get("started_at"), "started_at"),
            finished_at=_parse_time(values.get("finished_at"), "finished_at"),
            error=_optional_str(values.get("error"), "error"),
        )


@dataclass(slots=True)
class PipelineRun:
    """One run of a pipeline: its parameters, status and the run of each task."""

    run_id: str
    pipeline: PipelineInfo
    params: dict[str, str] = field(default_factory=dict)
    backend: str = "local"
    resume: bool = False
    status: RunStatus = RunStatus.PENDING
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    # In execution (topological) order
    tasks: list[TaskRun] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        pipeline: Pipeline,
        params: Mapping[str, str] | None = None,
        backend: str = "local",
        resume: bool = False,
        now: datetime | None = None,
    ) -> PipelineRun:
        """Build a new pending run of `pipeline`, with one pending TaskRun per task."""
        created = now or utc_now()
        return cls(
            run_id=new_run_id(created),
            pipeline=pipeline.info,
            params=dict(params or {}),
            backend=backend,
            resume=resume,
            created_at=created,
            tasks=[
                TaskRun.from_task(pipeline.tasks[name]) for name in pipeline.topological_order()
            ],
        )

    def task(self, name: str) -> TaskRun:
        """Return the run of task `name`; raises KeyError if the pipeline has no such task."""
        for task in self.tasks:
            if task.name == name:
                return task
        raise KeyError(name)

    def set_status(
        self, status: RunStatus, error: str | None = None, now: datetime | None = None
    ) -> None:
        """Change the run status; `running` stamps started_at, a finished status finished_at."""
        self.status = status
        self.error = error
        started, finished = _stamp(status, now)
        if started is not None:
            self.started_at = started
        if finished is not None:
            self.finished_at = finished

    def set_task_status(
        self, name: str, status: RunStatus, error: str | None = None, now: datetime | None = None
    ) -> None:
        """Change the status of task `name` (see `TaskRun.set_status`); KeyError if unknown."""
        self.task(name).set_status(status, error, now)

    def task_counts(self) -> dict[str, int]:
        """Return the number of tasks in each status, every status included."""
        counts = {str(status): 0 for status in RunStatus}
        for task in self.tasks:
            counts[str(task.status)] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON manifest of the run."""
        return {
            "manifest_version": MANIFEST_VERSION,
            "run_id": self.run_id,
            "pipeline": {
                "name": self.pipeline.name,
                "version": self.pipeline.version,
                "description": self.pipeline.description,
            },
            "params": dict(self.params),
            "backend": self.backend,
            "resume": self.resume,
            "status": str(self.status),
            "created_at": _format_time(self.created_at),
            "started_at": _format_time(self.started_at),
            "finished_at": _format_time(self.finished_at),
            "error": self.error,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: object) -> PipelineRun:
        """Build a PipelineRun from a manifest (`to_dict` output); unknown keys are ignored.

        Raises ManifestError for a missing or invalid value.
        """
        values = _require_mapping(data, "manifest")
        info = _require_mapping(values.get("pipeline"), "pipeline")
        params = _require_mapping(values.get("params", {}), "params")
        resume = values.get("resume", False)
        if not isinstance(resume, bool):
            raise ManifestError(f"resume: expected true or false, got {resume!r}")
        created_at = _parse_time(values.get("created_at"), "created_at")
        if created_at is None:
            raise ManifestError("created_at: required")
        tasks = values.get("tasks", [])
        if not isinstance(tasks, list):
            raise ManifestError(f"tasks: expected a list, got {type(tasks).__name__}")
        return cls(
            run_id=_require_str(values, "run_id"),
            pipeline=PipelineInfo(
                name=_require_str(info, "pipeline.name"),
                version=_require_str(info, "pipeline.version"),
                description=_optional_str(info.get("description"), "pipeline.description") or "",
            ),
            params={str(key): str(value) for key, value in params.items()},
            backend=_optional_str(values.get("backend"), "backend") or "local",
            resume=resume,
            status=_status(values.get("status")),
            created_at=created_at,
            started_at=_parse_time(values.get("started_at"), "started_at"),
            finished_at=_parse_time(values.get("finished_at"), "finished_at"),
            error=_optional_str(values.get("error"), "error"),
            tasks=[TaskRun.from_dict(task) for task in tasks],
        )


def _format_time(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _parse_time(value: object, name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManifestError(f"{name}: expected an ISO 8601 time, got {value!r}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ManifestError(f"{name}: expected an ISO 8601 time, got {value!r}") from None
    # A naive time is taken as UTC
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _status(value: object) -> RunStatus:
    if isinstance(value, str) and value in RunStatus.__members__.values():
        return RunStatus(value)
    expected = ", ".join(status.value for status in RunStatus)
    raise ManifestError(f"status: expected one of {expected}, got {value!r}")


def _require_mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ManifestError(f"{name}: expected a mapping, got {type(value).__name__}")
    return value


def _require_str(values: Mapping[str, Any], name: str) -> str:
    key = name.rpartition(".")[2]
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{name}: expected a non-empty string, got {value!r}")
    return value


def _optional_str(value: object, name: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise ManifestError(f"{name}: expected a string, got {value!r}")


def _str_list(value: object, name: str) -> list[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise ManifestError(f"{name}: expected a list of strings, got {value!r}")


@dataclass(frozen=True, slots=True)
class RunSummary:
    """The short form of a run listed by `runs list`: no per-task details."""

    run_id: str
    pipeline: PipelineInfo
    status: RunStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    # Number of tasks in each status
    tasks: dict[str, int]

    @classmethod
    def from_run(cls, run: PipelineRun) -> RunSummary:
        """Summarize `run`."""
        return cls(
            run_id=run.run_id,
            pipeline=run.pipeline,
            status=run.status,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            tasks=run.task_counts(),
        )
