"""CLI command: inspect."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from Bio import SeqUtils

from Bio import SeqIO
from Bio.Data import IUPACData

DNA_LETTERS = set("ACGTN")
RNA_LETTERS = set("ACGUN")

FASTA_SUFFIXES = {".fasta", ".fa", ".fna"}
GENBANK_SUFFIXES = {".gbk", ".gk", ".gp", "gpt"}


def find_warnings(records):
    """Return a list of warning strings: empty seqs, duplicate IDs, invalid chars."""
    warnings = []
    seen_ids = set()
    valid_chars = set(IUPACData.ambiguous_dna_letters + IUPACData.protein_letters)

    for record in records:
        if len(record.seq) == 0:
            warnings.append(f"{record.id}: empty sequence")
    seen_ids.add(record.id)

    bad_chars = set(str(record.seq).upper()) - valid_chars
    if bad_chars:
        warnings.append(f"{record.id}: invalid characters {sorted(bad_chars)}")
    return warnings


def guess_molecule_type(seq):
    """Try to guess type of molecule by estimation presence of corresponding elements in the sequence"""
    letters = set(str(seq).upper())
    if letters <= DNA_LETTERS:
        return "DNA"
    if letters <= RNA_LETTERS:
        return "RNA"
    return "protein"


def calculate_gc_fraction(seq):
    """Returns estimation of GC fraction"""
    return SeqUtils.gc_fraction(seq)


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


def general_info(path) -> dict:
    lengths = [len(record.seq) for record in SeqIO.parse(path, "fasta")]
    if not lengths:
        print(f"{path}: 0 records")
        return {}

    records = list(SeqIO.parse(path, "fasta"))
    result = {
        "warnings": find_warnings(records),
        "records": records,
        "records_num": len(lengths),
        "min": min(lengths),
        "max": max(lengths),
        "mean": sum(lengths) / len(lengths),
    }
    return result


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
        print(
            f"error: unsupported extension {path.suffix!r}, expected FASTA ({', '.join(sorted(FASTA_SUFFIXES))})"
        )
        return 1

    primary_result = general_info(path)

    if not primary_result:
        print(f"{path}: 0 records")
        return 0
    print(f"{path}: {primary_result['records_num']} record(s)")
    print(
        f" length: min={primary_result['min']}  max={primary_result['max']}  mean={primary_result['mean']:.1f}"
    )
    print(f"Number of warnings {len(primary_result['warnings'])}")
    if len(primary_result["warnings"]) > 0:
        for warning in warnings:
            print(f"     {warning}")
    print("--------------------------------------------------------------------------------------")
    if args.overview_only:
        return 0
    number_of_sequences = args.output_seq_number
    counter = 0
    result_array = []
    for seq_record in primary_result["records"]:
        counter = counter + 1
        if counter > number_of_sequences and number_of_sequences != -1:
            break
        result = {
            "id": seq_record.id,
            "length": len(seq_record),
            "sequence": seq_record.seq,
            "gc_fraction": calculate_gc_fraction(seq_record.seq),
            "type": guess_molecule_type(seq_record.seq),
        }
        result_array.append(result)
        print(f"Sequence name   : {result['id']}")
        print(f"Sequence length : {result['length']}")
        print(f"Sequence        : {repr(result['sequence'])}")
        print(f"GC fraction     : {repr(result['gc_fraction'])}")
        print(f"Type guess      : {result['type']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
