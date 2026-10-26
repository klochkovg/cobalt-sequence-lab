"""CLI command: pipeline (check a pipeline definition or print its DAG)."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from cobalt.pipeline import PipelineFileError, load_pipeline
from cobalt.pipeline.render import format_graph, format_structure

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for pipeline command."""
    parser = argparse.ArgumentParser(prog="cobalt pipeline")
    subparsers = parser.add_subparsers(dest="action", required=True)
    check = subparsers.add_parser(
        "check", help="Validate the pipeline schema and DAG and print its structure"
    )
    check.add_argument("pipeline", help="Pipeline definition (YAML)")
    graph = subparsers.add_parser("graph", help="Print the pipeline DAG")
    graph.add_argument("pipeline", help="Pipeline definition (YAML)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the pipeline command."""
    args = build_parser().parse_args(argv)
    path = Path(args.pipeline)
    try:
        pipeline = load_pipeline(path)
    except PipelineFileError as exc:
        log.error("%s", exc)
        return 1
    log.info(
        "%s: pipeline %s %s, %d tasks",
        path,
        pipeline.info.name,
        pipeline.info.version,
        len(pipeline.tasks),
    )
    if args.action == "check":
        print(format_structure(pipeline))
    else:
        print(format_graph(pipeline))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
