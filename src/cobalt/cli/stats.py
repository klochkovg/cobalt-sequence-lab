"""CLI command: stats."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys
from collections.abc import Sequence
from cobalt.analysis.inspect import read_file, FASTA_SUFFIXES, GENBANK_SUFFIXES, check_file

import csv

from typing import TextIO

def build_parser() -> argparse.ArgumentParser:
    """Build parser for stats command."""
    parser = argparse.ArgumentParser(prog="cobalt stats")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    parser.add_argument("--out", required=False, help="Output stats file path")
    return parser

def print_record(file: TextIO, record: dict) -> None:
    file.write(f"Sequence name   : {record['id']}")
    file.write(f"Sequence length : {record['length']}")
    file.write(f"Sequence        : {repr(record['sequence'])}")
    file.write(f"GC fraction     : {repr(record['gc_fraction'])}")
    file.write(f"Type guess      : {record['type']}")


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the stats command.
    In case of empty --out, input to stdout
    """
    args = build_parser().parse_args(argv)
    output = args.out if args.out else sys.stdout

    data_file_path = Path(args.input)

    if not check_file(data_file_path):
        return 1
    primary_result = []
    if path.suffix.lower() in FASTA_SUFFIXES:
        primary_result = read_file(path, "fasta")
    if path.suffix.lower() in GENBANK_SUFFIXES:
        primary_result = read_file(path, "genbank")
    if not primary_result:
        print(f"{path}: 0 records")
        return 0    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
