"""Main processing code."""

from __future__ import annotations

import logging

from Bio import SeqIO, SeqUtils
from Bio.Data import IUPACData
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.inspect import find_warnings, guess_molecule_type
from cobalt.model.record import AnalysisResult, SequenceRecord

log = logging.getLogger(__name__)


def calculate_gc_fraction(seq):
    """Returns estimation of GC fraction"""
    return SeqUtils.gc_fraction(seq)


VALID_DNA = set(IUPACData.ambiguous_dna_letters)
VALID_RNA = set(IUPACData.ambiguous_rna_letters)
VALID_PROTEIN = set(IUPACData.extended_protein_letters)


def invalid_char_count(seq_record: SeqRecord, type: str) -> int:
    """Calculate and return number of invalid symbols for the particular sequence"""
    if seq_record.seq is None:
        return 0
    seq_str = str(seq_record.seq).upper()
    valid_letters = {
        "DNA": VALID_DNA,
        "RNA": VALID_RNA,
        "protein": VALID_PROTEIN,
    }.get(type, set())
    return sum(1 for c in seq_str if c not in valid_letters)


AMBIGUOUS_DNA = set(IUPACData.ambiguous_dna_letters) - set(IUPACData.unambiguous_dna_letters)
AMBIGUOUS_RNA = set(IUPACData.ambiguous_rna_letters) - set(IUPACData.unambiguous_rna_letters)
AMBIGUOUS_PROTEIN = set(IUPACData.extended_protein_letters) - set(IUPACData.protein_letters)


def calculate_alphabet_class(seq, molecule_type) -> str:
    """Classify the sequence's alphabet relative to the IUPAC letter tiers.

    Returns "unambiguous" if every letter is in the strict (non-ambiguity-code)
    alphabet for `molecule_type`, "ambiguous" if it uses IUPAC ambiguity codes
    but nothing outside the valid alphabet, "invalid" if it contains characters
    outside the valid alphabet entirely, or "unknown" if the sequence is empty
    or `molecule_type` isn't recognized.
    """
    seq_str = str(seq).upper()
    if not seq_str:
        return "unknown"

    valid_letters = {
        "DNA": VALID_DNA,
        "RNA": VALID_RNA,
        "protein": VALID_PROTEIN,
    }.get(molecule_type)
    if valid_letters is None:
        return "unknown"

    ambiguity_letters = {
        "DNA": AMBIGUOUS_DNA,
        "RNA": AMBIGUOUS_RNA,
        "protein": AMBIGUOUS_PROTEIN,
    }[molecule_type]

    letters = set(seq_str)
    if letters - valid_letters:
        return "invalid"
    if letters & ambiguity_letters:
        return "ambiguous"
    return "unambiguous"


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


def read_file(path, type) -> AnalysisResult | None:
    """Provide some general information about records.
    What should be implemented:
    - number of records
    - guessed molecule types
    - min/max/mean length
    - formats detected
    - warning counts
    """

    records = list(SeqIO.parse(path, type))
    return process_records(records, type)


def annotation_str(seq_record: SeqRecord, key: str) -> str | None:
    """Return a record annotation as a string, or None if it is missing."""
    value = seq_record.annotations.get(key)
    return None if value is None else str(value)


def process_records(records: list[SeqRecord], type: str) -> AnalysisResult | None:
    lengths = [len(record.seq) if record.seq is not None else 0 for record in records]
    if not lengths:
        log.debug("no records to process")
        return None

    result_array = []
    for seq_record in records:
        seq_type = str(
            seq_record.annotations.get("molecule_type")
            if seq_record.annotations.get("molecule_type")
            else guess_molecule_type(seq_record.seq)
        )
        result = SequenceRecord(
            id=str(seq_record.id),
            description=seq_record.description,
            length=len(seq_record),
            sequence=str(seq_record.seq),
            gc_fraction=calculate_gc_fraction(seq_record.seq),
            ambiguity_fraction=calculate_ambiguity_fraction(seq_record.seq, seq_type),
            invalid_char_count=invalid_char_count(seq_record, seq_type),
            alphabetic_class=calculate_alphabet_class(seq_record, seq_type),
            source_format=type,
            type=seq_type,
            organism=annotation_str(seq_record, "organism"),
            molecule_type=annotation_str(seq_record, "molecule_type"),
            topology=annotation_str(seq_record, "topology"),
            feature_count=len(seq_record.features),
        )
        result_array.append(result)

    return AnalysisResult(
        warnings=find_warnings(records),
        records_num=len(lengths),
        min=min(lengths),
        max=max(lengths),
        mean=sum(lengths) / len(lengths),
        type=type,
        records=result_array,
    )
