from pathlib import Path

import pytest
from Bio import SeqIO

from cobalt.cli.main import main

TEST_DATA = Path(__file__).parents[2] / "test_data"


def test_normalize_uppercases_sequences(tmp_path):
    input_path = tmp_path / "input.fasta"
    input_path.write_text(">seq1 first\nacgTNa\n>seq2 second\nGgCc\n")
    output_path = tmp_path / "out.fasta"

    exit_code = main(["normalize", str(input_path), "--fasta", str(output_path)])

    assert exit_code == 0
    records = list(SeqIO.parse(output_path, "fasta"))
    assert [record.id for record in records] == ["seq1", "seq2"]
    assert [str(record.seq) for record in records] == ["ACGTNA", "GGCC"]


def test_normalize_genbank_to_fasta(tmp_path):
    output_path = tmp_path / "out.fasta"

    exit_code = main(["normalize", str(TEST_DATA / "ls_orchid.gbk"), "--fasta", str(output_path)])

    assert exit_code == 0
    records = list(SeqIO.parse(output_path, "fasta"))
    assert len(records) == len(list(SeqIO.parse(TEST_DATA / "ls_orchid.gbk", "genbank")))
    assert all(str(record.seq) == str(record.seq).upper() for record in records)


def test_normalize_missing_file(tmp_path, capsys):
    exit_code = main(
        ["normalize", str(tmp_path / "missing.fasta"), "--fasta", str(tmp_path / "out.fasta")]
    )

    assert exit_code == 1
    assert "file not found" in capsys.readouterr().err


def test_normalize_genbank_output(tmp_path):
    output_path = tmp_path / "out.gbk"

    exit_code = main(["normalize", str(TEST_DATA / "ls_orchid.gbk"), "--genbank", str(output_path)])

    assert exit_code == 0
    source = list(SeqIO.parse(TEST_DATA / "ls_orchid.gbk", "genbank"))
    records = list(SeqIO.parse(output_path, "genbank"))
    assert [record.id for record in records] == [record.id for record in source]
    assert [str(record.seq) for record in records] == [str(r.seq).upper() for r in source]
    assert all(record.annotations["molecule_type"] == "DNA" for record in records)


def test_normalize_fasta_to_genbank_uses_guessed_type(tmp_path):
    input_path = tmp_path / "input.fasta"
    input_path.write_text(">seq1 first\nacgTNa\n>seq2 second\nacgu\n")
    output_path = tmp_path / "out.gbk"

    exit_code = main(["normalize", str(input_path), "--genbank", str(output_path)])

    assert exit_code == 0
    records = list(SeqIO.parse(output_path, "genbank"))
    assert [str(record.seq) for record in records] == ["ACGTNA", "ACGU"]
    assert [record.annotations["molecule_type"] for record in records] == ["DNA", "RNA"]


# Long NCBI-style IDs must not produce a non-standard LOCUS line
@pytest.mark.filterwarnings("error::Bio.BiopythonWarning")
def test_normalize_fasta_and_genbank_together(tmp_path):
    fasta_path = tmp_path / "out.fasta"
    genbank_path = tmp_path / "out.gbk"

    exit_code = main(
        [
            "normalize",
            str(TEST_DATA / "ls_orchid.fasta"),
            "--fasta",
            str(fasta_path),
            "--genbank",
            str(genbank_path),
        ]
    )

    assert exit_code == 0
    fasta_ids = [record.id for record in SeqIO.parse(fasta_path, "fasta")]
    genbank_records = list(SeqIO.parse(genbank_path, "genbank"))
    assert len(fasta_ids) == len(genbank_records) > 0
    assert genbank_records[0].name == "Z78533"
    assert all(len(record.name) <= 16 for record in genbank_records)


def test_normalize_genbank_unknown_molecule_type(tmp_path, capsys):
    input_path = tmp_path / "input.fasta"
    input_path.write_text(">seq1\nACGT123\n")

    exit_code = main(["normalize", str(input_path), "--genbank", str(tmp_path / "out.gbk")])

    assert exit_code == 1
    assert "could not write genbank" in capsys.readouterr().err


def test_normalize_requires_output(capsys):
    with pytest.raises(SystemExit):
        main(["normalize", str(TEST_DATA / "ls_orchid.fasta")])
    assert "at least one of --fasta or --genbank" in capsys.readouterr().err
