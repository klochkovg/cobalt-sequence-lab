"""Statistics data structures and helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RecordStats:
    """Basic stats for a sequence collection."""

    n_records: int
    min_length: int
    max_length: int
    mean_length: float


def compute_record_stats(lengths: list[int]) -> RecordStats:
    """Compute length-based stats for records.

    Stub implementation.
    """
    raise NotImplementedError("compute_record_stats is not implemented yet")
