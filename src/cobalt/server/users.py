"""The user store of the server: users and their API keys in a SQLite file.

`cobalt-server` keeps `<storage_dir>/users.sqlite3`; `cobalt-admin users ...` manages it, also
while the server runs. API keys are stored as SHA-256 hashes only: a key is shown once, when it
is created. Passwords (optional, for a future UI login) are stored as salted scrypt hashes. The schema is versioned with `PRAGMA user_version`; opening a store applies the
missing migrations.

A seeded default user stands for callers without an account: every caller when authentication
is off, and callers with a key from `$COBALT_API_KEYS`. It can be renamed, never removed.

This module must not import the optional `server` dependencies (fastapi, uvicorn).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cobalt.core.pipeline.run import utc_now
from cobalt.server.config import ServerConfig

log = logging.getLogger(__name__)

USERS_DB_FILENAME = "users.sqlite3"
DEFAULT_USER_NAME = "lab user"
MAX_NAME_LENGTH = 100
KEY_PREFIX = "cobalt_"
# Characters of a key shown by `users list`: the prefix and a few random ones
KEY_HINT_LENGTH = 12
MIN_PASSWORD_LENGTH = 8
# scrypt parameters of new password hashes; stored with each hash, so they can be raised later
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_SALT_BYTES = 16
SCRYPT_DKLEN = 32
# How long a writer waits for another process's lock before failing
BUSY_TIMEOUT_MS = 5000

# Statements of each schema version; MIGRATIONS[n] upgrades version n to n + 1. Never edit a
# released entry: append a new one.
MIGRATIONS: tuple[tuple[str, ...], ...] = (
    (
        """CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE api_keys (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key_hash TEXT NOT NULL UNIQUE,
            hint TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""",
        "CREATE INDEX api_keys_user_id ON api_keys(user_id)",
        f"""INSERT INTO users (name, created_at, is_default)
            VALUES ('{DEFAULT_USER_NAME}', strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now'), 1)""",
    ),
    # 1 -> 2: optional password; NULL means the user has none
    ("ALTER TABLE users ADD COLUMN password_hash TEXT",),
)
SCHEMA_VERSION = len(MIGRATIONS)

_USER_COLUMNS = "users.id, users.name, users.created_at, users.is_default"


def users_db_path(config: ServerConfig) -> Path:
    """Return the user store file of the server configured by `config`."""
    return config.storage_dir / USERS_DB_FILENAME


class UserStoreError(Exception):
    """A user store operation that failed; the message is ready to log."""


@dataclass(frozen=True, slots=True)
class User:
    """A user of the server."""

    id: int
    name: str
    created_at: datetime
    is_default: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> User:
        return cls(
            id=row["id"],
            name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            is_default=bool(row["is_default"]),
        )


@dataclass(frozen=True, slots=True)
class UserInfo:
    """A user with the hints of its API keys, as `users list` shows it."""

    user: User
    key_hints: tuple[str, ...]
    has_password: bool = False


def hash_key(key: str) -> str:
    """Return the stored form of an API key.

    Keys are long random strings, so a plain SHA-256 is enough (no salt or slow hash needed).
    """
    return hashlib.sha256(key.encode()).hexdigest()


def new_key() -> str:
    """Return a new random API key."""
    return KEY_PREFIX + secrets.token_urlsafe(32)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def check_password_policy(password: str) -> None:
    """Raise UserStoreError if `password` is too weak to be stored."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise UserStoreError(f"password must have at least {MIN_PASSWORD_LENGTH} characters")


def hash_password(password: str) -> str:
    """Return the stored form of a password: `scrypt$n$r$p$<salt>$<hash>` (base64 salt, hash)."""
    salt = secrets.token_bytes(SCRYPT_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_DKLEN
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """Return True if `password` matches `stored` (from `hash_password`); False if malformed."""
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        expected_bytes = base64.b64decode(expected, validate=True)
        digest = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt, validate=True),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_bytes),
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest, expected_bytes)


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise UserStoreError("user name must not be empty")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise UserStoreError(f"user name is longer than {MAX_NAME_LENGTH} characters")
    return cleaned


class UserStore:
    """Users and API keys of the server; safe to use from several threads.

    `path` None keeps the store in memory (nothing is written). Raises UserStoreError if the
    file can't be opened or was written by a newer cobalt.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lock = threading.Lock()
        try:
            # isolation_level None: no implicit transactions, each write commits unless in BEGIN
            self._conn = sqlite3.connect(
                ":memory:" if path is None else path,
                check_same_thread=False,
                isolation_level=None,
            )
        except sqlite3.Error as exc:
            raise UserStoreError(f"could not open user store {path}: {exc}") from None
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            self._conn.execute("PRAGMA foreign_keys = ON")
            if path is not None:
                self._conn.execute("PRAGMA journal_mode = WAL")
            self._migrate()
        except sqlite3.Error as exc:
            self._conn.close()
            raise UserStoreError(f"could not open user store {path}: {exc}") from None
        except UserStoreError:
            self._conn.close()
            raise

    @property
    def _where(self) -> str:
        return "the in-memory user store" if self.path is None else str(self.path)

    def _migrate(self) -> None:
        # IMMEDIATE takes the write lock first, so two processes don't both migrate
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            version = self._conn.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise UserStoreError(
                    f"{self._where}: schema version {version} is newer than {SCHEMA_VERSION} "
                    "(written by a newer cobalt)"
                )
            for step in range(version, SCHEMA_VERSION):
                for statement in MIGRATIONS[step]:
                    self._conn.execute(statement)
            if version < SCHEMA_VERSION:
                self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                log.info("%s: schema version %d -> %d", self._where, version, SCHEMA_VERSION)
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()

    def default_user(self) -> User:
        """Return the default user, who stands for callers without an account."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE is_default = 1"
            ).fetchone()
        if row is None:
            raise UserStoreError(f"{self._where}: the default user is missing")
        return User.from_row(row)

    def user_for_key(self, key: str) -> User | None:
        """Return the user owning API key `key`, or None if no user has it."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_USER_COLUMNS} FROM users "
                "JOIN api_keys ON api_keys.user_id = users.id WHERE api_keys.key_hash = ?",
                (hash_key(key),),
            ).fetchone()
        return None if row is None else User.from_row(row)

    def has_keys(self) -> bool:
        """Return True if any user has an API key."""
        with self._lock:
            return self._conn.execute("SELECT 1 FROM api_keys LIMIT 1").fetchone() is not None

    def get(self, name: str) -> User | None:
        """Return the user called `name`, or None if there is none."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE name = ?", (name.strip(),)
            ).fetchone()
        return None if row is None else User.from_row(row)

    def add_user(self, name: str, password: str | None = None) -> tuple[User, str]:
        """Create user `name` with a new API key and an optional password; return user and key.

        The key is not stored, only its hash: this is the one chance to show it.
        """
        name = _clean_name(name)
        password_hash = None
        if password is not None:
            check_password_policy(password)
            password_hash = hash_password(password)
        key = new_key()
        now = utc_now().isoformat(timespec="seconds")
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = self._conn.execute(
                    "INSERT INTO users (name, created_at, password_hash) VALUES (?, ?, ?)",
                    (name, now, password_hash),
                )
                self._conn.execute(
                    "INSERT INTO api_keys (user_id, key_hash, hint, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (cursor.lastrowid, hash_key(key), key[:KEY_HINT_LENGTH], now),
                )
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError:
                self._conn.execute("ROLLBACK")
                raise UserStoreError(f"user already exists: {name}") from None
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        user = self.get(name)
        assert user is not None
        log.info("added user %s", name)
        return user, key

    def list_users(self) -> list[UserInfo]:
        """Return all users by name, with the hints of their keys."""
        with self._lock:
            users = self._conn.execute(
                f"SELECT {_USER_COLUMNS}, users.password_hash FROM users ORDER BY name"
            ).fetchall()
            hints: dict[int, list[str]] = {}
            for row in self._conn.execute("SELECT user_id, hint FROM api_keys ORDER BY id"):
                hints.setdefault(row["user_id"], []).append(row["hint"])
        return [
            UserInfo(
                User.from_row(row),
                tuple(hints.get(row["id"], [])),
                has_password=row["password_hash"] is not None,
            )
            for row in users
        ]

    def rename_user(self, old: str, new: str) -> User:
        """Rename user `old` to `new` and return it; the default user can be renamed too."""
        old, new = _clean_name(old), _clean_name(new)
        with self._lock:
            try:
                cursor = self._conn.execute("UPDATE users SET name = ? WHERE name = ?", (new, old))
            except sqlite3.IntegrityError:
                raise UserStoreError(f"user already exists: {new}") from None
        if cursor.rowcount == 0:
            raise UserStoreError(f"no such user: {old}")
        log.info("renamed user %s to %s", old, new)
        user = self.get(new)
        assert user is not None
        return user

    def remove_user(self, name: str) -> None:
        """Remove user `name` and its API keys; the default user can't be removed."""
        user = self.get(name)
        if user is None:
            raise UserStoreError(f"no such user: {name.strip()}")
        if user.is_default:
            raise UserStoreError(f"the default user can't be removed: {user.name}")
        with self._lock:
            # foreign_keys is on: the user's keys go with it (ON DELETE CASCADE)
            self._conn.execute("DELETE FROM users WHERE id = ?", (user.id,))
        log.info("removed user %s", user.name)

    def _account(self, name: str, action: str) -> User:
        """Return user `name` for `action`; the default user has no account to act on."""
        user = self.get(name)
        if user is None:
            raise UserStoreError(f"no such user: {name.strip()}")
        if user.is_default:
            raise UserStoreError(f"the default user can't {action}: {user.name}")
        return user

    def set_password(self, name: str, password: str | None) -> None:
        """Set the password of user `name`; None removes it. Not for the default user."""
        user = self._account(name, "have a password")
        password_hash = None
        if password is not None:
            check_password_policy(password)
            password_hash = hash_password(password)
        with self._lock:
            self._conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user.id)
            )
        log.info("%s password of user %s", "set" if password is not None else "removed", user.name)

    def check_password(self, name: str, password: str) -> User | None:
        """Return user `name` if `password` is its password, else None (also without one)."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_USER_COLUMNS}, users.password_hash FROM users WHERE name = ?",
                (name.strip(),),
            ).fetchone()
        if row is None or row["password_hash"] is None:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return User.from_row(row)

    def rotate_key(self, name: str) -> str:
        """Replace all API keys of user `name` with a new one and return it (shown once)."""
        user = self._account(name, "have API keys")
        key = new_key()
        now = utc_now().isoformat(timespec="seconds")
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute("DELETE FROM api_keys WHERE user_id = ?", (user.id,))
                self._conn.execute(
                    "INSERT INTO api_keys (user_id, key_hash, hint, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (user.id, hash_key(key), key[:KEY_HINT_LENGTH], now),
                )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        log.info("new API key for user %s; its old keys are revoked", user.name)
        return key

    def __len__(self) -> int:
        with self._lock:
            count: int = self._conn.execute("SELECT count(*) FROM users").fetchone()[0]
        return count
