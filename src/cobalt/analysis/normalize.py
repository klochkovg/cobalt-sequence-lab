"""Normalizaiton helpers"""

from __future__ import annotations

from typing import Any


def uppercase_result(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """uppercase the sequence, naive approach for now
    No data copying, actual replacement
    """
    for record in records:
        sequence = record["sequence"]
        record["sequence"] = sequence.upper()
    return records
