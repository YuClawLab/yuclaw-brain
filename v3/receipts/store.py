"""Local receipt store (v7): append-only JSON-lines files under one private directory.

  submissions.jsonl  — validated SUBMISSIONS with import provenance (synthetic flag set by the
                       IMPORT CALL, never by the participant), version number and digest.
  observations.jsonl — OBSERVATIONS keyed by submission digest (from verify.observe).
  reviews.jsonl      — REVIEW decisions from the TRUSTED review store, bound to a receipt digest
                       and policy version; only an authorized reviewer role recorded in
                       reviewers.json can add one. reviewers.json is operator-controlled; when it
                       declares `designated: false` every review is marked authority SYNTHETIC and
                       real qualification stays pending.
  secret.key         — store-local random key for opaque pseudonyms (never exported).
No network, no database. The store never mutates or deletes an earlier line.
"""
from __future__ import annotations

import hmac
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts.contracts import (ContractError, POLICY_VERSION, REVIEW_STATES, digest, format_ts, validate_submission)


class ReviewAuthorityError(ContractError):
    """The review was not issued by an authorized reviewer role."""


class Store:
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        self.f_sub = self.root / "submissions.jsonl"
        self.f_obs = self.root / "observations.jsonl"
        self.f_rev = self.root / "reviews.jsonl"
        self.f_auth = self.root / "reviewers.json"
        self.f_key = self.root / "secret.key"
        if not self.f_key.exists():
            self.f_key.write_text(secrets.token_hex(32)); os.chmod(self.f_key, 0o600)
        if not self.f_auth.exists():
            self.f_auth.write_text(json.dumps({"designated": False, "roles": {}}, indent=1) + "\n"); os.chmod(self.f_auth, 0o600)

    # ---------- primitives
    def _append(self, f: Path, rec: dict):
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        try:
            os.chmod(f, 0o600)
        except OSError:
            pass

    def _read(self, f: Path) -> list[dict]:
        if not f.exists():
            return []
        return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]

    # ---------- submissions
    def import_submission(self, raw: dict, *, synthetic: bool, received_at: datetime | None = None) -> dict:
        """Trusted import path. `synthetic` is the IMPORT CALL's statement of provenance — a participant
        flag in `raw` is stripped by the contract and never consulted. Same attempt_id with different
        content and no `supersedes` → conflict error; byte-equivalent duplicate → collapsed (no new line)."""
        sub, diagnostics = validate_submission(raw)
        d = digest(sub)
        existing = [r for r in self._read(self.f_sub) if r["submission"]["attempt_id"] == sub["attempt_id"]]
        current = existing[-1] if existing else None
        if current is not None:
            if current["digest"] == d:
                return dict(current, duplicate=True)                      # collapse deterministically
            if sub.get("supersedes") is None or sub["supersedes"]["digest"] != current["digest"]:
                raise ContractError(f"conflicting record for attempt_id {sub['attempt_id']!r}: a different version exists; "
                                    f"a correction must set supersedes.digest = {current['digest'][:16]}… with a reason")
            if current["provenance"]["synthetic"] != synthetic:
                raise ContractError("a correction cannot change provenance (synthetic vs real)")
        rec = {"kind": "submission", "digest": d, "version": (current["version"] + 1) if current else 1,
               "provenance": {"synthetic": bool(synthetic), "imported_at": format_ts(received_at or datetime.now(timezone.utc)), "path": "store.import_submission"},
               "diagnostics": diagnostics, "submission": sub}
        self._append(self.f_sub, rec)
        return rec

    def current_submissions(self) -> dict[str, dict]:
        cur: dict[str, dict] = {}
        for r in self._read(self.f_sub):
            cur[r["submission"]["attempt_id"]] = r          # last version wins; earlier lines stay inspectable
        return cur

    def history(self, attempt_id: str) -> list[dict]:
        return [r for r in self._read(self.f_sub) if r["submission"]["attempt_id"] == attempt_id]

    # ---------- observations
    def add_observation(self, receipt_digest: str, observation: dict) -> dict:
        rec = {"kind": "observation", "receipt_digest": receipt_digest, "observation": observation}
        self._append(self.f_obs, rec)
        return rec

    def observation_for(self, receipt_digest: str) -> dict | None:
        obs = [r["observation"] for r in self._read(self.f_obs) if r["receipt_digest"] == receipt_digest]
        return obs[-1] if obs else None

    # ---------- reviews (trusted)
    def authority(self) -> dict:
        return json.loads(self.f_auth.read_text())

    def designate_reviewer(self, role: str, token: str, *, designated: bool) -> None:
        """Operator action (never reachable from a submission). `designated=False` keeps authority SYNTHETIC."""
        a = self.authority()
        a["designated"] = bool(designated)
        a["roles"][role] = hashlib.sha256(token.encode()).hexdigest()
        self.f_auth.write_text(json.dumps(a, indent=1) + "\n")

    def add_review(self, receipt_digest: str, state: str, *, reviewer_role: str, token: str, reason: str = "", now: datetime | None = None) -> dict:
        if state not in REVIEW_STATES:
            raise ContractError(f"review state {state!r} not in {list(REVIEW_STATES)}")
        a = self.authority()
        h = a["roles"].get(reviewer_role)
        if h is None or not hmac.compare_digest(h, hashlib.sha256(token.encode()).hexdigest()):
            raise ReviewAuthorityError(f"reviewer role {reviewer_role!r} is not authorized in this store")
        if not any(r["digest"] == receipt_digest for r in self._read(self.f_sub)):
            raise ContractError("review must bind to an existing receipt digest")
        rec = {"kind": "review", "receipt_digest": receipt_digest, "policy_version": POLICY_VERSION, "state": state,
               "reviewer_role": reviewer_role, "authority": "DESIGNATED" if a.get("designated") else "SYNTHETIC",
               "decided_at": format_ts(now or datetime.now(timezone.utc)), "reason": reason[:500]}
        self._append(self.f_rev, rec)
        return rec

    def review_for(self, receipt_digest: str) -> dict | None:
        revs = [r for r in self._read(self.f_rev) if r["receipt_digest"] == receipt_digest]
        return revs[-1] if revs else None

    # ---------- pseudonyms
    def pseudonym(self, participant_id: str) -> str:
        key = self.f_key.read_text().strip().encode()
        return "p-" + hmac.new(key, participant_id.encode(), hashlib.sha256).hexdigest()[:16]
