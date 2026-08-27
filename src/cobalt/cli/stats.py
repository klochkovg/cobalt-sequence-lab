"""CLI command: stats."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys
from collections.abc import Sequence
from cobalt.analysis.inspect import read_file, FASTA_SUFFIXES, GENBANK_SUFFIXES, check_file

import csv
import json

from typing import TextIO


def build_parser() -> argparse.ArgumentParser:
    """Build parser for stats command."""
    parser = argparse.ArgumentParser(prog="cobalt stats")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    parser.add_argument("--out", required=False, help="Output stats file path")
    parser.add_argument(
        "--json", action="store_true", required=False, help="Output present as JSON"
    )
    return parser


def write_stats_csv(file: TextIO, records: dict) -> None:
    fieldnames = ["id", "length", "gc_fraction", "type"]
    writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow(record)


def write_stats_json(file: TextIO, records: dict) -> None:
    fieldnames = ["id", "length", "gc_fraction", "type"]
    filtered_records = [{name: record[name] for name in fieldnames} for record in records]
    json.dump(filtered_records, file, indent=2)


def write_stats(type: str, file: TextIO, records: dict) -> None:
    if type == "csv":
        write_stats_csv(file, records)
    elif type == "json":
        write_stats_json(file, records)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the stats command.
    In case of empty --out, input to stdout
    """
    args = build_parser().parse_args(argv)

    data_file_path = Path(args.input)
    output_type = "json" if args.json else "csv"
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
    if args.out:
        try:
            with open(args.out, "w", newline="") as f:
                write_stats(output_type, f, primary_result["records"])
        except IsADirectoryError:
            print(f"error: --out is a directory: {args.out}")
            return 1
        except FileNotFoundError:
            print(f"error: no such directory for --out: {args.out}")
            return 1
        except PermissionError:
            print(f"error: permission denied writing to: {args.out}")
            return 1
        except OSError as exc:
            print(f"error: could not write to {args.out}: {exc}")
            return 1
    else:
        write_stats(output_type, sys.stdout, primary_result["records"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
