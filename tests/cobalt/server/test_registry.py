import json
import logging
from pathlib import Path

import pytest

from cobalt.core.pipeline import PipelineRun, RunStatus, load_pipeline
from cobalt.server.registry import (
    DEFINITION_FILENAME,
    INTERRUPTED_ERROR,
    MANIFEST_FILENAME,
    RunRegistry,
)

SAMPLE = Path(__file__).parents[2] / "test_data" / "pipeline_test_v1.yaml"


@pytest.fixture
def pipeline():
    return load_pipeline(SAMPLE)


def create(registry, pipeline, **kwargs):
    return registry.create(pipeline, SAMPLE.read_text(), **kwargs)


def test_memory_only(pipeline, tmp_path):
    registry = RunRegistry()
    first = create(registry, pipeline)
    second = create(registry, pipeline, params={"a": "b"}, resume=True)
    assert registry.get(first.run_id) is first
    assert registry.list_runs() == [second, first]
    assert len(registry) == 2
    assert registry.run_dir(first.run_id) is None
    registry.save(first)
    assert registry.load() == 0
    assert list(tmp_path.iterdir()) == []


def test_get_unknown_or_path_like_id(pipeline, tmp_path):
    registry = RunRegistry(tmp_path)
    create(registry, pipeline)
    assert registry.get("nope") is None
    assert registry.get("../x") is None


def test_create_writes_definition_and_manifest(pipeline, tmp_path):
    registry = RunRegistry(tmp_path / "runs")
    run = create(registry, pipeline, params={"k": "v"})
    run_dir = tmp_path / "runs" / run.run_id
    assert (run_dir / DEFINITION_FILENAME).read_text() == SAMPLE.read_text()
    manifest = json.loads((run_dir / MANIFEST_FILENAME).read_text())
    assert manifest["run_id"] == run.run_id
    assert manifest["params"] == {"k": "v"}


def test_load_restores_runs(pipeline, tmp_path):
    registry = RunRegistry(tmp_path)
    run = create(registry, pipeline)
    run.set_task_status("inspect", RunStatus.SUCCEEDED)
    run.set_status(RunStatus.SUCCEEDED)
    registry.save(run)

    reloaded = RunRegistry(tmp_path)
    assert reloaded.load() == 1
    assert reloaded.get(run.run_id) == run


def test_load_marks_unfinished_runs_failed(pipeline, tmp_path):
    registry = RunRegistry(tmp_path)
    run = create(registry, pipeline)
    run.set_status(RunStatus.RUNNING)
    registry.save(run)

    reloaded = RunRegistry(tmp_path)
    assert reloaded.load() == 1
    loaded = reloaded.get(run.run_id)
    assert loaded is not None
    assert (loaded.status, loaded.error) == (RunStatus.FAILED, INTERRUPTED_ERROR)
    manifest = json.loads((tmp_path / run.run_id / MANIFEST_FILENAME).read_text())
    assert manifest["status"] == "failed"


def test_load_skips_bad_manifests(pipeline, tmp_path, caplog):
    registry = RunRegistry(tmp_path)
    good = create(registry, pipeline)
    for name, text in [("broken", "{not json"), ("invalid", '{"run_id": "invalid"}')]:
        (tmp_path / name).mkdir()
        (tmp_path / name / MANIFEST_FILENAME).write_text(text)
    # A valid manifest in a directory named after another run
    (tmp_path / "moved").mkdir()
    (tmp_path / "moved" / MANIFEST_FILENAME).write_text(json.dumps(good.to_dict()))

    reloaded = RunRegistry(tmp_path)
    with caplog.at_level(logging.WARNING):
        assert reloaded.load() == 1
    assert [run.run_id for run in reloaded.list_runs()] == [good.run_id]
    for name in ("broken", "invalid", "moved"):
        assert str(tmp_path / name / MANIFEST_FILENAME) in caplog.text


def test_load_creates_runs_dir(tmp_path):
    assert RunRegistry(tmp_path / "a" / "runs").load() == 0
    assert (tmp_path / "a" / "runs").is_dir()


def test_save_registers_run(pipeline, tmp_path):
    registry = RunRegistry(tmp_path)
    run = PipelineRun.create(pipeline)
    registry.save(run)
    assert registry.get(run.run_id) is run
    assert (tmp_path / run.run_id / MANIFEST_FILENAME).is_file()
