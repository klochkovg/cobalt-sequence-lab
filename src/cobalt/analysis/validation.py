"""Validation analysis helpers."""

from __future__ import annotations

from collections.abc import Sequence

from cobalt.model.qc import RecordWarning


def print_warnings(warnings: Sequence[RecordWarning | str]) -> int:
    """Print already collected warnings to stdout and return their count."""
    for warning in warnings:
        print(f"warning: {warning}")
    print(f"{len(warnings)} warning(s) found")
    return len(warnings)


def validate_sequences() -> list[str]:
    """Validate sequence-level constraints.

    Stub implementation.
    """
    raise NotImplementedError("validate_sequences is not implemented yet")


def validate_metadata() -> list[str]:
    """Validate metadata constraints.

    Stub implementation.
    """
    raise NotImplementedError("validate_metadata is not implemented yet")
