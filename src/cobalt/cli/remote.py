"""Choice between local and client mode: run a command here or on a cobalt server."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping, Sequence
from urllib.parse import urlsplit

log = logging.getLogger(__name__)

SERVER_ENV = "COBALT_SERVER"

# Commands that always run in this process, whatever --server or $COBALT_SERVER say
LOCAL_COMMANDS = frozenset({"serve", "help", "pipeline"})

CommandHandler = Callable[[Sequence[str] | None], int]


def resolve_server(
    server: str | None, local: bool, environ: Mapping[str, str] = os.environ
) -> str | None:
    """Pick the server URL: --local, then --server, then $COBALT_SERVER. None means local mode.

    Raises ValueError if the URL isn't an http(s) URL with a host.
    """
    if local:
        return None
    source = "--server"
    if server is None:
        server = environ.get(SERVER_ENV, "").strip() or None
        source = f"${SERVER_ENV}"
    if server is None:
        return None
    parts = urlsplit(server)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"{source}: expected an http:// or https:// URL, got {server!r}")
    return server.rstrip("/")


def run_remote(server: str, command: str, argv: Sequence[str], local: CommandHandler) -> int:
    """Run `command` on the cobalt server at `server`.

    Client mode is not implemented yet: the command runs locally through `local`.
    """
    log.warning(
        "client mode is not implemented yet: running %s locally instead of on %s", command, server
    )
    return local(argv)
