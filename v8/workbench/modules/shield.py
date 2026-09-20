"""SHD — Distillation Shield: protected evidence admission with an owner-controlled approval registry.

"Distillation" is a deterministic projection of an untrusted bundle into a narrow typed result. Nothing is trained, no
model is called, and a VERIFIED or ADMITTED bundle is never thereby TRUE: four answers are kept in four fields —
byte integrity · authority approval · factual adjudication (always NOT_ASSESSED here) · release permission (always NONE).

TRUST MECHANISM (exact). Trust roots are Ed25519 public keys enrolled by a principal holding the `admin` capability; the
enrollment, every revocation, every policy version and every approval are journal events written only through
admin-checked functions. An approval is a signed envelope of record type `shd.approval` that binds: the exact bundle
sha256, the expected evidence digests, ONE purpose, THIS workspace id, the approving principal, the signing key id, issue
and expiry times, and the policy version. A submitter cannot enroll a root, sign an accepted approval, change the policy
or approve its own bundle (the approver must differ from the submitter even when one principal holds both capabilities).
Nothing inside a bundle or an imported packet can add a root, a role or a policy: there is no trust on first use.

PROTECTED OPERATION. `admit` (1) pre-checks the approval, (2) runs the restricted worker with no lock held, then (3) under
the workspace lock re-reads the journal, RE-VALIDATES the approval against the state at that instant, and appends the
decision — that append is the commit point. A revocation recorded before it wins (REFUSED_APPROVAL_REVOKED); a decision
committed before a revocation stays in history as what it was. Consumers (COM intake, EVO import) call `require_current`
inside THEIR commit, so a result admitted yesterday is not usable after today's revocation or expiry. A missing approval,
an expired or revoked one, an unusable clock, a closed isolation boundary or a worker failure is an explicit refusal with
a fixed code; no route, retry or command-line shortcut reaches an unshielded parser, because none exists."""
from __future__ import annotations

import contextlib
import os
from datetime import timedelta

from v8.workbench.modkinds import SHD_KINDS
from v8.workbench.modules import authz, core, envelope, sandbox
from v8.workbench.modules.core import ModuleError
from v8.workbench.modules.shield_worker import MAX_BUNDLE, PURPOSES
from v8.workbench.store import Workspace

DEFAULT_POLICY = {"policy_version": 1, "max_approval_days": 30, "allowed_purposes": list(PURPOSES), "meaning": "built-in default until an administrator records a policy"}
SEPARATE_ANSWERS = {"factual_adjudication": "NOT_ASSESSED — no statement in the bundle was checked for truth; a correctly approved false statement stays false",
                    "release_permission": "NONE — admission authorizes no publication, deployment or trade"}
MAX_PENDING_PER_PRINCIPAL = 20


# ------------------------------------------------------------------ derived registry state (journal replay; cut by recorded time)
def state(ws: Workspace, as_of: str | None = None, evs: list | None = None) -> dict:
    roots, approvals, subs, decisions, discrepancies, pol, revision, last = {}, {}, {}, {}, [], dict(DEFAULT_POLICY), 0, None
    for e in core.events(ws, SHD_KINDS, as_of=as_of, evs=evs):
        k, p, at = e["kind"], e["payload"], e["time"]["recorded_at"]
        if k in ("SHD_ROOT_ENROLLED", "SHD_ROOT_REVOKED", "SHD_POLICY_SET", "SHD_APPROVAL_REVOKED"):
            revision += 1; last = at
        if k == "SHD_ROOT_ENROLLED":
            roots[p["key_id"]] = {"key_id": p["key_id"], "public_key": p["public_key"], "label": p.get("label", ""), "enrolled_at": at, "enrolled_by": e["actor"], "revoked": False, "revoked_at": None, "revoked_reason": None}
        elif k == "SHD_ROOT_REVOKED" and p["key_id"] in roots:
            roots[p["key_id"]].update(revoked=True, revoked_at=at, revoked_reason=p.get("reason"))
        elif k == "SHD_POLICY_SET":
            pol = {"policy_version": p["policy_version"], "max_approval_days": p["max_approval_days"], "allowed_purposes": p["allowed_purposes"], "set_at": at, "set_by": e["actor"]}
        elif k == "SHD_APPROVAL_ISSUED":
            b = p["envelope"]["body"]
            approvals[b["approval_id"]] = {**b, "envelope": p["envelope"], "recorded_at": at, "issued_by": e["actor"], "revoked_at": None, "revoked_reason": None}
        elif k == "SHD_APPROVAL_REVOKED" and p["approval_id"] in approvals:
            approvals[p["approval_id"]].update(revoked_at=at, revoked_reason=p.get("reason"), revoked_by=e["actor"])
        elif k == "SHD_SUBMISSION_RECEIVED":
            subs[p["submission_id"]] = {**p, "received_at": at, "actor": e["actor"]}
        elif k == "SHD_DECISION_RECORDED":
            decisions[p["decision_id"]] = {**p, "recorded_at": at, "actor": e["actor"]}
        elif k in ("SHD_TRUST_DISCREPANCY", "SHD_TRUST_RESOLUTION"):
            discrepancies.append({**p, "kind": k, "recorded_at": at, "actor": e["actor"]})
    return {"roots": roots, "approvals": approvals, "submissions": subs, "decisions": decisions, "policy": pol, "discrepancies": discrepancies,
            "trust_revision": revision, "trust_as_of": last}


def trust_snapshot(ws: Workspace, evs: list | None = None) -> dict:
    """What an export carries about THIS workspace's trust state: for display and discrepancy detection at a receiver,
    never for installation there."""
    st = state(ws, evs=evs)
    return {"workspace_id": ws.meta["workspace_id"], "trust_revision": st["trust_revision"], "trust_as_of": st["trust_as_of"], "policy_version": st["policy"]["policy_version"],
            "roots": [{"key_id": r["key_id"], "public_key": r["public_key"], "revoked": r["revoked"]} for r in st["roots"].values()],
            "revoked_approvals": sorted(a["approval_id"] for a in st["approvals"].values() if a["revoked_at"])}


def _keys_dir(ws: Workspace):
    d = ws.root / "private" / "keys"; d.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(d, 0o700)
    return d


# ------------------------------------------------------------------ administration (admin capability; every change is an event)
def enroll_root(ws: Workspace, principal, *, label: str, public_key: str | None = None, op_id: str) -> dict:
    """Enroll a trust root. With no key given, a new Ed25519 key pair is generated HERE: the private half goes to a 0600
    file under the workspace's private directory (never exported, never packaged) and becomes this workspace's signing key."""
    authz.require(principal, "admin")
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None and done["kind"] == "SHD_ROOT_ENROLLED":
            return done
        if public_key:
            import base64
            try:
                raw = base64.b64decode(public_key.strip(), validate=True)
            except ValueError:
                raise ModuleError("E_KEY", "the public key is not base64") from None
            if len(raw) != 32:
                raise ModuleError("E_KEY", "an Ed25519 public key is 32 bytes")
            kid, pub = envelope.key_id(raw), base64.b64encode(raw).decode("ascii")
        else:
            pem, pub, kid = envelope.generate()
            path = _keys_dir(ws) / f"{kid}.pem"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.write(fd, pem); os.fsync(fd)
            finally:
                os.close(fd)
        if kid in state(ws, evs=evs)["roots"]:
            raise ModuleError("E_ROOT_EXISTS", "this key is already enrolled (a revoked root is never revived: enroll a new key)")
        ev, _ = ws._append_unlocked("SHD_ROOT_ENROLLED", None, {"key_id": kid, "public_key": pub, "label": core.text(label, "label", maxlen=120), "algorithm": "Ed25519",
                                    "holds_private_key_here": not public_key}, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


def revoke_root(ws: Workspace, principal, key_id: str, reason: str, *, op_id: str) -> dict:
    authz.require(principal, "admin")
    with ws._locked():
        if key_id not in state(ws)["roots"]:
            raise ModuleError("E_UNKNOWN_ROOT", "no such enrolled root")
        ev, _ = ws._append_unlocked("SHD_ROOT_REVOKED", None, {"key_id": key_id, "reason": core.text(reason, "reason", maxlen=500),
                                    "meaning": "approvals signed by this root stop being applicable from now; decisions already committed stay in history"},
                                    op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


def set_policy(ws: Workspace, principal, *, max_approval_days: int, allowed_purposes: list, op_id: str) -> dict:
    authz.require(principal, "admin")
    if isinstance(max_approval_days, bool) or not isinstance(max_approval_days, int) or not 1 <= max_approval_days <= 365:
        raise ModuleError("E_POLICY", "maximum approval validity: 1 to 365 days")
    allowed = sorted(set(allowed_purposes))
    if not allowed or any(p not in PURPOSES for p in allowed):
        raise ModuleError("E_POLICY", f"purposes must be chosen from {', '.join(PURPOSES)}")
    with ws._locked():
        cur = state(ws)["policy"]
        ev, _ = ws._append_unlocked("SHD_POLICY_SET", None, {"policy_version": cur["policy_version"] + 1, "max_approval_days": max_approval_days, "allowed_purposes": allowed,
                                    "meaning": "approvals issued under an earlier policy version stop being applicable; issue new ones under this version"},
                                    op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


def _signing_key(ws: Workspace, st: dict) -> tuple[str, bytes]:
    for kid in sorted(st["roots"], key=lambda k: st["roots"][k]["enrolled_at"], reverse=True):
        path = _keys_dir(ws) / f"{kid}.pem"
        if not st["roots"][kid]["revoked"] and path.is_file():
            return kid, path.read_bytes()
    raise ModuleError("E_NO_SIGNING_KEY", "no unrevoked trust root with a private key is held in this workspace: an administrator enrolls one on the SHD trust page first")


def issue_approval(ws: Workspace, principal, *, bundle_sha256: str, source_sha256s: list, purpose: str, expires_at: str, op_id: str) -> dict:
    authz.require(principal, "admin")
    core.hex64(bundle_sha256, "bundle sha256")
    srcs = sorted({core.hex64(s, "evidence sha256") for s in source_sha256s})
    if len(srcs) > 64:
        raise ModuleError("E_LIMIT", "at most 64 evidence digests")
    exp = core.parse_time(core.norm_time(expires_at, "expiry"))
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None and done["kind"] == "SHD_APPROVAL_ISSUED":
            return done
        why = core.clock_problem(ws)
        if why:
            raise ModuleError("REFUSED_CLOCK_UNCERTAIN", why)
        st = state(ws, evs=evs); pol = st["policy"]; now = core.now()
        if purpose not in pol["allowed_purposes"]:
            raise ModuleError("E_PURPOSE", f"purpose must be one the policy allows: {', '.join(pol['allowed_purposes'])}")
        if exp <= now or exp > now + timedelta(days=pol["max_approval_days"]):
            raise ModuleError("E_EXPIRY", f"the expiry must be in the future and within {pol['max_approval_days']} days (policy version {pol['policy_version']})")
        for s in st["submissions"].values():
            if s["bundle_sha256"] == bundle_sha256 and s["submitter"] == principal["principal_id"]:
                raise ModuleError("REFUSED_SELF_APPROVAL", "the principal that submitted this bundle cannot approve it, whatever capabilities it holds")
        kid, pem = _signing_key(ws, st)
        body = {"approval_id": core.next_id(evs, "SHD_APPROVAL_ISSUED", "AP", "approval_id"), "bundle_sha256": bundle_sha256, "source_sha256s": srcs, "purpose": purpose,
                "workspace_id": ws.meta["workspace_id"], "approver": principal["principal_id"], "key_id": kid, "issued_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "expires_at": exp.strftime("%Y-%m-%dT%H:%M:%SZ"), "policy_version": pol["policy_version"]}
        ev, _ = ws._append_unlocked("SHD_APPROVAL_ISSUED", None, {"approval_id": body["approval_id"], "envelope": envelope.sign("shd.approval", body, pem)},
                                    op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


def revoke_approval(ws: Workspace, principal, approval_id: str, reason: str, *, op_id: str) -> dict:
    authz.require(principal, "admin")
    with ws._locked():
        if approval_id not in state(ws)["approvals"]:
            raise ModuleError("E_UNKNOWN_APPROVAL", "no such approval")
        ev, _ = ws._append_unlocked("SHD_APPROVAL_REVOKED", None, {"approval_id": approval_id, "reason": core.text(reason, "reason", maxlen=500),
                                    "meaning": "no protected operation may use this approval from now; operations already committed stay in history"},
                                    op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


# ------------------------------------------------------------------ submission (submit capability). The parent hashes and stores; it never parses.
def submit(ws: Workspace, principal, data: bytes, *, title: str, op_id: str) -> dict:
    authz.require(principal, "submit")
    if not isinstance(data, (bytes, bytearray)) or not 1 <= len(data) <= MAX_BUNDLE:
        raise ModuleError("INPUT_TOO_LARGE", f"a bundle is 1 byte to {MAX_BUNDLE // (1024 * 1024)} MiB")
    data = bytes(data); h = core.sha256_bytes(data)
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None and done["kind"] == "SHD_SUBMISSION_RECEIVED":
            return done
        st = state(ws, evs=evs)
        decided = {d["submission_id"] for d in st["decisions"].values()}
        pending = [s for s in st["submissions"].values() if s["submitter"] == principal["principal_id"] and s["submission_id"] not in decided]
        if len(pending) >= MAX_PENDING_PER_PRINCIPAL:
            raise ModuleError("E_LIMIT", f"{principal['principal_id']!r} already has {MAX_PENDING_PER_PRINCIPAL} undecided submissions")
        core.Vault(ws).put_bytes(data)                                   # staged bytes first; the event is the commit point
        ev, _ = ws._append_unlocked("SHD_SUBMISSION_RECEIVED", None, {"submission_id": core.next_id(evs, "SHD_SUBMISSION_RECEIVED", "SB", "submission_id"), "bundle_sha256": h,
                                    "size_bytes": len(data), "submitter": principal["principal_id"], "title": core.text(title, "title", maxlen=200, required=False),
                                    "note": "bytes stored unparsed; only the restricted worker opens them"}, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


def applicable_approval(ws: Workspace, st: dict, sub: dict, purpose: str | None, evidence_sha256s: list | None) -> tuple[dict | None, str, str]:
    """(approval, code, detail) for one submission against the registry state `st` AS READ NOW. code 'OK' or a fixed refusal."""
    why = core.clock_problem(ws)
    if why:
        return None, "REFUSED_CLOCK_UNCERTAIN", why
    cands = [a for a in st["approvals"].values() if a["bundle_sha256"] == sub["bundle_sha256"]]
    if not cands:
        return None, "REFUSED_NO_APPROVAL", "no approval names these exact bytes; an administrator other than the submitter issues one for this sha256"
    now, last = core.now(), (None, "REFUSED_NO_APPROVAL", "")
    trusted = {k: {"public_key": r["public_key"], "revoked": r["revoked"]} for k, r in st["roots"].items()}
    for a in sorted(cands, key=lambda a: a["recorded_at"], reverse=True):
        v = envelope.verify(a["envelope"], "shd.approval", trusted)
        if a["revoked_at"]:
            last = (a, "REFUSED_APPROVAL_REVOKED", f"approval {a['approval_id']} was revoked at {a['revoked_at']}")
        elif v["integrity"] == "UNVERIFIABLE":
            last = (a, "REFUSED_SIGNATURE_UNVERIFIABLE", v["reason"])
        elif v["integrity"] != "VALID":
            last = (a, "REFUSED_SIGNATURE_INVALID", v["reason"] or "")
        elif v["trust"] == "REVOKED_ROOT":
            last = (a, "REFUSED_ROOT_REVOKED", f"the root that signed approval {a['approval_id']} is revoked")
        elif v["trust"] != "TRUSTED":
            last = (a, "REFUSED_UNKNOWN_SIGNER", "the signing key is not a root enrolled in this workspace")
        elif a["workspace_id"] != ws.meta["workspace_id"]:
            last = (a, "REFUSED_WORKSPACE_MISMATCH", "the approval was issued for another workspace")
        elif a["approver"] == sub["submitter"]:
            last = (a, "REFUSED_SELF_APPROVAL", "the approver is the submitter")
        elif a["policy_version"] != st["policy"]["policy_version"]:
            last = (a, "REFUSED_POLICY_VERSION", f"approved under policy version {a['policy_version']}; the current version is {st['policy']['policy_version']}")
        elif core.parse_time(a["expires_at"]) <= now:
            last = (a, "REFUSED_APPROVAL_EXPIRED", f"approval {a['approval_id']} expired at {a['expires_at']}")
        elif core.parse_time(a["issued_at"]) > now + timedelta(minutes=5):
            last = (a, "REFUSED_CLOCK_UNCERTAIN", "the approval's issue time is in this server's future")
        elif purpose is not None and a["purpose"] != purpose:
            last = (a, "REFUSED_PURPOSE_MISMATCH", f"approved for {a['purpose']}, the bundle declares {purpose}")
        elif evidence_sha256s is not None and sorted(evidence_sha256s) != a["source_sha256s"]:
            last = (a, "REFUSED_SOURCE_DIGESTS_MISMATCH", "the evidence digests in the bundle are not the ones the approval names")
        else:
            return a, "OK", ""
    return last


def admit(ws: Workspace, principal, submission_id: str, *, op_id: str) -> dict:
    """The protected operation. Returns the decision event (ADMITTED or REFUSED with a fixed code)."""
    if principal is None or not ({"submit", "admin", "review"} & set(principal["caps"])):
        raise ModuleError("E_FORBIDDEN", "requesting a decision needs the submit, review or admin capability")
    evs = ws.load()["events"]; done = core.prior(evs, op_id)
    if done is not None and done["kind"] == "SHD_DECISION_RECORDED":
        return done
    st = state(ws, evs=evs); sub = st["submissions"].get(submission_id)
    if sub is None:
        raise ModuleError("E_UNKNOWN_SUBMISSION", "no such submission")
    if "admin" not in principal["caps"] and "review" not in principal["caps"] and sub["submitter"] != principal["principal_id"]:
        raise ModuleError("E_FORBIDDEN", "a submitter may request a decision on its own submissions only")
    typed = None; iso = None
    _, code, detail = applicable_approval(ws, st, sub, None, None)                         # (1) cheap pre-check: no worker run for an unapproved bundle
    if code == "OK":
        staged = core.Vault(ws).dir / sub["bundle_sha256"]
        try:
            typed = sandbox.run_worker(staged, sub["bundle_sha256"])                        # (2) restricted worker, no lock held
            iso = typed.pop("_isolation")
        except ModuleError as exc:
            code, detail = {"E_ISOLATION_UNAVAILABLE": "REFUSED_ISOLATION_UNAVAILABLE", "E_WORKER_FAILED": "REFUSED_WORKER_FAILED"}.get(exc.code, "REFUSED_WORKER_OUTPUT"), exc.detail
        if typed is not None and typed["result"] != "VERIFIED":
            code, detail = "REFUSED_BUNDLE_REJECTED", typed["code"]
    with ws._locked():                                                                       # (3) re-validate against the journal AS IT IS NOW, then commit
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None:
            return done
        st = state(ws, evs=evs); approval = None
        if code == "OK":
            approval, code, detail = applicable_approval(ws, st, sub, typed["purpose"], [e["sha256"] for e in typed["evidence"]])
        result_digest = excerpt_digest = None
        if code == "OK":
            v = core.Vault(ws); excerpt_digest = v.put({"excerpts": typed.pop("excerpts")}); result_digest = v.put(typed)
        else:
            approval = approval or applicable_approval(ws, st, sub, None, None)[0]
        payload = {"decision_id": core.next_id(evs, "SHD_DECISION_RECORDED", "DC", "decision_id"), "submission_id": submission_id, "bundle_sha256": sub["bundle_sha256"], "submitter": sub["submitter"],
                   "result": "ADMITTED" if code == "OK" else "REFUSED", "code": code, "detail": detail[:300], "requested_by": principal["principal_id"],
                   "byte_integrity": "VERIFIED" if code == "OK" else ("REJECTED" if code == "REFUSED_BUNDLE_REJECTED" else "NOT_ESTABLISHED"),
                   "authority_approval": {"status": "APPLICABLE" if code == "OK" else "NOT_APPLICABLE", "approval_id": approval["approval_id"] if approval else None, "approver": approval["approver"] if approval else None,
                                          "key_id": approval["key_id"] if approval else None, "policy_version": st["policy"]["policy_version"], "trust_revision": st["trust_revision"],
                                          "expires_at": approval["expires_at"] if approval else None},
                   **SEPARATE_ANSWERS, "purpose": typed["purpose"] if code == "OK" else None, "typed_result_sha256": result_digest, "inspection_excerpts_sha256": excerpt_digest,
                   "isolation": iso, "next_action": next_action(code)}
        ev, _ = ws._append_unlocked("SHD_DECISION_RECORDED", None, payload, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


def next_action(code: str) -> str:
    return {"OK": "the typed result can be consumed by the COM intake or the EVO import for its purpose while the approval stays applicable",
            "REFUSED_NO_APPROVAL": "an administrator other than the submitter issues an approval for this exact sha256, then request a decision again",
            "REFUSED_APPROVAL_EXPIRED": "an administrator issues a new approval", "REFUSED_APPROVAL_REVOKED": "an administrator issues a new approval if the bundle is still wanted",
            "REFUSED_ROOT_REVOKED": "an administrator issues a new approval under a current root", "REFUSED_POLICY_VERSION": "an administrator issues a new approval under the current policy",
            "REFUSED_SELF_APPROVAL": "a different administrator approves, or a different principal submits", "REFUSED_ISOLATION_UNAVAILABLE": "see the Setup page: the restricted worker cannot run on this host, so the protected route is closed",
            "REFUSED_CLOCK_UNCERTAIN": "correct the server clock", "REFUSED_BUNDLE_REJECTED": "correct the bundle (the fixed code names what failed) and submit the new bytes; they need their own approval"}.get(
                code, "correct what the code names and request a decision again; nothing was admitted")


def require_current(ws: Workspace, evs: list, decision_id: str, purpose: str) -> dict:
    """For a CONSUMER, inside its own locked commit: the typed result of an ADMITTED decision whose approval is STILL
    applicable now. A revoked, expired, re-policied or re-rooted approval refuses — no stale authorization is honoured."""
    st = state(ws, evs=evs); d = st["decisions"].get(decision_id)
    if d is None or d["result"] != "ADMITTED":
        raise ModuleError("REFUSED_NOT_ADMITTED", "only an ADMITTED decision has a typed result; a refused bundle reaches no consumer")
    if d["purpose"] != purpose:
        raise ModuleError("REFUSED_PURPOSE_MISMATCH", f"decision {decision_id} was admitted for {d['purpose']}, not {purpose}")
    sub = st["submissions"][d["submission_id"]]; typed = core.Vault(ws).get(d["typed_result_sha256"])
    _, code, detail = applicable_approval(ws, st, sub, typed["purpose"], [e["sha256"] for e in typed["evidence"]])
    if code != "OK":
        raise ModuleError(code, f"the approval behind decision {decision_id} is no longer applicable: {detail}")
    return typed


def inspection(ws: Workspace, principal, decision_id: str) -> list:
    """The separate human inspection view: bounded excerpts as inert text for an admin or reviewer. Never an input to a consumer."""
    if principal is None or not ({"admin", "review"} & set(principal["caps"])):
        raise ModuleError("E_FORBIDDEN", "inspecting evidence text needs the admin or review capability")
    d = state(ws)["decisions"].get(decision_id)
    if d is None or not d.get("inspection_excerpts_sha256"):
        raise ModuleError("E_NOT_AVAILABLE", "only an admitted bundle has inspection excerpts")
    import base64
    return [{"path": x["path"], "truncated": x["truncated"], "text": base64.b64decode(x["base64"]).decode("utf-8", "replace")} for x in core.Vault(ws).get(d["inspection_excerpts_sha256"])["excerpts"]]
