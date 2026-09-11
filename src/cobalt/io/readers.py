"""Input readers for cobalt sequence data."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any


def read_records(path: str | Path) -> list[dict[str, Any]]:
    """Read records from `path`.

    Stub implementation.
    """
    raise NotImplementedError("read_records is not implemented yet")


def iter_records(path: str | Path) -> Iterable[dict[str, Any]]:
    """Iterate records from `path`.

    Stub implementation.
    """
    raise NotImplementedError("iter_records is not implemented yet")
