"""BriefPacket/1 — a portable verification packet, a readable static HTML brief and JSON records; and their verification
in a fresh workspace without the author's database, credentials or machine paths.

Members (fixed names, bounded sizes, no paths outside the root): BRIEF_MANIFEST.json, brief.json (the reducer view with
private fields removed), records.json (spans, transforms, receipts, reports, calibrations, resolutions, measurements),
snapshot.json (rights-filtered), text/<view_sha256>.txt for every version of the brief, brief.html, appendix.md,
VERIFY.md. Rights are enforced before any text travels: source excerpts only for BUNDLE_RIGHTS; prompts and raw provider
responses only when their disclosure is `permitted`; API keys, signing secrets and workspace paths never.

Verification recomputes what the packet carries enough material for and declares each result separately:
VERIFIED / FAILED / NOT_RECOMPUTABLE / REPORT_ONLY / UNSUPPORTED / NOT_APPLICABLE. A manifest hash or a badge never
substitutes for these. The packet identifies itself as v9; a v8 export verifies through the v8 verifier unchanged.
"""
from __future__ import annotations

import html
import io
import json
import os
import re
import secrets
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts.contracts import ContractError, canonical_json, digest, format_ts
from v8.workbench import export as v8export
from v8.workbench.modules import envelope
from v8.workbench.store import Workspace
from v9 import V9_VERSION
from v9.brief import compose, contracts, finance, measure, reducer, reports, snapshot
from v9.brief.i18n import t
from v9.brief.sidecar import Sidecar, now_ts

FORMAT = contracts.BRIEF_PACKET
MANIFEST = "BRIEF_MANIFEST.json"
BRIEF_JSON, RECORDS_JSON, SNAPSHOT_JSON, HTML_MEMBER, APPENDIX, INSTRUCTIONS = "brief.json", "records.json", "snapshot.json", "brief.html", "appendix.md", "VERIFY.md"
REQUIRED = (MANIFEST, BRIEF_JSON, RECORDS_JSON, SNAPSHOT_JSON, HTML_MEMBER, APPENDIX, INSTRUCTIONS)
MAX_MEMBERS = 64
_PACKET_ID = re.compile(r"^bpk-[0-9a-f]{16}$")
_TEXT_MEMBER = re.compile(r"^text/([0-9a-f]{64})\.txt$")
CSP = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
LIMITS = ["A brief packet carries recorded statements, their bindings and the checks that can be recomputed from permitted material; it establishes none of: source authenticity, factual truth, human authorship, independent review, legal compliance, publication approval.",
          "Rights: source excerpts travel only for FICTIONAL, SEC_PUBLIC_FILING or operator-own text; prompts and raw provider responses only when disclosure is permitted; withheld inputs make a check NOT_RECOMPUTABLE, never a failure.",
          "A detector report that cannot be rerun here is REPORT_ONLY; its calibration applicability is whatever the enrolled calibration record of the RECEIVING workspace supports.",
          "Signatures are evaluated against the receiving workspace's own trust roots; an unknown signer is reported as unknown, never enrolled by the packet.",
          "Operation measurements count software attempts and durations; they are not labour time or cognitive effort.", "Research and education only. Not investment advice."]


def _esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


# ------------------------------------------------------------------ readable HTML (static, no scripts, no remote fetches)
def _trust_words(s: dict) -> str:
    return ", ".join(f"{r['record_id'][:8]}: {r['signature']['signature']}/{r['signature']['trust']}" for r in (s["issuer_trust"]["receipts"] + s["issuer_trust"]["reports"]))


def render_html(view: dict, lang: str) -> str:
    fr = lang == "fr"
    chips = []
    for s in view["statements"]:
        sup = s["substantive_support"]["status"]
        chips.append(f'<li id="s{s["n"]}" class="st {_esc(sup)}"><span class="n">{s["n"]}</span> <span class="txt">{_esc(s["text"])}</span>'
                     f'<dl><dt>{_esc(t("dim.byte_integrity", lang))}</dt><dd>{_esc(s["byte_integrity"]["status"])}</dd>'
                     f'<dt>{_esc(t("dim.recorded_origin", lang))}</dt><dd>{_esc(s["recorded_origin"]["transform"])} · {_esc(s["recorded_origin"]["implementation"])}</dd>'
                     f'<dt>{_esc(t("dim.issuer_trust", lang))}</dt><dd>{_esc(_trust_words(s) or t("label.signature.none", lang))}</dd>'
                     f'<dt>{_esc(t("dim.substantive_support", lang))}</dt><dd><b>{_esc(sup)}</b> — {_esc(s["substantive_support"]["label"])} <i>{_esc(s["substantive_support"]["method"])}</i><br><small>{_esc(s["substantive_support"]["limits"])}</small></dd>'
                     f'<dt>{_esc(t("dim.time_scope", lang))}</dt><dd>{_esc(s["time_scope"]["label"])}</dd>'
                     f'<dt>{_esc(t("dim.detector", lang))}</dt><dd>{_esc(s["detector"]["label"])}</dd></dl></li>')
    body = "\n".join(chips)
    never = "".join(f"<li>{_esc(x)}</li>" for x in view["never_claims"])
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{CSP}"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(view['title'])} — YUCLAW brief {_esc(view['brief_id'])} {_esc(view['version_id'])}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:900px;margin:1.5rem auto;padding:0 16px;color:#111;background:#fff}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f7f8;padding:1rem;border-radius:6px}}
.st{{border-left:4px solid #999;padding:.4rem .8rem;margin:.6rem 0;list-style:none}}.st.SUPPORTED{{border-color:#1a7f37}}.st.UNRESOLVED,.st.NOT_ASSESSED{{border-color:#9a6700}}.st.CONTRADICTED,.st.INVALIDATED{{border-color:#b42318}}.st.ATTRIBUTED{{border-color:#0b57d0}}
.n{{display:inline-block;min-width:1.6em;font-weight:700}}dl{{display:grid;grid-template-columns:max-content 1fr;gap:.1rem .8rem;font-size:.9em;margin:.3rem 0 0}}dt{{color:#555}}small{{color:#555}}h1,h2{{line-height:1.25}}@media (max-width:420px){{dl{{grid-template-columns:1fr}}}}</style></head>
<body><p><b>{_esc(view['not_advice'])}</b></p><h1>{_esc(view['title'])}</h1>
<p>{_esc(view['brief_id'])} · {_esc(t('word.version', lang))} {_esc(view['version_id'])} · {_esc(view['language'])} · {_esc(t('word.created', lang))} {_esc(view['recorded_at'])} · snapshot <code>{_esc(view['snapshot_digest'][:16])}…</code> · <b>{_esc(view.get('evidence_label'))}</b></p>
<p><i>{_esc(view['mission'])} {_esc(view['vision'])}</i></p>
<h2>{_esc("Texte" if fr else "Text")}</h2><pre>{_esc(view['text'])}</pre>
<h2>{_esc(t('brief.inspect', lang))}</h2><p>{_esc(view['coverage']['sentence'])} {_esc(view['dimension_note'])}</p><ol>{body}</ol>
<h2>{_esc("Limites" if fr else "Limits")}</h2><ul>{never}</ul></body></html>"""


# ------------------------------------------------------------------ public views (rights)
def _public_receipt(rec: dict) -> dict:
    """The record as imported: it never holds prompt text (only a digest), so it travels unchanged and its signed body stays bound."""
    return dict(rec)


def _public_report(rec: dict) -> dict:
    """The record as imported: raw response bytes live in the vault, never in the record, so the signed body stays bound."""
    return dict(rec)


def _public_view(view: dict) -> dict:
    v = dict(view)
    v.pop("missing_objects", None)
    return v


# ------------------------------------------------------------------ build
def build_packet(ws: Workspace, sc: Sidecar, brief_id: str, version_id: str | None = None, *, lang: str | None = None, op_id: str | None = None, actor: str = "host-operator(cli)",
                 built_at: datetime | None = None, packet_id: str | None = None, candidate_commit: str | None = None) -> dict:
    vrec = compose.version(sc, brief_id, version_id); p = vrec["payload"]
    if sc.missing_objects(vrec):
        raise ContractError("this version is INCOMPLETE (prepared objects missing); an incomplete brief is never exported as complete")
    lang = lang or p["language"]
    view = reducer.brief_view(ws, sc, brief_id, p["version_id"], lang)
    recs = sc.load()["records"]
    snap = snapshot.public_view(sc.get_object(p["snapshot_object"]))
    all_versions = compose.versions_of(sc, brief_id, recs)
    texts = {}
    for r in all_versions:
        h = r["payload"]["text_view"]["view_sha256"]
        if sc.has(h):
            texts[h] = sc.get_bytes(h)
    roots = reports.trust_roots(sc, recs)
    records = {"schema": "yuclaw.brief-records/1", "brief_id": brief_id, "version_id": p["version_id"],
               "versions": [{"version_id": r["payload"]["version_id"], "parent_version": r["payload"]["parent_version"], "language": r["payload"]["language"], "text_view": r["payload"]["text_view"],
                             "spans": compose.effective_spans(sc, r, recs), "transform": r["payload"]["transform"], "receipt": _public_receipt(r["payload"]["receipt"]), "production": r["payload"].get("production"),
                             "snapshot_digest": r["payload"]["snapshot_digest"], "v8_tip_at_snapshot": r["payload"]["v8_tip_at_snapshot"], "recorded_at": r["time"]["recorded_at"], "record_hash": r["record_hash"]} for r in all_versions],
               "receipts": [{"record": _public_receipt(r["payload"]["record"]), "signature": r["payload"]["signature"], "imported_at": r["payload"]["imported_at"]} for r in sc.records("RECEIPT_IMPORTED", None, recs) if r["payload"]["record"]["assembled_output_sha256"] in texts],
               "reports": [{"record": _public_report(r["payload"]["record"]), "signature": r["payload"]["signature"], "imported_at": r["payload"]["imported_at"]} for r in sc.records("REPORT_IMPORTED", None, recs) if r["payload"]["record"]["view_sha256"] in texts],
               "calibrations": [{"record": r["payload"]["record"], "signature": r["payload"]["signature"]} for r in sc.records("CALIBRATION_IMPORTED", None, recs)],
               "resolutions": [r["payload"] for r in sc.records("REVIEW_ITEM_RESOLVED", brief_id, recs)],
               "trust_roots_of_author": {k: {"label": r["label"], "revoked": r["revoked"]} for k, r in roots.items()},
               "measurements": measure.aggregate(sc), "research_cutoff": {"v8_tip": p["v8_tip_at_snapshot"], "snapshot_digest": p["snapshot_digest"], "packet_built_at": None}}
    software = {"yuclaw_v9": V9_VERSION, "reducer": reducer.REDUCER, "calculator": finance.CALCULATOR, "renderer": (p.get("production") or {}).get("renderer") or "none", "candidate_commit": candidate_commit or os.environ.get("YUCLAW_CANDIDATE_COMMIT") or "not recorded"}
    pid = packet_id or f"bpk-{secrets.token_hex(8)}"
    if not _PACKET_ID.match(pid):
        raise ContractError("packet_id must look like bpk-<16 hex>")
    built = format_ts(built_at or datetime.now(timezone.utc))
    records["research_cutoff"]["packet_built_at"] = built
    members = {BRIEF_JSON: canonical_json(_public_view(view)), RECORDS_JSON: canonical_json(records), SNAPSHOT_JSON: canonical_json(snap),
               HTML_MEMBER: render_html(view, lang).encode("utf-8"), APPENDIX: measure.appendix(view, records["measurements"], software=software, lang=lang).encode("utf-8")}
    for h, b in texts.items():
        members[f"text/{h}.txt"] = b
    files = [{"path": k, "sha256": contracts.sha256_hex(v), "size_bytes": len(v)} for k, v in sorted(members.items())]
    man = {"format": FORMAT, "packet_id": pid, "built_at": built, "brief_id": brief_id, "version_id": p["version_id"], "language": lang, "workspace_id": ws.meta["workspace_id"],
           "verifier": "v9.brief.packet/1", "software": software, "snapshot_digest": p["snapshot_digest"], "research_cutoff": records["research_cutoff"], "files": files,
           "content_digest": digest(files), "omitted": _omitted(records, snap), "verify": "python3 -m v9.brief verify <zip>   (or: yuclaw workbench brief verify <zip>)", "limitations": LIMITS}
    man_bytes = (json.dumps(man, indent=1, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")
    ins = _instructions(man).encode("utf-8")
    zpath = ws.exports / f"{pid}.zip"; buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in [(MANIFEST, man_bytes), (INSTRUCTIONS, ins)] + sorted(members.items()):
            zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED; zi.external_attr = (0o100600 << 16)
            z.writestr(zi, data)
    zb = buf.getvalue(); tmp = zpath.with_suffix(".zip.part"); tmp.write_bytes(zb); os.chmod(tmp, 0o600)
    with open(tmp, "rb") as fh:
        os.fsync(fh.fileno())
    os.replace(tmp, zpath)
    zs = contracts.sha256_hex(zb)
    rec, dup = sc.append("PACKET_BUILT", brief_id, {"packet_id": pid, "version_id": p["version_id"], "zip_sha256": zs, "zip_name": zpath.name, "content_digest": man["content_digest"], "language": lang, "objects": []},
                         op_id=op_id or f"packet:{pid}", actor=actor)
    return {"packet_id": pid, "zip_path": str(zpath), "zip_name": zpath.name, "zip_sha256": zs, "zip_bytes": len(zb), "content_digest": man["content_digest"], "manifest": man, "record": rec, "duplicate": dup}


def _omitted(records: dict, snap: dict) -> list[dict]:
    out = []
    for cid, c in snap["claims"].items():
        for sid, s in c["sources"].items():
            if s.get("excerpt") is None:
                out.append({"component": f"source excerpt {sid}", "reason": s.get("excerpt_withheld"), "effect": "quotation and claim-digest checks over that excerpt are NOT_RECOMPUTABLE"})
    for r in records["receipts"] + [{"record": v["receipt"]} for v in records["versions"]]:
        if r["record"].get("prompt_sha256") and r["record"].get("prompt_disclosure") != "permitted":
            out.append({"component": f"prompt of receipt {r['record']['record_id'][:12]}", "reason": "prompt disclosure not permitted; digest only", "effect": "prompt binding is NOT_RECOMPUTABLE"})
    for r in records["reports"]:
        if r["record"].get("response_sha256") and r["record"].get("disclosure") != "permitted":
            out.append({"component": f"raw response of report {r['record']['record_id'][:12]}", "reason": "disclosure not permitted; digest only", "effect": "the report is REPORT_ONLY"})
    return out


def _instructions(man: dict) -> str:
    rows = "\n".join(f"| {f['path']} | {f['sha256']} | {f['size_bytes']} |" for f in man["files"])
    return f"""# YUCLAW brief packet — verification

Packet `{man['packet_id']}` built {man['built_at']} for brief `{man['brief_id']}` version `{man['version_id']}` ({man['language']}). Content digest `{man['content_digest']}` (sha256 of the canonical file list; packet id and built-at are outside it).

```
{man['verify']}
```
Both routes refuse unsafe archives, check every digest and length, re-derive every span binding and every registered calculation from the typed inputs, re-check signatures against the RECEIVING workspace's trust roots, and declare each result separately: VERIFIED, FAILED, NOT_RECOMPUTABLE, REPORT_ONLY, UNSUPPORTED or NOT_APPLICABLE.

| path | sha256 | bytes |
|---|---|---|
{rows}

## Omitted or non-recomputable components
""" + ("\n".join(f"- {o['component']}: {o['reason']} → {o['effect']}" for o in man["omitted"]) or "- none") + "\n\n## Limitations\n" + "\n".join(f"- {l}" for l in man["limitations"]) + "\n"


# ------------------------------------------------------------------ verify
def read_packet(zip_path) -> tuple[dict | None, str | None, str | None]:
    """Bounded read with the v8 member rules but a larger member cap (text members are one per version)."""
    p = Path(zip_path)
    try:
        raw = p.read_bytes()
    except OSError as exc:
        return None, None, f"archive unreadable ({exc.__class__.__name__})"
    if len(raw) > v8export.MAX_ZIP_BYTES:
        return None, None, f"archive exceeds {v8export.MAX_ZIP_BYTES} bytes"
    zs = contracts.sha256_hex(raw)
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        return None, zs, "not a zip archive"
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist()
            if len(infos) > MAX_MEMBERS:
                return None, zs, f"more than {MAX_MEMBERS} members"
            members = {}
            for zi in infos:
                err = v8export._member_error(zi)
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


def verify_packet(zip_path, *, receiver: Sidecar | None = None) -> dict:
    """Never raises. Per-check outcomes; result SUCCESS when no check FAILED (NOT_RECOMPUTABLE and REPORT_ONLY do not fail),
    MISMATCH on any FAILED, UNSUPPORTED for an unknown or unreadable packet."""
    checks: list[dict] = []
    def done(result, first=None, **kw):
        counts = {k: sum(1 for c in checks if c["outcome"] == k) for k in contracts.CHECK_OUTCOMES}
        return {"result": result, "first_discrepancy": first, "checks": checks, "outcome_counts": counts, "format": FORMAT, **kw,
                "meaning": {"SUCCESS": "every recomputable binding and calculation reproduced; non-recomputable and report-only components are listed, not assumed; nothing here establishes truth, authorship or approval",
                            "MISMATCH": "at least one binding or calculation did not reproduce (the first is named)", "UNSUPPORTED": "not a v9 brief packet this verifier understands; nothing was reinterpreted"}[result]}
    members, zs, err = read_packet(zip_path)
    if err:
        checks.append({"check": "archive-safety", "outcome": "FAILED", "detail": err}); return done("UNSUPPORTED", f"refused: {err}", zip_sha256=zs)
    checks.append({"check": "archive-safety", "outcome": "VERIFIED", "detail": f"{len(members)} members within bounds; no traversal, symlink, oversized or duplicate member"})
    if MANIFEST not in members:
        if v8export.MANIFEST in members:
            return done("UNSUPPORTED", f"this is a v8 export ({v8export.MANIFEST} present, no {MANIFEST}); verify it with the v8 verifier (`yuclaw workbench verify-export`), which stays unchanged — this reader never reinterprets it", zip_sha256=zs)
        checks.append({"check": "required-members", "outcome": "FAILED", "detail": f"missing {MANIFEST}"}); return done("MISMATCH", f"incomplete packet: missing {MANIFEST}", zip_sha256=zs)
    try:
        man = json.loads(members[MANIFEST].decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return done("UNSUPPORTED", "manifest is not JSON", zip_sha256=zs)
    if not isinstance(man, dict) or man.get("format") != FORMAT:
        if isinstance(man, dict) and man.get("format") in v8export.SUPPORTED_FORMATS:
            return done("UNSUPPORTED", f"this is a v8 export ({man.get('format')}); verify it with the v8 verifier (`yuclaw workbench verify-export`), which this reader delegates to unchanged", zip_sha256=zs)
        return done("UNSUPPORTED", f"unsupported packet format {man.get('format') if isinstance(man, dict) else None!r}", zip_sha256=zs)
    missing = [m for m in REQUIRED if m not in members]
    if missing:
        checks.append({"check": "required-members", "outcome": "FAILED", "detail": f"missing {missing}"}); return done("MISMATCH", f"incomplete packet: missing {missing}", zip_sha256=zs)
    checks.append({"check": "required-members", "outcome": "VERIFIED", "detail": "all required members present"})
    first = None
    files = man.get("files") if isinstance(man.get("files"), list) else []
    for f in files:
        if not isinstance(f, dict) or f.get("path") not in members:
            checks.append({"check": "sha256+length", "path": f.get("path") if isinstance(f, dict) else None, "outcome": "FAILED", "detail": "listed in the manifest, absent from the archive"}); first = first or "manifest lists a member the archive lacks"; continue
        data = members[f["path"]]; ok = contracts.sha256_hex(data) == f.get("sha256") and len(data) == f.get("size_bytes")
        checks.append({"check": "sha256+length", "path": f["path"], "outcome": "VERIFIED" if ok else "FAILED"})
        if not ok:
            first = first or f"byte mismatch at {f['path']}"
    listed = {f.get("path") for f in files if isinstance(f, dict)}
    extra = [m for m in members if m not in listed and m not in (MANIFEST, INSTRUCTIONS)]
    if extra:
        checks.append({"check": "unlisted-members", "outcome": "FAILED", "detail": f"members not in the manifest: {extra}"}); first = first or f"unlisted member {extra[0]}"
    if digest(files) != man.get("content_digest"):
        checks.append({"check": "content-digest", "outcome": "FAILED"}); first = first or "content digest does not match the file list"
    else:
        checks.append({"check": "content-digest", "outcome": "VERIFIED"})
    if first:
        return done("MISMATCH", first, zip_sha256=zs, packet_id=man.get("packet_id"))
    try:
        view = json.loads(members[BRIEF_JSON].decode("ascii")); records = json.loads(members[RECORDS_JSON].decode("ascii")); snap = json.loads(members[SNAPSHOT_JSON].decode("ascii"))
    except (ValueError, UnicodeDecodeError):
        return done("UNSUPPORTED", "brief.json, records.json or snapshot.json is not ASCII JSON", zip_sha256=zs)
    for name, obj, raw in ((BRIEF_JSON, view, members[BRIEF_JSON]), (RECORDS_JSON, records, members[RECORDS_JSON]), (SNAPSHOT_JSON, snap, members[SNAPSHOT_JSON])):
        if canonical_json(obj) != raw:
            checks.append({"check": "canonical-form", "path": name, "outcome": "FAILED"}); return done("MISMATCH", f"{name} is not canonical JSON", zip_sha256=zs)
    checks.append({"check": "canonical-form", "outcome": "VERIFIED"})
    if records.get("schema") != "yuclaw.brief-records/1" or snap.get("schema") != contracts.EVIDENCE_SNAPSHOT:
        return done("UNSUPPORTED", "records or snapshot schema unknown", zip_sha256=zs)
    # snapshot identity
    s2 = {k: v for k, v in snap.items() if k != "snapshot_digest"}
    recomputable_snapshot = all(s.get("excerpt") is not None for c in snap["claims"].values() for s in c["sources"].values())
    if recomputable_snapshot:
        checks.append({"check": "snapshot-digest", "outcome": "VERIFIED" if digest(s2) == snap.get("snapshot_digest") == man.get("snapshot_digest") else "FAILED"})
        if checks[-1]["outcome"] == "FAILED":
            first = first or "snapshot digest does not reproduce from the packed snapshot"
    else:
        checks.append({"check": "snapshot-digest", "outcome": "NOT_RECOMPUTABLE", "detail": "an excerpt was withheld by rights; the full snapshot identity cannot be recomputed from the public view"})
    # text views, spans, calculations
    texts = {}
    for name, data in members.items():
        m = _TEXT_MEMBER.match(name)
        if m:
            texts[m.group(1)] = data
            checks.append({"check": "text-view-digest", "view": m.group(1)[:16], "outcome": "VERIFIED" if contracts.sha256_hex(data) == m.group(1) else "FAILED"})
            if checks[-1]["outcome"] == "FAILED":
                first = first or f"text view {m.group(1)[:16]}… does not hash to its name"
    excerpts = {s["source_hash"]: s.get("excerpt") for c in snap["claims"].values() for s in c["sources"].values()}
    n_spans = n_calc = 0
    for v in records.get("versions", []):
        data = texts.get(v["text_view"]["view_sha256"])
        if data is None:
            checks.append({"check": "version-text", "version": v["version_id"], "outcome": "FAILED", "detail": "text view member missing"}); first = first or f"version {v['version_id']}: text missing"; continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            checks.append({"check": "version-text", "version": v["version_id"], "outcome": "FAILED", "detail": "not UTF-8"}); first = first or f"version {v['version_id']}: text not UTF-8"; continue
        if v["text_view"].get("byte_length") != len(data):
            checks.append({"check": "version-text", "version": v["version_id"], "outcome": "FAILED", "detail": "byte length differs"}); first = first or f"version {v['version_id']}: length differs"
        for sp in v.get("spans", []):
            n_spans += 1
            rec, reasons = contracts.check_claim_span(sp, data)
            if reasons:
                checks.append({"check": "span-binding", "version": v["version_id"], "span": f"{sp.get('start')}..{sp.get('end')}", "outcome": "FAILED", "detail": "; ".join(reasons)}); first = first or f"version {v['version_id']}: span {sp.get('start')}..{sp.get('end')} binding failed"; continue
            if sp.get("role") == "direct_quotation" and sp.get("support") == "SUPPORTED":
                q = data[sp["start"]:sp["end"]].decode("utf-8")
                ex = [excerpts.get(e.get("digest")) for e in sp.get("evidence", []) if e.get("kind") == "source_excerpt"]
                if any(x is None for x in ex) and not any(x for x in ex if x and _inner(q) in x):
                    checks.append({"check": "quotation", "version": v["version_id"], "span": f"{sp['start']}..{sp['end']}", "outcome": "NOT_RECOMPUTABLE", "detail": "the quoted source excerpt was withheld by rights"}); continue
                okq = any(x and _inner(q) in x for x in ex)
                checks.append({"check": "quotation", "version": v["version_id"], "span": f"{sp['start']}..{sp['end']}", "outcome": "VERIFIED" if okq else "FAILED"})
                if not okq:
                    first = first or f"version {v['version_id']}: quotation {sp['start']}..{sp['end']} is not a substring of its source excerpt"
            c = sp.get("calculation")
            if isinstance(c, dict):
                n_calc += 1
                if c.get("kind") == "containment_pair":
                    o1, d1 = finance.recompute(c.get("original") or {}); o2, d2 = finance.recompute(c.get("revised") or {}); o, d = (o1 if o1 == o2 else "FAILED"), (d1 or d2)
                elif c.get("kind") == "pending":
                    o, d = "NOT_APPLICABLE", "PENDING_OUTCOME: no arithmetic"
                else:
                    o, d = finance.recompute(c)
                checks.append({"check": "calculation", "version": v["version_id"], "span": f"{sp['start']}..{sp['end']}", "kind": c.get("kind"), "outcome": o, "detail": d})
                if o == "FAILED":
                    first = first or f"version {v['version_id']}: calculation {c.get('kind')} does not reproduce"
        # transform parent link
        tr = v.get("transform") or {}
        if tr.get("parent_view") and tr["parent_view"] not in texts:
            checks.append({"check": "parent-link", "version": v["version_id"], "outcome": "FAILED", "detail": "parent view not in the packet"}); first = first or f"version {v['version_id']}: parent view missing"
        elif tr.get("parent_view"):
            checks.append({"check": "parent-link", "version": v["version_id"], "outcome": "VERIFIED"})
        # receipt binding
        rc = v.get("receipt") or {}
        checks.append({"check": "receipt-binding", "version": v["version_id"], "outcome": "VERIFIED" if rc.get("assembled_output_sha256") == v["text_view"]["view_sha256"] else "FAILED"})
        if checks[-1]["outcome"] == "FAILED":
            first = first or f"version {v['version_id']}: receipt is not bound to the text view"
    # signed records against the RECEIVER's roots (never the author's)
    roots = reports.trust_roots(receiver) if receiver is not None else {}
    for kind, items in (("receipt", records.get("receipts", [])), ("report", records.get("reports", [])), ("calibration", records.get("calibrations", []))):
        for it in items:
            rec = it.get("record") or {}
            if kind == "report":
                data = texts.get(rec.get("view_sha256"))
                sp = rec.get("span") or {}
                bound = data is not None and not contracts.span_problems(data, sp.get("start"), sp.get("end")) and contracts.span_digest(data, sp["start"], sp["end"]) == sp.get("span_sha256")
                checks.append({"check": "report-binding", "record": rec.get("record_id", "")[:12], "outcome": "VERIFIED" if bound else "FAILED"})
                if not bound:
                    first = first or f"report {rec.get('record_id', '')[:12]} is not bound to the packed text"
                checks.append({"check": "report-execution", "record": rec.get("record_id", "")[:12], "outcome": "REPORT_ONLY", "detail": f"execution {rec.get('execution')}, signal {rec.get('signal')}: a detector result cannot be rerun here; recorded as reported"})
            sig = reports.evaluate_signature(kind, rec, roots) if rec.get("signature_envelope") else {"signature": "NONE", "trust": "NOT_EVALUATED", "binding": "NOT_APPLICABLE"}
            if sig["signature"] == "NONE":
                checks.append({"check": "signature", "record": rec.get("record_id", "")[:12], "kind": kind, "outcome": "NOT_APPLICABLE", "detail": "unsigned record (operator assertion or connector observation)"})
            else:
                outcome = "VERIFIED" if sig["signature"] == "VALID" and sig["binding"] == "BOUND" else ("FAILED" if sig["signature"] == "INVALID" or sig["binding"] == "MISMATCH" else "NOT_RECOMPUTABLE")
                checks.append({"check": "signature", "record": rec.get("record_id", "")[:12], "kind": kind, "outcome": outcome, "signature": sig["signature"], "trust": sig["trust"], "binding": sig["binding"], "key_id": sig.get("key_id"),
                               "detail": "trust is this receiver's policy; an unknown signer is not a malformed signature" if receiver is not None else "no receiving workspace given: trust NOT_EVALUATED"})
                if outcome == "FAILED":
                    first = first or f"{kind} {rec.get('record_id', '')[:12]}: signature {sig['signature']} / binding {sig['binding']}"
    # measurements reproduce their own counts
    m = records.get("measurements") or {}
    checks.append({"check": "measurements-consistency", "outcome": "VERIFIED" if isinstance(m.get("attempts"), int) and isinstance(m.get("operations"), int) and m.get("retries") == m["attempts"] - m["operations"] else "FAILED"})
    if checks[-1]["outcome"] == "FAILED":
        first = first or "measurements: retries ≠ attempts − operations"
    checks.append({"check": "html-safety", "outcome": "VERIFIED" if b"<script" not in members[HTML_MEMBER].lower() and b"http-equiv=\"content-security-policy\"" in members[HTML_MEMBER].lower() else "FAILED", "detail": "no script element; CSP meta present"})
    if checks[-1]["outcome"] == "FAILED":
        first = first or "brief.html contains a script or lacks its CSP"
    summary = {"versions": len(records.get("versions", [])), "spans": n_spans, "calculations": n_calc, "reports": len(records.get("reports", [])), "omitted": man.get("omitted", [])}
    return done("MISMATCH" if first else "SUCCESS", first, zip_sha256=zs, packet_id=man.get("packet_id"), brief_id=man.get("brief_id"), version_id=man.get("version_id"), summary=summary, content_digest=man.get("content_digest"))


def _inner(q: str) -> str:
    inner = q
    for a, b in (("“", "”"), ("« ", " »"), ("« ", " »"), ('"', '"')):
        if a in inner and b in inner:
            inner = inner[inner.index(a) + len(a): inner.rindex(b)]
    return inner.strip()


def record_verification(ws: Workspace, sc: Sidecar, result: dict, *, op_id: str, actor: str = "host-operator(cli)") -> tuple[dict, bool]:
    return sc.append("PACKET_VERIFIED", None, {"packet_id": result.get("packet_id"), "zip_sha256": result.get("zip_sha256"), "result": result["result"], "first_discrepancy": result.get("first_discrepancy"),
                                              "outcome_counts": result.get("outcome_counts"), "imported_into_state": "nothing — verification installs no brief, claim, root or policy", "objects": []}, op_id=op_id, actor=actor)
