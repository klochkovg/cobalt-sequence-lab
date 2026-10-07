import pytest

from cobalt.cli.main import COMMAND_HANDLERS, main


def test_help_lists_all_commands(capsys):
    exit_code = main(["help"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[stub]" not in captured.out
    for command in COMMAND_HANDLERS:
        assert command in captured.out


def test_help_for_command(capsys):
    exit_code = main(["help", "stats"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "usage: cobalt stats" in captured.out


def test_help_unknown_command(capsys):
    with pytest.raises(SystemExit):
        main(["help", "nonexistent"])
    assert "invalid choice" in capsys.readouterr().err
