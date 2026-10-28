import pytest


def test_viennarna_fold_smoke():
    RNA = pytest.importorskip("RNA")
    seq = "GGGAAAUCC"

    structure, mfe = RNA.fold(seq)

    assert len(structure) == len(seq)
    assert set(structure) <= set("().")
    assert isinstance(mfe, float)
