"""The run registry: the one holder of pipeline runs for the lifetime of the server.

`cobalt serve` creates a single RunRegistry with the app and hands it to the endpoints. Each run
is kept in memory and, when the registry has a directory, persisted as
`<runs_dir>/<run_id>/manifest.json` next to a copy of its definition (`pipeline.yaml`).
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Mapping
from pathlib import Path

from cobalt.io.files import write_text_atomic
from cobalt.pipeline.model import Pipeline
from cobalt.pipeline.run import FINISHED, PipelineRun, RunStatus

log = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"
DEFINITION_FILENAME = "pipeline.yaml"
INTERRUPTED_ERROR = "interrupted: server stopped"


class RunRegistry:
    """Pipeline runs of the server, by run id; safe to use from several threads.

    `runs_dir` None keeps runs in memory only (nothing is written).
    """

    def __init__(self, runs_dir: Path | None = None) -> None:
        self.runs_dir = runs_dir
        self._runs: dict[str, PipelineRun] = {}
        self._lock = threading.Lock()

    def load(self) -> int:
        """Read the manifests in `runs_dir` and return the number of runs loaded.

        An unreadable or invalid manifest is skipped with a warning. A run found pending or
        running was cut off by a server stop: it is marked failed and its manifest rewritten.
        Raises OSError if `runs_dir` can't be created or listed.
        """
        if self.runs_dir is None:
            return 0
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        loaded = 0
        for manifest in sorted(self.runs_dir.glob(f"*/{MANIFEST_FILENAME}")):
            run = self._read_manifest(manifest)
            if run is None:
                continue
            if run.status not in FINISHED:
                log.warning("run %s was %s when the server stopped", run.run_id, run.status)
                run.set_status(RunStatus.FAILED, INTERRUPTED_ERROR)
                self._write_manifest(run)
            with self._lock:
                self._runs[run.run_id] = run
            loaded += 1
        return loaded

    def _read_manifest(self, path: Path) -> PipelineRun | None:
        try:
            run = PipelineRun.from_dict(json.loads(path.read_text()))
        except (OSError, ValueError) as exc:
            # json.JSONDecodeError is a ValueError
            log.warning("skipping run manifest %s: %s", path, exc)
            return None
        if run.run_id != path.parent.name:
            log.warning(
                "skipping run manifest %s: run_id %r doesn't match its directory", path, run.run_id
            )
            return None
        return run

    def create(
        self,
        pipeline: Pipeline,
        definition_text: str,
        params: Mapping[str, str] | None = None,
        backend: str = "local",
        resume: bool = False,
    ) -> PipelineRun:
        """Register a new pending run of `pipeline` and return it.

        With a `runs_dir`, the run directory gets the definition text and the manifest.
        Raises OSError if they can't be written.
        """
        run = PipelineRun.create(pipeline, params, backend, resume)
        run_dir = self.run_dir(run.run_id)
        if run_dir is not None:
            write_text_atomic(run_dir / DEFINITION_FILENAME, definition_text)
            self._write_manifest(run)
        with self._lock:
            self._runs[run.run_id] = run
        log.info("created run %s of %s %s", run.run_id, run.pipeline.name, run.pipeline.version)
        return run

    def save(self, run: PipelineRun) -> None:
        """Persist `run` after a change of its status; nothing to do without a `runs_dir`."""
        with self._lock:
            self._runs[run.run_id] = run
        self._write_manifest(run)

    def list_runs(self) -> list[PipelineRun]:
        """Return all runs, newest first."""
        with self._lock:
            runs = list(self._runs.values())
        return sorted(runs, key=lambda run: (run.created_at, run.run_id), reverse=True)

    def get(self, run_id: str) -> PipelineRun | None:
        """Return the run `run_id`, or None if there is none."""
        # A lookup by key only: an id like "../x" never reaches the filesystem
        with self._lock:
            return self._runs.get(run_id)

    def run_dir(self, run_id: str) -> Path | None:
        """Return the directory of run `run_id`, None without a `runs_dir`."""
        return None if self.runs_dir is None else self.runs_dir / run_id

    def _write_manifest(self, run: PipelineRun) -> None:
        run_dir = self.run_dir(run.run_id)
        if run_dir is not None:
            text = json.dumps(run.to_dict(), indent=2) + "\n"
            write_text_atomic(run_dir / MANIFEST_FILENAME, text)

    def __len__(self) -> int:
        with self._lock:
            return len(self._runs)
