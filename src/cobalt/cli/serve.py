"""Cli command: serve."""

from __future__ import annotations

import argparse
import bz2
import gzip
import ipaddress
import logging
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

import uvicorn
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from cobalt import __version__
from cobalt.analysis.folding import DEFAULT_ADAPTER
from cobalt.analysis.normalize import (
    OutputFormat,
    build_seq_records,
    records_for_format,
    write_records_text,
)
from cobalt.analysis.processor import InputFileError, load_file, process_records
from cobalt.cli.serve_auth import AUTH_MODES, AuthDependency, build_auth
from cobalt.io.sniff import sniff_compression
from cobalt.model.inspect import InspectReport, build_inspect_report
from cobalt.model.qc import QCReport, build_qc_report
from cobalt.model.record import AnalysisResult, SequenceRecord
from cobalt.model.stats import SortKey, StatsRow, build_stats_rows
from cobalt.server_config import (
    DEFAULT_API_PREFIX,
    DEFAULT_HOST,
    DEFAULT_MAX_UPLOAD_MB,
    DEFAULT_PORT,
    SERVER_DIR,
    ServerConfig,
    ServerConfigError,
    default_config_path,
    load_server_config,
    save_server_config,
)

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

API_TITLE = "Cobalt Sequence Lab"
BYTES_PER_MB = 1024 * 1024
# A compressed upload may expand to this many times the upload limit
DECOMPRESSED_LIMIT_FACTOR = 10
# Chunk size for counting decompressed bytes
DECOMPRESS_CHUNK_SIZE = 1024 * 1024

# Response headers of /normalize that browsers may read across origins
NORMALIZE_HEADERS = [
    "Content-Disposition",
    "X-Records-Read",
    "X-Records-Written",
    "X-Records-Skipped",
]
NORMALIZED_EXTENSIONS: dict[str, str] = {"fasta": ".fasta", "genbank": ".gbk", "fastq": ".fastq"}
COMPRESSION_SUFFIXES = (".gz", ".bz2")


def open_decompressed(path: Path, compression: str) -> gzip.GzipFile | bz2.BZ2File:
    """Open the gzip or bzip2 file at `path` for reading its decompressed bytes."""
    if compression == "gzip":
        return gzip.open(path, "rb")
    return bz2.open(path, "rb")


def normalize_api_prefix(prefix: str) -> str:
    """Return `prefix` with one leading slash and no trailing slash; "" stays "" (no prefix)."""
    stripped = prefix.strip().strip("/")
    return f"/{stripped}" if stripped else ""


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


class InternalErrorMiddleware:
    """Answer an unhandled exception with a JSON 500 and log the traceback.

    Added before `CORSMiddleware`, so it runs inside it and the 500 gets CORS headers
    (Starlette's own `Exception` handler runs outside every middleware).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            log.exception("unhandled error on %s %s", scope["method"], scope["path"])
            if started:
                raise
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )
            await response(scope, receive, send)


class BodySizeLimitMiddleware:
    """Answer 413 to a request body over `max_bytes`.

    A `Content-Length` over the limit is refused before the body is read; a chunked body is
    counted as it is read, and the endpoint's body parsing fails with 413 at the limit.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.detail = f"upload too large: limit is {max_bytes / BYTES_PER_MB:g} MB"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = Headers(scope=scope).get("content-length")
        if length is not None and length.isdigit() and int(length) > self.max_bytes:
            log.info("%s %s: %s", scope["method"], scope["path"], self.detail)
            response = JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE, content={"detail": self.detail}
            )
            await response(scope, receive, send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    log.info("%s %s: %s", scope["method"], scope["path"], self.detail)
                    # FastAPI re-raises an HTTPException from body parsing as is
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=self.detail
                    )
            return message

        await self.app(scope, limited_receive, send)


class UIStaticFiles(StaticFiles):
    """The built UI: static files, with `index.html` for other HTML requests (client routes).

    Paths under the API prefix are never answered from here.
    """

    def __init__(self, directory: Path, api_prefix: str) -> None:
        super().__init__(directory=directory, html=True)
        self.api_prefix = api_prefix

    def _is_api_path(self, path: str) -> bool:
        return path == self.api_prefix or path.startswith(f"{self.api_prefix}/")

    async def get_response(self, path: str, scope: Scope) -> Response:
        if self._is_api_path(scope["path"]):
            raise StarletteHTTPException(status_code=status.HTTP_404_NOT_FOUND)
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            accepts_html = "text/html" in Headers(scope=scope).get("accept", "")
            if exc.status_code != status.HTTP_404_NOT_FOUND or not accepts_html:
                raise
            return await super().get_response("index.html", scope)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for serve command.

    Server flags default to None, meaning "not given": the config file (or its defaults) then
    provides the value. Given flags override the file.
    """
    parser = argparse.ArgumentParser(prog="cobalt serve")
    parser.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        help=f"Server config file (default: ./{SERVER_DIR}/cobalt-config.yaml, created if missing)",
    )
    parser.add_argument("--host", help=f"Host to bind to (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, help=f"Port to bind to (default: {DEFAULT_PORT})")
    parser.add_argument(
        "--cors",
        nargs="*",
        metavar="ORIGIN",
        help="Enable CORS (for UI development). Without origins, any origin is allowed",
    )
    parser.add_argument(
        "--auth",
        choices=AUTH_MODES,
        help="Authentication for processing endpoints (default: none; "
        "api-key reads keys from $COBALT_API_KEYS)",
    )
    parser.add_argument(
        "--allow-no-auth",
        action="store_true",
        default=None,
        help="Allow --auth none on a non-loopback host (auth handled by a gateway or mesh)",
    )
    parser.add_argument(
        "--api-prefix",
        metavar="PREFIX",
        help=f'Path prefix of every endpoint (default: {DEFAULT_API_PREFIX}; "" for none)',
    )
    parser.add_argument(
        "--max-upload-mb",
        type=_non_negative_int,
        metavar="N",
        help=f"Request body size limit in MiB (default: {DEFAULT_MAX_UPLOAD_MB}; 0 for no limit)",
    )
    parser.add_argument(
        "--ui-dist",
        type=Path,
        metavar="PATH",
        help="Serve the built UI (its dist/ folder) at / alongside the API",
    )
    parser.add_argument(
        "--storage-dir",
        type=Path,
        metavar="PATH",
        help="Server file storage (default: the config file's directory)",
    )
    return parser


def _non_negative_int(value: str) -> int:
    """argparse type: an integer >= 0."""
    try:
        number = int(value)
    except ValueError:
        number = -1
    if number < 0:
        raise argparse.ArgumentTypeError(f"expected an integer >= 0, got {value!r}")
    return number


def _is_loopback(host: str) -> bool:
    """Return True when `host` only accepts connections from this machine."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def build_app(
    cors_origins: Sequence[str] | None = None,
    auth: AuthDependency | None = None,
    api_prefix: str = DEFAULT_API_PREFIX,
    max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB,
    ui_dist: Path | None = None,
) -> FastAPI:
    """Build the FastAPI application.

    Every endpoint, the OpenAPI schema and the docs are served under `api_prefix` ("" for none).
    CORS is disabled when `cors_origins` is None; an empty sequence allows any origin.
    `auth` guards the processing endpoints; the version (`<prefix>/`) and `<prefix>/health`
    stay public. Request bodies over `max_upload_mb` MiB (0: no limit) give 413. `ui_dist`
    serves the built UI at `/`; it needs a non-empty `api_prefix`.
    `/foldrna`, `/run` and `/runs` are stubs that answer 501 Not Implemented for now.
    """
    prefix = normalize_api_prefix(api_prefix)
    if ui_dist is not None and not prefix:
        raise ValueError("serving the UI needs an API prefix")
    max_bytes = max_upload_mb * BYTES_PER_MB or None
    max_decompressed = max_bytes * DECOMPRESSED_LIMIT_FACTOR if max_bytes else None

    app = FastAPI(
        title=API_TITLE,
        version=__version__,
        openapi_url=f"{prefix}/openapi.json",
        docs_url=f"{prefix}/docs",
        redoc_url=None,
    )
    public = APIRouter()
    api = APIRouter(dependencies=[Depends(auth)] if auth else [])

    # Middleware added last runs first: CORS, then JSON 500s, then the size limit
    if max_bytes:
        app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_bytes)
    app.add_middleware(InternalErrorMiddleware)
    if cors_origins is not None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins) or ["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=NORMALIZE_HEADERS,
        )

    async def root() -> dict[str, Any]:
        return {"title": API_TITLE, "version": __version__}

    # The version answers both with and without the trailing slash
    public.add_api_route("/", root, methods=["GET"])
    if prefix:
        app.add_api_route(prefix, root, methods=["GET"], include_in_schema=False)

    @public.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/stats", response_model=list[StatsRow])
    def stats(
        file: Annotated[list[UploadFile] | None, File()] = None,
        sequence: Annotated[str | None, Form()] = None,
        sort: Annotated[SortKey | None, Form()] = None,
        desc: Annotated[bool, Form()] = False,
    ) -> list[StatsRow]:
        # Sync handler: FastAPI runs it in a thread pool, so file I/O doesn't block the loop
        return stats_rows(file, sequence, sort, desc, max_decompressed)

    @api.post("/inspect", response_model=InspectReport)
    def inspect(
        file: UploadFile,
        overview_only: Annotated[bool, Form()] = False,
        output_seq_number: Annotated[int | None, Form(ge=0)] = None,
        offset: Annotated[int, Form(ge=0)] = 0,
        include_sequence: Annotated[bool, Form()] = True,
        max_warnings: Annotated[int | None, Form(ge=0)] = None,
    ) -> InspectReport:
        # Sync handler: FastAPI runs it in a thread pool, so file I/O doesn't block the loop
        options = InspectOptions(
            overview_only, output_seq_number, offset, include_sequence, max_warnings
        )
        return inspect_upload(file, options, max_decompressed)

    @api.post("/validate", response_model=QCReport)
    def validate(
        file: UploadFile,
        max_warnings: Annotated[int | None, Form(ge=0)] = None,
    ) -> QCReport:
        return validate_upload(file, max_warnings, max_decompressed)

    @api.post("/normalize", response_class=PlainTextResponse)
    def normalize(
        file: UploadFile,
        fmt: Annotated[OutputFormat, Form(alias="format")] = "fasta",
    ) -> PlainTextResponse:
        result = normalize_upload(file, fmt, max_decompressed)
        return PlainTextResponse(result.text, headers=result.headers())

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

    app.include_router(public, prefix=prefix)
    app.include_router(api, prefix=prefix)
    if ui_dist is not None:
        # Mounted last: the API routes match first
        app.mount("/", UIStaticFiles(ui_dist, prefix), name="ui")
    return app


def load_config(args: argparse.Namespace) -> ServerConfig:
    """Read the server config named by `args.config` (or the default one) and apply the flags.

    A missing default config file is created with default values; a missing file given with
    --config is an error. Raises ServerConfigError.
    """
    path = args.config if args.config is not None else default_config_path()
    if args.config is None and not path.exists():
        try:
            save_server_config(ServerConfig(), path)
        except OSError as exc:
            raise ServerConfigError(f"could not create {path}: {exc}") from None
        log.info("created default server config %s", path)
    config = load_server_config(path).resolve_paths(path.parent)
    log.info("server config: %s", path)
    return config.with_overrides(
        host=args.host,
        port=args.port,
        cors=args.cors,
        auth=args.auth,
        allow_no_auth=args.allow_no_auth,
        api_prefix=args.api_prefix,
        max_upload_mb=args.max_upload_mb,
        ui_dist=args.ui_dist,
        storage_dir=args.storage_dir,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the serve command."""
    args = build_parser().parse_args(argv)

    try:
        config = load_config(args)
    except ServerConfigError as exc:
        log.error("%s", exc)
        return 1
    try:
        config.storage_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.error("could not create storage directory %s: %s", config.storage_dir, exc)
        return 1
    log.info("storage directory: %s", config.storage_dir)

    try:
        auth = build_auth(config.auth)
    except ValueError as exc:
        log.error("%s", exc)
        return 1
    if auth is None and not _is_loopback(config.host) and not config.allow_no_auth:
        log.error(
            "refusing to serve %s without authentication: use --auth api-key, or "
            "--allow-no-auth if a gateway or service mesh handles authentication",
            config.host,
        )
        return 1
    api_prefix = normalize_api_prefix(config.api_prefix)
    if config.ui_dist is not None:
        if not api_prefix:
            log.error('--ui-dist needs an API prefix: drop --api-prefix "" or set another one')
            return 1
        if not (config.ui_dist / "index.html").is_file():
            log.error(
                "--ui-dist %s: no index.html found (expected the UI's dist/ folder)",
                config.ui_dist,
            )
            return 1
    log.info("authentication: %s", config.auth)
    log.info("API prefix: %s", api_prefix or "(none)")

    app = build_app(
        cors_origins=config.cors,
        auth=auth,
        api_prefix=api_prefix,
        max_upload_mb=config.max_upload_mb,
        ui_dist=config.ui_dist,
    )
    # log_config=None: uvicorn's loggers propagate to the handler set up by
    # cobalt.logging_config instead of installing uvicorn's own
    uvicorn.run(app, host=config.host, port=config.port, log_config=None)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
