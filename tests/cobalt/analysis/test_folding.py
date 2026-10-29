import io
from dataclasses import replace

import pytest
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from cobalt.analysis.folding import FoldResult, fold_records, write_fold_results
from cobalt.analysis.processor import process_records


def make_record(seq: str, seq_id: str = "seq1"):
    result = process_records([SeqRecord(Seq(seq), id=seq_id)], "raw")
    assert result is not None
    return result.records[0]


def test_fold_records_reads_dna_as_rna():
    pytest.importorskip("RNA")

    results = fold_records([make_record("gggaaatcc")], "viennarna")

    assert len(results) == 1
    assert results[0].sequence == "GGGAAAUCC"
    assert len(results[0].structure) == len(results[0].sequence)
    assert set(results[0].structure) <= set("().")


def test_fold_records_skips_protein_and_empty(caplog):
    protein = make_record("MKWVTFISLLFLFSSAYS", "prot1")
    no_sequence = replace(make_record("ACGU", "len_only"), sequence=None)

    results = fold_records([protein, no_sequence], "viennarna")

    assert results == []
    assert "prot1: protein sequence, skipped" in caplog.text
    assert "len_only: no sequence content, skipped" in caplog.text


def test_write_fold_results_rnafold_format():
    out = io.StringIO()

    write_fold_results(out, [FoldResult("seq1", "GGGAAAUCC", "(((...)))", -1.2)])

    assert out.getvalue() == ">seq1\nGGGAAAUCC\n(((...))) ( -1.20)\n"
