"""Output writers for cobalt sequence data."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


def write_records(records: Iterable[dict[str, Any]], path: str | Path) -> None:
    """Write `records` to `path`.

    Stub implementation.
    """
    raise NotImplementedError("write_records is not implemented yet")


def write_summary(summary: dict[str, Any], path: str | Path) -> None:
    """Write analysis summary to `path`.

    Stub implementation.
    """
    raise NotImplementedError("write_summary is not implemented yet")
