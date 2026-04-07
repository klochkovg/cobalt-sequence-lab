"""CLI command: normalize."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build parser for normalize command."""
    parser = argparse.ArgumentParser(prog="cobalt normalize")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    parser.add_argument("--fasta", required=True, help="Output cleaned FASTA path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the normalize command.

    Stub implementation that only parses CLI args.
    """
    args = build_parser().parse_args(argv)
    print(f"[stub] normalize: {args.input} -> {args.fasta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
