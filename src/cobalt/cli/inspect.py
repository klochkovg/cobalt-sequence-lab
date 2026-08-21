"""CLI command: inspect."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from Bio import SeqUtils

from Bio import SeqIO
from Bio.Data import IUPACData


from cobalt.analysis.inspect import read_file, FASTA_SUFFIXES, GENBANK_SUFFIXES


def build_parser() -> argparse.ArgumentParser:
    """Build parser for inspect command."""
    parser = argparse.ArgumentParser(prog="cobalt inspect")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    parser.add_argument(
        "--overview-only",
        action="store_true",
        help="Print only the record count, skip length/GC stats",
    )
    parser.add_argument(
        "--output-seq-number", type=int, default=-1, help="Number of sequences int output"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the inspect command.
    Checks that the input file exists and is a FASTA file, then
    reports the number of records inside
    """
    args = build_parser().parse_args(argv)
    path = Path(args.input)

    if not path.is_file():
        print(f"error: file not found: {path}")
        return 1

    if path.suffix.lower() not in (FASTA_SUFFIXES | GENBANK_SUFFIXES):
        print(
            f"error: unsupported extension {path.suffix!r}, expected ({', '.join(sorted(FASTA_SUFFIXES | GENBANK_SUFFIXES))})"
        )
        return 1
    primary_result = []
    if path.suffix.lower() in FASTA_SUFFIXES:
        primary_result = read_file(path, "fasta")
    if path.suffix.lower() in GENBANK_SUFFIXES:
        primary_result = read_file(path, "genbank")
    if not primary_result:
        print(f"{path}: 0 records")
        return 0
    print(f"{path}: {primary_result['records_num']} record(s)")
    print(
        f" length: min={primary_result['min']}  max={primary_result['max']}  mean={primary_result['mean']:.1f}"
    )
    print(f"Number of warnings {len(primary_result['warnings'])}")
    if len(primary_result["warnings"]) > 0:
        for warning in primary_result["warnings"]:
            print(f"     {warning}")
    print("--------------------------------------------------------------------------------------")
    if args.overview_only:
        return 0
    number_of_sequences = args.output_seq_number
    counter = 0
    result_array = []
    for record in primary_result["records"]:
        counter = counter + 1
        if counter > number_of_sequences and number_of_sequences != -1:
            break
        print(f"Sequence name   : {record['id']}")
        print(f"Sequence length : {record['length']}")
        print(f"Sequence        : {repr(record['sequence'])}")
        print(f"GC fraction     : {repr(record['gc_fraction'])}")
        print(f"Type guess      : {record['type']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
