"""Entry point of `cobalt-admin`: shared flags, command dispatch and error reporting.

Each command group lives in its own module with an `add_parser(commands)` function that
registers it and sets `run(args, config, config_path) -> int` as the parser's `run` default.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from collections.abc import Sequence

from cobalt import __version__
from cobalt.logging_config import configure_logging
from cobalt.server.admin import paths, users
from cobalt.server.config import ServerConfigError, add_location_arguments, resolve_config
from cobalt.server.users import UserStoreError

log = logging.getLogger(__name__)

COMMAND_MODULES = (users, paths)


def build_parser() -> argparse.ArgumentParser:
    """Build the parser of the `cobalt-admin` command."""
    parser = argparse.ArgumentParser(
        prog="cobalt-admin",
        description="Administer a Cobalt Sequence Lab server on its host: users, passwords, "
        "API keys and file locations. Works while the server runs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v", "--verbose", action="count", default=0, help="Show debug details on stderr"
    )
    verbosity.add_argument("-q", "--quiet", action="store_true", help="Show only errors on stderr")
    add_location_arguments(parser)
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for module in COMMAND_MODULES:
        module.add_parser(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the `cobalt-admin` command."""
    args = build_parser().parse_args(argv)
    # Like cobalt-server: INFO by default (what was changed), -v goes straight to DEBUG
    configure_logging(args.verbose + 1 if args.verbose else 0, args.quiet, server=True)
    try:
        config, config_path = resolve_config(args.config, args.home, args.storage_dir)
        result: int = args.run(args, config, config_path)
    except (ServerConfigError, UserStoreError) as exc:
        log.error("%s", exc)
        return 1
    except sqlite3.Error as exc:
        log.error("user store: %s", exc)
        return 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
