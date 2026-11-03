import gzip
import json
from pathlib import Path

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


DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


def post_inspect(client, path, filename=None, content=None, **form):
    """POST `path` (or `content`) to /inspect as a multipart upload with form fields."""
    body = content if content is not None else path.read_bytes()
    files = {"file": (filename or path.name, body)}
    return client.post("/inspect", files=files, data={k: str(v) for k, v in form.items()})


@pytest.mark.parametrize(
    ("name", "fmt", "records_num"),
    [
        ("ls_orchid.fasta", "fasta", 94),
        ("ls_orchid.gbk", "genbank", 94),
        ("sample.fastq", "fastq", 4),
    ],
)
def test_inspect_upload_formats(name, fmt, records_num):
    resp = post_inspect(TestClient(build_app()), DATA_DIR / name)
    assert resp.status_code == 200
    body = resp.json()
    assert body["file"] == name
    assert body["format"] == fmt
    assert body["compression"] is None
    assert body["records_num"] == records_num
    assert len(body["records"]) == records_num


def test_inspect_upload_gzip():
    content = gzip.compress((DATA_DIR / "ls_orchid.gbk").read_bytes())
    resp = post_inspect(
        TestClient(build_app()), DATA_DIR / "ls_orchid.gbk", "orchid.gbk.gz", content
    )
    assert resp.status_code == 200
    assert (resp.json()["format"], resp.json()["compression"]) == ("genbank", "gzip")


def test_inspect_overview_only_and_limit():
    client = TestClient(build_app())
    path = DATA_DIR / "ls_orchid.fasta"
    overview = post_inspect(client, path, overview_only="true").json()
    limited = post_inspect(client, path, output_seq_number=2).json()

    assert overview["records_num"] == 94
    assert overview["records"] == []
    assert [r["id"] for r in limited["records"]] == [
        "gi|2765658|emb|Z78533.1|CIZ78533",
        "gi|2765657|emb|Z78532.1|CCZ78532",
    ]


def test_inspect_rejects_negative_limit():
    resp = post_inspect(TestClient(build_app()), DATA_DIR / "ls_orchid.fasta", output_seq_number=-1)
    assert resp.status_code == 422


def test_inspect_unrecognized_file():
    resp = post_inspect(TestClient(build_app()), DATA_DIR / "text_input.txt")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail.startswith("text_input.txt: unrecognized format")
    assert "cobalt-" not in detail


def test_inspect_empty_upload():
    resp = post_inspect(TestClient(build_app()), DATA_DIR / "x.fasta", "empty.fasta", b"")
    assert resp.status_code == 200
    assert resp.json()["records_num"] == 0
    assert resp.json()["format"] is None


def test_inspect_requires_file():
    assert (
        TestClient(build_app()).post("/inspect", data={"overview_only": "true"}).status_code == 422
    )


@pytest.mark.parametrize(
    "args",
    [[], ["--overview-only"], ["--output-seq-number", "3"]],
)
@pytest.mark.parametrize("name", ["ls_orchid.gbk", "sample.fastq"])
def test_inspect_matches_cli_json(capsys, name, args):
    path = DATA_DIR / name
    form = {}
    if "--overview-only" in args:
        form["overview_only"] = "true"
    if "--output-seq-number" in args:
        form["output_seq_number"] = args[-1]
    resp = post_inspect(TestClient(build_app()), path, filename=str(path), **form)
    main(["inspect", "--json", *args, str(path)])
    assert resp.json() == json.loads(capsys.readouterr().out)


def test_api_key_auth_guards_inspect():
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"])))
    path = DATA_DIR / "ls_orchid.fasta"
    files = {"file": (path.name, path.read_bytes())}
    assert client.post("/inspect", files=files).status_code == 401
    resp = client.post("/inspect", files=files, headers={"X-API-Key": "k1"})
    assert resp.status_code == 200


def post_validate(client, path, filename=None, content=None):
    """POST `path` (or `content`) to /validate as a multipart upload."""
    body = content if content is not None else path.read_bytes()
    return client.post("/validate", files={"file": (filename or path.name, body)})


@pytest.mark.parametrize(
    ("name", "fmt", "records_num"),
    [
        ("ls_orchid.fasta", "fasta", 94),
        ("ls_orchid.gbk", "genbank", 94),
        ("sample.fastq", "fastq", 4),
    ],
)
def test_validate_upload_formats(name, fmt, records_num):
    resp = post_validate(TestClient(build_app()), DATA_DIR / name)
    assert resp.status_code == 200
    body = resp.json()
    assert body["file"] == name
    assert body["format"] == fmt
    assert body["compression"] is None
    assert body["records_num"] == records_num
    assert body["passed"] is True


def test_validate_upload_gzip():
    content = gzip.compress((DATA_DIR / "ls_orchid.fasta").read_bytes())
    resp = post_validate(TestClient(build_app()), DATA_DIR / "x", "orchid.fasta.gz", content)
    assert resp.status_code == 200
    assert (resp.json()["format"], resp.json()["compression"]) == ("fasta", "gzip")


def test_validate_upload_with_warnings():
    content = b">s1\nACGT\n>s1\nAC!T\n"
    resp = post_validate(TestClient(build_app()), DATA_DIR / "x", "bad.fasta", content)
    body = resp.json()
    assert body["passed"] is False
    assert body["warning_counts"]["duplicate_id"] == 1
    assert body["warning_counts"]["invalid_characters"] == 1
    assert {w["kind"] for w in body["warnings"]} == {"duplicate_id", "invalid_characters"}


def test_validate_unrecognized_file():
    resp = post_validate(TestClient(build_app()), DATA_DIR / "text_input.txt")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail.startswith("text_input.txt: unrecognized format")
    assert "cobalt-" not in detail


def test_validate_empty_upload():
    resp = post_validate(TestClient(build_app()), DATA_DIR / "x", "empty.fasta", b"")
    assert resp.status_code == 200
    assert (resp.json()["records_num"], resp.json()["passed"]) == (0, True)


def test_validate_requires_file():
    assert TestClient(build_app()).post("/validate").status_code == 422


@pytest.mark.parametrize(
    "content",
    [
        (DATA_DIR / "ls_orchid.gbk").read_bytes(),
        (DATA_DIR / "sample.fastq").read_bytes(),
        b">s1\nACGT\n>s1\nAC!T\n",  # duplicate ID and invalid characters
    ],
    ids=["genbank", "fastq", "warnings"],
)
def test_validate_matches_cli_json(capsys, tmp_path, content):
    path = tmp_path / "input"
    path.write_bytes(content)
    resp = post_validate(TestClient(build_app()), path, filename=str(path))
    main(["validate", "--json", str(path)])
    assert resp.json() == json.loads(capsys.readouterr().out)


def test_api_key_auth_guards_validate():
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"])))
    path = DATA_DIR / "ls_orchid.fasta"
    files = {"file": (path.name, path.read_bytes())}
    assert client.post("/validate", files=files).status_code == 401
    resp = client.post("/validate", files=files, headers={"X-API-Key": "k1"})
    assert resp.status_code == 200


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


STUB_REQUESTS = [
    ("post", "/foldrna", {"sequence": "GGGAAAUCC"}, "foldrna"),
    ("post", "/run", {"pipeline": "name: demo"}, "run"),
    ("get", "/runs", None, "runs list"),
    ("get", "/runs/r1", None, "runs show"),
]


@pytest.mark.parametrize(("method", "path", "body", "command"), STUB_REQUESTS)
def test_stub_endpoints_not_implemented(method, path, body, command):
    client = TestClient(build_app())
    resp = client.request(method, path, json=body)
    assert resp.status_code == 501
    assert resp.json() == {"detail": f"cobalt {command} is not implemented yet"}


def test_foldrna_validates_body():
    client = TestClient(build_app())
    assert client.post("/foldrna", json={}).status_code == 422


@pytest.mark.parametrize(("method", "path", "body", "command"), STUB_REQUESTS)
def test_api_key_auth_guards_stub_endpoints(method, path, body, command):
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"])))
    assert client.request(method, path, json=body).status_code == 401
    resp = client.request(method, path, json=body, headers={"X-API-Key": "k1"})
    assert resp.status_code == 501


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
