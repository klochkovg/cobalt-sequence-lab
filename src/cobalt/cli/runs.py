"""CLI command: runs (stub, `list` and `show` are not implemented yet)."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for runs command."""
    parser = argparse.ArgumentParser(prog="cobalt runs")
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("list", help="List past runs from their manifests")
    show = subparsers.add_parser("show", help="Show provenance for one run")
    show.add_argument("run_id", help="Run identifier, as printed by 'cobalt runs list'")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the runs command."""
    args = build_parser().parse_args(argv)
    log.debug("runs %s %s", args.action, getattr(args, "run_id", ""))
    log.error("cobalt runs %s is not implemented yet", args.action)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
