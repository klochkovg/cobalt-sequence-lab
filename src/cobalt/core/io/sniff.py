"""File format sniffing helpers.

The format is detected from the leading symbols of the content, not from the file extension:
a FASTA file starts with `>`, a GenBank file with `LOCUS`, a FASTQ file with `@` and has `+` on
the third line, a PDB file with a PDB record name (`HEADER`, `ATOM`, ...) and an mmCIF file with
`data_`. gzip and bzip2 compressed files are recognized by their magic bytes and
decompressed transparently.
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
# Record names a PDB file can start with: full files begin with HEADER, files written by
# modelling and prediction tools often begin with REMARK, MODEL or ATOM directly
PDB_RECORD_NAMES = frozenset(
    {
        "HEADER",
        "OBSLTE",
        "TITLE",
        "SPLIT",
        "CAVEAT",
        "COMPND",
        "SOURCE",
        "KEYWDS",
        "EXPDTA",
        "AUTHOR",
        "REMARK",
        "SEQRES",
        "CRYST1",
        "MODEL",
        "ATOM",
        "HETATM",
    }
)


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

    Returns "fasta", "genbank", "fastq", "pdb-atom" or "cif-atom" (Biopython SeqIO format
    names), or None if the content is not recognized or the compressed data is corrupt (logged
    at debug level). A missing file raises FileNotFoundError.

    PDB and mmCIF files are read as one protein sequence per chain, built from the ATOM records,
    so files from structure prediction tools without SEQRES records give sequences too.

    FASTQ needs the `+` separator on the third line, so SAM headers (`@HD`, `@SQ`) are not
    taken for FASTQ; wrapped (multi-line) FASTQ records are not detected either.
    """
    try:
        with open_text(path) as handle:
            line = _first_content_line(handle)
            # Sequence and separator lines of a FASTQ record; "" past the end of the file
            following = [next(handle, ""), next(handle, "")]
    except FileNotFoundError:
        raise
    except (OSError, EOFError) as exc:
        log.debug("cannot read %s: %s", path, exc)
        return None

    fmt = None
    if line is not None:
        if line.startswith(">"):
            fmt = "fasta"
        elif line.startswith("LOCUS"):
            fmt = "genbank"
        elif line.startswith("@") and following[1].startswith("+"):
            fmt = "fastq"
        elif line[:6].rstrip() in PDB_RECORD_NAMES:
            # Record names fill columns 1-6, so "ATOMIC notes" is not taken for PDB
            fmt = "pdb-atom"
        elif line.startswith("data_"):
            fmt = "cif-atom"
    log.debug("%s: format=%s, compression=%s", path, fmt, sniff_compression(path))
    return fmt


def is_blank(path: str | Path) -> bool:
    """Return whether `path` has no content besides whitespace (decompressed if needed)."""
    with open_text(path) as handle:
        return not any(line.strip() for line in handle)


def is_supported(path: str | Path) -> bool:
    """Return whether the content of `path` is a supported sequence format."""
    return sniff_format(path) is not None
