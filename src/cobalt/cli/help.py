"""CLI command: help."""


import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build parser for help command."""
    parser = argparse.ArgumentParser(prog="cobalt help")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the help command.
    """
    args = build_parser().parse_args(argv)
    print(f"[stub] help")
    print(f"Available commands: inspect, stats, normalize, validate, help")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
