import bz2
import gzip
import logging
from pathlib import Path

import pytest

from cobalt.io.sniff import is_supported, open_text, sniff_compression, sniff_format

DATA_DIR = Path(__file__).parent.parent.parent / "test_data"
FASTA = DATA_DIR / "ls_orchid.fasta"
GENBANK = DATA_DIR / "ls_orchid.gbk"

COMPRESSORS = {"gzip": gzip.compress, "bzip2": bz2.compress}


def write(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


@pytest.mark.parametrize(
    ("path", "expected"),
    [(FASTA, "fasta"), (GENBANK, "genbank"), (DATA_DIR / "text_input.txt", None)],
)
def test_sniff_format_test_data(path, expected):
    assert sniff_format(path) == expected


@pytest.mark.parametrize("compression", ["gzip", "bzip2"])
@pytest.mark.parametrize(("source", "expected"), [(FASTA, "fasta"), (GENBANK, "genbank")])
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
    ],
)
def test_sniff_format_content(tmp_path, content, expected):
    assert sniff_format(write(tmp_path, "input", content)) == expected


def test_sniff_format_corrupt_gzip(tmp_path, caplog):
    path = write(tmp_path, "broken.gz", b"\x1f\x8bnot really gzip")
    with caplog.at_level(logging.WARNING):
        assert sniff_format(path) is None
    assert "cannot read" in caplog.text


def test_sniff_format_truncated_bzip2(tmp_path, caplog):
    path = write(tmp_path, "broken.bz2", bz2.compress(FASTA.read_bytes())[:20])
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
    assert not is_supported(write(tmp_path, "notes.txt", b"hello\n"))
