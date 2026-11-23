"""Uploaded files: read them as the CLI reads local files and build the endpoint results."""

from __future__ import annotations

import bz2
import gzip
import logging
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from fastapi import HTTPException, UploadFile, status
from fastapi.exceptions import RequestValidationError

from cobalt.core.analysis.normalize import (
    OutputFormat,
    build_seq_records,
    records_for_format,
    write_records_text,
)
from cobalt.core.analysis.processor import InputFileError, load_file, process_records
from cobalt.core.io.sniff import sniff_compression
from cobalt.core.model.inspect import InspectReport, build_inspect_report
from cobalt.core.model.qc import QCReport, build_qc_report
from cobalt.core.model.record import AnalysisResult, SequenceRecord
from cobalt.core.model.stats import SortKey, StatsRow, build_stats_rows

log = logging.getLogger(__name__)

# Name reported for an upload sent without a filename
DEFAULT_UPLOAD_NAME = "upload"
# Chunk size for counting decompressed bytes
DECOMPRESS_CHUNK_SIZE = 1024 * 1024

NORMALIZED_EXTENSIONS: dict[str, str] = {"fasta": ".fasta", "genbank": ".gbk", "fastq": ".fastq"}
COMPRESSION_SUFFIXES = (".gz", ".bz2")


def open_decompressed(path: Path, compression: str) -> gzip.GzipFile | bz2.BZ2File:
    """Open the gzip or bzip2 file at `path` for reading its decompressed bytes."""
    if compression == "gzip":
        return gzip.open(path, "rb")
    return bz2.open(path, "rb")


def check_decompressed_size(path: Path, name: str, limit: int | None) -> None:
    """Raise 413 if the gzip/bzip2 file at `path` expands past `limit` bytes (None: no limit).

    Reads in chunks and stops at the limit. A broken archive is left for `load_file` to report.
    """
    compression = sniff_compression(path)
    if limit is None or compression is None:
        return
    total = 0
    try:
        with open_decompressed(path, compression) as handle:
            while chunk := handle.read(DECOMPRESS_CHUNK_SIZE):
                total += len(chunk)
                if total > limit:
                    log.info("%s: decompressed size exceeds %d bytes", name, limit)
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"{name}: decompressed size exceeds the limit",
                    )
    except (OSError, EOFError):
        return


@dataclass(slots=True)
class LoadedUpload:
    """An uploaded file read as `load_file` reads a local one."""

    name: str
    result: AnalysisResult | None
    compression: str | None


def load_upload(
    upload: UploadFile, command: str, max_decompressed: int | None = None
) -> LoadedUpload:
    """Read an uploaded file with the CLI's own format sniffing, decompression and parsing.

    The upload is saved to a temporary file; its filename replaces the temporary path in
    record `source_file`s and in errors. An unreadable or unrecognized file gives 422 with the
    CLI's error message (logged with `command`); a compressed file expanding past
    `max_decompressed` bytes gives 413.
    """
    name = upload.filename or DEFAULT_UPLOAD_NAME
    with tempfile.TemporaryDirectory(prefix="cobalt-") as tmp_dir:
        path = Path(tmp_dir) / "upload"
        with path.open("wb") as tmp:
            shutil.copyfileobj(upload.file, tmp)
        check_decompressed_size(path, name, max_decompressed)
        try:
            result = load_file(path)
        except InputFileError as exc:
            message = str(exc).replace(str(path), name)
            log.info("%s %s: %s", command, name, message)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=message
            ) from exc
        compression = sniff_compression(path)
    if result is not None:
        for record in result.records:
            record.source_file = name
    return LoadedUpload(name, result, compression)


@dataclass(slots=True)
class InspectOptions:
    """Listing options of `/inspect` (see `build_inspect_report`)."""

    overview_only: bool = False
    limit: int | None = None
    offset: int = 0
    include_sequence: bool = True
    max_warnings: int | None = None


def inspect_upload(
    upload: UploadFile, options: InspectOptions, max_decompressed: int | None = None
) -> InspectReport:
    """Inspect an uploaded file as `cobalt inspect --json` inspects a local one."""
    loaded = load_upload(upload, "inspect", max_decompressed)
    return build_inspect_report(
        loaded.name,
        loaded.result,
        loaded.compression,
        overview_only=options.overview_only,
        limit=options.limit,
        offset=options.offset,
        include_sequence=options.include_sequence,
        max_warnings=options.max_warnings,
    )


def validate_upload(
    upload: UploadFile, max_warnings: int | None = None, max_decompressed: int | None = None
) -> QCReport:
    """Validate an uploaded file as `cobalt validate --json` validates a local one."""
    loaded = load_upload(upload, "validate", max_decompressed)
    return build_qc_report(loaded.name, loaded.result, loaded.compression, max_warnings)


def stats_input_error(error_type: str, field: str, message: str, value: str | None) -> Exception:
    """Build a FastAPI-style validation error pointing at the form `field`."""
    return RequestValidationError(
        [{"type": error_type, "loc": ("body", field), "msg": message, "input": value}]
    )


def stats_rows(
    uploads: Sequence[UploadFile] | None,
    sequence: str | None,
    sort: SortKey | None,
    descending: bool,
    max_decompressed: int | None = None,
) -> list[StatsRow]:
    """Build stats rows as `cobalt stats --json` does, from uploaded files or a direct sequence.

    Exactly one of `uploads` and `sequence` must be given, as the CLI's `input` and `--input`
    are mutually exclusive; otherwise a 422 validation error points at the offending field.
    A blank `sequence` counts as not given, and whitespace inside it is removed. Any unreadable
    upload fails the request.
    """
    bases = "".join(sequence.split()) if sequence is not None else ""
    if not uploads and not bases:
        raise stats_input_error("missing", "file", "give one or more files or a sequence", None)
    if uploads and bases:
        raise stats_input_error(
            "value_error", "sequence", "give either files or a sequence, not both", sequence
        )
    records: list[SequenceRecord] = []
    if bases:
        primary_result = process_records([SeqRecord(Seq(bases), id="direct_input")], "raw")
        if primary_result is not None:
            records.extend(primary_result.records)
    else:
        for upload in uploads or []:
            loaded = load_upload(upload, "stats", max_decompressed)
            if loaded.result is not None:
                records.extend(loaded.result.records)
    return build_stats_rows(records, sort=sort, descending=descending)


@dataclass(slots=True)
class NormalizedUpload:
    """Result of `/normalize`: the file text, its suggested name and record counts."""

    text: str
    filename: str
    records_read: int
    records_written: int

    @property
    def records_skipped(self) -> int:
        return self.records_read - self.records_written

    def headers(self) -> dict[str, str]:
        """Return the response headers describing the result."""
        return {
            "Content-Disposition": content_disposition(self.filename),
            "X-Records-Read": str(self.records_read),
            "X-Records-Written": str(self.records_written),
            "X-Records-Skipped": str(self.records_skipped),
        }


def normalized_filename(upload_name: str | None, fmt: OutputFormat) -> str:
    """Suggest a name for the normalized file: the upload's base name, without `.gz`/`.bz2`
    and its extension, plus the extension of `fmt`; `upload.<ext>` for an unnamed upload."""
    base = (upload_name or "").replace("\\", "/").rsplit("/", 1)[-1]
    for suffix in COMPRESSION_SUFFIXES:
        if base.lower().endswith(suffix):
            base = base[: -len(suffix)]
            break
    stem, dot, _ = base.rpartition(".")
    if dot:
        base = stem
    return f"{base or DEFAULT_UPLOAD_NAME}{NORMALIZED_EXTENSIONS[fmt]}"


def content_disposition(filename: str) -> str:
    """Return an attachment `Content-Disposition` for `filename`, RFC 6266 encoded if needed."""
    fallback = "".join(
        c if c.isascii() and c.isprintable() and c not in '"\\' else "_" for c in filename
    )
    if fallback == filename:
        return f'attachment; filename="{filename}"'
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


def normalize_upload(
    upload: UploadFile, fmt: OutputFormat, max_decompressed: int | None = None
) -> NormalizedUpload:
    """Normalize an uploaded file as `cobalt normalize` does, returning the `fmt` file text.

    An upload with no records gives an empty text, as the CLI then writes no file. Records the
    format can't hold (no sequence content; no qualities for FASTQ) are skipped. A record
    Biopython can't write in `fmt` gives 422.
    """
    loaded = load_upload(upload, "normalize", max_decompressed)
    filename = normalized_filename(upload.filename, fmt)
    if loaded.result is None:
        return NormalizedUpload("", filename, 0, 0)
    selected = records_for_format(build_seq_records(loaded.result.records), fmt)
    try:
        text = write_records_text(selected, fmt)
    except ValueError as exc:
        message = f"{loaded.name}: could not write {fmt}: {exc}"
        log.info("normalize %s", message)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=message
        ) from exc
    return NormalizedUpload(text, filename, len(loaded.result.records), len(selected))
