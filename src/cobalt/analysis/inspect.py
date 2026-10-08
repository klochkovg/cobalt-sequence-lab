"""Inspect Implementation."""

from __future__ import annotations

import logging
from pathlib import Path

from Bio.Data import IUPACData
from Bio.SeqRecord import SeqRecord

log = logging.getLogger(__name__)

# Letters accepted by guess_molecule_type, ambiguity codes included
DNA_LETTERS = set(IUPACData.ambiguous_dna_letters)
RNA_LETTERS = set(IUPACData.ambiguous_rna_letters)
PROTEIN_LETTERS = set(IUPACData.extended_protein_letters)
# Plain nucleotides; N counts too, as it is the usual "unknown base" filler
CORE_NUCLEOTIDES = set("ACGTUN")
# Minimal share of core nucleotides for a sequence to be called DNA/RNA.
# Most protein letters (M, K, V, R, ...) are also nucleotide ambiguity codes,
# so the alphabet alone can't tell a short peptide from an ambiguous DNA.
MIN_CORE_NUCLEOTIDE_FRACTION = 0.75

FASTA_SUFFIXES = {".fasta", ".fa", ".fna"}
GENBANK_SUFFIXES = {".gb", ".gbk", ".genbank", ".gp", ".gpt"}

STATS_FIELDNAMES = [
    "id",
    "length",
    "description",
    "gc_fraction",
    "type",
    "source_format",
    "alphabetic_class",
    "ambiguity_fraction",
    "invalid_char_count",
]


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


def guess_molecule_type(seq) -> str:
    """Guess the molecule type ("DNA", "RNA", "protein" or "unknown") from sequence letters.

    A sequence is a nucleotide one when all its letters are IUPAC nucleotide codes and
    at least MIN_CORE_NUCLEOTIDE_FRACTION of them are A/C/G/T/U/N; RNA when it has U
    and no T. Otherwise it is a protein if all letters are (extended) amino acids.
    """
    seq_str = str(seq).upper()
    if not seq_str:
        return "unknown"
    letters = set(seq_str)
    core_fraction = sum(1 for c in seq_str if c in CORE_NUCLEOTIDES) / len(seq_str)
    if core_fraction >= MIN_CORE_NUCLEOTIDE_FRACTION:
        if letters <= DNA_LETTERS:
            return "DNA"
        if letters <= RNA_LETTERS:
            return "RNA"
    if letters <= PROTEIN_LETTERS:
        return "protein"
    return "unknown"


def canonical_molecule_type(value: str | None) -> str | None:
    """Map a GenBank molecule_type annotation ("mRNA", "ss-DNA", ...) to DNA/RNA/protein.

    Returns None for a missing or unrecognized value.
    """
    if not value:
        return None
    upper = value.upper()
    if "DNA" in upper:
        return "DNA"
    if "RNA" in upper:
        return "RNA"
    if upper in {"PROTEIN", "AA"}:
        return "protein"
    return None


def check_file(path: Path) -> bool:
    """ "Checking the file is correct and exists"""
    if not path.is_file():
        log.error("file not found: %s", path)
        return False
    if path.suffix.lower() not in (FASTA_SUFFIXES | GENBANK_SUFFIXES):
        log.error(
            "unsupported extension %r, expected (%s)",
            path.suffix,
            ", ".join(sorted(FASTA_SUFFIXES | GENBANK_SUFFIXES)),
        )
        return False
    return True
