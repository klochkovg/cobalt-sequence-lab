"""Logging setup for the cobalt CLI and server.

Library modules only call `logging.getLogger(__name__)`; handlers are installed
once, by the CLI entry point, through `configure_logging`.

Diagnostics (errors, warnings, debug details) go to stderr. Command results
(tables, reports, sequences) are written to stdout or files and are not logged.
"""

from __future__ import annotations

import logging
import os
import sys

from rich.console import Console
from rich.logging import RichHandler

LEVEL_ENV = "COBALT_LOG_LEVEL"
FORMAT_ENV = "COBALT_LOG_FORMAT"
FORMATS = ("auto", "rich", "plain")

# Marks handlers installed by configure_logging, so repeated calls replace them
_HANDLER_NAME = "cobalt"


def resolve_level(verbose: int, quiet: bool, default: int) -> int:
    """Pick the log level: command-line flags, then $COBALT_LOG_LEVEL, then `default`."""
    if quiet:
        return logging.ERROR
    if verbose >= 2:
        return logging.DEBUG
    if verbose == 1:
        return logging.INFO
    env_level = os.environ.get(LEVEL_ENV, "").strip().upper()
    if env_level:
        level = logging.getLevelName(env_level)
        if isinstance(level, int):
            return level
    return default


def resolve_format() -> str:
    """Pick the output format from $COBALT_LOG_FORMAT; `auto` uses rich only on a terminal."""
    fmt = os.environ.get(FORMAT_ENV, "auto").strip().lower()
    if fmt not in FORMATS:
        fmt = "auto"
    if fmt == "auto":
        return "rich" if sys.stderr.isatty() else "plain"
    return fmt


def build_handler(fmt: str, server: bool) -> logging.Handler:
    """Build the stderr handler; server mode adds timestamps and logger names."""
    handler: logging.Handler
    if fmt == "rich":
        handler = RichHandler(
            console=Console(stderr=True),
            show_time=server,
            show_path=False,
            rich_tracebacks=True,
        )
        handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
    else:
        handler = logging.StreamHandler(sys.stderr)
        if server:
            pattern = "%(asctime)s %(levelname)s %(name)s: %(message)s"
        else:
            pattern = "%(levelname)s: %(message)s"
        handler.setFormatter(logging.Formatter(pattern))
    handler.set_name(_HANDLER_NAME)
    return handler


def configure_logging(verbose: int = 0, quiet: bool = False, server: bool = False) -> None:
    """Install the cobalt handler on the root logger.

    Standalone runs default to WARNING, the server defaults to INFO (so request
    logs from uvicorn are visible). Calling it again replaces the previous handler.
    """
    default = logging.INFO if server else logging.WARNING
    root = logging.getLogger()
    for handler in [h for h in root.handlers if h.get_name() == _HANDLER_NAME]:
        root.removeHandler(handler)
    root.addHandler(build_handler(resolve_format(), server))
    root.setLevel(resolve_level(verbose, quiet, default))
