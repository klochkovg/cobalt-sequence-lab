from pathlib import Path

import pytest

from cobalt.analysis.processor import (
    InputFileError,
    calculate_alphabet_class,
    calculate_ambiguity_fraction,
    calculate_gc_fraction,
    decode_quality,
    encode_quality,
    load_file,
    quality_stats,
)

DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


@pytest.mark.parametrize(
    ("seq", "molecule_type", "expected"),
    [
        ("GGCC", "DNA", 1.0),
        ("ATAT", "DNA", 0.0),
        ("ACGT", "DNA", 0.5),
        ("acgt", "DNA", 0.5),
        ("ACGU", "RNA", 0.5),
        # Ambiguity codes other than S are left out of the count
        ("GCNN", "DNA", 1.0),
        ("GCAS", "DNA", 0.75),
    ],
)
def test_gc_fraction_nucleotide(seq, molecule_type, expected):
    assert calculate_gc_fraction(seq, molecule_type) == pytest.approx(expected)


@pytest.mark.parametrize("molecule_type", ["protein", "unknown"])
def test_gc_fraction_none_for_non_nucleotide(molecule_type):
    assert calculate_gc_fraction("GGCC", molecule_type) is None


@pytest.mark.xfail(strict=True, reason="all-ambiguous sequence reports 0 GC instead of None")
def test_gc_fraction_all_ambiguous_is_none():
    assert calculate_gc_fraction("NNNN", "DNA") is None


@pytest.mark.parametrize(
    ("seq", "molecule_type", "expected"),
    [
        ("ACGT", "DNA", "unambiguous"),
        ("acgt", "DNA", "unambiguous"),
        ("ACGU", "RNA", "unambiguous"),
        ("MKVLAAGIC", "protein", "unambiguous"),
        ("ACGTN", "DNA", "ambiguous"),
        ("ACGURY", "RNA", "ambiguous"),
        ("MKVX", "protein", "ambiguous"),
        ("ACGT1", "DNA", "invalid"),
        ("ACGU", "DNA", "invalid"),
        ("MKV1", "protein", "invalid"),
        ("", "DNA", "unknown"),
        ("ACGT", "unknown", "unknown"),
    ],
)
def test_alphabet_class(seq, molecule_type, expected):
    assert calculate_alphabet_class(seq, molecule_type) == expected


@pytest.mark.parametrize(
    ("seq", "molecule_type", "expected"),
    [
        ("ACGT", "DNA", 0.0),
        ("ACGTRYACGT", "DNA", 0.2),
        ("acgtn", "DNA", 0.2),
        ("NNNN", "DNA", 1.0),
        ("ACGN", "RNA", 0.25),
        ("MKVX", "protein", 0.25),
        ("", "DNA", 0.0),
    ],
)
def test_ambiguity_fraction(seq, molecule_type, expected):
    assert calculate_ambiguity_fraction(seq, molecule_type) == pytest.approx(expected)


@pytest.mark.xfail(strict=True, reason="unknown molecule type gives 0.0 instead of None")
def test_ambiguity_fraction_unknown_type_is_none():
    assert calculate_ambiguity_fraction("ACGTN", "unknown") is None


@pytest.mark.parametrize(
    ("phred", "expected"),
    [
        ([40, 40], (40.0, 40, 1.0)),
        ([30, 29, 0, 41], (25.0, 0, 0.5)),
        ([], None),
    ],
)
def test_quality_stats(phred, expected):
    assert quality_stats(phred) == expected


def test_quality_encoding_round_trip():
    assert encode_quality([0, 10, 40]) == "!+I"
    assert decode_quality("!+I") == [0, 10, 40]


def test_load_file_fastq():
    result = load_file(DATA_DIR / "sample.fastq")

    assert result is not None
    assert result.type == "fastq"
    assert [record.id for record in result.records] == ["read1", "read2", "read3", "read4"]
    read1, read2, read3, read4 = result.records
    assert read1.type == "DNA"
    assert read1.quality == "IIIIIIIIII"
    assert (read1.mean_quality, read1.min_quality, read1.q30_fraction) == (40.0, 40, 1.0)
    assert (read2.mean_quality, read2.min_quality, read2.q30_fraction) == (5.0, 0, 0.0)
    assert (read3.mean_quality, read3.min_quality, read3.q30_fraction) == (21.0, 2, 0.5)
    assert read4.mean_quality == pytest.approx(26.25)
    assert read4.q30_fraction == pytest.approx(0.625)


def test_load_file_fasta_has_no_quality():
    result = load_file(DATA_DIR / "ls_orchid.fasta")

    assert result is not None
    record = result.records[0]
    assert record.quality is None
    assert record.mean_quality is None
    assert record.min_quality is None
    assert record.q30_fraction is None


def test_load_file_fastq_quality_shorter_than_sequence(tmp_path):
    path = tmp_path / "bad.fastq"
    path.write_text("@r1\nACGT\n+\nII\n")

    with pytest.raises(InputFileError, match="cannot parse as fastq"):
        load_file(path)


@pytest.mark.parametrize(("name", "fmt"), [("1A8O.pdb", "pdb-atom"), ("1A8O.cif", "cif-atom")])
def test_load_file_structure(name, fmt):
    result = load_file(DATA_DIR / name)

    assert result is not None
    assert result.type == fmt
    assert result.records_num == 1
    record = result.records[0]
    assert record.id == "1A8O:A"
    assert record.description == ""
    assert record.type == "protein"
    assert record.source_format == fmt
    assert record.length == 70
    assert record.sequence is not None
    assert record.sequence.startswith("MDIRQGPKEPFRDYVDRFYK")
    assert record.gc_fraction is None


def test_load_file_pdb_and_mmcif_agree():
    pdb = load_file(DATA_DIR / "1A8O.pdb")
    mmcif = load_file(DATA_DIR / "1A8O.cif")

    assert pdb is not None and mmcif is not None
    assert [r.sequence for r in pdb.records] == [r.sequence for r in mmcif.records]
