import sqlite3

import pytest

from cobalt.server.users import (
    DEFAULT_USER_NAME,
    KEY_PREFIX,
    SCHEMA_VERSION,
    UserStore,
    UserStoreError,
    hash_key,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "users.sqlite3"


def test_new_store_has_default_user():
    store = UserStore()
    user = store.default_user()
    assert user.name == DEFAULT_USER_NAME
    assert user.is_default
    assert user.created_at.tzinfo is not None
    assert len(store) == 1
    assert not store.has_keys()


def test_add_user_key_resolves_to_user():
    store = UserStore()
    user, key = store.add_user("  ada  ")
    assert user.name == "ada"
    assert not user.is_default
    assert key.startswith(KEY_PREFIX)
    assert store.user_for_key(key) == user
    assert store.has_keys()


def test_unknown_key():
    store = UserStore()
    store.add_user("ada")
    assert store.user_for_key("cobalt_nope") is None
    assert store.user_for_key("") is None


def test_keys_are_unique_per_user():
    store = UserStore()
    _, key1 = store.add_user("ada")
    _, key2 = store.add_user("bob")
    assert key1 != key2
    assert store.user_for_key(key2).name == "bob"


def test_only_key_hash_is_stored(db_path):
    store = UserStore(db_path)
    _, key = store.add_user("ada")
    store.close()
    data = b"".join(p.read_bytes() for p in db_path.parent.glob("users.sqlite3*"))
    assert key.encode() not in data
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT key_hash FROM api_keys").fetchone()[0] == hash_key(key)


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_add_user_invalid_name(name):
    with pytest.raises(UserStoreError):
        UserStore().add_user(name)


def test_add_user_duplicate_name():
    store = UserStore()
    store.add_user("ada")
    with pytest.raises(UserStoreError, match="already exists: ada"):
        store.add_user("ada")
    with pytest.raises(UserStoreError, match="already exists"):
        store.add_user(DEFAULT_USER_NAME)
    assert len(store) == 2


def test_list_users():
    store = UserStore()
    _, key = store.add_user("ada")
    infos = store.list_users()
    assert [info.user.name for info in infos] == ["ada", DEFAULT_USER_NAME]
    assert infos[0].key_hints == (key[:12],)
    assert infos[1].key_hints == ()


def test_rename_user():
    store = UserStore()
    _, key = store.add_user("ada")
    renamed = store.rename_user("ada", "Ada Lovelace")
    assert renamed.name == "Ada Lovelace"
    assert store.user_for_key(key) == renamed
    assert store.get("ada") is None


def test_rename_default_user():
    store = UserStore()
    store.rename_user(DEFAULT_USER_NAME, "Lab")
    assert store.default_user().name == "Lab"


def test_rename_errors():
    store = UserStore()
    store.add_user("ada")
    with pytest.raises(UserStoreError, match="no such user: bob"):
        store.rename_user("bob", "carl")
    with pytest.raises(UserStoreError, match="already exists"):
        store.rename_user("ada", DEFAULT_USER_NAME)


def test_remove_user_removes_keys():
    store = UserStore()
    _, key = store.add_user("ada")
    store.remove_user("ada")
    assert store.get("ada") is None
    assert store.user_for_key(key) is None
    assert not store.has_keys()


def test_remove_errors():
    store = UserStore()
    with pytest.raises(UserStoreError, match="no such user"):
        store.remove_user("ada")
    with pytest.raises(UserStoreError, match="default user can't be removed"):
        store.remove_user(DEFAULT_USER_NAME)


def test_store_survives_reopen(db_path):
    store = UserStore(db_path)
    _, key = store.add_user("ada")
    store.rename_user(DEFAULT_USER_NAME, "Lab")
    store.close()

    reopened = UserStore(db_path)
    assert reopened.user_for_key(key).name == "ada"
    assert reopened.default_user().name == "Lab"
    assert len(reopened) == 2


def test_schema_version_set(db_path):
    UserStore(db_path).close()
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_newer_schema_refused(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    with pytest.raises(UserStoreError, match="newer cobalt"):
        UserStore(db_path)


def test_unreadable_file_refused(db_path):
    db_path.write_text("not a database " * 100)
    with pytest.raises(UserStoreError, match="could not open user store"):
        UserStore(db_path)


def test_two_stores_share_a_file(db_path):
    # The server and `cobalt-server users ...` open the same file
    server = UserStore(db_path)
    admin = UserStore(db_path)
    _, key = admin.add_user("ada")
    assert server.user_for_key(key).name == "ada"
