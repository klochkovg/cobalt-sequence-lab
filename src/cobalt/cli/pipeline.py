"""CLI command: pipeline (stub, `check` and `graph` are not implemented yet)."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for pipeline command."""
    parser = argparse.ArgumentParser(prog="cobalt pipeline")
    subparsers = parser.add_subparsers(dest="action", required=True)
    check = subparsers.add_parser(
        "check", help="Validate the pipeline schema and DAG, without execution"
    )
    check.add_argument("pipeline", help="Pipeline definition (YAML)")
    graph = subparsers.add_parser("graph", help="Print the pipeline DAG")
    graph.add_argument("pipeline", help="Pipeline definition (YAML)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the pipeline command."""
    args = build_parser().parse_args(argv)
    log.debug("pipeline %s %s", args.action, args.pipeline)
    log.error("cobalt pipeline %s is not implemented yet", args.action)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
