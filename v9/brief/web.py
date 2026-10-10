"""The v9 pages of the local workbench: /brief, /brief/<id>, /brief/verify, /brief/trust (served by v8's server, same
loopback binding, CSRF, Origin, session and capability protections; no script anywhere).

Every page is a rendering of the reducer view (`reducer.brief_view`): the sentence list, the four-area inspector for one
selected statement (`?s=N`), the five dimensions as separate words, review items, receipts and reports, and the forms
that create new records (edit, translate, link, resolve, import a record, export). Explanations follow `?lang=en|fr`;
identifiers, commands and status words stay as they are. The v8 pages around these keep their English labels.
"""
from __future__ import annotations

import json
import re
import urllib.parse

from v3.receipts.contracts import ContractError
from v8.workbench import store
from v8.workbench.modules import authz, web as modweb
from v8.workbench.modules.core import ModuleError, actor_of
from v8.workbench.modules.web import esc, field, form, select, table
from v8.workbench.store import StoreIntegrityError
from v9.brief import compose, contracts, measure, packet, reducer, reports, templates
from v9.brief.i18n import t
from v9.brief.sidecar import Sidecar

PREFIXES = ("/brief",)
_BID = r"(brf-[0-9a-f]{12})"
_PKT = re.compile(r"^/brief/exports/(bpk-[0-9a-f]{16})\.zip$")
_OP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
WRITE_CAPS = ("admin", "review", "submit")
UPLOAD_LIMIT = reports.MAX_IMPORT_BYTES + 256 * 1024


def owns(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in PREFIXES)


def _lang(q: dict) -> str:
    return "fr" if q.get("lang") == "fr" else "en"


def _sc(h) -> Sidecar:
    return Sidecar(h.server.ws)


def _writer(h) -> dict | None:
    """The principal allowed to create records here: when principals are configured, one holding admin, review or submit;
    before that, the single owner of the workspace (as for the v8 steps)."""
    p = getattr(h, "_principal", None)
    if not h.server.principals.configured():
        return None
    if p is None:
        raise ModuleError("E_SIGN_IN", "sign in first")
    if not set(p["caps"]) & set(WRITE_CAPS):
        raise ModuleError("E_FORBIDDEN", f"needs one of {WRITE_CAPS} (the practice capability cannot change briefs)")
    return p


def _admin(h) -> dict | None:
    p = getattr(h, "_principal", None)
    if not h.server.principals.configured():
        return None
    authz.require(p, "admin"); return p


def _ql(lang: str, **kw) -> str:
    kw["lang"] = lang
    return "?" + urllib.parse.urlencode({k: v for k, v in kw.items() if v is not None})


def _lang_switch(path: str, q: dict) -> str:
    keep = {k: v for k, v in q.items() if k != "lang"}
    en = path + "?" + urllib.parse.urlencode(dict(keep, lang="en")); fr = path + "?" + urllib.parse.urlencode(dict(keep, lang="fr"))
    return f'<p class="muted" aria-label="Language / Langue"><a href="{esc(en)}" hreflang="en">English</a> · <a href="{esc(fr)}" hreflang="fr">Français</a> — {esc(t("brief.legacy_note", _lang(q)))}</p>'


def _chip(word: str, cls: str) -> str:
    return f'<span class="{cls}"><code>{esc(word)}</code></span>'


def _status_cls(s: str) -> str:
    return {"SUPPORTED": "ok", "ATTRIBUTED": "notice", "UNRESOLVED": "warn", "NOT_ASSESSED": "muted", "CONTRADICTED": "bad", "INVALIDATED": "bad", "VERIFIED": "ok", "FAILED": "bad"}.get(s, "muted")


# ------------------------------------------------------------------ pages
def page_index(h, q: dict) -> str:
    lang = _lang(q); ws = h.server.ws; sc = _sc(h)
    briefs = reducer.list_briefs(ws, sc)
    rows = [[f'<a href="/brief/{esc(b["brief_id"])}{_ql(lang)}">{esc(b["brief_id"])}</a>', esc(b["title"]), esc(b["latest"]), esc(", ".join(b["languages"])), esc(", ".join(b["claim_ids"])),
             _chip("COMPLETE" if b["complete"] else "INCOMPLETE", "ok" if b["complete"] else "bad")] for b in briefs]
    claims = sorted(ws.claim_ids(ws.load()["events"]))
    opts = [(c, c) for c in claims] or [("", "— no frozen claim yet: load a fixture on the Workspace page —")]
    sections = "".join(f'<p><label><input type="checkbox" name="section_{esc(k)}" value="1" checked> {esc(k)}</label> <span class="muted">{esc(v[1 if lang == "fr" else 0])}</span></p>' for k, v in templates.TEMPLATE_HELP.items())
    create = form(h, "/brief/create", select(h, t("brief.claims", lang), "claim", opts) + sections + select(h, t("brief.language", lang), "lang", [("en", "English"), ("fr", "Français")], lang)
                  + f'<input type="hidden" name="ui_lang" value="{lang}">', t("form.create", lang))
    imp = form(h, "/brief/import", select(h, t("brief.claims", lang), "claim", opts) + field(h, t("form.text", lang), "text", rows=10, hint="UTF-8 text of the draft; it is stored as data, never executed")
               + field(h, t("form.translation_of", lang).replace("Translation provenance", "Provenance").replace("Provenance de la traduction", "Provenance"), "provenance", default="imported draft; origin stated by the operator")
               + select(h, t("brief.language", lang), "lang", [("en", "English"), ("fr", "Français")], lang) + f'<input type="hidden" name="ui_lang" value="{lang}">', t("brief.import", lang))
    return (_lang_switch("/brief", q) + modweb.err_box(h) + f'<p>{esc(t("brief.list.empty", lang)) if not briefs else ""}</p>' + table(["Brief", "Title", "Latest", "Languages", "Claims", "Status"], rows)
            + f'<h2>{esc(t("brief.new", lang))}</h2><div class="row"><div class="card"><h3>{esc(t("brief.template", lang))}</h3>{create}</div><div class="card"><h3>{esc(t("brief.import", lang))}</h3>{imp}</div></div>'
            + f'<p><a href="/brief/verify{_ql(lang)}">{esc(t("brief.verify", lang))}</a> · <a href="/brief/trust{_ql(lang)}">Trust roots</a> · <code>yuclaw workbench brief --help</code></p>'
            + f'<p class="muted">{esc(t("brief.not_advice", lang))} {esc(t("dim.note", lang))}</p>')


def _dims(s: dict, lang: str) -> str:
    bi = s["byte_integrity"]["status"]; ss = s["substantive_support"]["status"]
    sig = s["issuer_trust"]["receipts"] + s["issuer_trust"]["reports"]
    trust = ", ".join(f"{r['signature']['signature']}/{r['signature']['trust']}" for r in sig) or t("label.signature.none", lang)
    return (f'<span class="dims">{_chip(bi, _status_cls(bi))} {_chip(ss, _status_cls(ss))} <span class="muted">{esc(t("dim.issuer_trust", lang))}: {esc(trust)}</span> '
            f'<span class="muted">{esc(s["time_scope"]["label"])}</span> <span class="muted">{esc(s["detector"]["label"])}</span></span>')


def _inspector(view: dict, s: dict, lang: str) -> str:
    ss = s["substantive_support"]
    ev = "".join(f"<li><code>{esc(e['kind'])}</code> {esc(e['ref'])} <code>{esc((e.get('digest') or '')[:16])}</code></li>" for e in ss["evidence"]) or f"<li class='muted'>{esc(t('word.none', lang))}</li>"
    calc = ""
    if ss["calculation"]:
        c = ss["calculation"]
        rows = [[esc(k), f"<code>{esc(json.dumps(c[k], ensure_ascii=False))}</code>"] for k in ("kind", "formula", "inputs", "midpoint_original", "midpoint_revised", "absolute_change", "relative_change", "result", "contains", "scope") if k in c]
        calc = f"<h4>{esc('Calcul enregistré' if lang == 'fr' else 'Registered calculation')}</h4>" + table(["field", "value"], rows) + f"<p>{esc('Recalculé maintenant' if lang == 'fr' else 'Recomputed now')}: {_chip(ss['calculation_check']['outcome'], _status_cls(ss['calculation_check']['outcome']))} {esc(ss['calculation_check'].get('detail') or '')}</p>"
    prot = ", ".join(f"<code>{esc(p['slot'])}</code>={esc(p['value'])}" for p in ss["protected"]) or esc(t("word.none", lang))
    ro = s["recorded_origin"]; unk = "; ".join(f"{k}: {v}" for k, v in (ro.get("unknown") or {}).items()) or esc(t("word.none", lang))
    items = [it for it in view["review_items"] if it["item_id"] in s["time_scope"]["review_items"]]
    changes = "".join(f"<li><code>{esc(it['reason'])}</code> {esc(it['dependency'] or '')}: {esc(it['detail'])}" + (f" — <b>{esc(it['resolved']['disposition'])}</b>: {esc(it['resolved']['note'])}" if it["resolved"] else "") + "</li>" for it in items) or f"<li class='muted'>{esc(t('label.snapshot_current', lang))}</li>"
    sigs = s["issuer_trust"]["receipts"] + s["issuer_trust"]["reports"]
    sig_rows = [[esc(r["record_id"][:16]), _chip(r["signature"]["signature"], _status_cls("VERIFIED" if r["signature"]["signature"] == "VALID" else "FAILED")), esc(r["signature"]["trust"]), esc(r["signature"].get("binding")), esc(r["signature"].get("key_id") or "")] for r in sigs]
    det_rows = [[esc(r["detector"]), esc(r["execution"]), esc(r.get("signal") or "—"), esc(r["calibration"]["applicability"]), esc(r["origin"]), esc(r.get("provider_reported") or "")] for r in s["detector"]["reports"]]
    return f"""<section id="inspector" class="card" aria-labelledby="insp-h"><h2 id="insp-h">{esc(t('brief.inspect', lang))} — {esc(t('word.statement', lang))} {s['n']} <span class="muted">[{s['start']}:{s['end']}] {esc(s['role_label'])}</span></h2>
<blockquote>{esc(s['text'])}</blockquote><p class="muted">{esc(t('role.note', lang))}</p>
<h3>1. {esc(t('area.sources', lang))}</h3><p>{_chip(ss['status'], _status_cls(ss['status']))} {esc(ss['label'])}<br><span class="muted">{esc('méthode' if lang == 'fr' else 'method')}: <code>{esc(ss['method'])}</code> · {esc('évaluateur' if lang == 'fr' else 'assessor')}: <code>{esc(ss['assessor'])}</code></span><br>{esc(ss['limits'])}</p>
<p>{esc('Engagement' if lang == 'fr' else 'Claim')}: <code>{esc(json.dumps(ss['claim']))}</code></p><ul>{ev}</ul>{calc}<p>{esc('Champs protégés' if lang == 'fr' else 'Protected slots')}: {prot}</p>
<h3>2. {esc(t('area.origin', lang))}</h3><p>{esc(ro['transform'])} · {esc(ro['implementation'])} · {esc('déterministe' if lang == 'fr' else 'deterministic')}: <code>{esc(ro['deterministic'])}</code> · {esc('modèle' if lang == 'fr' else 'template')}: <code>{esc(ro['template'])}</code></p>
<p>{esc(t('label.generation_record', lang))}: {', '.join(f'<code>{esc(r[:16])}</code>' for r in ro['receipts'])}<br><span class="muted">{esc('inconnues explicites' if lang == 'fr' else 'explicit unknowns')}: {unk}</span></p>
<h3>3. {esc(t('area.changes', lang))}</h3><p>{esc(s['time_scope']['label'])} · snapshot <code>{esc(s['time_scope']['snapshot_digest'][:16])}…</code> · v8 tip <code>{esc(s['time_scope']['v8_tip_at_snapshot'][:12])}…</code></p><ul>{changes}</ul>
<h3>4. {esc(t('area.checks', lang))}</h3><p>{esc(t('dim.byte_integrity', lang))}: {_chip(s['byte_integrity']['status'], _status_cls(s['byte_integrity']['status']))} <code>{esc(s['byte_integrity'].get('recorded', '')[:16])}</code></p>
<p>{esc(t('dim.issuer_trust', lang))}:</p>{table(['record', 'signature', 'trust', 'binding', 'key'], sig_rows) if sig_rows else f"<p class='muted'>{esc(t('label.signature.none', lang))} — {esc(s['issuer_trust']['note'])}</p>"}
<p>{esc(t('dim.detector', lang))}: {esc(s['detector']['label'])}</p>{table(['detector', 'execution', 'signal', 'calibration', 'origin', 'note'], det_rows) if det_rows else ''}
<p class="muted">{esc(view['dimension_note'])}</p></section>"""


def page_brief(h, bid: str, q: dict) -> str:
    lang = _lang(q); ws = h.server.ws; sc = _sc(h)
    view = reducer.brief_view(ws, sc, bid, q.get("version") or None, lang)
    base = f"/brief/{bid}"; vq = {"version": view["version_id"]}
    head = (_lang_switch(base, q) + modweb.err_box(h)
            + f'<p>{esc(view["brief_id"])} · {esc(t("word.version", lang))} <b>{esc(view["version_id"])}</b> ({esc(view["language"])}) · {esc(t("word.parent", lang))} {esc(view["parent_version"] or "—")} · {esc(t("word.created", lang))} {esc(view["recorded_at"])} · snapshot <code>{esc(view["snapshot_digest"][:16])}…</code></p>'
            + f'<p><b>{esc(view.get("evidence_label") or view.get("status_label", view["status"]))}</b> · {esc(t("brief.claims", lang))}: {", ".join(f"<a href=/claim/{urllib.parse.quote(c, safe='')}><code>{esc(c)}</code></a>" for c in view["claim_ids"])}</p>'
            + f'<p class="muted"><i>{esc(view["mission"])} {esc(view["vision"])}</i></p>')
    if view["status"] != "COMPLETE":
        return head + f'<div class="err"><p>{esc(view["status_label"])}: {esc(view["missing_objects"])}</p></div>'
    vers = table([t("word.version", lang), "lang", "transform", t("word.parent", lang), t("word.created", lang), "status"],
                 [[f'<a href="{base}{_ql(lang, version=v["version_id"])}">{esc(v["version_id"])}</a>', esc(v["language"]), esc(v["transform"]), esc(v["parent_version"] or "—"), esc(v["recorded_at"]), _chip("COMPLETE" if v["complete"] else "INCOMPLETE", "ok" if v["complete"] else "bad")] for v in view["versions"]])
    sel = q.get("s")
    stmts = "".join(f'<li id="st{s["n"]}"{" class=sel" if sel == str(s["n"]) else ""}><a href="{base}{_ql(lang, version=view["version_id"], s=s["n"])}#inspector" aria-label="{esc(t("brief.inspect", lang))} {s["n"]}">[{s["n"]}]</a> {esc(s["text"])}<br>{_dims(s, lang)}</li>' for s in view["statements"])
    insp = ""
    if sel and sel.isdigit():
        try:
            insp = _inspector(view, reducer.statement_text(view, int(sel)), lang)
        except KeyError:
            insp = f'<div class="err"><p>statement {esc(sel)} does not exist</p></div>'
    cov = view["coverage"]
    body = head + f'<h2>{esc("Texte" if lang == "fr" else "Text")}</h2><pre class="excerpt">{esc(view["text"])}</pre>' \
        + f'<h2>{esc(t("word.statement", lang))}s</h2><p>{esc(cov["sentence"])} <span class="muted">{esc(cov["extraction_scope"] or "")}</span></p><p class="muted">{esc(t("dim.note", lang))}</p><ol class="stmts">{stmts}</ol>' + insp
    # review items
    rev_rows = []
    for it in view["review_items"]:
        act = ""
        if not it["resolved"]:
            act = form(h, f"{base}/resolve", f'<input type="hidden" name="item_id" value="{esc(it["item_id"])}"><input type="hidden" name="ui_lang" value="{lang}">' + select(h, "disposition", "disposition", ["REVIEWED_NO_CHANGE", "REVISED", "WITHDRAWN_STATEMENT", "DISPUTED"]) + field(h, t("form.reason", lang), "note"), t("form.resolve", lang))
        rev_rows.append([esc(it["item_id"][:12]), esc(it["reason"]), esc(it["dependency"] or view["version_id"]), esc(it["detail"]), (f"<b>{esc(it['resolved']['disposition'])}</b> {esc(it['resolved']['note'])}" if it["resolved"] else act)])
    body += f'<h2>{esc(t("brief.review", lang))} ({view["open_review_items"]} {esc("ouvert(s)" if lang == "fr" else "open")})</h2>' + table(["item", "reason", "dependency", "detail", "disposition"], rev_rows)
    # receipts and reports
    rc_rows = [[esc(r["record_id"][:16]), esc(r["origin"]), esc(r["recording_method"]), esc(r.get("template") or r.get("provider") or ""), esc(f"{r['signature']['signature']}/{r['signature']['trust']}"), esc("; ".join(f"{k}: {v}" for k, v in (r.get("unknown") or {}).items()))] for r in view["receipts"]]
    rp_rows = [[esc(r["record_id"][:16]), esc(r["detector"]), esc(r["execution"]), esc(r.get("signal") or "—"), f"{esc(r['calibration_claimed'])} → <b>{esc(r['calibration']['applicability'])}</b> <span class='muted'>{esc(r['calibration']['reason'])}</span>", esc(f"{r['span']['start']}..{r['span']['end']}"), esc(f"{r['signature']['signature']}/{r['signature']['trust']}/{r['signature']['binding']}"), esc(r["origin"])] for r in view["reports"]]
    body += f'<h2>{esc(t("brief.reports", lang))}</h2><h3>{esc(t("label.generation_record", lang))}</h3>' + table(["record", "origin", "method", "template/provider", "signature/trust", "unknown"], rc_rows) \
        + f'<h3>{esc(t("dim.detector", lang))}</h3>' + table(["record", "detector", "execution", "signal", "calibration", "span", "signature/trust/binding", "origin"], rp_rows) \
        + "<ul>" + "".join(f"<li class='muted'>{esc(x)}</li>" for x in view["never_claims"]) + "</ul>"
    # forms
    hidden = f'<input type="hidden" name="version" value="{esc(view["version_id"])}"><input type="hidden" name="ui_lang" value="{lang}">'
    edit = form(h, f"{base}/edit", hidden + field(h, t("form.text", lang), "text", default=view["text"], rows=14) + field(h, t("form.translation_of", lang).replace("Translation provenance", "Provenance").replace("Provenance de la traduction", "Provenance"), "provenance", default="edited by the operator"), t("form.save_version", lang))
    other = "fr" if view["language"] == "en" else "en"
    deterministic = bool(view["statements"]) and bool(view["statements"][0]["recorded_origin"]["deterministic"])
    tr_det = form(h, f"{base}/translate", hidden + f'<input type="hidden" name="to" value="{other}"><input type="hidden" name="mode" value="template">', f"{t('brief.translate', lang)} → {other} ({'modèle déterministe' if lang == 'fr' else 'deterministic template'})") if deterministic else ""
    tr_txt = form(h, f"{base}/translate", hidden + f'<input type="hidden" name="to" value="{other}"><input type="hidden" name="mode" value="text">' + field(h, f"{t('form.text', lang)} ({other})", "text", rows=10) + field(h, t("form.translation_of", lang), "provenance", default="translation entered by the operator; not certified"), f"{t('brief.translate', lang)} → {other} ({'texte saisi' if lang == 'fr' else 'entered text'})")
    roles = [(r, t(f"role.{r}", lang)) for r in contracts.ROLES]
    claims = [("", "—")] + [(c, c) for c in view["claim_ids"]]
    link = form(h, f"{base}/link", hidden + field(h, t("form.start_byte", lang), "start", kind="number") + field(h, t("form.end_byte", lang), "end", kind="number") + select(h, t("form.role", lang), "role", roles)
                + select(h, t("form.claim_ref", lang), "claim", claims) + field(h, "version (V1, R1, C1)", "claim_version", default="") + field(h, t("form.reason", lang), "note"), t("form.link", lang))
    rec = form(h, f"{base}/record", hidden + select(h, t("form.kind", lang), "kind", [("report", "DetectionReport/1"), ("receipt", "GenerationReceipt/1"), ("calibration", "CalibrationRecord/1")])
               + f'<p><label>{esc(t("form.file", lang))}</label> <input type="file" name="record" accept="application/json"></p><p><label>raw response (optional)</label> <input type="file" name="raw"></p>', t("form.submit", lang), multipart=True)
    exp = form(h, f"{base}/export", hidden, t("form.build_packet", lang))
    pk_rows = [[f'<a href="/brief/exports/{esc(r["payload"]["packet_id"])}.zip">{esc(r["payload"]["packet_id"])}.zip</a>', esc(r["payload"]["version_id"]), esc(r["payload"]["language"]), esc(r["payload"]["zip_sha256"][:16]), esc(r["time"]["recorded_at"])] for r in sc.records("PACKET_BUILT", bid)]
    body += (f'<h2>{esc(t("brief.versions", lang))}</h2>{vers}'
             f'<div class="row"><div class="card"><h2>{esc(t("brief.edit", lang))}</h2>{edit}</div><div class="card"><h2>{esc(t("brief.translate", lang))}</h2>{tr_det}{tr_txt}</div></div>'
             f'<div class="row"><div class="card"><h2>{esc(t("form.link", lang))}</h2><p class="muted">{esc("Décalages en octets UTF-8, demi-ouverts ; les décalages de caractères d’un éditeur doivent être convertis." if lang == "fr" else "Half-open UTF-8 byte offsets; an editor’s character offsets must be converted.")}</p>{link}</div>'
             f'<div class="card"><h2>{esc(t("brief.reports", lang))} — import</h2>{rec}</div></div>'
             f'<div class="card"><h2>{esc(t("brief.export", lang))}</h2>{exp}{table(["packet", "version", "lang", "sha256", "built"], pk_rows)}<p class="muted">{esc("Vérifiez le paquet dans un espace vierge : " if lang == "fr" else "Verify the packet in a fresh workspace: ")}<code>yuclaw workbench brief verify &lt;zip&gt;</code> · <a href="/brief/verify{_ql(lang)}">{esc(t("brief.verify", lang))}</a></p></div>')
    return body


def page_verify(h, q: dict, result: dict | None) -> str:
    lang = _lang(q)
    body = _lang_switch("/brief/verify", q) + modweb.err_box(h) + f'<p>{esc("Téléversez un paquet de note (bpk-….zip) construit ailleurs. Rien n’est importé dans cet espace." if lang == "fr" else "Upload a brief packet (bpk-….zip) built elsewhere. Nothing is imported into this workspace.")}</p>'
    if result is not None:
        cls = "ok" if result["result"] == "SUCCESS" else "bad"
        rows = [[esc(c.get("check")), esc(c.get("path") or c.get("version") or c.get("record") or c.get("span") or c.get("view") or ""), _chip(c["outcome"], _status_cls(c["outcome"] if c["outcome"] in ("VERIFIED", "FAILED") else "x")), esc(c.get("detail") or c.get("kind") or "")] for c in result["checks"]]
        body += f'<h2>{esc(t("word.result", lang))}: <span class="{cls}">{esc(result["result"])}</span></h2><p>{esc(result.get("first_discrepancy") or result["meaning"])}</p><p>zip sha256 <code>{esc(result.get("zip_sha256"))}</code> · outcomes <code>{esc(json.dumps(result.get("outcome_counts")))}</code> · {esc(json.dumps(result.get("summary")))}</p>' + table(["check", "item", "outcome", "detail"], rows)
    body += form(h, "/brief/verify", f'<input type="hidden" name="ui_lang" value="{lang}"><p><label>{esc(t("form.file", lang))}</label> <input type="file" name="packet" accept=".zip"></p>', t("brief.verify", lang), multipart=True)
    return body


def page_trust(h, q: dict) -> str:
    lang = _lang(q); sc = _sc(h); roots = reports.trust_roots(sc)
    rows = [[esc(k), esc(r["label"]), esc(r.get("issuer") or ""), _chip("REVOKED" if r["revoked"] else "ACTIVE", "bad" if r["revoked"] else "ok"), esc(r["enrolled_at"]),
             "" if r["revoked"] else form(h, "/brief/trust/revoke", f'<input type="hidden" name="key_id" value="{esc(k)}"><input type="hidden" name="ui_lang" value="{lang}">' + field(h, t("form.reason", lang), "reason"), "Revoke")] for k, r in roots.items()]
    enroll = form(h, "/brief/trust/enroll", f'<input type="hidden" name="ui_lang" value="{lang}">' + field(h, "public key (base64, raw Ed25519)", "public_key") + field(h, "label", "label") + field(h, "issuer", "issuer"), "Enroll")
    return (_lang_switch("/brief/trust", q) + modweb.err_box(h) + f'<p>{esc("Les racines de confiance de CET espace pour les enregistrements de provenance signés. Un paquet n’inscrit jamais son signataire." if lang == "fr" else "THIS workspace’s trust roots for signed provenance records. A packet never enrolls its own signer.")}</p>'
            + table(["key id", "label", "issuer", "status", "enrolled", ""], rows) + f"<h2>Enroll</h2>{modweb.need(h, 'admin') if h.server.principals.configured() and not modweb.can(h, 'admin') else enroll}")


# ------------------------------------------------------------------ GET / POST
def get(h, path: str, q: dict, extra) -> None:
    lang = _lang(q)
    send = lambda title, body, status=200: h._send(status, h.page(title, f'<p class="muted">{modweb.who(h)}</p>' + body), extra=extra)
    try:
        m = _PKT.match(path)
        if m:
            p = h.server.ws.exports / f"{m.group(1)}.zip"
            if not p.is_file():
                return h._text(404, "not found")
            data = p.read_bytes()
            return h._send(200, data, "application/zip", extra={"Content-Disposition": f'attachment; filename="{m.group(1)}.zip"', **(extra or {})})
        if path == "/brief":
            return send(t("brief.title", lang), page_index(h, q))
        if path == "/brief/verify":
            return send(t("brief.verify", lang), page_verify(h, q, None))
        if path == "/brief/trust":
            return send("Trust roots — v9 briefs", page_trust(h, q))
        m = re.match(rf"^/brief/{_BID}$", path)
        if m:
            return send(t("brief.title", lang) + f" — {m.group(1)}", page_brief(h, m.group(1), q))
        m = re.match(rf"^/brief/{_BID}/html$", path)
        if m:
            view = reducer.brief_view(h.server.ws, _sc(h), m.group(1), q.get("version") or None, lang)
            if view["status"] != "COMPLETE":
                return h._text(409, "incomplete version")
            data = packet.render_html(view, lang).encode("utf-8")
            return h._send(200, data, "text/html; charset=utf-8", extra={"Content-Disposition": f'attachment; filename="{m.group(1)}-{view["version_id"]}.html"', **(extra or {})})
        return h._text(404, "not found")
    except ModuleError as exc:
        h._mod_err = (exc.code, exc.detail)
        return send("Refused", f'<div class="err"><p><code>{esc(exc.code)}</code> {esc(exc.detail)}</p></div>', 403 if exc.code in ("E_FORBIDDEN", "E_SIGN_IN") else 422)
    except StoreIntegrityError as exc:
        return send("Refused", f'<div class="err"><p><code>{esc(exc.code)}</code> {esc(exc)}</p></div>', 409 if exc.code == "E_OP_CONFLICT" else 422)
    except ContractError as exc:
        return send("Refused", f'<div class="err"><p>{esc(exc)}</p></div>', 422)


def _rerender(h, path: str, q: dict, status: int):
    orig = h._send
    def send(st, body, ctype="text/html; charset=utf-8", extra=None):
        return orig(status if st == 200 else st, body, ctype, extra)
    h._send = send
    try:
        return get(h, path, q, None)
    finally:
        h._send = orig


def post(h, path: str) -> None:
    ws = h.server.ws; sc = _sc(h)
    if path == "/brief/verify" or re.match(rf"^/brief/{_BID}/record$", path):
        return _post_upload(h, path)
    f = h._form()
    if f is None:
        return
    if not h._csrf_ok(f):
        return h._text(403, "refused: CSRF token invalid; nothing was written")
    op = f.get("op_id", "")
    if not _OP.match(op):
        return h._text(400, "refused: op_id malformed")
    lang = "fr" if f.get("ui_lang") == "fr" else "en"; q = {"lang": lang}
    back = "/brief"
    try:
        if path == "/brief/create":
            p = _writer(h); sections = [k for k in templates.TEMPLATES if f.get(f"section_{k}")]
            with sc.operation("create_brief", op, actor=actor_of(p), surface="ui") as o:
                rec, dup = compose.create_from_template(ws, sc, claim_id=f.get("claim", ""), sections=sections, lang=f.get("lang", "en"), op_id=op, actor=actor_of(p)); o.committed(rec, dup)
            return h._redirect(f"/brief/{rec['brief_id']}{_ql(lang)}")
        if path == "/brief/import":
            p = _writer(h)
            with sc.operation("import_draft", op, actor=actor_of(p), surface="ui") as o:
                rec, dup = compose.import_draft(ws, sc, text=f.get("text", "").encode("utf-8"), lang=f.get("lang", "en"), claim_ids=[f.get("claim", "")], provenance=f.get("provenance", ""), actor=actor_of(p), op_id=op); o.committed(rec, dup)
            return h._redirect(f"/brief/{rec['brief_id']}{_ql(lang)}")
        if path == "/brief/trust/enroll":
            p = _admin(h); back = "/brief/trust"
            with sc.operation("trust_enroll", op, actor=actor_of(p), surface="ui") as o:
                rec, dup = reports.enroll_root(ws, sc, public_key=f.get("public_key", ""), label=f.get("label", ""), issuer=f.get("issuer", ""), actor=actor_of(p), op_id=op); o.committed(rec, dup)
            return h._redirect(f"/brief/trust{_ql(lang)}")
        if path == "/brief/trust/revoke":
            p = _admin(h); back = "/brief/trust"
            with sc.operation("trust_revoke", op, actor=actor_of(p), surface="ui") as o:
                rec, dup = reports.revoke_root(ws, sc, key_id=f.get("key_id", ""), reason=f.get("reason", ""), actor=actor_of(p), op_id=op); o.committed(rec, dup)
            return h._redirect(f"/brief/trust{_ql(lang)}")
        m = re.match(rf"^/brief/{_BID}/(edit|translate|link|resolve|export)$", path)
        if not m:
            return h._text(404, "not found")
        bid, action = m.group(1), m.group(2); back = f"/brief/{bid}"; q["version"] = f.get("version") or None
        p = _writer(h); actor = actor_of(p); ver = f.get("version") or None
        if action == "edit":
            with sc.operation("edit_brief", op, actor=actor, surface="ui") as o:
                rec, dup = compose.revise(ws, sc, brief_id=bid, parent_version_id=ver, text=f.get("text", "").encode("utf-8"), kind="edit", lang_to=None, actor=actor, provenance=f.get("provenance", "edited by the operator"), op_id=op); o.committed(rec, dup)
        elif action == "translate":
            with sc.operation("translate_brief", op, actor=actor, surface="ui") as o:
                if f.get("mode") == "template":
                    rec, dup = compose.retranslate_template(ws, sc, brief_id=bid, parent_version_id=ver, lang_to=f.get("to", "fr"), actor=actor, op_id=op)
                else:
                    rec, dup = compose.revise(ws, sc, brief_id=bid, parent_version_id=ver, text=f.get("text", "").encode("utf-8"), kind="translate", lang_to=f.get("to", "fr"), actor=actor, provenance=f.get("provenance", ""), op_id=op)
                o.committed(rec, dup)
        elif action == "link":
            try:
                start, end = int(f.get("start", "")), int(f.get("end", ""))
            except ValueError:
                raise ContractError("start and end must be integer UTF-8 byte offsets") from None
            with sc.operation("link_span", op, actor=actor, surface="ui") as o:
                rec, dup = compose.link_span(ws, sc, brief_id=bid, version_id=ver, start=start, end=end, role=f.get("role", ""), claim_id=f.get("claim") or None, version_ref=f.get("claim_version") or None, actor=actor, note=f.get("note", ""), op_id=op); o.committed(rec, dup)
            return h._redirect(f"/brief/{bid}{_ql(lang, version=ver)}")
        elif action == "resolve":
            with sc.operation("resolve_review", op, actor=actor, surface="ui") as o:
                rec, dup = compose.resolve_review(ws, sc, brief_id=bid, item_id=f.get("item_id", ""), disposition=f.get("disposition", ""), note=f.get("note", ""), actor=actor, op_id=op); o.committed(rec, dup)
            return h._redirect(f"/brief/{bid}{_ql(lang, version=ver)}")
        elif action == "export":
            with sc.operation("export_packet", op, actor=actor, surface="ui") as o:
                r = packet.build_packet(ws, sc, bid, ver, op_id=op, actor=actor, candidate_commit=h.server.candidate_commit); o.committed(r["record"], r["duplicate"], brief_id=bid)
            return h._redirect(f"/brief/{bid}{_ql(lang, version=ver)}#export")
        return h._redirect(f"/brief/{bid}{_ql(lang, version=rec['payload']['version_id'])}")
    except ModuleError as exc:
        h._mod_err = (exc.code, exc.detail); h._mod_form = f
        return _rerender(h, back, q, 403 if exc.code in ("E_FORBIDDEN", "E_SIGN_IN") else 422)
    except StoreIntegrityError as exc:
        h._mod_err = (exc.code, str(exc)); h._mod_form = f
        return _rerender(h, back, q, 409 if exc.code == "E_OP_CONFLICT" else 422)
    except ContractError as exc:
        h._mod_err = ("E_CONTRACT", str(exc)); h._mod_form = f
        return _rerender(h, back, q, 422)


def _post_upload(h, path: str) -> None:
    from v8.workbench.server import Multipart
    ws = h.server.ws; sc = _sc(h)
    ct = h.headers.get("Content-Type", "")
    body = h._read_body(UPLOAD_LIMIT)
    if body is None or not ct.startswith("multipart/form-data"):
        h.close_connection = True
        return h._send(413, h.page("Refused", f'<div class="err"><p>The upload was missing or larger than {UPLOAD_LIMIT // 1024} KB.</p></div>'), extra={"Connection": "close"})
    try:
        mp = Multipart(ct, body)
    except ContractError as exc:
        return h._text(400, f"refused: {exc}")
    if not h._csrf_ok(mp.fields):
        return h._text(403, "refused: CSRF token invalid; nothing was written")
    op = mp.fields.get("op_id", "")
    if not _OP.match(op):
        return h._text(400, "refused: op_id malformed")
    lang = "fr" if mp.fields.get("ui_lang") == "fr" else "en"; q = {"lang": lang}
    try:
        if path == "/brief/verify":
            if "packet" not in mp.files or not mp.files["packet"][1]:
                raise ContractError("choose the packet zip as downloaded")
            tmp = ws.imports / f"upload-{store.secrets.token_hex(8)}.zip"
            tmp.write_bytes(mp.files["packet"][1])
            try:
                res = packet.verify_packet(tmp, receiver=sc)
            finally:
                tmp.unlink(missing_ok=True)
            with sc.operation("verify_packet", op, actor=actor_of(getattr(h, "_principal", None)), surface="ui") as o:
                rec, dup = packet.record_verification(ws, sc, res, op_id=op, actor=actor_of(getattr(h, "_principal", None))); o.committed(rec, dup)
            return h._send(200 if res["result"] == "SUCCESS" else 422, h.page(t("brief.verify", lang), f'<p class="muted">{modweb.who(h)}</p>' + page_verify(h, q, res)))
        m = re.match(rf"^/brief/{_BID}/record$", path); bid = m.group(1); q["version"] = mp.fields.get("version") or None
        p = _writer(h)
        if "record" not in mp.files or not mp.files["record"][1]:
            raise ContractError("choose the JSON record file")
        raw = mp.files.get("raw", (None, b""))[1] or None
        with sc.operation(f"import_{mp.fields.get('kind', 'report')}", op, actor=actor_of(p), surface="ui") as o:
            rec, dup = reports.import_record(ws, sc, kind=mp.fields.get("kind", "report"), data=mp.files["record"][1], actor=actor_of(p), op_id=op, raw_response=raw, origin_label=mp.files["record"][0] or ""); o.committed(rec, dup)
        return h._redirect(f"/brief/{bid}{_ql(lang, version=mp.fields.get('version') or None)}")
    except ModuleError as exc:
        h._mod_err = (exc.code, exc.detail); return _rerender(h, path.rsplit("/", 1)[0] if path != "/brief/verify" else path, q, 403 if exc.code in ("E_FORBIDDEN", "E_SIGN_IN") else 422)
    except StoreIntegrityError as exc:
        h._mod_err = (exc.code, str(exc)); return _rerender(h, path.rsplit("/", 1)[0] if path != "/brief/verify" else path, q, 409 if exc.code == "E_OP_CONFLICT" else 422)
    except ContractError as exc:
        h._mod_err = ("E_CONTRACT", str(exc)); return _rerender(h, path.rsplit("/", 1)[0] if path != "/brief/verify" else path, q, 422)
