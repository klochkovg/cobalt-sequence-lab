"""CLI command: runs (stub). Lists and shows runs on a cobalt server, so it needs client mode;
in local (CLI) mode it is unsupported, and in client mode it is not implemented yet."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from cobalt.cli.run import report_server_only

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for runs command."""
    parser = argparse.ArgumentParser(
        prog="cobalt runs",
        description="List or show pipeline runs on a cobalt server "
        "(needs --server URL or $COBALT_SERVER)",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("list", help="List past runs from their manifests")
    show = subparsers.add_parser("show", help="Show provenance for one run")
    show.add_argument("run_id", help="Run identifier, as printed by 'cobalt runs list'")
    return parser


def main(argv: Sequence[str] | None = None, server: str | None = None) -> int:
    """Entry point for the runs command; `server` is the server URL, None in local (CLI) mode."""
    args = build_parser().parse_args(argv)
    log.debug("runs %s %s", args.action, getattr(args, "run_id", ""))
    return report_server_only(f"runs {args.action}", server)


if __name__ == "__main__":
    raise SystemExit(main())
