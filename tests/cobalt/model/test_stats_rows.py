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


# GC (N is not counted): g=1.0, a=0.0, n=0.5; ambiguity: n=0.5, others 0;
# invalid chars: x=1, others 0.
# p is a protein and x has an unknown type, so their gc_fraction is None.
MIXED = records(("n", "GANN"), ("g", "GGCC"), ("p", "MKVLW"), ("a", "AATT"), ("x", "ACGT1"))


def test_sort_by_gc_fraction_puts_none_last():
    rows = build_stats_rows(MIXED, sort=SortKey.GC_FRACTION)
    assert ids(rows) == ["a", "n", "g", "p", "x"]


def test_sort_by_gc_fraction_descending_keeps_none_last():
    rows = build_stats_rows(MIXED, sort=SortKey.GC_FRACTION, descending=True)
    assert ids(rows) == ["g", "n", "a", "p", "x"]


def test_sort_by_ambiguity_fraction():
    rows = build_stats_rows(MIXED, sort=SortKey.AMBIGUITY_FRACTION, descending=True)
    assert ids(rows)[0] == "n"
    # the rest tie at 0.0 and keep their input order
    assert ids(rows)[1:] == ["g", "p", "a", "x"]


def test_sort_by_invalid_char_count():
    rows = build_stats_rows(MIXED, sort=SortKey.INVALID_CHAR_COUNT, descending=True)
    assert ids(rows) == ["x", "n", "g", "p", "a"]


def test_sort_length_only_record_goes_last(length_only_genbank):
    from cobalt.analysis.processor import load_file

    result = load_file(length_only_genbank)
    assert result is not None
    for key in (SortKey.GC_FRACTION, SortKey.AMBIGUITY_FRACTION, SortKey.INVALID_CHAR_COUNT):
        for descending in (False, True):
            rows = build_stats_rows(result.records, sort=key, descending=descending)
            assert ids(rows)[-1] == "WGS1"


def test_quality_columns_follow_feature_count():
    assert STATS_FIELDNAMES[-4:] == ["feature_count", "mean_quality", "min_quality", "q30_fraction"]


def test_sort_by_mean_quality_puts_none_last():
    fastq = [
        SeqRecord(Seq("ACGT"), id="low", letter_annotations={"phred_quality": [10, 10, 10, 10]}),
        SeqRecord(Seq("ACGT"), id="high", letter_annotations={"phred_quality": [40, 40, 40, 40]}),
    ]
    sample = process_records(fastq, "fastq").records + records(("none", "ACGT"))

    rows = build_stats_rows(sample, sort=SortKey.MEAN_QUALITY)
    assert ids(rows) == ["low", "high", "none"]
    rows = build_stats_rows(sample, sort=SortKey.MEAN_QUALITY, descending=True)
    assert ids(rows) == ["high", "low", "none"]
