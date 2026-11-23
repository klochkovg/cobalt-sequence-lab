"""ASGI middleware and the static UI app of the server."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger(__name__)

BYTES_PER_MB = 1024 * 1024


class InternalErrorMiddleware:
    """Answer an unhandled exception with a JSON 500 and log the traceback.

    Added before `CORSMiddleware`, so it runs inside it and the 500 gets CORS headers
    (Starlette's own `Exception` handler runs outside every middleware).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            log.exception("unhandled error on %s %s", scope["method"], scope["path"])
            if started:
                raise
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )
            await response(scope, receive, send)


class BodySizeLimitMiddleware:
    """Answer 413 to a request body over `max_bytes`.

    A `Content-Length` over the limit is refused before the body is read; a chunked body is
    counted as it is read, and the endpoint's body parsing fails with 413 at the limit.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.detail = f"upload too large: limit is {max_bytes / BYTES_PER_MB:g} MB"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = Headers(scope=scope).get("content-length")
        if length is not None and length.isdigit() and int(length) > self.max_bytes:
            log.info("%s %s: %s", scope["method"], scope["path"], self.detail)
            response = JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE, content={"detail": self.detail}
            )
            await response(scope, receive, send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    log.info("%s %s: %s", scope["method"], scope["path"], self.detail)
                    # FastAPI re-raises an HTTPException from body parsing as is
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=self.detail
                    )
            return message

        await self.app(scope, limited_receive, send)


class UIStaticFiles(StaticFiles):
    """The built UI: static files, with `index.html` for other HTML requests (client routes).

    Paths under the API prefix are never answered from here.
    """

    def __init__(self, directory: Path, api_prefix: str) -> None:
        super().__init__(directory=directory, html=True)
        self.api_prefix = api_prefix

    def _is_api_path(self, path: str) -> bool:
        return path == self.api_prefix or path.startswith(f"{self.api_prefix}/")

    async def get_response(self, path: str, scope: Scope) -> Response:
        if self._is_api_path(scope["path"]):
            raise StarletteHTTPException(status_code=status.HTTP_404_NOT_FOUND)
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            accepts_html = "text/html" in Headers(scope=scope).get("accept", "")
            if exc.status_code != status.HTTP_404_NOT_FOUND or not accepts_html:
                raise
            return await super().get_response("index.html", scope)
