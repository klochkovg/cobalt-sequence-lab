"""Core record model objects."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from cobalt.model.qc import RecordWarning, WarningKind


@dataclass(slots=True)
class SequenceRecord:
    """Simple sequence record container."""

    id: str
    description: str
    length: int
    sequence: str
    gc_fraction: float | None
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SequenceRecord:
        """Build a record from a per-record dict as produced by processor.process_records."""
        return cls(
            id=data["id"],
            description=data["description"],
            length=int(data["length"]),
            sequence=str(data["sequence"]),
            gc_fraction=None if data["gc_fraction"] is None else float(data["gc_fraction"]),
            ambiguity_fraction=float(data["ambiguity_fraction"]),
            invalid_char_count=int(data["invalid_char_count"]),
            alphabetic_class=data["alphabetic_class"],
            source_format=data["source_format"],
            type=data["type"],
            feature_count=int(data.get("feature_count", 0)),
            organism=data.get("organism"),
            molecule_type=data.get("molecule_type"),
            topology=data.get("topology"),
            quality=data.get("quality"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the record as a plain dict."""
        return asdict(self)


@dataclass(slots=True)
class AnalysisResult:
    """Simple result of multisequence file analysis"""

    warnings: list[RecordWarning]
    records_num: int
    min: int
    max: int
    mean: float
    type: str
    records: list[SequenceRecord] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalysisResult:
        """Build a result from the dict returned by processor.process_records."""
        return cls(
            warnings=[RecordWarning.from_dict(w) for w in data["warnings"]],
            records_num=int(data["records_num"]),
            min=int(data["min"]),
            max=int(data["max"]),
            mean=float(data["mean"]),
            type=data["type"],
            records=[SequenceRecord.from_dict(r) for r in data.get("records", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the result as a plain dict, with records converted to dicts too."""
        return asdict(self)

    def type_counts(self) -> dict[str, int]:
        """Number of records per molecule type, most common first."""
        return dict(Counter(record.type for record in self.records).most_common())

    def warning_counts(self) -> dict[WarningKind, int]:
        """Number of warnings per kind; every kind is present, zero if not found."""
        counts = Counter(warning.kind for warning in self.warnings)
        return {kind: counts[kind] for kind in WarningKind}


def validate_record(record: SequenceRecord) -> list[str]:
    """Validate record fields and return a list of issues.

    Stub implementation.
    """
    raise NotImplementedError("validate_record is not implemented yet")
