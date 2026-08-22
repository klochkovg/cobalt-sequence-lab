from pathlib import Path

from cobalt.analysis.inspect import read_file

DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


def test_read_file_counts_orchid_records():
    result = read_file(DATA_DIR / "ls_orchid.fasta", "fasta")
    assert result["records_num"] > 0
    assert result["min"] <= result["mean"] <= result["max"]