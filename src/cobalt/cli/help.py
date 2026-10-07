"""CLI command: help."""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence

COMMAND_DESCRIPTIONS: dict[str, str] = {
    "inspect": "Summarize a FASTA/GenBank file: record count, lengths, types, warnings",
    "stats": "Emit a per-record stats table (CSV or JSON) for a file or a raw sequence",
    "validate": "Check records for problems (empty sequences, duplicate IDs, invalid chars)",
    "normalize": "Write cleaned (uppercased) records as FASTA and/or GenBank",
    "serve": "Run the REST API server (needs the optional 'serve' dependencies)",
    "help": "Show this message, or detailed help for a command",
}


def build_parser() -> argparse.ArgumentParser:
    """Build parser for help command."""
    parser = argparse.ArgumentParser(prog="cobalt help")
    parser.add_argument(
        "command",
        nargs="?",
        choices=sorted(COMMAND_DESCRIPTIONS),
        help="Command to show detailed help for",
    )
    return parser


def print_overview() -> None:
    """Print the list of available commands with short descriptions."""
    print("usage: cobalt <command> [args...]")
    print()
    print("Available commands:")
    width = max(len(name) for name in COMMAND_DESCRIPTIONS)
    for name, description in COMMAND_DESCRIPTIONS.items():
        print(f"  {name:<{width}}  {description}")
    print()
    print("Run 'cobalt help <command>' or 'cobalt <command> --help' for command options.")


def print_command_help(command: str) -> int:
    """Print the full argparse help of `command`."""
    try:
        module = importlib.import_module(f"cobalt.cli.{command}")
    except ImportError as exc:
        print(
            f"cobalt {command} requires optional dependencies ({exc.name} is missing).\n"
            'Install them with: pip install "cobalt-sequence-lab[serve]"',
            file=sys.stderr,
        )
        return 1
    module.build_parser().print_help()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the help command."""
    args = build_parser().parse_args(argv)
    if args.command:
        return print_command_help(args.command)
    print_overview()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
