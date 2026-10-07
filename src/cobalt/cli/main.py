"""Top-level CLI dispatcher for cobalt."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Sequence

from cobalt import __version__
from cobalt.cli import help, inspect, normalize, stats, validate
from cobalt.logging_config import configure_logging

log = logging.getLogger(__name__)


def _serve_main(argv: Sequence[str] | None) -> int:
    """Run `serve`, importing it lazily because its dependencies are optional."""
    try:
        from cobalt.cli import serve
    except ImportError as exc:
        log.error(
            "cobalt serve requires optional dependencies (%s is missing). "
            'Install them with: pip install "cobalt-sequence-lab[serve]"',
            exc.name,
        )
        return 1
    return serve.main(argv)


COMMAND_HANDLERS: dict[str, Callable[[Sequence[str] | None], int]] = {
    "inspect": inspect.main,
    "stats": stats.main,
    "normalize": normalize.main,
    "validate": validate.main,
    "help": help.main,
    "serve": _serve_main,
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
    configure_logging(parsed.verbose, parsed.quiet, server=parsed.command == "serve")
    handler = COMMAND_HANDLERS[parsed.command]
    return int(handler(parsed.args))


if __name__ == "__main__":
    raise SystemExit(main())
