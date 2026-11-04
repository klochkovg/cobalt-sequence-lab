"""CLI command: normalize."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.normalize import OutputFormat, build_seq_records, records_for_format
from cobalt.analysis.processor import InputFileError, load_file

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for normalize command."""
    parser = argparse.ArgumentParser(prog="cobalt normalize")
    parser.add_argument("input", help="Input FASTA/GenBank/FASTQ file (plain, gzip or bzip2)")
    parser.add_argument("--fasta", help="Output cleaned FASTA path")
    parser.add_argument("--genbank", help="Output cleaned GenBank path")
    parser.add_argument(
        "--fastq", help="Output cleaned FASTQ path (only records with qualities, from FASTQ input)"
    )
    return parser


def write_records(path: str, seq_records: list[SeqRecord], fmt: str) -> bool:
    """Write records to `path` in the given Biopython format, report errors."""
    try:
        with open(path, "w") as f:
            SeqIO.write(seq_records, f, fmt)
    except OSError as exc:
        log.error("could not write to %s: %s", path, exc)
        return False
    except ValueError as exc:
        log.error("could not write %s to %s: %s", fmt, path, exc)
        return False
    return True


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the normalize command.

    Reads the input file, uppercases every sequence and writes the result
    as FASTA, GenBank and/or FASTQ.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.fasta and not args.genbank and not args.fastq:
        parser.error("at least one of --fasta, --genbank or --fastq is required")

    data_file_path = Path(args.input)
    try:
        primary_result = load_file(data_file_path)
    except InputFileError as exc:
        log.error("%s", exc)
        return 1

    if not primary_result:
        log.warning("%s: 0 records", data_file_path)
        return 0

    seq_records = build_seq_records(primary_result.records)
    outputs: list[tuple[str | None, OutputFormat]] = [
        (args.fasta, "fasta"),
        (args.genbank, "genbank"),
        (args.fastq, "fastq"),
    ]
    for path, fmt in outputs:
        if path and not write_records(path, records_for_format(seq_records, fmt), fmt):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
