from pathlib import Path

from cobalt.pipeline import load_pipeline
from cobalt.pipeline.render import format_graph, format_structure

SAMPLE = Path(__file__).parents[2] / "test_data" / "pipeline_test_v1.yaml"


def test_format_structure():
    text = format_structure(load_pipeline(SAMPLE))

    assert text.startswith("pipeline: fold-rna-from-fasta 0.1.0 (schema v1)")
    assert "  min_length: int = 20" in text
    assert "  sequences: fasta" in text
    assert "    resources: cpus=2, memory=4GB" in text
    assert "    depends on: normalize" in text
    assert "  structures: ${tasks.fold.outputs.structures}" in text
    tasks = [line.split()[0] for line in text.splitlines() if line.endswith("]")]
    assert tasks.index("validate") < tasks.index("normalize") < tasks.index("fold")


def test_format_graph():
    lines = format_graph(load_pipeline(SAMPLE)).splitlines()

    assert lines == ["validate -> normalize", "normalize -> fold", "inspect"]
