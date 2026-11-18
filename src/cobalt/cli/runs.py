"""CLI command: runs. Lists and shows pipeline runs of a cobalt server, so it needs client mode
(--server URL or $COBALT_SERVER); in local (CLI) mode it is unsupported."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from cobalt.cli.client import ServerError, get_json
from cobalt.cli.run import report_server_only

log = logging.getLogger(__name__)

TABLE_HEADER = ("RUN ID", "PIPELINE", "STATUS", "CREATED", "TASKS")


def build_parser() -> argparse.ArgumentParser:
    """Build parser for runs command."""
    parser = argparse.ArgumentParser(
        prog="cobalt runs",
        description="List or show pipeline runs on a cobalt server "
        "(needs --server URL or $COBALT_SERVER)",
    )
    output = argparse.ArgumentParser(add_help=False)
    output.add_argument(
        "--json", action="store_true", help="Print the server's JSON answer instead of text"
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("list", parents=[output], help="List the runs, newest first")
    show = subparsers.add_parser("show", parents=[output], help="Show one run and its tasks")
    show.add_argument("run_id", help="Run identifier, as printed by 'cobalt runs list'")
    return parser


def main(argv: Sequence[str] | None = None, server: str | None = None) -> int:
    """Entry point for the runs command; `server` is the server URL, None in local (CLI) mode."""
    args = build_parser().parse_args(argv)
    log.debug("runs %s %s", args.action, getattr(args, "run_id", ""))
    if server is None:
        return report_server_only(f"runs {args.action}", server)

    path = "/runs" if args.action == "list" else f"/runs/{quote(args.run_id, safe='')}"
    try:
        data = get_json(server, path)
    except ServerError as exc:
        log.error("cobalt runs %s: %s", args.action, exc)
        return 1

    if args.json:
        print(json.dumps(data, indent=2))
    elif args.action == "list":
        print(format_runs(data))
    else:
        print(format_run(data))
    return 0


def format_runs(runs: Sequence[Mapping[str, Any]]) -> str:
    """Format run summaries (`GET /runs`) as an aligned table, one run per line."""
    if not runs:
        return "no runs"
    rows = [TABLE_HEADER] + [
        (
            str(run["run_id"]),
            _pipeline_label(run["pipeline"]),
            str(run["status"]),
            format_time(run.get("created_at")),
            _task_counts(run.get("tasks", {})),
        )
        for run in runs
    ]
    widths = [max(len(row[col]) for row in rows) for col in range(len(TABLE_HEADER) - 1)]
    return "\n".join(
        "  ".join([*(cell.ljust(width) for cell, width in zip(row, widths, strict=False)), row[-1]])
        for row in rows
    )


def format_run(run: Mapping[str, Any]) -> str:
    """Format one run (`GET /runs/{run_id}`) with its parameters and tasks."""
    status = str(run["status"])
    if run.get("error"):
        status += f" ({run['error']})"
    lines = [
        f"run: {run['run_id']}",
        f"pipeline: {_pipeline_label(run['pipeline'])}",
        f"status: {status}",
        f"backend: {run.get('backend', '')}" + (" (resume)" if run.get("resume") else ""),
        f"created: {format_time(run.get('created_at'))}",
        f"started: {format_time(run.get('started_at'))}",
        f"finished: {format_time(run.get('finished_at'))}",
        "params:",
    ]
    params = run.get("params") or {}
    lines += [f"  {key}={value}" for key, value in params.items()] or ["  (none)"]
    lines.append("tasks:")
    for task in run.get("tasks", []):
        line = f"  {task['name']} [{task['type']}] {task['status']}"
        if task.get("depends_on"):
            line += f", after {', '.join(task['depends_on'])}"
        if task.get("error"):
            line += f": {task['error']}"
        lines.append(line)
    if not run.get("tasks"):
        lines.append("  (none)")
    return "\n".join(lines)


def format_time(value: object) -> str:
    """Format an ISO 8601 time from the server as `YYYY-MM-DD HH:MM:SS UTC`; "-" if unset."""
    if not isinstance(value, str) or not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _pipeline_label(pipeline: Mapping[str, Any]) -> str:
    return f"{pipeline['name']} {pipeline['version']}"


def _task_counts(counts: Mapping[str, int]) -> str:
    """`succeeded 1, pending 3`: the non-zero task counts."""
    parts = [f"{status} {count}" for status, count in counts.items() if count]
    return ", ".join(parts) or "-"


if __name__ == "__main__":
    raise SystemExit(main())
