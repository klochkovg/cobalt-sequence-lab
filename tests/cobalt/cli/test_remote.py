import pytest

from cobalt.cli import main as cli_main
from cobalt.cli.main import main
from cobalt.cli.remote import SERVER_ENV, resolve_server


def test_resolve_server_default_is_local():
    assert resolve_server(None, False, environ={}) is None


def test_resolve_server_from_flag():
    assert resolve_server("http://lab-a:8000/", False, environ={}) == "http://lab-a:8000"


def test_resolve_server_from_env():
    environ = {SERVER_ENV: " https://lab-a "}
    assert resolve_server(None, False, environ=environ) == "https://lab-a"


def test_resolve_server_flag_overrides_env():
    environ = {SERVER_ENV: "http://env-host"}
    assert resolve_server("http://flag-host", False, environ=environ) == "http://flag-host"


def test_resolve_server_local_overrides_env():
    assert resolve_server(None, True, environ={SERVER_ENV: "http://lab-a"}) is None


def test_resolve_server_blank_env_is_local():
    assert resolve_server(None, False, environ={SERVER_ENV: "  "}) is None


@pytest.mark.parametrize("url", ["lab-a:8000", "ftp://lab-a", "http://", "lab-a"])
def test_resolve_server_rejects_bad_url(url):
    with pytest.raises(ValueError, match="--server"):
        resolve_server(url, False, environ={})


def test_resolve_server_bad_env_names_variable():
    with pytest.raises(ValueError, match=SERVER_ENV):
        resolve_server(None, False, environ={SERVER_ENV: "lab-a"})


@pytest.fixture
def recorded(monkeypatch):
    """Replace the stats handler with one that records its arguments."""
    calls = []

    def fake_stats(argv):
        calls.append(list(argv))
        return 0

    monkeypatch.setitem(cli_main.COMMAND_HANDLERS, "stats", fake_stats)
    monkeypatch.delenv(SERVER_ENV, raising=False)
    return calls


def test_main_local_by_default(recorded, capsys):
    assert main(["stats", "x.fasta"]) == 0
    assert recorded == [["x.fasta"]]
    assert "client mode" not in capsys.readouterr().err


def test_main_server_flag_runs_locally_with_warning(recorded, capsys):
    assert main(["--server", "http://lab-a:8000", "stats", "x.fasta"]) == 0
    assert recorded == [["x.fasta"]]
    err = capsys.readouterr().err
    assert "client mode is not implemented yet" in err
    assert "http://lab-a:8000" in err


def test_main_server_from_env(recorded, capsys, monkeypatch):
    monkeypatch.setenv(SERVER_ENV, "http://lab-a")
    assert main(["stats", "x.fasta"]) == 0
    assert recorded == [["x.fasta"]]
    assert "client mode is not implemented yet" in capsys.readouterr().err


def test_main_local_flag_ignores_env(recorded, capsys, monkeypatch):
    monkeypatch.setenv(SERVER_ENV, "http://lab-a")
    assert main(["--local", "stats", "x.fasta"]) == 0
    assert "client mode" not in capsys.readouterr().err


def test_main_bad_server_url_fails(recorded, capsys):
    assert main(["--server", "lab-a", "stats", "x.fasta"]) == 1
    assert recorded == []
    assert "expected an http:// or https:// URL" in capsys.readouterr().err


def test_main_server_and_local_are_exclusive(recorded):
    with pytest.raises(SystemExit):
        main(["--server", "http://lab-a", "--local", "stats", "x.fasta"])


def test_main_local_only_command_ignores_server(capsys, monkeypatch):
    monkeypatch.setenv(SERVER_ENV, "not a url")
    assert main(["help"]) == 0
    captured = capsys.readouterr()
    assert "Available commands" in captured.out
    assert "client mode" not in captured.err
