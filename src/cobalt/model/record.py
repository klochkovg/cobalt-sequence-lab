"""Core record model objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SequenceRecord:
    """Simple sequence record container."""

    record_id: str
    sequence: str
    quality: str | None = None


def validate_record(record: SequenceRecord) -> list[str]:
    """Validate record fields and return a list of issues.

    Stub implementation.
    """
    raise NotImplementedError("validate_record is not implemented yet")
