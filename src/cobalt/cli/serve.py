"""Cli command: serve."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from cobalt import __version__
from cobalt.analysis.processor import process_records
from cobalt.model.stats import StatsRow, build_stats_rows


class SequenceRequest(BaseModel):
    """Request body for manual sequence input."""

    sequence: str


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
    return parser


def build_app(cors_origins: Sequence[str] | None = None) -> FastAPI:
    """Build the FastAPI application.

    CORS is disabled when `cors_origins` is None; an empty sequence allows any origin.
    """
    app = FastAPI()

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

    @app.post("/stats", response_model=list[StatsRow])
    async def stats(body: SequenceRequest):
        seq_record = SeqRecord(Seq(body.sequence), id="direct_input")
        primary_result = process_records([seq_record], "raw")
        records = primary_result.records if primary_result else []
        return build_stats_rows(records)

    @app.post("/inspect", response_model=list[StatsRow])
    async def inspect(body: SequenceRequest):
        seq_record = SeqRecord(Seq(body.sequence), id="direct_input")
        primary_result = process_records([seq_record], "raw")
        records = primary_result.records if primary_result else []
        return build_stats_rows(records)

    @app.post("/validate", response_model=list[StatsRow])
    async def validate(body: SequenceRequest):
        seq_record = SeqRecord(Seq(body.sequence), id="direct_input")
        primary_result = process_records([seq_record], "raw")
        records = primary_result.records if primary_result else []
        return build_stats_rows(records)

    @app.post("/normalize", response_model=list[StatsRow])
    async def normalize(body: SequenceRequest):
        seq_record = SeqRecord(Seq(body.sequence), id="direct_input")
        primary_result = process_records([seq_record], "raw")
        records = primary_result.records if primary_result else []
        return build_stats_rows(records)

    return app


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the serve command."""
    args = build_parser().parse_args(argv)

    app = build_app(cors_origins=args.cors)
    # log_config=None: uvicorn's loggers propagate to the handler set up by
    # cobalt.logging_config instead of installing uvicorn's own
    uvicorn.run(app, host=args.host, port=args.port, log_config=None)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
