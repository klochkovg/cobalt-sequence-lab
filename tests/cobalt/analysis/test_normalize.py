"""Tests for normalize helpers"""

from cobalt.analysis.normalize import uppercase_result
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
