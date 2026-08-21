"""Inspect Implementation."""

from __future__ import annotations

from typing import Any


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


def read_file(path, type) -> dict:
    records = list(SeqIO.parse(path, type))

    lengths = [len(record.seq) for record in records]
    if not lengths:
        print(f"{path}: 0 records")
        return {}

    primary_result = {
        "warnings": find_warnings(records),
        "records_num": len(lengths),
        "min": min(lengths),
        "max": max(lengths),
        "mean": sum(lengths) / len(lengths),
    }

    result_array = []
    for seq_record in records:
        result = {
            "id": seq_record.id,
            "length": len(seq_record),
            "sequence": seq_record.seq,
            "gc_fraction": calculate_gc_fraction(seq_record.seq),
            "type": guess_molecule_type(seq_record.seq),
        }
        result_array.append(result)
    primary_result['records'] = result_array
    return primary_result


def inspect_records() -> dict[str, Any]:
    """Provide some general information about records.
       What should be implemented:
       - number of records
       - guessed molecule types
       - min/max/mean length
       - formats detected
       - warning counts

    Stub implementation.
    """

    raise NotImplementedError("summarize_records is not implemented yet")
