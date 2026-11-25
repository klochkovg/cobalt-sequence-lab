"""`cobalt-server users ...`: manage the users and API keys of the server's user store.

The commands work on the store file directly, also while the server runs. They don't need the
optional `server` dependencies (fastapi, uvicorn).
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys

from cobalt.server.config import ServerConfig
from cobalt.server.users import USERS_DB_FILENAME, UserInfo, UserStore, UserStoreError

log = logging.getLogger(__name__)


def add_users_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the `users` command and its actions to the `cobalt-server` subcommands."""
    users = subparsers.add_parser(
        "users",
        help="Manage users and their API keys",
        description=f"Manage the users and API keys in <storage-dir>/{USERS_DB_FILENAME}",
    )
    actions = users.add_subparsers(dest="users_command", required=True, metavar="ACTION")
    add = actions.add_parser("add", help="Add a user and print its new API key (shown once)")
    add.add_argument("name", help="User name")
    actions.add_parser("list", help="List users and the start of their API keys")
    rename = actions.add_parser("rename", help="Rename a user (also the default user)")
    rename.add_argument("old", help="Current name")
    rename.add_argument("new", help="New name")
    remove = actions.add_parser("remove", help="Remove a user and its API keys")
    remove.add_argument("name", help="User name")


def format_users(infos: list[UserInfo]) -> str:
    """Return the `users list` table."""
    rows = [("NAME", "KEYS", "CREATED")]
    for info in infos:
        name = info.user.name + (" (default)" if info.user.is_default else "")
        keys = ", ".join(f"{hint}..." for hint in info.key_hints) or "-"
        rows.append((name, keys, info.user.created_at.isoformat(timespec="seconds")))
    widths = [max(len(row[i]) for row in rows) for i in range(2)]
    return "\n".join(f"{row[0]:<{widths[0]}}  {row[1]:<{widths[1]}}  {row[2]}" for row in rows)


def run_users(args: argparse.Namespace, config: ServerConfig) -> int:
    """Run the `users` action in `args` on the store under `config.storage_dir`."""
    path = config.storage_dir / USERS_DB_FILENAME
    try:
        config.storage_dir.mkdir(parents=True, exist_ok=True)
        store = UserStore(path)
    except OSError as exc:
        log.error("could not create storage directory %s: %s", config.storage_dir, exc)
        return 1
    except UserStoreError as exc:
        log.error("%s", exc)
        return 1
    try:
        return _run_action(args, store)
    except UserStoreError as exc:
        log.error("%s", exc)
        return 1
    except sqlite3.Error as exc:
        log.error("%s: %s", path, exc)
        return 1
    finally:
        store.close()


def _run_action(args: argparse.Namespace, store: UserStore) -> int:
    command = args.users_command
    if command == "add":
        user, key = store.add_user(args.name)
        log.warning("API key of %s, shown only now: store it safely", user.name)
        sys.stdout.write(key + "\n")
    elif command == "list":
        sys.stdout.write(format_users(store.list_users()) + "\n")
    elif command == "rename":
        store.rename_user(args.old, args.new)
    elif command == "remove":
        store.remove_user(args.name)
    else:  # pragma: no cover - argparse only allows the actions above
        raise ValueError(f"unknown users action: {command}")
    return 0
