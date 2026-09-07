""" Cli command: serve."""


from __future__ import annotations

import argparse
from collections.abc import Sequence


from cobalt.analysis.inspect import read_file, FASTA_SUFFIXES, GENBANK_SUFFIXES, check_file


def build_parser() -> argparse.ArgumentParser:
    """Build parser for serve command."""
    parser = argparse.ArgumentParser(prog="cobalt serve")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the serve command.
    STUB
    """
    print("Stub serve command")
    args = build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
