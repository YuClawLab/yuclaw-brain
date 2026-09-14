"""Legacy adapter: the public replication log (docs/replication/replication_log.json) viewed as
`legacy-0` records. The original file and its consumers are untouched; the adapter is a VIEW.
An abbreviated binding stays PREFIX_ONLY — never expanded, never given a size."""
from __future__ import annotations

import re

from v3.receipts.contracts import LEGACY_VERSION

_PREFIX = re.compile(r"sha256\s+([0-9a-f]{8,63})…")


def adapt_entry(entry: dict, index: int) -> dict:
    aff = str(entry.get("operator_affiliation", "")).upper()
    rel = {"AFFILIATED": "OWNER-AFFILIATED", "UNAFFILIATED": "UNKNOWN"}.get(aff, "UNKNOWN")
    m = _PREFIX.search(str(entry.get("bundle", "")))
    res = str(entry.get("replication_result") or entry.get("result") or "").upper()
    outcome = "REPRODUCED" if res.startswith(("REPRODUCED", "PASS")) else ("FAILED" if res else "INCONCLUSIVE")
    return {"schema_version": LEGACY_VERSION, "attempt_id": f"legacy:{index}:{entry.get('date')}", "date": entry.get("date"),
            "relationship": rel, "execution_control": "UNKNOWN-LEGACY", "outcome": outcome,
            "machine_external": entry.get("replication_machine_external") is True,
            "artifact_type": "bundle" if m else None, "legacy_prefix": m.group(1) if m else None,
            "binding_completeness": "PREFIX_ONLY" if m else "NONE",
            "program_evidence": True, "exact_release_evidence": False,
            "note": "historical public log entry; affiliation is not a relationship class; prefix binding cannot support an exact-artifact claim"}


def adapt_log(log: dict) -> list[dict]:
    return [adapt_entry(e, i) for i, e in enumerate(log.get("replications", []))]
