"""CLI command: foldrna."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.folding import ADAPTERS, DEFAULT_ADAPTER, fold_records, write_fold_results
from cobalt.analysis.processor import InputFileError, load_file, process_records
from cobalt.model.record import SequenceRecord

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for foldrna command."""
    parser = argparse.ArgumentParser(prog="cobalt foldrna")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "input", nargs="*", help="Input FASTA/GenBank/FASTQ file(s) (plain, gzip or bzip2)"
    )
    source.add_argument(
        "--input",
        dest="raw_sequence",
        metavar="SEQ",
        help="Direct sequence string, e.g. --input GGGAAAUCC",
    )
    parser.add_argument(
        "--adapter",
        choices=sorted(ADAPTERS),
        default=DEFAULT_ADAPTER,
        help=f"Folding backend (default: {DEFAULT_ADAPTER})",
    )
    parser.add_argument("--out", required=False, help="Output file path (default: stdout)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the foldrna command."""
    args = build_parser().parse_args(argv)

    records: list[SequenceRecord] = []
    if args.raw_sequence is not None:
        record = SeqRecord(Seq(args.raw_sequence), id="direct_input")
        primary_result = process_records([record], "raw")
        if primary_result is None:
            log.warning("direct input: 0 records")
        else:
            records.extend(primary_result.records)
    else:
        # Any unreadable file fails the whole run before anything is folded
        for input_path in args.input:
            try:
                file_result = load_file(Path(input_path))
            except InputFileError as exc:
                log.error("%s", exc)
                return 1
            if file_result is None:
                log.warning("%s: 0 records", input_path)
            else:
                records.extend(file_result.records)

    try:
        results = fold_records(records, args.adapter)
    except ImportError as exc:
        log.error(
            "foldrna --adapter %s requires optional dependencies (%s is missing). "
            'Install them with: pip install "cobalt-sequence-lab[rna]"',
            args.adapter,
            exc.name,
        )
        return 1

    if args.out:
        try:
            with open(args.out, "w") as f:
                write_fold_results(f, results)
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
        write_fold_results(sys.stdout, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
