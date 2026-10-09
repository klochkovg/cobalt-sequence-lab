"""Tests for normalize helpers"""

import pytest

from cobalt.analysis.normalize import genbank_locus_name, uppercase_result
from cobalt.model.record import SequenceRecord


def make_record(sequence: str) -> SequenceRecord:
    return SequenceRecord(
        id="seq1",
        description="",
        length=len(sequence),
        sequence=sequence,
        gc_fraction=0.0,
        ambiguity_fraction=0.0,
        invalid_char_count=0,
        alphabetic_class="unambiguous",
        source_format="raw",
        type="RNA",
    )


def test_uppercase():
    test_data = [make_record("AdGcUAgU")]
    test_result = uppercase_result(test_data)
    assert test_result[0].sequence == "ADGCUAGU"


@pytest.mark.parametrize(
    ("record_id", "expected"),
    [
        ("Z78533.1", "Z78533.1"),
        ("exactly16chars__", "exactly16chars__"),
        ("gi|2765658|emb|Z78533.1|CIZ78533", "Z78533"),
        ("gi|123456789|ref|NM_000546.6|", "NM_000546"),
        ("sp|P69905|HBA_HUMAN_LONG_NAME", "P69905"),
        ("a_very_long_identifier_without_pipes", "a_very_long_iden"),
    ],
)
def test_genbank_locus_name(record_id, expected):
    assert genbank_locus_name(record_id) == expected
