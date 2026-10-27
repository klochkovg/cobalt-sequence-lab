import bz2
import gzip
import logging
from pathlib import Path

import pytest

from cobalt.io.sniff import is_blank, is_supported, open_text, sniff_compression, sniff_format

DATA_DIR = Path(__file__).parent.parent.parent / "test_data"
FASTA = DATA_DIR / "ls_orchid.fasta"
GENBANK = DATA_DIR / "ls_orchid.gbk"
FASTQ = DATA_DIR / "sample.fastq"
PDB = DATA_DIR / "1A8O.pdb"
MMCIF = DATA_DIR / "1A8O.cif"

COMPRESSORS = {"gzip": gzip.compress, "bzip2": bz2.compress}


def write(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (FASTA, "fasta"),
        (GENBANK, "genbank"),
        (FASTQ, "fastq"),
        (PDB, "pdb-atom"),
        (MMCIF, "cif-atom"),
        (DATA_DIR / "text_input.txt", None),
    ],
)
def test_sniff_format_test_data(path, expected):
    assert sniff_format(path) == expected


@pytest.mark.parametrize("compression", ["gzip", "bzip2"])
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (FASTA, "fasta"),
        (GENBANK, "genbank"),
        (FASTQ, "fastq"),
        (PDB, "pdb-atom"),
        (MMCIF, "cif-atom"),
    ],
)
@pytest.mark.parametrize("name", ["input.compressed", "misleading.txt"])
def test_sniff_format_compressed(tmp_path, compression, source, expected, name):
    path = write(tmp_path, name, COMPRESSORS[compression](source.read_bytes()))
    assert sniff_compression(path) == compression
    assert sniff_format(path) == expected


@pytest.mark.parametrize(
    ("source", "name", "expected"),
    [(GENBANK, "x.fasta", "genbank"), (FASTA, "x.gb", "fasta")],
)
def test_sniff_format_ignores_extension(tmp_path, source, name, expected):
    path = write(tmp_path, name, source.read_bytes())
    assert sniff_format(path) == expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"\n  \n\t\n>s1\nACGT\n", "fasta"),
        (b"\xef\xbb\xbf>s1\nACGT\n", "fasta"),
        (b"\xef\xbb\xbfLOCUS       X 4 bp    DNA\n", "genbank"),
        (b"", None),
        (b"\n\n   \n", None),
        (b"; comment\n>s1\nACGT\n", None),
        (b"\x00\xff\xfe\x80binary", None),
        (b"\n" * 200 + b">s1\nACGT\n", None),
        (b"@r1\nACGT\n+\nIIII\n", "fastq"),
        (b"\n\n@r1 desc\nACGT\n+r1 desc\nIIII\n", "fastq"),
        (b"\xef\xbb\xbf@r1\nACGT\n+\nIIII\n", "fastq"),
        # SAM header lines start with @ too, but have no + separator
        (b"@HD\tVN:1.6\n@SQ\tSN:chr1\tLN:100\n@PG\tID:bwa\n", None),
        (b"@r1\n", None),
        (b"@r1\nACGT\n", None),
        # Tool output often has no HEADER and starts with REMARK, MODEL or ATOM
        (b"REMARK   1 PREDICTED STRUCTURE\n", "pdb-atom"),
        (b"MODEL        1\n", "pdb-atom"),
        (
            b"ATOM      1  N   MET A   1      27.340  24.430   2.614  1.00 90.12           N\n",
            "pdb-atom",
        ),
        (b"ATOM\n", "pdb-atom"),
        (b"ATOMIC notes\n", None),
        (b"data_1ABC\n#\n_entry.id 1ABC\n", "cif-atom"),
        (b"DATA_1ABC\n", None),
    ],
)
def test_sniff_format_content(tmp_path, content, expected):
    assert sniff_format(write(tmp_path, "input", content)) == expected


def test_sniff_format_corrupt_gzip(tmp_path, caplog):
    path = write(tmp_path, "broken.gz", b"\x1f\x8bnot really gzip")
    with caplog.at_level(logging.DEBUG):
        assert sniff_format(path) is None
    assert "cannot read" in caplog.text


def test_sniff_format_truncated_bzip2(tmp_path, caplog):
    path = write(tmp_path, "broken.bz2", bz2.compress(FASTA.read_bytes())[:20])
    with caplog.at_level(logging.DEBUG):
        assert sniff_format(path) is None
    assert "cannot read" in caplog.text


def test_sniff_format_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        sniff_format(tmp_path / "missing.fasta")


def test_sniff_compression_plain():
    assert sniff_compression(FASTA) is None


@pytest.mark.parametrize("compression", ["gzip", "bzip2"])
def test_open_text_decompresses(tmp_path, compression):
    path = write(tmp_path, "input", COMPRESSORS[compression](b">s1\nACGT\n"))
    with open_text(path) as handle:
        assert handle.read() == ">s1\nACGT\n"


def test_is_supported(tmp_path):
    assert is_supported(FASTA)
    assert is_supported(GENBANK)
    assert is_supported(PDB)
    assert is_supported(MMCIF)
    assert not is_supported(write(tmp_path, "notes.txt", b"hello\n"))


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"", True),
        (b"\n \t\n", True),
        (gzip.compress(b"\n\n"), True),
        (b">s1\n", False),
        (bz2.compress(b"\n\nLOCUS"), False),
    ],
)
def test_is_blank(tmp_path, content, expected):
    assert is_blank(write(tmp_path, "input", content)) is expected
