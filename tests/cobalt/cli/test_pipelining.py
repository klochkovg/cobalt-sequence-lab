import logging
from pathlib import Path

import pytest

from cobalt.cli import run
from cobalt.cli.main import main
from cobalt.cli.remote import SERVER_ENV

SAMPLE = Path(__file__).parents[2] / "test_data" / "pipeline_test_v1.yaml"


SERVER_ONLY_CASES = [
    (
        ["run", "pipeline.yaml", "--backend", "local", "--param", "input=x.fasta", "--resume"],
        "run",
    ),
    (["runs", "list"], "runs list"),
    (["runs", "show", "run-1"], "runs show"),
]


@pytest.fixture
def no_server_env(monkeypatch):
    monkeypatch.delenv(SERVER_ENV, raising=False)


@pytest.mark.parametrize("local_flag", [[], ["--local"]])
@pytest.mark.parametrize(("argv", "command"), SERVER_ONLY_CASES)
def test_server_only_commands_unsupported_in_cli_mode(
    no_server_env, caplog, argv, command, local_flag
):
    with caplog.at_level(logging.ERROR):
        exit_code = main([*local_flag, *argv])

    assert exit_code == 1
    assert f"cobalt {command} is not supported in CLI mode" in caplog.text
    assert "not implemented" not in caplog.text


def test_run_not_implemented_in_client_mode(no_server_env, caplog):
    argv, command = SERVER_ONLY_CASES[0]
    with caplog.at_level(logging.WARNING):
        exit_code = main(["--server", "http://lab-a:8000", *argv])

    assert exit_code == 1
    assert f"cobalt {command} is not implemented yet in client mode" in caplog.text
    assert "http://lab-a:8000" in caplog.text
    assert "locally" not in caplog.text


def test_server_only_command_client_mode_from_env(monkeypatch, caplog):
    monkeypatch.setenv(SERVER_ENV, "http://lab-a")
    assert main(["run", "p.yaml"]) == 1
    assert "not implemented yet in client mode (server http://lab-a)" in caplog.text


def test_server_only_command_local_flag_overrides_env(monkeypatch, caplog):
    monkeypatch.setenv(SERVER_ENV, "http://lab-a")
    assert main(["--local", "run", "p.yaml"]) == 1
    assert "not supported in CLI mode" in caplog.text


def test_server_only_command_bad_server_url(no_server_env, caplog):
    assert main(["--server", "lab-a", "run", "p.yaml"]) == 1
    assert "expected an http:// or https:// URL" in caplog.text
    assert "not supported" not in caplog.text


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
