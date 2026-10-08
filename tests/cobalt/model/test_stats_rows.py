from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.processor import process_records
from cobalt.model.stats import STATS_FIELDNAMES, SortKey, StatsRow, build_stats_rows


def records(*items: tuple[str, str]):
    seq_records = [SeqRecord(Seq(seq), id=seq_id) for seq_id, seq in items]
    return process_records(seq_records, "raw").records


SAMPLE = records(("b", "ACGTACGT"), ("c", "AC"), ("a", "ACGTA"), ("d", "ACGTA"))


def ids(rows: list[StatsRow]) -> list[str]:
    return [row.id for row in rows]


def test_default_keeps_input_order():
    assert ids(build_stats_rows(SAMPLE)) == ["b", "c", "a", "d"]


def test_sort_by_id():
    assert ids(build_stats_rows(SAMPLE, sort=SortKey.ID)) == ["a", "b", "c", "d"]
    assert ids(build_stats_rows(SAMPLE, sort=SortKey.ID, descending=True)) == ["d", "c", "b", "a"]


def test_sort_by_length_is_stable():
    # a and d have equal length and keep their input order
    assert ids(build_stats_rows(SAMPLE, sort=SortKey.LENGTH)) == ["c", "a", "d", "b"]
    assert ids(build_stats_rows(SAMPLE, sort=SortKey.LENGTH, descending=True)) == [
        "b",
        "a",
        "d",
        "c",
    ]


def test_sort_does_not_mutate_input():
    before = ids(SAMPLE)
    build_stats_rows(SAMPLE, sort=SortKey.ID)
    assert [record.id for record in SAMPLE] == before


def test_row_columns_in_order():
    row = build_stats_rows(SAMPLE)[0].to_dict()
    assert list(row) == STATS_FIELDNAMES
    for column in ("organism", "molecule_type", "topology", "feature_count"):
        assert column in STATS_FIELDNAMES
