"""CLI command: stats."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build parser for stats command."""
    parser = argparse.ArgumentParser(prog="cobalt stats")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    parser.add_argument("--out", required=True, help="Output stats file path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the stats command.

    Stub implementation that only parses CLI args.
    """
    args = build_parser().parse_args(argv)
    print(f"[stub] stats: {args.input} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
