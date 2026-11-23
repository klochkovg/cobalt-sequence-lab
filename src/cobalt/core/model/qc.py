"""Quality-control model objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Only for annotations: cobalt.core.model.record imports this module
    from cobalt.core.model.record import AnalysisResult


class WarningKind(StrEnum):
    """Kinds of per-record problems found while reading a file."""

    DUPLICATE_ID = "duplicate_id"
    EMPTY_SEQUENCE = "empty_sequence"
    INVALID_CHARACTERS = "invalid_characters"
    UNDEFINED_SEQUENCE = "undefined_sequence"


# Number of invalid character positions listed in InvalidCharactersDetails.first_positions
MAX_INVALID_POSITIONS = 10


@dataclass(frozen=True, slots=True)
class InvalidCharactersDetails:
    """Where an `invalid_characters` warning found its characters."""

    # Distinct invalid characters, sorted
    characters: tuple[str, ...]
    # Total number of invalid characters in the sequence
    count: int
    # 1-based positions of the first MAX_INVALID_POSITIONS invalid characters
    first_positions: tuple[int, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InvalidCharactersDetails:
        """Build the details from the dict produced by `dataclasses.asdict`."""
        return cls(
            characters=tuple(data["characters"]),
            count=data["count"],
            first_positions=tuple(data["first_positions"]),
        )


@dataclass(frozen=True, slots=True)
class RecordWarning:
    """A problem found in one record. `str()` gives the human-readable form.

    `details` is set for `invalid_characters` warnings only, and None for every other kind.
    """

    record_id: str
    kind: WarningKind
    message: str
    details: InvalidCharactersDetails | None = None

    def __str__(self) -> str:
        return f"{self.record_id}: {self.message}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecordWarning:
        """Build a warning from the dict produced by `dataclasses.asdict`."""
        return cls(
            record_id=data["record_id"],
            kind=WarningKind(data["kind"]),
            message=data["message"],
            details=(
                InvalidCharactersDetails.from_dict(data["details"])
                if data.get("details") is not None
                else None
            ),
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
    # True when `max_warnings` left entries out of `warnings` (`warning_counts` still counts them)
    warnings_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the report as a plain, JSON-serializable dict."""
        return asdict(self)


def truncate_warnings(
    warnings: list[RecordWarning], max_warnings: int | None
) -> tuple[list[RecordWarning], bool]:
    """Return the first `max_warnings` warnings (all of them for None) and whether any were cut."""
    if max_warnings is None or len(warnings) <= max_warnings:
        return list(warnings), False
    return warnings[:max_warnings], True


def build_qc_report(
    file: str,
    result: AnalysisResult | None,
    compression: str | None,
    max_warnings: int | None = None,
) -> QCReport:
    """Build the QC report of `file` from its analysis result (None for an empty file).

    `warnings` holds at most `max_warnings` entries (all for None).
    """
    if result is None:
        return QCReport(
            file=file,
            records_num=0,
            format=None,
            compression=compression,
            passed=True,
            warning_counts={str(kind): 0 for kind in WarningKind},
        )
    warnings, truncated = truncate_warnings(result.warnings, max_warnings)
    return QCReport(
        file=file,
        records_num=result.records_num,
        format=result.type,
        compression=compression,
        passed=not result.warnings,
        warning_counts={str(kind): count for kind, count in result.warning_counts().items()},
        warnings=warnings,
        warnings_truncated=truncated,
    )
