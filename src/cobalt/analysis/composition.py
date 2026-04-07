"""Base composition analysis."""

from __future__ import annotations

from typing import Mapping


def compute_base_composition(sequence: str) -> Mapping[str, float]:
    """Compute base composition for a sequence.

    Stub implementation.
    """
    raise NotImplementedError("compute_base_composition is not implemented yet")


def compute_gc_content(sequence: str) -> float:
    """Compute GC fraction for a sequence.

    Stub implementation.
    """
    raise NotImplementedError("compute_gc_content is not implemented yet")
