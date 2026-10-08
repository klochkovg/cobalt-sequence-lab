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
