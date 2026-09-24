"""Top-level CLI dispatcher for cobalt."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from cobalt import __version__
from cobalt.cli import help, inspect, normalize, stats, validate


def _serve_main(argv: Sequence[str] | None) -> int:
    """Run `serve`, importing it lazily because its dependencies are optional."""
    try:
        from cobalt.cli import serve
    except ImportError as exc:
        print(
            f"cobalt serve requires optional dependencies ({exc.name} is missing).\n"
            'Install them with: pip install "cobalt-sequence-lab[serve]"',
            file=sys.stderr,
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
    handler = COMMAND_HANDLERS[parsed.command]
    return int(handler(parsed.args))


if __name__ == "__main__":
    raise SystemExit(main())
