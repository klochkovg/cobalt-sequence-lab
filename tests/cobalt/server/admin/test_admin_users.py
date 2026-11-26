"""Tests of `cobalt-admin users ...`."""

from pathlib import Path

import pytest

from cobalt import __version__
from cobalt.server.admin.main import main
from cobalt.server.config import HOME_ENV
from cobalt.server.users import UserStore

PASSWORD = "correct horse"
USERS_DB = Path(".cobalt-server/users.sqlite3")


def users_main(*args):
    return main(["users", *args])


def store():
    return UserStore(USERS_DB)


def test_add_without_password_and_list(capsys):
    assert users_main("add", "ada", "--no-password") == 0
    key = capsys.readouterr().out.strip()
    assert key.startswith("cobalt_")
    assert USERS_DB.is_file()
    assert Path(".cobalt-server/cobalt-config.yaml").is_file()

    assert users_main("list") == 0
    out = capsys.readouterr().out
    assert "lab user (default)" in out
    rows = [line.split() for line in out.splitlines()]
    assert rows[0] == ["NAME", "KEYS", "PASSWORD", "CREATED"]
    assert rows[1][:3] == ["ada", f"{key[:12]}...", "-"]


def test_add_with_password_on_terminal(terminal, capsys):
    terminal(PASSWORD, PASSWORD)
    assert users_main("add", "ada") == 0
    assert capsys.readouterr().out.strip().startswith("cobalt_")
    assert store().check_password("ada", PASSWORD).name == "ada"
    assert users_main("list") == 0
    assert capsys.readouterr().out.splitlines()[1].split()[2] == "yes"


def test_add_with_password_from_stdin(stdin):
    stdin(PASSWORD + "\n")
    assert users_main("add", "ada", "--password-stdin") == 0
    assert store().check_password("ada", PASSWORD) is not None


def test_add_mismatched_passwords(terminal, caplog):
    terminal(PASSWORD, "something else")
    assert users_main("add", "ada") == 1
    assert "passwords do not match" in caplog.text
    assert store().get("ada") is None


def test_add_short_password(stdin, caplog):
    stdin("short\n")
    assert users_main("add", "ada", "--password-stdin") == 1
    assert "at least 8 characters" in caplog.text
    assert store().get("ada") is None


def test_add_without_terminal_needs_a_flag(caplog):
    assert users_main("add", "ada") == 1
    assert "--password-stdin" in caplog.text
    assert store().get("ada") is None


def test_add_existing_user_asks_no_password(caplog):
    assert users_main("add", "ada", "--no-password") == 0
    # No terminal and no flag: an error about the password would come first if it were asked
    assert users_main("add", "ada") == 1
    assert "already exists: ada" in caplog.text


def test_passwd(stdin, terminal):
    assert users_main("add", "ada", "--no-password") == 0
    stdin(PASSWORD + "\n")
    assert users_main("passwd", "ada", "--password-stdin") == 0
    assert store().check_password("ada", PASSWORD) is not None

    terminal("new password", "new password")
    assert users_main("passwd", "ada") == 0
    assert store().check_password("ada", PASSWORD) is None
    assert store().check_password("ada", "new password") is not None

    assert users_main("passwd", "ada", "--clear") == 0
    assert store().check_password("ada", "new password") is None


@pytest.mark.parametrize(
    ("name", "message"),
    [("nobody", "no such user: nobody"), ("lab user", "default user can't have a password")],
)
def test_passwd_errors(caplog, name, message):
    assert users_main("passwd", name) == 1
    assert message in caplog.text


def test_rotate_key(capsys):
    assert users_main("add", "ada", "--no-password") == 0
    old = capsys.readouterr().out.strip()
    assert users_main("rotate-key", "ada") == 0
    new = capsys.readouterr().out.strip()
    assert new.startswith("cobalt_")
    assert new != old
    assert store().user_for_key(old) is None
    assert store().user_for_key(new).name == "ada"


def test_rename_and_remove(capsys):
    assert users_main("add", "ada", "--no-password") == 0
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
        (("add", " ", "--no-password"), "must not be empty"),
        (("rotate-key", "nobody"), "no such user: nobody"),
        (("rotate-key", "lab user"), "default user can't have API keys"),
    ],
)
def test_errors(caplog, args, message):
    assert users_main(*args) == 1
    assert message in caplog.text


def test_users_need_an_action():
    with pytest.raises(SystemExit):
        users_main()


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        main([])


def test_storage_dir_flag(tmp_path):
    assert (
        main(["--storage-dir", str(tmp_path / "store"), "users", "add", "a", "--no-password"]) == 0
    )
    assert (tmp_path / "store" / "users.sqlite3").is_file()


def test_server_home_env(monkeypatch, tmp_path):
    monkeypatch.setenv(HOME_ENV, str(tmp_path / "home"))
    assert users_main("add", "ada", "--no-password") == 0
    assert (tmp_path / "home" / "users.sqlite3").is_file()
    assert not Path(".cobalt-server").exists()


def test_home_flag_overrides_env(monkeypatch, tmp_path):
    monkeypatch.setenv(HOME_ENV, str(tmp_path / "env-home"))
    assert main(["--home", str(tmp_path / "flag-home"), "users", "list"]) == 0
    assert (tmp_path / "flag-home" / "users.sqlite3").is_file()
    assert not (tmp_path / "env-home").exists()


def test_missing_explicit_config(tmp_path, caplog):
    assert main(["--config", str(tmp_path / "missing.yaml"), "users", "list"]) == 1
    assert "config file not found" in caplog.text


def test_unusable_store(caplog):
    USERS_DB.parent.mkdir()
    USERS_DB.write_text("not a database " * 100)
    assert users_main("list") == 1
    assert "could not open user store" in caplog.text


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out == f"cobalt-admin {__version__}\n"
