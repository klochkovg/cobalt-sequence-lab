"""Data model of a pipeline definition, schema version 1."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from graphlib import TopologicalSorter

# `${inputs.<name>}`, `${params.<name>}` or `${tasks.<name>.outputs.<key>}`
REF = re.compile(r"\$\{([^}]*)\}")
TASK_REF = re.compile(r"\$\{tasks\.([^.}]+)\.outputs\.[^}]+\}")


def references(value: object) -> list[str]:
    """Return the dotted paths of all `${...}` references in a string value."""
    if not isinstance(value, str):
        return []
    return REF.findall(value)


@dataclass(frozen=True)
class PipelineInfo:
    """The `pipeline:` header: name, version and description."""

    name: str
    version: str
    description: str = ""


@dataclass(frozen=True)
class ParamSpec:
    """A pipeline-level parameter declared with type and default."""

    type: str
    default: object | None = None


@dataclass(frozen=True)
class InputSpec:
    """A named, typed pipeline input supplied at run time."""

    type: str


@dataclass(frozen=True)
class TaskSpec:
    """One task of the pipeline: what to run and how it is wired to the rest."""

    name: str
    type: str
    inputs: dict[str, str] = field(default_factory=dict)
    params: dict[str, object] = field(default_factory=dict)
    adapter: str | None = None
    container: str | None = None
    resources: dict[str, object] = field(default_factory=dict)
    scatter: str | None = None

    def dependencies(self) -> set[str]:
        """Names of the tasks whose outputs this task consumes."""
        values = [*self.inputs.values(), *self.params.values()]
        return {
            name for value in values if isinstance(value, str) for name in TASK_REF.findall(value)
        }


@dataclass(frozen=True)
class PipelineV1:
    """A whole pipeline definition: a DAG of tasks plus its params, inputs and outputs."""

    schema_version: int
    info: PipelineInfo
    tasks: dict[str, TaskSpec]
    params: dict[str, ParamSpec] = field(default_factory=dict)
    inputs: dict[str, InputSpec] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)

    def edges(self) -> list[tuple[str, str]]:
        """Dependency edges as (upstream, downstream) pairs, in topological order."""
        return [
            (upstream, name)
            for name in self.topological_order()
            for upstream in sorted(self.tasks[name].dependencies())
        ]

    def topological_order(self) -> list[str]:
        """Task names ordered so that every task comes after the tasks it depends on.

        Raises graphlib.CycleError if the dependencies form a cycle.
        """
        sorter = TopologicalSorter({name: task.dependencies() for name, task in self.tasks.items()})
        return list(sorter.static_order())
