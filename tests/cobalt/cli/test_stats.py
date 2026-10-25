import csv
import gzip
import io
import json
import logging
from pathlib import Path

import pytest
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.cli.main import main
from cobalt.cli.stats import output_format
from cobalt.model.stats import STATS_FIELDNAMES

DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


def test_stats_cmd_input(capsys):
    exit_code = main(["stats", "--input", "CATTGTTGAGATCACATAATAATTGATCGAGTTAAT", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0

    records = json.loads(captured.out)
    record = records[0]
    assert record["id"] == "direct_input"
    assert record["length"] == 36
    assert record["type"] == "DNA"
    assert record["source_format"] == "raw"


def test_stats_protein_has_no_gc(capsys):
    exit_code = main(["stats", "--input", "MKVLAAGIC", "--json"])

    record = json.loads(capsys.readouterr().out)[0]
    assert exit_code == 0
    assert record["type"] == "protein"
    assert record["gc_fraction"] is None


def test_stats_ambiguous_dna(capsys):
    exit_code = main(["stats", "--input", "ACGTRYACGT", "--json"])

    record = json.loads(capsys.readouterr().out)[0]
    assert exit_code == 0
    assert record["type"] == "DNA"
    assert record["alphabetic_class"] == "ambiguous"
    assert record["ambiguity_fraction"] == 0.2
    assert record["invalid_char_count"] == 0


def test_stats_fasta_file_alphabet_class(capsys):
    exit_code = main(["stats", str(DATA_DIR / "ls_orchid.fasta")])

    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert exit_code == 0
    assert len(rows) == 94
    assert "invalid" not in {row["alphabetic_class"] for row in rows}


def run_stats(capsys, *args: str) -> tuple[int, str]:
    exit_code = main(["stats", *args])
    return exit_code, capsys.readouterr().out


def test_stats_sort_by_length(capsys):
    exit_code, out = run_stats(capsys, str(DATA_DIR / "ls_orchid.fasta"), "--sort", "length")
    lengths = [int(row["length"]) for row in csv.DictReader(io.StringIO(out))]
    assert exit_code == 0
    assert lengths == sorted(lengths)

    exit_code, out = run_stats(
        capsys, str(DATA_DIR / "ls_orchid.fasta"), "--sort", "length", "--desc", "--json"
    )
    lengths = [row["length"] for row in json.loads(out)]
    assert lengths == sorted(lengths, reverse=True)


def test_stats_sort_by_id(capsys):
    exit_code, out = run_stats(capsys, str(DATA_DIR / "ls_orchid.fasta"), "--sort", "id", "--json")
    row_ids = [row["id"] for row in json.loads(out)]
    assert exit_code == 0
    assert row_ids == sorted(row_ids)


def test_stats_genbank_annotation_columns(capsys):
    exit_code, out = run_stats(capsys, str(DATA_DIR / "ls_orchid.gbk"), "--json")
    row = json.loads(out)[0]
    assert exit_code == 0
    assert row["organism"] == "Cypripedium irapeanum"
    assert row["molecule_type"] == "DNA"
    assert row["topology"] == "linear"
    assert row["feature_count"] > 0


def test_stats_fasta_annotation_columns_empty(capsys):
    exit_code, out = run_stats(capsys, str(DATA_DIR / "ls_orchid.fasta"))
    row = next(csv.DictReader(io.StringIO(out)))
    assert exit_code == 0
    assert row["organism"] == ""
    assert row["molecule_type"] == ""
    assert row["feature_count"] == "0"


def test_stats_csv_and_json_have_same_rows(capsys):
    path = str(DATA_DIR / "ls_orchid.gbk")
    _, csv_out = run_stats(capsys, path)
    _, json_out = run_stats(capsys, path, "--json")
    csv_rows = list(csv.DictReader(io.StringIO(csv_out)))
    json_rows = json.loads(json_out)
    assert len(csv_rows) == len(json_rows)
    for csv_row, json_row in zip(csv_rows, json_rows, strict=True):
        assert list(csv_row) == list(json_row)
        assert csv_row == {k: "" if v is None else str(v) for k, v in json_row.items()}


def test_stats_gzip_fasta(capsys, tmp_path):
    path = tmp_path / "ls_orchid.fasta.gz"
    path.write_bytes(gzip.compress((DATA_DIR / "ls_orchid.fasta").read_bytes()))

    exit_code = main(["stats", str(path), "--json"])

    assert exit_code == 0
    records = json.loads(capsys.readouterr().out)
    assert len(records) == 94
    assert records[0]["source_format"] == "fasta"


def test_stats_parquet_matches_json(capsys, tmp_path):
    pq = pytest.importorskip("pyarrow.parquet")
    path = str(DATA_DIR / "ls_orchid.gbk")
    out = tmp_path / "stats.parquet"

    exit_code, _ = run_stats(capsys, path, "--format", "parquet", "--out", str(out))
    _, json_out = run_stats(capsys, path, "--json")

    assert exit_code == 0
    assert pq.read_table(out).to_pylist() == json.loads(json_out)


def test_stats_parquet_keeps_types_of_empty_annotations(capsys, tmp_path):
    pq = pytest.importorskip("pyarrow.parquet")
    out = tmp_path / "stats.parquet"

    exit_code, _ = run_stats(
        capsys, str(DATA_DIR / "ls_orchid.fasta"), "--format", "parquet", "--out", str(out)
    )

    schema = pq.read_schema(out)
    assert exit_code == 0
    assert schema.names == STATS_FIELDNAMES
    assert str(schema.field("organism").type) == "string"
    assert str(schema.field("mean_quality").type) == "double"
    assert str(schema.field("min_quality").type) == "int64"


def test_stats_parquet_needs_out(capsys):
    exit_code, out = run_stats(capsys, "--input", "ACGT", "--format", "parquet")
    assert exit_code == 1
    assert out == ""


def test_stats_format_json_same_as_json_flag(capsys):
    _, by_flag = run_stats(capsys, "--input", "ACGT", "--json")
    _, by_format = run_stats(capsys, "--input", "ACGT", "--format", "json")
    assert by_flag == by_format


@pytest.mark.parametrize(
    ("fmt", "out", "expected"),
    [
        (None, None, "csv"),
        (None, "stats.csv", "csv"),
        (None, "stats.JSON", "json"),
        (None, "dir.v1/stats.parquet", "parquet"),
        (None, "stats.pq", "parquet"),
        (None, "stats.tsv", "csv"),
        (None, "stats", "csv"),
        ("csv", "stats.json", "csv"),
    ],
)
def test_output_format(fmt, out, expected):
    assert output_format(fmt, out) == expected


def test_stats_out_json_extension_writes_json(capsys, tmp_path):
    out = tmp_path / "stats.json"
    exit_code, _ = run_stats(capsys, "--input", "ACGT", "--out", str(out))
    assert exit_code == 0
    assert json.loads(out.read_text())[0]["id"] == "direct_input"


def test_stats_out_parquet_extension_writes_parquet(capsys, tmp_path):
    pq = pytest.importorskip("pyarrow.parquet")
    out = tmp_path / "stats.parquet"
    exit_code, _ = run_stats(capsys, "--input", "ACGT", "--out", str(out))
    assert exit_code == 0
    assert pq.read_table(out).num_rows == 1


def test_stats_format_overrides_extension(capsys, tmp_path):
    out = tmp_path / "stats.json"
    exit_code, _ = run_stats(capsys, "--input", "ACGT", "--format", "csv", "--out", str(out))
    assert exit_code == 0
    assert out.read_text().startswith("id,length,")


@pytest.mark.parametrize("out", ["stats.tsv", "stats"])
def test_output_format_warns_on_unknown_extension(caplog, out):
    with caplog.at_level(logging.WARNING, logger="cobalt.cli.stats"):
        assert output_format(None, out) == "csv"
    assert "unrecognized extension" in caplog.text
    assert out in caplog.text


@pytest.mark.parametrize(
    ("fmt", "out"),
    [(None, None), (None, "stats.csv"), (None, "stats.PQ"), ("json", "stats.tsv")],
)
def test_output_format_no_warning(caplog, fmt, out):
    with caplog.at_level(logging.WARNING, logger="cobalt.cli.stats"):
        output_format(fmt, out)
    assert caplog.records == []


def test_stats_genbank_mrna_has_no_invalid_chars(capsys, tmp_path):
    path = tmp_path / "mrna.gb"
    record = SeqRecord(
        Seq("ATGGCTTGTACGTAA"), id="NM_1", name="NM_1", annotations={"molecule_type": "mRNA"}
    )
    SeqIO.write(record, path, "genbank")

    exit_code, out = run_stats(capsys, str(path), "--json")
    row = json.loads(out)[0]
    assert exit_code == 0
    assert row["type"] == "RNA"
    assert row["invalid_char_count"] == 0
    assert row["alphabetic_class"] == "unambiguous"


def test_stats_length_only_record(capsys, length_only_genbank):
    exit_code, out = run_stats(capsys, str(length_only_genbank))
    rows = list(csv.DictReader(io.StringIO(out)))
    assert exit_code == 0
    assert [row["id"] for row in rows] == ["FULL1", "WGS1"]
    wgs = rows[1]
    assert wgs["length"] == "50"
    assert wgs["gc_fraction"] == wgs["ambiguity_fraction"] == wgs["invalid_char_count"] == ""
    assert wgs["description"] == "WGS master record"


def test_stats_length_only_record_parquet(capsys, tmp_path, length_only_genbank):
    pq = pytest.importorskip("pyarrow.parquet")
    out = tmp_path / "stats.parquet"
    exit_code, _ = run_stats(capsys, str(length_only_genbank), "--out", str(out))
    wgs = pq.read_table(out).to_pylist()[1]
    assert exit_code == 0
    assert wgs["invalid_char_count"] is None
    assert wgs["ambiguity_fraction"] is None


def test_stats_raw_input_has_empty_description(capsys):
    exit_code, out = run_stats(capsys, "--input", "ACGT", "--json")
    assert exit_code == 0
    assert json.loads(out)[0]["description"] == ""


@pytest.fixture
def empty_fasta(tmp_path):
    path = tmp_path / "empty.fasta"
    path.write_text("")
    return path


def test_stats_empty_file_csv_has_header(capsys, empty_fasta):
    exit_code, out = run_stats(capsys, str(empty_fasta))
    assert exit_code == 0
    assert out == ",".join(STATS_FIELDNAMES) + "\r\n"


def test_stats_empty_file_json_is_empty_list(capsys, empty_fasta):
    exit_code, out = run_stats(capsys, str(empty_fasta), "--json")
    assert exit_code == 0
    assert json.loads(out) == []


def test_stats_empty_file_parquet_has_schema(capsys, tmp_path, empty_fasta):
    pq = pytest.importorskip("pyarrow.parquet")
    out = tmp_path / "stats.parquet"
    exit_code, _ = run_stats(capsys, str(empty_fasta), "--out", str(out))
    table = pq.read_table(out)
    assert exit_code == 0
    assert table.num_rows == 0
    assert table.schema.names == STATS_FIELDNAMES


def test_stats_empty_file_warns(capsys, caplog, empty_fasta):
    run_stats(capsys, str(empty_fasta))
    assert "0 records" in caplog.text


FASTA = str(DATA_DIR / "ls_orchid.fasta")
GENBANK = str(DATA_DIR / "ls_orchid.gbk")


def test_stats_multiple_files_in_order(capsys):
    exit_code, out = run_stats(capsys, FASTA, GENBANK, "--json")
    rows = json.loads(out)
    assert exit_code == 0
    assert len(rows) == 94 + 94
    assert {row["source_file"] for row in rows[:94]} == {FASTA}
    assert {row["source_file"] for row in rows[94:]} == {GENBANK}
    assert {row["source_format"] for row in rows[:94]} == {"fasta"}
    assert {row["source_format"] for row in rows[94:]} == {"genbank"}


def test_stats_multiple_files_sort_across_files(capsys):
    exit_code, out = run_stats(capsys, FASTA, GENBANK, "--json", "--sort", "length")
    lengths = [row["length"] for row in json.loads(out)]
    assert exit_code == 0
    assert lengths == sorted(lengths)
    assert len(lengths) == 188


def test_stats_multiple_files_missing_one_fails(capsys, caplog, tmp_path):
    out_path = tmp_path / "stats.csv"
    exit_code, out = run_stats(
        capsys, FASTA, str(tmp_path / "missing.fasta"), GENBANK, "--out", str(out_path)
    )
    assert exit_code == 1
    assert out == ""
    assert not out_path.exists()
    assert "file not found" in caplog.text


def test_stats_multiple_files_empty_one_warns(capsys, caplog, empty_fasta):
    exit_code, out = run_stats(capsys, FASTA, str(empty_fasta), "--json")
    assert exit_code == 0
    assert len(json.loads(out)) == 94
    assert f"{empty_fasta}: 0 records" in caplog.text


def test_stats_direct_input_has_no_source_file(capsys):
    exit_code, out = run_stats(capsys, "--input", "ACGT", "--json")
    assert exit_code == 0
    assert json.loads(out)[0]["source_file"] is None


def test_stats_file_and_direct_input_are_exclusive(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["stats", FASTA, "--input", "ACGT"])
    assert exc.value.code == 2


def test_stats_multiple_files_parquet_matches_json(capsys, tmp_path):
    pq = pytest.importorskip("pyarrow.parquet")
    out = tmp_path / "stats.parquet"

    exit_code, _ = run_stats(capsys, FASTA, GENBANK, "--out", str(out))
    _, json_out = run_stats(capsys, FASTA, GENBANK, "--json")

    assert exit_code == 0
    assert pq.read_table(out).to_pylist() == json.loads(json_out)


@pytest.mark.parametrize("column", ["gc_fraction", "ambiguity_fraction", "invalid_char_count"])
def test_stats_sort_by_computed_column(capsys, column):
    exit_code, out = run_stats(capsys, FASTA, "--sort", column, "--desc", "--json")
    values = [row[column] for row in json.loads(out)]
    assert exit_code == 0
    assert values == sorted(values, reverse=True)


def test_stats_fastq_json(capsys):
    exit_code, out = run_stats(capsys, str(DATA_DIR / "sample.fastq"), "--json")

    assert exit_code == 0
    rows = json.loads(out)
    assert [row["id"] for row in rows] == ["read1", "read2", "read3", "read4"]
    assert rows[0]["source_format"] == "fastq"
    assert (rows[0]["mean_quality"], rows[0]["min_quality"], rows[0]["q30_fraction"]) == (
        40.0,
        40,
        1.0,
    )
    assert "quality" not in rows[0]


def test_stats_fastq_sort_by_mean_quality(capsys, tmp_path):
    path = tmp_path / "reads.fastq.gz"
    path.write_bytes(gzip.compress((DATA_DIR / "sample.fastq").read_bytes()))

    exit_code, out = run_stats(capsys, str(path), "--sort", "mean_quality", "--desc")

    assert exit_code == 0
    assert [row["id"] for row in csv.DictReader(io.StringIO(out))] == [
        "read1",
        "read4",
        "read3",
        "read2",
    ]


def test_stats_fastq_parquet_matches_json(capsys, tmp_path):
    pq = pytest.importorskip("pyarrow.parquet")
    path = str(DATA_DIR / "sample.fastq")
    out = tmp_path / "stats.parquet"

    exit_code, _ = run_stats(capsys, path, "--format", "parquet", "--out", str(out))
    _, json_out = run_stats(capsys, path, "--json")

    assert exit_code == 0
    assert pq.read_table(out).to_pylist() == json.loads(json_out)
