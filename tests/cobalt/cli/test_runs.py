import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cobalt.cli import runs
from cobalt.cli.client import ServerError
from cobalt.cli.main import main
from cobalt.cli.remote import SERVER_ENV
from cobalt.cli.serve import build_app
from cobalt.pipeline import PipelineRun, RunRegistry, RunStatus, load_pipeline

SAMPLE = Path(__file__).parents[2] / "test_data" / "pipeline_test_v1.yaml"
SERVER = "http://lab-a:8000"
T0 = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


@pytest.fixture
def registry():
    return RunRegistry()


@pytest.fixture
def server(monkeypatch, registry):
    """Answer the client's requests with a real app holding `registry`; record the paths."""
    monkeypatch.delenv(SERVER_ENV, raising=False)
    client = TestClient(build_app(runs=registry))
    paths = []

    def fake_get_json(server_url, path):
        assert server_url == SERVER
        paths.append(path)
        resp = client.get(f"/api{path}")
        if resp.status_code >= 400:
            raise ServerError(f"server answered {resp.status_code}: {resp.json()['detail']}")
        return resp.json()

    monkeypatch.setattr(runs, "get_json", fake_get_json)
    return paths


def add_run(registry, now=T0, **params):
    run = PipelineRun.create(load_pipeline(SAMPLE), params, now=now)
    registry.save(run)
    return run


def test_list_empty(server, capsys):
    assert main(["--server", SERVER, "runs", "list"]) == 0
    assert capsys.readouterr().out == "no runs\n"
    assert server == ["/runs"]


def test_list(server, registry, capsys):
    old = add_run(registry)
    new = add_run(registry, now=T0.replace(hour=4))
    new.set_task_status("inspect", RunStatus.SUCCEEDED)
    new.set_status(RunStatus.FAILED, "boom")

    assert main(["--server", SERVER, "runs", "list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["RUN", "ID", "PIPELINE", "STATUS", "CREATED", "TASKS"]
    assert lines[1].startswith(new.run_id)
    assert "fold-rna-from-fasta 0.1.0" in lines[1]
    assert "failed" in lines[1]
    assert "2026-01-02 04:04:05 UTC" in lines[1]
    assert lines[1].endswith("pending 3, succeeded 1")
    assert lines[2].startswith(old.run_id)
    assert lines[2].endswith("pending 4")
    # Columns are aligned
    assert lines[1].index("fold-rna") == lines[0].index("PIPELINE")


def test_show(server, registry, capsys):
    run = add_run(registry, min_length="30")
    run.set_task_status("validate", RunStatus.FAILED, "bad input", now=T0)

    assert main(["--server", SERVER, "runs", "show", run.run_id]) == 0
    out = capsys.readouterr().out
    assert server == [f"/runs/{run.run_id}"]
    assert f"run: {run.run_id}\n" in out
    assert "pipeline: fold-rna-from-fasta 0.1.0\n" in out
    assert "status: pending\n" in out
    assert "created: 2026-01-02 03:04:05 UTC\n" in out
    assert "started: -\n" in out
    assert "  min_length=30\n" in out
    assert "  validate [validate] failed: bad input\n" in out
    assert "  normalize [normalize] pending, after validate\n" in out


def test_show_json(server, registry, capsys):
    run = add_run(registry)
    assert main(["--server", SERVER, "runs", "show", run.run_id, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["run_id"] == run.run_id


def test_list_json(server, registry, capsys):
    run = add_run(registry)
    assert main(["--server", SERVER, "runs", "list", "--json"]) == 0
    assert [r["run_id"] for r in json.loads(capsys.readouterr().out)] == [run.run_id]


def test_show_unknown_run(server, caplog, capsys):
    with caplog.at_level(logging.ERROR):
        assert main(["--server", SERVER, "runs", "show", "nope"]) == 1
    assert "cobalt runs show: server answered 404: run not found: nope" in caplog.text
    assert capsys.readouterr().out == ""


def test_show_quotes_run_id(server):
    main(["--server", SERVER, "runs", "show", "../x"])
    assert server == ["/runs/..%2Fx"]


def test_server_from_env(server, monkeypatch, capsys):
    monkeypatch.setenv(SERVER_ENV, SERVER)
    assert main(["runs", "list"]) == 0
    assert server == ["/runs"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "-"),
        ("2026-01-02T03:04:05.123Z", "2026-01-02 03:04:05 UTC"),
        ("2026-01-02T05:04:05+02:00", "2026-01-02 03:04:05 UTC"),
        ("2026-01-02T03:04:05", "2026-01-02 03:04:05"),
        ("soon", "soon"),
    ],
)
def test_format_time(value, expected):
    assert runs.format_time(value) == expected
