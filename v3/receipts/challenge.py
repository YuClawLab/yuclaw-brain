"""Local structured challenges (v7): a challenge binds an artifact identity (type + sha256 + length)
and a claim identifier to expected vs observed behavior. Dispositions: OPEN → CONFIRMED / REFUTED /
WITHDRAWN / RESOLVED. The challenger cannot dispose their own finding: CONFIRMED, REFUTED and RESOLVED
require a reviewer appointment from the trusted review store (same directory) — for a REAL challenge a
DESIGNATED appointment; SYNTHETIC appointments may dispose synthetic challenges only; HELD authority
disposes nothing. WITHDRAWN is the challenger's own retraction and keeps the record.

RESOLVED requires a VERIFICATION RECORD that this store itself produced by executing the permitted
deterministic verifier for the revised artifact (`verify_revision`): `packet-verify` runs the existing
offline packet verification and binds the revised artifact to an INCLUDED artifact whose bytes were
observed in that run; `receipt` resolves a qualified, successful receipt in the same store whose exact
binding is the revised artifact. A submitted label, a correctly shaped digest, or a record for another
challenge / artifact / non-success leaves the resolution unestablished with its reason. Every disposition
SUPERSEDES rather than erases the original finding. Sensitive details stay in `private` (never exported).
Aggregation always retains adverse and unresolved findings."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts import verify as _verify
from v3.receipts.contracts import ContractError, canonical_json, format_ts, validate_binding_claim
from v3.receipts.storage import resolve_store_root

DISPOSITIONS = ("OPEN", "CONFIRMED", "REFUTED", "WITHDRAWN", "RESOLVED")
TRUSTED_DISPOSITIONS = ("CONFIRMED", "REFUTED", "RESOLVED")
VERIFICATION_METHODS = ("packet-verify", "receipt")
# Machine-checkable claim CRITERIA and the ONE allowlisted verifier that can evaluate each. A challenge states
# its criterion at creation; a verification record for another criterion, or a generic replay-success label,
# never resolves it. "general" criteria are resolved only by a separately authenticated reviewer EVALUATION.
CRITERIA = {
    "packet-integrity-and-replay": {"verifier": "packet-verify", "predicate": "packet.verify(packet containing the revised artifact) == SUCCESS and the revised bytes are an observed INCLUDED artifact"},
    "artifact-reproduction-by-qualified-receipt": {"verifier": "receipt", "predicate": "a qualified, successful receipt of the same provenance binds exactly the revised artifact"},
    "general": {"verifier": None, "predicate": "stated in the challenge text; requires an explicit reviewer evaluation of that statement"},
}
EVALUATION_OUTCOMES = ("SATISFIED", "NOT_SATISFIED", "NOT_EVALUATED")


def _verifier_identity(method: str) -> dict:
    try:
        import importlib.metadata as _m
        ver = _m.version("yuclaw")
    except Exception:
        ver = "checkout"
    return {"module": {"packet-verify": "v3.receipts.packet.verify", "receipt": "v3.receipts.counting.derive"}[method], "package_version": ver}
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ChallengeStore:
    def __init__(self, root):
        self.root = resolve_store_root(root)                 # location boundary BEFORE any write
        self.f = self.root / "challenges.jsonl"
        self.f_ver = self.root / "verifications.jsonl"
        self.f_eval = self.root / "evaluations.jsonl"

    def _read(self, f=None):
        f = f or self.f
        return [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []

    def _append(self, rec, f=None):
        f = f or self.f
        with f.open("a") as fh: fh.write(json.dumps(rec, sort_keys=True) + "\n")
        try: os.chmod(f, 0o600)
        except OSError: pass

    def create(self, challenge_id: str, *, artifact: dict, claim_id: str, expected: str, observed: str, private: dict | None = None,
               synthetic: bool, criterion: str = "general", now: datetime | None = None) -> dict:
        if not isinstance(challenge_id, str) or not _ID.match(challenge_id) or not isinstance(claim_id, str) or not _ID.match(claim_id):
            raise ContractError("challenge_id/claim_id: registered id shape required")
        if criterion not in CRITERIA:
            raise ContractError(f"criterion must be one of {list(CRITERIA)}")
        if any(r["challenge_id"] == challenge_id for r in self._read()):
            raise ContractError("challenge_id already exists")
        for label, txt in (("expected", expected), ("observed", observed)):
            if not isinstance(txt, str) or not txt.strip() or len(txt) > 1000:
                raise ContractError(f"{label}: 1..1000 chars required")
        if private is not None and not isinstance(private, dict):
            raise ContractError("private: object or null")
        rec = {"kind": "challenge", "challenge_id": challenge_id, "artifact": validate_binding_claim(artifact, "artifact"), "claim_id": claim_id, "criterion": criterion,
               "expected": expected, "observed": observed, "disposition": "OPEN", "supersedes": None, "resolution": None, "disposed_by": None,
               "private": dict(private or {}), "synthetic": bool(synthetic), "created_at": format_ts(now or datetime.now(timezone.utc)), "version": 1}
        self._append(rec); return rec

    def current(self) -> dict[str, dict]:
        cur = {}
        for r in self._read(): cur[r["challenge_id"]] = r
        return cur

    # ---------- verification records (produced by executing the permitted verifier; never submitted)
    def verification(self, verification_id: str) -> dict | None:
        for r in self._read(self.f_ver):
            if r.get("verification_id") == verification_id:
                return r
        return None

    def verify_revision(self, challenge_id: str, *, revised_artifact: dict, method: str, packet_dir=None, receipt_digest: str | None = None,
                        now: datetime | None = None) -> dict:
        """Execute the deterministic verifier for a revised artifact and append an immutable verification record
        bound to this challenge. Returns the record (result SUCCESS or FAILURE with its reason)."""
        cur = self.current().get(challenge_id)
        if cur is None:
            raise ContractError("unknown challenge_id")
        ra = validate_binding_claim(revised_artifact, "revised_artifact")
        if ra["artifact_type"] != cur["artifact"]["artifact_type"]:
            raise ContractError("revised artifact must have the challenged artifact's type")
        if method not in VERIFICATION_METHODS:
            raise ContractError(f"method must be one of {list(VERIFICATION_METHODS)}")
        ts = format_ts(now or datetime.now(timezone.utc))
        criterion = cur.get("criterion", "general"); expected_verifier = CRITERIA[criterion]["verifier"]
        if expected_verifier != method:
            rec = {"kind": "verification", "challenge_id": challenge_id, "claim_id": cur["claim_id"], "criterion": criterion, "challenged_artifact": cur["artifact"], "revised_artifact": ra,
                   "method": method, "verifier": _verifier_identity(method), "result": "NOT_EVALUATED",
                   "reason": (f"criterion {criterion!r} is not testable by verifier {method!r}" + ("; it needs an explicit reviewer evaluation" if expected_verifier is None else f"; its allowlisted verifier is {expected_verifier!r}")),
                   "evidence": {}, "executed_at": ts, "executed_by": "store.verify_revision", "synthetic": cur["synthetic"]}
            rec["verification_id"] = hashlib.sha256(canonical_json(rec)).hexdigest(); self._append(rec, self.f_ver); return rec
        if method == "packet-verify":
            if packet_dir is None:
                raise ContractError("packet-verify needs packet_dir")
            from v3.receipts import packet
            res = packet.verify(packet_dir)
            hit = [c for c in res["checks"] if c.get("check") == "sha256+length" and c.get("ok") is True
                   and (c["observed"]["sha256"], c["observed"]["size_bytes"]) == (ra["sha256"], ra["size_bytes"])]
            if res["result"] != "SUCCESS":
                result, reason = "FAILURE", f"packet verification {res['result']}: {res.get('first_discrepancy')}"
            elif not hit:
                result, reason = "FAILURE", "the revised artifact's bytes are not among the packet's observed INCLUDED artifacts"
            else:
                result, reason = "SUCCESS", "packet verification SUCCESS and the revised artifact's exact bytes were observed in it"
            evidence = {"manifest_digest": res.get("manifest_digest"), "packet_result": res["result"], "observed_path": hit[0]["path"] if hit else None,
                        "replay": (res.get("replay") if isinstance(res.get("replay"), dict) else {"note": res.get("replay")})}
        else:
            if not isinstance(receipt_digest, str) or not _HEX64.match(receipt_digest):
                raise ContractError("receipt method needs a full receipt digest")
            from v3.receipts import counting
            from v3.receipts.store import Store
            rows = [r for r in counting.derive(Store(self.root), synthetic=cur["synthetic"]) if r["digest"] == receipt_digest]
            if not rows:
                result, reason, row = "FAILURE", "no current receipt with that digest in this store (same provenance as the challenge)", None
            else:
                row = rows[0]; b = row["submission"]["artifact_binding"]
                if (b["artifact_type"], b["sha256"], b["size_bytes"]) != (ra["artifact_type"], ra["sha256"], ra["size_bytes"]):
                    result, reason = "FAILURE", "the receipt binds a different artifact than the revised artifact"
                elif not row["qualified"] or not row["successful"]:
                    result, reason = "FAILURE", "the receipt is not a qualified successful attempt: " + "; ".join(row["reasons"] or ["outcome not REPRODUCED"])
                else:
                    result, reason = "SUCCESS", "qualified successful receipt binds the revised artifact"
            evidence = {"receipt_digest": receipt_digest, "qualified": bool(row and row["qualified"]), "successful": bool(row and row["successful"]),
                        "review_appointment_id": (row["review"] or {}).get("appointment_id") if row else None}
        rec = {"kind": "verification", "challenge_id": challenge_id, "claim_id": cur["claim_id"], "criterion": criterion, "challenged_artifact": cur["artifact"], "revised_artifact": ra,
               "method": method, "verifier": _verifier_identity(method), "result": result, "reason": reason, "evidence": evidence, "executed_at": ts, "executed_by": "store.verify_revision", "synthetic": cur["synthetic"]}
        rec["verification_id"] = hashlib.sha256(canonical_json(rec)).hexdigest()
        self._append(rec, self.f_ver); return rec

    def evaluate(self, challenge_id: str, *, reviewer_role: str, token: str, outcome: str, statement: str, revised_artifact: dict | None = None,
                 now: datetime | None = None) -> dict:
        """A separately authenticated reviewer EVALUATION of the challenge's stated criterion (the only way a
        'general' criterion is evaluated). DESIGNATED authority for real challenges; SYNTHETIC for synthetic; HELD never."""
        cur = self.current().get(challenge_id)
        if cur is None:
            raise ContractError("unknown challenge_id")
        if outcome not in EVALUATION_OUTCOMES:
            raise ContractError(f"outcome must be one of {list(EVALUATION_OUTCOMES)}")
        if not isinstance(statement, str) or not statement.strip() or len(statement) > 2000:
            raise ContractError("statement: 1..2000 chars required (what was examined and why the criterion holds or not)")
        from v3.receipts.store import Store, ReviewAuthorityError
        appt = Store(self.root).authorize(reviewer_role, token)
        if appt["authority"] == "HELD" or (not cur["synthetic"] and appt["authority"] != "DESIGNATED"):
            raise ReviewAuthorityError("evaluation of a real challenge needs a DESIGNATED appointment; HELD authority evaluates nothing")
        ra = validate_binding_claim(revised_artifact, "revised_artifact") if revised_artifact is not None else None
        rec = {"kind": "evaluation", "challenge_id": challenge_id, "claim_id": cur["claim_id"], "criterion": cur.get("criterion", "general"), "challenged_artifact": cur["artifact"],
               "revised_artifact": ra, "outcome": outcome, "statement": statement, "evaluated_at": format_ts(now or datetime.now(timezone.utc)),
               "evaluator": {"role": appt["role"], "authority": appt["authority"], "appointment_id": appt["appointment_id"]}, "synthetic": cur["synthetic"]}
        rec["evaluation_id"] = hashlib.sha256(canonical_json(rec)).hexdigest()
        self._append(rec, self.f_eval); return rec

    def evaluation(self, evaluation_id: str) -> dict | None:
        for r in self._read(self.f_eval):
            if r.get("evaluation_id") == evaluation_id:
                return r
        return None

    def resolve_evaluation(self, challenge_id: str, revised_artifact: dict, evaluation_id) -> dict:
        if not isinstance(evaluation_id, str) or not _HEX64.match(evaluation_id):
            raise ContractError("evaluation_id: full sha256 of an evaluation record required")
        rec = self.evaluation(evaluation_id)
        if rec is None:
            raise ContractError("unknown evaluation reference: no evaluation was recorded by this store for that id")
        if rec["challenge_id"] != challenge_id:
            raise ContractError("evaluation record belongs to another challenge")
        if rec["revised_artifact"] != validate_binding_claim(revised_artifact, "revised_artifact"):
            raise ContractError("evaluation record is for a different revised artifact")
        if rec["outcome"] != "SATISFIED":
            raise ContractError(f"evaluation outcome is {rec['outcome']}: the stated criterion is not established")
        return rec

    def resolve_verification(self, challenge_id: str, revised_artifact: dict, verification_id) -> dict:
        """Resolve a reference to a verification record and check it establishes THIS resolution."""
        if not isinstance(verification_id, str) or not _HEX64.match(verification_id):
            raise ContractError("verification_id: full sha256 of a verification record required (a label is not a test)")
        rec = self.verification(verification_id)
        if rec is None:
            raise ContractError("unknown verification reference: no record was produced by this store for that id")
        if rec["challenge_id"] != challenge_id:
            raise ContractError("verification record belongs to another challenge")
        ra = validate_binding_claim(revised_artifact, "revised_artifact")
        if rec["revised_artifact"] != ra:
            raise ContractError("verification record is for a different revised artifact")
        if rec["result"] != "SUCCESS":
            raise ContractError(f"verification did not succeed ({rec['result']}): {rec['reason']}")
        return rec

    def dispose(self, challenge_id: str, disposition: str, *, reviewer_role: str | None = None, token: str | None = None,
                revised_artifact: dict | None = None, revised_bytes: bytes | None = None, revised_path=None, allowed_roots=(),
                verification_id: str | None = None, evaluation_id: str | None = None, reason: str = "", now: datetime | None = None) -> dict:
        if disposition not in DISPOSITIONS or disposition == "OPEN":
            raise ContractError(f"disposition {disposition!r} not allowed")
        cur = self.current().get(challenge_id)
        if cur is None:
            raise ContractError("unknown challenge_id")
        ts = format_ts(now or datetime.now(timezone.utc))
        actor = {"kind": "challenger", "authority": None, "appointment_id": None}
        if disposition in TRUSTED_DISPOSITIONS:
            from v3.receipts.store import Store, ReviewAuthorityError   # same private directory holds the appointments
            appt = Store(self.root).authorize(reviewer_role, token)      # raises ReviewAuthorityError (a ContractError)
            if appt["authority"] == "HELD":
                raise ReviewAuthorityError("HELD (ambiguous legacy) authority cannot dispose any challenge; re-designate explicitly")
            if not cur["synthetic"] and appt["authority"] != "DESIGNATED":
                raise ReviewAuthorityError(f"a REAL challenge needs a DESIGNATED appointment; {appt['authority']} authority cannot affect real evidence")
            actor = {"kind": "reviewer", "role": appt["role"], "authority": appt["authority"], "appointment_id": appt["appointment_id"]}
        rec = dict(cur); rec["version"] = cur["version"] + 1; rec["supersedes"] = {"version": cur["version"], "disposition": cur["disposition"]}
        rec["disposition"] = disposition; rec["reason"] = str(reason)[:500]; rec["updated_at"] = ts; rec["disposed_by"] = actor
        if disposition == "RESOLVED":
            criterion = cur.get("criterion", "general")
            if revised_artifact is None or (verification_id is None and evaluation_id is None):
                raise ContractError("RESOLVED requires the tested revised artifact (type+sha256+length, with its actual bytes) and a verification record (verifier-backed criterion) or an evaluation record (general criterion)")
            ra = validate_binding_claim(revised_artifact, "revised_artifact")
            if ra["artifact_type"] != cur["artifact"]["artifact_type"]:
                raise ContractError("revised artifact must have the challenged artifact's type")
            if (ra["sha256"], ra["size_bytes"]) == (cur["artifact"]["sha256"], cur["artifact"]["size_bytes"]):
                raise ContractError("RESOLVED must reference a REVISED artifact — the original bytes cannot resolve their own failure")
            if revised_bytes is None and revised_path is None:
                raise ContractError("RESOLVED requires the revised artifact's actual bytes (revised_bytes or revised_path) — a digest alone is not a test")
            obs = _verify.observe(ra, data=revised_bytes, path=revised_path, allowed_roots=allowed_roots, now=now)
            if not obs["verified"]:
                raise ContractError("revised artifact bytes do not equal the claimed revised binding (sha256 + length)")
            if CRITERIA[criterion]["verifier"] is None:
                if evaluation_id is None:
                    raise ContractError(f"criterion {criterion!r} has no allowlisted verifier: RESOLVED needs an evaluation record (NOT_EVALUATED otherwise)")
                ev = self.resolve_evaluation(challenge_id, ra, evaluation_id)
                rec["resolution"] = {"revised_artifact": ra, "revised_observation": obs, "evaluation_id": ev["evaluation_id"], "verification_method": "reviewer-evaluation",
                                     "criterion": criterion, "verification_executed_at": ev["evaluated_at"], "original_finding_retained": True}
            else:
                if verification_id is None:
                    raise ContractError(f"criterion {criterion!r} is verifier-backed ({CRITERIA[criterion]['verifier']}): RESOLVED needs its verification record, not an evaluation")
                ver = self.resolve_verification(challenge_id, ra, verification_id)
                if ver.get("criterion", "general") != criterion:
                    raise ContractError("verification record was produced for a different criterion")
                rec["resolution"] = {"revised_artifact": ra, "revised_observation": obs, "verification_id": ver["verification_id"], "verification_method": ver["method"],
                                     "criterion": criterion, "verification_executed_at": ver["executed_at"], "original_finding_retained": True}
        self._append(rec); return rec

    def public_view(self, *, synthetic: bool) -> list[dict]:
        """Sanitized aggregation: adverse/unresolved findings retained; private never exported."""
        out = []
        for r in sorted(self.current().values(), key=lambda x: x["challenge_id"]):
            if r["synthetic"] != synthetic: continue
            by = r.get("disposed_by") or {}
            out.append({"challenge_id": r["challenge_id"], "artifact": r["artifact"], "claim_id": r["claim_id"], "criterion": r.get("criterion", "general"), "disposition": r["disposition"],
                        "version": r["version"], "created_at": r["created_at"], "synthetic": r["synthetic"],
                        "disposed_by_authority": by.get("authority") if by.get("kind") == "reviewer" else ("challenger" if by else None),
                        "resolution": (None if not r.get("resolution") else {"revised_artifact": r["resolution"]["revised_artifact"],
                                                                             "verification_method": r["resolution"]["verification_method"], "original_finding_retained": True}),
                        "adverse": r["disposition"] in ("OPEN", "CONFIRMED")})
        return out

    def history(self, challenge_id: str) -> list[dict]:
        return [r for r in self._read() if r["challenge_id"] == challenge_id]
