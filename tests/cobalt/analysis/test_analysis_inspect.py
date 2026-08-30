from pathlib import Path

from cobalt.analysis.inspect import read_file, find_warnings, guess_molecule_type, process_records

from Bio.SeqRecord import SeqRecord;
from Bio.Seq import Seq

DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


def test_read_file_counts_orchid_records_fasta():
    result = read_file(DATA_DIR / "ls_orchid.fasta", "fasta")
    assert result["records_num"] > 0
    assert result["min"] <= result["mean"] <= result["max"]

def test_read_file_counts_orchid_records_genbank():
    result = read_file(DATA_DIR / "ls_orchid.gbk", "genbank")
    assert result["records_num"] > 0
    assert result["min"] <= result["mean"] <= result["max"]

def test_find_warnings_empty_records():
    input_data: list[SeqRecord] =  [
            SeqRecord(Seq('ADGCTAGT'), id="seq1"),
            SeqRecord(Seq('TTGCTAGT'), id="seq2"),
            SeqRecord(Seq(''), id="seq3")
        ]
    warnings = find_warnings(input_data)
    assert len(warnings) == 1
    print(warnings[0])
    assert warnings[0] == "seq3: empty sequence"

def test_find_warnings_invalid_character():
    input_data: list[SeqRecord] =  [
            SeqRecord(Seq('ADGCTAGT'), id="seq1"),
            SeqRecord(Seq('TTGCTAGT'), id="seq2"),
            SeqRecord(Seq('ADCCTZGT'), id="seq3")
        ]
    warnings = find_warnings(input_data)
    assert len(warnings) == 1
    assert warnings[0] == "seq3: invalid characters ['Z']"

def test_find_warnings_duplicate_ids():
    input_data: list[SeqRecord] =  [
            SeqRecord(Seq('ADGCTAGT'), id="seq1"),
            SeqRecord(Seq('TTGCTAGT'), id="seq2"),
            SeqRecord(Seq('ADCCTGT'), id="seq2")
        ]
    warnings = find_warnings(input_data)
    assert len(warnings) == 1
    assert warnings[0] == "seq2: duplicate ID"


def test_guess_molecule_type_dna():
    test_result = guess_molecule_type(Seq('AGCTAGT'))
    assert test_result == "DNA"
    test_result = guess_molecule_type(Seq('AGCAU'))
    assert test_result == "RNA"
    test_result = guess_molecule_type(Seq('AGCAUGW'))
    assert test_result == "protein"

def test_type_finding():
    test_data = [SeqRecord(Seq('ADGCUAGU'),
                          id="seq1",
                          annotations={
                              "molecule_type": "DNA"
                          })]
    test_result = process_records(test_data)
    # Dispite Uracil, distinct as DNA from metadata
    assert test_result['records'][0]['type'] == 'DNA'

    
    