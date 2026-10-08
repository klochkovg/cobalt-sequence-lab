"""CLI command: stats."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.inspect import FASTA_SUFFIXES, GENBANK_SUFFIXES, check_file
from cobalt.analysis.processor import process_records, read_file
from cobalt.model.stats import STATS_FIELDNAMES, SortKey, StatsRow, build_stats_rows

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for stats command."""
    parser = argparse.ArgumentParser(prog="cobalt stats")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("input", nargs="?", default=None, help="Input FASTA/GenBank file")
    source.add_argument(
        "--input",
        dest="raw_sequence",
        metavar="SEQ",
        help="Direct sequence string, e.g. --input AGCGCA",
    )

    parser.add_argument("--out", required=False, help="Output stats file path")
    parser.add_argument(
        "--json", action="store_true", required=False, help="Output present as JSON"
    )
    parser.add_argument(
        "--sort",
        choices=[key.value for key in SortKey],
        help="Sort rows by this column (default: input order)",
    )
    parser.add_argument("--desc", action="store_true", help="Sort in descending order")
    return parser


def write_stats_csv(file: TextIO, rows: list[StatsRow]) -> None:
    """Write rows as CSV; None values become empty cells."""
    writer = csv.DictWriter(file, fieldnames=STATS_FIELDNAMES)
    writer.writeheader()
    for row in rows:
        writer.writerow(row.to_dict())


def write_stats_json(file: TextIO, rows: list[StatsRow]) -> None:
    """Write rows as a JSON array; None values become null."""
    json.dump([row.to_dict() for row in rows], file, indent=2)


def write_stats(type: str, file: TextIO, rows: list[StatsRow]) -> None:
    if type == "csv":
        write_stats_csv(file, rows)
    elif type == "json":
        write_stats_json(file, rows)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the stats command.
    In case of empty --out, input to stdout
    """
    args = build_parser().parse_args(argv)

    if args.raw_sequence is not None:
        record = SeqRecord(Seq(args.raw_sequence), id="direct_input")
        primary_result = process_records([record], "raw")
    else:
        data_file_path = Path(args.input)
        if not check_file(data_file_path):
            return 1
        primary_result = None
        if data_file_path.suffix.lower() in FASTA_SUFFIXES:
            primary_result = read_file(data_file_path, "fasta")
        if data_file_path.suffix.lower() in GENBANK_SUFFIXES:
            primary_result = read_file(data_file_path, "genbank")

    if not primary_result:
        source = "direct input" if args.raw_sequence is not None else args.input
        log.warning("%s: 0 records", source)
        return 0

    sort = SortKey(args.sort) if args.sort else None
    rows = build_stats_rows(primary_result.records, sort=sort, descending=args.desc)
    output_type = "json" if args.json else "csv"
    if args.out:
        try:
            with open(args.out, "w", newline="") as f:
                write_stats(output_type, f, rows)
        except IsADirectoryError:
            log.error("--out is a directory: %s", args.out)
            return 1
        except FileNotFoundError:
            log.error("no such directory for --out: %s", args.out)
            return 1
        except PermissionError:
            log.error("permission denied writing to: %s", args.out)
            return 1
        except OSError as exc:
            log.error("could not write to %s: %s", args.out, exc)
            return 1
    else:
        write_stats(output_type, sys.stdout, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
