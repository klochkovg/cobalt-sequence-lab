"""Quality-control model objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WarningKind(StrEnum):
    """Kinds of per-record problems found while reading a file."""

    DUPLICATE_ID = "duplicate_id"
    EMPTY_SEQUENCE = "empty_sequence"
    INVALID_CHARACTERS = "invalid_characters"


@dataclass(frozen=True, slots=True)
class RecordWarning:
    """A problem found in one record. `str()` gives the human-readable form."""

    record_id: str
    kind: WarningKind
    message: str

    def __str__(self) -> str:
        return f"{self.record_id}: {self.message}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecordWarning:
        """Build a warning from the dict produced by `dataclasses.asdict`."""
        return cls(
            record_id=data["record_id"],
            kind=WarningKind(data["kind"]),
            message=data["message"],
        )


@dataclass(slots=True)
class QCReport:
    """Quality control report."""

    passed: bool
    issues: list[str] = field(default_factory=list)


def run_qc_checks() -> QCReport:
    """Run quality checks and return a report.

    Stub implementation.
    """
    raise NotImplementedError("run_qc_checks is not implemented yet")
