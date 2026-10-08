import csv
import io
import json
from pathlib import Path

from cobalt.cli.main import main

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
