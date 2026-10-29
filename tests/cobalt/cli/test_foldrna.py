import sys
from pathlib import Path

import pytest

from cobalt.cli.main import main


def test_foldrna_direct_input(capsys):
    pytest.importorskip("RNA")

    exit_code = main(["foldrna", "--input", "GGGGAAAACCCC"])

    lines = capsys.readouterr().out.splitlines()
    assert exit_code == 0
    assert lines[0] == ">direct_input"
    assert lines[1] == "GGGGAAAACCCC"
    structure, mfe = lines[2].split(" ", 1)
    assert len(structure) == 12
    assert mfe.startswith("(") and mfe.endswith(")")


def test_foldrna_file_to_out(tmp_path):
    pytest.importorskip("RNA")
    path = tmp_path / "in.fasta"
    path.write_text(">a\nGGGAAAUCC\n>b\nACGTACGT\n")
    out = tmp_path / "folds.txt"

    exit_code = main(["foldrna", str(path), "--out", str(out)])

    lines = out.read_text().splitlines()
    assert exit_code == 0
    assert lines[0] == ">a"
    assert lines[3] == ">b"
    assert lines[4] == "ACGUACGU"


def test_foldrna_unknown_adapter(capsys):
    with pytest.raises(SystemExit):
        main(["foldrna", "--input", "ACGU", "--adapter", "bogus"])
    assert "invalid choice" in capsys.readouterr().err


def test_foldrna_file_not_found(capsys, caplog, tmp_path):
    exit_code = main(["foldrna", str(Path(tmp_path) / "missing.fasta")])

    assert exit_code == 1
    assert "file not found" in caplog.text
    assert capsys.readouterr().out == ""


def test_foldrna_missing_dependency(capsys, caplog, monkeypatch):
    monkeypatch.setitem(sys.modules, "RNA", None)

    exit_code = main(["foldrna", "--input", "GGGAAAUCC"])

    assert exit_code == 1
    assert "cobalt-sequence-lab[rna]" in caplog.text
    assert capsys.readouterr().out == ""
