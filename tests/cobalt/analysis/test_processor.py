import pytest

from cobalt.analysis.processor import (
    calculate_alphabet_class,
    calculate_ambiguity_fraction,
    calculate_gc_fraction,
)


@pytest.mark.parametrize(
    ("seq", "molecule_type", "expected"),
    [
        ("GGCC", "DNA", 1.0),
        ("ATAT", "DNA", 0.0),
        ("ACGT", "DNA", 0.5),
        ("acgt", "DNA", 0.5),
        ("ACGU", "RNA", 0.5),
        # Ambiguity codes other than S are left out of the count
        ("GCNN", "DNA", 1.0),
        ("GCAS", "DNA", 0.75),
    ],
)
def test_gc_fraction_nucleotide(seq, molecule_type, expected):
    assert calculate_gc_fraction(seq, molecule_type) == pytest.approx(expected)


@pytest.mark.parametrize("molecule_type", ["protein", "unknown"])
def test_gc_fraction_none_for_non_nucleotide(molecule_type):
    assert calculate_gc_fraction("GGCC", molecule_type) is None


@pytest.mark.xfail(strict=True, reason="all-ambiguous sequence reports 0 GC instead of None")
def test_gc_fraction_all_ambiguous_is_none():
    assert calculate_gc_fraction("NNNN", "DNA") is None


@pytest.mark.parametrize(
    ("seq", "molecule_type", "expected"),
    [
        ("ACGT", "DNA", "unambiguous"),
        ("acgt", "DNA", "unambiguous"),
        ("ACGU", "RNA", "unambiguous"),
        ("MKVLAAGIC", "protein", "unambiguous"),
        ("ACGTN", "DNA", "ambiguous"),
        ("ACGURY", "RNA", "ambiguous"),
        ("MKVX", "protein", "ambiguous"),
        ("ACGT1", "DNA", "invalid"),
        ("ACGU", "DNA", "invalid"),
        ("MKV1", "protein", "invalid"),
        ("", "DNA", "unknown"),
        ("ACGT", "unknown", "unknown"),
    ],
)
def test_alphabet_class(seq, molecule_type, expected):
    assert calculate_alphabet_class(seq, molecule_type) == expected


@pytest.mark.parametrize(
    ("seq", "molecule_type", "expected"),
    [
        ("ACGT", "DNA", 0.0),
        ("ACGTRYACGT", "DNA", 0.2),
        ("acgtn", "DNA", 0.2),
        ("NNNN", "DNA", 1.0),
        ("ACGN", "RNA", 0.25),
        ("MKVX", "protein", 0.25),
        ("", "DNA", 0.0),
    ],
)
def test_ambiguity_fraction(seq, molecule_type, expected):
    assert calculate_ambiguity_fraction(seq, molecule_type) == pytest.approx(expected)


@pytest.mark.xfail(strict=True, reason="unknown molecule type gives 0.0 instead of None")
def test_ambiguity_fraction_unknown_type_is_none():
    assert calculate_ambiguity_fraction("ACGTN", "unknown") is None
