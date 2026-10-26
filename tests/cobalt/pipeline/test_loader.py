import copy
from pathlib import Path

import pytest

from cobalt.pipeline import PipelineFileError, load_pipeline, parse_pipeline

SAMPLE = Path(__file__).parents[2] / "test_data" / "pipeline_test_v1.yaml"

MINIMAL = {
    "schema_version": 1,
    "pipeline": {"name": "p", "version": "1"},
    "inputs": {"sequences": {"type": "fasta"}},
    "tasks": {
        "a": {"type": "inspect", "inputs": {"file": "${inputs.sequences}"}},
        "b": {"type": "validate", "inputs": {"file": "${tasks.a.outputs.report}"}},
    },
}


def minimal(**changes):
    data = copy.deepcopy(MINIMAL)
    data.update(changes)
    return data


def test_load_sample():
    pipeline = load_pipeline(SAMPLE)

    assert pipeline.schema_version == 1
    assert pipeline.info.name == "fold-rna-from-fasta"
    assert pipeline.info.version == "0.1.0"
    assert pipeline.params["min_length"].type == "int"
    assert pipeline.params["min_length"].default == 20
    assert pipeline.params["temperature"].default == 37.0
    assert pipeline.inputs["sequences"].type == "fasta"
    assert list(pipeline.tasks) == ["inspect", "validate", "normalize", "fold"]
    assert pipeline.outputs["structures"] == "${tasks.fold.outputs.structures}"


def test_sample_fold_task():
    fold = load_pipeline(SAMPLE).tasks["fold"]

    assert fold.type == "fold_rna"
    assert fold.adapter == "viennarna"
    assert fold.container is not None and fold.container.startswith("quay.io/biocontainers/")
    assert fold.resources == {"cpus": 2, "memory": "4GB"}
    assert fold.scatter == "record"
    assert fold.inputs == {"sequences": "${tasks.normalize.outputs.fasta}"}
    assert fold.params == {"temperature": "${params.temperature}"}
    assert fold.dependencies() == {"normalize"}


def test_sample_edges_and_order():
    pipeline = load_pipeline(SAMPLE)

    assert pipeline.edges() == [("validate", "normalize"), ("normalize", "fold")]
    order = pipeline.topological_order()
    assert order.index("validate") < order.index("normalize") < order.index("fold")


def test_parse_minimal():
    pipeline = parse_pipeline(minimal())

    assert pipeline.info.description == ""
    assert pipeline.params == {}
    assert pipeline.outputs == {}
    assert pipeline.edges() == [("a", "b")]


def test_numeric_version_is_accepted():
    assert parse_pipeline(minimal(pipeline={"name": "p", "version": 1.0})).info.version == "1.0"


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ([1, 2], "pipeline file: expected a mapping"),
        (minimal(schema_version=2), "schema_version: unsupported value 2"),
        (minimal(schema_version=True), "schema_version: unsupported value True"),
        (minimal(pipeline={"version": "1"}), "pipeline.name: required"),
        (minimal(tasks=None), "tasks: missing or empty"),
        (minimal(tasks={}), "tasks: at least one task is required"),
        (minimal(tasks={"a": {"inputs": {}}}), "tasks.a.type: required"),
        (minimal(tasks={"a": {"type": "x", "adaptor": "y"}}), "tasks.a: unknown key 'adaptor'"),
        (minimal(extra=1), "pipeline file: unknown key 'extra'"),
        (minimal(params={"n": {"default": 1}}), "params.n.type: required"),
        (
            minimal(tasks={"a": {"type": "x", "inputs": {"f": "${tasks.zz.outputs.r}"}}}),
            "tasks.a.inputs.f: unresolved reference ${tasks.zz.outputs.r}",
        ),
        (
            minimal(tasks={"a": {"type": "x", "params": {"n": "${params.n}"}}}),
            "tasks.a.params.n: unresolved reference ${params.n}",
        ),
        (minimal(outputs={"r": "${inputs.other}"}), "outputs.r: unresolved reference"),
        (
            minimal(
                tasks={
                    "a": {"type": "x", "inputs": {"f": "${tasks.b.outputs.r}"}},
                    "b": {"type": "x", "inputs": {"f": "${tasks.a.outputs.r}"}},
                }
            ),
            "tasks: dependency cycle",
        ),
    ],
)
def test_parse_errors(data, message):
    with pytest.raises(PipelineFileError) as excinfo:
        parse_pipeline(data)
    assert message in str(excinfo.value)


def test_load_missing_file(tmp_path):
    with pytest.raises(PipelineFileError, match="file not found"):
        load_pipeline(tmp_path / "missing.yaml")


def test_load_directory(tmp_path):
    with pytest.raises(PipelineFileError, match="is a directory"):
        load_pipeline(tmp_path)


def test_load_invalid_yaml(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("tasks:\n  a: {file: ${inputs.x}}\n")

    with pytest.raises(PipelineFileError, match="invalid YAML"):
        load_pipeline(path)


def test_load_error_names_the_file(tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text("schema_version: 3\n")

    with pytest.raises(PipelineFileError, match=r"p\.yaml: schema_version"):
        load_pipeline(path)
