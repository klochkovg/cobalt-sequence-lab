import json

from fastapi.testclient import TestClient

from cobalt import __version__
from cobalt.cli.main import main
from cobalt.cli.serve import build_app, build_parser


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
