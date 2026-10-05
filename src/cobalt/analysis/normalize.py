"""Normalizaiton helpers"""

from __future__ import annotations

from cobalt.model.record import SequenceRecord


def uppercase_result(records: list[SequenceRecord]) -> list[SequenceRecord]:
    """uppercase the sequence, naive approach for now
    No data copying, actual replacement
    """
    for record in records:
        record.sequence = record.sequence.upper()
    return records
