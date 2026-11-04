"""Normalizaiton helpers"""

from __future__ import annotations

import io
import logging
from itertools import pairwise
from typing import Literal, get_args

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.processor import decode_quality
from cobalt.model.record import SequenceRecord

log = logging.getLogger(__name__)

# Biopython formats `normalize` writes
OutputFormat = Literal["fasta", "genbank", "fastq"]
OUTPUT_FORMATS: tuple[OutputFormat, ...] = get_args(OutputFormat)


def uppercase_result(records: list[SequenceRecord]) -> list[SequenceRecord]:
    """uppercase the sequence, naive approach for now
    No data copying, actual replacement
    """
    for record in records:
        if record.sequence is not None:
            record.sequence = record.sequence.upper()
    return records


# GenBank LOCUS lines reserve 16 characters for the name
MAX_LOCUS_NAME_LENGTH = 16
# Database tags in NCBI-style FASTA IDs (gi|2765658|emb|Z78533.1|...) followed by an accession
NCBI_DB_TAGS = {"gb", "emb", "dbj", "ref", "sp", "tr", "pir", "prf", "pdb", "tpg", "tpe", "tpd"}


def genbank_locus_name(record_id: str) -> str:
    """Return a LOCUS name of at most 16 characters for `record_id`.

    Short IDs are kept. For NCBI-style IDs the accession without version is used
    (gi|2765658|emb|Z78533.1|CIZ78533 -> Z78533); anything else is truncated.
    """
    if len(record_id) <= MAX_LOCUS_NAME_LENGTH:
        return record_id
    fields = record_id.split("|")
    for tag, value in pairwise(fields):
        accession = value.split(".", 1)[0]
        if tag in NCBI_DB_TAGS and 0 < len(accession) <= MAX_LOCUS_NAME_LENGTH:
            return accession
    return record_id[:MAX_LOCUS_NAME_LENGTH]


def build_seq_records(records: list[SequenceRecord]) -> list[SeqRecord]:
    """Uppercase `records` and convert them to Biopython records ready to write.

    Records with no sequence content (GenBank WGS/CONTIG) are skipped with a warning.
    """
    records = uppercase_result(records)
    undefined = [record.id for record in records if record.sequence is None]
    if undefined:
        log.warning(
            "skipping %d record(s) with no sequence content: %s",
            len(undefined),
            ", ".join(undefined),
        )
    return [
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


def records_for_format(seq_records: list[SeqRecord], fmt: OutputFormat) -> list[SeqRecord]:
    """Return the records written as `fmt`, logging what the format changes or drops.

    GenBank shortens long IDs in the LOCUS line; FASTQ keeps only records with qualities.
    """
    if fmt == "genbank":
        shortened = sum(1 for seq_record in seq_records if seq_record.name != seq_record.id)
        if shortened:
            log.info("%d ID(s) too long for GenBank LOCUS, shortened to accessions", shortened)
    if fmt != "fastq":
        return seq_records
    with_quality = [r for r in seq_records if "phred_quality" in r.letter_annotations]
    no_quality = [str(r.id) for r in seq_records if "phred_quality" not in r.letter_annotations]
    if no_quality:
        log.warning(
            "skipping %d record(s) with no qualities for FASTQ: %s",
            len(no_quality),
            ", ".join(no_quality),
        )
    return with_quality


def format_records(seq_records: list[SeqRecord], fmt: OutputFormat) -> str:
    """Return `seq_records` written as `fmt` (see `records_for_format`).

    Raises ValueError if Biopython can't write a record in this format.
    """
    buffer = io.StringIO()
    SeqIO.write(records_for_format(seq_records, fmt), buffer, fmt)
    return buffer.getvalue()
