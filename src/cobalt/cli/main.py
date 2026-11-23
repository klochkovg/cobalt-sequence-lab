"""Top-level CLI dispatcher for cobalt."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable, Sequence

from cobalt import __version__
from cobalt.cli import foldrna, help, inspect, normalize, pipeline, run, runs, stats, validate
from cobalt.cli.remote import (
    LOCAL_COMMANDS,
    SERVER_ENV,
    SERVER_ONLY_COMMANDS,
    resolve_server,
    run_remote,
)
from cobalt.logging_config import configure_logging

log = logging.getLogger(__name__)

# Exit status of a process killed by SIGPIPE (128 + 13), as `cat` or `grep` report it
EXIT_BROKEN_PIPE = 141


COMMAND_HANDLERS: dict[str, Callable[[Sequence[str] | None], int]] = {
    "inspect": inspect.main,
    "stats": stats.main,
    "normalize": normalize.main,
    "validate": validate.main,
    "foldrna": foldrna.main,
    "run": run.main,
    "pipeline": pipeline.main,
    "runs": runs.main,
    "help": help.main,
}

# Handlers of SERVER_ONLY_COMMANDS: they also take the server URL (None in local mode)
SERVER_ONLY_HANDLERS: dict[str, Callable[[Sequence[str] | None, str | None], int]] = {
    "run": run.main,
    "runs": runs.main,
}


def build_parser() -> argparse.ArgumentParser:
    """Build top-level parser for `cobalt` command."""
    parser = argparse.ArgumentParser(prog="cobalt")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Show more diagnostics on stderr (-v: info, -vv: debug)",
    )
    verbosity.add_argument("-q", "--quiet", action="store_true", help="Show only errors on stderr")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--server",
        metavar="URL",
        help=f"Client mode: run the command on the cobalt server at URL (default: ${SERVER_ENV})",
    )
    mode.add_argument(
        "--local", action="store_true", help=f"Run the command locally, ignoring ${SERVER_ENV}"
    )
    parser.add_argument(
        "command",
        choices=sorted(COMMAND_HANDLERS),
        help="Subcommand to run",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to subcommand",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the top-level cobalt CLI dispatcher."""
    parsed = build_parser().parse_args(argv)
    configure_logging(parsed.verbose, parsed.quiet)
    handler = COMMAND_HANDLERS[parsed.command]
    server = None
    if parsed.command not in LOCAL_COMMANDS:
        try:
            server = resolve_server(parsed.server, parsed.local)
        except ValueError as exc:
            log.error("%s", exc)
            return 1
    try:
        if parsed.command in SERVER_ONLY_COMMANDS:
            return int(SERVER_ONLY_HANDLERS[parsed.command](parsed.args, server))
        if server is not None:
            return int(run_remote(server, parsed.command, parsed.args, handler))
        return int(handler(parsed.args))
    except BrokenPipeError:
        # The reader of stdout exited early (e.g. `cobalt stats big.fa | head`): stop quietly.
        # stdout is pointed at devnull so the flush at interpreter exit doesn't fail again.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return EXIT_BROKEN_PIPE


if __name__ == "__main__":
    raise SystemExit(main())
