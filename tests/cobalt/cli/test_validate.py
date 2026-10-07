from pathlib import Path

import pytest

from cobalt.cli.main import main

DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


def write_fasta(path: Path, records: list[tuple[str, str]]) -> Path:
    path.write_text("".join(f">{seq_id}\n{seq}\n" for seq_id, seq in records))
    return path


def run_warnings(capsys, path: Path) -> tuple[int, str]:
    exit_code = main(["validate", "--warnings", str(path)])
    return exit_code, capsys.readouterr().out


def test_validate_warnings_mode(capsys):
    exit_code, out = run_warnings(capsys, DATA_DIR / "ls_orchid.fasta")

    assert exit_code == 0
    assert "warning(s) found" in out
    assert "id,length" not in out


def test_validate_warnings_file_not_found(capsys, caplog):
    exit_code, out = run_warnings(capsys, DATA_DIR / "ls_orchid_non_existing.fasta")

    assert exit_code == 1
    assert "file not found" in caplog.text
    assert out == ""


def test_validate_warnings_unsupported_extension(capsys, caplog, tmp_path):
    path = tmp_path / "input.txt"
    path.write_text(">seq1\nACGT\n")

    exit_code, out = run_warnings(capsys, path)

    assert exit_code == 1
    assert "unsupported extension" in caplog.text
    assert out == ""


def test_validate_warnings_clean_file(capsys, tmp_path):
    path = write_fasta(tmp_path / "clean.fasta", [("seq1", "ACGT"), ("seq2", "GGCC")])

    exit_code, out = run_warnings(capsys, path)

    assert exit_code == 0
    assert "warning:" not in out
    assert "0 warning(s) found" in out


def test_validate_warnings_duplicate_id(capsys, tmp_path):
    path = write_fasta(tmp_path / "dup.fasta", [("seq1", "ACGT"), ("seq1", "GGCC")])

    exit_code, out = run_warnings(capsys, path)

    assert exit_code == 0
    assert "warning: seq1: duplicate ID" in out
    assert "1 warning(s) found" in out


def test_validate_warnings_empty_sequence(capsys, tmp_path):
    path = write_fasta(tmp_path / "empty.fasta", [("seq1", "ACGT"), ("seq2", "")])

    exit_code, out = run_warnings(capsys, path)

    assert exit_code == 0
    assert "warning: seq2: empty sequence" in out
    assert "1 warning(s) found" in out


def test_validate_warnings_invalid_characters(capsys, tmp_path):
    path = write_fasta(tmp_path / "invalid.fasta", [("seq1", "AC*GT1")])

    exit_code, out = run_warnings(capsys, path)

    assert exit_code == 0
    assert "warning: seq1: invalid characters ['*', '1']" in out


def test_validate_warnings_multiple_issues(capsys, tmp_path):
    path = write_fasta(
        tmp_path / "mixed.fasta",
        [("seq1", "ACGT"), ("seq1", ""), ("seq2", "AC#GT")],
    )

    exit_code, out = run_warnings(capsys, path)

    assert exit_code == 0
    assert "warning: seq1: duplicate ID" in out
    assert "warning: seq1: empty sequence" in out
    assert "warning: seq2: invalid characters ['#']" in out
    assert "3 warning(s) found" in out


@pytest.mark.parametrize("suffix", [".fa", ".fna"])
def test_validate_warnings_fasta_suffixes(capsys, tmp_path, suffix):
    path = write_fasta(tmp_path / f"input{suffix}", [("seq1", "ACGT"), ("seq1", "ACGT")])

    exit_code, out = run_warnings(capsys, path)

    assert exit_code == 0
    assert "warning: seq1: duplicate ID" in out


def test_validate_warnings_empty_file(capsys, caplog, tmp_path):
    path = tmp_path / "nothing.fasta"
    path.write_text("")

    exit_code, out = run_warnings(capsys, path)

    assert exit_code == 0
    assert "0 records" in caplog.text
    assert "warning(s) found" not in out


def test_validate_without_warnings_flag_prints_stats(capsys, tmp_path):
    path = write_fasta(tmp_path / "dup.fasta", [("seq1", "ACGT"), ("seq1", "GGCC")])

    exit_code = main(["validate", str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.startswith("id,length")
    assert "warning:" not in out
