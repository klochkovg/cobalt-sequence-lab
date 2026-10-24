import json

import pytest
import uvicorn
from fastapi.testclient import TestClient

from cobalt import __version__
from cobalt.cli import serve
from cobalt.cli.main import main
from cobalt.cli.serve import build_app, build_parser
from cobalt.cli.serve_auth import API_KEYS_ENV, ApiKeyAuth


def test_root():
    client = TestClient(build_app())
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"title": "Cobalt Sequence Lab", "version": __version__}


def test_stats():
    client = TestClient(build_app())
    resp = client.post("/stats", json={"sequence": "ACGT"})
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["length"] == 4


def test_stats_matches_cli_json(capsys):
    resp = TestClient(build_app()).post("/stats", json={"sequence": "MKVLAAGIC"})
    main(["stats", "--input", "MKVLAAGIC", "--json"])
    assert resp.json() == json.loads(capsys.readouterr().out)


PREFLIGHT_HEADERS = {
    "Origin": "http://localhost:5173",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type",
}


def test_cors_disabled_by_default():
    client = TestClient(build_app())
    resp = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" not in resp.headers


def test_cors_any_origin():
    client = TestClient(build_app(cors_origins=[]))
    resp = client.options("/stats", headers=PREFLIGHT_HEADERS)
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "*"


def test_cors_specific_origin():
    client = TestClient(build_app(cors_origins=["http://localhost:5173"]))
    resp = client.options("/stats", headers=PREFLIGHT_HEADERS)
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"

    resp = client.options("/stats", headers={**PREFLIGHT_HEADERS, "Origin": "http://evil.test"})
    assert resp.status_code == 400


def test_parser_cors():
    parser = build_parser()
    assert parser.parse_args([]).cors is None
    assert parser.parse_args(["--cors"]).cors == []
    assert parser.parse_args(["--cors", "http://a", "http://b"]).cors == ["http://a", "http://b"]


def test_parser_auth_defaults():
    args = build_parser().parse_args([])
    assert args.auth == "none"
    assert args.allow_no_auth is False


def test_api_key_auth_guards_processing_endpoints():
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"])))
    body = {"sequence": "ACGT"}

    resp = client.post("/stats", json=body)
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "ApiKey"
    assert client.post("/stats", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/stats", json=body, headers={"X-API-Key": "k1"}).status_code == 200


def test_api_key_auth_leaves_root_public():
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"])))
    assert client.get("/").status_code == 200


@pytest.fixture
def uvicorn_calls(monkeypatch):
    """Record uvicorn.run calls instead of starting a server."""
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.append((app, kwargs)))
    return calls


def test_main_api_key_without_keys_fails(monkeypatch, uvicorn_calls):
    monkeypatch.delenv(API_KEYS_ENV, raising=False)
    assert serve.main(["--auth", "api-key"]) == 1
    assert uvicorn_calls == []


def test_main_refuses_no_auth_on_public_host(uvicorn_calls):
    assert serve.main(["--host", "0.0.0.0"]) == 1
    assert uvicorn_calls == []


def test_main_allow_no_auth_on_public_host(uvicorn_calls):
    assert serve.main(["--host", "0.0.0.0", "--allow-no-auth"]) == 0
    assert len(uvicorn_calls) == 1


def test_main_no_auth_on_loopback(uvicorn_calls):
    assert serve.main(["--host", "localhost"]) == 0
    assert serve.main(["--host", "::1"]) == 0
    assert len(uvicorn_calls) == 2


def test_main_api_key(monkeypatch, uvicorn_calls):
    monkeypatch.setenv(API_KEYS_ENV, "k1")
    assert serve.main(["--host", "0.0.0.0", "--auth", "api-key"]) == 0
    ((app, kwargs),) = uvicorn_calls
    assert kwargs["host"] == "0.0.0.0"
    client = TestClient(app)
    assert client.post("/stats", json={"sequence": "ACGT"}).status_code == 401
    resp = client.post("/stats", json={"sequence": "ACGT"}, headers={"X-API-Key": "k1"})
    assert resp.status_code == 200
