from pathlib import Path

import pytest
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.inspect import (
    canonical_molecule_type,
    find_warnings,
    guess_molecule_type,
)
from cobalt.analysis.processor import process_records, read_file
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
    warnings = find_warnings(input_data)
    assert len(warnings) == 1
    assert warnings[0].kind == WarningKind.EMPTY_SEQUENCE
    assert str(warnings[0]) == "seq3: empty sequence"


def test_find_warnings_invalid_character():
    input_data: list[SeqRecord] = [
        SeqRecord(Seq("ADGCTAGT"), id="seq1"),
        SeqRecord(Seq("TTGCTAGT"), id="seq2"),
        SeqRecord(Seq("ADCCTZGT"), id="seq3"),
    ]
    warnings = find_warnings(input_data)
    assert len(warnings) == 1
    assert str(warnings[0]) == "seq3: invalid characters ['Z']"


def test_find_warnings_duplicate_ids():
    input_data: list[SeqRecord] = [
        SeqRecord(Seq("ADGCTAGT"), id="seq1"),
        SeqRecord(Seq("TTGCTAGT"), id="seq2"),
        SeqRecord(Seq("ADCCTGT"), id="seq2"),
    ]
    warnings = find_warnings(input_data)
    assert len(warnings) == 1
    assert str(warnings[0]) == "seq2: duplicate ID"


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
        SeqRecord(Seq("ACGTACGT"), id="bad", annotations={"molecule_type": "RNA"}),
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
