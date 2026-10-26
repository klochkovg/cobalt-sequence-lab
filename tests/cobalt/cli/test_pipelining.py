import logging
from pathlib import Path

import pytest

from cobalt.cli import run
from cobalt.cli.main import main

SAMPLE = Path(__file__).parents[2] / "test_data" / "pipeline_test_v1.yaml"


@pytest.mark.parametrize(
    "argv",
    [
        ["run", "pipeline.yaml", "--backend", "local", "--param", "input=x.fasta", "--resume"],
        ["runs", "list"],
        ["runs", "show", "run-1"],
    ],
)
def test_stub_commands_report_not_implemented(argv, caplog):
    with caplog.at_level(logging.ERROR):
        exit_code = main(argv)

    assert exit_code == 1
    assert "not implemented yet" in caplog.text


def test_run_parses_params():
    args = run.build_parser().parse_args(
        ["p.yaml", "--param", "input=x.fasta", "--param", "expr=a=b"]
    )

    assert dict(args.param) == {"input": "x.fasta", "expr": "a=b"}
    assert args.backend == "local"
    assert args.resume is False


@pytest.mark.parametrize("bad", ["input", "=x.fasta"])
def test_run_rejects_malformed_param(bad, capsys):
    with pytest.raises(SystemExit):
        main(["run", "p.yaml", "--param", bad])
    assert "expected KEY=VALUE" in capsys.readouterr().err


def test_run_rejects_unknown_backend(capsys):
    with pytest.raises(SystemExit):
        main(["run", "p.yaml", "--backend", "slurm"])
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["pipeline"], ["pipeline", "check"], ["runs", "show"]])
def test_missing_arguments_are_usage_errors(argv):
    with pytest.raises(SystemExit) as excinfo:
        main(argv)
    assert excinfo.value.code == 2


def test_help_for_pipelining_commands(capsys):
    for command in ("run", "pipeline", "runs"):
        assert main(["help", command]) == 0
        assert f"usage: cobalt {command}" in capsys.readouterr().out


def test_pipeline_check_prints_structure(capsys):
    exit_code = main(["pipeline", "check", str(SAMPLE)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.startswith("pipeline: fold-rna-from-fasta 0.1.0")
    assert "  fold [fold_rna]" in captured.out


def test_pipeline_graph_prints_edges(capsys):
    exit_code = main(["pipeline", "graph", str(SAMPLE)])

    assert exit_code == 0
    assert capsys.readouterr().out == "validate -> normalize\nnormalize -> fold\ninspect\n"


@pytest.mark.parametrize("action", ["check", "graph"])
def test_pipeline_missing_file(action, tmp_path, caplog, capsys):
    with caplog.at_level(logging.ERROR):
        exit_code = main(["pipeline", action, str(tmp_path / "missing.yaml")])

    assert exit_code == 1
    assert "file not found" in caplog.text
    assert capsys.readouterr().out == ""
