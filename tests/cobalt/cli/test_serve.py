from fastapi.testclient import TestClient

from cobalt import __version__
from cobalt.cli.serve import build_app


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
