"""File format sniffing helpers."""

from __future__ import annotations

from pathlib import Path


def sniff_format(path: str | Path) -> str:
    """Infer file format from `path`.

    Stub implementation.
    """
    raise NotImplementedError("sniff_format is not implemented yet")


def is_supported(path: str | Path) -> bool:
    """Return whether `path` appears to be a supported format.

    Stub implementation.
    """
    raise NotImplementedError("is_supported is not implemented yet")
