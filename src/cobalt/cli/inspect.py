"""CLI command: inspect."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from Bio import SeqIO

FASTA_SUFFIXES = {".fasta", ".fa", ".fna"}


def build_parser() -> argparse.ArgumentParser:
    """Build parser for inspect command."""
    parser = argparse.ArgumentParser(prog="cobalt inspect")
    parser.add_argument("input", help="Input FASTA/GenBank file")
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

    if path.suffix.lower() not in FASTA_SUFFIXES:
        print(f"error: unsupported extension {path.suffix!r}, expected FASTA ({', '.join(sorted(FASTA_SUFFIXES))})")
        return 1

    lengths = [len(record.seq) for record in SeqIO.parse(path, "fasta")]

    if not lengths:
        print(f"{path}: 0 records")
        return 0

    print(f"{path}: {len(lengths)} record(s)")
    print(f" length: min={min(lengths)}  max={max(lengths)}  mean={sum(lengths) / len(lengths):.1f}")
    print("-----------------------------------------------------------------------------------------")

    for seq_record in SeqIO.parse(path, "fasta"):
        print(f"Sequence name   : {seq_record.id}")
        print(f"Sequence length : {len(seq_record)}")
        print(f"Sequence        : {repr(seq_record.seq)}")
        print()
    #print(f"{path}: {record_count} record(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
