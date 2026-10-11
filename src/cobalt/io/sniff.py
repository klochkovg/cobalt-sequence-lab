"""File format sniffing helpers.

The format is detected from the leading symbols of the content, not from the file extension:
a FASTA file starts with `>`, a GenBank file with `LOCUS`. gzip and bzip2 compressed files
are recognized by their magic bytes and decompressed transparently.
"""

from __future__ import annotations

import bz2
import gzip
import logging
from pathlib import Path
from typing import TextIO

log = logging.getLogger(__name__)

GZIP_MAGIC = b"\x1f\x8b"
BZIP2_MAGIC = b"BZh"
# Limit on leading blank lines skipped, so a huge blank file is never read in full
MAX_SNIFF_LINES = 100


def sniff_compression(path: str | Path) -> str | None:
    """Return "gzip" or "bzip2" from the file's magic bytes, None for an uncompressed file."""
    with open(path, "rb") as handle:
        head = handle.read(len(BZIP2_MAGIC))
    if head.startswith(GZIP_MAGIC):
        return "gzip"
    if head.startswith(BZIP2_MAGIC):
        return "bzip2"
    return None


def open_text(path: str | Path) -> TextIO:
    """Open `path` as text, decompressing gzip/bzip2 content transparently.

    A UTF-8 BOM is dropped and undecodable bytes are replaced, so binary junk never raises
    UnicodeDecodeError.
    """
    compression = sniff_compression(path)
    if compression == "gzip":
        return gzip.open(path, "rt", encoding="utf-8-sig", errors="replace")
    if compression == "bzip2":
        return bz2.open(path, "rt", encoding="utf-8-sig", errors="replace")
    return open(path, encoding="utf-8-sig", errors="replace")


def _first_content_line(handle: TextIO) -> str | None:
    """Return the first non-blank line within MAX_SNIFF_LINES lines, or None."""
    for _, line in zip(range(MAX_SNIFF_LINES), handle, strict=False):
        if line.strip():
            return line
    return None


def sniff_format(path: str | Path) -> str | None:
    """Infer the sequence format of `path` from its content.

    Returns "fasta" or "genbank" (Biopython SeqIO format names), or None if the content is
    not recognized or the compressed data is corrupt. A missing file raises FileNotFoundError.
    """
    try:
        with open_text(path) as handle:
            line = _first_content_line(handle)
    except FileNotFoundError:
        raise
    except (OSError, EOFError) as exc:
        log.warning("cannot read %s: %s", path, exc)
        return None

    fmt = None
    if line is not None:
        if line.startswith(">"):
            fmt = "fasta"
        elif line.startswith("LOCUS"):
            fmt = "genbank"
    log.debug("%s: format=%s, compression=%s", path, fmt, sniff_compression(path))
    return fmt


def is_supported(path: str | Path) -> bool:
    """Return whether the content of `path` is a supported sequence format."""
    return sniff_format(path) is not None
