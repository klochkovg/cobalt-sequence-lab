"""CLI command: validate."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from cobalt.analysis.processor import InputFileError, load_file
from cobalt.analysis.validation import print_warnings
from cobalt.cli.stats import write_stats_csv
from cobalt.io.sniff import sniff_compression
from cobalt.model.qc import QCReport, build_qc_report
from cobalt.model.stats import build_stats_rows

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for validate command."""
    parser = argparse.ArgumentParser(prog="cobalt validate")
    parser.add_argument("input", help="Input FASTA/GenBank/FASTQ file (plain, gzip or bzip2)")
    parser.add_argument("--report", required=False, help="JSON QC report output path")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the JSON QC report to stdout (the format of the REST API)",
    )
    parser.add_argument(
        "--warnings",
        action="store_true",
        help="Print only warnings (empty or undefined sequences, duplicate IDs, "
        "invalid characters) to stdout",
    )
    return parser


def write_qc_report(file: TextIO, report: QCReport) -> None:
    """Write the QC report as indented JSON."""
    json.dump(report.to_dict(), file, indent=2)
    file.write("\n")


def save_qc_report(path: str, report: QCReport) -> bool:
    """Write the QC report to `path`; log the error and return False if it can't be written."""
    try:
        with open(path, "w") as f:
            write_qc_report(f, report)
    except IsADirectoryError:
        log.error("--report is a directory: %s", path)
    except FileNotFoundError:
        log.error("no such directory for --report: %s", path)
    except PermissionError:
        log.error("permission denied writing to: %s", path)
    except OSError as exc:
        log.error("could not write to %s: %s", path, exc)
    else:
        return True
    return False


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the validate command.

    `--report` writes the JSON QC report to a file. On stdout, `--json` prints the QC report,
    `--warnings` the warnings as text; without either (and without `--report`) the stats table
    is printed as CSV.
    """
    args = build_parser().parse_args(argv)
    data_file_path = Path(args.input)

    try:
        primary_result = load_file(data_file_path)
    except InputFileError as exc:
        log.error("%s", exc)
        return 1
    if args.json or args.report:
        report = build_qc_report(
            str(data_file_path), primary_result, sniff_compression(data_file_path)
        )
        if args.report and not save_qc_report(args.report, report):
            return 1
        if args.json:
            write_qc_report(sys.stdout, report)
            return 0
    if not primary_result:
        log.warning("%s: 0 records", data_file_path)
        return 0
    if args.warnings:
        print_warnings(primary_result.warnings)
    elif not args.report:
        write_stats_csv(sys.stdout, build_stats_rows(primary_result.records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
