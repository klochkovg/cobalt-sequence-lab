"""Tests of the `cobalt-server` entry point: flags, config file and startup checks."""

import logging
import sys
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from cobalt import __version__
from cobalt.core.pipeline import load_pipeline
from cobalt.server.auth import API_KEYS_ENV
from cobalt.server.config import ServerConfig, load_server_config
from cobalt.server.main import build_parser, main
from cobalt.server.registry import RunRegistry

VERSION_BODY = {"title": "Cobalt Sequence Lab", "version": __version__}
PIPELINE_FILE = Path(__file__).parents[2] / "test_data" / "pipeline_test_v1.yaml"
ONE_MB = 1024 * 1024


def registry_with_run(runs_dir):
    registry = RunRegistry(runs_dir)
    run = registry.create(load_pipeline(PIPELINE_FILE), PIPELINE_FILE.read_text(), {"k": "v"})
    return registry, run


def test_parser_cors():
    parser = build_parser()
    assert parser.parse_args([]).cors is None
    assert parser.parse_args(["--cors"]).cors == []
    assert parser.parse_args(["--cors", "http://a", "http://b"]).cors == ["http://a", "http://b"]


def test_parser_flags_default_to_not_given():
    # None means "not given": the config file provides the value
    args = build_parser().parse_args([])
    for name in (
        "config",
        "host",
        "port",
        "cors",
        "auth",
        "allow_no_auth",
        "api_prefix",
        "max_upload_mb",
        "ui_dist",
        "storage_dir",
    ):
        assert getattr(args, name) is None, name


def test_parser_given_flags():
    args = build_parser().parse_args(["--allow-no-auth", "--api-prefix", "", "--port", "1"])
    assert (args.allow_no_auth, args.api_prefix, args.port) == (True, "", 1)


def test_parser_rejects_negative_upload_limit():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--max-upload-mb", "-1"])


@pytest.fixture
def uvicorn_calls(monkeypatch, tmp_path):
    """Record uvicorn.run calls instead of starting a server.

    Also runs in an empty working directory, where `main` creates its default config.
    """
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.append((app, kwargs)))
    return calls


def test_main_api_key_without_keys_fails(monkeypatch, uvicorn_calls):
    monkeypatch.delenv(API_KEYS_ENV, raising=False)
    assert main(["--auth", "api-key"]) == 1
    assert uvicorn_calls == []


def test_main_refuses_no_auth_on_public_host(uvicorn_calls):
    assert main(["--host", "0.0.0.0"]) == 1
    assert uvicorn_calls == []


def test_main_allow_no_auth_on_public_host(uvicorn_calls):
    assert main(["--host", "0.0.0.0", "--allow-no-auth"]) == 0
    assert len(uvicorn_calls) == 1


def test_main_no_auth_on_loopback(uvicorn_calls):
    assert main(["--host", "localhost"]) == 0
    assert main(["--host", "::1"]) == 0
    assert len(uvicorn_calls) == 2


def test_main_api_key(monkeypatch, uvicorn_calls):
    monkeypatch.setenv(API_KEYS_ENV, "k1")
    assert main(["--host", "0.0.0.0", "--auth", "api-key"]) == 0
    ((app, kwargs),) = uvicorn_calls
    assert kwargs["host"] == "0.0.0.0"
    client = TestClient(app)
    assert client.post("/api/stats", data={"sequence": "ACGT"}).status_code == 401
    resp = client.post("/api/stats", data={"sequence": "ACGT"}, headers={"X-API-Key": "k1"})
    assert resp.status_code == 200


def test_main_api_prefix(uvicorn_calls):
    assert main(["--api-prefix", ""]) == 0
    ((app, _),) = uvicorn_calls
    assert TestClient(app).get("/").json() == VERSION_BODY


def test_main_ui_dist(uvicorn_calls, ui_dist):
    assert main(["--ui-dist", str(ui_dist)]) == 0
    ((app, _),) = uvicorn_calls
    assert TestClient(app).get("/").text == "<html>cobalt ui</html>"


def test_main_ui_dist_without_index(uvicorn_calls, tmp_path):
    assert main(["--ui-dist", str(tmp_path)]) == 1
    assert uvicorn_calls == []


def test_main_ui_dist_needs_prefix(uvicorn_calls, ui_dist):
    assert main(["--ui-dist", str(ui_dist), "--api-prefix", ""]) == 1
    assert uvicorn_calls == []


def test_main_max_upload_mb(uvicorn_calls):
    assert main(["--max-upload-mb", "1"]) == 0
    ((app, _),) = uvicorn_calls
    files = [("file", ("big.fasta", b">s\n" + b"A" * ONE_MB))]
    assert TestClient(app).post("/api/stats", files=files).status_code == 413


def write_config(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_main_creates_default_config(uvicorn_calls):
    assert main([]) == 0
    config_path = Path(".cobalt-server/cobalt-config.yaml")
    assert config_path.is_file()
    assert load_server_config(config_path) == ServerConfig()
    ((_, kwargs),) = uvicorn_calls
    assert (kwargs["host"], kwargs["port"]) == ("127.0.0.1", 8000)


def test_main_uses_config_values(uvicorn_calls):
    write_config(
        Path(".cobalt-server/cobalt-config.yaml"),
        "config_version: 1\nhost: localhost\nport: 9000\napi_prefix: /v2\n",
    )
    assert main([]) == 0
    ((app, kwargs),) = uvicorn_calls
    assert (kwargs["host"], kwargs["port"]) == ("localhost", 9000)
    assert TestClient(app).get("/v2/health").status_code == 200


def test_main_flags_override_config(uvicorn_calls):
    write_config(
        Path(".cobalt-server/cobalt-config.yaml"),
        "config_version: 1\nport: 9000\napi_prefix: /v2\n",
    )
    assert main(["--port", "8080", "--api-prefix", ""]) == 0
    ((app, kwargs),) = uvicorn_calls
    assert kwargs["port"] == 8080
    assert TestClient(app).get("/health").status_code == 200


def test_main_explicit_config(uvicorn_calls, tmp_path):
    path = write_config(tmp_path / "conf" / "server.yaml", "config_version: 1\nport: 9100\n")
    assert main(["--config", str(path)]) == 0
    assert uvicorn_calls[0][1]["port"] == 9100
    assert (tmp_path / "conf").is_dir()
    assert not Path(".cobalt-server").exists()


def test_main_explicit_missing_config_fails(uvicorn_calls, tmp_path, caplog):
    assert main(["--config", str(tmp_path / "missing.yaml")]) == 1
    assert uvicorn_calls == []
    assert "config file not found" in caplog.text
    assert not (tmp_path / "missing.yaml").exists()


def test_main_invalid_config_fails(uvicorn_calls, caplog):
    write_config(Path(".cobalt-server/cobalt-config.yaml"), "config_version: 1\nport: abc\n")
    assert main([]) == 1
    assert uvicorn_calls == []
    assert "cobalt-config.yaml: port: expected an integer 1-65535" in caplog.text


def test_main_config_auth_without_keys_fails(monkeypatch, uvicorn_calls):
    monkeypatch.delenv(API_KEYS_ENV, raising=False)
    write_config(Path(".cobalt-server/cobalt-config.yaml"), "config_version: 1\nauth: api-key\n")
    assert main([]) == 1
    assert uvicorn_calls == []


def test_main_creates_storage_dir_relative_to_config(uvicorn_calls, tmp_path):
    path = write_config(tmp_path / "conf" / "server.yaml", "config_version: 1\nstorage_dir: data\n")
    assert main(["--config", str(path)]) == 0
    assert (tmp_path / "conf" / "data").is_dir()


def test_main_storage_dir_flag(uvicorn_calls, tmp_path):
    assert main(["--storage-dir", str(tmp_path / "store")]) == 0
    assert (tmp_path / "store").is_dir()


def test_main_creates_runs_registry(uvicorn_calls):
    assert main([]) == 0
    ((app, _),) = uvicorn_calls
    assert app.state.runs.runs_dir == Path(".cobalt-server/runs").absolute()
    assert Path(".cobalt-server/runs").is_dir()


def test_main_loads_stored_runs(uvicorn_calls):
    _, run = registry_with_run(Path(".cobalt-server/runs"))
    assert main([]) == 0
    ((app, _),) = uvicorn_calls
    assert TestClient(app).get(f"/api/runs/{run.run_id}").json()["run_id"] == run.run_id


def test_main_runs_dir_unusable(uvicorn_calls):
    # A file where the runs directory should be
    write_config(Path(".cobalt-server/runs"), "not a directory")
    assert main([]) == 1
    assert uvicorn_calls == []


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out == f"cobalt-server {__version__}\n"


@pytest.mark.parametrize(("flags", "level"), [([], logging.INFO), (["-q"], logging.ERROR)])
def test_logging_flags(uvicorn_calls, flags, level):
    assert main(flags) == 0
    assert logging.getLogger().level == level


def test_verbose_flag_shows_debug(uvicorn_calls):
    assert main(["-v"]) == 0
    assert logging.getLogger().level == logging.DEBUG


def test_missing_server_dependencies(monkeypatch, uvicorn_calls, caplog):
    monkeypatch.setitem(sys.modules, "uvicorn", None)  # import uvicorn raises ImportError
    assert main([]) == 1
    assert uvicorn_calls == []
    assert 'pip install "cobalt-sequence-lab[server]"' in caplog.text


def users_main(*args):
    return main(["users", *args])


def test_users_add_and_list(uvicorn_calls, capsys):
    assert users_main("add", "ada") == 0
    key = capsys.readouterr().out.strip()
    assert key.startswith("cobalt_")
    assert Path(".cobalt-server/users.sqlite3").is_file()

    assert users_main("list") == 0
    out = capsys.readouterr().out
    assert "lab user (default)" in out
    rows = [line.split() for line in out.splitlines()]
    assert ["ada", f"{key[:12]}..."] == rows[1][:2]
    assert uvicorn_calls == []


def test_users_rename_and_remove(uvicorn_calls, capsys):
    assert users_main("add", "ada") == 0
    assert users_main("rename", "ada", "bob") == 0
    assert users_main("remove", "bob") == 0
    capsys.readouterr()
    assert users_main("list") == 0
    out = capsys.readouterr().out
    assert "ada" not in out
    assert "bob" not in out


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("remove", "lab user"), "default user can't be removed"),
        (("remove", "nobody"), "no such user: nobody"),
        (("rename", "nobody", "x"), "no such user: nobody"),
        (("add", " "), "must not be empty"),
    ],
)
def test_users_errors(uvicorn_calls, caplog, args, message):
    assert users_main(*args) == 1
    assert message in caplog.text


def test_users_need_an_action(uvicorn_calls):
    with pytest.raises(SystemExit):
        users_main()


def test_users_storage_dir_flag(uvicorn_calls, tmp_path, capsys):
    assert main(["--storage-dir", str(tmp_path / "store"), "users", "add", "ada"]) == 0
    assert (tmp_path / "store" / "users.sqlite3").is_file()


def test_users_unusable_store(uvicorn_calls, caplog):
    write_config(Path(".cobalt-server/users.sqlite3"), "not a database " * 100)
    assert users_main("list") == 1
    assert "could not open user store" in caplog.text
    assert main([]) == 1
    assert uvicorn_calls == []


def test_main_serves_user_keys(monkeypatch, uvicorn_calls, capsys):
    monkeypatch.delenv(API_KEYS_ENV, raising=False)
    assert users_main("add", "ada") == 0
    key = capsys.readouterr().out.strip()
    assert main(["--auth", "api-key"]) == 0
    ((app, _),) = uvicorn_calls
    client = TestClient(app)
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"X-API-Key": key}).json() == {"name": "ada"}


def test_main_no_auth_me_is_default_user(uvicorn_calls):
    assert users_main("rename", "lab user", "Lab") == 0
    assert main([]) == 0
    ((app, _),) = uvicorn_calls
    assert TestClient(app).get("/api/me").json() == {"name": "Lab"}
