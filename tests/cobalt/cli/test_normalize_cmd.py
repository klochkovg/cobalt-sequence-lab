from pathlib import Path

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
    assert "file not found" in capsys.readouterr().out
