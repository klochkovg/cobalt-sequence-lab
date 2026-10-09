from pathlib import Path

import pytest
from Bio import SeqIO
from Bio.Seq import Seq

from cobalt.analysis.processor import process_records
from cobalt.model.qc import RecordWarning, WarningKind
from cobalt.model.record import AnalysisResult, SequenceRecord

TEST_DATA = Path(__file__).parents[2] / "test_data"


def make_record_dict(**overrides):
    data = {
        "id": "seq1",
        "description": "seq1 first",
        "length": 6,
        "sequence": Seq("ACGTNA"),
        "gc_fraction": 0.4,
        "ambiguity_fraction": 1 / 6,
        "invalid_char_count": "0",
        "alphabetic_class": "ambiguous",
        "source_format": "fasta",
        "type": "DNA",
        "organism": None,
        "molecule_type": None,
        "topology": None,
        "feature_count": 0,
    }
    data.update(overrides)
    return data


def make_result_dict(**overrides):
    data = {
        "warnings": [{"record_id": "seq2", "kind": "empty_sequence", "message": "empty sequence"}],
        "records_num": 1,
        "min": 6,
        "max": 6,
        "mean": 6.0,
        "type": "fasta",
        "records": [make_record_dict()],
    }
    data.update(overrides)
    return data


def test_sequence_record_from_dict_fields():
    record = SequenceRecord.from_dict(make_record_dict())

    assert record.id == "seq1"
    assert record.description == "seq1 first"
    assert record.length == 6
    assert record.type == "DNA"
    assert record.source_format == "fasta"
    assert record.alphabetic_class == "ambiguous"
    assert record.gc_fraction == pytest.approx(0.4)
    assert record.ambiguity_fraction == pytest.approx(1 / 6)


def test_sequence_record_from_dict_converts_types():
    record = SequenceRecord.from_dict(make_record_dict())

    assert record.sequence == "ACGTNA"
    assert type(record.sequence) is str
    assert record.invalid_char_count == 0
    assert type(record.invalid_char_count) is int


def test_sequence_record_from_dict_optional_defaults():
    data = make_record_dict()
    for key in ("organism", "molecule_type", "topology", "feature_count"):
        del data[key]

    record = SequenceRecord.from_dict(data)

    assert record.organism is None
    assert record.molecule_type is None
    assert record.topology is None
    assert record.quality is None
    assert record.feature_count == 0


def test_sequence_record_from_dict_genbank_annotations():
    record = SequenceRecord.from_dict(
        make_record_dict(
            organism="Cypripedium irapeanum",
            molecule_type="DNA",
            topology="linear",
            feature_count=5,
            source_format="genbank",
        )
    )

    assert record.organism == "Cypripedium irapeanum"
    assert record.molecule_type == "DNA"
    assert record.topology == "linear"
    assert record.feature_count == 5


def test_sequence_record_from_dict_missing_required_key():
    data = make_record_dict()
    del data["id"]

    with pytest.raises(KeyError):
        SequenceRecord.from_dict(data)


def test_sequence_record_to_dict():
    data = SequenceRecord.from_dict(make_record_dict()).to_dict()

    assert data["id"] == "seq1"
    assert data["sequence"] == "ACGTNA"
    assert data["invalid_char_count"] == 0
    assert data["quality"] is None
    assert set(data) == set(make_record_dict()) | {"quality"}


def test_sequence_record_round_trip():
    record = SequenceRecord.from_dict(make_record_dict(organism="Homo sapiens"))

    assert SequenceRecord.from_dict(record.to_dict()) == record


def test_analysis_result_from_dict():
    result = AnalysisResult.from_dict(make_result_dict())

    assert result.warnings == [RecordWarning("seq2", WarningKind.EMPTY_SEQUENCE, "empty sequence")]
    assert str(result.warnings[0]) == "seq2: empty sequence"
    assert result.records_num == 1
    assert result.min == 6
    assert result.max == 6
    assert result.mean == pytest.approx(6.0)
    assert result.type == "fasta"
    assert len(result.records) == 1
    assert isinstance(result.records[0], SequenceRecord)
    assert result.records[0].id == "seq1"


def test_analysis_result_from_dict_without_records():
    data = make_result_dict()
    del data["records"]

    result = AnalysisResult.from_dict(data)

    assert result.records == []


def test_analysis_result_to_dict_nests_records_as_dicts():
    data = AnalysisResult.from_dict(make_result_dict()).to_dict()

    assert set(data) == set(make_result_dict())
    assert isinstance(data["records"][0], dict)
    assert data["records"][0]["sequence"] == "ACGTNA"


def test_analysis_result_round_trip():
    result = AnalysisResult.from_dict(make_result_dict())

    assert AnalysisResult.from_dict(result.to_dict()) == result


@pytest.mark.parametrize(
    ("filename", "fmt"),
    [("ls_orchid.fasta", "fasta"), ("ls_orchid.gbk", "genbank")],
)
def test_analysis_result_from_process_records(filename, fmt):
    seq_records = list(SeqIO.parse(TEST_DATA / filename, fmt))

    result = process_records(seq_records, fmt)

    assert isinstance(result, AnalysisResult)
    assert result.records_num == len(seq_records)
    assert [r.id for r in result.records] == [r.id for r in seq_records]
    assert [r.sequence for r in result.records] == [str(r.seq) for r in seq_records]
    assert all(type(r.invalid_char_count) is int for r in result.records)
    assert AnalysisResult.from_dict(result.to_dict()) == result


def test_process_records_empty_returns_none():
    assert process_records([], "fasta") is None
