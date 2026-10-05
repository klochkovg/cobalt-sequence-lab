"""CLI command: normalize."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.inspect import FASTA_SUFFIXES, GENBANK_SUFFIXES, check_file
from cobalt.analysis.normalize import uppercase_result
from cobalt.analysis.processor import read_file


def build_parser() -> argparse.ArgumentParser:
    """Build parser for normalize command."""
    parser = argparse.ArgumentParser(prog="cobalt normalize")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    parser.add_argument("--fasta", required=True, help="Output cleaned FASTA path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the normalize command.

    Reads the input file, uppercases every sequence and writes the result as FASTA.
    """
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
        print(f"{data_file_path}: 0 records")
        return 0

    records = uppercase_result(primary_result.records)
    seq_records = [
        SeqRecord(Seq(record.sequence), id=record.id, description=record.description)
        for record in records
    ]
    try:
        with open(args.fasta, "w") as f:
            SeqIO.write(seq_records, f, "fasta")
    except OSError as exc:
        print(f"error: could not write to {args.fasta}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
