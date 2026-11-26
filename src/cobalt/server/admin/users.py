"""`cobalt-admin users ...`: manage the users, passwords and API keys of the server's user store.

The commands work on the store file directly, also while the server runs. A password is never
taken from a flag (flags are visible in `ps`): it is asked for on a terminal, or read from stdin
with `--password-stdin`.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sys
from pathlib import Path

from cobalt.server.config import ServerConfig
from cobalt.server.users import (
    USERS_DB_FILENAME,
    UserInfo,
    UserStore,
    UserStoreError,
    check_password_policy,
    users_db_path,
)

log = logging.getLogger(__name__)


def add_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the `users` command and its actions."""
    users = commands.add_parser(
        "users",
        help="Manage users, passwords and API keys",
        description=f"Manage the users, passwords and API keys in <storage-dir>/{USERS_DB_FILENAME}",
    )
    users.set_defaults(run=run)
    actions = users.add_subparsers(dest="users_command", required=True, metavar="ACTION")

    add = actions.add_parser(
        "add", help="Add a user with a password; print its new API key (shown once)"
    )
    add.add_argument("name", help="User name")
    add_source = add.add_mutually_exclusive_group()
    add_source.add_argument(
        "--password-stdin", action="store_true", help="Read the password from stdin (one line)"
    )
    add_source.add_argument("--no-password", action="store_true", help="Add the user without one")

    passwd = actions.add_parser("passwd", help="Change a user's password")
    passwd.add_argument("name", help="User name")
    passwd_source = passwd.add_mutually_exclusive_group()
    passwd_source.add_argument(
        "--password-stdin", action="store_true", help="Read the password from stdin (one line)"
    )
    passwd_source.add_argument("--clear", action="store_true", help="Remove the password")

    rotate = actions.add_parser(
        "rotate-key", help="Revoke a user's API keys and print a new one (shown once)"
    )
    rotate.add_argument("name", help="User name")

    actions.add_parser("list", help="List users, the start of their API keys, passwords")
    rename = actions.add_parser("rename", help="Rename a user (also the default user)")
    rename.add_argument("old", help="Current name")
    rename.add_argument("new", help="New name")
    remove = actions.add_parser("remove", help="Remove a user and its API keys")
    remove.add_argument("name", help="User name")


def format_users(infos: list[UserInfo]) -> str:
    """Return the `users list` table."""
    rows = [("NAME", "KEYS", "PASSWORD", "CREATED")]
    for info in infos:
        name = info.user.name + (" (default)" if info.user.is_default else "")
        keys = ", ".join(f"{hint}..." for hint in info.key_hints) or "-"
        password = "yes" if info.has_password else "-"
        rows.append((name, keys, password, info.user.created_at.isoformat(timespec="seconds")))
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    return "\n".join(
        "  ".join(f"{cell:<{width}}" for cell, width in zip(row[:3], widths, strict=True))
        + f"  {row[3]}"
        for row in rows
    )


def read_password(from_stdin: bool) -> str:
    """Return a new password: one stdin line, or asked twice on a terminal.

    Raises UserStoreError if none can be read, the two entries differ or it is too weak.
    """
    if from_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    elif sys.stdin.isatty():
        password = getpass.getpass("New password: ")
        if getpass.getpass("Repeat password: ") != password:
            raise UserStoreError("passwords do not match")
    else:
        raise UserStoreError(
            "no terminal to ask for the password: use --password-stdin (or --no-password / --clear)"
        )
    check_password_policy(password)
    return password


def run(args: argparse.Namespace, config: ServerConfig, config_path: Path) -> int:
    """Run the `users` action in `args` on the store under `config.storage_dir`."""
    try:
        config.storage_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UserStoreError(
            f"could not create storage directory {config.storage_dir}: {exc}"
        ) from None
    store = UserStore(users_db_path(config))
    try:
        _run_action(args, store)
    finally:
        store.close()
    return 0


def _show_key(name: str, key: str) -> None:
    log.warning("API key of %s, shown only now: store it safely", name)
    sys.stdout.write(key + "\n")


def _run_action(args: argparse.Namespace, store: UserStore) -> None:
    command = args.users_command
    if command == "add":
        # Checked before asking for the password; add_user checks again
        if store.get(args.name) is not None:
            raise UserStoreError(f"user already exists: {args.name.strip()}")
        password = None if args.no_password else read_password(args.password_stdin)
        user, key = store.add_user(args.name, password)
        _show_key(user.name, key)
    elif command == "passwd":
        # Checked before asking for the password; set_password checks again
        account = store.get(args.name)
        if account is None:
            raise UserStoreError(f"no such user: {args.name.strip()}")
        if account.is_default:
            raise UserStoreError(f"the default user can't have a password: {account.name}")
        password = None if args.clear else read_password(args.password_stdin)
        store.set_password(account.name, password)
    elif command == "rotate-key":
        _show_key(args.name.strip(), store.rotate_key(args.name))
    elif command == "list":
        sys.stdout.write(format_users(store.list_users()) + "\n")
    elif command == "rename":
        store.rename_user(args.old, args.new)
    elif command == "remove":
        store.remove_user(args.name)
    else:  # pragma: no cover - argparse only allows the actions above
        raise ValueError(f"unknown users action: {command}")
