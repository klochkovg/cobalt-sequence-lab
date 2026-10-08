"""CLI command: validate."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from cobalt.analysis.inspect import FASTA_SUFFIXES, GENBANK_SUFFIXES, check_file
from cobalt.analysis.processor import read_file
from cobalt.analysis.validation import print_warnings
from cobalt.cli.stats import write_stats_csv
from cobalt.model.stats import build_stats_rows

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for validate command."""
    parser = argparse.ArgumentParser(prog="cobalt validate")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    parser.add_argument("--report", required=False, help="JSON report output path")
    parser.add_argument(
        "--warnings",
        action="store_true",
        help="Print only warnings (empty sequences, duplicate IDs, invalid characters) to stdout",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the validate command."""
    args = build_parser().parse_args(argv)
    data_file_path = Path(args.input)

    if not check_file(data_file_path):
        return 1
    primary_result = None
    if data_file_path.suffix.lower() in FASTA_SUFFIXES:
        primary_result = read_file(data_file_path, "fasta")
    if data_file_path.suffix.lower() in GENBANK_SUFFIXES:
        primary_result = read_file(data_file_path, "genbank")
    if not primary_result:
        log.warning("%s: 0 records", data_file_path)
        return 0
    if args.warnings:
        print_warnings(primary_result.warnings)
        return 0
    if args.report:
        try:
            with open(args.report, "w", newline="") as f:
                write_stats_csv(f, build_stats_rows(primary_result.records))
                # TODO temporary for infrastructure testing
                # later replace with correct call
        except IsADirectoryError:
            log.error("--report is a directory: %s", args.report)
            return 1
        except FileNotFoundError:
            log.error("no such directory for --report: %s", args.report)
            return 1
        except PermissionError:
            log.error("permission denied writing to: %s", args.report)
            return 1
        except OSError as exc:
            log.error("could not write to %s: %s", args.report, exc)
            return 1
    else:
        write_stats_csv(sys.stdout, build_stats_rows(primary_result.records))
        # TODO the same as above
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
