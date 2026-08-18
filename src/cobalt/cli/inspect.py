"""CLI command: inspect."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from Bio import SeqUtils

from Bio import SeqIO

DNA_LETTERS = set("ACGTN")
RNA_LETTERS = set("ACGUN")

FASTA_SUFFIXES = {".fasta", ".fa", ".fna"}
GENBANK_SUFFIXES = {".gbk", ".gk", ".gp", "gpt"}




def guess_molecule_type(seq):
    """ Try to guess type of molecule by estimation presence of corresponding elements in the sequence """
    letters = set(str(seq).upper())
    if letters <= DNA_LETTERS:
        return "DNA"
    if letters <= RNA_LETTERS:
        return "RNA"
    return "protein"

def calculate_gc_fraction(seq):
    """ Returns estimation of GC fraction"""
    return SeqUtils.gc_fraction(seq)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for inspect command."""
    parser = argparse.ArgumentParser(prog="cobalt inspect")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    parser.add_argument(
        "--overview-only",
        action="store_true",
        help="Print only the record count, skip length/GC stats"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the inspect command.

    Checks that the input file exists and is a FASTA file, then
    reports the number of records inside

    Supposed functionality 
    Printing
    - number of records  DONE
    - guessed molecule types  : does it look like DNA or RNA or protein (ACGTN, ACGUN, Aminoacids)
    - min/max/mean length  DONE
    - formats detected  DONE
    - warning couts  : empty/duplicate IDs, 
    - GC fraction - Bio.SeqUtils.gc_fraction  DONE
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
    if args.overview_only:
        return 0

    for seq_record in SeqIO.parse(path, "fasta"):
        print(f"Sequence name   : {seq_record.id}")
        print(f"Sequence length : {len(seq_record)}")
        print(f"Sequence        : {repr(seq_record.seq)}")
        print(f"GC fraction     : {repr(calculate_gc_fraction(seq_record.seq))}")
        print(f"Type guess      : {guess_molecule_type(seq_record.seq)}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
