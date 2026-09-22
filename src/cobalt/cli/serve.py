"""Cli command: serve."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from fastapi import FastAPI
from pydantic import BaseModel

from cobalt import __version__
from cobalt.analysis.inspect import (
    STATS_FIELDNAMES,
)

from cobalt.analysis.processor import process_records


class SequenceRequest(BaseModel):
    """Request body for manual sequence input."""

    sequence: str


class StatsRecord(BaseModel):
    """One row of the stats output, mirroring `cobalt stats --json`."""

    id: str
    length: int
    gc_fraction: float
    type: str


def build_parser() -> argparse.ArgumentParser:
    """Build parser for serve command."""
    parser = argparse.ArgumentParser(prog="cobalt serve")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    return parser


def build_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI()

    @app.get("/")
    async def root():
        return {"title": "Cobalt Sequence Lab",
                "version": __version__}

    @app.post("/stats", response_model=list[StatsRecord])
    async def stats(body: SequenceRequest):
        seq_record = SeqRecord(Seq(body.sequence), id="direct_input")
        primary_result = process_records([seq_record], "raw")
        records = primary_result["records"] if primary_result else []
        return [{name: rec[name] for name in STATS_FIELDNAMES} for rec in records]

    @app.post("/inspect", response_model=list[StatsRecord])
    async def inspect(body: SequenceRequest):
        seq_record = SeqRecord(Seq(body.sequence), id="direct_input")
        primary_result = process_records([seq_record], "raw")
        records = primary_result["records"] if primary_result else []
        return [{name: rec[name] for name in STATS_FIELDNAMES} for rec in records]

    @app.post("/validate", response_model=list[StatsRecord])
    async def validate(body: SequenceRequest):
        seq_record = SeqRecord(Seq(body.sequence), id="direct_input")
        primary_result = process_records([seq_record], "raw")
        records = primary_result["records"] if primary_result else []
        return [{name: rec[name] for name in STATS_FIELDNAMES} for rec in records]

    @app.post("/normalize", response_model=list[StatsRecord])
    async def normalize(body: SequenceRequest):
        seq_record = SeqRecord(Seq(body.sequence), id="direct_input")
        primary_result = process_records([seq_record], "raw")
        records = primary_result["records"] if primary_result else []
        return [{name: rec[name] for name in STATS_FIELDNAMES} for rec in records]

    return app


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the serve command."""
    args = build_parser().parse_args(argv)

    app = build_app()
    uvicorn.run(app, host=args.host, port=args.port)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
