"""Authentication backends of the server, selected with `--auth`."""

from __future__ import annotations

import os
import secrets
from collections.abc import Awaitable, Callable, Collection, Mapping

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from cobalt.server.config import AUTH_MODES
from cobalt.server.users import User, UserStore

__all__ = ["AUTH_MODES", "ApiKeyAuth", "AuthDependency", "build_auth", "parse_api_keys"]

API_KEYS_ENV = "COBALT_API_KEYS"
API_KEY_HEADER = "X-API-Key"

# A FastAPI dependency that raises for a request that isn't authenticated. Otherwise it returns
# the caller's User, or None for a caller without an account (who counts as the default user).
AuthDependency = Callable[..., Awaitable[User | None]]

_api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def parse_api_keys(value: str) -> list[str]:
    """Split a comma-separated list of API keys, dropping blanks."""
    return [key.strip() for key in value.split(",") if key.strip()]


class ApiKeyAuth:
    """Check the X-API-Key header against the users' keys and the shared `keys`.

    A user's key (from `users`) authenticates as that user; a shared key (from
    `$COBALT_API_KEYS`) authenticates without an account. Keys added to `users` while the
    server runs work at once.
    """

    def __init__(self, keys: Collection[str] = (), users: UserStore | None = None) -> None:
        if not keys and users is None:
            raise ValueError("at least one API key or a user store is required")
        self._keys = list(keys)
        self._users = users

    async def __call__(self, api_key: str | None = Security(_api_key_header)) -> User | None:
        if api_key is not None and self._users is not None:
            # Looked up by the key's hash, so the lookup time doesn't depend on the key
            user = self._users.user_for_key(api_key)
            if user is not None:
                return user
        # compare_digest against every key, so timing doesn't reveal which key nearly matched
        matched = False
        if api_key is not None:
            for key in self._keys:
                matched |= secrets.compare_digest(api_key.encode(), key.encode())
        if not matched:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        return None


def build_auth(
    mode: str, users: UserStore | None = None, environ: Mapping[str, str] = os.environ
) -> AuthDependency | None:
    """Build the auth dependency for `mode`; None means no authentication.

    `api-key` needs a user with a key in `users` or shared keys in `$COBALT_API_KEYS`.
    """
    if mode == "none":
        return None
    if mode == "api-key":
        keys = parse_api_keys(environ.get(API_KEYS_ENV, ""))
        if not keys and (users is None or not users.has_keys()):
            raise ValueError(
                "--auth api-key requires API keys: add a user with `cobalt-admin users add "
                f"NAME`, or set shared keys in ${API_KEYS_ENV} (comma-separated)"
            )
        return ApiKeyAuth(keys, users)
    raise ValueError(f"unknown auth mode: {mode!r} (choose from {', '.join(AUTH_MODES)})")
