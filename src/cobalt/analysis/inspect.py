"""Inspect Implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from Bio import SeqIO, SeqUtils
from Bio.Data import IUPACData
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.processor import process_records, read_file

DNA_LETTERS = set("ACGTN")
RNA_LETTERS = set("ACGUN")
PROTEIN_LETTERS = set(IUPACData.extended_protein_letters)

FASTA_SUFFIXES = {".fasta", ".fa", ".fna"}
GENBANK_SUFFIXES = {".gbk", ".gk", ".gp", "gpt"}

STATS_FIELDNAMES = ["id", 
                    "length", 
                    "description", 
                    "gc_fraction", 
                    "type", 
                    "source_format", 
                    "alphabetic_class",
                    "ambiguity_fraction",
                    "invalid_char_count"]


def find_warnings(records: list[SeqRecord]):
    """Return a list of warning strings: empty seqs, duplicate IDs, invalid chars."""
    warnings = []
    seen_ids = set()
    valid_chars = set(IUPACData.ambiguous_dna_letters + IUPACData.protein_letters)

    for record in records:
        if record.id in seen_ids:
            warnings.append(f"{record.id}: duplicate ID")
        if record.seq is None or len(record.seq) == 0:
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
    if letters <= PROTEIN_LETTERS:
        return "protein"
    return "unknown"


def check_file(path: Path) -> bool:
    """ "Checking the file is correct and exists"""
    if not path.is_file():
        print(f"error: file not found: {path}")
        return False
    if path.suffix.lower() not in (FASTA_SUFFIXES | GENBANK_SUFFIXES):
        print(
            f"error: unsupported extension {path.suffix!r}, expected ({', '.join(sorted(FASTA_SUFFIXES | GENBANK_SUFFIXES))})"
        )
        return False
    return True
