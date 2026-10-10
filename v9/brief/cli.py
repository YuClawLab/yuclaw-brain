"""`yuclaw workbench brief …` (also `python3 -m v9.brief …`, the same function): the v9 brief command family.

create · import · list · show · edit · translate · link · review · import-record · trust · export · verify · measure ·
status · recover · orphans · example · schema. Exit codes follow the workbench: 0 = success · 1 = operation ran, negative
result (verify MISMATCH, open review items with --strict) · 2 = usage/validation error · 3 = environment unsupported.
Every write is one measured operation with an op_id (a retry with the same --op-id and the same content is idempotent).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from v3.receipts.contracts import ContractError
from v8.workbench import store
from v8.workbench.store import StoreIntegrityError
from v9 import V9_VERSION
from v9.brief import NOT_ADVICE, compose, contracts, measure, packet, reducer, reports, templates
from v9.brief.sidecar import Sidecar

ACTOR = "host-operator(cli)"
OVERVIEW = ("A brief is text whose statements are bound to exact source passages, specific v8 claim versions and registered calculations. "
            "Start: `example --workspace DIR` loads the fictional fixture and composes the acceptance brief; `show` inspects it sentence by sentence; "
            "`export` writes a portable packet; `verify` checks a packet in a fresh workspace. Nothing here needs an API key, a model download or a hosted service.")


def _ws(path, create=True):
    return store.Workspace(path, create=create)


def _open(path, create=True):
    ws = _ws(path, create=create); return ws, Sidecar(ws, create=create)


def _out(obj, as_json: bool, text: str | None = None):
    if as_json or text is None:
        print(json.dumps(obj, indent=1, ensure_ascii=False, default=str))
    else:
        print(text)


def _read(path: str) -> bytes:
    p = Path(path)
    data = p.read_bytes()
    if len(data) > contracts.TEXT_MAX * 4:
        raise ContractError(f"{path}: file too large")
    return data


def _show_text(view: dict, statement: int | None) -> str:
    L = [f"{view['brief_id']} {view['version_id']} ({view['language']}) — {view['title']}", f"status {view['status']} · {view.get('evidence_label')} · snapshot {view['snapshot_digest'][:16]}… at v8 tip {view['v8_tip_at_snapshot'][:12]}…"]
    if view["status"] != "COMPLETE":
        L.append(f"INCOMPLETE: missing objects {view['missing_objects']}"); return "\n".join(L)
    if statement is None:
        L.append(view["coverage"]["sentence"]); L.append("")
        for s in view["statements"]:
            L.append(f"[{s['n']:>2}] {s['role']:28} {s['substantive_support']['status']:12} bytes {s['byte_integrity']['status']:8} {s['time_scope']['label']} · {s['detector']['label']}")
            L.append(f"     {s['text']}")
        L.append(""); L.append(f"open review items: {view['open_review_items']} · receipts: {len(view['receipts'])} · reports: {len(view['reports'])} · versions: {[v['version_id'] for v in view['versions']]}")
        L.append(view["dimension_note"])
        return "\n".join(L)
    s = reducer.statement_text(view, statement)
    ss = s["substantive_support"]
    L += ["", f"Statement {s['n']} [{s['start']}:{s['end']}] role {s['role']}", f"  {s['text']}", "",
          "1. Sources and calculations", f"   support: {ss['status']} — {ss['label']}", f"   method: {ss['method']} · assessor: {ss['assessor']}", f"   limits: {ss['limits']}", f"   claim: {ss['claim']}"]
    for e in ss["evidence"]:
        L.append(f"   evidence: {e['kind']} {e['ref']} {(e.get('digest') or '')[:16]}")
    if ss["calculation"]:
        c = ss["calculation"]; L.append(f"   calculation: {c.get('kind')} — {c.get('formula', '')[:160]}")
        for k in ("inputs", "midpoint_original", "midpoint_revised", "absolute_change", "relative_change", "result", "contains"):
            if k in c:
                L.append(f"     {k}: {json.dumps(c[k], ensure_ascii=False)}")
        L.append(f"   recomputed now: {ss['calculation_check']}")
    if ss["protected"]:
        L.append("   protected slots: " + ", ".join(f"{p['slot']}={p['value']!r}" for p in ss["protected"]))
    ro = s["recorded_origin"]
    L += ["", "2. How the text was produced", f"   transform: {ro['transform']} · implementation: {ro['implementation']} · renderer: {ro['renderer']} · template: {ro['template']} · deterministic: {ro['deterministic']}",
          f"   receipts: {ro['receipts']}", f"   explicit unknowns: {ro['unknown']}"]
    L += ["", "3. Changes", f"   {s['time_scope']['label']} · snapshot {s['time_scope']['snapshot_digest'][:16]}… · review items: {s['time_scope']['review_items']}"]
    for it in view["review_items"]:
        if it["item_id"] in s["time_scope"]["review_items"]:
            L.append(f"   - {it['reason']} ({it['dependency']}): {it['detail']}")
    L += ["", "4. Checks", f"   byte integrity: {s['byte_integrity']}", f"   issuer trust: {s['issuer_trust']['receipts'] + s['issuer_trust']['reports'] or 'no signed record on these bytes'}",
          f"   detector: {s['detector']}", f"   {view['dimension_note']}"]
    return "\n".join(L)


def main(argv=None, prog: str = "python3 -m v9.brief") -> int:
    ap = argparse.ArgumentParser(prog=prog, description=f"YUCLAW v9 research briefs with traceable AI assistance ({V9_VERSION}; local, beside the v8 workbench). " + NOT_ADVICE, epilog=OVERVIEW)
    sub = ap.add_subparsers(dest="cmd", required=True)
    def ws_arg(p):
        p.add_argument("--workspace", required=True, help="the v8 workspace directory (the v9 sidecar lives inside it)")
    def common(p):
        p.add_argument("--actor", default=ACTOR, help="attribution label recorded with the write (not authentication)"); p.add_argument("--op-id", default=None, help="operation id (a retry with the same id and content is idempotent)"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("example", help="load the fictional fixture (idempotent) and compose the acceptance brief from all three templates"); ws_arg(p); common(p)
    p.add_argument("--lang", default="en", choices=contracts.LANGUAGES); p.add_argument("--fixture", default="001_base"); p.add_argument("--brief-id", default=None)
    p = sub.add_parser("create", help="compose a brief from deterministic templates over one frozen claim"); ws_arg(p); common(p)
    p.add_argument("--claim", required=True); p.add_argument("--sections", default=",".join(templates.TEMPLATES), help="comma list of " + ", ".join(templates.TEMPLATES)); p.add_argument("--lang", default="en", choices=contracts.LANGUAGES); p.add_argument("--brief-id", default=None)
    p = sub.add_parser("import", help="import an AI-assisted or hand-written draft as a new brief (sentences become unassessed statements to link)"); ws_arg(p); common(p)
    p.add_argument("--file", required=True); p.add_argument("--claim", action="append", required=True, help="claim id(s) the draft is about (repeatable)"); p.add_argument("--lang", default="en", choices=contracts.LANGUAGES)
    p.add_argument("--provenance", default="imported draft; origin stated by the operator", help="where the text came from, in words"); p.add_argument("--receipt", default=None, help="optional GenerationReceipt/1 JSON describing the draft's production"); p.add_argument("--brief-id", default=None)
    p = sub.add_parser("list", help="briefs of this workspace"); ws_arg(p); p.add_argument("--json", action="store_true")
    p = sub.add_parser("show", help="the brief and its statements (the reducer view); --statement N opens the inspector's four areas"); ws_arg(p)
    p.add_argument("--brief", required=True); p.add_argument("--version", default=None); p.add_argument("--lang", default="en", choices=contracts.LANGUAGES); p.add_argument("--statement", type=int, default=None); p.add_argument("--json", action="store_true"); p.add_argument("--strict", action="store_true", help="exit 1 when review items are open or any statement is not SUPPORTED/ATTRIBUTED")
    p = sub.add_parser("edit", help="save edited text as a new version (parent preserved; spans re-mapped; protected facts validated)"); ws_arg(p); common(p)
    p.add_argument("--brief", required=True); p.add_argument("--version", default=None, help="parent version (default: latest)"); p.add_argument("--file", required=True); p.add_argument("--provenance", default="edited by the operator")
    p = sub.add_parser("translate", help="add a translation: deterministic re-render for a template version, or --file with an entered translation"); ws_arg(p); common(p)
    p.add_argument("--brief", required=True); p.add_argument("--version", default=None); p.add_argument("--to", required=True, choices=contracts.LANGUAGES); p.add_argument("--file", default=None); p.add_argument("--provenance", default="translation entered by the operator; not certified")
    p = sub.add_parser("link", help="link a byte span to a claim version and role (manual span selection / link correction)"); ws_arg(p); common(p)
    p.add_argument("--brief", required=True); p.add_argument("--version", default=None); p.add_argument("--start", type=int, required=True); p.add_argument("--end", type=int, required=True); p.add_argument("--role", required=True, choices=contracts.ROLES)
    p.add_argument("--claim", default=None); p.add_argument("--claim-version", default=None); p.add_argument("--note", default="")
    p = sub.add_parser("review", help="review items of a brief (live dependency review + transform findings); --resolve records a disposition"); ws_arg(p); common(p)
    p.add_argument("--brief", required=True); p.add_argument("--version", default=None); p.add_argument("--lang", default="en", choices=contracts.LANGUAGES); p.add_argument("--resolve", default=None, help="item id"); p.add_argument("--disposition", default="REVIEWED_NO_CHANGE"); p.add_argument("--note", default="")
    p = sub.add_parser("import-record", help="import a generation receipt, detector report or calibration record (validated, bound, signature-checked)"); ws_arg(p); common(p)
    p.add_argument("--kind", required=True, choices=("receipt", "report", "calibration")); p.add_argument("--file", required=True); p.add_argument("--raw-response", default=None, help="raw provider response bytes (retained privately only when disclosure is permitted)"); p.add_argument("--label", default="")
    p = sub.add_parser("trust", help="this workspace's trust roots for signed provenance records: enroll | revoke | list"); ws_arg(p); common(p)
    p.add_argument("action", choices=("enroll", "revoke", "list")); p.add_argument("--public-key", default=None); p.add_argument("--label", default=None); p.add_argument("--issuer", default=""); p.add_argument("--key-id", default=None); p.add_argument("--reason", default="")
    p = sub.add_parser("export", help="build the readable HTML brief, JSON records and the verification packet (zip)"); ws_arg(p); common(p)
    p.add_argument("--brief", required=True); p.add_argument("--version", default=None); p.add_argument("--lang", default=None, choices=contracts.LANGUAGES)
    p = sub.add_parser("verify", help="verify a brief packet offline (exit 0 SUCCESS / 1 MISMATCH / 3 UNSUPPORTED); --workspace records the verification in that fresh workspace")
    p.add_argument("zip"); p.add_argument("--workspace", default=None); p.add_argument("--op-id", default=None); p.add_argument("--json", action="store_true")
    p = sub.add_parser("measure", help="operation measurements with their definitions"); ws_arg(p); p.add_argument("--json", action="store_true")
    p = sub.add_parser("status", help="sidecar status (integrity, briefs, v8 binding)"); ws_arg(p)
    p = sub.add_parser("recover", help="recover a torn sidecar tail (preserves the bytes; records a RECOVERY record)"); ws_arg(p)
    p = sub.add_parser("orphans", help="list prepared vault objects that no record commits; --remove deletes only those"); ws_arg(p); p.add_argument("--remove", action="store_true")
    p = sub.add_parser("schema", help="the v9 record contracts and vocabularies (developer reference)"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("selftest", help="bounded self-check from the installed package in a temporary fictional workspace: compose, inspect, edit, translate, export, verify in a fresh workspace, hostile inputs refused"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("guide", help="print the packaged v9 quick start (--lang fr for French)"); p.add_argument("--lang", default="en", choices=contracts.LANGUAGES)
    a = ap.parse_args(argv)
    try:
        return _run(a)
    except StoreIntegrityError as exc:
        print(f"[brief] refused: {exc}", file=sys.stderr); return 1 if exc.code == "E_OP_CONFLICT" else 3
    except ContractError as exc:
        print(f"[brief] refused: {exc}", file=sys.stderr); return 2
    except FileNotFoundError as exc:
        print(f"[brief] refused: file not found: {exc.filename}", file=sys.stderr); return 2


def _run(a) -> int:
    if a.cmd == "guide":
        from v9.brief import resources
        print(resources.guide(a.lang), end=""); return 0
    if a.cmd == "selftest":
        from v9.brief import selftest
        return selftest.main(as_json=a.json)
    if a.cmd == "schema":
        sch = {"schemas": list(contracts.SUPPORTED_SCHEMAS), "roles": list(contracts.ROLES), "support": list(contracts.SUPPORT), "support_methods": list(contracts.SUPPORT_METHODS),
               "execution": list(contracts.EXECUTION), "signal": list(contracts.SIGNAL), "calibration": list(contracts.CALIBRATION), "origin_kinds": list(contracts.ORIGIN_KINDS),
               "transform_kinds": list(contracts.TRANSFORM_KINDS), "check_outcomes": list(contracts.CHECK_OUTCOMES), "review_reasons": list(contracts.REVIEW_REASONS), "rights": list(contracts.RIGHTS),
               "bundle_rights": list(contracts.BUNDLE_RIGHTS), "templates": dict(zip(templates.TEMPLATES, [h[0] for h in templates.TEMPLATE_HELP.values()])), "measurement_definitions": measure.DEFINITIONS}
        _out(sch, a.json, None if a.json else json.dumps(sch, indent=1)); return 0
    if a.cmd == "verify":
        receiver = None
        if a.workspace:
            ws, sc = _open(a.workspace); receiver = sc
        r = packet.verify_packet(a.zip, receiver=receiver)
        if receiver is not None:
            with sc.operation("verify_packet", a.op_id or store.new_op_id("cli")) as op:
                rec, dup = packet.record_verification(ws, sc, r, op_id=a.op_id or store.new_op_id("cli")); op.committed(rec, dup)
        if a.json:
            print(json.dumps(r, indent=1, ensure_ascii=False))
        else:
            print(f"[brief verify] {r['result']} — {r.get('first_discrepancy') or r['meaning']}\n  zip sha256 {r.get('zip_sha256')}\n  outcomes {r.get('outcome_counts')}\n  summary {r.get('summary')}")
        return {"SUCCESS": 0, "MISMATCH": 1}.get(r["result"], 3)
    if a.cmd == "status":
        ws, sc = _open(a.workspace, create=False); print(json.dumps(sc.status(), indent=1)); return 0
    if a.cmd == "recover":
        ws, sc = _open(a.workspace, create=False); print(json.dumps(sc.recover(), indent=1, default=str)); return 0
    if a.cmd == "orphans":
        ws, sc = _open(a.workspace, create=False); o = sc.orphans()
        if a.remove and o["orphans"]:
            o["removal"] = sc.remove_orphans([x["digest"] for x in o["orphans"]])
        print(json.dumps(o, indent=1)); return 0
    if a.cmd == "measure":
        ws, sc = _open(a.workspace, create=False); m = measure.aggregate(sc)
        _out(m, a.json, None if a.json else f"operations {m['operations']} · attempts {m['attempts']} · retries {m['retries']} · outcomes {m['outcomes']} · durations {m['durations']} · missing {m['missing']}\nper task: {json.dumps(m['per_task'], indent=1)}\ndefinitions: {json.dumps(m['definitions'], indent=1)}")
        return 0
    if a.cmd == "list":
        ws, sc = _open(a.workspace); L = reducer.list_briefs(ws, sc)
        _out(L, a.json, "\n".join(f"{b['brief_id']}  {b['latest']:4} {','.join(b['languages']):6} {'complete' if b['complete'] else 'INCOMPLETE'}  {b['title']}  claims {b['claim_ids']}" for b in L) or "no brief yet"); return 0
    if a.cmd == "show":
        ws, sc = _open(a.workspace); view = reducer.brief_view(ws, sc, a.brief, a.version, a.lang)
        _out(view if a.statement is None else reducer.statement_text(view, a.statement), a.json, _show_text(view, a.statement))
        if a.strict and (view["status"] != "COMPLETE" or view["open_review_items"] or any(s["substantive_support"]["status"] not in ("SUPPORTED", "ATTRIBUTED") for s in view["statements"])):
            return 1
        return 0
    # ---- writes: one measured operation each
    ws, sc = _open(a.workspace); op_id = a.op_id or store.new_op_id("cli")
    if a.cmd == "example":
        from v8.workbench.server import load_fixture
        cid = load_fixture(ws, a.fixture)
        with sc.operation("create_brief", op_id, actor=a.actor) as op:
            rec, dup = compose.create_from_template(ws, sc, claim_id=cid, sections=list(templates.TEMPLATES), lang=a.lang, op_id=op_id, actor=a.actor, brief_id=a.brief_id); op.committed(rec, dup)
        view = reducer.brief_view(ws, sc, rec["brief_id"], None, a.lang)
        _out({"claim_id": cid, "brief_id": rec["brief_id"], "version_id": rec["payload"]["version_id"], "duplicate": dup, "view": view}, a.json, f"claim {cid}\n" + _show_text(view, None)); return 0
    if a.cmd == "create":
        with sc.operation("create_brief", op_id, actor=a.actor) as op:
            rec, dup = compose.create_from_template(ws, sc, claim_id=a.claim, sections=[s.strip() for s in a.sections.split(",") if s.strip()], lang=a.lang, op_id=op_id, actor=a.actor, brief_id=a.brief_id); op.committed(rec, dup)
        _out({"brief_id": rec["brief_id"], "version_id": rec["payload"]["version_id"], "duplicate": dup, "view_sha256": rec["payload"]["text_view"]["view_sha256"]}, a.json, f"[brief] {rec['brief_id']} {rec['payload']['version_id']} {'(duplicate retry)' if dup else 'created'} — {rec['payload']['text_view']['byte_length']} bytes, {len(rec['payload']['spans'])} statements"); return 0
    if a.cmd == "import":
        receipt = json.loads(_read(a.receipt)) if a.receipt else None
        with sc.operation("import_draft", op_id, actor=a.actor) as op:
            rec, dup = compose.import_draft(ws, sc, text=_read(a.file), lang=a.lang, claim_ids=a.claim, provenance=a.provenance, actor=a.actor, op_id=op_id, brief_id=a.brief_id, origin_receipt=receipt); op.committed(rec, dup)
        _out({"brief_id": rec["brief_id"], "version_id": rec["payload"]["version_id"], "duplicate": dup, "statements": len(rec["payload"]["spans"])}, a.json, f"[brief] {rec['brief_id']} {rec['payload']['version_id']} imported — {len(rec['payload']['spans'])} statements identified ({compose.EXTRACTOR}); link them with `link`"); return 0
    if a.cmd == "edit":
        with sc.operation("edit_brief", op_id, actor=a.actor) as op:
            rec, dup = compose.revise(ws, sc, brief_id=a.brief, parent_version_id=a.version, text=_read(a.file), kind="edit", lang_to=None, actor=a.actor, provenance=a.provenance, op_id=op_id); op.committed(rec, dup)
        tr = rec["payload"]["transform"]
        _out({"brief_id": a.brief, "version_id": rec["payload"]["version_id"], "parent": rec["payload"]["parent_version"], "mapping": tr["mapping"], "findings": tr["review_findings"], "duplicate": dup}, a.json,
             f"[brief] {a.brief} {rec['payload']['version_id']} saved (parent {rec['payload']['parent_version']} preserved) — mapped {sum(1 for m in tr['mapping'] if m['status'] == 'MAPPED')}/{len(tr['mapping'])} statements; findings: " + ("; ".join(f"{f['reason']}: {f['detail']}" for f in tr["review_findings"]) or "none")); return 0
    if a.cmd == "translate":
        with sc.operation("translate_brief", op_id, actor=a.actor) as op:
            if a.file:
                rec, dup = compose.revise(ws, sc, brief_id=a.brief, parent_version_id=a.version, text=_read(a.file), kind="translate", lang_to=a.to, actor=a.actor, provenance=a.provenance, op_id=op_id)
            else:
                rec, dup = compose.retranslate_template(ws, sc, brief_id=a.brief, parent_version_id=a.version, lang_to=a.to, actor=a.actor, op_id=op_id)
            op.committed(rec, dup)
        tr = rec["payload"]["transform"]
        _out({"brief_id": a.brief, "version_id": rec["payload"]["version_id"], "parent": rec["payload"]["parent_version"], "language": a.to, "mapping_method": tr["mapping_method"], "findings": tr["review_findings"], "duplicate": dup}, a.json,
             f"[brief] {a.brief} {rec['payload']['version_id']} ({a.to}) saved from {rec['payload']['parent_version']} — mapping {tr['mapping_method']}; findings: " + ("; ".join(f"{f['reason']}: {f['detail']}" for f in tr["review_findings"]) or "none")); return 0
    if a.cmd == "link":
        with sc.operation("link_span", op_id, actor=a.actor) as op:
            rec, dup = compose.link_span(ws, sc, brief_id=a.brief, version_id=a.version, start=a.start, end=a.end, role=a.role, claim_id=a.claim, version_ref=a.claim_version, actor=a.actor, note=a.note, op_id=op_id); op.committed(rec, dup)
        sp = rec["payload"]["span"]
        _out({"span": sp, "duplicate": dup}, a.json, f"[brief] span {sp['start']}..{sp['end']} → role {sp['role']}, support {sp['support']} ({sp['method']}); {sp['limits']}"); return 0
    if a.cmd == "review":
        if a.resolve:
            with sc.operation("resolve_review", op_id, actor=a.actor) as op:
                rec, dup = compose.resolve_review(ws, sc, brief_id=a.brief, item_id=a.resolve, disposition=a.disposition, note=a.note, actor=a.actor, op_id=op_id); op.committed(rec, dup)
        view = reducer.brief_view(ws, sc, a.brief, a.version, a.lang)
        items = view["review_items"]
        _out(items, a.json, "\n".join(f"{'resolved' if it['resolved'] else 'OPEN    '} {it['item_id']} {it['reason']} ({it['dependency'] or 'this version'}): {it['detail']}" for it in items) or "no review items"); return 0
    if a.cmd == "import-record":
        raw = _read(a.raw_response) if a.raw_response else None
        with sc.operation(f"import_{a.kind}", op_id, actor=a.actor) as op:
            rec, dup = reports.import_record(ws, sc, kind=a.kind, data=_read(a.file), actor=a.actor, op_id=op_id, raw_response=raw, origin_label=a.label); op.committed(rec, dup)
        pl = rec["payload"]; r = pl["record"]
        _out({"record_id": r["record_id"], "kind": a.kind, "signature": pl["signature"], "bound_to": pl["bound_to"], "duplicate": dup}, a.json,
             f"[brief] {a.kind} {r['record_id'][:16]} imported — origin {r['origin']}; signature {pl['signature']['signature']} / trust {pl['signature']['trust']} / binding {pl['signature']['binding']}; bound to {pl['bound_to'] or 'workspace'}"
             + (f"; execution {r['execution']} signal {r.get('signal')} calibration {r['calibration']}" if a.kind == "report" else "")); return 0
    if a.cmd == "trust":
        if a.action == "list":
            print(json.dumps(reports.trust_roots(sc), indent=1)); return 0
        with sc.operation(f"trust_{a.action}", op_id, actor=a.actor) as op:
            if a.action == "enroll":
                if not a.public_key or not a.label:
                    raise ContractError("enroll needs --public-key and --label")
                rec, dup = reports.enroll_root(ws, sc, public_key=a.public_key, label=a.label, issuer=a.issuer, actor=a.actor, op_id=op_id)
            else:
                if not a.key_id:
                    raise ContractError("revoke needs --key-id")
                rec, dup = reports.revoke_root(ws, sc, key_id=a.key_id, reason=a.reason, actor=a.actor, op_id=op_id)
            op.committed(rec, dup)
        print(json.dumps({"key_id": rec["payload"]["key_id"], "kind": rec["kind"], "duplicate": dup}, indent=1)); return 0
    if a.cmd == "export":
        with sc.operation("export_packet", op_id, actor=a.actor) as op:
            r = packet.build_packet(ws, sc, a.brief, a.version, lang=a.lang, op_id=op_id, actor=a.actor); op.committed(r["record"], r["duplicate"], brief_id=a.brief)
        _out({k: r[k] for k in ("packet_id", "zip_path", "zip_sha256", "zip_bytes", "content_digest")}, a.json, f"[brief] packet {r['packet_id']} → {r['zip_path']} ({r['zip_bytes']} bytes, sha256 {r['zip_sha256'][:16]}…); members: brief.html, brief.json, records.json, snapshot.json, appendix.md, text/, VERIFY.md"); return 0
    return 2


def main_from_workbench(argv=None) -> int:
    return main(argv, prog="yuclaw workbench brief")
