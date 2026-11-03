from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.processor import process_records
from cobalt.model.qc import WarningKind, build_qc_report


def result_of(*records):
    return process_records([SeqRecord(Seq(seq), id=seq_id) for seq_id, seq in records], "fasta")


def test_qc_report_with_warnings():
    report = build_qc_report("in.fasta", result_of(("a", "ACGT"), ("a", "AC!T")), "bzip2")

    assert report.file == "in.fasta"
    assert report.records_num == 2
    assert report.format == "fasta"
    assert report.compression == "bzip2"
    assert report.passed is False
    assert report.warning_counts["duplicate_id"] == 1
    assert report.warning_counts["invalid_characters"] == 1
    assert set(report.warning_counts) == {str(kind) for kind in WarningKind}
    assert {w.kind for w in report.warnings} == {
        WarningKind.DUPLICATE_ID,
        WarningKind.INVALID_CHARACTERS,
    }


def test_qc_report_clean_input():
    report = build_qc_report("in.fasta", result_of(("a", "ACGT"), ("b", "MKVLA")), None)

    assert report.passed is True
    assert report.warnings == []
    assert set(report.warning_counts.values()) == {0}


def test_qc_report_empty_input():
    report = build_qc_report("empty.fasta", None, None)

    assert report.records_num == 0
    assert report.format is None
    assert report.passed is True
    assert report.warning_counts == {str(kind): 0 for kind in WarningKind}


def test_qc_report_to_dict_is_plain():
    data = build_qc_report(
        "in.fasta",
        result_of(
            ("a", ""),
        ),
        None,
    ).to_dict()

    assert data["passed"] is False
    assert data["warnings"] == [
        {"record_id": "a", "kind": "empty_sequence", "message": "empty sequence"}
    ]
