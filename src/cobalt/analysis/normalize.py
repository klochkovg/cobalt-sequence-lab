"""Normalizaiton helpers"""

from __future__ import annotations

from itertools import pairwise

from cobalt.model.record import SequenceRecord


def uppercase_result(records: list[SequenceRecord]) -> list[SequenceRecord]:
    """uppercase the sequence, naive approach for now
    No data copying, actual replacement
    """
    for record in records:
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
