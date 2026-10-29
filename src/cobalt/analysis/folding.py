"""RNA secondary structure prediction through pluggable folding backends (adapters)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO

from cobalt.model.record import SequenceRecord

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FoldResult:
    """Minimum free energy structure of one sequence."""

    id: str
    sequence: str
    # Dot-bracket notation, same length as sequence
    structure: str
    # Minimum free energy, kcal/mol
    mfe: float


def fold_viennarna(sequence: str) -> tuple[str, float]:
    """Fold `sequence` with ViennaRNA and return (dot-bracket structure, MFE).

    RNA is imported here because ViennaRNA is an optional dependency.
    """
    import RNA

    structure, mfe = RNA.fold(sequence)
    return str(structure), float(mfe)


ADAPTERS: dict[str, Callable[[str], tuple[str, float]]] = {"viennarna": fold_viennarna}
DEFAULT_ADAPTER = "viennarna"


def fold_records(records: list[SequenceRecord], adapter: str) -> list[FoldResult]:
    """Fold each nucleotide record with `adapter`; DNA letters are read as RNA (T -> U).

    Protein records and records without sequence content are skipped with a warning.
    """
    fold = ADAPTERS[adapter]
    results = []
    for record in records:
        if record.sequence is None:
            log.warning("%s: no sequence content, skipped", record.id)
            continue
        if record.type == "protein":
            log.warning("%s: protein sequence, skipped", record.id)
            continue
        sequence = record.sequence.upper().replace("T", "U")
        structure, mfe = fold(sequence)
        results.append(FoldResult(record.id, sequence, structure, mfe))
    return results


def write_fold_results(file: TextIO, results: list[FoldResult]) -> None:
    """Write results in RNAfold format: header, sequence, then structure and MFE."""
    file.writelines(
        f">{result.id}\n{result.sequence}\n{result.structure} ({result.mfe:6.2f})\n"
        for result in results
    )
