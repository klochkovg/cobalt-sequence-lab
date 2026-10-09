from pathlib import Path

import pytest

from cobalt.cli.main import main

DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


def test_inspect_requires_input_arg(capsys):
    with pytest.raises(SystemExit):
        main([])
    assert "usage:" in capsys.readouterr().err


def test_file_not_found(capsys, caplog):
    exit_code = main(["inspect", "--overview-only", str(DATA_DIR / "ls_orchid_non_existing.fasta")])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "file not found" in caplog.text
    assert captured.out == ""


def test_number_of_records(capsys):
    exit_code = main(["inspect", "--overview-only", str(DATA_DIR / "ls_orchid.fasta")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "94 record(s)" in captured.out


def test_genbank_gb_suffix(capsys, tmp_path):
    gb_file = tmp_path / "ls_orchid.gb"
    gb_file.write_text((DATA_DIR / "ls_orchid.gbk").read_text())

    exit_code = main(["inspect", "--overview-only", str(gb_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "94 record(s)" in captured.out


def test_errors_go_to_stderr(capsys):
    exit_code = main(["inspect", str(DATA_DIR / "ls_orchid_non_existing.fasta")])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "ERROR" in captured.err
    assert "file not found" in captured.err


def test_quiet_hides_warnings(capsys, tmp_path):
    path = tmp_path / "nothing.fasta"
    path.write_text("")

    exit_code = main(["-q", "validate", str(path)])

    assert exit_code == 0
    assert "0 records" not in capsys.readouterr().err


def test_inspect_summary_counts(capsys, tmp_path):
    path = tmp_path / "mixed.fasta"
    path.write_text(">s1\nACGT\n>s1\nACGT\n>p1\nMKVLAAGIC\n>bad\nACGT12\n")

    exit_code = main(["inspect", "--overview-only", str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "molecule types: DNA=2, protein=1, unknown=1" in out
    assert "warnings: 2 (duplicate_id=1, empty_sequence=0, invalid_characters=1)" in out
    assert "s1: duplicate ID" in out


def test_inspect_summary_genbank(capsys):
    exit_code = main(["inspect", "--overview-only", str(DATA_DIR / "ls_orchid.gbk")])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "molecule types: DNA=94" in out
    assert "warnings: 0 (duplicate_id=0, empty_sequence=0, invalid_characters=0)" in out
