"""Statistics data structures and helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from enum import Enum
from typing import Any

from cobalt.model.record import SequenceRecord


@dataclass(slots=True)
class RecordStats:
    """Basic stats for a sequence collection."""

    n_records: int
    min_length: int
    max_length: int
    mean_length: float


def compute_record_stats(lengths: list[int]) -> RecordStats:
    """Compute length-based stats for records.

    Stub implementation.
    """
    raise NotImplementedError("compute_record_stats is not implemented yet")


@dataclass(slots=True)
class StatsRow:
    """One row of the `stats` table, shared by the CSV and JSON output and the REST API.

    Field order is the column order. Annotation fields are None when the source
    format has no such annotation (e.g. FASTA).
    """

    id: str
    length: int
    description: str
    gc_fraction: float | None
    type: str
    source_format: str
    alphabetic_class: str
    ambiguity_fraction: float
    invalid_char_count: int
    organism: str | None
    molecule_type: str | None
    topology: str | None
    feature_count: int

    @classmethod
    def from_record(cls, record: SequenceRecord) -> StatsRow:
        """Build a row from a processed record."""
        return cls(
            id=record.id,
            length=record.length,
            description=record.description,
            gc_fraction=record.gc_fraction,
            type=record.type,
            source_format=record.source_format,
            alphabetic_class=record.alphabetic_class,
            ambiguity_fraction=record.ambiguity_fraction,
            invalid_char_count=record.invalid_char_count,
            organism=record.organism,
            molecule_type=record.molecule_type,
            topology=record.topology,
            feature_count=record.feature_count,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the row as a plain dict, keys in column order."""
        return asdict(self)


STATS_FIELDNAMES = [f.name for f in fields(StatsRow)]


class SortKey(Enum):
    """Columns the stats table can be sorted by."""

    ID = "id"
    LENGTH = "length"


def build_stats_rows(
    records: Iterable[SequenceRecord],
    sort: SortKey | None = None,
    descending: bool = False,
) -> list[StatsRow]:
    """Build stats rows, in input order unless `sort` is given (the sort is stable)."""
    rows = [StatsRow.from_record(record) for record in records]
    if sort is not None:
        rows.sort(key=lambda row: getattr(row, sort.value), reverse=descending)
    return rows
