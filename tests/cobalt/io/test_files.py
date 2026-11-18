import stat

from cobalt.io.files import write_text_atomic


def test_write_text_atomic(tmp_path):
    path = tmp_path / "sub" / "file.txt"
    write_text_atomic(path, "one")
    write_text_atomic(path, "two")
    assert path.read_text() == "two"
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    assert [p.name for p in path.parent.iterdir()] == ["file.txt"]


def test_write_text_atomic_mode(tmp_path):
    path = tmp_path / "secret"
    write_text_atomic(path, "x", mode=0o600)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
