"""CLI command: validate."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
from cobalt.analysis.inspect import read_file, FASTA_SUFFIXES, GENBANK_SUFFIXES, check_file
from cobalt.cli.stats import write_stats_csv


def build_parser() -> argparse.ArgumentParser:
    """Build parser for validate command."""
    parser = argparse.ArgumentParser(prog="cobalt validate")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    parser.add_argument("--report", required=False, help="JSON report output path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the validate command."""
    args = build_parser().parse_args(argv)
    data_file_path = Path(args.input)

    if not check_file(data_file_path):
        return 1
    primary_result = {}
    if data_file_path.suffix.lower() in FASTA_SUFFIXES:
        primary_result = read_file(data_file_path, "fasta")
    if data_file_path.suffix.lower() in GENBANK_SUFFIXES:
        primary_result = read_file(data_file_path, "genbank")
    if not primary_result:
        print(f"{data_file_path}: 0 records")
        return 0
    if args.report:
        try:
            with open(args.report, "w", newline="") as f:
                write_stats_csv(f, primary_result["records"])
                # TODO temporary for infrastructure testing
                # later replace with correct call
        except IsADirectoryError:
            print(f"error: --out is a directory: {args.report}")
            return 1
        except FileNotFoundError:
            print(f"error: no such directory for --out: {args.report}")
            return 1
        except PermissionError:
            print(f"error: permission denied writing to: {args.report}")
            return 1
        except OSError as exc:
            print(f"error: could not write to {args.report}: {exc}")
            return 1
    else:
        write_stats_csv(sys.stdout, primary_result["records"])
        # TODO the same as above
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
