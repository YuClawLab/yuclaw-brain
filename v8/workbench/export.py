"""Reproducible research export and its verification in a fresh workspace.

An export is a zip holding `canonical.json` (the research content), `EXPORT_MANIFEST.json` (export operation
metadata: export id, built-at time, candidate identity, file digests), `VERIFY.md` and a copy of the claim schema.
`canonical_digest` is the sha256 of the canonical.json bytes; the export operation's own timestamp and id live in
the manifest, OUTSIDE the digest, so two exports of the same research state reproduce the same digest.

Verification (a) refuses unsafe archives (absolute paths, traversal, symlinks, oversized or too many members),
(b) checks every declared digest and length, (c) checks the canonical bytes are canonical JSON with the declared
digest, (d) recomputes every claim-version digest whose excerpt is present, every event hash, and the supported
calculations from the packed versions and outcome, comparing them with the packed results. A changed payload,
a missing member or a tampered result fails with the first discrepancy named.

Local research export is SEPARATE from public publication: `publication_eligibility()` reports why a commitment
export is not publishable through the receipts packet in 8.0.0 (not in the PERMITTED class; rights; free-text
policy) and never adds anything to that class.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts.contracts import ContractError, canonical_json, digest, format_ts
from v8.workbench import NOT_ADVICE, calc, schema
from v8.workbench.store import Workspace, _line_hash

FORMAT = "yuclaw-commitment-export/1"
MANIFEST = "EXPORT_MANIFEST.json"
CANONICAL = "canonical.json"
INSTRUCTIONS = "VERIFY.md"
SCHEMA_COPY = "schemas/CommitmentClaim.v1.json"
REQUIRED_MEMBERS = (MANIFEST, CANONICAL, INSTRUCTIONS, SCHEMA_COPY)
MAX_ZIP_BYTES = 32 << 20
MAX_MEMBER_BYTES = 16 << 20
MAX_MEMBERS = 16
MAX_RATIO = 200
BUNDLE_RIGHTS = ("FICTIONAL", "SEC_PUBLIC_FILING")
RESEARCH_EVENTS = ("SOURCE_REGISTERED", "CLAIM_FROZEN", "CLAIM_REVISED", "SOURCE_CORRECTED", "CLAIM_WITHDRAWN", "OUTCOME_RECORDED", "ADJUDICATION_RECORDED")
_EXPORT_ID = re.compile(r"^exp-[0-9a-f]{16}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REPO = Path(__file__).resolve().parents[2]
LIMITS = [
    "Research content only: claim versions, source references (digests; excerpts only where rights allow), events, method and results. No filing bodies, no market data, no private workspace paths.",
    "Verification establishes exact bytes and recomputes the supported calculations; it does not establish scientific validity, source authenticity, independence or any investment conclusion.",
    "Source digests bind bytes; they do not prove publisher authenticity.",
    "The claim statement is the researcher's authored restatement; verbatim quotations belong in the excerpt, where the rights rule is enforced.",
    "An export is not a backup, a disaster-recovery copy or a publication. Backup creation and restoration are not provided in 8.0.0.",
    "Fictional fixture data is a demonstration, never a validated dataset product.",
    NOT_ADVICE,
]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _source_ref(src: dict) -> dict:
    ref = {k: src[k] for k in ("kind", "form", "accession", "url", "filed_at", "available_as_of", "source_hash", "fictional", "rights")}
    if src["rights"] in BUNDLE_RIGHTS:
        ref["excerpt"] = src["excerpt"]; ref["excerpt_included"] = True
    else:
        ref["excerpt_included"] = False; ref["excerpt_withheld_reason"] = "rights UNKNOWN: excerpt bytes are not bundled; the digest still binds them"
    return ref


def _redact_claim(claim: dict) -> dict:
    c = {k: v for k, v in claim.items() if not k.startswith("_")}
    if c["source"]["rights"] not in BUNDLE_RIGHTS:
        s = dict(c["source"]); s["excerpt"] = None; s["excerpt_redacted"] = True; c["source"] = s
    return c


def build_canonical(state: dict) -> dict:
    """The research content of one claim (JSON-safe, rights-filtered). Deterministic for a given state."""
    versions = []
    for v in state["versions"]:
        versions.append({"version_id": v["version_id"], "type": v["type"], "claim": _redact_claim(v["claim"]), "claim_digest": v["claim"]["_digest"], "event_hash": v["event_hash"],
                         "time": v["time"], "reason": v.get("reason"), "notes": v.get("notes"), "supersedes": v.get("supersedes")})
    outcome = None
    if state["outcome"] is not None:
        o = {k: v for k, v in state["outcome"].items() if not k.startswith("_")}
        if o["source"]["rights"] not in BUNDLE_RIGHTS:
            s = dict(o["source"]); s["excerpt"] = None; s["excerpt_redacted"] = True; o["source"] = s
        outcome = {"outcome": o, "outcome_digest": state["outcome"]["_digest"], "event_hash": state["outcome"]["_event_hash"], "time": state["outcome"]["_time"]}
    withdrawn = None
    if state["withdrawn"] is not None:
        w = state["withdrawn"]; withdrawn = {"revision_id": w["revision_id"], "reason": w["reason"], "supersedes": w["supersedes"], "source": _source_ref(w["source"]), "event_hash": w["event_hash"], "time": w["time"]}
    srcs = [_source_ref(v["claim"]["source"]) for v in state["versions"]]
    if state["outcome"] is not None:
        srcs.append(_source_ref(state["outcome"]["source"]))
    if state["withdrawn"] is not None:
        srcs.append(_source_ref(state["withdrawn"]["source"]))
    # research events only: export/verification events are operation metadata and stay outside the canonical content,
    # so two exports of the same research state reproduce the same canonical digest
    events = [dict(e) for e in state["events"] if e["kind"] in RESEARCH_EVENTS]
    results = calc.adjudicate(state)
    orig_eff = next((v for v in reversed(state["versions"]) if v["type"] == "CORRECTED_SOURCE"), state["versions"][0])
    revised = [v for v in state["versions"] if v["type"] == "REVISED"]
    comparison = calc.compare_versions(orig_eff["claim"], revised[-1]["claim"]) if revised else None
    can = {"schema": FORMAT, "claim_id": state["claim_id"], "fictional": bool(state["versions"][0]["claim"]["fictional"]), "versions": versions, "withdrawn": withdrawn, "outcome": outcome,
           "adjudications": [{k: v for k, v in a.items()} for a in state["adjudications"]], "sources": srcs, "events": events,
           "method": {"calculator": calc.CALCULATOR, "rule": results["rule"], "rule_text": results["rule_text"], "formula": calc.FORMULA, "no_inference": calc.NO_INFERENCE,
                      "time_semantics": "source_available_as_of = public availability of the source; observed_at = when this workspace saw it; recorded_at = local action time; as-of views cut by source availability"},
           "results": results, "comparison": comparison, "limitations": LIMITS, "not_advice": NOT_ADVICE}
    # events carry the same excerpts as versions/outcome; withhold them under the same rights rule
    withheld = {s["source_hash"] for s in srcs if not s["excerpt_included"]}
    if withheld:
        for ev in can["events"]:
            p = ev.get("payload", {})
            for holder in ([p.get("claim"), p.get("outcome"), p] if isinstance(p, dict) else []):
                if isinstance(holder, dict) and isinstance(holder.get("source"), dict) and holder["source"].get("source_hash") in withheld:
                    holder["source"] = dict(holder["source"], excerpt=None, excerpt_redacted=True)
    return can


def instructions(man: dict) -> str:
    rows = "\n".join(f"| {f['path']} | {f['sha256']} | {f['size_bytes']} |" for f in man["files"])
    return f"""# YUCLAW commitment research export — verification

Export `{man['export_id']}` built {man['built_at']} for claim `{man['claim_id']}` (candidate commit: {man['candidate'].get('commit') or 'not recorded'}).
Canonical research digest: `{man['canonical_digest']}` (sha256 of canonical.json; the export id and built-at time are outside it).

## Verify without an account or a service
```
python3 -m v8.workbench verify-export <this zip>
```
or open the workbench of a FRESH workspace, choose "Verify an export" and upload this zip. Both paths refuse unsafe archives,
check every digest and length, re-derive every claim digest and event hash, and recompute the calculations from the packed
versions and outcome. A changed payload fails with the first discrepancy named.

## Files
| path | sha256 | bytes |
|---|---|---|
{rows}

## Limitations
""" + "\n".join(f"- {l}" for l in man["limitations"]) + "\n"


def build_export(ws: Workspace, claim_id: str, *, export_id: str | None = None, built_at: datetime | None = None, candidate_commit: str | None = None, op_id: str | None = None) -> dict:
    state = ws.claim_state(claim_id)
    if state is None:
        raise ContractError(f"claim {claim_id!r} is not frozen")
    can = build_canonical(state)
    can_bytes = canonical_json(can)
    cdig = _sha(can_bytes)
    eid = export_id or f"exp-{secrets.token_hex(8)}"
    if not _EXPORT_ID.match(eid):
        raise ContractError("export_id must look like exp-<16 hex>")
    built = format_ts(built_at or datetime.now(timezone.utc))
    schema_bytes = (_REPO / "schemas" / "CommitmentClaim.v1.json").read_bytes()
    man = {"format": FORMAT, "export_id": eid, "built_at": built, "claim_id": claim_id, "canonical_digest": cdig,
           "candidate": {"commit": candidate_commit or os.environ.get("YUCLAW_CANDIDATE_COMMIT"), "workbench": "v8.workbench/1"},
           "digest_rule": "canonical_digest = sha256(canonical.json bytes) where canonical.json is canonical JSON (sorted keys, no whitespace, ASCII); export_id and built_at are excluded",
           "files": [{"path": CANONICAL, "sha256": cdig, "size_bytes": len(can_bytes)}, {"path": SCHEMA_COPY, "sha256": _sha(schema_bytes), "size_bytes": len(schema_bytes)}],
           "verify": "python3 -m v8.workbench verify-export <zip>", "limitations": LIMITS, "not_advice": NOT_ADVICE}
    man_bytes = (json.dumps(man, indent=1, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")
    ins_bytes = instructions(man).encode("utf-8")
    out_dir = ws.exports / eid
    out_dir.mkdir(parents=True, exist_ok=True)
    zpath = ws.exports / f"{eid}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in ((MANIFEST, man_bytes), (CANONICAL, can_bytes), (INSTRUCTIONS, ins_bytes), (SCHEMA_COPY, schema_bytes)):
            zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED; zi.external_attr = (0o100600 << 16)
            z.writestr(zi, data)
            (out_dir / name).parent.mkdir(parents=True, exist_ok=True); (out_dir / name).write_bytes(data)
    zb = buf.getvalue()
    tmp = zpath.with_suffix(".zip.part")
    tmp.write_bytes(zb); os.chmod(tmp, 0o600)
    with open(tmp, "rb") as fh:
        os.fsync(fh.fileno())
    os.replace(tmp, zpath)                                   # an interrupted build never leaves a half zip under the final name
    zs = _sha(zb)
    ev, dup = ws.record_export(claim_id, export_id=eid, canonical_digest=cdig, zip_sha256=zs, zip_name=zpath.name, op_id=op_id or f"export:{eid}")
    return {"export_id": eid, "canonical_digest": cdig, "zip_path": str(zpath), "zip_name": zpath.name, "zip_sha256": zs, "zip_bytes": len(zb), "manifest": man, "event": ev, "duplicate": dup}


# ---------------------------------------------------------------- verification
def _member_error(zi: zipfile.ZipInfo) -> str | None:
    n = zi.filename
    if not n or n.endswith("/") or n.startswith("/") or "\\" in n or ".." in n.split("/") or any(p in ("", ".") for p in n.split("/")) or re.match(r"^[A-Za-z]:", n):
        return f"unsafe member name {n!r}"
    if (zi.external_attr >> 16) & 0o170000 == 0o120000:
        return f"symlink member {n!r} refused"
    if zi.file_size > MAX_MEMBER_BYTES:
        return f"member {n!r} exceeds {MAX_MEMBER_BYTES} bytes"
    if zi.compress_size and zi.file_size / max(zi.compress_size, 1) > MAX_RATIO:
        return f"member {n!r} compression ratio refused"
    return None


def read_zip_safely(zip_path) -> tuple[dict[str, bytes] | None, str | None, str | None]:
    """(members, zip_sha256, error). Members are read fully into memory within the bounds; nothing is extracted to disk."""
    p = Path(zip_path)
    try:
        raw = p.read_bytes()
    except OSError as exc:
        return None, None, f"archive unreadable ({exc.__class__.__name__})"
    if len(raw) > MAX_ZIP_BYTES:
        return None, None, f"archive exceeds {MAX_ZIP_BYTES} bytes"
    zs = _sha(raw)
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        return None, zs, "not a zip archive"
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist()
            if len(infos) > MAX_MEMBERS:
                return None, zs, f"more than {MAX_MEMBERS} members"
            members = {}
            for zi in infos:
                err = _member_error(zi)
                if err:
                    return None, zs, err
                if zi.filename in members:
                    return None, zs, f"duplicate member {zi.filename!r}"
                data = z.read(zi)
                if len(data) != zi.file_size:
                    return None, zs, f"member {zi.filename!r} size differs from its header"
                members[zi.filename] = data
    except (zipfile.BadZipFile, RuntimeError, ValueError, OSError) as exc:
        return None, zs, f"archive rejected ({exc.__class__.__name__})"
    return members, zs, None


def _state_from_canonical(can: dict) -> dict:
    versions = [{"version_id": v["version_id"], "type": v["type"], "claim": dict(v["claim"], _digest=v["claim_digest"]), "event_hash": v["event_hash"], "time": v["time"]} for v in can["versions"]]
    withdrawn = None
    if can.get("withdrawn"):
        w = can["withdrawn"]; withdrawn = {"revision_id": w["revision_id"], "source": w["source"], "reason": w["reason"]}
    outcome = None
    if can.get("outcome"):
        outcome = dict(can["outcome"]["outcome"], _digest=can["outcome"]["outcome_digest"])
    return {"claim_id": can["claim_id"], "versions": versions, "withdrawn": withdrawn, "outcome": outcome, "adjudications": can.get("adjudications", []), "events": can.get("events", [])}


def verify_export(zip_path) -> dict:
    """Never raises. {'result': SUCCESS|MISMATCH|UNSUPPORTED, 'first_discrepancy', 'checks': [...], 'zip_sha256', 'canonical_digest', 'claim_id', 'recompute': {...}}"""
    checks: list[dict] = []
    def unsupported(msg, zs=None, cdig=None, cid=None):
        return {"result": "UNSUPPORTED", "first_discrepancy": msg, "checks": checks, "zip_sha256": zs, "canonical_digest": cdig, "claim_id": cid, "recompute": None}
    members, zs, err = read_zip_safely(zip_path)
    if err:
        return unsupported(f"refused: {err}", zs)
    checks.append({"check": "archive-safety", "ok": True, "note": f"{len(members)} members within bounds; no traversal, symlink or oversized member"})
    missing = [m for m in REQUIRED_MEMBERS if m not in members]
    if missing:
        checks.append({"check": "required-members", "ok": False, "missing": missing})
        return {"result": "MISMATCH", "first_discrepancy": f"incomplete packet: missing {missing}", "checks": checks, "zip_sha256": zs, "canonical_digest": None, "claim_id": None, "recompute": None}
    checks.append({"check": "required-members", "ok": True})
    try:
        man = json.loads(members[MANIFEST].decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return unsupported("manifest is not JSON", zs)
    if not isinstance(man, dict) or man.get("format") != FORMAT or not isinstance(man.get("files"), list) or not _HEX64.match(str(man.get("canonical_digest", ""))):
        return unsupported("manifest invalid (format, files or canonical_digest)", zs)
    cdig, cid = man["canonical_digest"], man.get("claim_id")
    first = None
    for f in man["files"]:
        if not isinstance(f, dict) or set(f) != {"path", "sha256", "size_bytes"} or f["path"] not in members:
            first = first or f"manifest lists {f.get('path') if isinstance(f, dict) else f!r} which the archive lacks"
            checks.append({"check": "sha256+length", "path": (f.get("path") if isinstance(f, dict) else None), "ok": False}); continue
        data = members[f["path"]]; ok = (_sha(data) == f["sha256"] and len(data) == f["size_bytes"])
        checks.append({"check": "sha256+length", "path": f["path"], "ok": ok, "observed": {"sha256": _sha(data), "size_bytes": len(data)}})
        if not ok:
            first = first or f"byte mismatch at {f['path']}: expected {f['sha256'][:16]}…/{f['size_bytes']} B, observed {_sha(data)[:16]}…/{len(data)} B"
    can_bytes = members[CANONICAL]
    if _sha(can_bytes) != cdig:
        first = first or f"canonical digest mismatch: manifest {cdig[:16]}…, observed {_sha(can_bytes)[:16]}…"
        checks.append({"check": "canonical-digest", "ok": False})
    else:
        checks.append({"check": "canonical-digest", "ok": True})
    if first:
        return {"result": "MISMATCH", "first_discrepancy": first, "checks": checks, "zip_sha256": zs, "canonical_digest": cdig, "claim_id": cid, "recompute": None}
    try:
        can = json.loads(can_bytes.decode("ascii"))
    except (ValueError, UnicodeDecodeError):
        return unsupported("canonical.json is not ASCII JSON", zs, cdig, cid)
    if canonical_json(can) != can_bytes:
        return {"result": "MISMATCH", "first_discrepancy": "canonical.json is not in canonical form (re-serialization differs)", "checks": checks, "zip_sha256": zs, "canonical_digest": cdig, "claim_id": cid, "recompute": None}
    checks.append({"check": "canonical-form", "ok": True})
    if not isinstance(can, dict) or can.get("schema") != FORMAT or can.get("claim_id") != cid or not can.get("versions"):
        return unsupported("canonical content invalid (schema, claim_id or versions)", zs, cdig, cid)
    # claim digests (recomputable only when the excerpt is present), event hashes, outcome digest
    for v in can["versions"]:
        c = v["claim"]
        if c["source"].get("excerpt") is None:
            checks.append({"check": "claim-digest", "version": v["version_id"], "ok": None, "note": "excerpt withheld by rights; digest not recomputable here"}); continue
        try:
            norm = schema.validate_claim(c)
        except ContractError as exc:
            first = first or f"version {v['version_id']}: packed claim invalid: {exc}"; checks.append({"check": "claim-valid", "version": v["version_id"], "ok": False}); continue
        ok = schema.claim_digest(norm) == v["claim_digest"]
        checks.append({"check": "claim-digest", "version": v["version_id"], "ok": ok})
        if not ok:
            first = first or f"version {v['version_id']}: claim digest does not match its content"
    if can.get("outcome") and can["outcome"]["outcome"]["source"].get("excerpt") is not None:
        try:
            ok = digest(schema.validate_outcome(can["outcome"]["outcome"])) == can["outcome"]["outcome_digest"]
        except ContractError:
            ok = False
        checks.append({"check": "outcome-digest", "ok": ok})
        if not ok:
            first = first or "outcome digest does not match its content"
    hashes = set()
    for i, ev in enumerate(can.get("events", [])):
        body = {k: v for k, v in ev.items() if k != "event_hash"}
        redacted = any(isinstance(h, dict) and isinstance(h.get("source"), dict) and h["source"].get("excerpt_redacted") for h in (ev.get("payload", {}).get("claim"), ev.get("payload", {}).get("outcome"), ev.get("payload")))
        if redacted:
            checks.append({"check": "event-hash", "seq": ev.get("seq"), "ok": None, "note": "excerpt withheld by rights"}); hashes.add(ev["event_hash"]); continue
        ok = _line_hash(body) == ev.get("event_hash")
        hashes.add(ev.get("event_hash"))
        checks.append({"check": "event-hash", "seq": ev.get("seq"), "ok": ok})
        if not ok:
            first = first or f"event {ev.get('seq')}: event_hash does not match its content"
    for a in can.get("adjudications", []):
        unknown = [h for h in a.get("evidence", []) if h not in hashes]
        if unknown:
            first = first or f"adjudication evidence references unknown event {unknown[0][:12]}"; checks.append({"check": "adjudication-evidence", "ok": False})
    if first:
        return {"result": "MISMATCH", "first_discrepancy": first, "checks": checks, "zip_sha256": zs, "canonical_digest": cdig, "claim_id": cid, "recompute": None}
    # recompute the supported calculations from the packed versions and outcome
    try:
        st = _state_from_canonical(can)
        recomputed = calc.adjudicate(st)
        orig_eff = next((v for v in reversed(st["versions"]) if v["type"] == "CORRECTED_SOURCE"), st["versions"][0])
        revised = [v for v in st["versions"] if v["type"] == "REVISED"]
        recomparison = calc.compare_versions(orig_eff["claim"], revised[-1]["claim"]) if revised else None
    except Exception as exc:                                # a malformed packet must not produce a traceback
        return unsupported(f"recompute raised {exc.__class__.__name__}: {exc}", zs, cdig, cid)
    same_results = json.loads(canonical_json(recomputed)) == can["results"]
    same_comparison = json.loads(canonical_json(recomparison)) == can.get("comparison")
    checks.append({"check": "recompute-results", "ok": same_results, "observed": recomputed["result"], "packed": can["results"].get("result")})
    checks.append({"check": "recompute-comparison", "ok": same_comparison})
    rec = {"result": recomputed["result"], "original": recomputed["original"]["result"], "revised": None if recomputed["revised"] is None else recomputed["revised"]["result"],
           "delta_vs_original_midpoint": recomputed.get("delta_vs_original_midpoint"), "delta_vs_revised_midpoint": recomputed.get("delta_vs_revised_midpoint"), "comparison": None if recomparison is None else recomparison["result"]}
    if not same_results:
        return {"result": "MISMATCH", "first_discrepancy": f"recomputed result {recomputed['result']} differs from the packed results block", "checks": checks, "zip_sha256": zs, "canonical_digest": cdig, "claim_id": cid, "recompute": rec}
    if not same_comparison:
        return {"result": "MISMATCH", "first_discrepancy": "recomputed comparison differs from the packed comparison block", "checks": checks, "zip_sha256": zs, "canonical_digest": cdig, "claim_id": cid, "recompute": rec}
    return {"result": "SUCCESS", "first_discrepancy": None, "checks": checks, "zip_sha256": zs, "canonical_digest": cdig, "claim_id": cid, "recompute": rec,
            "meaning": "exact bytes verified and the supported calculations reproduced from the packed claim versions and outcome; not a research interpretation, not proof of source authenticity, not a publication"}


def publication_eligibility(can: dict) -> dict:
    """Why this export is NOT publishable through the receipts packet in 8.0.0. Never changes any policy."""
    from v3.receipts import packet as v7packet
    from v3.receipts.export import publication_policy, text_publishable
    in_class = any(p.startswith("commitments/") for p in v7packet.PERMITTED)
    rights = sorted({s["rights"] for s in can.get("sources", [])})
    policy = publication_policy()
    texts = []
    for v in can["versions"]:
        texts.append(("statement", v["claim"]["statement"]))
        if v["claim"]["source"].get("excerpt"):
            texts.append(("excerpt", v["claim"]["source"]["excerpt"]))
        if v.get("notes"):
            for k, t in v["notes"].items():
                if t:
                    texts.append((f"notes.{k}", t))
    for a in can.get("adjudications", []):
        texts.append(("adjudication.reason", a.get("reason", "")))
        if a.get("conflicts"):
            texts.append(("adjudication.conflicts", a["conflicts"]))
    free_text = [{"field": f, "ok": ok, "why": why} for f, t in texts for ok, why in [text_publishable(t)]]
    reasons = ["commitments/<claim_id>.json is not in the receipts packet PERMITTED class; adding it is an owner decision (V8-001 §5 proposal step 4) and is not executed automatically"]
    if can.get("fictional"):
        reasons.append("fictional demonstration data is never published as research")
    if "UNKNOWN" in rights:
        reasons.append("a source with UNKNOWN rights is present; its excerpt is withheld from the export and nothing derived from it is publishable")
    if not policy["free_text_publishable"]:
        reasons.append("free-text publication policy unavailable (denylist or language rail missing; fail closed)")
    bad = [f for f in free_text if not f["ok"]]
    if bad:
        reasons.append(f"free text fails the publication gates: {[b['field'] + ':' + b['why'] for b in bad][:5]}")
    return {"eligible": False, "in_packet_permitted_class": in_class, "rights_present": rights, "policy": policy, "free_text": free_text, "reasons": reasons,
            "meaning": "local research export and public publication are separate decisions; this record explains the second, it never performs it"}
