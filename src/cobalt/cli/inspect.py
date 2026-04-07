"""CLI command: inspect."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build parser for inspect command."""
    parser = argparse.ArgumentParser(prog="cobalt inspect")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the inspect command.

    Stub implementation that only parses CLI args.
    """
    args = build_parser().parse_args(argv)
    print(f"[stub] inspect: {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
