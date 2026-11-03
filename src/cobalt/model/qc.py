"""Quality-control model objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Only for annotations: cobalt.model.record imports this module
    from cobalt.model.record import AnalysisResult


class WarningKind(StrEnum):
    """Kinds of per-record problems found while reading a file."""

    DUPLICATE_ID = "duplicate_id"
    EMPTY_SEQUENCE = "empty_sequence"
    INVALID_CHARACTERS = "invalid_characters"
    UNDEFINED_SEQUENCE = "undefined_sequence"


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
    """Quality-control report of one `validate` input, shared by `validate --json`/`--report`
    and the REST API.

    `passed` is True when no warning was found. For an empty file `records_num` is 0 and
    `format` is None.
    """

    file: str
    records_num: int
    format: str | None
    compression: str | None
    passed: bool
    # Number of warnings per kind; every kind is present, zero if not found
    warning_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[RecordWarning] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the report as a plain, JSON-serializable dict."""
        return asdict(self)


def build_qc_report(file: str, result: AnalysisResult | None, compression: str | None) -> QCReport:
    """Build the QC report of `file` from its analysis result (None for an empty file)."""
    if result is None:
        return QCReport(
            file=file,
            records_num=0,
            format=None,
            compression=compression,
            passed=True,
            warning_counts={str(kind): 0 for kind in WarningKind},
        )
    return QCReport(
        file=file,
        records_num=result.records_num,
        format=result.type,
        compression=compression,
        passed=not result.warnings,
        warning_counts={str(kind): count for kind, count in result.warning_counts().items()},
        warnings=list(result.warnings),
    )
