"""Browser routes of the four modules, the Modules and Setup pages, and sign-in. Plain HTML forms, no scripts.

Access rule. While no principal exists the workbench behaves as before (one owner on the loopback port) and every
protected module action is refused with the exact setup step — a module is shown, never hidden, and never silently
downgraded. Once a principal exists EVERY page needs a signed-in principal, and a principal whose only capability is
`practice` is confined to the practice routes, Modules, Help and sign-out: the claim pages, the journal and the exports are
then not alternate views of a practice answer. The actor of every write is the authenticated principal; no form field is."""
from __future__ import annotations

import html
import json
import re
import secrets
import urllib.parse

from v8.workbench.modules import authz, commons, core, evolution, modexport, practice, sandbox, shield
from v8.workbench.modules.core import ModuleError
from v8.workbench.modules.shield_worker import MAX_BUNDLE, PURPOSES

PREFIXES = ("/modules", "/setup", "/login", "/logout", "/shd", "/evo", "/com", "/prc", "/modx")
OPEN_PATHS = ("/login", "/static/style.css")
PRACTICE_ONLY_OK = ("/prc", "/modx", "/modules", "/logout", "/login", "/help", "/static/")      # /modx: a practitioner may export and verify ITS OWN sessions only
_ID = r"([A-Za-z0-9][A-Za-z0-9._:-]{0,127})"


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def owns(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in PREFIXES)


# ------------------------------------------------------------------ authentication plumbing
def principal_for(h) -> dict | None:
    for part in h.headers.get("Cookie", "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == "wb_auth" and re.match(r"^[0-9a-f]{64}$", v):
            got = h.server.sessions.lookup(v, h.server.principals)
            if got:
                h._auth_sid = v; return got[0]
    return None


def gate(h, path: str, method: str) -> bool:
    """True when a response was already sent (sign-in required, or a practice-only principal outside its routes)."""
    h._principal = principal_for(h)
    if not h.server.principals.configured() or path in OPEN_PATHS:
        return False
    if h._principal is None:
        if method == "GET":
            h._headers(303, "text/plain; charset=utf-8", 0, {"Location": "/login?next=" + urllib.parse.quote(path, safe="")})
        else:
            h._text(403, "refused: sign in first; nothing was written")
        return True
    if set(h._principal["caps"]) == {"practice"} and not any(path == p or path.startswith(p) for p in PRACTICE_ONLY_OK):
        h._send(403, h.page("Not available to a practice principal", f'<div class="err"><p>Principal <code>{esc(h._principal["principal_id"])}</code> holds only the <b>practice</b> capability and is confined to '
                            f'<a href="/prc">Independent Practice</a>, <a href="/modules">Modules</a> and <a href="/help">Help</a>. Claim pages, the journal and exports are not available to it, so they cannot show a practice comparison early.</p></div>'))
        return True
    return False


def who(h) -> str:
    p = getattr(h, "_principal", None)
    if p:
        return f'Signed in as <code>{esc(p["principal_id"])}</code> ({esc(", ".join(p["caps"]))}) · <a href="/logout">Sign out</a>'
    return 'Not signed in · <a href="/login">Sign in</a>' if h.server.principals.configured() else 'No principals yet · <a href="/setup">Setup</a>'


# ------------------------------------------------------------------ small HTML helpers
def V(h, name: str, default="") -> str:
    f = getattr(h, "_mod_form", None) or {}
    return esc(f.get(name, default))


def form(h, action: str, inner: str, submit: str, *, multipart: bool = False) -> str:
    enc = ' enctype="multipart/form-data"' if multipart else ""
    return f'<form method="post" action="{esc(action)}"{enc}>{h._csrf_field()}{inner}<p><button type="submit">{esc(submit)}</button></p></form>'


def field(h, label: str, name: str, *, kind="text", default="", hint="", rows=0) -> str:
    hint = f' <span class="muted">{esc(hint)}</span>' if hint else ""
    if rows:
        return f'<p><label>{esc(label)}</label> <textarea name="{esc(name)}" rows="{rows}" cols="90">{V(h, name, default)}</textarea>{hint}</p>'
    return f'<p><label>{esc(label)}</label> <input type="{kind}" name="{esc(name)}" value="{V(h, name, default)}" size="50">{hint}</p>'


def select(h, label: str, name: str, options, default=None) -> str:
    cur = (getattr(h, "_mod_form", None) or {}).get(name, default)
    opts = "".join(f'<option value="{esc(o)}"{" selected" if o == cur else ""}>{esc(o)}</option>' for o in options)
    return f'<p><label>{esc(label)}</label> <select name="{esc(name)}">{opts}</select></p>'


def table(head: list, rows: list) -> str:
    if not rows:
        return '<p class="muted">None yet.</p>'
    return "<table><tr>" + "".join(f"<th>{esc(c)}</th>" for c in head) + "</tr>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>"      # server.a11y wraps it in a scroll region


def err_box(h) -> str:
    m = getattr(h, "_mod_err", None)
    return f'<div class="err"><b>Refused — nothing was written.</b> <code>{esc(m[0])}</code> {esc(m[1])}<p>What you entered is still in the form below.</p></div>' if m else ""


def need(h, cap: str) -> str:
    """A visible note instead of a hidden form when the signed-in principal cannot use it."""
    p = getattr(h, "_principal", None)
    if not h.server.principals.configured():
        return f'<div class="notice"><b>Trust boundary not set up.</b> This action needs a principal with the <b>{esc(cap)}</b> capability. Setup step (host operator, once): <code>{esc(authz.SETUP_STEP)}</code> — see <a href="/setup">Setup</a>. Until then the action is refused; nothing falls back to an unauthenticated path.</div>'
    if p is None or cap not in p["caps"]:
        return f'<p class="muted">Needs the <b>{esc(cap)}</b> capability ({esc(authz.CAP_MEANING[cap])}).</p>'
    return ""


def can(h, *caps) -> bool:
    p = getattr(h, "_principal", None)
    return bool(p and set(caps) & set(p["caps"]))


# ------------------------------------------------------------------ GET
def get(h, path: str, q: dict, extra) -> None:
    ws = h.server.ws
    send = lambda title, body, status=200: h._send(status, h.page(title, f'<p class="muted">{who(h)}</p>' + err_box(h) + body), extra=extra)
    try:
        if path == "/login":
            return send("Sign in", page_login(h, q))
        if path == "/logout":
            if getattr(h, "_auth_sid", None):
                h.server.sessions.close(h._auth_sid)
            return h._headers(303, "text/plain; charset=utf-8", 0, {"Location": "/modules", "Set-Cookie": "wb_auth=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})
        if path == "/modules":
            return send("Modules — SHD · EVO · COM · PRC", page_modules(h))
        if path == "/setup":
            return send("Setup and status — principals and the restricted worker", page_setup(h, q))
        if path == "/shd":
            return send("SHD — Distillation Shield: protected evidence admission", page_shd(h, q))
        if path == "/shd/trust":
            return send("SHD — trust roots, policy and approvals", page_shd_trust(h, q))
        m = re.match(rf"^/shd/decision/{_ID}$", path)
        if m:
            return send(f"SHD decision {m.group(1)}", page_shd_decision(h, m.group(1)))
        if path == "/evo":
            return send("EVO — Evolution Evidence Audit", page_evo(h, q))
        m = re.match(rf"^/evo/version/{_ID}$", path)
        if m:
            return send(f"EVO version {m.group(1)}", page_evo_version(h, m.group(1), q))
        if path == "/com":
            return send("COM — Research Commons Guard: the review queue", page_com(h, q))
        m = re.match(rf"^/com/group/{_ID}$", path)
        if m:
            return send(f"COM group {m.group(1)}", page_com_group(h, m.group(1)))
        if path == "/prc":
            return send("PRC — Independent Practice", page_prc(h, q))
        m = re.match(rf"^/prc/session/{_ID}$", path)
        if m:
            return send(f"Practice session {m.group(1)}", page_prc_session(h, m.group(1), q))
        m = re.match(rf"^/prc/session/{_ID}/source$", path)
        if m:
            return send("Practice session — evidence", page_prc_source(h, m.group(1), q))
        m = re.match(r"^/prc/checkpoint/([0-9]{1,5})\.json$", path)
        if m:
            authz.require(h._principal, "admin"); cps = practice.state(ws)["checkpoints"]; n = int(m.group(1))
            if not 1 <= n <= len(cps):
                return h._text(404, "no such checkpoint")
            return h._send(200, json.dumps(cps[n - 1]["checkpoint"], sort_keys=True), "application/json; charset=utf-8", {"Content-Disposition": f'attachment; filename="yuclaw-checkpoint-{n}.json"'})
        if path == "/modx":
            return send("Module evidence export and verification", page_modx(h, q, None))
        m = re.match(r"^/modx/(modx-[0-9a-f]{16})\.zip$", path)
        if m:
            built = next((e for e in ws.load()["events"] if e["kind"] == "MODULE_EXPORT_BUILT" and e["payload"]["export_id"] == m.group(1)), None); p = h._principal
            if built is None or p is None or not (built["payload"]["built_by"] == p["principal_id"] or "admin" in p["caps"]):
                return h._text(404, "no such export for this principal")
            return h._send(200, (ws.exports / f"{m.group(1)}.zip").read_bytes(), "application/zip", {"Content-Disposition": f'attachment; filename="{m.group(1)}.zip"'})
        return h._text(404, "not found")
    except ModuleError as exc:
        status = 403 if exc.code in ("E_FORBIDDEN", "E_SIGN_IN", "E_CONFLICT") else 404 if exc.code in ("E_NOT_FOUND", "E_UNKNOWN") else 422
        return send("Refused", f'<div class="err"><p><code>{esc(exc.code)}</code> {esc(exc.detail)}</p></div><p><a href="/modules">Back to Modules</a></p>', status)


# ------------------------------------------------------------------ POST
def post(h, path: str) -> None:
    ws = h.server.ws; P = h.server.principals; p = h._principal
    if path in ("/shd/submit", "/modx/verify"):
        return post_upload(h, path)
    f = h._form()
    if f is None:
        return h._text(400, "refused: form body missing, too large or not urlencoded")
    if not h._csrf_ok(f):
        return h._text(403, "refused: CSRF token invalid; nothing was written. Reload the page you submitted from and submit again")
    op = f.get("op_id", "")
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$", op):
        return h._text(400, "refused: operation identifier missing")
    g = lambda k, d="": f.get(k, d)
    num = lambda k: int(g(k)) if re.match(r"^-?\d{1,9}$", g(k).strip()) else -1
    back = "/modules"
    try:
        if path == "/login":
            pid = g("principal_id").strip()
            if h.server.sessions.throttle(pid):
                raise ModuleError("E_AUTH", "too many failed attempts for this principal; wait a few minutes")
            try:
                pr = P.authenticate(pid, g("credential"))
            except ModuleError:
                h.server.sessions.failed(pid); raise
            sid = h.server.sessions.open(pr); nxt = g("next") if re.match(r"^/[A-Za-z0-9/_.-]*$", g("next")) else "/modules"
            return h._headers(303, "text/plain; charset=utf-8", 0, {"Location": nxt, "Set-Cookie": f"wb_auth={sid}; Path=/; HttpOnly; SameSite=Strict"})
        # ---- setup (admin)
        if path == "/setup/enroll":
            back = "/setup"; authz.require(p, "admin")
            ev, cred = P.enroll(g("principal_id").strip(), [c for c in authz.CAPS if g("cap_" + c)], display_name=g("display_name"), declared_role_note=g("declared_role_note"), expires_at=g("expires_at") or None, op_id=op, by=p)
            return h._send(200, h.page("Principal enrolled — credential shown once", _credential_once(ev["payload"]["principal_id"], cred)))
        if path == "/setup/rotate":
            back = "/setup"; authz.require(p, "admin"); ev, cred = P.rotate(g("principal_id"), op_id=op, by=p)
            return h._send(200, h.page("Credential rotated — shown once", _credential_once(ev["payload"]["principal_id"], cred)))
        if path == "/setup/revoke":
            back = "/setup"; authz.require(p, "admin"); P.revoke(g("principal_id"), g("reason"), op_id=op, by=p); return h._redirect("/setup?done=revoked")
        if path == "/setup/probe":
            back = "/setup"; authz.require(p, "admin"); sandbox.capability(refresh=True); return h._redirect("/setup?done=probed")
        # ---- SHD
        if path == "/shd/root":
            back = "/shd/trust"; shield.enroll_root(ws, p, label=g("label"), public_key=g("public_key").strip() or None, op_id=op); return h._redirect("/shd/trust?done=root")
        if path == "/shd/root/revoke":
            back = "/shd/trust"; shield.revoke_root(ws, p, g("key_id"), g("reason"), op_id=op); return h._redirect("/shd/trust?done=root-revoked")
        if path == "/shd/policy":
            back = "/shd/trust"; shield.set_policy(ws, p, max_approval_days=num("max_approval_days"), allowed_purposes=[x for x in PURPOSES if g("purpose_" + x)], op_id=op); return h._redirect("/shd/trust?done=policy")
        if path == "/shd/approve":
            back = "/shd/trust"; shield.issue_approval(ws, p, bundle_sha256=g("bundle_sha256").strip(), source_sha256s=g("source_sha256s").split(), purpose=g("purpose"), expires_at=g("expires_at"), op_id=op); return h._redirect("/shd/trust?done=approved")
        if path == "/shd/approval/revoke":
            back = "/shd/trust"; shield.revoke_approval(ws, p, g("approval_id"), g("reason"), op_id=op); return h._redirect("/shd/trust?done=approval-revoked")
        if path == "/shd/admit":
            back = "/shd"; ev = shield.admit(ws, p, g("submission_id"), op_id=op); return h._redirect("/shd/decision/" + ev["payload"]["decision_id"])
        # ---- EVO
        if path == "/evo/config":
            back = "/evo"; evolution.set_config(ws, p, core.strict_json(g("config").encode("utf-8"), max_bytes=64 * 1024, code="CONFIG"), op_id=op); return h._redirect("/evo?done=config")
        if path == "/evo/register":
            back = "/evo"; ev = evolution.register_version(ws, p, version_id=g("version_id").strip(), parent_version_id=g("parent_version_id").strip() or None, label=g("label"), declared={"model": g("declared_model")}, op_id=op)
            return h._redirect("/evo/version/" + ev["payload"]["version_id"])
        if path == "/evo/import":
            back = "/evo"; evolution.import_declared(ws, p, g("decision_id").strip(), op_id=op); return h._redirect("/evo?done=imported")
        if path == "/evo/access":
            back = "/evo"; evolution.record_test_access(ws, p, subject_principal=g("principal_id").strip(), action=g("action"), op_id=op); return h._redirect("/evo?done=access")
        m = re.match(rf"^/evo/version/{_ID}/(evaluate|review|request|commitment|resolve)$", path)
        if m:
            vid, act = m.group(1), m.group(2); back = "/evo/version/" + vid
            if act == "evaluate":
                evolution.run_evaluation(ws, p, version_id=vid, protocol_id=g("protocol_id"), op_id=op)
            elif act == "review":
                evolution.record_review(ws, p, version_id=vid, decision=g("decision"), note=g("note"), asserted_review_time=g("asserted_review_time") or None, op_id=op)
            elif act == "request":
                evolution.request_reevaluation(ws, p, version_id=vid, protocol_id=g("protocol_id"), reason=g("reason"), op_id=op)
            elif act == "commitment":
                evolution.link_commitment(ws, p, version_id=vid, claim_id=g("claim_id").strip(), amount=g("amount").strip() or None, currency=g("currency"), op_id=op)
            else:
                evolution.resolve_failure(ws, p, issue_id=g("issue_id"), evidence_evaluation_id=g("evidence_evaluation_id").strip(), reason=g("reason"), op_id=op)
            return h._redirect(back + "?done=" + act)
        # ---- COM
        if path.startswith("/com/"):
            back = "/com"
            if path == "/com/budget":
                commons.set_budget(ws, p, period_id=g("period_id").strip(), review_minutes=num("review_minutes"), practice_minutes=num("practice_minutes"), contributor_packet_cap=num("contributor_packet_cap"), max_open_tasks=num("max_open_tasks"), op_id=op)
            elif path == "/com/submit":
                commons.submit_direct(ws, p, claim_id=g("claim_id").strip(), kind=g("kind"), ancestry=g("ancestry"), derived_from=g("derived_from").split(), proposed_cost_minutes=max(1, num("proposed_cost_minutes")),
                                      asserts_withdrawn=bool(g("asserts_withdrawn")), client_packet_id=g("client_packet_id").strip() or None, op_id=op)
            elif path == "/com/intake":
                commons.intake_from_shield(ws, p, g("decision_id").strip(), op_id=op)
            elif path == "/com/cost":
                commons.set_cost(ws, p, group_id_=g("group_id"), minutes=num("minutes"), rule=g("rule"), op_id=op)
            elif path == "/com/assign":
                commons.assign(ws, p, g("group_id"), op_id=op)
            elif path == "/com/work":
                commons.work(ws, p, g("group_id"), g("action"), note=g("note"), op_id=op)
            elif path == "/com/leases":
                commons.recover_leases(ws, p, op_id=op)
            elif path == "/com/effort":
                commons.declare_effort(ws, p, group_id_=g("group_id"), minutes=num("minutes"), category=g("category"), op_id=op)
            elif path == "/com/urgent":
                commons.override_urgent(ws, p, group_id_=g("group_id"), reason=g("reason"), op_id=op)
            elif path == "/com/dispute":
                commons.record_dispute(ws, p, target_type=g("target_type"), target=g("target").strip(), dispute_type=g("dispute_type"), reason=g("reason"), op_id=op)
            elif path == "/com/appeal":
                commons.appeal(ws, p, dispute_id=g("dispute_id"), reason=g("reason"), op_id=op)
            elif path == "/com/resolve":
                commons.resolve_dispute(ws, p, dispute_id=g("dispute_id"), outcome=g("outcome"), reason=g("reason"), op_id=op)
            else:
                return h._text(404, "not found")
            return h._redirect("/com?done=" + path.rsplit("/", 1)[1])
        # ---- PRC
        if path == "/prc/task":
            back = "/prc"
            practice.freeze_task(ws, p, title=g("title"), question=g("question"), claim_id=g("claim_id").strip() or None, source_ids=g("source_ids").split(), labels=[x.strip() for x in g("labels").split(",") if x.strip()],
                                 reference_label=g("reference_label").strip(), reference_answer=g("reference_answer"), rationale=g("rationale"), provenance=g("provenance"), declared_curator_qualification=g("declared_curator_qualification"),
                                 public_example=bool(g("public_example")), session_minutes=num("session_minutes"), evo_version_id=g("evo_version_id").strip() or None, op_id=op)
            return h._redirect("/prc?done=task")
        if path == "/prc/open":
            back = "/prc"; ev = practice.open_session(ws, p, task_id=g("task_id"), assistance=g("assistance"), assistance_note=g("assistance_note"), prior_exposure=g("prior_exposure"), op_id=op)
            return h._redirect("/prc/session/" + ev["payload"]["session_id"])
        if path == "/prc/followup":
            back = "/prc"; practice.schedule_followup(ws, p, session_id=g("session_id"), followup_task_id=g("followup_task_id"), due_at=g("due_at"), op_id=op); return h._redirect("/prc?done=followup")
        if path == "/prc/checkpoint":
            back = "/prc"; practice.issue_checkpoint(ws, p, op_id=op); return h._redirect("/prc?done=checkpoint")
        m = re.match(rf"^/prc/session/{_ID}/(attempt|reveal|reflect|feedback)$", path)
        if m:
            sid, act = m.group(1), m.group(2); back = "/prc/session/" + sid
            if act == "attempt":
                practice.commit_attempt(ws, p, sid, judgment=g("judgment"), reasoning=g("reasoning"), source_refs=[k[4:] for k in f if k.startswith("ref_")], unresolved_note=g("unresolved_note"), op_id=op)
            elif act == "reveal":
                practice.reveal(ws, p, sid)
            elif act == "reflect":
                practice.reflect(ws, p, sid, text_=g("reflection"), op_id=op)
            else:
                practice.feedback(ws, p, sid, text_=g("feedback"), op_id=op)
            return h._redirect(back + "?done=" + act)
        # ---- export
        if path == "/modx/build":
            back = "/modx"; r = modexport.build_packet(ws, p, modules=[m_ for m_ in ("SHD", "EVO", "COM") if g("mod_" + m_)], prc_sessions=g("prc_sessions").split(), withhold_text=bool(g("withhold_text")), op_id=op)
            return h._redirect("/modx?built=" + r["export_id"])
        if path == "/modx/resolve":
            back = "/modx"; modexport.resolve_discrepancy(ws, p, packet_sha256=g("packet_sha256").strip(), resolution=g("resolution"), op_id=op); return h._redirect("/modx?done=resolved")
        return h._text(404, "not found")
    except ModuleError as exc:
        h._mod_err = (exc.code, exc.detail); h._mod_form = f
        status = 403 if exc.code in ("E_FORBIDDEN", "E_SIGN_IN", "E_CONFLICT", "E_AUTH", "REFUSED_SELF_APPROVAL") else 404 if exc.code == "E_NOT_FOUND" else 422
        u = urllib.parse.urlsplit(back); h.path = back
        h._principal = p
        return _rerender(h, u.path, status)


def _rerender(h, path: str, status: int):
    class _Cap:                                                             # render the GET page for `path` with the refusal on top, at the refusal's status
        pass
    orig = h._send

    def send(st, body, ctype="text/html; charset=utf-8", extra=None):
        return orig(status if st == 200 else st, body, ctype, extra)
    h._send = send
    try:
        return get(h, path, {}, None)
    finally:
        h._send = orig


def post_upload(h, path: str) -> None:
    """Multipart uploads. The size limit is applied to Content-Length BEFORE any byte of the body is read; the parent then
    splits the multipart frame (a fixed, bounded format it generated itself) and never opens the uploaded file's content."""
    ws = h.server.ws; limit = MAX_BUNDLE + 256 * 1024
    ct = h.headers.get("Content-Type", ""); body = h._read_body(limit)
    if body is None or not ct.startswith("multipart/form-data"):
        h.close_connection = True
        return h._text(413, f"refused: the upload is missing or larger than {limit // (1024 * 1024)} MiB; nothing was read or written")
    from v8.workbench.server import Multipart
    try:
        mp = Multipart(ct, body)
    except Exception:                                                        # noqa: BLE001
        return h._text(400, "refused: malformed multipart body")
    if not h._csrf_ok(mp.fields):
        return h._text(403, "refused: CSRF token invalid; nothing was written")
    op = mp.fields.get("op_id", "")
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$", op):
        return h._text(400, "refused: operation identifier missing")
    try:
        if path == "/shd/submit":
            data = (mp.files.get("bundle") or ("", b""))[1]
            ev = shield.submit(ws, h._principal, data, title=mp.fields.get("title", ""), op_id=op)
            return h._redirect("/shd?submitted=" + ev["payload"]["submission_id"])
        data = (mp.files.get("packet") or ("", b""))[1]; cp = (mp.files.get("checkpoint") or ("", b""))[1] or None
        if not data:
            raise ModuleError("E_REQUIRED", "choose the module packet zip (modx-….zip)")
        if h.server.principals.configured() and h._principal is None:
            raise ModuleError("E_SIGN_IN", "sign in to verify a packet here")
        res = modexport.verify_packet(ws, data, checkpoint=cp, principal=h._principal, op_id=op)
        return h._send(200, h.page("Module packet verification", f'<p class="muted">{who(h)}</p>' + page_modx(h, {}, res)))
    except ModuleError as exc:
        h._mod_err = (exc.code, exc.detail); h._mod_form = mp.fields
        return _rerender(h, "/shd" if path == "/shd/submit" else "/modx", 403 if exc.code in ("E_FORBIDDEN", "E_SIGN_IN") else 422)


def _credential_once(pid: str, cred: str | None) -> str:
    if cred is None:
        return f'<p>Principal <code>{esc(pid)}</code>: this operation was already recorded; its credential is not shown again. Rotate the credential on <a href="/setup">Setup</a> to obtain a new one.</p>'
    return (f'<div class="notice"><p>Principal <code>{esc(pid)}</code>. <b>This credential is shown once and is not stored</b> (only an scrypt hash is kept). Hand it to its holder now:</p>'
            f'<p><code id="credential">{esc(cred)}</code></p></div><p><a href="/setup">Back to Setup</a></p>')


# ------------------------------------------------------------------ pages: sign-in, Modules, Setup
def page_login(h, q) -> str:
    if not h.server.principals.configured():
        return f'<div class="notice"><p>No principal exists in this workspace yet, so there is nothing to sign in to. The host operator creates the first administrator once:</p><p><code>{esc(authz.SETUP_STEP)}</code></p><p>See <a href="/setup">Setup</a>.</p></div>'
    return form(h, "/login", f'<input type="hidden" name="next" value="{esc(q.get("next", "/modules"))}">' + field(h, "Principal id", "principal_id") + '<p><label>Credential</label> <input type="password" name="credential" size="50" autocomplete="off"></p>',
                "Sign in") + '<p class="muted">Signing in proves which local credential is acting. It says nothing about legal identity, qualification or who is at the keyboard.</p>'


def page_modules(h) -> str:
    ws = h.server.ws; cap = sandbox.capability(); conf = h.server.principals.configured(); evs = ws.load()["events"]
    cs = commons.capacity(commons.state(ws, evs=evs)); es = evolution.state(ws, evs=evs)
    rows = [
        ("SHD — Distillation Shield", "/shd", "Admit an evidence bundle through a controlled boundary: an administrator's signed approval for the exact bytes, verification inside a restricted worker, a typed result with a fixed reason. Admission never makes a statement true.",
         f"restricted worker: <b>{esc(cap['backend'] or 'CLOSED')}</b>" + ("" if cap["backend"] else f' — <a href="/setup">why</a>')),
        ("EVO — Evolution Evidence Audit", "/evo", "Register measured versions of an AI system's parts, see what changed, and which review evidence still applies. It audits; it controls no deployment.", "configuration: " + ("recorded" if es["config"] else "<b>not recorded</b> (administrator)")),
        ("COM — Research Commons Guard", "/com", "A durable review queue: exact duplicate groups, authenticated admission limits, transactional budgets with a separate practice reserve, disputes with appeals.", "budget: " + (f"period {esc(cs['period_id'])}" if cs.get("configured") else "<b>not set</b> (administrator)")),
        ("PRC — Independent Practice", "/prc", "Commit a judgment and reasoning on a frozen task before the comparison opens; then reflect. Assisted and already-exposed sessions are labelled, not refused.", "comparison: server-held until the attempt is committed"),
    ]
    body = ('<p>Four modules share this workbench\'s claims, versions, sources and journal. ' + ("" if conf else f'<b>The trust boundary is not set up</b>: protected actions are refused until the host operator runs <code>{esc(authz.SETUP_STEP)}</code> (<a href="/setup">Setup</a>). ') + '</p>'
            + table(["Module", "What you can do", "Status"], [[f'<a href="{u}"><b>{esc(n)}</b></a>', esc(d), s] for n, u, d, s in rows])
            + '<p><a href="/modx">Module evidence export and verification</a> · <a href="/setup">Setup and status</a></p>'
            + '<h2>What these modules do not establish</h2><ul><li>A signed or admitted bundle is not thereby true; no factual adjudication happens in SHD.</li><li>EVO does not detect or control self-improvement and gates no external deployment.</li>'
              '<li>A duplicate or a shared source is not evidence of misconduct; the FIFO comparison is a simulation, not a measurement of people.</li><li>PRC records order and declarations; it cannot prove authorship, comprehension or improved ability. Human benefit: PENDING.</li>'
              '<li>No independent security review has been performed. The restricted worker\'s denials are probed on this host and listed on Setup; that is not a certification.</li></ul>')
    return body


def page_setup(h, q) -> str:
    P = h.server.principals; conf = P.configured(); cap = sandbox.capability(); st = P.state()
    out = ['<h2>1 · Principals (the local trust boundary)</h2>']
    if not conf:
        out.append(f'<div class="notice"><p><b>Not set up.</b> The first administrator is created only from the host command line, never from this page (a browser on the loopback port must not be able to enroll itself):</p><p><code>{esc(authz.SETUP_STEP)}</code></p>'
                   '<p>It prints a generated credential once. No default password exists and no key ships with the package. After that, every page asks for sign-in and administrators enroll further principals here.</p></div>')
    else:
        out.append(table(["Principal", "Capabilities", "Enrolled", "Expires", "State", "Credential id"],
                         [[f"<code>{esc(p['principal_id'])}</code> {esc(p['display_name'])}", esc(", ".join(p["caps"])), esc(p["enrolled_at"]) + " by " + esc(p["enrolled_by"]), esc(p["expires_at"] or "—"),
                           "REVOKED " + esc(p["revoked_at"]) if p["revoked_at"] else "active", f"<code>{esc(p['credential_id'])}</code>"] for p in st.values()]))
        if can(h, "admin"):
            caps = "".join(f'<label><input type="checkbox" name="cap_{c}" value="1"> {c}</label> ' for c in authz.CAPS)
            out.append("<h3>Enroll a principal</h3>" + form(h, "/setup/enroll", field(h, "Principal id", "principal_id", hint="lowercase, 2–40 characters") + f"<p>{caps}</p>" + field(h, "Display name (a label, never an identity)", "display_name")
                       + field(h, "Declared role note (recorded as declared)", "declared_role_note") + field(h, "Expires at (UTC, optional)", "expires_at", hint="YYYY-MM-DDTHH:MM:SSZ"), "Enroll and show the credential once"))
            out.append("<h3>Rotate or revoke</h3>" + form(h, "/setup/rotate", field(h, "Principal id", "principal_id"), "Rotate credential") + form(h, "/setup/revoke", field(h, "Principal id", "principal_id") + field(h, "Reason", "reason"), "Revoke (never revived)"))
        else:
            out.append(need(h, "admin"))
    out.append('<h2>2 · Restricted worker (SHD isolation)</h2>')
    out.append(f'<p>Backend in use: <b>{esc(cap["backend"] or "NONE — the protected SHD route is CLOSED")}</b>. A backend is used only after a live probe on this host shows every required denial. There is no unconfined fallback.</p>')
    for pr in cap["probes"]:
        obs = pr.get("observed") or {}
        out.append(f'<h3>{esc(pr["backend"])}: {"AVAILABLE" if pr["available"] else "UNAVAILABLE"}</h3><p class="muted">{esc(pr.get("platform"))} · Python {esc(pr.get("python"))} · checked {esc(pr.get("checked_at"))}</p>'
                   + (f'<p>{esc(pr.get("reason"))}</p>' if pr.get("reason") else "") + (table(["Attempt inside the worker", "Observed"], [[esc(k), esc(v)] for k, v in sorted(obs.items()) if isinstance(v, str)]) if obs else ""))
    if not cap["backend"]:
        out.append('<div class="notice"><p>Platform gap, stated plainly: bubblewrap needs unprivileged user namespaces (on Ubuntu 24.04 an AppArmor profile for <code>bwrap</code>, which only the machine\'s administrator can install); the Landlock backend needs a kernel with the Landlock LSM and seccomp. '
                   'Nothing in this product weakens host security to obtain a pass. Until a backend passes, bundles are refused with <code>REFUSED_ISOLATION_UNAVAILABLE</code>; the rest of the workbench is unaffected.</p></div>')
    if can(h, "admin"):
        out.append(form(h, "/setup/probe", "", "Run the isolation probe again"))
    return "".join(out)


# ------------------------------------------------------------------ pages: SHD
def page_shd(h, q) -> str:
    ws = h.server.ws; st = shield.state(ws); cap = sandbox.capability(); me = (h._principal or {}).get("principal_id")
    decided: dict = {}
    for d in st["decisions"].values():
        decided.setdefault(d["submission_id"], []).append(d)
    rows = []
    for s in sorted(st["submissions"].values(), key=lambda s: s["received_at"], reverse=True):
        ds = decided.get(s["submission_id"], []); last = ds[-1] if ds else None
        act = form(h, "/shd/admit", f'<input type="hidden" name="submission_id" value="{esc(s["submission_id"])}">', "Request a decision") if can(h, "submit", "review", "admin") and (me == s["submitter"] or can(h, "review", "admin")) else ""
        rows.append([esc(s["submission_id"]), esc(s["title"]), f"<code>{esc(s['bundle_sha256'])}</code>", esc(s["size_bytes"]), esc(s["submitter"]), esc(s["received_at"]),
                     (f'<a href="/shd/decision/{esc(last["decision_id"])}"><b>{esc(last["result"])}</b> <code>{esc(last["code"])}</code></a>' if last else "undecided") + act])
    out = [f'<p>Restricted worker: <b>{esc(cap["backend"] or "CLOSED")}</b>. Policy version {esc(st["policy"]["policy_version"])}. <a href="/shd/trust">Trust roots, policy and approvals</a> (administrator).</p>',
           '<h2>Submit a bundle</h2>', need(h, "submit")]
    if can(h, "submit"):
        out.append(form(h, "/shd/submit", field(h, "Title", "title") + f'<p><label>Bundle zip</label> <input type="file" name="bundle"> <span class="muted">a zip with <code>bundle.json</code> and <code>evidence/…</code>; at most {MAX_BUNDLE // (1024 * 1024)} MiB. '
                        'The server stores and hashes the bytes; only the restricted worker opens them.</span></p>', "Submit", multipart=True))
    out += ['<h2>Submissions and decisions</h2>', table(["Id", "Title", "Bundle sha256 (what an approval must name)", "Bytes", "Submitter", "Received", "Decision"], rows),
            '<p class="muted">Order of use: submit → an administrator OTHER than the submitter approves that exact sha256 for one purpose → request a decision → the typed result can feed <a href="/com">COM intake</a> or the <a href="/evo">EVO import</a> while the approval stays applicable.</p>']
    return "".join(out)


def page_shd_trust(h, q) -> str:
    ws = h.server.ws; st = shield.state(ws); out = [need(h, "admin")]
    out.append("<h2>Trust roots</h2>" + table(["Key id", "Label", "Enrolled", "State"], [[f"<code>{esc(r['key_id'])}</code>", esc(r["label"]), esc(r["enrolled_at"]) + " by " + esc(r["enrolled_by"]),
                                                                                     ("REVOKED " + esc(r["revoked_at"]) + " — " + esc(r["revoked_reason"])) if r["revoked"] else "trusted"] for r in st["roots"].values()]))
    out.append(f'<h2>Policy</h2><p>Version <b>{esc(st["policy"]["policy_version"])}</b>: approvals valid at most {esc(st["policy"]["max_approval_days"])} day(s); purposes {esc(", ".join(st["policy"]["allowed_purposes"]))}. Trust revision {esc(st["trust_revision"])}.</p>')
    out.append("<h2>Approvals</h2>" + table(["Id", "Bundle sha256", "Purpose", "Approver", "Key", "Issued", "Expires", "Policy", "State"],
               [[esc(a["approval_id"]), f"<code>{esc(a['bundle_sha256'][:16])}…</code>", esc(a["purpose"]), esc(a["approver"]), f"<code>{esc(a['key_id'][:12])}…</code>", esc(a["issued_at"]), esc(a["expires_at"]), esc(a["policy_version"]),
                 ("REVOKED " + esc(a["revoked_at"])) if a["revoked_at"] else "issued"] for a in st["approvals"].values()]))
    if can(h, "admin"):
        out.append("<h3>Enroll a root</h3>" + form(h, "/shd/root", field(h, "Label", "label") + field(h, "Ed25519 public key, base64 (leave empty to generate a signing key here)", "public_key"), "Enroll root"))
        out.append("<h3>Revoke a root</h3>" + form(h, "/shd/root/revoke", field(h, "Key id", "key_id") + field(h, "Reason", "reason"), "Revoke root"))
        purposes = "".join(f'<label><input type="checkbox" name="purpose_{esc(x)}" value="1" checked> {esc(x)}</label> ' for x in PURPOSES)
        out.append("<h3>Set the policy (starts a new policy version)</h3>" + form(h, "/shd/policy", field(h, "Maximum approval validity, days", "max_approval_days", default="30") + f"<p>{purposes}</p>", "Record policy"))
        out.append("<h3>Approve exact bytes</h3>" + form(h, "/shd/approve", field(h, "Bundle sha256", "bundle_sha256") + field(h, "Evidence sha256 list (space separated; what the bundle's evidence files must hash to)", "source_sha256s", rows=3)
                   + select(h, "Purpose", "purpose", PURPOSES) + field(h, "Expires at (UTC)", "expires_at", hint="YYYY-MM-DDTHH:MM:SSZ"), "Sign and record the approval"))
        out.append("<h3>Revoke an approval</h3>" + form(h, "/shd/approval/revoke", field(h, "Approval id", "approval_id") + field(h, "Reason", "reason"), "Revoke approval"))
    if st["discrepancies"]:
        out.append("<h2>Trust discrepancies from imports (retained)</h2>" + table(["Recorded", "Record"], [[esc(d["recorded_at"]), esc(d.get("discrepancy") or d.get("resolution"))] for d in st["discrepancies"]]))
    return "".join(out)


def page_shd_decision(h, did: str) -> str:
    ws = h.server.ws; d = shield.state(ws)["decisions"].get(did)
    if d is None:
        raise ModuleError("E_NOT_FOUND", "no such decision")
    aa = d["authority_approval"]
    out = [table(["Field", "Value"], [["Result", f"<b>{esc(d['result'])}</b> <code>{esc(d['code'])}</code> {esc(d['detail'])}"], ["Next action", esc(d["next_action"])], ["Byte integrity", esc(d["byte_integrity"])],
                                       ["Authority approval", f"{esc(aa['status'])} — approval {esc(aa['approval_id'])} by {esc(aa['approver'])}, key <code>{esc(aa['key_id'])}</code>, policy v{esc(aa['policy_version'])}, trust revision {esc(aa['trust_revision'])}, expires {esc(aa['expires_at'])}"],
                                       ["Factual adjudication", esc(d["factual_adjudication"])], ["Release permission", esc(d["release_permission"])], ["Bundle", f"<code>{esc(d['bundle_sha256'])}</code> from {esc(d['submitter'])}"],
                                       ["Isolation", esc(json.dumps(d["isolation"]))], ["Recorded", esc(d["recorded_at"]) + " on request of " + esc(d["requested_by"])]])]
    if d["result"] == "ADMITTED":
        typed = core.Vault(ws).get(d["typed_result_sha256"])
        out.append(f'<h2>Typed result (what a consumer may read)</h2><p>Purpose <code>{esc(typed["purpose"])}</code>; {len(typed["evidence"])} evidence file(s).</p>'
                   + table(["Evidence path", "sha256", "Bytes"], [[esc(e["path"]), f"<code>{esc(e['sha256'])}</code>", esc(e["size"])] for e in typed["evidence"]]) + f'<div class="guide">{esc(json.dumps(typed["payload"], indent=1))}</div>')
        if can(h, "admin", "review"):
            out.append('<h2>Human inspection (separate, escaped, never an input to a consumer)</h2>' + "".join(f'<h3>{esc(x["path"])}{" (truncated)" if x["truncated"] else ""}</h3><div class="guide">{esc(x["text"])}</div>' for x in shield.inspection(ws, h._principal, did))
                       + '<p class="muted">Shown as inert text. Instruction-like sentences in evidence are data: nothing here is executed, fetched or passed to a tool.</p>')
    return "".join(out) + '<p><a href="/shd">Back to SHD</a></p>'


# ------------------------------------------------------------------ pages: EVO
def page_evo(h, q) -> str:
    ws = h.server.ws; st = evolution.state(ws); cfg = st["config"]
    out = ['<p>Eight components per version: ' + esc(", ".join(evolution.COMPONENTS)) + '. Each is MEASURED, DECLARED, UNKNOWN or NOT_APPLICABLE; a provider alias is never a measurement.</p>']
    out.append("<h2>Versions</h2>" + table(["Version", "Parent", "Improver", "Changed from parent", "Unknown inventory", "Registered"],
               [[f'<a href="/evo/version/{esc(v["version_id"])}"><b>{esc(v["version_id"])}</b></a> {esc(v["label"])}', esc(v["parent_version_id"] or "—"), esc(v["improver"]), esc(", ".join(v["changed_components"]) or "nothing"), esc(", ".join(v["inventory"]["unknown"]) or "none"), esc(v["recorded_at"])]
                for v in st["versions"].values()]))
    out.append("<h2>Register the current state as a version</h2>" + need(h, "submit"))
    if can(h, "submit"):
        out.append(form(h, "/evo/register", field(h, "Version id", "version_id") + field(h, "Parent version id (empty for the first)", "parent_version_id") + field(h, "Label", "label") + field(h, "Declared model identity (kept as DECLARED)", "declared_model"),
                        "Measure and register") if cfg else '<p class="muted">An administrator records the configuration first.</p>')
        out.append("<h3>Import declared evaluations from an SHD-admitted bundle</h3>" + form(h, "/evo/import", field(h, "SHD decision id (purpose evo.evaluations)", "decision_id"), "Import as DECLARED_IMPORT"))
    out.append("<h2>Reevaluation requests</h2>" + table(["Request", "Version", "Protocol", "Job", "Reason", "By"], [[esc(r["request_id"]), esc(r["version_id"]), esc(r["protocol_id"]), esc(r["job"]), esc(r["reason"]), esc(r["requested_by"])] for r in st["requests"].values()]))
    out.append("<h2>Protected-test access records</h2>" + table(["Principal", "Action", "Recorded"], [[esc(a["principal_id"]), esc(a["action"]), esc(a["recorded_at"])] for a in st["test_access"]]))
    out.append("<h2>Configuration (administrator)</h2>" + (f'<p>Recorded {esc(cfg["set_at"])} by {esc(cfg["set_by"])}; digest <code>{esc(cfg["config_digest"][:16])}…</code></p><div class="guide">{esc(json.dumps({k: cfg[k] for k in ("roots", "components", "depends_on", "protocols", "authority")}, indent=1))}</div>' if cfg else "<p><b>Not recorded.</b></p>") + need(h, "admin"))
    if can(h, "admin"):
        out.append(form(h, "/evo/config", field(h, "Configuration JSON: roots, components {name: {mode: path|declared|unknown|not_applicable|runtime, …}}, depends_on, protocols {id: {scope, job, validity_days}}, authority", "config", rows=12), "Record configuration")
                   + form(h, "/evo/access", field(h, "Principal id", "principal_id") + select(h, "Protected-test access", "action", ("GRANTED", "REVOKED")), "Record test access"))
    return "".join(out)


def page_evo_version(h, vid: str, q) -> str:
    ws = h.server.ws; a = evolution.audit(ws, vid, q.get("as_of") or None); v = a["version"]; st = evolution.state(ws); parent = st["versions"].get(v["parent_version_id"]) if v["parent_version_id"] else None
    out = [f'<p>View: <b>{esc(a["view"])}</b>{" as of " + esc(a["as_of"]) if a["as_of"] else ""}. Lineage: {esc(" ← ".join(a["lineage"]))}. Improver <code>{esc(v["improver"])}</code>. '
           f'<form method="get" action="/evo/version/{esc(vid)}"><label>Historical cutoff (UTC)</label> <input name="as_of" value="{esc(a["as_of"] or "")}" size="24"> <button>Show what was recorded by then</button></form></p>']
    e = a["eligibility"]
    out.append(f'<h2>Eligibility (read-only)</h2><p><b>{esc(e["status"])}</b> — {esc(e["findings"])} finding(s). {esc(e["scope"])}</p>' + ("<ul>" + "".join(f"<li>{esc(g)}</li>" for g in a["gaps"]) + "</ul>" if a["gaps"] else ""))
    out.append("<h2>Inventory and change from the parent</h2>" + table(["Component", "Status", "Digest", "Detail", "vs parent"],
               [[esc(c), esc(v["components"][c]["status"]), f"<code>{esc((v['components'][c]['digest'] or '')[:16])}</code>", esc(v["components"][c]["detail"]), ("—" if parent is None else ("<b>CHANGED</b>" if c in v["changed_components"] else "same"))] for c in evolution.COMPONENTS]))
    out.append("<h2>Evidence reuse per protocol</h2>" + table(["Protocol", "Decision", "Configured closure", "Why"], [[esc(p), f"<b>{esc(d['decision'])}</b>" + (f" {esc(d['evaluation_id'])}" if d["evaluation_id"] else ""), esc(", ".join(d["closure"])), "<br>".join(esc(r) for r in d["reasons"])] for p, d in a["reuse"].items()]))
    out.append("<h2>Open failures on this lineage</h2>" + table(["Issue", "Key", "First failed", "Scope", "Recorded"], [[esc(f["issue_id"]), esc(f["issue_key"]), esc(f["first_failed_version"]), esc(", ".join(f["scope_closure"])), esc(f["recorded_at"])] for f in a["open_failures"]]))
    out.append("<h2>Evaluations on this lineage</h2>" + table(["Id", "Version", "Protocol", "Origin", "Result", "Failing", "Evaluated", "Valid until", "Age (days)"],
               [[esc(x["evaluation_id"]), esc(x["version_id"]), esc(x["protocol_id"]), esc(x["origin"]), esc(x["result"]), esc(", ".join(x["failing"])), esc(x["evaluated_at"]), esc(x["valid_until"]), esc(a["evidence_age_days"].get(x["evaluation_id"]))]
                for x in st["evaluations"].values() if x["version_id"] in a["lineage"]]))
    out.append("<h2>Reviews</h2>" + table(["Reviewer", "Decision", "Covers", "Note", "Recorded", "Asserted time"], [[esc(r["reviewer"]), esc(r["decision"]), esc(", ".join(r["covers_versions"])), esc(r["note"]), esc(r["recorded_at"]), esc((r["asserted_review_time"] or "") + (" — " + r["asserted_time_label"] if r["asserted_time_label"] else ""))] for r in a["reviews"]]))
    money = a["linked_commitments_by_currency"]
    out.append("<h2>Linked financial commitments (as supplied; no conversion)</h2>" + table(["Currency", "Known total", "Known", "Unknown amounts", "Claims"], [[esc(c), esc(m["known_total"]), esc(m["known_count"]), esc(m["unknown_amount_count"]), esc(", ".join(m["claims"]))] for c, m in money.items()]))
    protos = sorted((st["config"] or {}).get("protocols", {})); base = f"/evo/version/{vid}"
    if can(h, "review"):
        out.append("<h2>Reviewer actions</h2>" + form(h, base + "/evaluate", select(h, "Protocol (built-in job on an immutable snapshot)", "protocol_id", protos), "Run the trusted evaluation")
                   + form(h, base + "/review", select(h, "Decision", "decision", ("REVIEWED_ACCEPTABLE", "REVIEWED_CONCERNS")) + field(h, "Note", "note", rows=3) + field(h, "Asserted review time (optional; a backdated one is only labelled)", "asserted_review_time"), "Record review"))
    if can(h, "submit", "review", "admin"):
        out.append("<h2>Request a targeted reevaluation</h2>" + form(h, base + "/request", select(h, "Protocol", "protocol_id", protos) + field(h, "Reason", "reason"), "Record request"))
    if can(h, "submit"):
        out.append("<h2>Link a financial commitment</h2>" + form(h, base + "/commitment", field(h, "Claim id", "claim_id") + field(h, "Amount (whole number, empty = unknown)", "amount") + field(h, "Currency (default: the claim's)", "currency"), "Link"))
    if can(h, "admin") and a["open_failures"]:
        out.append("<h2>Resolve a failure (administrator, evidence-backed)</h2>" + form(h, base + "/resolve", select(h, "Issue", "issue_id", [f["issue_id"] for f in a["open_failures"]]) + field(h, "Supporting trusted-runner PASS (evaluation id)", "evidence_evaluation_id") + field(h, "Reason", "reason", rows=3), "Record resolution"))
    return "".join(out) + '<p><a href="/evo">Back to EVO</a></p>'


# ------------------------------------------------------------------ pages: COM
def page_com(h, q) -> str:
    ws = h.server.ws; d = commons.dashboard(ws, q.get("as_of") or None); s = d["state"]; cap = d["capacity"]; out = []
    if cap.get("configured"):
        out.append(f'<h2>Capacity — period {esc(cap["period_id"])}</h2>' + table(["", "Budget", "Reserved", "Consumed", "Remaining", "Overrun"],
                   [["Review minutes", esc(cap["review_minutes"]), esc(cap["reserved"]), esc(cap["consumed"]), esc(cap["remaining"]), f"<b>{esc(cap['overrun'])}</b>" if cap["overrun"] else "0"],
                    ["Practice minutes (separate reserve)", esc(cap["practice_minutes"]), esc(cap["practice_reserved"]), "—", esc(cap["practice_remaining"]), esc(cap["practice_overrun"])]])
                   + f'<p class="muted">Contributor cap {esc(cap["contributor_packet_cap"])} packets per principal per period; at most {esc(cap["max_open_tasks"])} open tasks. Review and practice minutes never borrow from each other. Budget revisions: {esc(len(cap["revisions"]))}.</p>')
    else:
        out.append('<div class="notice"><b>No budget is set.</b> An administrator sets the period, the review minutes, the separate practice reserve and the contributor cap below; until then submissions are refused.</div>')
    out.append(f'<h2>Dashboard</h2><p>Unique claims <b>{esc(d["unique_claims"])}</b> · review groups <b>{esc(d["groups"])}</b> · packets <b>{esc(d["packets"])}</b> · duplicate volume <b>{esc(d["duplicate_volume"])}</b> · unknown-ancestry groups <b>{esc(d["unknown_ancestry_groups"])}</b> · quarantined <b>{esc(d["quarantined"])}</b> · '
               f'oldest open task {esc(d["backlog_age_hours"]["oldest"])} h (median {esc(d["backlog_age_hours"]["median"])} h) · estimated minutes completed {esc(d["effort"]["estimated_minutes_completed"])} · server-observed seconds {esc(d["effort"]["server_observed_seconds"])} · declared minutes {esc(json.dumps(d["effort"]["declared_minutes_by_category"]))}</p>'
               f'<p class="muted">{esc(d["effort"]["note"])}. Shared roots (one source behind several groups is one root, not independent corroboration): {esc(json.dumps(d["shared_roots"]) if d["shared_roots"] else "none")}.</p>')
    why = {r["group_id"]: r["reason"] for r in d["plan"]["deferred"]}; fits = {r["group_id"] for r in d["plan"]["selected"]}
    rows = []
    for g in sorted(s["groups"].values(), key=lambda g: g["first_at"]):
        gid = g["group_id"]; hid = f'<input type="hidden" name="group_id" value="{esc(gid)}">'; acts = []
        if can(h, "review") and gid in fits:
            acts.append(form(h, "/com/assign", hid, "Take (reserves the cost)"))
        if can(h, "review") and g["assignee"] == (h._principal or {}).get("principal_id"):
            for a_ in {"ASSIGNED": ("start", "release"), "ACTIVE": ("pause", "finish"), "PAUSED": ("resume", "finish", "release")}.get(g["state"], ()):
                acts.append(form(h, "/com/work", hid + f'<input type="hidden" name="action" value="{a_}"><input name="note" size="18" placeholder="note">', a_))
        rows.append([f'<a href="/com/group/{esc(gid)}"><code>{esc(gid)}</code></a>', esc(g["claim"]["claim_id"]), esc(len(g["packets"])), esc(", ".join(g["contributors"])), esc(g["ancestry"]), f"<b>{esc(g['state'])}</b>" + (" URGENT" if g["urgent"] else ""),
                     esc(g["cost_minutes"]) + f' <span class="muted">({esc(g["cost_authority"])}; proposals {esc(g["proposed_costs"])})</span>', esc(g["assignee"] or "—"), esc(g["observed_seconds"]),
                     esc(("QUARANTINED by " + ", ".join(g["quarantined_by"])) if g["quarantined_by"] else ("fits now" if gid in fits else why.get(gid, ""))) + " " + esc("; ".join(d["upstream_flags"].get(gid, []))), "".join(acts)])
    out.append("<h2>Review groups (one task per exact duplicate group)</h2>" + table(["Group", "Claim", "Packets", "Contributors (all retained)", "Ancestry", "State", "Scheduling cost", "Assignee", "Observed s", "Plan / flags", "Actions"], rows)
               + f'<p class="muted">Unspent after this plan: {esc(d["plan"].get("unspent_after_plan"))} minute(s).</p>')
    out.append("<h2>Submit a packet that references a claim in this workspace</h2>" + need(h, "submit"))
    if can(h, "submit"):
        out.append(form(h, "/com/submit", field(h, "Claim id", "claim_id") + select(h, "Kind", "kind", ("SUMMARY", "PRIMARY")) + select(h, "Ancestry", "ancestry", ("KNOWN", "UNKNOWN")) + field(h, "Derived from (packet or source ids, space separated)", "derived_from")
                        + field(h, "Your packet id (optional)", "client_packet_id") + field(h, "Proposed minutes (a proposal only)", "proposed_cost_minutes", default="30") + '<p><label><input type="checkbox" name="asserts_withdrawn" value="1"> I assert the source was withdrawn (kept as an assertion; quarantines nothing)</label></p>', "Submit packet")
                   + "<h3>Intake from an SHD-admitted bundle</h3>" + form(h, "/com/intake", field(h, "SHD decision id (purpose com.packets)", "decision_id"), "Take the packets in"))
    if can(h, "review", "admin"):
        gsel = select(h, "Group", "group_id", sorted(s["groups"]))
        out.append("<h2>Reviewer and administrator actions</h2>" + form(h, "/com/cost", gsel + field(h, "Scheduling cost, minutes", "minutes") + field(h, "Estimation rule", "rule"), "Set the scheduling cost")
                   + form(h, "/com/effort", gsel + field(h, "Minutes", "minutes") + select(h, "Category", "category", commons.EFFORT_CATEGORIES), "Declare manual effort") + form(h, "/com/leases", "", "Return tasks with an expired lease to the queue")
                   + form(h, "/com/work", gsel + '<input type="hidden" name="action" value="cancel">' + field(h, "Reason", "note"), "Cancel a task")
                   + "<h3>Record a dispute, withdrawal or source correction (changes queue handling)</h3>" + form(h, "/com/dispute", select(h, "Target type", "target_type", ("source", "claim", "packet")) + field(h, "Target id", "target") + select(h, "Type", "dispute_type", ("DISPUTED", "WITHDRAWN", "SOURCE_CORRECTED")) + field(h, "Reason", "reason", rows=2), "Record"))
    out.append("<h2>Disputes</h2>" + table(["Id", "Target", "Type", "Reason", "By", "Appeals", "Resolution"], [[esc(x["dispute_id"]), esc(x["target_type"] + " " + x["target"]), esc(x["dispute_type"]), esc(x["reason"]), esc(x["recorded_by"]),
               "<br>".join(esc(a_["appellant"] + ": " + a_["reason"]) for a_ in x["appeals"]), esc((x["resolution"] or {}).get("outcome", "open")) + " " + esc((x["resolution"] or {}).get("reason", ""))] for x in s["disputes"].values()])
               + '<p class="muted">Quarantine is a handling state pending resolution. It is not a finding of plagiarism or misconduct.</p>')
    if getattr(h, "_principal", None) and s["disputes"]:
        out.append(form(h, "/com/appeal", select(h, "Dispute", "dispute_id", sorted(s["disputes"])) + field(h, "Reason", "reason", rows=2), "Appeal"))
    if can(h, "admin"):
        out.append("<h2>Administrator</h2>" + form(h, "/com/budget", field(h, "Period id", "period_id", default=cap.get("period_id") or "") + field(h, "Review minutes", "review_minutes", default=str(cap.get("review_minutes", 240))) + field(h, "Practice minutes (separate reserve)", "practice_minutes", default=str(cap.get("practice_minutes", 60)))
                   + field(h, "Contributor packet cap", "contributor_packet_cap", default=str(cap.get("contributor_packet_cap", 10))) + field(h, "Maximum open tasks", "max_open_tasks", default=str(cap.get("max_open_tasks", 200))), "Set or change the budget")
                   + form(h, "/com/urgent", select(h, "Group", "group_id", sorted(s["groups"])) + field(h, "Reason", "reason"), "Urgent override (orders first; creates no capacity)")
                   + (form(h, "/com/resolve", select(h, "Dispute", "dispute_id", sorted(s["disputes"])) + select(h, "Outcome", "outcome", ("LIFTED", "UPHELD")) + field(h, "Reason", "reason", rows=2), "Resolve dispute") if s["disputes"] else ""))
    sim = commons.simulate([{"key": k, "minutes": m} for k, m in (("A", 30), ("A", 30), ("B", 90), ("C", 20), ("A", 30), ("D", 25), ("C", 20), ("E", 15))], 120)
    out.append(f'<h2>Queue comparison — {esc(sim["label"])}</h2>' + table(["Rule", "Completed tasks", "Unique keys completed", "Minutes on duplicates", "Minutes unspent"],
               [[esc(n), esc(sim[k]["completed_tasks"]), esc(sim[k]["completed_unique_keys"]), esc(sim[k]["minutes_spent_on_duplicates"]), esc(sim[k]["minutes_unspent"])] for n, k in (("Plain FIFO", "plain_fifo"), ("FIFO + exact de-duplication", "fifo_exact_dedup"), ("This queue's rule", "commons_rule"))])
               + '<p class="muted">Eight fixed synthetic arrivals against 120 minutes. No human comparison has been run; the counters above are the instrumentation a future voluntary comparison would use.</p>')
    return "".join(out)


def page_com_group(h, gid: str) -> str:
    ws = h.server.ws; s = commons.state(ws); g = s["groups"].get(gid)
    if g is None:
        raise ModuleError("E_NOT_FOUND", "no such group")
    c = g["claim"]
    out = [f'<p>Claim <a href="/claim/{esc(urllib.parse.quote(c["claim_id"], safe=""))}"><code>{esc(c["claim_id"])}</code></a>, version digest <code>{esc(c["version_digest"][:16])}…</code>. Contract that decides compatibility: <code>{esc(json.dumps(c["contract"], sort_keys=True))}</code>.</p>',
           f'<p>Known source roots: {esc(", ".join(g["source_roots"]) or "none")} · unknown roots: {esc(", ".join(g["unknown_roots"]) or "none")} · ancestry <b>{esc(g["ancestry"])}</b>. Several packets over one root are one root.</p>',
           "<h2>Member packets (every contributor keeps its attribution)</h2>" + table(["Packet", "Submitter", "Kind", "Derived from", "Admission", "Proposed min", "Asserts withdrawn", "Recorded"],
           [[esc(pid), esc(s["packets"][pid]["submitter"]), esc(s["packets"][pid]["kind"]), esc(", ".join(s["packets"][pid]["derived_from"])), esc(s["packets"][pid]["admission"]["route"] + (" " + (s["packets"][pid]["admission"]["shd_decision_id"] or ""))),
             esc(s["packets"][pid]["proposed_cost_minutes"]), esc("yes (assertion only)" if s["packets"][pid]["submitter_asserts_withdrawn"] else "no"), esc(s["packets"][pid]["recorded_at"])] for pid in g["packets"]]),
           "<h2>Task history</h2>" + table(["At", "From", "To", "By", "Reserved min", "Reason"], [[esc(x["at"]), esc(x["from"]), esc(x["to"]), esc(x["by"]), esc(x["reservation_minutes"]), esc(x["reason"])] for x in g["history"]])]
    return "".join(out) + '<p><a href="/com">Back to COM</a></p>'


# ------------------------------------------------------------------ pages: PRC
def page_prc(h, q) -> str:
    ws = h.server.ws; s = practice.state(ws); p = getattr(h, "_principal", None); me = (p or {}).get("principal_id"); out = []
    out.append('<p>A bounded task: read the frozen evidence, commit a judgment and reasoning, then see the comparison and reflect. The comparison is held by the server and opens only after your attempt is committed. '
               'Declare assistance and earlier exposure truthfully — every answer is accepted; the session is labelled, never refused.</p>')
    mine = {x["task_id"] for x in s["sessions"].values() if x["practitioner"] == me}
    out.append("<h2>Tasks</h2>" + table(["Task", "Title", "Question", "Sources", "Minutes", "Comparison provenance", "Curator"], [[esc(t["task_id"]), esc(t["title"]), esc(t["question"]), esc(len(t["source_scope"])), esc(t["session_minutes"]),
               esc(t["comparison_provenance"]) + (" · packaged public example (a demonstration, not a confidential assessment)" if t["public_example"] else ""), esc(t["curator"]) + (f' — declares: {esc(t["declared_curator_qualification"])}' if t["declared_curator_qualification"] else "")] for t in s["tasks"].values()]))
    if can(h, "practice"):
        avail = [t for t in s["tasks"] if t not in mine and s["tasks"][t]["curator"] != me]
        due = practice.due_state(s, me)
        if due:
            out.append("<h2>Your follow-up tasks (local due-states)</h2>" + table(["Task", "Due", "State"], [[esc(f["followup_task_id"]), esc(f["due_at"]), f"<b>{esc(f['state'])}</b>"] for f in due]))
        out.append("<h2>Open a session</h2>" + (form(h, "/prc/open", select(h, "Task", "task_id", avail) + select(h, "Assistance during this session", "assistance", practice.ASSISTANCE) + field(h, "Assistance note (optional)", "assistance_note")
                   + select(h, "Have you seen an answer to this task before?", "prior_exposure", practice.EXPOSURE), "Open (draws on the practice reserve)") if avail else '<p class="muted">No task is open to you right now.</p>'))
    else:
        out.append("<h2>Open a session</h2>" + need(h, "practice"))
    rows = []
    for x in s["sessions"].values():
        visible = x["practitioner"] == me or can(h, "admin") or (can(h, "review") and x["attempt"] is not None)
        if visible:
            rows.append([f'<a href="/prc/session/{esc(x["session_id"])}">{esc(x["session_id"])}</a>', esc(x["task_id"]), esc(x["practitioner"]), f"<b>{esc(x['category'])}</b>", "committed " + esc(x["attempt"]["at"]) if x["attempt"] else "no attempt yet", esc(x["revealed_at"] or "closed")])
    out.append("<h2>Sessions you may see</h2>" + table(["Session", "Task", "Practitioner", "Category", "Attempt", "Comparison"], rows) + '<p class="muted">Participant records are private by default: a practitioner sees only its own sessions; a reviewer sees a session once its attempt is committed.</p>')
    if can(h, "review"):
        out.append("<h2>Freeze a task (curator)</h2>" + form(h, "/prc/task", field(h, "Title", "title") + field(h, "Question", "question", rows=3) + field(h, "Claim id (optional)", "claim_id") + field(h, "Source ids in scope (space separated)", "source_ids", rows=2)
                   + field(h, "Judgment labels (comma separated; UNRESOLVED is always offered)", "labels", default="IN_RANGE, OUT_OF_RANGE") + field(h, "Reference label", "reference_label") + field(h, "Reference answer (held by the server)", "reference_answer", rows=3)
                   + field(h, "Rationale", "rationale", rows=2) + select(h, "Comparison provenance", "provenance", tuple(practice.PROVENANCE)) + field(h, "Your declared qualification (recorded as declared, not verified)", "declared_curator_qualification")
                   + field(h, "Session minutes", "session_minutes", default="20") + field(h, "EVO version this task concerns (optional)", "evo_version_id") + '<p><label><input type="checkbox" name="public_example" value="1"> The answer is public (a demonstration task)</label></p>', "Freeze task")
                   + "<h3>Schedule a follow-up (a local due-state; nobody is contacted)</h3>" + form(h, "/prc/followup", select(h, "After session", "session_id", sorted(s["sessions"])) + select(h, "Follow-up task", "followup_task_id", sorted(s["tasks"])) + field(h, "Due at (UTC)", "due_at"), "Schedule"))
    if can(h, "admin"):
        out.append("<h2>Checkpoints (administrator)</h2><p>A signed statement of the journal's tip. Download it and keep it somewhere else: an export is later checked against the separately held copy.</p>"
                   + table(["#", "Issued", "Journal seq", "Download"], [[esc(i), esc(c["at"]), esc(c["checkpoint"]["body"]["journal_seq"]), f'<a href="/prc/checkpoint/{i}.json">checkpoint {i}</a>'] for i, c in enumerate(s["checkpoints"], start=1)]) + form(h, "/prc/checkpoint", "", "Issue a checkpoint now"))
    return "".join(out)


def page_prc_session(h, sid: str, q) -> str:
    ws = h.server.ws; v = practice.session_view(ws, h._principal, sid); ss, t = v["session"], v["task"]; mine = ss["practitioner"] == h._principal["principal_id"]; base = f"/prc/session/{sid}"
    out = [f'<p>Task <b>{esc(t["task_id"])}</b> — {esc(t["title"])}. Session category: <b>{esc(ss["category"])}</b> (assistance {esc(ss["declarations"]["assistance"])}, prior exposure {esc(ss["declarations"]["prior_exposure"])}; these are the practitioner\'s own declarations).</p>',
           f'<h2>Question</h2><div class="guide">{esc(t["question"])}</div>',
           "<h2>Frozen evidence in scope</h2><ul>" + "".join(f'<li><a href="{base}/source?id={esc(urllib.parse.quote(x["source_id"], safe=""))}">{esc(x["source_id"])}</a> <span class="muted">source hash {esc((x["source_hash"] or "")[:16])}…</span></li>' for x in t["source_scope"]) + "</ul>"
           + f'<p class="muted">Opened so far: {esc(", ".join(r["source_id"] for r in ss["reads"]) or "none")}. Opening a page shows access, not comprehension.</p>']
    if v["current_interpretation"]:
        out.append('<div class="notice"><b>Changed after this task was frozen</b> (the session and the attempt are not rewritten):<ul>' + "".join(f"<li>{esc(n)}</li>" for n in v["current_interpretation"]) + "</ul></div>")
    if v["attempt"] is None:
        if mine:
            refs = "".join(f'<label><input type="checkbox" name="ref_{esc(x["source_id"])}" value="1"> {esc(x["source_id"])}</label><br>' for x in t["source_scope"])
            out.append("<h2>Your attempt (committed once, never replaced)</h2>" + form(h, base + "/attempt", select(h, "Judgment", "judgment", t["labels"] + ["UNRESOLVED"]) + field(h, "Reasoning", "reasoning", rows=6) + f"<p>Sources the judgment rests on:<br>{refs}</p>"
                       + field(h, "If UNRESOLVED: what evidence would resolve it", "unresolved_note", rows=2), "Commit attempt") + '<p class="muted">The comparison stays closed until this is committed.</p>')
    else:
        a = v["attempt"]
        out.append(f'<h2>Attempt — committed {esc(a["committed_at"])}</h2><p>Judgment <b>{esc(a["judgment"])}</b>; rests on {esc(", ".join(a["source_refs"]))}.</p><div class="guide">{esc(a["reasoning"])}</div>' + (f'<p>Would resolve it: {esc(a["unresolved_note"])}</p>' if a["unresolved_note"] else ""))
        if v["comparison"] is None and mine:
            out.append("<h2>Comparison</h2>" + form(h, base + "/reveal", "", "Open the comparison"))
    if v["comparison"] is not None:
        c = v["comparison"]
        out.append(f'<h2>Comparison</h2><p>Provenance: <b>{esc(c["provenance"])}</b> — {esc(c["provenance_meaning"])}. Curator <code>{esc(c["curator"])}</code>.</p><p>Reference label <b>{esc(c["reference_label"])}</b>.</p><div class="guide">{esc(c["reference_answer"])}</div>'
                   + (f'<p>{esc(c["rationale"])}</p>' if c["rationale"] else "") + '<p class="muted">Agreement with a reference is not correctness, and neither is evidence of learning.</p>')
        out.append("<h2>Reflections</h2>" + "".join(f'<div class="guide">{esc(r["reflection"])}</div><p class="muted">{esc(r["at"])}</p>' for r in v["reflections"]) + (form(h, base + "/reflect", field(h, "Reflection (a separate later record)", "reflection", rows=4), "Record reflection") if mine else ""))
    if v["feedback"] or (can(h, "review") and not mine and v["attempt"] is not None):
        out.append("<h2>Reviewer feedback</h2>" + "".join(f'<div class="guide">{esc(x["feedback"])}</div><p class="muted">{esc(x["reviewer"])} · {esc(x["at"])}</p>' for x in v["feedback"])
                   + (form(h, base + "/feedback", field(h, "Feedback on this attempt (formative; not a ranking of a person)", "feedback", rows=4), "Record feedback") if can(h, "review") and not mine else ""))
    return "".join(out) + f'<p><a href="/prc">Back to Practice</a> · <a href="/modx">Export this session</a> (session id <code>{esc(sid)}</code>)</p>'


def page_prc_source(h, sid: str, q) -> str:
    r = practice.read_evidence(h.server.ws, h._principal, sid, q.get("id", ""))
    return (f'<p>Source <code>{esc(r["source_id"])}</code> · {esc(r["kind"])} {esc(r["form"] or "")} · available {esc(r["available_as_of"])}{" · fictional demonstration data" if r["fictional"] else ""}.</p><div class="guide">{esc(r["excerpt"])}</div>'
            f'<p class="muted">Shown as inert text exactly as registered.</p><p><a href="/prc/session/{esc(sid)}">Back to the session</a></p>')


# ------------------------------------------------------------------ pages: export and verification
def page_modx(h, q, result) -> str:
    ws = h.server.ws; p = getattr(h, "_principal", None); out = []
    if result is not None:
        cls = "ok" if result["result"] == "SUCCESS" else "bad"
        out.append(f'<h2>Result: <span class="{cls}">{esc(result["result"])}</span></h2>' + (f'<div class="err"><p>First discrepancy: {esc(result["first_discrepancy"])}</p></div>' if result["first_discrepancy"] else "")
                   + table(["Check", "Finding"], [["Integrity (independent of trust)", esc(json.dumps(result["integrity"]))], ["Recomputed views", esc(", ".join(result["recompute"]))], ["Trust (this receiver's own roots)", esc(json.dumps(result["trust"]))],
                                                   ["Freshness", esc(json.dumps(result["freshness"]))], ["Separately held checkpoint", esc(result["checkpoint"])], ["Discrepancies recorded", esc("; ".join(result["discrepancies"]) or "none")],
                                                   ["Imported into this workspace's state", "nothing — no claim, queue entry, role, key or policy is installed by verification"]]))
    if q.get("built"):
        out.append(f'<div class="notice">Built <a href="/modx/{esc(q["built"])}.zip"><code>{esc(q["built"])}.zip</code></a>.</div>')
    out.append("<h2>Build a packet</h2>")
    if p is None:
        out.append(need(h, "submit"))
    else:
        mods = "".join(f'<label><input type="checkbox" name="mod_{m}" value="1"> {m}</label> ' for m in ("SHD", "EVO", "COM")) if can(h, "submit", "review", "admin") else '<span class="muted">SHD, EVO and COM records need the submit, review or admin capability.</span>'
        out.append(form(h, "/modx/build", f"<p>{mods}</p>" + field(h, "Practice sessions to include (ids, space separated; your own, or any as administrator)", "prc_sessions")
                        + '<p><label><input type="checkbox" name="withhold_text" value="1"> Withhold attempt, reflection and feedback text (digests only)</label></p>', "Build packet")
                   + '<p class="muted">Never included: credential hashes, signing keys, staged bundle bytes, inspection excerpts, a comparison that was not revealed in the session, other practitioners\' sessions. No training dataset or ranking is produced.</p>')
    built = [e for e in ws.load()["events"] if e["kind"] == "MODULE_EXPORT_BUILT" and p and (e["payload"]["built_by"] == p["principal_id"] or "admin" in p["caps"])]
    out.append("<h2>Packets built here</h2>" + table(["Export", "Scope", "Events", "Objects", "By"], [[f'<a href="/modx/{esc(e["payload"]["export_id"])}.zip">{esc(e["payload"]["export_id"])}</a>', esc(json.dumps(e["payload"]["scope"])), esc(e["payload"]["events_included"]), esc(e["payload"]["objects_included"]), esc(e["payload"]["built_by"])] for e in built]))
    out.append("<h2>Verify a packet (works in a fresh workspace)</h2>" + form(h, "/modx/verify", '<p><label>Module packet</label> <input type="file" name="packet"></p><p><label>Separately held checkpoint (optional)</label> <input type="file" name="checkpoint"> '
               '<span class="muted">the JSON downloaded from the origin\'s Practice page and kept elsewhere — not a file from inside the packet</span></p>', "Verify", multipart=True))
    if can(h, "admin"):
        out.append("<h3>Resolve a recorded trust discrepancy (a note; trust changes only on the SHD trust page)</h3>" + form(h, "/modx/resolve", field(h, "Packet sha256", "packet_sha256") + field(h, "Resolution", "resolution", rows=2), "Record resolution"))
    return "".join(out)


def context_links(ws, claim_id: str | None = None) -> str:
    """A small block for the existing source and claim pages: where this object appears in the modules."""
    evs = ws.load()["events"]; cs = commons.state(ws, evs=evs); ps = practice.state(ws, evs=evs); es = evolution.state(ws, evs=evs)
    if claim_id:
        groups = [g["group_id"] for g in cs["groups"].values() if g["claim"]["claim_id"] == claim_id]; tasks = [t["task_id"] for t in ps["tasks"].values() if t["claim"] and t["claim"]["claim_id"] == claim_id]
        links = [c["version_id"] for c in es["commitments"] if c["claim_id"] == claim_id]
        return ('<section id="modules"><h2>In the modules</h2><p>COM review groups: ' + (", ".join(f'<a href="/com/group/{esc(g)}">{esc(g)}</a>' for g in groups) or "none") + " · PRC tasks: " + (esc(", ".join(tasks)) or "none")
                + " · EVO versions linked: " + (", ".join(f'<a href="/evo/version/{esc(v)}">{esc(v)}</a>' for v in links) or "none") + ' · <a href="/modules">Modules</a></p></section>')
    return '<p class="muted">Registered sources can be named by <a href="/com">COM packets</a>, put in the scope of a <a href="/prc">practice task</a>, and listed as evidence digests in an <a href="/shd">SHD bundle</a>. <a href="/modules">Modules</a></p>'
