"""CLI command: normalize."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.normalize import genbank_locus_name, uppercase_result
from cobalt.analysis.processor import InputFileError, decode_quality, load_file

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

    records = uppercase_result(primary_result.records)
    undefined = [record.id for record in records if record.sequence is None]
    if undefined:
        log.warning(
            "skipping %d record(s) with no sequence content: %s",
            len(undefined),
            ", ".join(undefined),
        )
    seq_records = [
        SeqRecord(
            Seq(record.sequence),
            id=record.id,
            # Used for the GenBank LOCUS line, which only fits 16 characters
            name=genbank_locus_name(record.id),
            description=record.description,
            # GenBank output requires molecule_type; FASTA ignores it
            annotations={"molecule_type": record.molecule_type or record.type},
            # FASTQ output requires phred_quality; FASTA and GenBank ignore it
            letter_annotations=(
                {"phred_quality": decode_quality(record.quality)}
                if record.quality is not None
                else None
            ),
        )
        for record in records
        if record.sequence is not None
    ]
    if args.fasta and not write_records(args.fasta, seq_records, "fasta"):
        return 1
    if args.genbank:
        shortened = sum(1 for seq_record in seq_records if seq_record.name != seq_record.id)
        if shortened:
            log.info("%d ID(s) too long for GenBank LOCUS, shortened to accessions", shortened)
        if not write_records(args.genbank, seq_records, "genbank"):
            return 1
    if args.fastq:
        with_quality = [r for r in seq_records if "phred_quality" in r.letter_annotations]
        no_quality = [
            record.id
            for record in records
            if record.sequence is not None and record.quality is None
        ]
        if no_quality:
            log.warning(
                "skipping %d record(s) with no qualities for FASTQ: %s",
                len(no_quality),
                ", ".join(no_quality),
            )
        if not write_records(args.fastq, with_quality, "fastq"):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
