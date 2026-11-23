"""Minimal HTTP client for the cobalt server API, used by commands in client mode.

Only the standard library is used, so client mode needs no optional dependencies.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

log = logging.getLogger(__name__)

# API prefix of the server (`cobalt-server --api-prefix`, default /api)
API_PREFIX = "/api"
# API key sent to servers started with --auth api-key
API_KEY_ENV = "COBALT_API_KEY"
API_KEY_HEADER = "X-API-Key"
DEFAULT_TIMEOUT = 30.0


class ServerError(Exception):
    """A request to the server failed; the message is ready to log.

    `status` is the HTTP status code, or None if no response came back.
    """

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def api_url(server: str, path: str) -> str:
    """Return the URL of API `path` (starting with "/") on `server`."""
    return f"{server.rstrip('/')}{API_PREFIX}{path}"


def get_json(
    server: str,
    path: str,
    environ: Mapping[str, str] = os.environ,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """GET API `path` on `server` and return the decoded JSON body.

    Sends $COBALT_API_KEY as the API key when it is set. Raises ServerError if the server
    can't be reached, answers with an error status or doesn't answer with JSON.
    """
    url = api_url(server, path)
    headers = {"Accept": "application/json"}
    api_key = environ.get(API_KEY_ENV, "").strip()
    if api_key:
        headers[API_KEY_HEADER] = api_key
    request = urllib.request.Request(url, headers=headers, method="GET")
    log.debug("GET %s", url)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise ServerError(_error_message(exc), exc.code) from None
    except urllib.error.URLError as exc:
        raise ServerError(f"could not reach {server}: {exc.reason}") from None
    except TimeoutError:
        raise ServerError(f"could not reach {server}: timed out") from None
    try:
        return json.loads(body)
    except ValueError:
        raise ServerError(f"{url}: the server didn't answer with JSON") from None


def _error_message(exc: urllib.error.HTTPError) -> str:
    """Describe an error response, with the server's `detail` when it gives one."""
    detail: object = None
    try:
        body = json.loads(exc.read())
        if isinstance(body, dict):
            detail = body.get("detail")
    except (OSError, ValueError):
        pass
    if exc.code == 401:
        hint = f" (set ${API_KEY_ENV} to an API key of the server)"
        return f"server answered 401 Unauthorized: {detail or 'missing or invalid API key'}{hint}"
    if isinstance(detail, str) and detail:
        return f"server answered {exc.code}: {detail}"
    return f"server answered {exc.code} {exc.reason} for {exc.url}"
