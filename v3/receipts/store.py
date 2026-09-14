"""Local receipt store (v7): append-only JSON-lines files under one private directory.

  submissions.jsonl  — validated SUBMISSIONS with import provenance (synthetic flag set by the
                       IMPORT CALL, never by the participant), version number and digest.
  observations.jsonl — OBSERVATIONS keyed by submission digest; each is validated against the exact
                       artifact binding of that receipt (a caller cannot mark FULL).
  reviews.jsonl      — REVIEW decisions from the TRUSTED review store, bound to a receipt digest,
                       the policy version and the reviewer's APPOINTMENT.
  reviewers.json     — current appointments (format `reviewers-2`): one entry per role with the
                       credential hash, its own designated flag, its policy version and appointment id.
                       Designation belongs to the appointment — never to a store-wide Boolean.
  appointments.jsonl — private, append-only record of every appointment / revocation / migration.
  secret.key         — store-local random key for opaque pseudonyms (never exported).
No network, no database. The store never mutates or deletes an earlier line. Tokens are hashed at
rest and never logged, printed or embedded in exceptions."""
from __future__ import annotations

import hmac
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts.contracts import (ContractError, POLICY_VERSION, REVIEW_STATES, digest, format_ts, validate_observation, validate_submission)

AUTH_FORMAT = "reviewers-2"
_ROLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


class ReviewAuthorityError(ContractError):
    """The review or disposition was not issued by an authorized reviewer appointment."""


def _hash_token(token: str) -> str:
    if not isinstance(token, str) or not token:
        raise ContractError("token: non-empty string required")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
        self.f_appt = self.root / "appointments.jsonl"
        self.f_key = self.root / "secret.key"
        if not self.f_key.exists():
            self.f_key.write_text(secrets.token_hex(32)); os.chmod(self.f_key, 0o600)
        if not self.f_auth.exists():
            self._write_auth({"authority_format": AUTH_FORMAT, "appointments": {}})

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

    def _write_auth(self, a: dict):
        self.f_auth.write_text(json.dumps(a, indent=1, sort_keys=True) + "\n")
        try:
            os.chmod(self.f_auth, 0o600)
        except OSError:
            pass

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

    def receipt(self, receipt_digest: str) -> dict | None:
        recs = [r for r in self._read(self.f_sub) if r["digest"] == receipt_digest]
        return recs[-1] if recs else None

    # ---------- observations (bound to the receipt's exact artifact)
    def add_observation(self, receipt_digest: str, observation: dict) -> dict:
        rec_sub = self.receipt(receipt_digest)
        if rec_sub is None:
            raise ContractError("observation must bind to an existing receipt digest")
        obs = validate_observation(observation, rec_sub["submission"]["artifact_binding"])
        rec = {"kind": "observation", "receipt_digest": receipt_digest, "observation": obs}
        self._append(self.f_obs, rec)
        return rec

    def observation_for(self, receipt_digest: str) -> dict | None:
        obs = [r["observation"] for r in self._read(self.f_obs) if r["receipt_digest"] == receipt_digest]
        return obs[-1] if obs else None

    # ---------- reviewer appointments (trusted; operator-only; never reachable from a submission)
    def authority(self) -> dict:
        raw = json.loads(self.f_auth.read_text())
        if raw.get("authority_format") == AUTH_FORMAT:
            return raw
        # Legacy `{"designated": bool, "roles": {role: hash}}`: the shared Boolean is IGNORED. Every legacy role
        # becomes a HELD appointment (credential kept so existing synthetic workflows keep working; real authority
        # is never inferred). An explicit designate_reviewer() replaces the HELD entry.
        now = format_ts(datetime.now(timezone.utc))
        appts = {}
        for role, h in (raw.get("roles") or {}).items():
            appts[role] = {"role": role, "token_sha256": h, "designated": False, "status": "HELD", "policy_version": None, "appointed_at": None,
                           "supersedes_appointment_id": None, "appointment_id": hashlib.sha256(f"legacy:{role}:{h}".encode()).hexdigest(),
                           "note": "migrated from the shared-Boolean format; held for explicit designation"}
        mig = {"authority_format": AUTH_FORMAT, "appointments": appts,
               "migrated": {"at": now, "legacy_shared_designated_ignored": raw.get("designated"), "roles": sorted(appts)}}
        self._write_auth(mig)
        self._append(self.f_appt, {"kind": "migration", "at": now, "legacy_shared_designated_ignored": raw.get("designated"),
                                   "held_roles": sorted(appts), "note": "real authority is never inferred from the legacy shared Boolean"})
        return mig

    def designate_reviewer(self, role: str, token: str, *, designated: bool, policy_version: str = POLICY_VERSION,
                           now: datetime | None = None, note: str = "") -> dict:
        """Operator action. Designation is a property of THIS appointment (role + credential + policy); it never
        touches another role's appointment and never rewrites earlier reviews. `designated=False` keeps SYNTHETIC."""
        if not isinstance(role, str) or not _ROLE.match(role):
            raise ContractError("role: registered id shape required")
        if not isinstance(designated, bool):
            raise ContractError("designated: bool required")
        h = _hash_token(token)
        a = self.authority(); prev = a["appointments"].get(role)
        ts = format_ts(now or datetime.now(timezone.utc))
        appt = {"role": role, "token_sha256": h, "designated": designated, "status": "DESIGNATED" if designated else "SYNTHETIC",
                "policy_version": policy_version, "appointed_at": ts,
                "supersedes_appointment_id": prev["appointment_id"] if prev else None}
        appt["appointment_id"] = hashlib.sha256(json.dumps({k: appt[k] for k in ("role", "token_sha256", "designated", "policy_version", "appointed_at", "supersedes_appointment_id")},
                                                           sort_keys=True).encode()).hexdigest()
        a["appointments"][role] = appt
        self._write_auth(a)
        self._append(self.f_appt, {"kind": "appointment", **appt, "note": str(note)[:200]})
        return {k: v for k, v in appt.items() if k != "token_sha256"}

    def revoke_reviewer(self, role: str, *, now: datetime | None = None, note: str = "") -> dict:
        a = self.authority(); prev = a["appointments"].get(role)
        if prev is None:
            raise ContractError("unknown reviewer role")
        ts = format_ts(now or datetime.now(timezone.utc))
        rec = {"role": role, "token_sha256": None, "designated": False, "status": "REVOKED", "policy_version": prev.get("policy_version"),
               "appointed_at": ts, "supersedes_appointment_id": prev["appointment_id"],
               "appointment_id": hashlib.sha256(f"revoked:{prev['appointment_id']}:{ts}".encode()).hexdigest()}
        a["appointments"][role] = rec
        self._write_auth(a)
        self._append(self.f_appt, {"kind": "revocation", **rec, "note": str(note)[:200]})
        return dict(rec)

    def authorize(self, reviewer_role: str, token: str) -> dict:
        """Check a credential against the role's CURRENT appointment. Returns the appointment (without the hash)
        with its authority label: DESIGNATED, SYNTHETIC or HELD. Raises ReviewAuthorityError otherwise."""
        a = self.authority()
        appt = a["appointments"].get(reviewer_role) if isinstance(reviewer_role, str) else None
        if appt is None or appt.get("status") == "REVOKED" or not appt.get("token_sha256"):
            raise ReviewAuthorityError(f"reviewer role {reviewer_role!r} is not authorized in this store")
        try:
            h = _hash_token(token)
        except ContractError:
            raise ReviewAuthorityError(f"reviewer role {reviewer_role!r}: credential missing") from None
        if not hmac.compare_digest(appt["token_sha256"], h):
            raise ReviewAuthorityError(f"reviewer role {reviewer_role!r} is not authorized in this store")
        authority = appt["status"] if appt["status"] in ("DESIGNATED", "SYNTHETIC") else "HELD"
        if authority == "DESIGNATED" and appt.get("policy_version") != POLICY_VERSION:
            raise ReviewAuthorityError(f"reviewer role {reviewer_role!r}: designated appointment is bound to policy {appt.get('policy_version')!r}; re-designate under {POLICY_VERSION!r}")
        return {"role": reviewer_role, "authority": authority, "appointment_id": appt["appointment_id"], "policy_version": appt.get("policy_version")}

    def add_review(self, receipt_digest: str, state: str, *, reviewer_role: str, token: str, reason: str = "", now: datetime | None = None) -> dict:
        if state not in REVIEW_STATES:
            raise ContractError(f"review state {state!r} not in {list(REVIEW_STATES)}")
        appt = self.authorize(reviewer_role, token)
        if self.receipt(receipt_digest) is None:
            raise ContractError("review must bind to an existing receipt digest")
        rec = {"kind": "review", "receipt_digest": receipt_digest, "policy_version": POLICY_VERSION, "state": state,
               "reviewer_role": reviewer_role, "authority": appt["authority"], "appointment_id": appt["appointment_id"],
               "decided_at": format_ts(now or datetime.now(timezone.utc)), "reason": str(reason)[:500]}
        self._append(self.f_rev, rec)
        return rec

    def review_for(self, receipt_digest: str) -> dict | None:
        revs = [r for r in self._read(self.f_rev) if r["receipt_digest"] == receipt_digest]
        return revs[-1] if revs else None

    # ---------- pseudonyms
    def pseudonym(self, participant_id: str) -> str:
        key = self.f_key.read_text().strip().encode()
        return "p-" + hmac.new(key, participant_id.encode(), hashlib.sha256).hexdigest()[:16]
