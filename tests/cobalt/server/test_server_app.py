import bz2
import gzip
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cobalt import __version__
from cobalt.cli.main import main
from cobalt.core.pipeline import RunStatus, load_pipeline
from cobalt.server import app as app_module
from cobalt.server.app import build_app
from cobalt.server.auth import ApiKeyAuth
from cobalt.server.config import normalize_api_prefix
from cobalt.server.registry import RunRegistry
from cobalt.server.uploads import normalized_filename
from cobalt.server.users import UserStore

VERSION_BODY = {"title": "Cobalt Sequence Lab", "version": __version__}


@pytest.mark.parametrize("path", ["/api", "/api/"])
def test_root(path):
    client = TestClient(build_app())
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.json() == VERSION_BODY


def test_health():
    resp = TestClient(build_app(auth=ApiKeyAuth(["k1"]))).get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        ("/api", "/api"),
        ("/api/", "/api"),
        ("api", "/api"),
        ("/v2/api/", "/v2/api"),
        ("", ""),
        ("/", ""),
    ],
)
def test_normalize_api_prefix(prefix, expected):
    assert normalize_api_prefix(prefix) == expected


@pytest.mark.parametrize("path", ["/", "/inspect", "/stats", "/openapi.json", "/docs"])
def test_paths_outside_prefix_not_found(path):
    client = TestClient(build_app())
    resp = client.post(path) if path in ("/inspect", "/stats") else client.get(path)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}


def test_empty_prefix_keeps_old_paths():
    client = TestClient(build_app(api_prefix=""))
    assert client.get("/").json() == VERSION_BODY
    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/stats", data={"sequence": "ACGT"}).status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.post("/api/stats", data={"sequence": "ACGT"}).status_code == 404


def test_custom_prefix():
    client = TestClient(build_app(api_prefix="/v2/"))
    assert client.get("/v2").json() == VERSION_BODY
    assert client.post("/v2/stats", data={"sequence": "ACGT"}).status_code == 200
    assert client.post("/api/stats", data={"sequence": "ACGT"}).status_code == 404


def test_openapi_lists_prefixed_paths():
    client = TestClient(build_app())
    schema = client.get("/api/openapi.json").json()
    assert schema["info"]["version"] == __version__
    expected = {
        "/api/",
        "/api/health",
        "/api/me",
        "/api/inspect",
        "/api/validate",
        "/api/stats",
        "/api/normalize",
        "/api/foldrna",
        "/api/run",
        "/api/runs",
        "/api/runs/{run_id}",
    }
    assert set(schema["paths"]) == expected
    assert client.get("/api/docs").status_code == 200


DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


def upload(path, filename=None, content=None):
    """Return a multipart `file` entry for `path` (or `content`)."""
    body = content if content is not None else path.read_bytes()
    return ("file", (filename or path.name, body))


def test_stats_sequence():
    resp = TestClient(build_app()).post("/api/stats", data={"sequence": "ACGT"})
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["length"] == 4
    assert body[0]["source_file"] is None


def test_stats_sequence_matches_cli_json(capsys):
    resp = TestClient(build_app()).post("/api/stats", data={"sequence": "MKVLAAGIC"})
    main(["stats", "--input", "MKVLAAGIC", "--json"])
    assert resp.json() == json.loads(capsys.readouterr().out)


def test_stats_uploads():
    files = [upload(DATA_DIR / "sample.fastq"), upload(DATA_DIR / "ls_orchid.gbk")]
    resp = TestClient(build_app()).post("/api/stats", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 4 + 94
    assert {row["source_file"] for row in body} == {"sample.fastq", "ls_orchid.gbk"}
    assert body[0]["mean_quality"] is not None


def test_stats_upload_gzip():
    content = gzip.compress((DATA_DIR / "ls_orchid.fasta").read_bytes())
    files = [upload(DATA_DIR / "x", "orchid.fasta.gz", content)]
    resp = TestClient(build_app()).post("/api/stats", files=files)
    assert resp.status_code == 200
    assert len(resp.json()) == 94


@pytest.mark.parametrize(
    "args",
    [[], ["--sort", "length"], ["--sort", "mean_quality", "--desc"]],
)
def test_stats_uploads_match_cli_json(capsys, args):
    paths = [DATA_DIR / "sample.fastq", DATA_DIR / "ls_orchid.fasta"]
    form = {}
    if "--sort" in args:
        form["sort"] = args[1]
    if "--desc" in args:
        form["desc"] = "true"
    files = [upload(path, str(path)) for path in paths]
    resp = TestClient(build_app()).post("/api/stats", files=files, data=form)
    main(["stats", "--json", *args, *map(str, paths)])
    assert resp.json() == json.loads(capsys.readouterr().out)


def test_stats_empty_upload():
    files = [upload(DATA_DIR / "x", "empty.fasta", b"")]
    resp = TestClient(build_app()).post("/api/stats", files=files)
    assert resp.status_code == 200
    assert resp.json() == []


def test_stats_unrecognized_upload_fails_request():
    files = [upload(DATA_DIR / "ls_orchid.fasta"), upload(DATA_DIR / "text_input.txt")]
    resp = TestClient(build_app()).post("/api/stats", files=files)
    assert resp.status_code == 422
    assert resp.json()["detail"].startswith("text_input.txt: unrecognized format")


@pytest.mark.parametrize("form", [{}, {"sequence": ""}, {"sequence": "  \n\t "}])
def test_stats_neither_source(form):
    resp = TestClient(build_app()).post("/api/stats", data=form)
    assert resp.status_code == 422
    assert resp.json() == {
        "detail": [
            {
                "type": "missing",
                "loc": ["body", "file"],
                "msg": "give one or more files or a sequence",
                "input": None,
            }
        ]
    }


def test_stats_both_sources():
    files = [upload(DATA_DIR / "ls_orchid.fasta")]
    resp = TestClient(build_app()).post("/api/stats", files=files, data={"sequence": "ACGT"})
    assert resp.status_code == 422
    assert resp.json() == {
        "detail": [
            {
                "type": "value_error",
                "loc": ["body", "sequence"],
                "msg": "give either files or a sequence, not both",
                "input": "ACGT",
            }
        ]
    }


def test_stats_sequence_whitespace_removed():
    resp = TestClient(build_app()).post("/api/stats", data={"sequence": "AC GT\nAA"})
    assert resp.status_code == 200
    assert resp.json()[0]["length"] == 6


def test_stats_rejects_unknown_sort():
    resp = TestClient(build_app()).post("/api/stats", data={"sequence": "ACGT", "sort": "bogus"})
    assert resp.status_code == 422


def post_inspect(client, path, filename=None, content=None, **form):
    """POST `path` (or `content`) to /inspect as a multipart upload with form fields."""
    body = content if content is not None else path.read_bytes()
    files = {"file": (filename or path.name, body)}
    return client.post("/api/inspect", files=files, data={k: str(v) for k, v in form.items()})


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


def test_inspect_offset_pages_records():
    content = b"".join(f">s{i}\nACGT\n".encode() for i in range(1, 11))
    client = TestClient(build_app())
    body = post_inspect(
        client, DATA_DIR / "x", "ten.fasta", content, offset=2, output_seq_number=3
    ).json()
    assert [r["id"] for r in body["records"]] == ["s3", "s4", "s5"]
    assert body["records_offset"] == 2
    assert body["records_num"] == 10


def test_inspect_offset_past_end():
    body = post_inspect(TestClient(build_app()), DATA_DIR / "ls_orchid.fasta", offset=1000).json()
    assert body["records"] == []
    assert body["records_offset"] == 1000
    assert body["records_num"] == 94


def test_inspect_offset_with_overview_only():
    path = DATA_DIR / "ls_orchid.fasta"
    body = post_inspect(TestClient(build_app()), path, offset=1, overview_only="true").json()
    assert body["records"] == []


def test_inspect_without_sequences():
    path = DATA_DIR / "ls_orchid.fasta"
    body = post_inspect(TestClient(build_app()), path, include_sequence="false").json()
    record = body["records"][0]
    assert record["sequence"] is None
    assert record["length"] == 740
    assert record["gc_fraction"] is not None


def test_inspect_defaults_keep_sequences_and_all_warnings():
    content = b">s1\nAC!T\n>s1\nACGT\n>s3\n\n"
    body = post_inspect(TestClient(build_app()), DATA_DIR / "x", "w.fasta", content).json()
    assert body["records"][0]["sequence"] == "AC!T"
    assert len(body["warnings"]) == 3
    assert (body["records_offset"], body["warnings_truncated"]) == (0, False)


def test_inspect_max_warnings():
    content = b">s1\nAC!T\n>s1\nACGT\n>s3\n\n"
    client = TestClient(build_app())
    body = post_inspect(client, DATA_DIR / "x", "w.fasta", content, max_warnings=1).json()
    assert len(body["warnings"]) == 1
    assert body["warnings_truncated"] is True
    assert sum(body["warning_counts"].values()) == 3


@pytest.mark.parametrize("field", ["offset", "max_warnings"])
def test_inspect_rejects_negative_paging_fields(field):
    path = DATA_DIR / "ls_orchid.fasta"
    assert post_inspect(TestClient(build_app()), path, **{field: -1}).status_code == 422


def test_inspect_invalid_characters_details():
    content = b">seq7\nAC!G1!\n"
    body = post_inspect(TestClient(build_app()), DATA_DIR / "x", "s.fasta", content).json()
    (warning,) = body["warnings"]
    assert warning["kind"] == "invalid_characters"
    assert warning["details"] == {
        "characters": ["!", "1"],
        "count": 3,
        "first_positions": [3, 5, 6],
    }


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
        TestClient(build_app()).post("/api/inspect", data={"overview_only": "true"}).status_code
        == 422
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
    assert client.post("/api/inspect", files=files).status_code == 401
    resp = client.post("/api/inspect", files=files, headers={"X-API-Key": "k1"})
    assert resp.status_code == 200


def post_validate(client, path, filename=None, content=None):
    """POST `path` (or `content`) to /validate as a multipart upload."""
    body = content if content is not None else path.read_bytes()
    return client.post("/api/validate", files={"file": (filename or path.name, body)})


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


def test_validate_max_warnings():
    content = b">s1\nACGT\n>s1\nAC!T\n"
    client = TestClient(build_app())
    body = client.post(
        "/api/validate", files={"file": ("bad.fasta", content)}, data={"max_warnings": "1"}
    ).json()
    assert len(body["warnings"]) == 1
    assert body["warnings_truncated"] is True
    assert body["passed"] is False
    assert body["warning_counts"]["invalid_characters"] == 1


def test_validate_warning_details():
    content = b">s1\nACGT\n>s1\nAC!T\n"
    body = post_validate(TestClient(build_app()), DATA_DIR / "x", "bad.fasta", content).json()
    details = {w["kind"]: w["details"] for w in body["warnings"]}
    assert details["duplicate_id"] is None
    assert details["invalid_characters"] == {
        "characters": ["!"],
        "count": 1,
        "first_positions": [3],
    }


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
    assert TestClient(build_app()).post("/api/validate").status_code == 422


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
    assert client.post("/api/validate", files=files).status_code == 401
    resp = client.post("/api/validate", files=files, headers={"X-API-Key": "k1"})
    assert resp.status_code == 200


def post_normalize(client, path, filename=None, content=None, **form):
    """POST `path` (or `content`) to /normalize as a multipart upload with form fields."""
    return client.post("/api/normalize", files=[upload(path, filename, content)], data=form)


@pytest.mark.parametrize(
    ("name", "fmt"),
    [
        ("ls_orchid.gbk", "fasta"),
        ("ls_orchid.fasta", "genbank"),
        ("sample.fastq", "fastq"),
        ("sample.fastq", "fasta"),
    ],
)
def test_normalize_matches_cli_output(tmp_path, name, fmt):
    path = DATA_DIR / name
    resp = post_normalize(TestClient(build_app()), path, format=fmt)
    out = tmp_path / f"out.{fmt}"
    assert main(["normalize", str(path), f"--{fmt}", str(out)]) == 0
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert resp.text == out.read_text()


def test_normalize_defaults_to_uppercase_fasta():
    content = b">s1 lower\nacgtn\n"
    resp = post_normalize(TestClient(build_app()), DATA_DIR / "x", "s.fasta", content)
    assert resp.status_code == 200
    assert resp.text == ">s1 lower\nACGTN\n"


def test_normalize_gzip_upload():
    content = gzip.compress((DATA_DIR / "sample.fastq").read_bytes())
    client = TestClient(build_app())
    resp = post_normalize(client, DATA_DIR / "x", "reads.fastq.gz", content, format="fastq")
    assert resp.status_code == 200
    assert resp.text.count("@read") == 4


def test_normalize_fastq_skips_records_without_quality(caplog):
    content = b">seq1\nACGT\n>seq2\nAC\n"
    client = TestClient(build_app())
    resp = post_normalize(client, DATA_DIR / "x", "s.fasta", content, format="fastq")
    assert resp.status_code == 200
    assert resp.text == ""
    assert resp.headers["x-records-read"] == "2"
    assert resp.headers["x-records-written"] == "0"
    assert resp.headers["x-records-skipped"] == "2"
    assert "skipping 2 record(s) with no qualities for FASTQ: seq1, seq2" in caplog.text


def test_normalize_record_headers():
    resp = post_normalize(TestClient(build_app()), DATA_DIR / "ls_orchid.gbk", format="fasta")
    assert resp.headers["content-disposition"] == 'attachment; filename="ls_orchid.fasta"'
    assert resp.headers["x-records-read"] == "94"
    assert resp.headers["x-records-written"] == "94"
    assert resp.headers["x-records-skipped"] == "0"


def test_normalize_filename_of_compressed_upload():
    content = gzip.compress((DATA_DIR / "sample.fastq").read_bytes())
    client = TestClient(build_app())
    resp = post_normalize(client, DATA_DIR / "x", "reads.fq.gz", content, format="fasta")
    assert resp.headers["content-disposition"] == 'attachment; filename="reads.fasta"'


def test_normalize_non_ascii_filename():
    content = b">s1\nACGT\n"
    client = TestClient(build_app())
    resp = post_normalize(client, DATA_DIR / "x", "séq.fa", content, format="genbank")
    assert resp.headers["content-disposition"] == (
        "attachment; filename=\"s_q.gbk\"; filename*=UTF-8''s%C3%A9q.gbk"
    )


@pytest.mark.parametrize(
    ("name", "fmt", "expected"),
    [
        ("reads.fq.gz", "fasta", "reads.fasta"),
        ("in.gb.bz2", "fastq", "in.fastq"),
        ("/tmp/dir/seqs.fasta", "genbank", "seqs.gbk"),
        ("C:\\data\\seqs.fasta", "fasta", "seqs.fasta"),
        ("my.reads.fastq", "fasta", "my.reads.fasta"),
        ("noext", "fasta", "noext.fasta"),
        ("", "fastq", "upload.fastq"),
        (None, "genbank", "upload.gbk"),
    ],
)
def test_normalized_filename(name, fmt, expected):
    assert normalized_filename(name, fmt) == expected


def test_normalize_empty_upload():
    resp = post_normalize(TestClient(build_app()), DATA_DIR / "x", "empty.fasta", b"")
    assert resp.status_code == 200
    assert resp.text == ""
    assert resp.headers["x-records-read"] == "0"
    assert resp.headers["x-records-written"] == "0"


def test_normalize_unrecognized_file():
    resp = post_normalize(TestClient(build_app()), DATA_DIR / "text_input.txt")
    assert resp.status_code == 422
    assert resp.json()["detail"].startswith("text_input.txt: unrecognized format")


def test_normalize_rejects_unknown_format():
    client = TestClient(build_app())
    resp = post_normalize(client, DATA_DIR / "ls_orchid.fasta", format="embl")
    assert resp.status_code == 422


def test_normalize_requires_file():
    assert (
        TestClient(build_app()).post("/api/normalize", data={"format": "fasta"}).status_code == 422
    )


def test_api_key_auth_guards_normalize():
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"])))
    files = [upload(DATA_DIR / "ls_orchid.fasta")]
    assert client.post("/api/normalize", files=files).status_code == 401
    resp = client.post("/api/normalize", files=files, headers={"X-API-Key": "k1"})
    assert resp.status_code == 200


PREFLIGHT_HEADERS = {
    "Origin": "http://localhost:5173",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type",
}


def test_cors_disabled_by_default():
    client = TestClient(build_app())
    resp = client.get("/api/", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" not in resp.headers


def test_cors_any_origin():
    client = TestClient(build_app(cors_origins=[]))
    resp = client.options("/api/stats", headers=PREFLIGHT_HEADERS)
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "*"


def test_cors_specific_origin():
    client = TestClient(build_app(cors_origins=["http://localhost:5173"]))
    resp = client.options("/api/stats", headers=PREFLIGHT_HEADERS)
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"

    resp = client.options("/api/stats", headers={**PREFLIGHT_HEADERS, "Origin": "http://evil.test"})
    assert resp.status_code == 400


def test_cors_exposes_normalize_headers():
    client = TestClient(build_app(cors_origins=["http://localhost:5173"]))
    preflight = client.options("/api/normalize", headers=PREFLIGHT_HEADERS)
    assert preflight.status_code == 200
    resp = client.post(
        "/api/normalize",
        files=[upload(DATA_DIR / "ls_orchid.fasta")],
        headers={"Origin": "http://localhost:5173"},
    )
    exposed = {h.strip().lower() for h in resp.headers["access-control-expose-headers"].split(",")}
    assert exposed == {
        "content-disposition",
        "x-records-read",
        "x-records-written",
        "x-records-skipped",
    }


@pytest.fixture
def failing_stats(monkeypatch):
    """Make /stats raise an unexpected error."""

    def boom(*args, **kwargs):
        raise RuntimeError("secret traceback detail")

    monkeypatch.setattr(app_module, "stats_rows", boom)


def test_internal_error_is_json(failing_stats, caplog):
    resp = TestClient(build_app()).post("/api/stats", data={"sequence": "ACGT"})
    assert resp.status_code == 500
    assert resp.headers["content-type"] == "application/json"
    assert resp.json() == {"detail": "Internal server error"}
    assert "secret" not in resp.text
    assert "secret traceback detail" in caplog.text


def test_internal_error_has_cors_headers(failing_stats):
    client = TestClient(build_app(cors_origins=[]))
    resp = client.post(
        "/api/stats", data={"sequence": "ACGT"}, headers={"Origin": "http://localhost:5173"}
    )
    assert resp.status_code == 500
    assert resp.headers["access-control-allow-origin"] == "*"


ONE_MB = 1024 * 1024


def test_upload_over_limit():
    client = TestClient(build_app(max_upload_mb=1))
    files = [upload(DATA_DIR / "x", "big.fasta", b">s\n" + b"A" * ONE_MB)]
    resp = client.post("/api/stats", files=files)
    assert resp.status_code == 413
    assert resp.json() == {"detail": "upload too large: limit is 1 MB"}


def test_upload_limit_covers_all_stats_files():
    client = TestClient(build_app(max_upload_mb=1))
    half = b">s\n" + b"A" * (ONE_MB // 2)
    files = [upload(DATA_DIR / "x", "a.fasta", half), upload(DATA_DIR / "x", "b.fasta", half)]
    assert client.post("/api/stats", files=files).status_code == 413
    assert client.post("/api/stats", files=files[:1]).status_code == 200


def test_chunked_upload_over_limit():
    client = TestClient(build_app(max_upload_mb=1))
    boundary = "cobaltboundary"
    head = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="big.fasta"'
        "\r\n\r\n>s\n"
    ).encode()

    def body():
        yield head
        for _ in range(4):
            yield b"A" * (ONE_MB // 2)
        yield f"\r\n--{boundary}--\r\n".encode()

    resp = client.post(
        "/api/stats",
        content=body(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "upload too large: limit is 1 MB"


@pytest.mark.parametrize(
    ("name", "compress"), [("big.fasta.gz", gzip.compress), ("big.fasta.bz2", bz2.compress)]
)
def test_decompressed_size_over_limit(name, compress):
    content = compress(b">s\n" + b"A" * (11 * ONE_MB))
    assert len(content) < ONE_MB
    client = TestClient(build_app(max_upload_mb=1))
    resp = post_inspect(client, DATA_DIR / "x", name, content, overview_only="true")
    assert resp.status_code == 413
    assert resp.json() == {"detail": f"{name}: decompressed size exceeds the limit"}


def test_upload_limit_disabled():
    content = gzip.compress(b">s\n" + b"A" * (11 * ONE_MB))
    files = [upload(DATA_DIR / "x", "big.fasta", b">s\n" + b"A" * ONE_MB)]
    client = TestClient(build_app(max_upload_mb=0))
    assert client.post("/api/stats", files=files).status_code == 200
    resp = post_inspect(client, DATA_DIR / "x", "big.fasta.gz", content, overview_only="true")
    assert resp.status_code == 200


def test_upload_limit_has_cors_headers():
    client = TestClient(build_app(cors_origins=[], max_upload_mb=1))
    files = [upload(DATA_DIR / "x", "big.fasta", b">s\n" + b"A" * ONE_MB)]
    resp = client.post("/api/stats", files=files, headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 413
    assert resp.headers["access-control-allow-origin"] == "*"


HTML = {"Accept": "text/html,application/xhtml+xml"}


def test_ui_static_files(ui_dist):
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"]), ui_dist=ui_dist))
    assert client.get("/").text == "<html>cobalt ui</html>"
    resp = client.get("/assets/app.js")
    assert resp.status_code == 200
    assert resp.text == "console.log('ui')"


def test_ui_client_routes_get_index(ui_dist):
    client = TestClient(build_app(ui_dist=ui_dist))
    resp = client.get("/inspect", headers=HTML)
    assert resp.status_code == 200
    assert resp.text == "<html>cobalt ui</html>"


def test_ui_missing_asset_without_html_is_404(ui_dist):
    client = TestClient(build_app(ui_dist=ui_dist))
    assert client.get("/assets/missing.js", headers={"Accept": "*/*"}).status_code == 404


def test_ui_never_answers_api_paths(ui_dist):
    client = TestClient(build_app(ui_dist=ui_dist))
    assert client.get("/api", headers=HTML).json() == VERSION_BODY
    assert client.get("/api/", headers=HTML).json() == VERSION_BODY
    for resp in [client.get("/api/missing", headers=HTML), client.post("/api/missing")]:
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Not Found"}
    # An API route with the wrong method is not the UI either (404 here, as the UI mount
    # fully matches the path and wins over the route's method mismatch)
    resp = client.get("/api/stats", headers=HTML)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}


def test_ui_needs_api_prefix(ui_dist):
    with pytest.raises(ValueError, match="API prefix"):
        build_app(api_prefix="", ui_dist=ui_dist)


def test_api_key_auth_guards_processing_endpoints():
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"])))
    body = {"sequence": "ACGT"}

    resp = client.post("/api/stats", data=body)
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "ApiKey"
    assert client.post("/api/stats", data=body, headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/api/stats", data=body, headers={"X-API-Key": "k1"}).status_code == 200


def test_me():
    resp = TestClient(build_app()).get("/api/me")
    assert resp.status_code == 200
    assert resp.json() == {"name": "lab user"}


def test_me_requires_api_key():
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"])))

    resp = client.get("/api/me")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid or missing API key"}
    assert resp.headers["www-authenticate"] == "ApiKey"
    assert client.get("/api/me", headers={"X-API-Key": "wrong"}).status_code == 401
    resp = client.get("/api/me", headers={"X-API-Key": "k1"})
    assert resp.status_code == 200
    assert resp.json() == {"name": "lab user"}


def test_me_user_key():
    users = UserStore()
    _, key = users.add_user("Ada Lovelace")
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"], users), users=users))
    assert client.get("/api/me", headers={"X-API-Key": key}).json() == {"name": "Ada Lovelace"}
    # A shared key has no user: the default user answers
    assert client.get("/api/me", headers={"X-API-Key": "k1"}).json() == {"name": "lab user"}


def test_me_renamed_default_user():
    users = UserStore()
    users.rename_user("lab user", "Lab")
    assert TestClient(build_app(users=users)).get("/api/me").json() == {"name": "Lab"}


def test_me_other_methods_not_allowed():
    resp = TestClient(build_app()).post("/api/me")
    assert resp.status_code == 405
    assert resp.json() == {"detail": "Method Not Allowed"}


def test_api_key_auth_leaves_root_public():
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"])))
    assert client.get("/api/").json() == VERSION_BODY
    assert client.get("/api").json() == VERSION_BODY
    assert client.get("/api/openapi.json").status_code == 200


STUB_REQUESTS = [
    ("post", "/api/foldrna", {"sequence": "GGGAAAUCC"}, "foldrna"),
    ("post", "/api/run", {"pipeline": "name: demo"}, "run"),
]


@pytest.mark.parametrize(("method", "path", "body", "command"), STUB_REQUESTS)
def test_stub_endpoints_not_implemented(method, path, body, command):
    client = TestClient(build_app())
    resp = client.request(method, path, json=body)
    assert resp.status_code == 501
    assert resp.json() == {"detail": f"cobalt {command} is not implemented yet"}


def test_foldrna_validates_body():
    client = TestClient(build_app())
    assert client.post("/api/foldrna", json={}).status_code == 422


@pytest.mark.parametrize(("method", "path", "body", "command"), STUB_REQUESTS)
def test_api_key_auth_guards_stub_endpoints(method, path, body, command):
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"])))
    assert client.request(method, path, json=body).status_code == 401
    resp = client.request(method, path, json=body, headers={"X-API-Key": "k1"})
    assert resp.status_code == 501


PIPELINE_FILE = Path(__file__).parents[2] / "test_data" / "pipeline_test_v1.yaml"


def registry_with_run(runs_dir=None):
    registry = RunRegistry(runs_dir)
    run = registry.create(load_pipeline(PIPELINE_FILE), PIPELINE_FILE.read_text(), {"k": "v"})
    return registry, run


def test_runs_list_empty():
    assert TestClient(build_app()).get("/api/runs").json() == []


def test_runs_list_and_show():
    registry, run = registry_with_run()
    run.set_task_status("validate", RunStatus.SUCCEEDED)
    client = TestClient(build_app(runs=registry))

    (summary,) = client.get("/api/runs").json()
    assert summary["run_id"] == run.run_id
    assert summary["pipeline"]["name"] == "fold-rna-from-fasta"
    assert summary["status"] == "pending"
    assert summary["tasks"]["pending"] == 3
    assert summary["tasks"]["succeeded"] == 1
    assert "params" not in summary

    resp = client.get(f"/api/runs/{run.run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["params"] == {"k": "v"}
    assert [task["name"] for task in body["tasks"]] == ["inspect", "validate", "normalize", "fold"]
    assert body["tasks"][1]["status"] == "succeeded"
    assert body["tasks"][2]["depends_on"] == ["validate"]


def test_runs_show_unknown_run():
    resp = TestClient(build_app()).get("/api/runs/nope")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "run not found: nope"}


def test_app_keeps_its_registry():
    registry = RunRegistry()
    assert build_app(runs=registry).state.runs is registry
    assert isinstance(build_app().state.runs, RunRegistry)


@pytest.mark.parametrize("path", ["/api/runs", "/api/runs/r1"])
def test_api_key_auth_guards_runs(path):
    client = TestClient(build_app(auth=ApiKeyAuth(["k1"])))
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-API-Key": "k1"}).status_code in (200, 404)
