"""CLI command: inspect."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable, Sequence
from itertools import islice
from pathlib import Path

from cobalt.analysis.processor import InputFileError, load_file
from cobalt.io.sniff import sniff_compression
from cobalt.model.record import AnalysisResult, SequenceRecord

log = logging.getLogger(__name__)


def format_counts(counts: Iterable[tuple[str, int]]) -> str:
    """Format (name, count) pairs as `name=count, ...`."""
    return ", ".join(f"{name}={count}" for name, count in counts)


def print_file_results(path: Path, result: AnalysisResult) -> None:
    compression = sniff_compression(path)
    print(f"{path}: {result.records_num} record(s)")
    print(f" format: {result.type}" + (f" ({compression})" if compression else ""))
    print(f" length: min={result.min}  max={result.max}  mean={result.mean:.1f}")
    print(f" molecule types: {format_counts(result.type_counts().items())}")
    print(f" warnings: {len(result.warnings)} ({format_counts(result.warning_counts().items())})")
    for warning in result.warnings:
        print(f"     {warning}")


def print_record(record: SequenceRecord) -> None:
    print(f"Sequence name   : {record.id}")
    print(f"Sequence length : {record.length}")
    sequence = record.sequence if record.sequence is not None else "(undefined, length only)"
    print(f"Sequence        : {sequence}")
    print(f"GC fraction     : {record.gc_fraction!r}")
    print(f"Type guess      : {record.type}")
    if record.molecule_type:
        print(f"Type            : {record.molecule_type}")
    print(f"Description     : {record.description}")
    if record.organism:
        print(f"Organism        : {record.organism}")
    print()


def non_negative_int(value: str) -> int:
    """argparse type for an integer >= 0."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer: {value!r}") from None
    if number < 0:
        raise argparse.ArgumentTypeError(f"must be 0 or greater, got {number}")
    return number


def build_parser() -> argparse.ArgumentParser:
    """Build parser for inspect command."""
    parser = argparse.ArgumentParser(prog="cobalt inspect")
    parser.add_argument("input", help="Input FASTA/GenBank file (plain, gzip or bzip2)")
    parser.add_argument(
        "--overview-only",
        action="store_true",
        help="Print only the file summary, skip the per-record listing",
    )
    parser.add_argument(
        "--output-seq-number",
        type=non_negative_int,
        default=None,
        metavar="N",
        help="List only the first N records (default: all)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the inspect command.

    Detects the input format from the content (FASTA or GenBank, optionally gzip/bzip2
    compressed), prints a summary of the file and then the records.
    """
    args = build_parser().parse_args(argv)
    path = Path(args.input)

    try:
        primary_result = load_file(path)
    except InputFileError as exc:
        log.error("%s", exc)
        return 1
    if not primary_result:
        print(f"{path}: 0 records")
        return 0
    print_file_results(path, primary_result)
    if args.overview_only:
        return 0
    print("--------------------------------------------------------------------------------------")
    for record in islice(primary_result.records, args.output_seq_number):
        print_record(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
