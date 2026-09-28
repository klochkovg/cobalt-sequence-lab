import pytest

from cobalt.analysis.validation import print_warnings


def test_print_warnings(capsys):
    count = print_warnings(["seq2: duplicate ID", "seq3: empty sequence"])

    captured = capsys.readouterr()
    assert count == 2
    assert "warning: seq2: duplicate ID" in captured.out
    assert "warning: seq3: empty sequence" in captured.out
    assert "2 warning(s) found" in captured.out


def test_print_warnings_none(capsys):
    count = print_warnings([])

    assert count == 0
    assert capsys.readouterr().out == "0 warning(s) found\n"


def test_print_warnings_keeps_order(capsys):
    print_warnings(["b: second", "a: first", "c: third"])

    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "warning: b: second",
        "warning: a: first",
        "warning: c: third",
        "3 warning(s) found",
    ]


def test_print_warnings_writes_nothing_to_stderr(capsys):
    print_warnings(["seq1: duplicate ID"])

    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("count", [1, 5, 100])
def test_print_warnings_returns_count(capsys, count):
    warnings = [f"seq{i}: empty sequence" for i in range(count)]

    assert print_warnings(warnings) == count
    assert f"{count} warning(s) found" in capsys.readouterr().out
