"""Human-readable text views of a pipeline definition."""

from __future__ import annotations

from cobalt.pipeline.model import PipelineV1


def _inline(values: dict[str, object] | dict[str, str]) -> str:
    return ", ".join(f"{key}={value}" for key, value in values.items())


def format_structure(pipeline: PipelineV1) -> str:
    """Describe the whole pipeline; tasks are listed in execution (topological) order."""
    info = pipeline.info
    lines = [f"pipeline: {info.name} {info.version} (schema v{pipeline.schema_version})"]
    if info.description:
        lines.append(f"  {info.description}")

    lines.append("params:")
    for name, param in pipeline.params.items():
        default = "" if param.default is None else f" = {param.default!r}"
        lines.append(f"  {name}: {param.type}{default}")
    if not pipeline.params:
        lines.append("  (none)")

    lines.append("inputs:")
    for name, spec in pipeline.inputs.items():
        lines.append(f"  {name}: {spec.type}")
    if not pipeline.inputs:
        lines.append("  (none)")

    lines.append("tasks:")
    for name in pipeline.topological_order():
        task = pipeline.tasks[name]
        lines.append(f"  {name} [{task.type}]")
        if task.adapter:
            lines.append(f"    adapter: {task.adapter}")
        if task.container:
            lines.append(f"    container: {task.container}")
        if task.resources:
            lines.append(f"    resources: {_inline(task.resources)}")
        if task.scatter:
            lines.append(f"    scatter: {task.scatter}")
        if task.inputs:
            lines.append(f"    inputs: {_inline(task.inputs)}")
        if task.params:
            lines.append(f"    params: {_inline(task.params)}")
        depends_on = sorted(task.dependencies())
        if depends_on:
            lines.append(f"    depends on: {', '.join(depends_on)}")

    lines.append("outputs:")
    for name, value in pipeline.outputs.items():
        lines.append(f"  {name}: {value}")
    if not pipeline.outputs:
        lines.append("  (none)")
    return "\n".join(lines)


def format_graph(pipeline: PipelineV1) -> str:
    """List the DAG as `upstream -> downstream` lines; tasks without edges appear alone."""
    edges = pipeline.edges()
    connected = {name for edge in edges for name in edge}
    lines = [f"{upstream} -> {downstream}" for upstream, downstream in edges]
    lines += [name for name in pipeline.topological_order() if name not in connected]
    return "\n".join(lines)
