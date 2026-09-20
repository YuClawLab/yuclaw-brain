"""Module evidence packets: a permitted, scoped export of SHD / EVO / COM / PRC records, and its verification elsewhere.

A packet (`modx-<id>.zip`, one member `packet.json`) carries: the module events the exporter is permitted to include, a
hash-only SKELETON of the whole journal (seq, kind, prev_hash, event_hash — no payloads) so that every included event can be
placed in the chain, the private objects those events name and the export's scope allows, the exporter's trust snapshot,
and the derived views as the exporter computed them.

A receiver establishes, separately:
  INTEGRITY   every included event re-hashes to its event_hash and sits in a consistent chain; every private object
              re-hashes to the digest an included event names; derived views recompute to the same values. Independent of
              who the receiver trusts and of the receiver's permissions.
  TRUST       approval / checkpoint / packet signatures are checked against the RECEIVER's own enrolled roots. A key that
              arrives inside a packet is never enrolled by importing it: an unknown signer stays UNKNOWN_SIGNER.
  FRESHNESS   the exporter's trust snapshot is shown with its revision and time. A disconnected receiver cannot know of a
              later revocation: current authorization is reported UNKNOWN and nothing freshness-dependent is authorized.
              A snapshot OLDER than one already seen from that workspace, or one that trusts a root this receiver revoked,
              is recorded as a discrepancy for an administrator to resolve; it never changes the receiver's trust state.
  COMPLETENESS against a checkpoint the receiver holds SEPARATELY: a skeleton that is shorter than, or different at, the
              checkpoint's position is TRUNCATED_OR_ALTERED. A checkpoint shipped inside the same packet proves nothing.
Forged relations are rejected: a private object no included event names, a practice comparison without that session's
reveal event (UNAUTHORIZED_PRIVATE_ANSWER), a comparison that is not the task's commitment, an event that is not in the
skeleton. Nothing imported installs a role, a key, a policy, a claim or a queue entry."""
from __future__ import annotations

import hashlib
import io
import json
import secrets
import zipfile

from v3.receipts.contracts import canonical_json
from v8.workbench.modkinds import COM_KINDS, EVO_KINDS, MODULE_KINDS, PRC_KINDS, SHD_KINDS
from v8.workbench.modules import commons, core, envelope, evolution, practice, shield
from v8.workbench.modules.core import ModuleError
from v8.workbench.store import GENESIS, Workspace, _line_hash

FORMAT = "yuclaw-module-packet/1"
MAX_PACKET = 8 * 1024 * 1024
_PRC_SESSION_KINDS = ("PRC_SESSION_OPENED", "PRC_EVIDENCE_READ", "PRC_ATTEMPT_COMMITTED", "PRC_COMPARISON_REVEALED", "PRC_REFLECTION_RECORDED", "PRC_FEEDBACK_RECORDED")


def _derived(ws, evs: list, at) -> dict:
    """Views a receiver can recompute from the included events alone."""
    cs = commons.state(ws, evs=evs); es = evolution.state(ws, evs=evs); ss = shield.state(ws, evs=evs)
    return {"com": {"packets": len(cs["packets"]), "groups": {g["group_id"]: {"packets": len(g["packets"]), "contributors": sorted(g["contributors"]), "claim_id": g["claim"]["claim_id"], "state": g["state"],
                                                                                "cost_minutes": g["cost_minutes"], "quarantined_by": g["quarantined_by"]} for g in cs["groups"].values()},
                    "duplicate_volume": len(cs["packets"]) - len(cs["groups"])},
            "evo": {vid: {"reuse": {p: d["decision"] for p, d in evolution.reuse_decisions(es, vid, at).items()}, "changed_components": v["changed_components"], "unknown": v["inventory"]["unknown"]} for vid, v in es["versions"].items()},
            "shd": {d["decision_id"]: {"result": d["result"], "code": d["code"], "bundle_sha256": d["bundle_sha256"]} for d in ss["decisions"].values()}}


def build_packet(ws: Workspace, principal, *, modules: list, prc_sessions: list, withhold_text: bool, op_id: str) -> dict:
    if principal is None:
        raise ModuleError("E_SIGN_IN", "sign in to build an export")
    caps = set(principal["caps"]); modules = [m for m in dict.fromkeys(modules) if m in ("SHD", "EVO", "COM")]
    if modules and not ({"admin", "review", "submit"} & caps):
        raise ModuleError("E_FORBIDDEN", "exporting SHD, EVO or COM records needs the submit, review or admin capability")
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        ps = practice.state(ws, evs=evs); vault = core.Vault(ws); include, objects, withheld = [], {}, []
        kinds = sum(({"SHD": SHD_KINDS, "EVO": EVO_KINDS, "COM": COM_KINDS}[m] for m in modules), ())
        include += [e for e in evs if e["kind"] in kinds]
        if "SHD" in modules:
            for d in shield.state(ws, evs=evs)["decisions"].values():
                if d.get("typed_result_sha256"):
                    objects[d["typed_result_sha256"]] = vault.get(d["typed_result_sha256"])        # typed result only — never the staged bytes or the inspection excerpts
        for sid in dict.fromkeys(prc_sessions):
            ss = ps["sessions"].get(sid)
            if ss is None or not (ss["practitioner"] == principal["principal_id"] or "admin" in caps):
                raise ModuleError("E_NOT_FOUND", "no such session for this principal")           # a practitioner exports its own sessions; an administrator any
            t = ps["tasks"][ss["task_id"]]
            include += [e for e in evs if (e["kind"] == "PRC_TASK_FROZEN" and e["payload"]["task_id"] == t["task_id"]) or (e["kind"] in _PRC_SESSION_KINDS and e["payload"].get("session_id") == sid)]
            want = [("attempt", (ss["attempt"] or {}).get("attempt_sha256"))] + [("reflection", r["reflection_sha256"]) for r in ss["reflections"]] + [("feedback", f["feedback_sha256"]) for f in ss["feedback"]]
            if ss["revealed_at"] is not None:
                want.append(("comparison", t["comparison_commitment"]))                            # only a REVEALED comparison can ever leave; an unrevealed one is not exportable by anyone
            for label, dg in want:
                if dg:
                    if withhold_text and label != "comparison":
                        withheld.append(dg)
                    else:
                        objects[dg] = vault.get(dg)
        seen = set(); include = [e for e in sorted(include, key=lambda e: e["seq"]) if not (e["seq"] in seen or seen.add(e["seq"]))]
        now = core.now(); body = {"format": FORMAT, "workspace_id": ws.meta["workspace_id"], "built_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "built_by": principal["principal_id"],
                                  "scope": {"modules": modules, "prc_sessions": list(dict.fromkeys(prc_sessions)), "text_withheld": bool(withhold_text), "withheld_object_digests": sorted(withheld)},
                                  "events": include, "journal_skeleton": [{"seq": e["seq"], "kind": e["kind"], "prev_hash": e["prev_hash"], "event_hash": e["event_hash"]} for e in evs],
                                  "objects": objects, "trust_snapshot": shield.trust_snapshot(ws, evs=evs), "derived": _derived(ws, include, now),
                                  "limits": "integrity is checkable anywhere; trust is the receiver's own; current authorization is unknown offline; nothing here proves a statement true"}
        body["packet_digest"] = hashlib.sha256(canonical_json(body)).hexdigest()
        try:
            kid, pem = shield._signing_key(ws, shield.state(ws, evs=evs))
            body["packet_signature"] = envelope.sign("module.export", {"packet_digest": body["packet_digest"], "workspace_id": body["workspace_id"], "built_at": body["built_at"]}, pem)
        except ModuleError:
            body["packet_signature"] = None
        data = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        if len(data) > MAX_PACKET:
            raise ModuleError("E_TOO_LARGE", "the packet would exceed 8 MiB; narrow the scope")
        core.strict_json(data, max_bytes=MAX_PACKET, code="PACKET", max_nodes=400000, max_string=1 << 20)      # what is built here must be readable by the strict verifier anywhere
        if done is not None and done["kind"] == "MODULE_EXPORT_BUILT":
            return {**done["payload"], "zip_path": str(ws.exports / f"{done['payload']['export_id']}.zip")}
        export_id = "modx-" + secrets.token_hex(8); buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            zi = zipfile.ZipInfo("packet.json", date_time=(1980, 1, 1, 0, 0, 0)); zi.external_attr = 0o600 << 16; z.writestr(zi, data)
        path = ws.exports / f"{export_id}.zip"; path.write_bytes(buf.getvalue())
        payload = {"export_id": export_id, "packet_digest": body["packet_digest"], "zip_sha256": hashlib.sha256(buf.getvalue()).hexdigest(), "scope": body["scope"], "events_included": len(include),
                   "objects_included": len(objects), "built_by": principal["principal_id"]}
        ws._append_unlocked("MODULE_EXPORT_BUILT", None, payload, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return {**payload, "zip_path": str(path)}


def preview(ws: Workspace, principal, *, modules: list, prc_sessions: list, withhold_text: bool) -> dict:
    """What a packet WOULD contain (counts and object kinds), before anything is written."""
    evs = ws.load()["events"]; ps = practice.state(ws, evs=evs); rows = []
    for sid in prc_sessions:
        ss = ps["sessions"].get(sid)
        if ss is None or not (principal and (ss["practitioner"] == principal["principal_id"] or "admin" in principal["caps"])):
            raise ModuleError("E_NOT_FOUND", "no such session for this principal")
        rows.append({"session_id": sid, "practitioner_id_included": True, "attempt_text": "withheld (digest only)" if withhold_text else ("included" if ss["attempt"] else "none"),
                     "comparison": "included (revealed)" if ss["revealed_at"] else "NOT exportable (never revealed in this session)", "reflections": len(ss["reflections"]), "feedback": len(ss["feedback"])})
    return {"modules": modules, "sessions": rows, "never_included": ["credential hashes", "signing keys", "staged SHD bundle bytes", "SHD inspection excerpts", "unrevealed comparisons", "other practitioners' sessions"]}


# ------------------------------------------------------------------ verification (fresh workspace; nothing is imported into state)
def _read_packet(data: bytes) -> dict:
    if len(data) > MAX_PACKET:
        raise ModuleError("PACKET_TOO_LARGE")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data)); infos = zf.infolist()
    except (zipfile.BadZipFile, ValueError, OSError):
        raise ModuleError("PACKET_NOT_A_ZIP") from None
    if len(infos) != 1 or infos[0].filename != "packet.json" or infos[0].file_size > MAX_PACKET or infos[0].flag_bits & 1:
        raise ModuleError("PACKET_MEMBERS_REJECTED")
    with zf.open(infos[0]) as fh:
        raw = fh.read(MAX_PACKET + 1)
    if len(raw) != infos[0].file_size:
        raise ModuleError("PACKET_SIZE_MISMATCH")
    return core.strict_json(raw, max_bytes=MAX_PACKET, code="PACKET", max_nodes=400000, max_string=1 << 20)


def verify_packet(ws: Workspace, data: bytes, *, checkpoint: bytes | None = None, principal=None, op_id: str | None = None) -> dict:
    out = {"result": "MISMATCH", "packet_sha256": hashlib.sha256(data).hexdigest(), "first_discrepancy": None, "integrity": {}, "trust": {}, "freshness": {}, "checkpoint": "NOT_SUPPLIED", "recompute": [], "discrepancies": []}

    def fail(msg, result="MISMATCH"):
        out["result"], out["first_discrepancy"] = result, msg; return _record(ws, out, principal, op_id)
    try:
        p = _read_packet(data)
    except ModuleError as exc:
        return fail(exc.code, "UNSUPPORTED")
    if not isinstance(p, dict) or p.get("format") != FORMAT:
        return fail(f"unknown or future packet format {p.get('format') if isinstance(p, dict) else None!r}; this version reads {FORMAT} only", "UNSUPPORTED")
    need = {"format", "workspace_id", "built_at", "built_by", "scope", "events", "journal_skeleton", "objects", "trust_snapshot", "derived", "limits", "packet_digest", "packet_signature"}
    if set(p) != need:
        return fail("packet keys are not the declared set")
    body = {k: v for k, v in p.items() if k not in ("packet_digest", "packet_signature")}
    if hashlib.sha256(canonical_json(body)).hexdigest() != p["packet_digest"]:
        return fail("packet_digest does not match the packet content")
    # -- chain skeleton
    prev, skel = GENESIS, {}
    for i, row in enumerate(p["journal_skeleton"], start=1):
        if not isinstance(row, dict) or row.get("seq") != i or row.get("prev_hash") != prev or not core.HEX64.match(str(row.get("event_hash"))):
            return fail(f"journal skeleton breaks at position {i}")
        prev = row["event_hash"]; skel[i] = row
    # -- every included event re-hashes and sits in the skeleton
    for e in p["events"]:
        if not isinstance(e, dict) or e.get("kind") not in MODULE_KINDS:
            return fail("an included event is not a module event")
        b = {k: v for k, v in e.items() if k != "event_hash"}
        if _line_hash(b) != e.get("event_hash") or skel.get(e.get("seq"), {}).get("event_hash") != e["event_hash"] or skel[e["seq"]]["kind"] != e["kind"]:
            return fail(f"event seq {e.get('seq')} does not re-hash to its place in the journal skeleton (forged or altered)")
    out["integrity"]["events"] = f"{len(p['events'])} event(s) re-hashed and placed in a {len(skel)}-event chain"
    # -- private objects: each re-hashes AND is named by an included event; comparisons need the reveal
    evs = p["events"]; ps = practice.state(ws, evs=evs); named = {}
    for d in shield.state(ws, evs=evs)["decisions"].values():
        if d.get("typed_result_sha256"):
            named[d["typed_result_sha256"]] = "shd typed result"
    for ss in ps["sessions"].values():
        t = ps["tasks"].get(ss["task_id"])
        if ss["attempt"]:
            named[ss["attempt"]["attempt_sha256"]] = "attempt"
        for r in ss["reflections"]:
            named[r["reflection_sha256"]] = "reflection"
        for f in ss["feedback"]:
            named[f["feedback_sha256"]] = "feedback"
        if t is not None and ss["revealed_at"] is not None:
            named[t["comparison_commitment"]] = "comparison"
    commitments = {t["comparison_commitment"] for t in ps["tasks"].values()}
    for dg, obj in p["objects"].items():
        if hashlib.sha256(canonical_json(obj)).hexdigest() != dg:
            return fail(f"private object {dg[:12]}… does not match its digest")
        if dg in commitments and named.get(dg) != "comparison":
            return fail("UNAUTHORIZED_PRIVATE_ANSWER: a practice comparison is included without that session's reveal event")
        if dg not in named:
            return fail(f"FORGED_LINK: private object {dg[:12]}… is not named by any included event")
    out["integrity"]["objects"] = f"{len(p['objects'])} private object(s) re-hashed and linked; {len(p['scope'].get('withheld_object_digests', []))} withheld by the exporter (digest only)"
    # -- derived views recompute
    try:
        again = _derived(ws, evs, core.parse_time(p["built_at"]))
    except Exception as exc:                                                   # noqa: BLE001 - a packet that cannot be recomputed is a mismatch, never a crash
        return fail(f"derived views could not be recomputed: {type(exc).__name__}")
    for k in ("com", "evo", "shd"):
        ok = again[k] == p["derived"].get(k); out["recompute"].append(f"recompute-{k}: {'MATCH' if ok else 'MISMATCH'}")
        if not ok:
            return fail(f"the {k.upper()} view recomputed from the included events differs from the packet's")
    # -- trust: the RECEIVER's roots only
    mine = shield.state(ws); trusted = {k: {"public_key": r["public_key"], "revoked": r["revoked"]} for k, r in mine["roots"].items()}
    sig = envelope.verify(p["packet_signature"], "module.export", trusted) if p["packet_signature"] else {"integrity": "ABSENT", "trust": "NOT_EVALUATED", "key_id": None, "reason": "the exporter held no signing key"}
    if p["packet_signature"] and sig["integrity"] == "VALID" and p["packet_signature"]["body"].get("packet_digest") != p["packet_digest"]:
        return fail("the packet signature is for a different packet digest")
    if sig["integrity"] == "INVALID":
        return fail(f"packet signature invalid: {sig['reason']}")
    approvals = []
    for a in shield.state(ws, evs=evs)["approvals"].values():
        v = envelope.verify(a["envelope"], "shd.approval", trusted); approvals.append({"approval_id": a["approval_id"], "integrity": v["integrity"], "trust": v["trust"], "key_id": v["key_id"]})
        if v["integrity"] == "INVALID":
            return fail(f"approval {a['approval_id']}: signature invalid ({v['reason']})")
    out["trust"] = {"packet_signature": {"integrity": sig["integrity"], "trust": sig["trust"], "key_id": sig["key_id"]}, "approvals": approvals,
                    "rule": "trust comes only from roots this receiver's administrator enrolled; a key carried by the packet was NOT enrolled and never is by verification"}
    # -- freshness and discrepancies against what this receiver knows
    snap = p["trust_snapshot"]; seen = [e["payload"] for e in ws.load()["events"] if e["kind"] == "MODULE_PACKET_VERIFIED" and e["payload"].get("origin_workspace_id") == snap.get("workspace_id")]
    top = max([s.get("origin_trust_revision") or 0 for s in seen], default=0)
    out["freshness"] = {"origin_workspace_id": snap.get("workspace_id"), "origin_trust_revision": snap.get("trust_revision"), "origin_trust_as_of": snap.get("trust_as_of"), "verified_at": core.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "current_authorization": "UNKNOWN — a receiver that is not connected to the origin cannot know of a revocation after the snapshot; this verification authorizes nothing that depends on freshness"}
    if (snap.get("trust_revision") or 0) < top:
        out["discrepancies"].append(f"TRUST_STATE_ROLLBACK: this packet carries trust revision {snap.get('trust_revision')} but revision {top} from the same workspace was verified here earlier")
    for r in snap.get("roots", []):
        if r.get("key_id") in mine["roots"] and mine["roots"][r["key_id"]]["revoked"] and not r.get("revoked"):
            out["discrepancies"].append(f"REVOKED_HERE_TRUSTED_THERE: root {r['key_id']} is revoked in this receiver's registry; the packet lists it as unrevoked (the receiver's state stands)")
    # -- independent checkpoint
    if checkpoint is not None:
        try:
            env = core.strict_json(checkpoint, max_bytes=64 * 1024, code="CHECKPOINT"); cv = envelope.verify(env, "prc.checkpoint", trusted); cb = env.get("body", {}) if isinstance(env, dict) else {}
        except ModuleError as exc:
            return fail(f"checkpoint unreadable: {exc.code}")
        if cv["integrity"] != "VALID":
            return fail(f"checkpoint signature {cv['integrity']}: {cv['reason']}")
        if cb.get("workspace_id") != p["workspace_id"]:
            return fail("the checkpoint is for another workspace")
        n = cb.get("journal_seq")
        if not isinstance(n, int) or n > len(skel) or (n and skel[n]["event_hash"] != cb.get("journal_tip")):
            out["checkpoint"] = "TRUNCATED_OR_ALTERED"; return fail(f"TRUNCATED_OR_ALTERED: the separately held checkpoint names event {n} with tip {str(cb.get('journal_tip'))[:12]}…; the packet's journal has {len(skel)} event(s) and does not contain it")
        out["checkpoint"] = "CONSISTENT" + ("" if cv["trust"] == "TRUSTED" else f" (signer {cv['trust']}: consistent with a checkpoint whose signer this receiver does not trust)")
    out["result"] = "SUCCESS"; out["scope"] = p["scope"]; out["origin"] = {"workspace_id": p["workspace_id"], "built_at": p["built_at"], "built_by": p["built_by"]}
    return _record(ws, out, principal, op_id, snap)


def _record(ws, out, principal, op_id, snap=None):
    if op_id:
        with ws._locked():
            for i, d in enumerate(out["discrepancies"]):
                ws._append_unlocked("SHD_TRUST_DISCREPANCY", None, {"packet_sha256": out["packet_sha256"], "discrepancy": d, "effect": "retained for an administrator's resolution; this receiver's trust state was not changed"},
                                    op_id=f"{op_id}:disc{i}", observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
            ws._append_unlocked("MODULE_PACKET_VERIFIED", None, {"packet_sha256": out["packet_sha256"], "result": out["result"], "first_discrepancy": out["first_discrepancy"], "checkpoint": out["checkpoint"],
                                "origin_workspace_id": (snap or {}).get("workspace_id"), "origin_trust_revision": (snap or {}).get("trust_revision"), "imported_into_state": "nothing"},
                                op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
    return out


def resolve_discrepancy(ws: Workspace, principal, *, packet_sha256: str, resolution: str, op_id: str) -> dict:
    from v8.workbench.modules import authz
    authz.require(principal, "admin")
    return core.append(ws, "SHD_TRUST_RESOLUTION", {"packet_sha256": core.hex64(packet_sha256, "packet sha256"), "resolution": core.text(resolution, "resolution", maxlen=1000),
                       "effect": "an administrator's note; the discrepancy record is kept; trust changes only through the SHD trust page"}, op_id=op_id, principal=principal)[0]
