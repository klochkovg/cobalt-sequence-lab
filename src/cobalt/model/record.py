"""Core record model objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SequenceRecord:
    """Simple sequence record container."""

    id: str
    description: str
    length: int
    sequence: str
    gc_fraction: float
    ambiguity_fraction: float
    invalid_char_count: int
    alphabetic_class: str
    source_format: str
    type: str
    feature_count: int = 0
    organism: str | None = None
    molecule_type: str | None = None
    topology: str | None = None
    quality: str | None = None

@dataclass(slots=True)
class AnalysisResult:
    """Simple result of multisequence file analysis"""

    warnings: list[str]
    records_num: int
    min: int
    max: int
    mean: float
    type: str

def validate_record(record: SequenceRecord) -> list[str]:
    """Validate record fields and return a list of issues.

    Stub implementation.
    """
    raise NotImplementedError("validate_record is not implemented yet")
