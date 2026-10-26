"""CLI command: run (stub, pipeline execution is not implemented yet)."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

log = logging.getLogger(__name__)

BACKENDS = ("local",)


def parse_param(value: str) -> tuple[str, str]:
    """Parse a `KEY=VALUE` pipeline parameter."""
    key, sep, param_value = value.partition("=")
    if not sep or not key:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {value!r}")
    return key, param_value


def build_parser() -> argparse.ArgumentParser:
    """Build parser for run command."""
    parser = argparse.ArgumentParser(prog="cobalt run")
    parser.add_argument("pipeline", help="Pipeline definition (YAML)")
    parser.add_argument(
        "--backend", choices=BACKENDS, default="local", help="Execution backend (default: local)"
    )
    parser.add_argument(
        "--param",
        action="append",
        type=parse_param,
        default=[],
        metavar="KEY=VALUE",
        help="Pipeline parameter, may be repeated (e.g. --param input=x.fasta)",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Reuse results of jobs completed in a previous run"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the run command."""
    args = build_parser().parse_args(argv)
    params = dict(args.param)
    log.debug(
        "run %s: backend=%s params=%s resume=%s", args.pipeline, args.backend, params, args.resume
    )
    log.error("cobalt run is not implemented yet")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
