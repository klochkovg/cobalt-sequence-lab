""" Normalizaiton helpers
"""
from __future__ import annotations

from Bio.Seq import Seq


def uppercase_result(records: Seq) -> int:
    """ uppercase the sequence, naive approach for now
        No data copying, actual replacement
    """
    for record in records:
        sequence = record['sequence']
        record['sequence'] = sequence.upper()
    return records