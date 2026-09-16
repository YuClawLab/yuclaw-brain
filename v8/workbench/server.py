"""Local, owner-operated browser workbench — the seven steps behind ordinary HTML forms, no JavaScript at all.

Boundaries enforced by the server itself:
  * binds 127.0.0.1 only (a bind elsewhere is refused in code; network exposure needs its own authenticated design);
  * every request's Host header must name this loopback origin; every POST must carry a same-origin Origin header
    (and Sec-Fetch-Site same-origin/none when the browser sends it), the session cookie, and the CSRF token derived
    from it — otherwise 403 and nothing is written;
  * a strict Content-Security-Policy (no scripts, no remote resources), nosniff, no framing, same-origin-only referrer, no cache;
  * every value is HTML-escaped on output; source passages and imported packets are rendered as inert text and are
    never interpreted, executed or fetched;
  * the only filesystem paths touched are the workspace root (validated by the v7 store boundary), the export files
    it wrote (addressed by a validated id, never by a user path) and the bounded upload for verification (read in
    memory; nothing extracted to disk); no outbound network access exists in this module.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import re
import secrets
import sys
import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from v3.receipts.contracts import ContractError
from v8.workbench import NOT_ADVICE, calc, export, money, schema
from v8.workbench.store import StoreIntegrityError, Workspace, new_op_id

_REPO = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parent / "resources" / "fixtures"      # packaged copies of tests/fixtures/v8/commitments (identity tested)
FORM_LIMIT = 256 * 1024
UPLOAD_LIMIT = export.MAX_ZIP_BYTES + 64 * 1024
CSP = "default-src 'none'; img-src 'self'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
_CLAIM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_EXPORT_ID = re.compile(r"^exp-[0-9a-f]{16}$")
_FIXTURE = re.compile(r"^00[1-9]_[a-z_]+$")
_TS_INPUT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z?$")
STEPS = [("source", "1 Source"), ("claim", "2 Typed claim"), ("comparison", "3 Comparison"), ("calculation", "4 Calculation"), ("history", "5 History"), ("adjudication", "6 Adjudication"), ("export", "7 Reproducible export")]
CSS = """
body{font-family:system-ui,sans-serif;max-width:1100px;margin:1.5rem auto;padding:0 1rem;color:#1b1b1b;background:#fafafa;line-height:1.4}
h1,h2,h3{font-weight:600} h1{font-size:1.3rem} h2{font-size:1.1rem;margin-top:2rem;border-top:1px solid #ddd;padding-top:.8rem}
nav a{margin-right:.8rem} .steps{display:flex;gap:.4rem;flex-wrap:wrap;margin:.6rem 0} .steps span{border:1px solid #bbb;border-radius:4px;padding:.15rem .5rem;font-size:.85rem;background:#fff}
table{border-collapse:collapse;width:100%;font-size:.9rem;background:#fff} th,td{border:1px solid #ddd;padding:.3rem .5rem;text-align:left;vertical-align:top} th{background:#f1f1f1}
pre.excerpt{white-space:pre-wrap;background:#fff;border:1px solid #ccd;padding:.5rem;font-size:.9rem} code{background:#eee;padding:0 .2rem}
form.card{border:1px solid #ccc;background:#fff;padding:.8rem;margin:.8rem 0} label{display:block;margin:.35rem 0 .1rem;font-size:.85rem} input[type=text],input[type=date],textarea,select{width:100%;box-sizing:border-box;padding:.3rem;font:inherit}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.6rem} button{padding:.4rem .9rem;font:inherit;margin-top:.6rem}
.ok{color:#136f2e;font-weight:600} .bad{color:#a11;font-weight:600} .warn{color:#8a5a00;font-weight:600} .muted{color:#666;font-size:.85rem}
.notice{border-left:4px solid #8a5a00;background:#fff8e6;padding:.5rem .8rem;margin:.6rem 0} .err{border-left:4px solid #a11;background:#fff0f0;padding:.5rem .8rem;margin:.6rem 0}
footer{margin-top:3rem;font-size:.8rem;color:#555;border-top:1px solid #ddd;padding-top:.6rem}
"""


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def jesc(v) -> str:
    return esc(json.dumps(v, indent=1, sort_keys=True, ensure_ascii=False))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _norm_ts(v: str | None, field: str = "timestamp") -> str | None:
    """User-entered timestamps: 'YYYY-MM-DDTHH:MM[:SS][Z]' → RFC3339 Z. Empty → None."""
    if not v:
        return None
    v = v.strip()
    if not _TS_INPUT.match(v):
        raise ContractError(f"{field}: {v!r} is not a UTC timestamp; use YYYY-MM-DDTHH:MM:SSZ (an unknown availability stays unknown — it is never guessed)")
    if v.endswith("Z"):
        v = v[:-1]
    if len(v) == 16:
        v += ":00"
    return v + "Z"


class Multipart:
    """Minimal multipart/form-data reader (one file field + text fields), bounded by the caller."""
    def __init__(self, content_type: str, body: bytes):
        m = re.search(r'boundary="?([^";]+)"?', content_type)
        if not m:
            raise ContractError("multipart boundary missing")
        b = m.group(1).encode()
        self.fields: dict[str, str] = {}
        self.files: dict[str, tuple[str, bytes]] = {}
        for part in body.split(b"--" + b)[1:]:
            if part.startswith(b"--"):
                break
            head, _, data = part.partition(b"\r\n\r\n")
            data = data[:-2] if data.endswith(b"\r\n") else data
            hd = head.decode("latin-1")
            name = re.search(r'name="([^"]*)"', hd); fn = re.search(r'filename="([^"]*)"', hd)
            if not name:
                continue
            if fn:
                self.files[name.group(1)] = (Path(fn.group(1)).name, data)
            else:
                self.fields[name.group(1)] = data.decode("utf-8", "replace")


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, workspace, port: int, *, fixtures_dir: Path | None = None, candidate_commit: str | None = None, host: str = "127.0.0.1"):
        if host not in ("127.0.0.1", "::1"):
            raise ValueError("the workbench binds loopback only; network exposure requires an explicit authenticated deployment design")
        self.ws = Workspace(workspace)
        self.secret = secrets.token_bytes(32)
        self.fixtures_dir = Path(fixtures_dir or FIXTURES_DIR)
        self.candidate_commit = candidate_commit
        super().__init__((host, port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_address[1]}"
        self.allowed_hosts = {f"127.0.0.1:{self.server_address[1]}", f"localhost:{self.server_address[1]}"}
        self.allowed_origins = {f"http://{h}" for h in self.allowed_hosts}

    def csrf_for(self, session: str) -> str:
        return hmac.new(self.secret, session.encode(), hashlib.sha256).hexdigest()[:32]


class Handler(BaseHTTPRequestHandler):
    server_version = "YUCLAW-workbench/1"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ plumbing
    def log_message(self, fmt, *args):
        sys.stderr.write("[workbench] %s %s\n" % (self.address_string(), fmt % args))

    def _headers(self, status: int, ctype: str, length: int, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(length))
        self.send_header("Content-Security-Policy", CSP); self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY"); self.send_header("Referrer-Policy", "same-origin")   # no-referrer would make the browser send Origin: null on same-origin form posts (Fetch §4.1.1); self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin"); self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def _send(self, status: int, body: str | bytes, ctype="text/html; charset=utf-8", extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self._headers(status, ctype, len(data), extra)
        if self.command != "HEAD":
            self.wfile.write(data)

    def _text(self, status: int, msg: str):
        extra = None
        if status >= 400:
            # A refused request may leave an unread body on the socket; never let those bytes be parsed as the next
            # request. The header tells the client, the flag makes the handler loop stop after this response.
            self.close_connection = True; extra = {"Connection": "close"}
        self._send(status, msg + "\n", "text/plain; charset=utf-8", extra)

    def _redirect(self, location: str):
        self._headers(HTTPStatus.SEE_OTHER, "text/plain; charset=utf-8", 0, {"Location": location})

    def _session(self) -> tuple[str, bool]:
        c = self.headers.get("Cookie", "")
        for part in c.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "wb_session" and re.match(r"^[0-9a-f]{32}$", v):
                return v, False
        return secrets.token_hex(16), True

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in self.server.allowed_hosts

    def _post_guard(self) -> str | None:
        """Returns None when the POST is acceptable, else the refusal reason (nothing is written)."""
        if not self._host_ok():
            return "Host header is not this loopback origin"
        origin = self.headers.get("Origin")
        if origin is None or origin not in self.server.allowed_origins or origin.split("//", 1)[1] != self.headers.get("Host"):
            return "Origin header missing or not same-origin"
        sfs = self.headers.get("Sec-Fetch-Site")
        if sfs is not None and sfs not in ("same-origin", "none"):
            return f"Sec-Fetch-Site {sfs!r} refused"
        sess, fresh = self._session()
        if fresh:
            return "session cookie missing; open a page first"
        self._sess = sess
        return None

    def _read_body(self, limit: int) -> bytes | None:
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if n < 0 or n > limit:
            return None
        return self.rfile.read(n) if n else b""

    def _csrf_ok(self, form: dict) -> bool:
        return hmac.compare_digest(form.get("csrf", ""), self.server.csrf_for(self._sess))

    # ------------------------------------------------------------------ routing
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self._host_ok():
            return self._text(400, "refused: Host header is not this loopback origin")
        u = urllib.parse.urlsplit(self.path); path = u.path; q = {k: v[-1] for k, v in urllib.parse.parse_qs(u.query, keep_blank_values=True).items()}
        sess, fresh = self._session(); self._sess = sess
        extra = {"Set-Cookie": f"wb_session={sess}; Path=/; HttpOnly; SameSite=Strict"} if fresh else None
        try:
            if path == "/static/style.css":
                return self._send(200, CSS, "text/css; charset=utf-8")
            torn = self.server.ws.load()["torn_tail"]           # a chain failure raises here and is handled below
            if torn:
                # Reads are not served over a torn tail: the durable events are intact, but the workspace needs the
                # operator's recovery decision first, so every page is the integrity page with the recovery form.
                raise StoreIntegrityError("E_TORN_TAIL", f"{torn['bytes']} byte(s) after the last newline (sha256 {torn['sha256'][:16]}…); an interrupted append left a torn tail; run recovery before reading or writing (nothing durable is lost)")
            if path == "/":
                return self._send(200, self.page_home(q), extra=extra)
            if path == "/source":
                return self._send(200, self.page_source(q), extra=extra)
            if path == "/claim/new":
                return self._send(200, self.page_claim_new(q), extra=extra)
            m = re.match(r"^/claim/([^/]+)$", path)
            if m:
                cid = urllib.parse.unquote(m.group(1))
                if not _CLAIM_ID.match(cid):
                    return self._text(404, "no such claim")
                return self._send(200, self.page_claim(cid, q), extra=extra)
            m = re.match(r"^/exports/(exp-[0-9a-f]{16})\.zip$", path)
            if m:
                p = self.server.ws.exports / f"{m.group(1)}.zip"
                if not p.is_file():
                    return self._text(404, "no such export")
                data = p.read_bytes()
                return self._send(200, data, "application/zip", {"Content-Disposition": f'attachment; filename="{m.group(1)}.zip"'})
            if path == "/verify":
                return self._send(200, self.page_verify(q, None), extra=extra)
            if path == "/journal":
                return self._send(200, self.page_journal(q), extra=extra)
            return self._text(404, "not found")
        except StoreIntegrityError as exc:
            return self._send(200, self.page_integrity(exc), extra=extra)

    def do_POST(self):
        why = self._post_guard()
        if why:
            self._read_body(UPLOAD_LIMIT)
            return self._text(403, f"refused: {why}; nothing was written")
        path = urllib.parse.urlsplit(self.path).path
        if path == "/verify":
            return self.post_verify()
        form = self._form()
        if form is None:
            return self._text(413 if self.headers.get("Content-Length", "0").isdigit() and int(self.headers.get("Content-Length", "0")) > FORM_LIMIT else 400, "refused: form body missing, too large or not urlencoded")
        if not self._csrf_ok(form):
            return self._text(403, "refused: CSRF token invalid; nothing was written")
        op_id = form.get("op_id", "")
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$", op_id):
            return self._text(400, "refused: operation identifier missing")
        try:
            if path == "/source/register":
                return self.post_source(form, op_id)
            if path == "/claim/freeze":
                return self.post_freeze(form, op_id)
            m = re.match(r"^/claim/([^/]+)/(amend|outcome|adjudicate|export)$", path)
            if m:
                cid = urllib.parse.unquote(m.group(1))
                if not _CLAIM_ID.match(cid):
                    return self._text(404, "no such claim")
                return getattr(self, "post_" + m.group(2))(cid, form, op_id)
            if path == "/fixtures/load":
                return self.post_fixture(form, op_id)
            if path == "/recover":
                r = self.server.ws.recover()
                return self._redirect("/?recovered=" + ("1" if r["recovered"] else "0"))
            return self._text(404, "not found")
        except StoreIntegrityError as exc:
            return self._send(200, self.page_integrity(exc))
        except ContractError as exc:
            return self._send(422, self.page_error(str(exc), form))

    # ------------------------------------------------------------------ building blocks
    def _csrf_field(self) -> str:
        return f'<input type="hidden" name="csrf" value="{esc(self.server.csrf_for(self._sess))}"><input type="hidden" name="op_id" value="{esc(new_op_id("ui"))}">'

    def page(self, title: str, body: str, *, claim_id: str | None = None) -> str:
        ws = self.server.ws; st = ws.status()
        integ = st["integrity"]
        cls = "ok" if integ == "OK" else "bad"
        steps = "".join(f'<span>{esc(lbl)}</span>' for _, lbl in STEPS)
        cand = self.server.candidate_commit or "not recorded"
        return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{esc(title)} — YUCLAW workbench</title><link rel="stylesheet" href="/static/style.css"></head><body>
<p class="muted"><b>Research &amp; education only. Not investment advice.</b> Local workbench bound to 127.0.0.1. Nothing here publishes.</p>
<nav><a href="/">Workspace</a><a href="/source">1 Source</a><a href="/claim/new">2 Typed claim</a><a href="/verify">Verify an export (fresh workspace)</a><a href="/journal">Journal</a></nav>
<div class="steps">{steps}</div>
<h1>{esc(title)}</h1>
{body}
<footer>Workspace <code>{esc(st['workspace_id'])}</code> · events {esc(st.get('events'))} · integrity <span class="{cls}">{esc(integ)}</span> · candidate commit <code>{esc(cand)}</code> · {esc(NOT_ADVICE)}</footer></body></html>"""

    def page_error(self, msg: str, form: dict | None = None) -> str:
        reasons = [r.strip() for r in msg.split(":", 1)[-1].split(";")] if ";" in msg else [msg]
        items = "".join(f"<li>{esc(r)}</li>" for r in reasons)
        return self.page("Blocked — nothing was written", f'<div class="err"><p><b>{esc(msg.split(":", 1)[0] if ";" in msg else "Refused")}</b></p><ul>{items}</ul></div><p><a href="/">Back to the workspace</a> · use the browser Back button to correct the form (the operation identifier is reused, so a corrected resubmission cannot duplicate anything).</p>')

    def page_integrity(self, exc: StoreIntegrityError) -> str:
        body = f'<div class="err"><p><b>{esc(exc.code)}</b>: {esc(str(exc))}</p></div>'
        if exc.code == "E_TORN_TAIL":
            body += f'<form class="card" method="post" action="/recover">{self._csrf_field()}<p>An interrupted append left bytes without a terminating newline. Recovery preserves those bytes in a side file, truncates only them, and records a RECOVERY event. No durable event is changed.</p><button type="submit">Run recovery</button></form>'
        else:
            body += "<p>The log fails its chain check. The workspace refuses to serve or write until a person inspects the file; nothing is repaired automatically.</p>"
        return self.page("Workspace integrity", body)

    def _sources(self):
        return [e["payload"] for e in self.server.ws.events() if e["kind"] == "SOURCE_REGISTERED"]

    def _source_select(self, name="source_id") -> str:
        opts = "".join(f'<option value="{esc(s["source_id"])}">{esc(s["source"]["accession"])} · {esc(s["source"]["form"])} · filed {esc(s["source"]["filed_at"])} · available {esc(s["source"]["available_as_of"])} · {esc(s["source"]["rights"])}</option>' for s in self._sources())
        return f'<label>Registered source (step 1)</label><select name="{name}" required><option value="">— choose a registered source —</option>{opts}</select>'

    def _source_by_id(self, sid: str) -> dict:
        for s in self._sources():
            if s["source_id"] == sid:
                return s["source"]
        raise ContractError("source_id: choose a registered source first (step 1); an unregistered passage cannot back a claim")

    def _period_fields(self, prefix="fp_", p: dict | None = None) -> str:
        p = p or {}
        opts = "".join(f'<option value="{t}"{" selected" if p.get("type") == t else ""}>{t}</option>' for t in schema.PERIOD_TYPES)
        return f'<div class="row"><div><label>Fiscal period label</label><input type="text" name="{prefix}label" value="{esc(p.get("label", ""))}" placeholder="FY2026 or Q3 FY2026"></div><div><label>Period type</label><select name="{prefix}type"><option value="">—</option>{opts}</select></div><div><label>Period start</label><input type="date" name="{prefix}start" value="{esc(p.get("start", ""))}"></div><div><label>Period end</label><input type="date" name="{prefix}end" value="{esc(p.get("end", ""))}"></div></div>'

    def _period_from(self, form: dict, prefix="fp_"):
        return {"label": form.get(prefix + "label", ""), "type": form.get(prefix + "type", ""), "start": form.get(prefix + "start", ""), "end": form.get(prefix + "end", "")}

    @staticmethod
    def _sel(name, options, current=None, blank=True):
        o = ('<option value="">—</option>' if blank else "") + "".join(f'<option value="{esc(v)}"{" selected" if v == current else ""}>{esc(v)}</option>' for v in options)
        return f'<select name="{name}">{o}</select>'

    def _times(self, t: dict) -> str:
        return f'<span class="muted">source available {esc(t.get("source_available_as_of") or "—")} · observed {esc(t.get("observed_at"))} · recorded {esc(t.get("recorded_at"))}</span>'

    # ------------------------------------------------------------------ pages
    def page_home(self, q) -> str:
        ws = self.server.ws; st = ws.status()
        rows = ""
        for cid in st["claims"]:
            s = ws.claim_state(cid)
            res = calc.adjudicate(s)["result"] if s else "—"
            rows += f'<tr><td><a href="/claim/{esc(urllib.parse.quote(cid, safe=""))}">{esc(cid)}</a></td><td>{esc(len(s["versions"]))}</td><td>{esc("yes" if s["withdrawn"] else "no")}</td><td>{esc("yes" if s["outcome"] else "no")}</td><td>{esc(res)}</td><td>{esc(len(s["adjudications"]))}</td><td>{esc(len(s["exports"]))}</td></tr>'
        fx = sorted(p.stem for p in self.server.fixtures_dir.glob("00*_*.json")) if self.server.fixtures_dir.is_dir() else []
        fxo = "".join(f'<option value="{esc(f)}">{esc(f)}</option>' for f in fx)
        notice = '<div class="notice">Recovery completed; the torn bytes are preserved in a side file and a RECOVERY event was recorded.</div>' if q.get("recovered") == "1" else ""
        body = f"""{notice}<p>Trace one financial commitment from an exact source through revision, numerical checks, outcome review and an export another researcher can verify. Start at <a href="/source">step 1</a>, or verify a packet from another workspace under <a href="/verify">Verify an export</a>.</p>
<h2>Claims in this workspace</h2><table><tr><th>claim</th><th>versions</th><th>withdrawn</th><th>outcome</th><th>computed result</th><th>adjudications</th><th>exports</th></tr>{rows or '<tr><td colspan="7" class="muted">none yet</td></tr>'}</table>
<h2>Load a fictional fixture (demonstration data)</h2><form class="card" method="post" action="/fixtures/load">{self._csrf_field()}<label>Fixture</label><select name="fixture">{fxo}</select><p class="muted">Loads the fixture's sources, claim, revisions and outcome as events with fixture-derived operation identifiers (idempotent). Fixture data is a demonstration, never a validated dataset product.</p><button type="submit">Load fixture</button></form>
<h2>Workspace</h2><pre class="excerpt">{jesc(st)}</pre>"""
        return self.page("Workspace", body)

    def page_source(self, q) -> str:
        as_of = q.get("as_of") or ""
        try:
            cut = _norm_ts(as_of, "as_of")
        except ContractError as exc:
            cut = None; as_of_err = str(exc)
        else:
            as_of_err = None
        evs = [e for e in self.server.ws.events(None, cut) if e["kind"] == "SOURCE_REGISTERED"]
        hidden = len([e for e in self.server.ws.events() if e["kind"] == "SOURCE_REGISTERED"]) - len(evs)
        rows = "".join(f'<tr><td><code>{esc(e["payload"]["source_id"])}</code></td><td>{esc(e["payload"]["source"]["accession"])}<br>{esc(e["payload"]["source"]["form"])}</td><td>{esc(e["payload"]["source"]["filed_at"])}</td><td><b>{esc(e["payload"]["source"]["available_as_of"])}</b></td><td>{esc(e["time"]["observed_at"])}</td><td>{esc(e["time"]["recorded_at"])}</td><td>{esc(e["payload"]["source"]["rights"])}{" · fictional" if e["payload"]["source"]["fictional"] else ""}</td><td><pre class="excerpt">{esc(e["payload"]["source"]["excerpt"])}</pre><span class="muted">sha256 {esc(e["payload"]["source"]["source_hash"])}</span></td></tr>' for e in evs)
        kinds = self._sel("kind", schema.SOURCE_KINDS, "filing", blank=False); rights = self._sel("rights", schema.RIGHTS, "FICTIONAL", blank=False)
        body = f"""<p>Register the exact passage a claim, an amendment or an outcome comes from. The availability timestamp is when the source became public (EDGAR acceptance), never the time you entered it; the workbench records the observation and action times separately. Passages are stored and shown as inert text.</p>
<form class="card" method="get" action="/source"><label>View the sources as they were available at a cutoff (UTC, e.g. 2026-03-01T00:00:00Z) — later sources are hidden, not backdated</label><input type="text" name="as_of" value="{esc(as_of)}"><button type="submit">Apply cutoff</button></form>
{f'<div class="err">{esc(as_of_err)}</div>' if as_of_err else ''}{f'<div class="notice">As-of view at <b>{esc(cut)}</b>: {hidden} source(s) with a later availability are hidden.</div>' if cut else ''}
<table><tr><th>source id</th><th>accession · form</th><th>filed</th><th>available as of (source)</th><th>observed (workspace)</th><th>recorded (local action)</th><th>rights</th><th>passage</th></tr>{rows or '<tr><td colspan="8" class="muted">no sources registered</td></tr>'}</table>
<h2>Register a source</h2><form class="card" method="post" action="/source/register">{self._csrf_field()}
<div class="row"><div><label>Kind</label>{kinds}</div><div><label>Form</label><input type="text" name="form" placeholder="8-K EX-99.1"></div><div><label>Accession (EDGAR) or publisher id (PREFIX:publisher:id) for a non-filing</label><input type="text" name="accession"></div><div><label>URL (optional)</label><input type="text" name="url"></div></div>
<div class="row"><div><label>Filed at (date)</label><input type="date" name="filed_at"></div><div><label>Available as of (UTC, YYYY-MM-DDTHH:MM:SSZ)</label><input type="text" name="available_as_of"></div><div><label>Observed at (UTC, optional; default now)</label><input type="text" name="observed_at"></div><div><label>Rights</label>{rights}</div></div>
<label>Exact passage (excerpt)</label><textarea name="excerpt" rows="3"></textarea>
<label><input type="checkbox" name="fictional" value="1" checked> Fictional source (demonstration data)</label>
<button type="submit">Register source</button></form>"""
        return self.page("Step 1 — Source", body)

    def page_claim_new(self, q) -> str:
        scales = self._sel("scale_as_stated", money.SCALES, "millions", blank=False); bases = self._sel("basis", schema.BASES); rules = self._sel("resolution_rule", list(schema.RESOLUTION_RULES))
        body = f"""<p>Freeze a fully specified commitment. Every comparability field is mandatory; a missing fiscal period, currency, basis or resolution rule blocks the freeze and every reason is listed. An amendment later creates a new version; the frozen original is never rewritten.</p>
<form class="card" method="post" action="/claim/freeze">{self._csrf_field()}
<div class="row"><div><label>Claim id</label><input type="text" name="claim_id" placeholder="ZZFX-FY2026-REV-GUIDE"></div><div><label>Issuer name</label><input type="text" name="issuer_name"></div><div><label>Ticker</label><input type="text" name="issuer_ticker"></div><div><label>CIK (10 digits)</label><input type="text" name="issuer_cik"></div></div>
<div class="row"><div><label>Metric</label><input type="text" name="metric" value="revenue"></div><div><label>Range low (in units, exact)</label><input type="text" name="range_low"></div><div><label>Range high (in units, exact)</label><input type="text" name="range_high"></div><div><label>Scale as stated in the source</label>{scales}</div></div>
<div class="row"><div><label>Currency (ISO-4217)</label><input type="text" name="currency" value="USD"></div><div><label>Measurement unit (= currency for money)</label><input type="text" name="unit" value="USD"></div><div><label>Accounting basis</label>{bases}</div><div><label>Resolution rule</label>{rules}</div></div>
{self._period_fields()}
<label>Statement (as made)</label><textarea name="statement" rows="2"></textarea>
{self._source_select()}
<label><input type="checkbox" name="fictional" value="1" checked> Fictional claim (demonstration data)</label>
<button type="submit">Save and freeze claim</button></form>"""
        return self.page("Step 2 — Typed claim", body)

    def page_claim(self, cid: str, q) -> str:
        ws = self.server.ws
        as_of_raw = q.get("as_of") or ""
        as_of_err = None
        try:
            cut = _norm_ts(as_of_raw, "as_of")
        except ContractError as exc:
            cut, as_of_err = None, str(exc)
        full = ws.claim_state(cid)
        if full is None:
            return self.page("No such claim", '<div class="err">This claim is not frozen in this workspace.</div>')
        st = ws.claim_state(cid, cut) if cut else full
        if st is None:
            return self.page(cid, f'<div class="notice">As-of <b>{esc(cut)}</b>: nothing about this claim was available yet (its first source became available {esc(full["versions"][0]["claim"]["source"]["available_as_of"])}).</div><p><a href="/claim/{esc(urllib.parse.quote(cid, safe=""))}">Back to the current view</a></p>')
        res = calc.adjudicate(st)
        orig_eff = next((v for v in reversed(st["versions"]) if v["type"] == "CORRECTED_SOURCE"), st["versions"][0])
        revised = [v for v in st["versions"] if v["type"] == "REVISED"]
        cmp = calc.compare_versions(orig_eff["claim"], revised[-1]["claim"]) if revised else None
        cq = urllib.parse.quote(cid, safe="")
        # --- 1 source (the registration's observation time is the workspace's first sight of the passage; the event
        #     times beside it are those of the claim action that cites it — kept apart, never merged)
        src_seen = {e["payload"]["source_id"]: e["time"]["observed_at"] for e in ws.events() if e["kind"] == "SOURCE_REGISTERED"}
        def times_with_source(t: dict, s: dict) -> str:
            sid = s["accession"] + ":" + s["source_hash"][:16]
            return f'{self._times(t)}<br><span class="muted">source observed {esc(src_seen.get(sid) or "—")}</span>'
        src_rows = ""
        for v in st["versions"]:
            s = v["claim"]["source"]
            src_rows += f'<tr><td>{esc(v["version_id"])} {esc(v["type"])}</td><td>{esc(s["accession"])} · {esc(s["form"])}</td><td>{esc(s["filed_at"])}</td><td><b>{esc(s["available_as_of"])}</b></td><td>{times_with_source(v["time"], s)}</td><td><pre class="excerpt">{esc(s["excerpt"])}</pre><span class="muted">sha256 {esc(s["source_hash"])} · rights {esc(s["rights"])}</span></td></tr>'
        if st["withdrawn"]:
            s = st["withdrawn"]["source"]; src_rows += f'<tr><td>{esc(st["withdrawn"]["revision_id"])} WITHDRAWN</td><td>{esc(s["accession"])} · {esc(s["form"])}</td><td>{esc(s["filed_at"])}</td><td><b>{esc(s["available_as_of"])}</b></td><td>{times_with_source(st["withdrawn"]["time"], s)}</td><td><pre class="excerpt">{esc(s["excerpt"])}</pre></td></tr>'
        if st["outcome"]:
            s = st["outcome"]["source"]; src_rows += f'<tr><td>OUTCOME</td><td>{esc(s["accession"])} · {esc(s["form"])}</td><td>{esc(s["filed_at"])}</td><td><b>{esc(s["available_as_of"])}</b></td><td>{times_with_source(st["outcome"]["_time"], s)}</td><td><pre class="excerpt">{esc(s["excerpt"])}</pre><span class="muted">sha256 {esc(s["source_hash"])}</span></td></tr>'
        # --- 2 versions
        ver_rows = "".join(f'<tr><td><b>{esc(v["version_id"])}</b><br>{esc(v["type"])}</td><td>{esc(v["claim"]["range"]["low"])} – {esc(v["claim"]["range"]["high"])} {esc(v["claim"]["unit"])}<br><span class="muted">({esc(money.as_stated(money.parse_amount(v["claim"]["range"]["low"]), v["claim"]["scale_as_stated"]))} – {esc(money.as_stated(money.parse_amount(v["claim"]["range"]["high"]), v["claim"]["scale_as_stated"]))})</span></td><td>{esc(v["claim"]["currency"])} / {esc(v["claim"]["unit"])}</td><td>{esc(v["claim"]["basis"])}</td><td>{esc(v["claim"]["fiscal_period"]["label"])} ({esc(v["claim"]["fiscal_period"]["type"])} {esc(v["claim"]["fiscal_period"]["start"])}..{esc(v["claim"]["fiscal_period"]["end"])})</td><td>{esc(v["claim"]["resolution_rule"])}</td><td>{esc(v["claim"]["stated_at"])}</td><td><code>{esc(v["claim"]["_digest"][:16])}…</code>{"<br><span class=muted>supersedes " + esc(v.get("supersedes", "")[:16]) + "…</span>" if v.get("supersedes") else ""}</td><td>{esc(v.get("reason") or "")}</td></tr>' for v in st["versions"])
        # --- 3 comparison
        if cmp is None:
            cmp_html = '<p class="muted">No revision yet: nothing to compare.</p>'
        elif cmp["comparable"]:
            notes = revised[-1].get("notes") or {}
            cmp_html = f'<table><tr><th></th><th>original ({esc(orig_eff["version_id"])})</th><th>revised ({esc(revised[-1]["version_id"])})</th><th>delta (revised − original)</th></tr><tr><td>low</td><td>{esc(cmp["a"]["range"]["low"])}</td><td>{esc(cmp["b"]["range"]["low"])}</td><td>{esc(cmp["low_delta"])}</td></tr><tr><td>high</td><td>{esc(cmp["a"]["range"]["high"])}</td><td>{esc(cmp["b"]["range"]["high"])}</td><td>{esc(cmp["high_delta"])}</td></tr><tr><td>midpoint delta</td><td colspan="3">{esc(cmp["midpoint_delta"])} {esc(cmp["unit"])}</td></tr><tr><td>width</td><td>{esc(cmp["width_a"])}</td><td>{esc(cmp["width_b"])}</td><td>{esc(cmp["width_delta"])}</td></tr><tr><td>overlap</td><td colspan="3">{esc(cmp["overlap"])}</td></tr><tr><td>direction</td><td colspan="3"><b>{esc(cmp["direction"])}</b> · metrics comparable: <span class="ok">COMPARABLE</span></td></tr></table><p><b>Unresolved explanation:</b> {esc(notes.get("explanation_unresolved") or "—")}<br><b>Next evidence:</b> {esc(notes.get("next_evidence") or "—")}<br>{f"<b class=warn>Source discrepancy (preserved verbatim, not corrected):</b> {esc(notes.get('source_discrepancy'))}<br>" if notes.get("source_discrepancy") else ""}<span class="muted">{esc(cmp["note"])}</span></p>'
        else:
            cmp_html = f'<p class="bad">INCOMPARABLE</p><ul>{"".join(f"<li>{esc(r["reason"])}</li>" for r in cmp["reasons"])}</ul><p class="muted">A metric or accounting-basis change yields INCOMPARABLE; no delta is computed.</p>'
        # --- 4 calculation
        def ev_html(e, title):
            if e is None:
                return ""
            cls = "ok" if e["result"] == "IN_RANGE" else "bad" if e["result"] == "OUT_OF_RANGE" else "warn"
            rs = "".join(f'<li>{esc(r["code"])}: {esc(r["reason"])}</li>' for r in e["reasons"])
            return f'<div class="card"><h3>{esc(title)} — <span class="{cls}">{esc(e["result"])}</span></h3><table><tr><th>inputs</th><td>low {esc(e["inputs"]["low"])} · high {esc(e["inputs"]["high"])} · actual {esc(e["inputs"]["actual"])} · {esc(e["inputs"]["currency"])}/{esc(e["inputs"]["unit"])} · {esc(e["inputs"]["basis"])} · {esc(e["inputs"]["fiscal_period"]["label"])} · {esc(e["inputs"]["metric"])}</td></tr><tr><th>formula</th><td>{esc(e["formula"])}</td></tr><tr><th>midpoint</th><td>{esc(e.get("midpoint"))}</td></tr><tr><th>delta vs midpoint</th><td>{esc(e.get("delta_vs_midpoint"))}</td></tr><tr><th>distance outside</th><td>{esc(e.get("distance_outside"))}</td></tr><tr><th>source links</th><td>claim {esc(e["source_links"]["claim_source"])} · outcome {esc(e["source_links"]["outcome_source"])}</td></tr>{f"<tr><th>reasons</th><td><ul>{rs}</ul></td></tr>" if rs else ""}</table></div>'
        calc_html = f'<p>Overall: <b class="{"ok" if res["result"] == "IN_RANGE" else "bad" if res["result"] == "OUT_OF_RANGE" else "warn"}">{esc(res["result"])}</b> · comparison permitted: {esc(res["comparison_permitted"])} · rule {esc(res["rule"])}</p>{"".join(f"<div class=err>{esc(r["code"])}: {esc(r["reason"])}</div>" for r in res["reasons"])}{ev_html(res["original"], "Original range" + (" (corrected source)" if res["uses_corrected_range"] else ""))}{ev_html(res["revised"], "Revised range")}<p class="notice">{esc(res["no_inference"])}</p>'
        # --- 5 history
        hidden = len(full["events"]) - len(st["events"])
        hist_rows = "".join(f'<tr><td>{esc(e["seq"])}</td><td>{esc(e["kind"])}</td><td>{esc(e["payload"].get("version_id") or e["payload"].get("export_id") or e["payload"].get("label") or "")}</td><td><b>{esc(e["time"]["source_available_as_of"] or "—")}</b></td><td>{esc(e["time"]["observed_at"])}</td><td>{esc(e["time"]["recorded_at"])}</td><td><code>{esc(e["event_hash"][:16])}…</code></td><td><code>{esc(e["op_id"])}</code></td></tr>' for e in st["events"])
        hist_html = f"""<form class="card" method="get" action="/claim/{esc(cq)}"><label>Replay as of a cutoff (UTC). Events whose source became available later are hidden; later information never rewrites the original claim or an earlier as-of result.</label><input type="text" name="as_of" value="{esc(as_of_raw)}" placeholder="2026-03-01T00:00:00Z"><button type="submit">Replay</button> <a href="/claim/{esc(cq)}">current view</a></form>
{f'<div class="err">{esc(as_of_err)}</div>' if as_of_err else ''}{f'<div class="notice">As-of view at <b>{esc(cut)}</b>: {hidden} later event(s) hidden. Result at this cutoff: <b>{esc(res["result"])}</b>; versions visible: {esc(", ".join(v["version_id"] for v in st["versions"]))}.</div>' if cut else ''}
<table><tr><th>seq</th><th>event</th><th>ref</th><th>source available as of</th><th>observed (workspace)</th><th>recorded (local action)</th><th>event hash</th><th>operation id</th></tr>{hist_rows}</table>"""
        # --- 6 adjudication
        adj_rows = "".join(f'<tr><td>{esc(a["reviewer"])}</td><td>{esc(a["rule"])}</td><td><b>{esc(a["label"])}</b>{" <span class=warn>DISPUTED</span>" if a["disputed"] else ""}</td><td>{esc(a["computed_result"])}</td><td>{esc(a["reason"])}</td><td>{esc(a["conflicts"] or "—")}</td><td>{"".join(f"<code>{esc(h[:12])}…</code> " for h in a["evidence"])}</td><td>{esc(a["time"]["recorded_at"])}</td></tr>' for a in st["adjudications"])
        ev_opts = "".join(f'<label><input type="checkbox" name="evidence" value="{esc(e["event_hash"])}"> {esc(e["seq"])} {esc(e["kind"])} <code>{esc(e["event_hash"][:12])}…</code></label>' for e in full["events"] if e["kind"] != "ADJUDICATION_RECORDED")
        labels = self._sel("label", calc.RESULTS, res["result"], blank=False)
        adj_form = f"""<form class="card" method="post" action="/claim/{esc(cq)}/adjudicate">{self._csrf_field()}<div class="row"><div><label>Reviewer identity</label><input type="text" name="reviewer"></div><div><label>Rule applied</label><input type="text" name="rule" value="{esc(res["rule"])}"></div><div><label>Label (computed: {esc(res["result"])})</label>{labels}</div></div><label>Evidence (events relied on)</label>{ev_opts}<label>Reason</label><textarea name="reason" rows="2"></textarea><label>Conflicts (who disagrees and why; kept visible)</label><input type="text" name="conflicts"><label><input type="checkbox" name="disputed" value="1"> Disputed — my label differs from the computed result and I explain why (a differing label without this flag is refused)</label><button type="submit">Record adjudication</button></form>"""
        # --- amendments / outcome forms
        bases = self._sel("basis", schema.BASES, st["current"]["claim"]["basis"]); types = self._sel("amend_type", ("REVISED", "WITHDRAWN", "CORRECTED_SOURCE"), "REVISED", blank=False)
        cur = st["current"]["claim"]
        amend_form = "" if full["withdrawn"] else f"""<form class="card" method="post" action="/claim/{esc(cq)}/amend">{self._csrf_field()}<h3>Create an amendment</h3><div class="row"><div><label>Type</label>{types}</div><div><label>New range low</label><input type="text" name="range_low" value="{esc(cur["range"]["low"])}"></div><div><label>New range high</label><input type="text" name="range_high" value="{esc(cur["range"]["high"])}"></div><div><label>Basis</label>{bases}</div></div><div class="row"><div><label>Currency</label><input type="text" name="currency" value="{esc(cur["currency"])}"></div><div><label>Unit</label><input type="text" name="unit" value="{esc(cur["unit"])}"></div><div><label>Metric</label><input type="text" name="metric" value="{esc(cur["metric"])}"></div></div>{self._period_fields("fp_", cur["fiscal_period"])}<label>Statement (optional; keeps the current one when empty)</label><input type="text" name="statement"><label>Reason (required)</label><input type="text" name="reason">{self._source_select()}<label>Unresolved explanation (a note, not causal proof)</label><input type="text" name="explanation_unresolved"><label>Next evidence needed</label><input type="text" name="next_evidence"><label>Source discrepancy (verbatim; e.g. the amendment restates the prior range differently from the original — preserved, never corrected)</label><input type="text" name="source_discrepancy"><button type="submit">Record amendment</button></form>"""
        out_form = f"""<form class="card" method="post" action="/claim/{esc(cq)}/outcome">{self._csrf_field()}<h3>Record the disclosed outcome</h3><div class="row"><div><label>Actual (in units, exact)</label><input type="text" name="actual"></div><div><label>Currency</label><input type="text" name="currency" value="{esc(cur["currency"])}"></div><div><label>Unit</label><input type="text" name="unit" value="{esc(cur["unit"])}"></div><div><label>Basis</label>{self._sel("basis", schema.BASES, cur["basis"])}</div><div><label>Metric</label><input type="text" name="metric" value="{esc(cur["metric"])}"></div></div>{self._period_fields("fp_", cur["fiscal_period"])}{self._source_select()}<label><input type="checkbox" name="comparable" value="1" checked> Recorder declares the outcome comparable (the calculator re-checks every field regardless)</label><button type="submit">Record outcome</button></form>"""
        # --- 7 export
        exp_rows = "".join(f'<tr><td><a href="/exports/{esc(x["export_id"])}.zip">{esc(x["export_id"])}.zip</a></td><td><code>{esc(x["canonical_digest"])}</code></td><td><code>{esc(x["zip_sha256"][:16])}…</code></td><td>{esc(x["time"]["recorded_at"])}</td></tr>' for x in full["exports"])
        built = q.get("built")
        exp_notice = f'<div class="notice">Export <b>{esc(built)}</b> built. Download it below and verify it in a <b>fresh</b> workspace (Verify an export).</div>' if built and _EXPORT_ID.match(built) else ""
        pe = export.publication_eligibility(export.build_canonical(full))
        exp_html = f"""{exp_notice}<form class="card" method="post" action="/claim/{esc(cq)}/export">{self._csrf_field()}<p>Builds a rights-permitted research export: schema, claim versions, source references and digests, events, method and results. The canonical research digest excludes the export id and time; verify it in a fresh workspace through the UI or with <code>python3 -m v8.workbench verify-export</code>.</p><button type="submit">Build export</button></form>
<table><tr><th>download</th><th>canonical research digest</th><th>zip sha256</th><th>built (local action)</th></tr>{exp_rows or '<tr><td colspan="4" class="muted">no export yet</td></tr>'}</table>
<h3>Public publication eligibility (separate from local export)</h3><p class="bad">NOT ELIGIBLE</p><ul>{"".join(f"<li>{esc(r)}</li>" for r in pe["reasons"])}</ul><p class="muted">{esc(pe["meaning"])}</p>"""
        retro = ""
        if full["outcome"] is not None:
            latest_avail = max(schema.parse_ts(e["time"]["source_available_as_of"]) for e in full["events"] if e["time"].get("source_available_as_of"))
            observed = [schema.parse_ts(e["time"]["observed_at"]) for e in full["events"] if e["time"].get("source_available_as_of")]
            if observed and min(observed) > latest_avail:
                retro = f'<div class="notice"><b>RETROSPECTIVE REPLAY.</b> Every source was first observed by this workspace on {esc(min(observed).strftime("%Y-%m-%d"))}, after the latest source became public ({esc(latest_avail.strftime("%Y-%m-%d"))}). The as-of views below are reconstructions from source availability timestamps, not contemporaneous records.</div>'
        body = f"""{retro}<p class="muted">{esc(cur["issuer"]["name"])} ({esc(cur["issuer"]["ticker"])}, CIK {esc(cur["issuer"]["cik"])}) · {esc(cur["metric"])} · {"FICTIONAL demonstration data" if cur["fictional"] else "real-source data"}{" · <b class=warn>WITHDRAWN</b>" if full["withdrawn"] else ""}</p>
<h2 id="source">1 Source</h2><table><tr><th>version</th><th>accession · form</th><th>filed</th><th>available as of</th><th>times</th><th>passage</th></tr>{src_rows}</table>
<h2 id="claim">2 Typed claim — versions</h2><table><tr><th>version</th><th>range</th><th>currency / unit</th><th>basis</th><th>fiscal period</th><th>rule</th><th>stated</th><th>digest</th><th>reason</th></tr>{ver_rows}</table>{amend_form}
<h2 id="comparison">3 Comparison — original vs revised</h2>{cmp_html}
<h2 id="calculation">4 Calculation</h2>{calc_html}{out_form if not full["withdrawn"] else ""}
<h2 id="history">5 History — as-of replay</h2>{hist_html}
<h2 id="adjudication">6 Adjudication</h2><table><tr><th>reviewer</th><th>rule</th><th>label</th><th>computed</th><th>reason</th><th>conflicts</th><th>evidence</th><th>recorded</th></tr>{adj_rows or '<tr><td colspan="8" class="muted">no adjudication recorded; the claim stays unresolved</td></tr>'}</table>{adj_form}
<h2 id="export">7 Reproducible export</h2>{exp_html}"""
        return self.page(cid, body, claim_id=cid)

    def page_verify(self, q, result: dict | None) -> str:
        res_html = ""
        if result is not None:
            cls = "ok" if result["result"] == "SUCCESS" else "bad"
            checks = "".join(f'<tr><td>{esc(c.get("check"))}</td><td>{esc(c.get("path") or c.get("version") or c.get("seq") or "")}</td><td class="{"ok" if c.get("ok") else ("muted" if c.get("ok") is None else "bad")}">{esc({True: "ok", False: "FAIL", None: "n/a"}[c.get("ok")])}</td><td>{esc(c.get("note") or c.get("observed") or c.get("missing") or "")}</td></tr>' for c in result["checks"])
            res_html = f'<h2>Result: <span class="{cls}">{esc(result["result"])}</span></h2><p>{esc(result.get("first_discrepancy") or result.get("meaning") or "")}</p><p>zip sha256 <code>{esc(result["zip_sha256"])}</code> · canonical digest <code>{esc(result["canonical_digest"])}</code> · claim {esc(result["claim_id"])}</p>{f"<p>Recomputed: <b>{esc(result["recompute"]["result"])}</b> · original {esc(result["recompute"]["original"])} · revised {esc(result["recompute"]["revised"])} · Δ original midpoint {esc(result["recompute"]["delta_vs_original_midpoint"])} · Δ revised midpoint {esc(result["recompute"]["delta_vs_revised_midpoint"])} · comparison {esc(result["recompute"]["comparison"])}</p>" if result.get("recompute") else ""}<table><tr><th>check</th><th>item</th><th>ok</th><th>detail</th></tr>{checks}</table>'
        body = f"""<p>Upload an export zip produced by another workspace. The archive is read in memory within fixed bounds (no extraction), unsafe member names and symlinks are refused, every digest and length is checked, the canonical content is re-serialized, claim digests and event hashes are re-derived, and the calculations are recomputed from the packed versions and outcome. Imported content is data: it is never executed, fetched or merged into this workspace's claims.</p>
<form class="card" method="post" action="/verify" enctype="multipart/form-data">{self._csrf_field()}<label>Export zip</label><input type="file" name="packet"><button type="submit">Verify</button></form>{res_html}"""
        return self.page("Verify an export — fresh workspace", body)

    def page_journal(self, q) -> str:
        ws = self.server.ws
        rows = "".join(f'<tr><td>{esc(e["seq"])}</td><td>{esc(e["kind"])}</td><td>{esc(e["claim_id"] or "")}</td><td><code>{esc(e["op_id"])}</code></td><td>{esc(e["time"]["source_available_as_of"] or "—")}</td><td>{esc(e["time"]["observed_at"])}</td><td>{esc(e["time"]["recorded_at"])}</td><td><code>{esc(e["prev_hash"][:12])}… → {esc(e["event_hash"][:12])}…</code></td></tr>' for e in ws.events())
        return self.page("Journal — append-only event log", f'<p>Every durable line, chained by digest. Nothing is edited in place; corrections are new events that name what they supersede.</p><table><tr><th>seq</th><th>kind</th><th>claim</th><th>op id</th><th>source available</th><th>observed</th><th>recorded</th><th>chain</th></tr>{rows}</table>')

    # ------------------------------------------------------------------ actions
    def post_source(self, form, op_id):
        ex = form.get("excerpt", "")
        raw = {"kind": form.get("kind", ""), "form": form.get("form", ""), "accession": form.get("accession", "").strip(), "url": form.get("url") or None, "filed_at": form.get("filed_at", ""),
               "available_as_of": _norm_ts(form.get("available_as_of"), "source.available_as_of") or "", "excerpt": ex, "source_hash": hashlib.sha256(ex.encode("utf-8")).hexdigest(), "fictional": form.get("fictional") == "1", "rights": form.get("rights", "")}
        self.server.ws.register_source(raw, op_id=op_id, observed_at=_norm_ts(form.get("observed_at"), "observed_at"))
        return self._redirect("/source")

    def post_freeze(self, form, op_id):
        src = self._source_by_id(form.get("source_id", ""))
        raw = {"schema": schema.SCHEMA, "claim_id": form.get("claim_id", "").strip(), "issuer": {"name": form.get("issuer_name", ""), "ticker": form.get("issuer_ticker", "").strip().upper(), "cik": form.get("issuer_cik", "").strip()},
               "metric": form.get("metric", ""), "kind": schema.KIND, "statement": form.get("statement", ""), "range": {"low": form.get("range_low", "").strip(), "high": form.get("range_high", "").strip()},
               "unit": form.get("unit", "").strip(), "currency": form.get("currency", "").strip(), "scale_as_stated": form.get("scale_as_stated", ""), "basis": form.get("basis", ""),
               "fiscal_period": self._period_from(form), "resolution_rule": form.get("resolution_rule", ""), "stated_at": src["filed_at"], "source": src, "fictional": form.get("fictional") == "1"}
        ev, _ = self.server.ws.freeze_claim(raw, op_id=op_id)
        return self._redirect(f"/claim/{urllib.parse.quote(ev['claim_id'], safe='')}#claim")

    def post_amend(self, cid, form, op_id):
        src = self._source_by_id(form.get("source_id", ""))
        t = form.get("amend_type", "")
        changes = None
        if t in ("REVISED", "CORRECTED_SOURCE"):
            changes = {"range": {"low": form.get("range_low", "").strip(), "high": form.get("range_high", "").strip()}, "basis": form.get("basis", ""), "currency": form.get("currency", "").strip(),
                       "unit": form.get("unit", "").strip(), "metric": form.get("metric", ""), "fiscal_period": self._period_from(form)}
            if form.get("statement"):
                changes["statement"] = form["statement"]
        self.server.ws.amend_claim(cid, t, changes=changes, reason=form.get("reason", ""), source=src, notes={"explanation_unresolved": form.get("explanation_unresolved", ""), "next_evidence": form.get("next_evidence", ""), "source_discrepancy": form.get("source_discrepancy", "")}, op_id=op_id)
        return self._redirect(f"/claim/{urllib.parse.quote(cid, safe='')}#comparison")

    def post_outcome(self, cid, form, op_id):
        src = self._source_by_id(form.get("source_id", ""))
        raw = {"schema": schema.OUTCOME_SCHEMA, "claim_id": cid, "metric": form.get("metric", ""), "actual": form.get("actual", "").strip(), "unit": form.get("unit", "").strip(), "currency": form.get("currency", "").strip(),
               "basis": form.get("basis", ""), "fiscal_period": self._period_from(form), "comparable": form.get("comparable") == "1", "source": src, "fictional": src["fictional"]}
        self.server.ws.record_outcome(cid, raw, op_id=op_id)
        return self._redirect(f"/claim/{urllib.parse.quote(cid, safe='')}#calculation")

    def post_adjudicate(self, cid, form, op_id):
        body = self._last_body_qs
        ev = [v for v in body.get("evidence", []) if re.match(r"^[0-9a-f]{64}$", v)]
        self.server.ws.record_adjudication(cid, reviewer=form.get("reviewer", "").strip(), rule=form.get("rule", ""), evidence=ev, reason=form.get("reason", ""), conflicts=form.get("conflicts", ""),
                                           label=form.get("label", ""), disputed=form.get("disputed") == "1", op_id=op_id)
        return self._redirect(f"/claim/{urllib.parse.quote(cid, safe='')}#adjudication")

    def post_export(self, cid, form, op_id):
        r = export.build_export(self.server.ws, cid, candidate_commit=self.server.candidate_commit, op_id=op_id)
        return self._redirect(f"/claim/{urllib.parse.quote(cid, safe='')}?built={r['export_id']}#export")

    def post_fixture(self, form, op_id):
        fid = form.get("fixture", "")
        p = self.server.fixtures_dir / f"{fid}.json"
        if not _FIXTURE.match(fid) or not p.is_file():
            raise ContractError("fixture: unknown fixture id")
        fx = json.loads(p.read_text()); rec = schema.from_fixture(fx); ws = self.server.ws
        cid = f"{rec['claim']['claim_id']}--{fx['fixture_id']}"          # fixtures share one claim id; each variant loads under its own suffixed id
        rec["claim"] = dict(rec["claim"], claim_id=cid)
        for r in rec["revisions"]:
            if r.get("claim"):
                r["claim"] = dict(r["claim"], claim_id=cid)
        tag = f"fx:{fx['fixture_id']}"
        ws.register_source(rec["claim"]["source"], op_id=f"{tag}:src:{rec['claim']['source']['accession']}", observed_at=rec["claim"]["source"]["available_as_of"])
        ws.freeze_claim(rec["claim"], op_id=f"{tag}:freeze", observed_at=rec["claim"]["source"]["available_as_of"])
        for r in rec["revisions"]:
            ws.register_source(r["source"], op_id=f"{tag}:src:{r['source']['accession']}", observed_at=r["source"]["available_as_of"])
            if r["type"] == "WITHDRAWN":
                ws.amend_claim(cid, "WITHDRAWN", changes=None, reason=r["reason"] or "withdrawn per fixture", source=r["source"], op_id=f"{tag}:{r['revision_id']}", observed_at=r["source"]["available_as_of"])
            else:
                c = r["claim"]; ws.amend_claim(cid, r["type"], changes={"range": c["range"], "basis": c["basis"], "unit": c["unit"], "currency": c["currency"], "statement": c["statement"], "fiscal_period": c["fiscal_period"], "metric": c["metric"]},
                                              reason=r["reason"] or f"{r['type']} per fixture", source=r["source"], op_id=f"{tag}:{r['revision_id']}", observed_at=r["source"]["available_as_of"])
        if rec["outcome"]:
            ws.register_source(rec["outcome"]["source"], op_id=f"{tag}:src:{rec['outcome']['source']['accession']}", observed_at=rec["outcome"]["source"]["available_as_of"])
            ws.record_outcome(cid, rec["outcome"], op_id=f"{tag}:outcome", observed_at=rec["outcome"]["source"]["available_as_of"])
        return self._redirect(f"/claim/{urllib.parse.quote(cid, safe='')}")

    def post_verify(self):
        ct = self.headers.get("Content-Type", "")
        body = self._read_body(UPLOAD_LIMIT)
        if body is None or not ct.startswith("multipart/form-data"):
            return self._text(413, "refused: upload missing, too large or not multipart")
        try:
            mp = Multipart(ct, body)
        except ContractError as exc:
            return self._text(400, f"refused: {exc}")
        if not hmac.compare_digest(mp.fields.get("csrf", ""), self.server.csrf_for(self._sess)):
            return self._text(403, "refused: CSRF token invalid; nothing was written")
        op_id = mp.fields.get("op_id", "")
        if "packet" not in mp.files or not mp.files["packet"][1]:
            return self._send(422, self.page_error("verify: choose an export zip first"))
        ws = self.server.ws
        tmp = ws.imports / f"upload-{secrets.token_hex(6)}.zip"
        tmp.write_bytes(mp.files["packet"][1])
        try:
            result = export.verify_export(tmp)
        finally:
            tmp.unlink(missing_ok=True)
        if re.match(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$", op_id):
            ws.record_verification(result.get("claim_id") if result.get("claim_id") and _CLAIM_ID.match(result["claim_id"]) else None, packet_sha256=result["zip_sha256"] or "", result=result["result"],
                                   first_discrepancy=result["first_discrepancy"], canonical_digest=result["canonical_digest"], op_id=op_id)
        return self._send(200, self.page_verify({}, result))

    # the adjudication form needs multi-valued checkboxes: keep the raw query string
    def _form(self, limit=FORM_LIMIT):
        ct = self.headers.get("Content-Type", "")
        body = self._read_body(limit)
        if body is None or not ct.startswith("application/x-www-form-urlencoded"):
            return None
        qs = urllib.parse.parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
        self._last_body_qs = qs
        return {k: v[-1] for k, v in qs.items()}


def serve(workspace, port: int = 8765, *, fixtures_dir=None, candidate_commit=None):
    srv = WorkbenchServer(workspace, port, fixtures_dir=fixtures_dir, candidate_commit=candidate_commit)
    print(f"[workbench] serving workspace {srv.ws.root.name} at {srv.origin}  (loopback only; Ctrl-C to stop)", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
