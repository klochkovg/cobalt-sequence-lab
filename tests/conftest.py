import logging

import pytest
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord


@pytest.fixture(autouse=True)
def restore_root_logger():
    """cobalt's main() installs a handler on the root logger; undo it after each test."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.fixture
def length_only_genbank(tmp_path):
    """GenBank file with a normal record (FULL1) and a WGS-style one with no bases (WGS1)."""
    path = tmp_path / "length_only.gb"
    records = [
        SeqRecord(
            Seq("ACGTACGTGG"), id="FULL1", name="FULL1", annotations={"molecule_type": "DNA"}
        ),
        SeqRecord(
            Seq(None, length=50),
            id="WGS1",
            name="WGS1",
            description="WGS master record",
            annotations={"molecule_type": "DNA"},
        ),
    ]
    SeqIO.write(records, path, "genbank")
    return path
