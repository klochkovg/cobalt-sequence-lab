"""Tests for normalize helpers"""

from cobalt.analysis.normalize import uppercase_result


def test_uppercase():
    test_data = [{"sequence": "AdGcUAgU"}]
    test_result = uppercase_result(test_data)
    assert test_result[0]["sequence"] == "ADGCUAGU"
