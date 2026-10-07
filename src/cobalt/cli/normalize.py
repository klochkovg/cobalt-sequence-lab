"""CLI command: normalize."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.inspect import FASTA_SUFFIXES, GENBANK_SUFFIXES, check_file
from cobalt.analysis.normalize import uppercase_result
from cobalt.analysis.processor import read_file

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for normalize command."""
    parser = argparse.ArgumentParser(prog="cobalt normalize")
    parser.add_argument("input", help="Input FASTA/GenBank file")
    parser.add_argument("--fasta", help="Output cleaned FASTA path")
    parser.add_argument("--genbank", help="Output cleaned GenBank path")
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
    as FASTA and/or GenBank.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.fasta and not args.genbank:
        parser.error("at least one of --fasta or --genbank is required")

    data_file_path = Path(args.input)
    if not check_file(data_file_path):
        return 1
    primary_result = None
    if data_file_path.suffix.lower() in FASTA_SUFFIXES:
        primary_result = read_file(data_file_path, "fasta")
    if data_file_path.suffix.lower() in GENBANK_SUFFIXES:
        primary_result = read_file(data_file_path, "genbank")

    if not primary_result:
        log.warning("%s: 0 records", data_file_path)
        return 0

    records = uppercase_result(primary_result.records)
    seq_records = [
        SeqRecord(
            Seq(record.sequence),
            id=record.id,
            description=record.description,
            # GenBank output requires molecule_type; FASTA ignores it
            annotations={"molecule_type": record.molecule_type or record.type},
        )
        for record in records
    ]
    if args.fasta and not write_records(args.fasta, seq_records, "fasta"):
        return 1
    if args.genbank and not write_records(args.genbank, seq_records, "genbank"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
