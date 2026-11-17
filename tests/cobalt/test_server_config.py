import logging
import os
from pathlib import Path

import pytest

from cobalt.server_config import (
    CONFIG_VERSION,
    ServerConfig,
    ServerConfigError,
    default_config_path,
    load_server_config,
    parse_server_config,
    save_server_config,
)


def write(tmp_path, text, name="cobalt-config.yaml"):
    path = tmp_path / name
    path.write_text(text)
    return path


def test_defaults():
    config = ServerConfig()
    assert config.config_version == CONFIG_VERSION
    assert (config.host, config.port) == ("127.0.0.1", 8000)
    assert (config.api_prefix, config.max_upload_mb) == ("/api", 100)
    assert (config.cors, config.auth, config.allow_no_auth) == (None, "none", False)
    assert config.ui_dist is None
    assert config.storage_dir == Path(".")


def test_default_config_path(tmp_path):
    assert default_config_path(tmp_path) == tmp_path / ".cobalt-server" / "cobalt-config.yaml"
    assert default_config_path() == Path.cwd() / ".cobalt-server" / "cobalt-config.yaml"


def test_save_and_load_round_trip(tmp_path):
    config = ServerConfig(
        host="0.0.0.0",
        port=9000,
        api_prefix="",
        max_upload_mb=0,
        cors=["http://localhost:5173"],
        auth="api-key",
        allow_no_auth=True,
        ui_dist=Path("../ui/dist"),
        storage_dir=Path("/srv/cobalt"),
    )
    path = tmp_path / "cfg.yaml"
    save_server_config(config, path)
    assert load_server_config(path) == config


def test_save_creates_directories_and_writes_current_version(tmp_path):
    path = tmp_path / "a" / "b" / "cobalt-config.yaml"
    save_server_config(ServerConfig(config_version=0), path)
    text = path.read_text()
    assert text.startswith("# Cobalt Sequence Lab server configuration")
    assert f"config_version: {CONFIG_VERSION}\n" in text
    assert "storage_dir: .\n" in text
    assert os.stat(path).st_mode & 0o777 == 0o644
    assert [p.name for p in path.parent.iterdir()] == ["cobalt-config.yaml"]


def test_older_version_gets_defaults(tmp_path, caplog):
    path = write(tmp_path, "config_version: 0\nport: 9000\n")
    with caplog.at_level(logging.INFO):
        config = load_server_config(path)
    assert config == ServerConfig(port=9000)
    assert "config version 0 is older than 1" in caplog.text


def test_newer_version_ignores_unknown_keys(tmp_path, caplog):
    path = write(tmp_path, "config_version: 7\nport: 9000\nfuture_key: 1\nworkers: 4\n")
    config = load_server_config(path)
    assert config == ServerConfig(port=9000)
    assert config.config_version == CONFIG_VERSION
    assert "config version 7 is newer than 1" in caplog.text
    assert "ignoring unknown key(s): future_key, workers" in caplog.text


def test_load_never_rewrites_file(tmp_path):
    text = "config_version: 7\nfuture_key: 1\n"
    path = write(tmp_path, text)
    load_server_config(path)
    assert path.read_text() == text


def test_missing_version_warns(tmp_path, caplog):
    assert load_server_config(write(tmp_path, "port: 9000\n")) == ServerConfig(port=9000)
    assert "no config_version" in caplog.text


def test_empty_file_gives_defaults(tmp_path):
    assert load_server_config(write(tmp_path, "")) == ServerConfig()


def test_cors_empty_list_allows_any_origin():
    assert parse_server_config({"config_version": 1, "cors": []}).cors == []


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("- a\n- b\n", "expected a mapping, got list"),
        ("port: [1\n", "invalid YAML"),
        ("config_version: one\n", "config_version: expected an integer, got 'one'"),
        ("config_version: true\n", "config_version: expected an integer"),
        ("port: abc\n", "port: expected an integer 1-65535, got 'abc'"),
        ("port: 70000\n", "port: expected an integer 1-65535, got 70000"),
        ("port: 0\n", "port: expected an integer 1-65535"),
        ("port: true\n", "port: expected an integer 1-65535, got True"),
        ("max_upload_mb: -1\n", "max_upload_mb: expected an integer >= 0"),
        ("auth: jwt\n", "auth: expected one of none, api-key, got 'jwt'"),
        ("allow_no_auth: yes please\n", "allow_no_auth: expected true or false"),
        ("cors: 5\n", "cors: expected a list of origins"),
        ("cors: [1, 2]\n", "cors: expected a list of origins"),
        ("host: ''\n", "host: expected a non-empty string"),
        ("api_prefix: 5\n", "api_prefix: expected a string"),
        ("storage_dir: null\n", "storage_dir: expected a non-empty string"),
        ("ui_dist: 3\n", "ui_dist: expected a non-empty string"),
    ],
)
def test_invalid_values_are_errors(tmp_path, text, message):
    path = write(tmp_path, text)
    with pytest.raises(ServerConfigError, match="cobalt-config.yaml") as excinfo:
        load_server_config(path)
    assert message in str(excinfo.value)


def test_missing_file(tmp_path):
    with pytest.raises(ServerConfigError, match="config file not found"):
        load_server_config(tmp_path / "missing.yaml")


def test_directory_instead_of_file(tmp_path):
    with pytest.raises(ServerConfigError, match="is a directory"):
        load_server_config(tmp_path)


def test_resolve_paths(tmp_path):
    config = ServerConfig(ui_dist=Path("ui"), storage_dir=Path("data")).resolve_paths(tmp_path)
    assert config.storage_dir == tmp_path / "data"
    assert config.ui_dist == tmp_path / "ui"
    assert ServerConfig().resolve_paths(tmp_path).storage_dir == tmp_path
    absolute = ServerConfig(storage_dir=Path("/srv/cobalt")).resolve_paths(tmp_path)
    assert absolute.storage_dir == Path("/srv/cobalt")
    assert absolute.ui_dist is None


def test_with_overrides_ignores_none():
    config = ServerConfig(port=9000).with_overrides(port=None, host="0.0.0.0", api_prefix="")
    assert (config.port, config.host, config.api_prefix) == (9000, "0.0.0.0", "")
