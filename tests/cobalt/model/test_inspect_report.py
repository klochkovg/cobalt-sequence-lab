from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.processor import process_records
from cobalt.model.inspect import InspectRecord, build_inspect_report
from cobalt.model.qc import WarningKind


def make_result():
    records = [
        SeqRecord(Seq("ACGT"), id="a"),
        SeqRecord(Seq("MKVLA"), id="b"),
        SeqRecord(Seq("ACGU"), id="a"),
    ]
    return process_records(records, "fasta")


def test_report_summary():
    report = build_inspect_report("in.fasta", make_result(), "gzip")

    assert report.file == "in.fasta"
    assert report.records_num == 3
    assert report.format == "fasta"
    assert report.compression == "gzip"
    assert (report.min_length, report.max_length) == (4, 5)
    assert report.mean_length == 13 / 3
    assert report.molecule_types == {"DNA": 1, "protein": 1, "RNA": 1}
    assert report.warning_counts["duplicate_id"] == 1
    assert set(report.warning_counts) == {str(kind) for kind in WarningKind}
    assert [w.record_id for w in report.warnings] == ["a"]
    assert [r.id for r in report.records] == ["a", "b", "a"]
    assert isinstance(report.records[0], InspectRecord)


def test_report_overview_only():
    report = build_inspect_report("in.fasta", make_result(), None, overview_only=True)
    assert report.records_num == 3
    assert report.records == []


def test_report_limit():
    report = build_inspect_report("in.fasta", make_result(), None, limit=2)
    assert [r.id for r in report.records] == ["a", "b"]
    assert build_inspect_report("in.fasta", make_result(), None, limit=0).records == []


def test_report_empty_input():
    report = build_inspect_report("empty.fasta", None, None)

    assert report.records_num == 0
    assert report.format is None
    assert report.min_length is None
    assert report.records == []
    assert report.warning_counts == {str(kind): 0 for kind in WarningKind}


def test_report_to_dict_is_plain():
    data = build_inspect_report("in.fasta", make_result(), None).to_dict()
    assert data["warnings"][0] == {
        "record_id": "a",
        "kind": "duplicate_id",
        "message": "duplicate ID",
    }
    assert data["records"][1]["type"] == "protein"
