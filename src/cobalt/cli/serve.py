"""Cli command: serve."""

from __future__ import annotations

import argparse
import ipaddress
import logging
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import uvicorn
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from cobalt import __version__
from cobalt.analysis.folding import DEFAULT_ADAPTER
from cobalt.analysis.normalize import OutputFormat, build_seq_records, format_records
from cobalt.analysis.processor import InputFileError, load_file, process_records
from cobalt.cli.serve_auth import AUTH_MODES, AuthDependency, build_auth
from cobalt.io.sniff import sniff_compression
from cobalt.model.inspect import InspectReport, build_inspect_report
from cobalt.model.qc import QCReport, build_qc_report
from cobalt.model.record import AnalysisResult, SequenceRecord
from cobalt.model.stats import SortKey, StatsRow, build_stats_rows

log = logging.getLogger(__name__)


class FoldRequest(BaseModel):
    """Request body for RNA folding of a manual sequence input."""

    sequence: str
    adapter: str = DEFAULT_ADAPTER


class RunRequest(BaseModel):
    """Request body for a pipeline run; `pipeline` is the YAML definition text."""

    pipeline: str
    params: dict[str, str] = {}
    backend: str = "local"
    resume: bool = False


def _not_implemented(command: str) -> HTTPException:
    """Build the error that stub endpoints raise, worded like the CLI stubs."""
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"cobalt {command} is not implemented yet",
    )


# Name reported for an upload sent without a filename
DEFAULT_UPLOAD_NAME = "upload"


@dataclass(slots=True)
class LoadedUpload:
    """An uploaded file read as `load_file` reads a local one."""

    name: str
    result: AnalysisResult | None
    compression: str | None


def load_upload(upload: UploadFile, command: str) -> LoadedUpload:
    """Read an uploaded file with the CLI's own format sniffing, decompression and parsing.

    The upload is saved to a temporary file; its filename replaces the temporary path in
    record `source_file`s and in errors. An unreadable or unrecognized file gives 422 with the
    CLI's error message (logged with `command`).
    """
    name = upload.filename or DEFAULT_UPLOAD_NAME
    with tempfile.TemporaryDirectory(prefix="cobalt-") as tmp_dir:
        path = Path(tmp_dir) / "upload"
        with path.open("wb") as tmp:
            shutil.copyfileobj(upload.file, tmp)
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


def inspect_upload(upload: UploadFile, overview_only: bool, limit: int | None) -> InspectReport:
    """Inspect an uploaded file as `cobalt inspect --json` inspects a local one."""
    loaded = load_upload(upload, "inspect")
    return build_inspect_report(
        loaded.name, loaded.result, loaded.compression, overview_only, limit
    )


def validate_upload(upload: UploadFile) -> QCReport:
    """Validate an uploaded file as `cobalt validate --json` validates a local one."""
    loaded = load_upload(upload, "validate")
    return build_qc_report(loaded.name, loaded.result, loaded.compression)


def stats_rows(
    uploads: Sequence[UploadFile] | None,
    sequence: str | None,
    sort: SortKey | None,
    descending: bool,
) -> list[StatsRow]:
    """Build stats rows as `cobalt stats --json` does, from uploaded files or a direct sequence.

    Exactly one of `uploads` and `sequence` must be given (422 otherwise), as the CLI's
    `input` and `--input` are mutually exclusive. Any unreadable upload fails the request.
    """
    if bool(uploads) == (sequence is not None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="give either file uploads or a sequence, not both",
        )
    records: list[SequenceRecord] = []
    if sequence is not None:
        primary_result = process_records([SeqRecord(Seq(sequence), id="direct_input")], "raw")
        if primary_result is not None:
            records.extend(primary_result.records)
    else:
        for upload in uploads or []:
            loaded = load_upload(upload, "stats")
            if loaded.result is not None:
                records.extend(loaded.result.records)
    return build_stats_rows(records, sort=sort, descending=descending)


def normalize_upload(upload: UploadFile, fmt: OutputFormat) -> str:
    """Normalize an uploaded file as `cobalt normalize` does, returning the `fmt` file text.

    An upload with no records gives an empty text, as the CLI then writes no file. A record
    Biopython can't write in `fmt` gives 422.
    """
    loaded = load_upload(upload, "normalize")
    if loaded.result is None:
        return ""
    try:
        return format_records(build_seq_records(loaded.result.records), fmt)
    except ValueError as exc:
        message = f"{loaded.name}: could not write {fmt}: {exc}"
        log.info("normalize %s", message)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=message
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    """Build parser for serve command."""
    parser = argparse.ArgumentParser(prog="cobalt serve")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument(
        "--cors",
        nargs="*",
        metavar="ORIGIN",
        help="Enable CORS (for UI development). Without origins, any origin is allowed",
    )
    parser.add_argument(
        "--auth",
        choices=AUTH_MODES,
        default="none",
        help="Authentication for processing endpoints (api-key reads keys from $COBALT_API_KEYS)",
    )
    parser.add_argument(
        "--allow-no-auth",
        action="store_true",
        help="Allow --auth none on a non-loopback host (auth handled by a gateway or mesh)",
    )
    return parser


def _is_loopback(host: str) -> bool:
    """Return True when `host` only accepts connections from this machine."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def build_app(
    cors_origins: Sequence[str] | None = None, auth: AuthDependency | None = None
) -> FastAPI:
    """Build the FastAPI application.

    CORS is disabled when `cors_origins` is None; an empty sequence allows any origin.
    `auth` guards the processing endpoints; `/` stays public (version info, liveness probe).
    `/foldrna`, `/run` and `/runs` are stubs that answer 501 Not Implemented for now.
    """
    app = FastAPI()
    api = APIRouter(dependencies=[Depends(auth)] if auth else [])

    if cors_origins is not None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins) or ["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/")
    async def root():
        return {"title": "Cobalt Sequence Lab", "version": __version__}

    @api.post("/stats", response_model=list[StatsRow])
    def stats(
        file: Annotated[list[UploadFile] | None, File()] = None,
        sequence: Annotated[str | None, Form()] = None,
        sort: Annotated[SortKey | None, Form()] = None,
        desc: Annotated[bool, Form()] = False,
    ) -> list[StatsRow]:
        # Sync handler: FastAPI runs it in a thread pool, so file I/O doesn't block the loop
        return stats_rows(file, sequence, sort, desc)

    @api.post("/inspect", response_model=InspectReport)
    def inspect(
        file: UploadFile,
        overview_only: Annotated[bool, Form()] = False,
        output_seq_number: Annotated[int | None, Form(ge=0)] = None,
    ) -> InspectReport:
        # Sync handler: FastAPI runs it in a thread pool, so file I/O doesn't block the loop
        return inspect_upload(file, overview_only, output_seq_number)

    @api.post("/validate", response_model=QCReport)
    def validate(file: UploadFile) -> QCReport:
        return validate_upload(file)

    @api.post("/normalize", response_class=PlainTextResponse)
    def normalize(
        file: UploadFile,
        fmt: Annotated[OutputFormat, Form(alias="format")] = "fasta",
    ) -> PlainTextResponse:
        return PlainTextResponse(normalize_upload(file, fmt))

    @api.post("/foldrna")
    async def foldrna(body: FoldRequest):
        raise _not_implemented("foldrna")

    @api.post("/run")
    async def run(body: RunRequest):
        raise _not_implemented("run")

    @api.get("/runs")
    async def runs_list():
        raise _not_implemented("runs list")

    @api.get("/runs/{run_id}")
    async def runs_show(run_id: str):
        raise _not_implemented("runs show")

    app.include_router(api)
    return app


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the serve command."""
    args = build_parser().parse_args(argv)

    try:
        auth = build_auth(args.auth)
    except ValueError as exc:
        log.error("%s", exc)
        return 1
    if auth is None and not _is_loopback(args.host) and not args.allow_no_auth:
        log.error(
            "refusing to serve %s without authentication: use --auth api-key, or "
            "--allow-no-auth if a gateway or service mesh handles authentication",
            args.host,
        )
        return 1
    log.info("authentication: %s", args.auth)

    app = build_app(cors_origins=args.cors, auth=auth)
    # log_config=None: uvicorn's loggers propagate to the handler set up by
    # cobalt.logging_config instead of installing uvicorn's own
    uvicorn.run(app, host=args.host, port=args.port, log_config=None)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
