"""Document-use receipts (v7): a local record that a research decision was taken on the basis of an
exact packet — INVESTIGATE_FURTHER, DISCARD_CLAIM or REQUEST_EVIDENCE — bound to the packet manifest
digest and the claim identifier. Export requires explicit permission; decision context stays private.
No investment benefit or institutional endorsement is implied or recorded."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts.contracts import ContractError, format_ts

DECISIONS = ("INVESTIGATE_FURTHER", "DISCARD_CLAIM", "REQUEST_EVIDENCE")
_HEX64 = re.compile(r"^[0-9a-f]{64}$"); _ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
PUBLIC_FIELDS = ("decision_id", "decision", "packet_manifest_digest", "claim_id", "decided_at", "synthetic")


class DecisionStore:
    def __init__(self, root):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        try: os.chmod(self.root, 0o700)
        except OSError: pass
        self.f = self.root / "decisions.jsonl"

    def _read(self):
        return [json.loads(l) for l in self.f.read_text().splitlines() if l.strip()] if self.f.exists() else []

    def record(self, decision_id: str, decision: str, *, packet_manifest_digest: str, claim_id: str, context: dict | None = None,
               export_permitted: bool = False, synthetic: bool, now: datetime | None = None) -> dict:
        if decision not in DECISIONS:
            raise ContractError(f"decision {decision!r} not in {list(DECISIONS)}")
        if not _ID.match(decision_id or "") or not _ID.match(claim_id or ""):
            raise ContractError("decision_id/claim_id: registered id shape required")
        if not _HEX64.match(packet_manifest_digest or ""):
            raise ContractError("packet_manifest_digest: full sha256 required (binds the exact packet)")
        if any(r["decision_id"] == decision_id for r in self._read()):
            raise ContractError("decision_id already exists")
        rec = {"kind": "decision", "decision_id": decision_id, "decision": decision, "packet_manifest_digest": packet_manifest_digest, "claim_id": claim_id,
               "context": dict(context or {}), "export_permitted": bool(export_permitted), "synthetic": bool(synthetic),
               "decided_at": format_ts(now or datetime.now(timezone.utc)),
               "disclaimer": "research decision record; no investment benefit or institutional endorsement implied"}
        with self.f.open("a") as fh: fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return rec

    def export(self, *, synthetic: bool) -> list[dict]:
        return [{k: r[k] for k in PUBLIC_FIELDS} for r in self._read() if r["export_permitted"] and r["synthetic"] == synthetic]

    def all(self) -> list[dict]:
        return self._read()
