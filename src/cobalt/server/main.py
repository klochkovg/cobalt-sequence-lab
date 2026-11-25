"""Entry point of the cobalt server (`cobalt-server`): flags, config file and startup checks.

Without a command it serves the API; `cobalt-server users ...` manages the user store instead.
This module imports the optional server dependencies (fastapi, uvicorn) only inside `main`, so
a missing `server` extra gives an error message instead of a traceback.
"""

from __future__ import annotations

import argparse
import ipaddress
import logging
from collections.abc import Sequence
from pathlib import Path

from cobalt import __version__
from cobalt.logging_config import configure_logging
from cobalt.server.config import (
    AUTH_MODES,
    DEFAULT_API_PREFIX,
    DEFAULT_HOST,
    DEFAULT_MAX_UPLOAD_MB,
    DEFAULT_PORT,
    SERVER_DIR,
    ServerConfig,
    ServerConfigError,
    default_config_path,
    load_server_config,
    normalize_api_prefix,
    save_server_config,
)
from cobalt.server.users import USERS_DB_FILENAME, UserStore, UserStoreError
from cobalt.server.users_cli import add_users_parser, run_users

log = logging.getLogger(__name__)

# Directory of run manifests under the storage directory
RUNS_DIRNAME = "runs"


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the `cobalt-server` command.

    Server flags default to None, meaning "not given": the config file (or its defaults) then
    provides the value. Given flags override the file.
    """
    parser = argparse.ArgumentParser(
        prog="cobalt-server", description="Run the Cobalt Sequence Lab REST API server"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Show more diagnostics on stderr (-v also shows debug details)",
    )
    verbosity.add_argument(
        "-q", "--quiet", action="store_true", help="Show only errors on stderr (no access logs)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        help=f"Server config file (default: ./{SERVER_DIR}/cobalt-config.yaml, created if missing)",
    )
    parser.add_argument("--host", help=f"Host to bind to (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, help=f"Port to bind to (default: {DEFAULT_PORT})")
    parser.add_argument(
        "--cors",
        nargs="*",
        metavar="ORIGIN",
        help="Enable CORS (for UI development). Without origins, any origin is allowed",
    )
    parser.add_argument(
        "--auth",
        choices=AUTH_MODES,
        help="Authentication for processing endpoints (default: none; "
        "api-key reads keys from $COBALT_API_KEYS)",
    )
    parser.add_argument(
        "--allow-no-auth",
        action="store_true",
        default=None,
        help="Allow --auth none on a non-loopback host (auth handled by a gateway or mesh)",
    )
    parser.add_argument(
        "--api-prefix",
        metavar="PREFIX",
        help=f'Path prefix of every endpoint (default: {DEFAULT_API_PREFIX}; "" for none)',
    )
    parser.add_argument(
        "--max-upload-mb",
        type=_non_negative_int,
        metavar="N",
        help=f"Request body size limit in MiB (default: {DEFAULT_MAX_UPLOAD_MB}; 0 for no limit)",
    )
    parser.add_argument(
        "--ui-dist",
        type=Path,
        metavar="PATH",
        help="Serve the built UI (its dist/ folder) at / alongside the API",
    )
    parser.add_argument(
        "--storage-dir",
        type=Path,
        metavar="PATH",
        help="Server file storage (default: the config file's directory)",
    )
    # No command: serve the API
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    add_users_parser(commands)
    return parser


def _non_negative_int(value: str) -> int:
    """argparse type: an integer >= 0."""
    try:
        number = int(value)
    except ValueError:
        number = -1
    if number < 0:
        raise argparse.ArgumentTypeError(f"expected an integer >= 0, got {value!r}")
    return number


def _is_loopback(host: str) -> bool:
    """Return True when `host` only accepts connections from this machine."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def load_config(args: argparse.Namespace) -> ServerConfig:
    """Read the server config named by `args.config` (or the default one) and apply the flags.

    A missing default config file is created with default values; a missing file given with
    --config is an error. Raises ServerConfigError.
    """
    path = args.config if args.config is not None else default_config_path()
    if args.config is None and not path.exists():
        try:
            save_server_config(ServerConfig(), path)
        except OSError as exc:
            raise ServerConfigError(f"could not create {path}: {exc}") from None
        log.info("created default server config %s", path)
    config = load_server_config(path).resolve_paths(path.parent)
    log.info("server config: %s", path)
    return config.with_overrides(
        host=args.host,
        port=args.port,
        cors=args.cors,
        auth=args.auth,
        allow_no_auth=args.allow_no_auth,
        api_prefix=args.api_prefix,
        max_upload_mb=args.max_upload_mb,
        ui_dist=args.ui_dist,
        storage_dir=args.storage_dir,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the `cobalt-server` command."""
    args = build_parser().parse_args(argv)
    # The server logs at INFO by default, so -v goes straight to DEBUG
    configure_logging(args.verbose + 1 if args.verbose else 0, args.quiet, server=True)
    if args.command == "users":
        # Needs no server dependencies: handled before importing them
        try:
            return run_users(args, load_config(args))
        except ServerConfigError as exc:
            log.error("%s", exc)
            return 1
    try:
        import uvicorn

        from cobalt.server.app import build_app
        from cobalt.server.auth import build_auth
        from cobalt.server.registry import RunRegistry
    except ImportError as exc:
        log.error(
            "cobalt-server requires optional dependencies (%s is missing). "
            'Install them with: pip install "cobalt-sequence-lab[server]"',
            exc.name,
        )
        return 1

    try:
        config = load_config(args)
    except ServerConfigError as exc:
        log.error("%s", exc)
        return 1
    try:
        config.storage_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.error("could not create storage directory %s: %s", config.storage_dir, exc)
        return 1
    log.info("storage directory: %s", config.storage_dir)
    runs = RunRegistry(config.storage_dir / RUNS_DIRNAME)
    try:
        loaded = runs.load()
    except OSError as exc:
        log.error("could not read runs directory %s: %s", runs.runs_dir, exc)
        return 1
    log.info("runs loaded: %d", loaded)
    try:
        users = UserStore(config.storage_dir / USERS_DB_FILENAME)
    except UserStoreError as exc:
        log.error("%s", exc)
        return 1
    log.info("users: %d", len(users))

    try:
        auth = build_auth(config.auth, users)
    except ValueError as exc:
        log.error("%s", exc)
        return 1
    if auth is None and not _is_loopback(config.host) and not config.allow_no_auth:
        log.error(
            "refusing to serve %s without authentication: use --auth api-key, or "
            "--allow-no-auth if a gateway or service mesh handles authentication",
            config.host,
        )
        return 1
    api_prefix = normalize_api_prefix(config.api_prefix)
    if config.ui_dist is not None:
        if not api_prefix:
            log.error('--ui-dist needs an API prefix: drop --api-prefix "" or set another one')
            return 1
        if not (config.ui_dist / "index.html").is_file():
            log.error(
                "--ui-dist %s: no index.html found (expected the UI's dist/ folder)",
                config.ui_dist,
            )
            return 1
    log.info("authentication: %s", config.auth)
    log.info("API prefix: %s", api_prefix or "(none)")

    app = build_app(
        cors_origins=config.cors,
        auth=auth,
        api_prefix=api_prefix,
        max_upload_mb=config.max_upload_mb,
        ui_dist=config.ui_dist,
        runs=runs,
        users=users,
    )
    # log_config=None: uvicorn's loggers propagate to the handler set up by
    # cobalt.logging_config instead of installing uvicorn's own
    uvicorn.run(app, host=config.host, port=config.port, log_config=None)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
