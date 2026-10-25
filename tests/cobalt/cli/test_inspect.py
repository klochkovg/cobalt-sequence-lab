import gzip
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
    assert (
        "warnings: 2 (duplicate_id=1, empty_sequence=0, invalid_characters=1, undefined_sequence=0)"
    ) in out
    assert "s1: duplicate ID" in out


def test_inspect_summary_genbank(capsys):
    exit_code = main(["inspect", "--overview-only", str(DATA_DIR / "ls_orchid.gbk")])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "molecule types: DNA=94" in out
    assert (
        "warnings: 0 (duplicate_id=0, empty_sequence=0, invalid_characters=0, undefined_sequence=0)"
    ) in out


def test_inspect_prints_format(capsys):
    exit_code = main(["inspect", "--overview-only", str(DATA_DIR / "ls_orchid.fasta")])

    assert exit_code == 0
    assert " format: fasta\n" in capsys.readouterr().out


def test_inspect_gzip_genbank(capsys, tmp_path):
    path = tmp_path / "ls_orchid.gbk.gz"
    path.write_bytes(gzip.compress((DATA_DIR / "ls_orchid.gbk").read_bytes()))

    exit_code = main(["inspect", "--overview-only", str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "94 record(s)" in out
    assert " format: genbank (gzip)" in out


def test_inspect_genbank_content_with_fasta_extension(capsys, tmp_path):
    path = tmp_path / "mislabelled.fasta"
    path.write_bytes((DATA_DIR / "ls_orchid.gbk").read_bytes())

    exit_code = main(["inspect", "--overview-only", str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "94 record(s)" in out
    assert " format: genbank" in out


def test_inspect_unrecognized_content(capsys, caplog, tmp_path):
    path = tmp_path / "junk.gb"
    path.write_text("hello\n")

    exit_code = main(["inspect", str(path)])

    assert exit_code == 1
    assert "unrecognized format" in caplog.text
    assert capsys.readouterr().out == ""


def test_inspect_empty_file(capsys, tmp_path):
    path = tmp_path / "empty.fasta"
    path.write_text("\n\n")

    exit_code = main(["inspect", str(path)])

    assert exit_code == 0
    assert "0 records" in capsys.readouterr().out


def test_inspect_no_false_invalid_character_warnings(capsys, tmp_path):
    path = tmp_path / "rna_protein.fasta"
    path.write_text(">r1\nACGUACGU\n>p1\nMKVXB\n")

    exit_code = main(["inspect", "--overview-only", str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert (
        "warnings: 0 (duplicate_id=0, empty_sequence=0, invalid_characters=0, undefined_sequence=0)"
    ) in out


def test_inspect_fasta_listing_has_no_type_line(capsys, tmp_path):
    path = tmp_path / "dna.fasta"
    path.write_text(">s1\nACGT\n")

    exit_code = main(["inspect", str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Type guess      : DNA" in out
    assert "Type            :" not in out


def test_inspect_genbank_listing_shows_annotated_type(capsys):
    exit_code = main(["inspect", "--output-seq-number", "1", str(DATA_DIR / "ls_orchid.gbk")])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Type            : DNA" in out


@pytest.mark.parametrize(("args", "expected"), [([], 3), (["--output-seq-number", "2"], 2)])
def test_inspect_output_seq_number(capsys, tmp_path, args, expected):
    path = tmp_path / "three.fasta"
    path.write_text(">s1\nACGT\n>s2\nACGT\n>s3\nACGT\n")

    exit_code = main(["inspect", *args, str(path)])

    assert exit_code == 0
    assert capsys.readouterr().out.count("Sequence name   :") == expected


def test_inspect_output_seq_number_zero_lists_nothing(capsys):
    exit_code = main(["inspect", "--output-seq-number", "0", str(DATA_DIR / "ls_orchid.fasta")])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "94 record(s)" in out
    assert "Sequence name   :" not in out


@pytest.mark.parametrize("value", ["-1", "abc"])
def test_inspect_output_seq_number_rejects_invalid(capsys, value):
    with pytest.raises(SystemExit) as excinfo:
        main(["inspect", "--output-seq-number", value, str(DATA_DIR / "ls_orchid.fasta")])

    assert excinfo.value.code == 2
    assert "--output-seq-number" in capsys.readouterr().err


def test_inspect_overview_only_skips_listing(capsys):
    exit_code = main(["inspect", "--overview-only", str(DATA_DIR / "ls_orchid.fasta")])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert " length: min=" in out
    assert "Sequence name   :" not in out


def test_inspect_length_only_record(capsys, length_only_genbank):
    exit_code = main(["inspect", str(length_only_genbank)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "undefined_sequence=1" in out
    assert "Sequence        : (undefined, length only)" in out


def test_inspect_fastq(capsys):
    exit_code = main(["inspect", str(DATA_DIR / "sample.fastq")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "4 record(s)" in captured.out
    assert "format: fastq" in captured.out
    assert "Quality         : mean=40.0  min=40  Q30=100.0%" in captured.out
    assert "Quality         : mean=26.2  min=20  Q30=62.5%" in captured.out


def test_inspect_fasta_has_no_quality_line(capsys):
    exit_code = main(["inspect", "--output-seq-number", "2", str(DATA_DIR / "ls_orchid.fasta")])

    assert exit_code == 0
    assert "Quality" not in capsys.readouterr().out
