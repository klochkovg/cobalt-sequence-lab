import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cobalt.cli.client import API_KEY_ENV, ServerError, api_url, get_json


class FakeServer:
    """A local HTTP server answering every GET with `status` and `body`; records requests."""

    def __init__(self):
        self.status = 200
        self.body = b"{}"
        self.requests = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                server.requests.append((self.path, {k.lower(): v for k, v in self.headers.items()}))
                self.send_response(server.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(server.body)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def answer(self, status, body):
        self.status = status
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()


@pytest.fixture
def fake_server():
    server = FakeServer()
    yield server
    server.httpd.shutdown()
    server.httpd.server_close()


def test_api_url():
    assert api_url("http://lab-a:8000", "/runs") == "http://lab-a:8000/api/runs"
    assert api_url("http://lab-a:8000/", "/runs") == "http://lab-a:8000/api/runs"


def test_get_json(fake_server):
    fake_server.answer(200, [{"run_id": "r1"}])
    assert get_json(fake_server.url, "/runs", environ={}) == [{"run_id": "r1"}]
    ((path, headers),) = fake_server.requests
    assert path == "/api/runs"
    assert "x-api-key" not in headers


def test_get_json_sends_api_key(fake_server):
    get_json(fake_server.url, "/runs", environ={API_KEY_ENV: " k1 "})
    ((_, headers),) = fake_server.requests
    assert headers["x-api-key"] == "k1"


def test_get_json_error_detail(fake_server):
    fake_server.answer(404, {"detail": "run not found: r9"})
    with pytest.raises(ServerError, match="server answered 404: run not found: r9") as info:
        get_json(fake_server.url, "/runs/r9", environ={})
    assert info.value.status == 404


def test_get_json_unauthorized_hint(fake_server):
    fake_server.answer(401, {"detail": "Missing or invalid API key"})
    with pytest.raises(ServerError, match=f"401 Unauthorized.*\\${API_KEY_ENV}"):
        get_json(fake_server.url, "/runs", environ={})


def test_get_json_error_without_detail(fake_server):
    fake_server.answer(502, b"bad gateway")
    with pytest.raises(ServerError, match="server answered 502"):
        get_json(fake_server.url, "/runs", environ={})


def test_get_json_not_json(fake_server):
    fake_server.answer(200, b"<html>")
    with pytest.raises(ServerError, match="didn't answer with JSON"):
        get_json(fake_server.url, "/runs", environ={})


def test_get_json_unreachable(fake_server):
    url = fake_server.url
    fake_server.httpd.shutdown()
    fake_server.httpd.server_close()
    with pytest.raises(ServerError, match=f"could not reach {url}") as info:
        get_json(url, "/runs", environ={}, timeout=2)
    assert info.value.status is None
