"""Report of the `inspect` command, shared by `inspect --json` and the REST API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import islice
from typing import Any

from cobalt.model.qc import RecordWarning, WarningKind
from cobalt.model.record import AnalysisResult, SequenceRecord


@dataclass(slots=True)
class InspectRecord:
    """One record of the `inspect` listing: the fields the text output shows.

    Computed fields are None for a record with a length but no sequence content (GenBank
    WGS/CONTIG); quality fields are None for formats without qualities (all but FASTQ).
    """

    id: str
    length: int
    sequence: str | None
    gc_fraction: float | None
    type: str
    molecule_type: str | None
    description: str
    organism: str | None
    mean_quality: float | None
    min_quality: int | None
    q30_fraction: float | None

    @classmethod
    def from_record(cls, record: SequenceRecord) -> InspectRecord:
        """Build a listing entry from a processed record."""
        return cls(
            id=record.id,
            length=record.length,
            sequence=record.sequence,
            gc_fraction=record.gc_fraction,
            type=record.type,
            molecule_type=record.molecule_type,
            description=record.description,
            organism=record.organism,
            mean_quality=record.mean_quality,
            min_quality=record.min_quality,
            q30_fraction=record.q30_fraction,
        )


@dataclass(slots=True)
class InspectReport:
    """File summary and record listing of one `inspect` input.

    For an empty file `records_num` is 0 and format and length fields are None.
    `records` is empty with `overview_only`, and holds at most `limit` records otherwise.
    """

    file: str
    records_num: int
    format: str | None
    compression: str | None
    min_length: int | None
    max_length: int | None
    mean_length: float | None
    # Number of records per molecule type, most common first
    molecule_types: dict[str, int] = field(default_factory=dict)
    # Number of warnings per kind; every kind is present, zero if not found
    warning_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[RecordWarning] = field(default_factory=list)
    records: list[InspectRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the report as a plain, JSON-serializable dict."""
        return asdict(self)


def build_inspect_report(
    file: str,
    result: AnalysisResult | None,
    compression: str | None,
    overview_only: bool = False,
    limit: int | None = None,
) -> InspectReport:
    """Build the `inspect` report of `file` from its analysis result (None for an empty file)."""
    if result is None:
        return InspectReport(
            file=file,
            records_num=0,
            format=None,
            compression=compression,
            min_length=None,
            max_length=None,
            mean_length=None,
            warning_counts={str(kind): 0 for kind in WarningKind},
        )
    records = [] if overview_only else list(islice(result.records, limit))
    return InspectReport(
        file=file,
        records_num=result.records_num,
        format=result.type,
        compression=compression,
        min_length=result.min,
        max_length=result.max,
        mean_length=result.mean,
        molecule_types=result.type_counts(),
        warning_counts={str(kind): count for kind, count in result.warning_counts().items()},
        warnings=list(result.warnings),
        records=[InspectRecord.from_record(record) for record in records],
    )
