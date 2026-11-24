"""The FastAPI application of the cobalt server: endpoints, routers and middleware setup."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from cobalt import __version__
from cobalt.core.analysis.folding import DEFAULT_ADAPTER
from cobalt.core.analysis.normalize import OutputFormat
from cobalt.core.model.inspect import InspectReport
from cobalt.core.model.qc import QCReport
from cobalt.core.model.stats import SortKey, StatsRow
from cobalt.core.pipeline.run import PipelineRun, RunSummary
from cobalt.server.auth import AuthDependency
from cobalt.server.config import DEFAULT_API_PREFIX, DEFAULT_MAX_UPLOAD_MB, normalize_api_prefix
from cobalt.server.middleware import (
    BYTES_PER_MB,
    BodySizeLimitMiddleware,
    InternalErrorMiddleware,
    UIStaticFiles,
)
from cobalt.server.registry import RunRegistry
from cobalt.server.uploads import (
    InspectOptions,
    inspect_upload,
    normalize_upload,
    stats_rows,
    validate_upload,
)

log = logging.getLogger(__name__)

API_TITLE = "Cobalt Sequence Lab"
# A compressed upload may expand to this many times the upload limit
DECOMPRESSED_LIMIT_FACTOR = 10

# Response headers of /normalize that browsers may read across origins
NORMALIZE_HEADERS = [
    "Content-Disposition",
    "X-Records-Read",
    "X-Records-Written",
    "X-Records-Skipped",
]

# Temporary placeholder: the server has no users yet, so /me returns this name to every caller
DEFAULT_USER_NAME = "lab user"


class Me(BaseModel):
    """The current user, as `GET /me` returns it."""

    name: str


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


def get_runs(request: Request) -> RunRegistry:
    """FastAPI dependency: the run registry of the app serving `request`."""
    registry: RunRegistry = request.app.state.runs
    return registry


def build_app(
    cors_origins: Sequence[str] | None = None,
    auth: AuthDependency | None = None,
    api_prefix: str = DEFAULT_API_PREFIX,
    max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB,
    ui_dist: Path | None = None,
    runs: RunRegistry | None = None,
) -> FastAPI:
    """Build the FastAPI application.

    Every endpoint, the OpenAPI schema and the docs are served under `api_prefix` ("" for none).
    CORS is disabled when `cors_origins` is None; an empty sequence allows any origin.
    `auth` guards the processing endpoints; the version (`<prefix>/`) and `<prefix>/health`
    stay public. Request bodies over `max_upload_mb` MiB (0: no limit) give 413. `ui_dist`
    serves the built UI at `/`; it needs a non-empty `api_prefix`.
    `runs` is the run registry the app keeps for its lifetime (`app.state.runs`); by default a
    new in-memory one. `/runs` and `/runs/{run_id}` answer from it; `/foldrna` and `/run` are
    stubs that answer 501 Not Implemented for now. `/me` returns a hardcoded user for now.
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
    # The one run registry of this app, handed to endpoints by get_runs
    app.state.runs = runs if runs is not None else RunRegistry()
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

    @api.get("/me", response_model=Me)
    async def me() -> Me:
        return Me(name=DEFAULT_USER_NAME)

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

    @api.get("/runs", response_model=list[RunSummary])
    def runs_list(registry: Annotated[RunRegistry, Depends(get_runs)]) -> list[RunSummary]:
        return [RunSummary.from_run(run) for run in registry.list_runs()]

    @api.get("/runs/{run_id}", response_model=PipelineRun)
    def runs_show(run_id: str, registry: Annotated[RunRegistry, Depends(get_runs)]) -> PipelineRun:
        run = registry.get(run_id)
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"run not found: {run_id}")
        return run

    app.include_router(public, prefix=prefix)
    app.include_router(api, prefix=prefix)
    if ui_dist is not None:
        # Mounted last: the API routes match first
        app.mount("/", UIStaticFiles(ui_dist, prefix), name="ui")
    return app
