"""Document-use receipts (v7): a local record that a research decision was taken on the basis of an
exact packet — INVESTIGATE_FURTHER, DISCARD_CLAIM or REQUEST_EVIDENCE — bound to the packet manifest
digest and the claim identifier. Export requires explicit permission; decision context stays private
(a bounded JSON object of scalars). Recording a use is a fact about a decision process; it is never
evidence of investment benefit, performance or institutional endorsement."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts.contracts import ContractError, format_ts
from v3.receipts.storage import resolve_store_root

DECISIONS = ("INVESTIGATE_FURTHER", "DISCARD_CLAIM", "REQUEST_EVIDENCE")
_HEX64 = re.compile(r"^[0-9a-f]{64}$"); _ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
PUBLIC_FIELDS = ("decision_id", "decision", "packet_manifest_digest", "claim_id", "decided_at", "synthetic")
MEANING = "a document-use receipt records that a research decision was taken on an exact packet; it is not evidence of investment benefit, performance or endorsement"


def validate_context(ctx) -> dict:
    if ctx is None:
        return {}
    if not isinstance(ctx, dict):
        raise ContractError("context: JSON object required (private; never exported)")
    if len(ctx) > 20:
        raise ContractError("context: at most 20 keys")
    for k, v in ctx.items():
        if not isinstance(k, str) or not k or len(k) > 64:
            raise ContractError("context: keys are strings of 1..64 chars")
        if isinstance(v, bool) or v is None or isinstance(v, (int, float)):
            continue
        if isinstance(v, str) and len(v) <= 2000:
            continue
        raise ContractError(f"context.{k}: scalar (string ≤2000 chars, number, bool, null) required")
    return dict(ctx)


class DecisionStore:
    def __init__(self, root):
        self.root = resolve_store_root(root)                 # location boundary BEFORE any write
        self.f = self.root / "decisions.jsonl"

    def _read(self):
        return [json.loads(l) for l in self.f.read_text().splitlines() if l.strip()] if self.f.exists() else []

    def record(self, decision_id: str, decision: str, *, packet_manifest_digest: str, claim_id: str, context: dict | None = None,
               export_permitted: bool = False, synthetic: bool, now: datetime | None = None) -> dict:
        if decision not in DECISIONS:
            raise ContractError(f"decision {decision!r} not in {list(DECISIONS)}")
        if not isinstance(decision_id, str) or not _ID.match(decision_id) or not isinstance(claim_id, str) or not _ID.match(claim_id):
            raise ContractError("decision_id/claim_id: registered id shape required")
        if not isinstance(packet_manifest_digest, str) or not _HEX64.match(packet_manifest_digest):
            raise ContractError("packet_manifest_digest: full sha256 required (binds the exact packet)")
        if not isinstance(export_permitted, bool):
            raise ContractError("export_permitted: bool required")
        ctx = validate_context(context)
        if any(r["decision_id"] == decision_id for r in self._read()):
            raise ContractError("decision_id already exists")
        rec = {"kind": "decision", "decision_id": decision_id, "decision": decision, "packet_manifest_digest": packet_manifest_digest, "claim_id": claim_id,
               "context": ctx, "export_permitted": export_permitted, "synthetic": bool(synthetic),
               "decided_at": format_ts(now or datetime.now(timezone.utc)), "disclaimer": MEANING}
        with self.f.open("a") as fh: fh.write(json.dumps(rec, sort_keys=True) + "\n")
        try: os.chmod(self.f, 0o600)
        except OSError: pass
        return rec

    def export(self, *, synthetic: bool) -> list[dict]:
        """Only records whose author permitted export, with the PUBLIC fields only (context never leaves)."""
        return [{k: r[k] for k in PUBLIC_FIELDS} for r in self._read() if r["export_permitted"] is True and r["synthetic"] == synthetic]

    def all(self) -> list[dict]:
        return self._read()
