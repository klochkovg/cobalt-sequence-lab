import bz2
import gzip
from pathlib import Path

import pytest
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.inspect import (
    canonical_molecule_type,
    find_warnings,
    guess_molecule_type,
)
from cobalt.analysis.processor import InputFileError, load_file, process_records, read_file
from cobalt.model.qc import WarningKind

DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


def test_read_file_counts_orchid_records_fasta():
    result = read_file(DATA_DIR / "ls_orchid.fasta", "fasta")
    assert result.records_num > 0
    assert result.min <= result.mean <= result.max


def test_read_file_counts_orchid_records_genbank():
    result = read_file(DATA_DIR / "ls_orchid.gbk", "genbank")
    assert result.records_num > 0
    assert result.min <= result.mean <= result.max


def test_find_warnings_empty_records():
    input_data: list[SeqRecord] = [
        SeqRecord(Seq("ADGCTAGT"), id="seq1"),
        SeqRecord(Seq("TTGCTAGT"), id="seq2"),
        SeqRecord(Seq(""), id="seq3"),
    ]
    warnings = find_warnings(input_data, ["DNA", "DNA", "unknown"])
    assert len(warnings) == 1
    assert warnings[0].kind == WarningKind.EMPTY_SEQUENCE
    assert str(warnings[0]) == "seq3: empty sequence"


def test_find_warnings_invalid_character():
    input_data: list[SeqRecord] = [
        SeqRecord(Seq("ADGCTAGT"), id="seq1"),
        SeqRecord(Seq("TTGCTAGT"), id="seq2"),
        SeqRecord(Seq("ADCCTZGT"), id="seq3"),
    ]
    warnings = find_warnings(input_data, ["DNA", "DNA", "DNA"])
    assert len(warnings) == 1
    assert str(warnings[0]) == "seq3: invalid characters ['Z']"


def test_find_warnings_duplicate_ids():
    input_data: list[SeqRecord] = [
        SeqRecord(Seq("ADGCTAGT"), id="seq1"),
        SeqRecord(Seq("TTGCTAGT"), id="seq2"),
        SeqRecord(Seq("ADCCTGT"), id="seq2"),
    ]
    warnings = find_warnings(input_data, ["DNA", "DNA", "DNA"])
    assert len(warnings) == 1
    assert str(warnings[0]) == "seq2: duplicate ID"


@pytest.mark.parametrize(
    ("sequence", "molecule_type", "expected"),
    [
        ("ACGUACGU", "RNA", []),
        ("MKVXBZ", "protein", []),
        ("MKV*", "protein", ["seq: invalid characters ['*']"]),
        ("ACGT-ACGT", "DNA", ["seq: invalid characters ['-']"]),
        ("ACGUACGU", "DNA", ["seq: invalid characters ['U']"]),
    ],
)
def test_find_warnings_uses_molecule_type(sequence, molecule_type, expected):
    warnings = find_warnings([SeqRecord(Seq(sequence), id="seq")], [molecule_type])
    assert [str(warning) for warning in warnings] == expected


def test_process_records_warnings_follow_annotation():
    records = [
        SeqRecord(Seq("ACGUACGU"), id="annotated", annotations={"molecule_type": "DNA"}),
        SeqRecord(Seq("ACGUACGU"), id="guessed"),
    ]
    result = process_records(records, "genbank")
    assert [str(warning) for warning in result.warnings] == ["annotated: invalid characters ['U']"]


def test_guess_molecule_type_dna():
    test_result = guess_molecule_type(Seq("AGCTAGT"))
    assert test_result == "DNA"
    test_result = guess_molecule_type(Seq("AGCAU"))
    assert test_result == "RNA"
    # W is an IUPAC ambiguity code, so this is still a valid RNA
    test_result = guess_molecule_type(Seq("AGCAUGW"))
    assert test_result == "RNA"


def test_type_finding():
    test_data = [SeqRecord(Seq("ADGCUAGU"), id="seq1", annotations={"molecule_type": "DNA"})]
    test_result = process_records(test_data, "raw")
    # Dispite Uracil, distinct as DNA from metadata
    assert test_result.records[0].type == "DNA"


def test_annotations():
    test_data = [
        SeqRecord(
            Seq("ADGCUAGU"),
            id="seq1",
            annotations={
                "molecule_type": "DNA",
                "organism": "test_subject_1",
                "topology": "test_topology_1",
            },
        )
    ]
    test_result = process_records(test_data, "raw")
    assert test_result.records[0].type == "DNA"
    assert test_result.records[0].organism == "test_subject_1"
    assert test_result.records[0].topology == "test_topology_1"


@pytest.mark.parametrize(
    ("sequence", "expected"),
    [
        ("ACGTRYACGT", "DNA"),  # ambiguity codes R, Y
        ("acgtnnnnacgt", "DNA"),
        ("ACGURYACGU", "RNA"),
        ("MKVLAAGIC", "protein"),
        ("MKVAG", "protein"),  # only nucleotide-code letters, but too few A/C/G/T
        ("", "unknown"),
        ("ACGT123", "unknown"),
    ],
)
def test_guess_molecule_type_cases(sequence, expected):
    assert guess_molecule_type(Seq(sequence)) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("DNA", "DNA"),
        ("genomic DNA", "DNA"),
        ("ss-DNA", "DNA"),
        ("mRNA", "RNA"),
        ("ss-RNA", "RNA"),
        ("protein", "protein"),
        (None, None),
        ("", None),
        ("other", None),
    ],
)
def test_canonical_molecule_type(value, expected):
    assert canonical_molecule_type(value) == expected


def test_process_records_alphabet_class():
    records = [
        SeqRecord(Seq("ACGTACGT"), id="clean"),
        SeqRecord(Seq("ACGTRYACGT"), id="ambiguous"),
        SeqRecord(Seq("ACGUACGU"), id="bad", annotations={"molecule_type": "DNA"}),
    ]
    result = process_records(records, "raw")
    classes = {record.id: record.alphabetic_class for record in result.records}
    assert classes == {"clean": "unambiguous", "ambiguous": "ambiguous", "bad": "invalid"}


def test_process_records_gc_only_for_nucleotides():
    records = [
        SeqRecord(Seq("GGCC"), id="dna"),
        SeqRecord(Seq("GGCCAU"), id="rna"),
        SeqRecord(Seq("MKVLAAGIC"), id="protein"),
    ]
    result = process_records(records, "raw")
    gc = {record.id: record.gc_fraction for record in result.records}
    assert gc["dna"] == pytest.approx(1.0)
    assert gc["rna"] == pytest.approx(4 / 6)
    assert gc["protein"] is None


def test_process_records_genbank_molecule_type_variants():
    record = SeqRecord(Seq("ACGUACGU"), id="m1", annotations={"molecule_type": "mRNA"})
    result = process_records([record], "genbank")
    processed = result.records[0]
    assert processed.type == "RNA"
    assert processed.molecule_type == "mRNA"
    assert processed.invalid_char_count == 0
    assert processed.alphabetic_class == "unambiguous"


def test_type_and_warning_counts():
    records = [
        SeqRecord(Seq("ACGT"), id="dna1"),
        SeqRecord(Seq("ACGT"), id="dna1"),
        SeqRecord(Seq("MKVLAAGIC"), id="prot"),
        SeqRecord(Seq(""), id="empty"),
    ]
    result = process_records(records, "raw")
    assert result.type_counts() == {"DNA": 2, "protein": 1, "unknown": 1}
    assert result.warning_counts() == {
        WarningKind.DUPLICATE_ID: 1,
        WarningKind.EMPTY_SEQUENCE: 1,
        WarningKind.INVALID_CHARACTERS: 0,
    }


@pytest.mark.parametrize("compress", [gzip.compress, bz2.compress])
@pytest.mark.parametrize(
    ("source", "fmt"), [("ls_orchid.fasta", "fasta"), ("ls_orchid.gbk", "genbank")]
)
def test_load_file_compressed(tmp_path, compress, source, fmt):
    path = tmp_path / "input"
    path.write_bytes(compress((DATA_DIR / source).read_bytes()))
    result = load_file(path)
    assert result is not None
    assert result.records_num == 94
    assert result.type == fmt


def test_load_file_ignores_extension(tmp_path):
    path = tmp_path / "mislabelled.fasta"
    path.write_bytes((DATA_DIR / "ls_orchid.gbk").read_bytes())
    result = load_file(path)
    assert result is not None
    assert result.type == "genbank"


@pytest.mark.parametrize("content", [b"", b"\n  \n", gzip.compress(b"\n")])
def test_load_file_blank_returns_none(tmp_path, content):
    path = tmp_path / "blank"
    path.write_bytes(content)
    assert load_file(path) is None


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"hello\n", "unrecognized format"),
        (b"\x1f\x8bnot really gzip", "cannot read"),
        (
            gzip.compress((DATA_DIR / "ls_orchid.fasta").read_bytes())[:3000],
            "cannot parse as fasta",
        ),
    ],
)
def test_load_file_errors(tmp_path, content, message):
    path = tmp_path / "input"
    path.write_bytes(content)
    with pytest.raises(InputFileError, match=message):
        load_file(path)


def test_load_file_missing(tmp_path):
    with pytest.raises(InputFileError, match="file not found"):
        load_file(tmp_path / "missing.fasta")


def test_load_file_parser_value_error(monkeypatch):
    def broken_parse(handle, fmt):
        raise ValueError("bad record\nwith a long explanation")

    monkeypatch.setattr("cobalt.analysis.processor.SeqIO.parse", broken_parse)
    with pytest.raises(InputFileError) as excinfo:
        load_file(DATA_DIR / "ls_orchid.fasta")
    assert str(excinfo.value).endswith("cannot parse as fasta: bad record")


def annotated(seq: str, molecule_type: str) -> SeqRecord:
    return SeqRecord(Seq(seq), id="r1", annotations={"molecule_type": molecule_type})


def test_genbank_mrna_with_t_is_valid():
    # GenBank stores mRNA with T, as its cDNA
    result = process_records([annotated("ATGGCTTGTACGTAA", "mRNA")], "genbank")
    record = result.records[0]
    assert record.type == "RNA"
    assert record.invalid_char_count == 0
    assert record.alphabetic_class == "unambiguous"
    assert result.warnings == []


def test_rna_with_u_still_valid_and_other_letters_still_invalid():
    record = process_records([annotated("AUGGCUUGA", "mRNA")], "genbank").records[0]
    assert record.alphabetic_class == "unambiguous"

    result = process_records([annotated("AUGXXUGA", "mRNA")], "genbank")
    assert result.records[0].invalid_char_count == 2
    assert result.records[0].alphabetic_class == "invalid"
    assert [w.kind for w in result.warnings] == [WarningKind.INVALID_CHARACTERS]


def test_dna_with_u_still_invalid():
    record = process_records([annotated("ACGU", "DNA")], "genbank").records[0]
    assert record.invalid_char_count == 1
    assert record.alphabetic_class == "invalid"
