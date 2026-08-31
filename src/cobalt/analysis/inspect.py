"""Inspect Implementation."""

from __future__ import annotations

from typing import Any


from Bio import SeqUtils

from Bio import SeqIO
from Bio.Data import IUPACData
from Bio.SeqRecord import SeqRecord
from pathlib import Path

DNA_LETTERS = set("ACGTN")
RNA_LETTERS = set("ACGUN")
PROTEIN_LETTERS = set(IUPACData.extended_protein_letters)

FASTA_SUFFIXES = {".fasta", ".fa", ".fna"}
GENBANK_SUFFIXES = {".gbk", ".gk", ".gp", "gpt"}


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


def calculate_gc_fraction(seq):
    """Returns estimation of GC fraction"""
    return SeqUtils.gc_fraction(seq)

VALID_DNA = set(IUPACData.ambiguous_dna_letters)
VALID_RNA = set(IUPACData.ambiguous_rna_letters)
VALID_PROTEIN = set(IUPACData.extended_protein_letters)


def invalid_char_count(seq_record: SeqRecord, type: str) -> str:
    """Calculate and return number of invalid symbols for the particular sequence"""
    if seq_record.seq is None:
        return "0"
    seq_str = str(seq_record.seq).upper()
    valid_letters = {
        "DNA": VALID_DNA,
        "RNA": VALID_RNA,
        "protein": VALID_PROTEIN,
    }.get(type, set())
    return str(sum(1 for c in seq_str if c not in valid_letters))

AMBIGUOUS_DNA = set(IUPACData.ambiguous_dna_letters) - set(IUPACData.unambiguous_dna_letters)
AMBIGUOUS_RNA = set(IUPACData.ambiguous_rna_letters) - set(IUPACData.unambiguous_rna_letters)
AMBIGUOUS_PROTEIN = set(IUPACData.extended_protein_letters) - set(IUPACData.protein_letters)


def calculate_ambiguity_fraction(seq, molecule_type):
    seq_str = str(seq).upper()
    if not seq_str:
        return 0.0
    ambiguity_letters = {
        "DNA": AMBIGUOUS_DNA,
        "RNA": AMBIGUOUS_RNA,
        "protein": AMBIGUOUS_PROTEIN,
    }.get(molecule_type, set())
    ambiguous_count = sum(1 for c in seq_str if c in ambiguity_letters)
    return ambiguous_count / len(seq_str)


def read_file(path, type) -> dict[str, Any]:
    """Provide some general information about records.
    What should be implemented:
    - number of records
    - guessed molecule types
    - min/max/mean length
    - formats detected
    - warning counts
    """

    records = list(SeqIO.parse(path, type))
    return process_records(records)


def process_records(records: list[SeqRecord]) -> dict[str, Any]:
    lengths = [len(record.seq) if record.seq is not None else 0 for record in records]
    if not lengths:
        print("0 records")
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
        seq_type = str(
            seq_record.annotations.get("molecule_type")
            if seq_record.annotations.get("molecule_type")
            else guess_molecule_type(seq_record.seq)
        )
        result = {
            "id": seq_record.id,
            "description": seq_record.description,
            "length": len(seq_record),
            "sequence": seq_record.seq,
            "gc_fraction": calculate_gc_fraction(seq_record.seq),
            "ambiguity_fraction": calculate_ambiguity_fraction(seq_record.seq, seq_type),
            "invalid_char_count": invalid_char_count(seq_record, seq_type),
            "type": seq_type,
            "organism": seq_record.annotations.get("organism"),
            "molecule_type": seq_record.annotations.get("molecule_type"),
            "topology": seq_record.annotations.get("topology"),
            "feature_count": len(seq_record.features),
        }
        result_array.append(result)
    primary_result["records"] = result_array
    return primary_result
