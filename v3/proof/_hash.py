"""
Canonical content_hash computation. Shared between snapshot_writer (write
side) and the ledger / verify code (audit side). Anyone running this
function over the same inputs gets the same hash — this is what makes
the ledger useful as tamper-evidence.

Inputs:
    snapshot_id     — sha-derived id from snapshot_writer
    total_score     — composite score (float)
    component_scores — dict {c1..c9: float}

Output: hex sha256 string.

This MUST match v3/signal/snapshot_writer.py::_content_hash. The two
implementations are intentionally duplicated (write side lives in the
internal signal package; audit side lives here so the proof module
doesn't depend on the writer). A unit / sanity check at module import
time would also work but is overkill for v3.0 — instead the daily
ledger run cross-checks naturally: a divergence shows up as an
immediate hash mismatch on Day 0.
"""
from __future__ import annotations

import hashlib
from typing import Mapping


def content_hash(snapshot_id: str, total_score: float, component_scores: Mapping[str, float]) -> str:
    parts = [snapshot_id, f"{float(total_score):.6f}"]
    for cid in sorted(component_scores):
        parts.append(f"{cid}={float(component_scores[cid]):.6f}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def daily_root(content_hashes: list[str]) -> str:
    """Roll all the day's content_hashes into one root hash.

    sha256 of sorted+concatenated hex strings, joined by '|'. Sorting is
    important so a different ordering of snapshots (DB row order is not
    guaranteed) yields the same root.
    """
    payload = "|".join(sorted(content_hashes))
    return hashlib.sha256(payload.encode()).hexdigest()
