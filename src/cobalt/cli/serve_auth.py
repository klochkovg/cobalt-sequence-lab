"""Authentication backends for the serve command, selected with `--auth`."""

from __future__ import annotations

import os
import secrets
from collections.abc import Awaitable, Callable, Collection, Mapping

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEYS_ENV = "COBALT_API_KEYS"
API_KEY_HEADER = "X-API-Key"
AUTH_MODES = ("none", "api-key")

# A FastAPI dependency that returns normally for an authenticated request and raises otherwise
AuthDependency = Callable[..., Awaitable[None]]

_api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def parse_api_keys(value: str) -> list[str]:
    """Split a comma-separated list of API keys, dropping blanks."""
    return [key.strip() for key in value.split(",") if key.strip()]


class ApiKeyAuth:
    """Check the X-API-Key header against the configured keys."""

    def __init__(self, keys: Collection[str]) -> None:
        if not keys:
            raise ValueError("at least one API key is required")
        self._keys = list(keys)

    async def __call__(self, api_key: str | None = Security(_api_key_header)) -> None:
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


def build_auth(mode: str, environ: Mapping[str, str] = os.environ) -> AuthDependency | None:
    """Build the auth dependency for `mode`; None means no authentication."""
    if mode == "none":
        return None
    if mode == "api-key":
        keys = parse_api_keys(environ.get(API_KEYS_ENV, ""))
        if not keys:
            raise ValueError(f"--auth api-key requires keys in ${API_KEYS_ENV} (comma-separated)")
        return ApiKeyAuth(keys)
    raise ValueError(f"unknown auth mode: {mode!r} (choose from {', '.join(AUTH_MODES)})")
