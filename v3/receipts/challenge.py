"""Local structured challenges (v7): a challenge binds an artifact identity (type + sha256 + length)
and a claim identifier to expected vs observed behavior. Dispositions: OPEN → CONFIRMED / REFUTED /
WITHDRAWN / RESOLVED. The challenger cannot dispose their own finding: CONFIRMED, REFUTED and RESOLVED
require a reviewer appointment from the trusted review store (same directory); WITHDRAWN is the
challenger's own retraction and keeps the record. RESOLVED must name a REVISED artifact whose ACTUAL
bytes were observed to equal the revised binding, plus a structured verification result — a revised
digest alone is not a resolution test. Every disposition SUPERSEDES rather than erases the original
finding. Sensitive details stay in `private` (never exported). Aggregation always retains adverse and
unresolved findings."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts import verify as _verify
from v3.receipts.contracts import ContractError, format_ts, validate_binding_claim

DISPOSITIONS = ("OPEN", "CONFIRMED", "REFUTED", "WITHDRAWN", "RESOLVED")
TRUSTED_DISPOSITIONS = ("CONFIRMED", "REFUTED", "RESOLVED")
VERIFICATION_METHODS = ("packet-verify", "replay-lab", "receipt")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def validate_verification(v) -> dict:
    """A resolution test is STRUCTURED: method (closed), result SUCCESS, and a full digest reference
    (packet manifest digest, bundle sha256 or receipt digest). Free text is not a test."""
    if not isinstance(v, dict):
        raise ContractError("verification: object {method, result, reference} required (free text is not a resolution test)")
    if set(v) - {"method", "result", "reference", "note"}:
        raise ContractError("verification: unexpected keys")
    if v.get("method") not in VERIFICATION_METHODS:
        raise ContractError(f"verification.method must be one of {list(VERIFICATION_METHODS)}")
    if v.get("result") != "SUCCESS":
        raise ContractError("verification.result must be SUCCESS for a RESOLVED disposition")
    if not isinstance(v.get("reference"), str) or not _HEX64.match(v["reference"]):
        raise ContractError("verification.reference: full sha256 of the packet manifest / bundle / receipt required")
    note = v.get("note", "")
    if not isinstance(note, str) or len(note) > 500:
        raise ContractError("verification.note: string ≤500 chars")
    return {"method": v["method"], "result": "SUCCESS", "reference": v["reference"], "note": note}


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
        try: os.chmod(self.f, 0o600)
        except OSError: pass

    def create(self, challenge_id: str, *, artifact: dict, claim_id: str, expected: str, observed: str, private: dict | None = None,
               synthetic: bool, now: datetime | None = None) -> dict:
        if not _ID.match(challenge_id or "") or not _ID.match(claim_id or ""):
            raise ContractError("challenge_id/claim_id: registered id shape required")
        if any(r["challenge_id"] == challenge_id for r in self._read()):
            raise ContractError("challenge_id already exists")
        for label, txt in (("expected", expected), ("observed", observed)):
            if not isinstance(txt, str) or not txt.strip() or len(txt) > 1000:
                raise ContractError(f"{label}: 1..1000 chars required")
        if private is not None and not isinstance(private, dict):
            raise ContractError("private: object or null")
        rec = {"kind": "challenge", "challenge_id": challenge_id, "artifact": validate_binding_claim(artifact, "artifact"), "claim_id": claim_id,
               "expected": expected, "observed": observed, "disposition": "OPEN", "supersedes": None, "resolution": None, "disposed_by": None,
               "private": dict(private or {}), "synthetic": bool(synthetic), "created_at": format_ts(now or datetime.now(timezone.utc)), "version": 1}
        self._append(rec); return rec

    def current(self) -> dict[str, dict]:
        cur = {}
        for r in self._read(): cur[r["challenge_id"]] = r
        return cur

    def dispose(self, challenge_id: str, disposition: str, *, reviewer_role: str | None = None, token: str | None = None,
                revised_artifact: dict | None = None, revised_bytes: bytes | None = None, revised_path=None, allowed_roots=(),
                verification: dict | None = None, reason: str = "", now: datetime | None = None) -> dict:
        if disposition not in DISPOSITIONS or disposition == "OPEN":
            raise ContractError(f"disposition {disposition!r} not allowed")
        cur = self.current().get(challenge_id)
        if cur is None:
            raise ContractError("unknown challenge_id")
        ts = format_ts(now or datetime.now(timezone.utc))
        actor = {"kind": "challenger", "authority": None, "appointment_id": None}
        if disposition in TRUSTED_DISPOSITIONS:
            from v3.receipts.store import Store              # same private directory holds the appointments
            appt = Store(self.root).authorize(reviewer_role, token)   # raises ReviewAuthorityError (a ContractError)
            actor = {"kind": "reviewer", "role": appt["role"], "authority": appt["authority"], "appointment_id": appt["appointment_id"]}
        rec = dict(cur); rec["version"] = cur["version"] + 1; rec["supersedes"] = {"version": cur["version"], "disposition": cur["disposition"]}
        rec["disposition"] = disposition; rec["reason"] = str(reason)[:500]; rec["updated_at"] = ts; rec["disposed_by"] = actor
        if disposition == "RESOLVED":
            if revised_artifact is None or verification is None:
                raise ContractError("RESOLVED requires the tested revised artifact (type+sha256+length, with its actual bytes) and a structured verification result")
            ra = validate_binding_claim(revised_artifact, "revised_artifact")
            if (ra["sha256"], ra["size_bytes"]) == (cur["artifact"]["sha256"], cur["artifact"]["size_bytes"]):
                raise ContractError("RESOLVED must reference a REVISED artifact — the original bytes cannot resolve their own failure")
            if revised_bytes is None and revised_path is None:
                raise ContractError("RESOLVED requires the revised artifact's actual bytes (revised_bytes or revised_path) — a digest alone is not a test")
            obs = _verify.observe(ra, data=revised_bytes, path=revised_path, allowed_roots=allowed_roots, now=now)
            if not obs["verified"]:
                raise ContractError("revised artifact bytes do not equal the claimed revised binding (sha256 + length)")
            rec["resolution"] = {"revised_artifact": ra, "revised_observation": obs, "verification": validate_verification(verification), "original_finding_retained": True}
        self._append(rec); return rec

    def public_view(self, *, synthetic: bool) -> list[dict]:
        """Sanitized aggregation: adverse/unresolved findings retained; private never exported."""
        out = []
        for r in sorted(self.current().values(), key=lambda x: x["challenge_id"]):
            if r["synthetic"] != synthetic: continue
            by = r.get("disposed_by") or {}
            out.append({"challenge_id": r["challenge_id"], "artifact": r["artifact"], "claim_id": r["claim_id"], "disposition": r["disposition"],
                        "version": r["version"], "created_at": r["created_at"], "synthetic": r["synthetic"],
                        "disposed_by_authority": by.get("authority") if by.get("kind") == "reviewer" else ("challenger" if by else None),
                        "resolution": (None if not r.get("resolution") else {"revised_artifact": r["resolution"]["revised_artifact"],
                                                                             "verification_method": r["resolution"]["verification"]["method"], "original_finding_retained": True}),
                        "adverse": r["disposition"] in ("OPEN", "CONFIRMED")})
        return out

    def history(self, challenge_id: str) -> list[dict]:
        return [r for r in self._read() if r["challenge_id"] == challenge_id]
