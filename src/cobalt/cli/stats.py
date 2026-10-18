"""CLI command: stats."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.processor import InputFileError, load_file, process_records
from cobalt.model.stats import STATS_FIELDNAMES, SortKey, StatsRow, build_stats_rows

log = logging.getLogger(__name__)

OUTPUT_FORMATS = ["csv", "json", "parquet"]
FORMAT_BY_EXTENSION = {".csv": "csv", ".json": "json", ".parquet": "parquet", ".pq": "parquet"}


def build_parser() -> argparse.ArgumentParser:
    """Build parser for stats command."""
    parser = argparse.ArgumentParser(prog="cobalt stats")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "input", nargs="?", default=None, help="Input FASTA/GenBank file (plain, gzip or bzip2)"
    )
    source.add_argument(
        "--input",
        dest="raw_sequence",
        metavar="SEQ",
        help="Direct sequence string, e.g. --input AGCGCA",
    )

    parser.add_argument("--out", required=False, help="Output stats file path")
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument(
        "--format",
        choices=OUTPUT_FORMATS,
        help="Output format (default: from the --out extension, else csv); "
        "parquet needs --out and the 'parquet' extra",
    )
    format_group.add_argument(
        "--json", dest="format", action="store_const", const="json", help="Same as --format json"
    )
    parser.add_argument(
        "--sort",
        choices=[key.value for key in SortKey],
        help="Sort rows by this column (default: input order)",
    )
    parser.add_argument("--desc", action="store_true", help="Sort in descending order")
    return parser


def output_format(format: str | None, out: str | None) -> str:
    """Return the output format: `format` if given, else guessed from the `out` extension.

    Falls back to csv for stdout and, with a warning, for unknown or missing extensions.
    """
    if format is not None:
        return format
    if out is None:
        return "csv"
    guessed = FORMAT_BY_EXTENSION.get(Path(out).suffix.lower())
    if guessed is None:
        log.warning(
            "%s: unrecognized extension (expected %s), writing csv; use --format to choose",
            out,
            ", ".join(FORMAT_BY_EXTENSION),
        )
        return "csv"
    return guessed


def write_stats_csv(file: TextIO, rows: list[StatsRow]) -> None:
    """Write rows as CSV; None values become empty cells."""
    writer = csv.DictWriter(file, fieldnames=STATS_FIELDNAMES)
    writer.writeheader()
    for row in rows:
        writer.writerow(row.to_dict())


def write_stats_json(file: TextIO, rows: list[StatsRow]) -> None:
    """Write rows as a JSON array; None values become null."""
    json.dump([row.to_dict() for row in rows], file, indent=2)


def write_stats_parquet(path: str, rows: list[StatsRow]) -> None:
    """Write rows as a Parquet file; None values become nulls.

    pyarrow is imported here because it is an optional dependency.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    # Explicit types, so columns that are all None (e.g. organism for FASTA) are not typed null
    schema = pa.schema(
        [
            ("id", pa.string()),
            ("length", pa.int64()),
            ("description", pa.string()),
            ("gc_fraction", pa.float64()),
            ("type", pa.string()),
            ("source_format", pa.string()),
            ("alphabetic_class", pa.string()),
            ("ambiguity_fraction", pa.float64()),
            ("invalid_char_count", pa.int64()),
            ("organism", pa.string()),
            ("molecule_type", pa.string()),
            ("topology", pa.string()),
            ("feature_count", pa.int64()),
        ]
    )
    table = pa.Table.from_pylist([row.to_dict() for row in rows], schema=schema)
    pq.write_table(table, path)


def write_stats(type: str, file: TextIO, rows: list[StatsRow]) -> None:
    """Write rows to a text stream as CSV or JSON."""
    if type == "csv":
        write_stats_csv(file, rows)
    elif type == "json":
        write_stats_json(file, rows)
    else:
        raise ValueError(f"unsupported text output format: {type}")


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the stats command.
    In case of empty --out, input to stdout
    """
    args = build_parser().parse_args(argv)
    output_type = output_format(args.format, args.out)
    log.debug("output format: %s", output_type)
    if output_type == "parquet" and not args.out:
        log.error("parquet output is binary and needs --out FILE")
        return 1

    if args.raw_sequence is not None:
        record = SeqRecord(Seq(args.raw_sequence), id="direct_input")
        primary_result = process_records([record], "raw")
    else:
        try:
            primary_result = load_file(Path(args.input))
        except InputFileError as exc:
            log.error("%s", exc)
            return 1

    if not primary_result:
        source = "direct input" if args.raw_sequence is not None else args.input
        log.warning("%s: 0 records", source)
    # An empty input still gets an empty table (CSV header, [] or a schema-only Parquet file),
    # so the next step of a pipeline can read it
    records = primary_result.records if primary_result else []

    sort = SortKey(args.sort) if args.sort else None
    rows = build_stats_rows(records, sort=sort, descending=args.desc)
    if args.out:
        try:
            if output_type == "parquet":
                write_stats_parquet(args.out, rows)
            else:
                with open(args.out, "w", newline="") as f:
                    write_stats(output_type, f, rows)
        except ImportError as exc:
            log.error(
                "parquet output requires optional dependencies (%s is missing). "
                'Install them with: pip install "cobalt-sequence-lab[parquet]"',
                exc.name,
            )
            return 1
        except IsADirectoryError:
            log.error("--out is a directory: %s", args.out)
            return 1
        except FileNotFoundError:
            log.error("no such directory for --out: %s", args.out)
            return 1
        except PermissionError:
            log.error("permission denied writing to: %s", args.out)
            return 1
        except OSError as exc:
            log.error("could not write to %s: %s", args.out, exc)
            return 1
    else:
        write_stats(output_type, sys.stdout, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
