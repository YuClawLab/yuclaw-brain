"""Local structured challenges (v7): a challenge binds an artifact identity (type + sha256 + length)
and a claim identifier to expected vs observed behavior. Dispositions: OPEN → CONFIRMED / REFUTED /
WITHDRAWN; a RESOLVED disposition must name a tested revised artifact (type + sha256 + length) and a
verification result, and it SUPERSEDES rather than erases the original finding. Sensitive details
stay in `private` (never exported). Aggregation always retains adverse and unresolved findings."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts.contracts import ContractError, format_ts, parse_ts, validate_binding_claim

DISPOSITIONS = ("OPEN", "CONFIRMED", "REFUTED", "WITHDRAWN", "RESOLVED")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ChallengeStore:
    def __init__(self, root):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        try: os.chmod(self.root, 0o700)
        except OSError: pass
        self.f = self.root / "challenges.jsonl"

    def _read(self):
        return [json.loads(l) for l in self.f.read_text().splitlines() if l.strip()] if self.f.exists() else []

    def _append(self, rec):
        with self.f.open("a") as fh: fh.write(json.dumps(rec, sort_keys=True) + "\n")

    def create(self, challenge_id: str, *, artifact: dict, claim_id: str, expected: str, observed: str, private: dict | None = None,
               synthetic: bool, now: datetime | None = None) -> dict:
        if not _ID.match(challenge_id or "") or not _ID.match(claim_id or ""):
            raise ContractError("challenge_id/claim_id: registered id shape required")
        if any(r["challenge_id"] == challenge_id for r in self._read()):
            raise ContractError("challenge_id already exists")
        for label, txt in (("expected", expected), ("observed", observed)):
            if not isinstance(txt, str) or not txt.strip() or len(txt) > 1000:
                raise ContractError(f"{label}: 1..1000 chars required")
        rec = {"kind": "challenge", "challenge_id": challenge_id, "artifact": validate_binding_claim(artifact, "artifact"), "claim_id": claim_id,
               "expected": expected, "observed": observed, "disposition": "OPEN", "supersedes": None, "resolution": None,
               "private": dict(private or {}), "synthetic": bool(synthetic), "created_at": format_ts(now or datetime.now(timezone.utc)), "version": 1}
        self._append(rec); return rec

    def current(self) -> dict[str, dict]:
        cur = {}
        for r in self._read(): cur[r["challenge_id"]] = r
        return cur

    def dispose(self, challenge_id: str, disposition: str, *, revised_artifact: dict | None = None, verification: str | None = None,
                reason: str = "", now: datetime | None = None) -> dict:
        if disposition not in DISPOSITIONS or disposition == "OPEN":
            raise ContractError(f"disposition {disposition!r} not allowed")
        cur = self.current().get(challenge_id)
        if cur is None:
            raise ContractError("unknown challenge_id")
        rec = dict(cur); rec["version"] = cur["version"] + 1; rec["supersedes"] = {"version": cur["version"], "disposition": cur["disposition"]}
        rec["disposition"] = disposition; rec["reason"] = reason[:500]; rec["updated_at"] = format_ts(now or datetime.now(timezone.utc))
        if disposition == "RESOLVED":
            if revised_artifact is None or not verification:
                raise ContractError("RESOLVED requires the tested revised artifact (type+sha256+length) and its verification result")
            ra = validate_binding_claim(revised_artifact, "revised_artifact")
            if (ra["sha256"], ra["size_bytes"]) == (cur["artifact"]["sha256"], cur["artifact"]["size_bytes"]):
                raise ContractError("RESOLVED must reference a REVISED artifact — the original bytes cannot resolve their own failure")
            rec["resolution"] = {"revised_artifact": ra, "verification": verification[:500], "original_finding_retained": True}
        self._append(rec); return rec

    def public_view(self, *, synthetic: bool) -> list[dict]:
        """Sanitized aggregation: adverse/unresolved findings retained; private never exported."""
        out = []
        for r in sorted(self.current().values(), key=lambda x: x["challenge_id"]):
            if r["synthetic"] != synthetic: continue
            out.append({"challenge_id": r["challenge_id"], "artifact": r["artifact"], "claim_id": r["claim_id"], "disposition": r["disposition"],
                        "version": r["version"], "created_at": r["created_at"], "synthetic": r["synthetic"],
                        "resolution": (None if not r.get("resolution") else {"revised_artifact": r["resolution"]["revised_artifact"], "original_finding_retained": True}),
                        "adverse": r["disposition"] in ("OPEN", "CONFIRMED")})
        return out

    def history(self, challenge_id: str) -> list[dict]:
        return [r for r in self._read() if r["challenge_id"] == challenge_id]
