"""CLI command: validate."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build parser for validate command."""
    parser = argparse.ArgumentParser(prog="cobalt validate")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    parser.add_argument("--report", required=True, help="JSON report output path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the validate command.

    Stub implementation that only parses CLI args.
    """
    args = build_parser().parse_args(argv)
    print(f"[stub] validate: {args.input} -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
