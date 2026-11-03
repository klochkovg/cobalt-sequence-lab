import bz2
import json
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


def test_validate_warnings_any_extension(capsys, tmp_path):
    path = tmp_path / "input.txt"
    path.write_text(">seq1\nACGT\n")

    exit_code, out = run_warnings(capsys, path)

    assert exit_code == 0
    assert "0 warning(s) found" in out


def test_validate_warnings_unrecognized_content(capsys, caplog, tmp_path):
    path = tmp_path / "input.fasta"
    path.write_text("just some notes\n")

    exit_code, out = run_warnings(capsys, path)

    assert exit_code == 1
    assert "unrecognized format" in caplog.text
    assert out == ""


def test_validate_bzip2_genbank(capsys, tmp_path):
    path = tmp_path / "ls_orchid.gbk.bz2"
    path.write_bytes(bz2.compress((DATA_DIR / "ls_orchid.gbk").read_bytes()))

    exit_code = main(["validate", str(path)])

    assert exit_code == 0
    assert len(capsys.readouterr().out.splitlines()) == 95  # header + 94 records


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


def run_json(capsys, *args) -> tuple[int, dict]:
    """Run `cobalt validate --json` and return the exit code and the parsed report."""
    exit_code = main(["validate", "--json", *args])
    return exit_code, json.loads(capsys.readouterr().out)


def test_validate_json_clean_file(capsys):
    path = DATA_DIR / "ls_orchid.fasta"
    exit_code, report = run_json(capsys, str(path))

    assert exit_code == 0
    assert report["file"] == str(path)
    assert report["records_num"] == 94
    assert report["format"] == "fasta"
    assert report["compression"] is None
    assert report["passed"] is True
    assert report["warnings"] == []


def test_validate_json_warnings(capsys, tmp_path):
    path = write_fasta(tmp_path / "bad.fasta", [("seq1", "ACGT"), ("seq1", "AC!T"), ("seq2", "")])
    exit_code, report = run_json(capsys, str(path))

    assert exit_code == 0
    assert report["passed"] is False
    assert report["warning_counts"] == {
        "duplicate_id": 1,
        "empty_sequence": 1,
        "invalid_characters": 1,
        "undefined_sequence": 0,
    }
    assert [w["record_id"] for w in report["warnings"]] == ["seq1", "seq1", "seq2"]


def test_validate_json_bzip2(capsys, tmp_path):
    path = tmp_path / "ls_orchid.gbk.bz2"
    path.write_bytes(bz2.compress((DATA_DIR / "ls_orchid.gbk").read_bytes()))
    _, report = run_json(capsys, str(path))

    assert (report["format"], report["compression"]) == ("genbank", "bzip2")


def test_validate_json_empty_file(capsys, tmp_path):
    path = tmp_path / "empty.fasta"
    path.write_text("")
    exit_code, report = run_json(capsys, str(path))

    assert exit_code == 0
    assert report["records_num"] == 0
    assert report["format"] is None
    assert report["passed"] is True


def test_validate_report_file_matches_json(capsys, tmp_path):
    path = write_fasta(tmp_path / "dup.fasta", [("seq1", "ACGT"), ("seq1", "GGCC")])
    report_path = tmp_path / "qc.json"

    exit_code = main(["validate", str(path), "--report", str(report_path)])
    assert exit_code == 0
    assert capsys.readouterr().out == ""
    _, printed = run_json(capsys, str(path))
    assert json.loads(report_path.read_text()) == printed


def test_validate_report_with_warnings_flag(capsys, tmp_path):
    path = write_fasta(tmp_path / "dup.fasta", [("seq1", "ACGT"), ("seq1", "GGCC")])
    report_path = tmp_path / "qc.json"

    exit_code = main(["validate", "--warnings", "--report", str(report_path), str(path)])

    assert exit_code == 0
    assert "1 warning(s) found" in capsys.readouterr().out
    assert json.loads(report_path.read_text())["passed"] is False


def test_validate_report_to_directory(caplog, tmp_path):
    path = write_fasta(tmp_path / "ok.fasta", [("seq1", "ACGT")])

    assert main(["validate", str(path), "--report", str(tmp_path)]) == 1
    assert "--report is a directory" in caplog.text


def test_validate_report_missing_directory(caplog, tmp_path):
    path = write_fasta(tmp_path / "ok.fasta", [("seq1", "ACGT")])

    assert main(["validate", str(path), "--report", str(tmp_path / "no" / "qc.json")]) == 1
    assert "no such directory for --report" in caplog.text
