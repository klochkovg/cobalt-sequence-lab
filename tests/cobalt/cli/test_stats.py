from pathlib import Path

import pytest
from cobalt.cli.main import main
import json

def test_stats_cmd_input(capsys):
    exit_code = main(["stats", "--input", "CATTGTTGAGATCACATAATAATTGATCGAGTTAAT", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0

    records = json.loads(captured.out)
    record = records[0]
    assert record['id'] == 'direct_input'
    assert record['length'] == 36
    assert record['type'] == 'DNA'
