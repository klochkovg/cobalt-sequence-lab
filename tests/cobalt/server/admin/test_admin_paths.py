"""Tests of `cobalt-admin paths`."""

from pathlib import Path

from cobalt.server.admin.main import main
from cobalt.server.config import HOME_ENV


def paths(capsys, *flags):
    assert main([*flags, "paths"]) == 0
    return dict(line.split(": ", 1) for line in capsys.readouterr().out.splitlines())


def test_default_paths(capsys, admin_cwd):
    home = admin_cwd / ".cobalt-server"
    assert paths(capsys) == {
        "config": str(home / "cobalt-config.yaml"),
        "storage_dir": str(home),
        "users_db": str(home / "users.sqlite3"),
        "runs_dir": str(home / "runs"),
    }


def test_paths_follow_server_home(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv(HOME_ENV, str(tmp_path / "home"))
    result = paths(capsys)
    assert result["config"] == str(tmp_path / "home" / "cobalt-config.yaml")
    assert result["users_db"] == str(tmp_path / "home" / "users.sqlite3")


def test_paths_storage_dir_from_config(capsys, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "cobalt-config.yaml").write_text("config_version: 1\nstorage_dir: ../store\n")
    result = paths(capsys, "--home", str(home))
    assert Path(result["storage_dir"]) == (home / "../store").absolute()
    assert Path(result["users_db"]) == (home / "../store/users.sqlite3").absolute()
    # Only shows the locations: creates no storage
    assert not (tmp_path / "store").exists()
