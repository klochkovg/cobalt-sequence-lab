import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cobalt.pipeline import PipelineRun, RunStatus, TaskRun, load_pipeline
from cobalt.pipeline.run import MANIFEST_VERSION, RunSummary, new_run_id

SAMPLE = Path(__file__).parents[2] / "test_data" / "pipeline_test_v1.yaml"
T0 = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


@pytest.fixture
def run():
    return PipelineRun.create(load_pipeline(SAMPLE), {"min_length": "30"}, now=T0)


def test_create_builds_pending_tasks_in_order(run):
    assert run.run_id.startswith("20260102-030405-")
    assert run.pipeline.name == "fold-rna-from-fasta"
    assert run.params == {"min_length": "30"}
    assert run.status is RunStatus.PENDING
    assert run.created_at == T0
    assert [task.name for task in run.tasks] == ["inspect", "validate", "normalize", "fold"]
    assert run.task("normalize").depends_on == ["validate"]
    assert run.task("fold").type == "fold_rna"
    assert all(task.status is RunStatus.PENDING for task in run.tasks)


def test_task_unknown_name(run):
    with pytest.raises(KeyError):
        run.task("nope")
    with pytest.raises(KeyError):
        run.set_task_status("nope", RunStatus.RUNNING)


def test_status_changes_stamp_times(run):
    t1, t2 = T0 + timedelta(seconds=1), T0 + timedelta(seconds=2)
    run.set_task_status("inspect", RunStatus.RUNNING, now=t1)
    run.set_task_status("inspect", RunStatus.FAILED, "boom", now=t2)
    task = run.task("inspect")
    assert (task.status, task.error) == (RunStatus.FAILED, "boom")
    assert (task.started_at, task.finished_at) == (t1, t2)

    run.set_status(RunStatus.RUNNING, now=t1)
    run.set_status(RunStatus.SUCCEEDED, now=t2)
    assert (run.started_at, run.finished_at, run.error) == (t1, t2, None)


def test_task_counts(run):
    run.set_task_status("inspect", RunStatus.SUCCEEDED)
    counts = run.task_counts()
    assert counts == {
        "pending": 3,
        "running": 0,
        "succeeded": 1,
        "failed": 0,
        "cancelled": 0,
    }
    summary = RunSummary.from_run(run)
    assert (summary.run_id, summary.tasks) == (run.run_id, counts)


def test_round_trip(run):
    run.set_status(RunStatus.RUNNING, now=T0)
    run.set_task_status("validate", RunStatus.CANCELLED, "stopped", now=T0)
    data = run.to_dict()
    assert data["manifest_version"] == MANIFEST_VERSION
    assert data["created_at"] == "2026-01-02T03:04:05+00:00"
    assert PipelineRun.from_dict(data) == run


def test_from_dict_ignores_unknown_keys(run):
    data = run.to_dict() | {"future": 1}
    data["tasks"][0]["future"] = 2
    assert PipelineRun.from_dict(data) == run


def test_naive_time_is_utc(run):
    data = run.to_dict() | {"created_at": "2026-01-02T03:04:05"}
    assert PipelineRun.from_dict(data).created_at == T0


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("run_id", None, "run_id"),
        ("pipeline", "x", "pipeline"),
        ("status", "done", "status"),
        ("created_at", None, "created_at"),
        ("created_at", "yesterday", "created_at"),
        ("resume", "yes", "resume"),
        ("tasks", {}, "tasks"),
        ("params", [], "params"),
    ],
)
def test_from_dict_invalid(run, key, value, message):
    data = run.to_dict() | {key: value}
    with pytest.raises(ValueError, match=message):
        PipelineRun.from_dict(data)


def test_task_from_dict_invalid():
    with pytest.raises(ValueError, match="depends_on"):
        TaskRun.from_dict({"name": "a", "type": "t", "depends_on": "b", "status": "pending"})
    with pytest.raises(ValueError, match="task"):
        TaskRun.from_dict([])


def test_new_run_id():
    first = new_run_id(T0)
    later = new_run_id(T0 + timedelta(seconds=1))
    assert re.fullmatch(r"20260102-030405-[0-9a-f]{8}", first)
    assert first < later
    assert new_run_id(T0) != first
