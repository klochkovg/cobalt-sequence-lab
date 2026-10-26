"""Read and validate a pipeline definition from YAML."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from graphlib import CycleError
from pathlib import Path

import yaml

from cobalt.pipeline.model import (
    InputSpec,
    ParamSpec,
    PipelineInfo,
    PipelineV1,
    TaskSpec,
    references,
)

log = logging.getLogger(__name__)

SUPPORTED_SCHEMA_VERSIONS = (1,)
TOP_LEVEL_KEYS = {"schema_version", "pipeline", "params", "inputs", "tasks", "outputs"}
TASK_KEYS = {"type", "inputs", "params", "adapter", "container", "resources", "scatter"}


class PipelineFileError(Exception):
    """A pipeline definition that can't be read or is invalid; the message is ready to be logged."""


def load_pipeline(path: Path) -> PipelineV1:
    """Read the pipeline definition in `path`.

    Raises PipelineFileError if the file is missing, is not valid YAML or doesn't
    describe a valid pipeline.
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise PipelineFileError(f"file not found: {path}") from None
    except IsADirectoryError:
        raise PipelineFileError(f"is a directory: {path}") from None
    except OSError as exc:
        raise PipelineFileError(f"could not read {path}: {exc}") from None
    except yaml.YAMLError as exc:
        raise PipelineFileError(f"{path}: invalid YAML: {exc}") from None
    try:
        return parse_pipeline(data)
    except PipelineFileError as exc:
        raise PipelineFileError(f"{path}: {exc}") from None


def parse_pipeline(data: object) -> PipelineV1:
    """Build a PipelineV1 from already parsed YAML, validating its structure and references."""
    top = _mapping(data, "pipeline file")
    _check_keys(top, TOP_LEVEL_KEYS, "pipeline file")

    schema_version = top.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version not in SUPPORTED_SCHEMA_VERSIONS
    ):
        raise PipelineFileError(
            f"schema_version: unsupported value {schema_version!r} "
            f"(supported: {', '.join(map(str, SUPPORTED_SCHEMA_VERSIONS))})"
        )

    header = _mapping(top.get("pipeline"), "pipeline")
    _check_keys(header, {"name", "version", "description"}, "pipeline")
    info = PipelineInfo(
        name=_string(header.get("name"), "pipeline.name"),
        version=_version(header.get("version"), "pipeline.version"),
        description=_string(header.get("description", ""), "pipeline.description"),
    )

    params = {}
    for name, spec in _mapping(top.get("params", {}), "params").items():
        where = f"params.{name}"
        spec = _mapping(spec, where)
        _check_keys(spec, {"type", "default"}, where)
        params[name] = ParamSpec(
            type=_string(spec.get("type"), f"{where}.type"), default=spec.get("default")
        )

    inputs = {}
    for name, spec in _mapping(top.get("inputs", {}), "inputs").items():
        where = f"inputs.{name}"
        spec = _mapping(spec, where)
        _check_keys(spec, {"type"}, where)
        inputs[name] = InputSpec(type=_string(spec.get("type"), f"{where}.type"))

    raw_tasks = _mapping(top.get("tasks"), "tasks")
    if not raw_tasks:
        raise PipelineFileError("tasks: at least one task is required")
    tasks = {name: _parse_task(name, spec) for name, spec in raw_tasks.items()}

    outputs = {
        name: _string(value, f"outputs.{name}")
        for name, value in _mapping(top.get("outputs", {}), "outputs").items()
    }

    pipeline = PipelineV1(
        schema_version=schema_version,
        info=info,
        tasks=tasks,
        params=params,
        inputs=inputs,
        outputs=outputs,
    )
    _check_references(pipeline)
    try:
        pipeline.topological_order()
    except CycleError as exc:
        raise PipelineFileError(f"tasks: dependency cycle: {' -> '.join(exc.args[1])}") from None
    log.debug("parsed pipeline %s %s: %d tasks", info.name, info.version, len(tasks))
    return pipeline


def _parse_task(name: str, data: object) -> TaskSpec:
    where = f"tasks.{name}"
    spec = _mapping(data, where)
    _check_keys(spec, TASK_KEYS, where)
    return TaskSpec(
        name=name,
        type=_string(spec.get("type"), f"{where}.type"),
        inputs={
            key: _string(value, f"{where}.inputs.{key}")
            for key, value in _mapping(spec.get("inputs", {}), f"{where}.inputs").items()
        },
        params=dict(_mapping(spec.get("params", {}), f"{where}.params")),
        adapter=_optional_string(spec.get("adapter"), f"{where}.adapter"),
        container=_optional_string(spec.get("container"), f"{where}.container"),
        resources=dict(_mapping(spec.get("resources", {}), f"{where}.resources")),
        scatter=_optional_string(spec.get("scatter"), f"{where}.scatter"),
    )


def _check_references(pipeline: PipelineV1) -> None:
    """Check that every `${...}` reference points to a declared input, param or task."""
    values: list[tuple[str, object]] = []
    for task in pipeline.tasks.values():
        values += [(f"tasks.{task.name}.inputs.{k}", v) for k, v in task.inputs.items()]
        values += [(f"tasks.{task.name}.params.{k}", v) for k, v in task.params.items()]
    values += [(f"outputs.{k}", v) for k, v in pipeline.outputs.items()]

    for where, value in values:
        for ref in references(value):
            kind, _, rest = ref.partition(".")
            if kind == "inputs" and rest in pipeline.inputs:
                continue
            if kind == "params" and rest in pipeline.params:
                continue
            if kind == "tasks":
                task_name, _, output = rest.partition(".outputs.")
                if task_name in pipeline.tasks and output:
                    continue
            raise PipelineFileError(f"{where}: unresolved reference ${{{ref}}}")


def _mapping(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        if value is None:
            raise PipelineFileError(f"{where}: missing or empty")
        raise PipelineFileError(f"{where}: expected a mapping, got {type(value).__name__}")
    for key in value:
        if not isinstance(key, str):
            raise PipelineFileError(f"{where}: keys must be strings, got {key!r}")
    return value


def _check_keys(value: Mapping[str, object], allowed: set[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise PipelineFileError(f"{where}: unknown key {unknown[0]!r}")


def _string(value: object, where: str) -> str:
    if value is None:
        raise PipelineFileError(f"{where}: required")
    if not isinstance(value, str):
        raise PipelineFileError(f"{where}: expected a string, got {type(value).__name__}")
    return value


def _version(value: object, where: str) -> str:
    # An unquoted `version: 1.0` or `version: 2` is read by YAML as a number
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    return _string(value, where)


def _optional_string(value: object, where: str) -> str | None:
    return None if value is None else _string(value, where)
