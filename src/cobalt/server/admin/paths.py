"""`cobalt-admin paths`: show where the server keeps its config and files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cobalt.server.config import HOME_ENV, RUNS_DIRNAME, ServerConfig
from cobalt.server.users import users_db_path


def add_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the `paths` command."""
    parser = commands.add_parser(
        "paths",
        help="Show the config file, storage and user store locations",
        description=f"Show the files the server uses; set the home with --home or ${HOME_ENV}",
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, config: ServerConfig, config_path: Path) -> int:
    """Print one `name: path` line per location."""
    locations = {
        "config": config_path.absolute(),
        "storage_dir": config.storage_dir.absolute(),
        "users_db": users_db_path(config).absolute(),
        "runs_dir": (config.storage_dir / RUNS_DIRNAME).absolute(),
    }
    sys.stdout.write("".join(f"{name}: {path}\n" for name, path in locations.items()))
    return 0
