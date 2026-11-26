import io

import pytest


@pytest.fixture(autouse=True)
def admin_cwd(monkeypatch, tmp_path):
    """Run each admin command in an empty working directory, with no terminal on stdin."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    return cwd


@pytest.fixture
def stdin(monkeypatch):
    """Replace stdin with the given text."""

    def feed(text):
        monkeypatch.setattr("sys.stdin", io.StringIO(text))

    return feed


@pytest.fixture
def terminal(monkeypatch):
    """Make stdin a terminal whose getpass prompts answer with the given entries."""

    def answer(*entries):
        replies = iter(entries)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("getpass.getpass", lambda prompt="": next(replies))

    return answer
