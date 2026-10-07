from pathlib import Path

import pytest

from cobalt.cli.main import main

DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


def test_inspect_requires_input_arg(capsys):
    with pytest.raises(SystemExit):
        main([])
    assert "usage:" in capsys.readouterr().err


def test_file_not_found(capsys):
    exit_code = main(["inspect", "--overview-only", str(DATA_DIR / "ls_orchid_non_existing.fasta")])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error: file not found" in captured.out


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
