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
from v8.workbench import NOT_ADVICE, availability, calc, dataset, export, money, schema
from v8.workbench.sci import adapter as sci_adapter
from v8.workbench.store import StoreIntegrityError, Workspace, new_op_id

_REPO = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parent / "resources" / "fixtures"      # packaged copies of tests/fixtures/v8/commitments (identity tested)
FORM_LIMIT = 256 * 1024
IMPORT_LIMIT = 64 * 1024                                                       # one pasted ingestion source record (a passage, not a document)
UPLOAD_LIMIT = export.MAX_ZIP_BYTES + 64 * 1024
CSP = "default-src 'none'; img-src 'self'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
_CLAIM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_EXPORT_ID = re.compile(r"^exp-[0-9a-f]{16}$")
_FIXTURE = re.compile(r"^00[1-9]_[a-z_]{1,64}$")          # bounded: the value becomes a file name (an over-long one raised OSError and dropped the connection)
_SCI_EXAMPLE = re.compile(r"^[a-z_]{1,64}$")
_SCI_ID = re.compile(r"^S[0-9]{1,5}$")
_CORRECTION_ID = re.compile(r"^AC[0-9]{1,6}$")
SCI_EXAMPLES_DIR = Path(__file__).resolve().parent / "resources" / "sci"
GUIDE_PATH = Path(__file__).resolve().parent / "resources" / "OPERATOR_GUIDE.md"   # packaged; shown under /help and by `python -m v8.workbench guide`
DICTIONARY_PATH = Path(__file__).resolve().parent / "resources" / "DATA_DICTIONARY.md"   # packaged; shown under /help/data
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
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,.tw:focus-visible,input[type=date]:focus-within{outline:3px solid #0b57d0;outline-offset:2px}
.skip{position:absolute;left:-999px;top:0;background:#fff;padding:.4rem .8rem;border:2px solid #0b57d0} .skip:focus{left:.5rem;top:.5rem;z-index:2}
.tw{overflow-x:auto;margin:.4rem 0} nav{display:flex;flex-wrap:wrap;gap:.2rem .8rem} nav a{margin-right:0}
ol.steps{list-style:none;padding:0} ol.steps li{border:1px solid #bbb;border-radius:4px;padding:.15rem .5rem;font-size:.85rem;background:#fff}
fieldset{border:1px solid #ddd;margin:.5rem 0;padding:.3rem .6rem} legend{font-size:.85rem;padding:0 .3rem}
code,pre.excerpt,p,li,h1{overflow-wrap:anywhere} input[type=file]{max-width:100%} th{white-space:nowrap} td{min-width:5rem} td pre.excerpt{min-width:16rem} td p,td li{overflow-wrap:break-word}
.guide{white-space:pre-wrap;background:#fff;border:1px solid #ccd;padding:.8rem;font-size:.9rem;font-family:inherit}
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
    try:
        schema.parse_ts(v + "Z")                                   # the pattern admits impossible dates (30 February); refuse them here, with the field named
    except ContractError:
        raise ContractError(f"{field}: {v + 'Z'!r} is not a real UTC date and time; use YYYY-MM-DDTHH:MM:SSZ") from None
    return v + "Z"


_LABEL_CONTROL = re.compile(r"<label>((?:(?!</?label\b).)*?)</label>(\s*)<(input|select|textarea)\b", re.S)
_ROW_HEADER = re.compile(r"<th>((?:(?!</th>).)*?)</th>(?=<td)", re.S)
_TH_TEXT = re.compile(r"<th[^>]*>([^<]{1,40})")


def a11y(markup: str) -> str:
    """Accessibility pass over server-built markup. Every dynamic value is escaped before it reaches here, so the literal
    tags matched below can only be the server's own. Binds each <label> to the control that follows it (unique ids per
    page), scopes header cells, puts every table in a named, keyboard-scrollable region (wide tables scroll inside the
    region instead of pushing the page sideways) and gives error/notice blocks a role plus a text cue, so no status
    depends on colour alone."""
    n = [0]

    def bind(m):
        n[0] += 1
        return f'<label for="f{n[0]}">{m.group(1)}</label>{m.group(2)}<{m.group(3)} id="f{n[0]}"'
    markup = _LABEL_CONTROL.sub(bind, markup)
    markup = _ROW_HEADER.sub(lambda m: f'<th scope="row">{m.group(1)}</th>', markup).replace("<th>", '<th scope="col">')
    parts = markup.split("<table>")
    for i in range(1, len(parts)):
        heads = [h.strip() for h in _TH_TEXT.findall(parts[i].split("</table>", 1)[0]) if h.strip()][:3]
        name = "Table: " + ", ".join(heads) + (" …" if heads else "")
        parts[i] = f'<div class="tw" role="region" tabindex="0" aria-label="{name}"><table>' + parts[i].replace("</table>", "</table></div>", 1)
    markup = "".join(parts)
    markup = re.sub(r'<div class="?err"?>', '<div class="err" role="alert"><b>Error.</b> ', markup)
    return re.sub(r'<(div|p) class="notice">', r'<\1 class="notice" role="status">', markup)


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
        self.send_header("X-Frame-Options", "DENY"); self.send_header("Referrer-Policy", "same-origin")   # no-referrer would make the browser send Origin: null on same-origin form posts (Fetch §4.1.1)
        self.send_header("Cache-Control", "no-store")
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
            return "session cookie missing; open the page in this browser first, then submit its form"
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
        self._pf_action = self._pf = self._pf_msg = None
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
            if path == "/help":
                return self._send(200, self.page_help(q), extra=extra)
            if path == "/help/data":
                text = DICTIONARY_PATH.read_text(encoding="utf-8") if DICTIONARY_PATH.is_file() else "The packaged data dictionary is missing from this installation."
                return self._send(200, self.page("Help — data dictionary and dataset card", f'<p class="muted">Shown as plain text exactly as packaged (<code>v8/workbench/resources/DATA_DICTIONARY.md</code>). <a href="/help">Back to Help</a>.</p><div class="guide">{esc(text)}</div>'), extra=extra)
            if path == "/notes":
                return self._send(200, self.page_notes(q), extra=extra)
            if path == "/dataset":
                return self._send(200, self.page_dataset(q), extra=extra)
            if path == "/sci":
                return self._send(200, self.page_sci(q), extra=extra)
            m = re.match(r"^/sci/(S[0-9]{1,5})$", path)
            if m:
                return self._send(200, self.page_sci_record(m.group(1)), extra=extra)
            if path == "/dataset.json":
                snap = dataset.build_snapshot(self.server.ws)
                return self._send(200, json.dumps({"snapshot": snap, "snapshot_digest": dataset.snapshot_digest(snap), "derived_at": _now(), "note": "derived_at is outside the snapshot identity"}, indent=1, sort_keys=True, ensure_ascii=True), "application/json; charset=utf-8", extra)
            return self._text(404, "not found")
        except StoreIntegrityError as exc:
            return self._send(200, self.page_integrity(exc), extra=extra)

    def do_POST(self):
        self._pf_action = self._pf = self._pf_msg = None
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
            return self._text(403, "refused: CSRF token invalid; nothing was written. Form tokens are issued per server start and browser session: reload the page you submitted from and submit again")
        op_id = form.get("op_id", "")
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$", op_id):
            return self._text(400, "refused: operation identifier missing")
        try:
            if path == "/source/register":
                return self.post_source(form, op_id)
            if path == "/source/import":
                return self.post_import(form, op_id)
            if path == "/source/correct-availability":
                return self.post_availability(form, op_id)
            if path == "/claim/freeze":
                return self.post_freeze(form, op_id)
            m = re.match(r"^/claim/([^/]+)/(amend|outcome|adjudicate|export|note)$", path)
            if m:
                cid = urllib.parse.unquote(m.group(1))
                if not _CLAIM_ID.match(cid):
                    return self._text(404, "no such claim")
                return getattr(self, "post_" + m.group(2))(cid, form, op_id)
            if path == "/fixtures/load":
                return self.post_fixture(form, op_id)
            if path == "/sci/replay":
                return self.post_sci(form, op_id)
            if path == "/dataset/export":
                r = export.build_dataset_export(self.server.ws, candidate_commit=self.server.candidate_commit, op_id=op_id)
                return self._redirect(f"/dataset?built={r['export_id']}")
            if path == "/recover":
                r = self.server.ws.recover()
                return self._redirect("/?recovered=" + ("1" if r["recovered"] else "0"))
            return self._text(404, "not found")
        except StoreIntegrityError as exc:
            return self._send(200, self.page_integrity(exc))
        except ContractError as exc:
            return self._send(422, self._rerender(path, form, str(exc)))

    # ------------------------------------------------------------------ building blocks
    def _csrf_field(self, action: str | None = None) -> str:
        # a refused form is re-rendered with the operation identifier it was submitted under (nothing was written under it)
        op = self._pf.get("op_id") if action is not None and self._pf_action == action else None
        return f'<input type="hidden" name="csrf" value="{esc(self.server.csrf_for(self._sess))}"><input type="hidden" name="op_id" value="{esc(op or new_op_id("ui"))}">'

    def _rerender(self, path: str, form: dict, msg: str) -> str:
        """A refused form comes back as the page it was submitted from: the refusal and its reasons first, then the same
        form with everything the user entered still in its fields. Nothing was written."""
        m = re.match(r"^/claim/([^/]+)/(amend|outcome|adjudicate|note)$", path)
        self._pf, self._pf_msg = form, msg
        self._pf_action = m.group(2) if m else {"/source/register": "register", "/source/import": "import", "/source/correct-availability": "availability", "/claim/freeze": "freeze", "/sci/replay": "replay"}.get(path)
        if m and self.server.ws.claim_state(urllib.parse.unquote(m.group(1))) is not None:
            return self.page_claim(urllib.parse.unquote(m.group(1)), {})
        if self._pf_action in ("register", "import", "availability"):
            return self.page_source({})
        if self._pf_action == "freeze":
            return self.page_claim_new({})
        if self._pf_action == "replay":
            return self.page_sci({})
        self._pf_action = self._pf = self._pf_msg = None
        return self.page_error(msg, form)

    def _cur(self, action: str, name: str, default=None):
        """A field's current value: what the user entered when this form was just refused, else the default."""
        return self._pf.get(name, "") if self._pf_action == action else default

    def _val(self, action: str, name: str, default="") -> str:
        return esc(self._cur(action, name, default))

    def _checked(self, action: str, name: str, default: bool = False, value: str | None = None) -> str:
        if self._pf_action != action:
            on = default
        elif value is None:
            on = name in self._pf
        else:
            on = value in getattr(self, "_last_body_qs", {}).get(name, [])
        return " checked" if on else ""

    def _blocked(self) -> str:
        """The refusal summary shown at the top of a re-rendered page."""
        msg = self._pf_msg
        reasons = [r.strip() for r in msg.split(":", 1)[-1].split(";")] if ";" in msg else [msg]
        items = "".join(f"<li>{esc(r)}</li>" for r in reasons)
        head = esc(msg.split(":", 1)[0]) if ";" in msg else "Refused"
        return (f'<div class="err"><b>Blocked — nothing was written.</b> {head}<ul>{items}</ul><p>Everything you entered is still in <a href="#form-{esc(self._pf_action)}">the form below</a>. '
                f'Correct the listed fields and submit again; the operation identifier is unchanged, so a corrected resubmission cannot duplicate anything.</p></div>')

    def page(self, title: str, body: str, *, claim_id: str | None = None) -> str:
        ws = self.server.ws; st = ws.status()
        integ = st["integrity"]
        cls = "ok" if integ == "OK" else "bad"
        cq = urllib.parse.quote(claim_id, safe="") if claim_id else None
        href = (lambda key: f"/claim/{cq}#{key}") if cq else {"source": "/source", "claim": "/claim/new"}.get
        steps = "".join(f'<li><a href="{esc(href(key))}">{esc(lbl)}</a></li>' if href(key) else f"<li>{esc(lbl)}</li>" for key, lbl in STEPS)
        hint = "" if cq else '<p class="muted">Steps 3–7 are sections of a claim\'s page: open a claim from the <a href="/">Workspace</a>.</p>'
        cand = self.server.candidate_commit or "not recorded"
        return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{"Blocked — " if self._pf_msg else ""}{esc(title)} — YUCLAW workbench</title><link rel="stylesheet" href="/static/style.css"></head><body>
<a class="skip" href="#main">Skip to the page content</a>
<p class="muted"><b>Research &amp; education only. Not investment advice.</b> Local workbench bound to 127.0.0.1. Nothing here publishes.</p>
<nav aria-label="Workbench functions"><a href="/">Workspace</a><a href="/source">1 Source</a><a href="/claim/new">2 Typed claim</a><a href="/notes">Research notes</a><a href="/dataset">Dataset coverage</a><a href="/sci">Scientific report</a><a href="/verify">Verify an export (fresh workspace)</a><a href="/journal">Journal</a><a href="/help">Help</a></nav>
<ol class="steps" aria-label="The seven steps">{steps}</ol>{hint}
<main id="main" tabindex="-1"><h1>{esc(title)}</h1>
{a11y((self._blocked() if self._pf_msg else "") + body)}</main>
<footer>Workspace <code>{esc(st['workspace_id'])}</code> · events {esc(st.get('events'))} · integrity <span class="{cls}">{esc(integ)}</span> · candidate commit <code>{esc(cand)}</code> · {esc(NOT_ADVICE)}</footer></body></html>"""

    def page_error(self, msg: str, form: dict | None = None) -> str:
        reasons = [r.strip() for r in msg.split(":", 1)[-1].split(";")] if ";" in msg else [msg]
        items = "".join(f"<li>{esc(r)}</li>" for r in reasons)
        return self.page("Blocked — nothing was written", f'<div class="err"><p><b>{esc(msg.split(":", 1)[0] if ";" in msg else "Refused")}</b></p><ul>{items}</ul></div><p>Next: <a href="/">go back to the workspace</a> and repeat the action with a valid choice. Pages are not cached, so the browser Back button shows a fresh form.</p>')

    def page_integrity(self, exc: StoreIntegrityError) -> str:
        body = f'<div class="err"><p><b>{esc(exc.code)}</b>: {esc(str(exc))}</p></div>'
        if exc.code == "E_TORN_TAIL":
            body += f'<form class="card" method="post" action="/recover">{self._csrf_field()}<p>An interrupted append left bytes without a terminating newline. Recovery preserves those bytes in a side file, truncates only them, and records a RECOVERY event. No durable event is changed.</p><button type="submit">Run recovery</button></form>'
        else:
            body += "<p>The log fails its chain check. The workspace refuses to serve or write until a person inspects the file; nothing is repaired automatically.</p>"
        return self.page("Workspace integrity", body)

    def _sources(self):
        return [e["payload"] for e in self.server.ws.events() if e["kind"] == "SOURCE_REGISTERED"]

    def _source_select(self, action: str, name="source_id") -> str:
        cur = self._cur(action, name); idx = availability.index(self.server.ws.events())
        fixed = lambda s: f' (corrected to {esc(idx[s["source_id"]]["effective"])})' if idx.get(s["source_id"], {}).get("applied") else ""
        opts = "".join(f'<option value="{esc(s["source_id"])}"{" selected" if s["source_id"] == cur else ""}>{esc(s["source"]["accession"])} · {esc(s["source"]["form"])} · filed {esc(s["source"]["filed_at"])} · available {esc(s["source"]["available_as_of"])}{fixed(s)} · {esc(s["source"]["rights"])}</option>' for s in self._sources())
        return f'<label>Registered source (step 1)</label><select name="{name}" required><option value="">— choose a registered source —</option>{opts}</select>'

    def _source_by_id(self, sid: str) -> dict:
        for s in self._sources():
            if s["source_id"] == sid:
                return s["source"]
        raise ContractError("source_id: choose a registered source first (step 1); an unregistered passage cannot back a claim")

    def _period_fields(self, action: str, prefix="fp_", p: dict | None = None) -> str:
        p = self._period_from(self._pf, prefix) if self._pf_action == action else (p or {})
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

    def _version_notes_html(self, v: dict) -> str:
        n = v.get("notes") or {}
        if not any(n.get(k) for k in ("explanation_unresolved", "next_evidence", "source_discrepancy")):
            return ""
        return (f'<p><span class="muted">Amendment notes on <b>{esc(v["version_id"])}</b> (digest <code>{esc(v["claim"]["_digest"][:12])}…</code>, recorded {esc(v["time"]["recorded_at"])}):</span><br>'
                f'<b>Unresolved explanation:</b> {esc(n.get("explanation_unresolved") or "—")}<br><b>Next evidence:</b> {esc(n.get("next_evidence") or "—")}'
                + (f'<br><b class="warn">Source discrepancy (preserved verbatim, not corrected):</b> {esc(n.get("source_discrepancy"))}' if n.get("source_discrepancy") else "") + '<br><span class="muted">explanatory notes are not causal proof</span></p>')

    @staticmethod
    def _note_row(n: dict) -> str:
        kind = '<span class="warn">simulated test action</span>' if n["actor_kind"] == "simulated_test_action" else '<span class="muted">attribution label</span>'
        sup = (f'<br><span class="muted">corrects {esc(n["supersedes_note"])}</span>' if n.get("supersedes_note") else "") + (f'<br><span class="muted">corrected by {esc(n["superseded_by"])} (this text is retained)</span>' if n.get("superseded_by") else "")
        return (f'<tr><td><b>{esc(n["note_id"])}</b>{sup}</td><td>{esc(n["category"])}</td><td>{esc(n["actor"])}<br>{kind}</td><td>{esc(n["version_ref"])} <code>{esc(n["version_digest"][:12])}…</code></td>'
                f'<td>{esc(n["unresolved_question"] or "—")}</td><td>{esc(n["next_evidence"] or "—")}</td><td>{esc(n["reason"])}</td><td>{"".join(f"<code>{esc(h[:12])}…</code> " for h in n["evidence"]) or "—"}</td><td>{esc(n["time"]["recorded_at"])}</td></tr>')

    _NOTE_HEAD = '<table><tr><th>note</th><th>category</th><th>actor</th><th>version</th><th>unresolved question / explanation</th><th>next evidence</th><th>reason</th><th>evidence</th><th>recorded (local action)</th></tr>'

    def _notes_block(self, st: dict, full: dict, cut: str | None, where: str, categories: tuple | None, title: str) -> str:
        """Relevant current notes for a section (comparison, calculation). In an as-of view only notes recorded at or before
        the cutoff are shown here; later ones are listed separately with their actual action times."""
        cur = [n for n in st.get("research_notes_current", []) if categories is None or n["category"] in categories]
        if not cur:
            return f'<p class="muted">{esc(title)}: none recorded. Notes are written under "Research notes" below; they explain, they never change the claim or its result.</p>'
        return f'<h3>{esc(title)}</h3>{self._NOTE_HEAD}{"".join(self._note_row(n) for n in cur)}</table>'

    def _notes_section(self, cid: str, cq: str, st: dict, full: dict, cut: str | None) -> str:
        notes = st.get("research_notes", []); rows = "".join(self._note_row(n) for n in notes)
        later = ""
        if cut:
            hidden = [n for n in full.get("research_notes", []) if n["event_hash"] not in {x["event_hash"] for x in notes}]
            if hidden:
                later = f'<div class="notice"><b>Later annotations — recorded after this cutoff ({esc(cut)}); NOT contemporaneous with the as-of view above.</b> Each carries its actual local action time.</div>{self._NOTE_HEAD}{"".join(self._note_row(n) for n in hidden)}</table>'
        A = "note"; V = lambda n, d="": self._val(A, n, d)
        vcur = self._cur(A, "version_ref", full["current"]["version_id"])
        vopts = "".join(f'<option value="{esc(v["version_id"])}"{" selected" if v["version_id"] == vcur else ""}>{esc(v["version_id"])} · {esc(v["type"])} · {esc(v["claim"]["_digest"][:12])}…</option>' for v in full["versions"])
        copts = "".join(f'<option value="{esc(c)}"{" selected" if c == self._cur(A, "category") else ""}>{esc(c)}</option>' for c in schema.NOTE_CATEGORIES)
        sopts = "".join(f'<option value="{esc(n["note_id"])}"{" selected" if n["note_id"] == self._cur(A, "supersedes_note") else ""}>{esc(n["note_id"])} · {esc(n["category"])} · {esc(n["reason"][:40])}</option>' for n in full.get("research_notes_current", []))
        ev_opts = "".join(f'<label><input type="checkbox" name="evidence" value="{esc(e["event_hash"])}"{self._checked(A, "evidence", value=e["event_hash"])}> {esc(e["seq"])} {esc(e["kind"])} <code>{esc(e["event_hash"][:12])}…</code></label>' for e in full["events"] + self._correction_events(full) if e["kind"] not in ("RESEARCH_NOTE_RECORDED",))
        form = f"""<form class="card" id="form-note" method="post" action="/claim/{esc(cq)}/note">{self._csrf_field(A)}<h3>Record a research note</h3>
<p class="muted">A note is a separate research action: it records an unresolved question or explanation, the next evidence needed and why. It changes nothing about the claim — range, metric, currency, basis, fiscal period, sources and frozen digests stay exactly as they are — and it never resolves an outcome or reopens a withdrawn commitment. A correction is a new note that names the note it corrects; the earlier text is retained.</p>
<div class="row"><div><label>Category</label><select name="category">{copts}</select></div><div><label>Actor (attribution label — not authenticated identity; does not establish independent review)</label><input type="text" name="actor" value="{V('actor')}"></div><div><label>About version</label><select name="version_ref">{vopts}</select></div><div><label>Corrects an earlier note (optional)</label><select name="supersedes_note"><option value="">— new note —</option>{sopts}</select></div></div>
<label>Unresolved question or explanation</label><textarea name="unresolved_question" rows="2">{V('unresolved_question')}</textarea>
<label>Next evidence needed</label><input type="text" name="next_evidence" value="{V('next_evidence')}">
<label>Reason for the note (required)</label><input type="text" name="reason" value="{V('reason')}">
<fieldset><legend>Evidence (events this note refers to)</legend>{ev_opts}</fieldset>
<label><input type="checkbox" name="simulated" value="1"{self._checked(A, 'simulated')}> This is a simulated test action (automated), not a human's note</label>
<button type="submit">Record research note</button></form>"""
        table = f'{self._NOTE_HEAD}{rows}</table>' if rows else '<p class="muted">No research notes on this claim yet.</p>'
        return f'<p class="muted">{esc(len(notes))} note(s), {esc(len([n for n in notes if n.get("supersedes_note")]))} correction(s). Notes carry no source availability: an as-of replay shows only the notes recorded at or before the cutoff.</p>{table}{later}{form}'

    @staticmethod
    def _correction_events(full: dict) -> list[dict]:
        return sorted((e for ent in (full.get("availability") or {}).values() for e in ent["applied"] + ent["later"]), key=lambda e: e["seq"])

    @staticmethod
    def _later_corrections_html(later: list[dict], cut: str | None) -> str:
        if not later:
            return ""
        def line(x: dict) -> str:
            if x["public_as_held"] == x["public_under_correction"]:
                effect = "it does not change whether the source counts as public at this cutoff"
            elif x["public_under_correction"]:
                effect = "under it the source would already count as public at this cutoff, but that was not known then: the view keeps the source as the record held it"
            else:
                effect = "under it the source would not yet count as public at this cutoff: the view keeps the source as the record held it, and what it shows needs review"
            return f'<li><b>{esc(x["correction_id"])}</b> on <code>{esc(x["source_id"])}</code>, recorded {esc(x["recorded_at"])}: {esc(x["held_at_cutoff"])} → {esc(x["corrected_available_as_of"])} — {effect}</li>'
        return f'<div class="notice"><b>Later corrections — recorded after this cutoff ({esc(cut)}); NOT applied to the as-of view.</b> A later correction is later knowledge and is never shown as known at the cutoff.<ul>{"".join(line(x) for x in later)}</ul></div>'

    def _availability_html(self, st: dict, cut: str | None, later: list[dict]) -> str:
        """Beside the source table: the correction chain of this claim's sources, the corrected view next to the recorded
        result, and what needs review. The registration, the claim versions and earlier adjudications are never rewritten."""
        blk = availability.block(st)
        if blk is None or not any(s["corrections"] for s in blk["sources"]):
            return self._later_corrections_html(later, cut) or '<p class="muted">A wrong availability time is corrected with a linked event under <a href="/source#availability">1 Source — Correct a source\'s availability time</a>; the registration is never edited.</p>'
        rows = "".join(f'<tr><td><b>{esc(c["correction_id"])}</b></td><td><code>{esc(s["source_id"])}</code><br><span class="muted">registered {esc(s["registration"]["available_as_of"])} · observed {esc(s["registration"]["observed_at"])}</span></td><td>{esc(c["prior_available_as_of"])}</td><td><b>{esc(c["corrected_available_as_of"])}</b><br><span class="muted">{esc(c["direction"])}</span></td><td>{esc(c["reason"])}</td><td>{esc(c["evidence_ref"])}</td><td>{esc(c["actor"])}<br><span class="{"warn" if c["actor_kind"] == "simulated_test_action" else "muted"}">{esc(c["actor_kind"].replace("_", " "))}</span></td><td>{esc(c["recorded_at"])}</td></tr>' for s in blk["sources"] for c in s["corrections"])
        v = blk["corrected_view"]
        windows = "".join(f'<li><code>{esc(s["source_id"])}</code>: cutoffs from {esc(s["affected_cutoffs"]["from"])} until {esc(s["affected_cutoffs"]["until"])} differ between the registered and the corrected availability</li>' for s in blk["sources"])
        review = "".join(f'<li><b>{esc(r["code"])}</b>: {esc(r["detail"])}</li>' for r in blk["review"])
        return f"""<h3 id="availability">Source availability corrections</h3>
<table><tr><th>correction</th><th>source</th><th>replaces</th><th>corrected availability</th><th>reason</th><th>evidence reference</th><th>actor</th><th>recorded (local action)</th></tr>{rows}</table>
<p>Computed result <b>as recorded: {esc(v["recorded_result"])}</b> · <b>under the corrected availability: {esc(v["result"])}</b>{' <span class="warn">— they differ</span>' if v["result_changes"] else " (the same)"} · retrospective as recorded: {esc(v["recorded_retrospective"])} · recomputed: {esc(v["recomputed_retrospective"])}. The frozen claim versions, their digests, the outcome and earlier adjudications are unchanged; the calculation in section 4 is the as-recorded one.</p>
{('<div class="notice"><b>Needs review.</b><ul>' + review + '</ul></div>') if review else '<p class="muted">Nothing needs review: the corrected view computes the same result and status.</p>'}
<p class="muted">Historical views: a correction applies to cutoffs at or after the time it was recorded; an earlier cutoff keeps the value the record held then and lists the correction as later.</p><ul class="muted">{windows}</ul>{self._later_corrections_html(later, cut)}"""

    def _sci_linked_html(self, full: dict) -> str:
        recs = full.get("sci", [])
        if not recs:
            return '<p class="muted">No scientific record links to this claim. A replay is recorded under <a href="/sci">Scientific report</a>; linking it here names this claim\'s bytes, nothing more — the claim\'s IN_RANGE / OUT_OF_RANGE results are never units of a study.</p>'
        rows = "".join(f'<tr><td><a href="/sci/{esc(r["sci_id"])}">{esc(r["sci_id"])}</a></td><td><b>{esc(r["status"])}</b><br><span class="muted">{esc(r["replay_status"])}</span></td><td>{esc((r.get("report") or {}).get("family_id") or "—")}</td><td><code>{esc(r["input_sha256"][:16])}…</code></td><td>{esc(r["actor"])}<br><span class="muted">{esc(r["actor_kind"].replace("_", " "))}</span></td><td>{esc(r["time"]["recorded_at"])}</td></tr>' for r in recs)
        return f'<table><tr><th>record</th><th>status · replay status</th><th>family</th><th>input identity</th><th>actor</th><th>recorded (local action)</th></tr>{rows}</table><p class="muted">A link names this claim\'s bytes; it establishes no source authenticity, no prospective commitment and no scientific improvement about the commitment.</p>'

    def _sci_examples(self) -> list[str]:
        return sorted(p.stem for p in SCI_EXAMPLES_DIR.glob("*.json") if p.stem != "template_manifest") if SCI_EXAMPLES_DIR.is_dir() else []

    # ------------------------------------------------------------------ pages
    def page_sci(self, q) -> str:
        ws = self.server.ws; recs = ws.sci_records("*"); k = sci_adapter.kernel_identity()
        rows = "".join(f'<tr><td><a href="/sci/{esc(r["sci_id"])}">{esc(r["sci_id"])}</a></td><td><b>{esc(r["status"])}</b><br><span class="muted">{esc(r["replay_status"])}</span></td><td>{esc((r.get("report") or {}).get("family_id") or "—")}<br><span class="muted">{esc((r.get("report") or {}).get("mode") or "")}</span></td><td>{esc("; ".join(c["status"] for c in (r.get("report") or {}).get("claims", [])) or "; ".join(x["code"] for x in r.get("reasons", [])))}</td><td>{esc(r["claim_id"] or "—")}</td><td><code>{esc(r["input_sha256"][:16])}…</code> · {esc(r["input_bytes"])} B</td><td>{esc(r["actor"])}<br><span class="muted">{esc(r["actor_kind"].replace("_", " "))}</span></td><td>{esc(r["time"]["recorded_at"])}</td></tr>' for r in recs)
        A = "replay"; V = lambda n, d="": self._val(A, n, d)
        ex = "".join(f'<option value="{esc(x)}"{" selected" if x == self._cur(A, "example") else ""}>{esc(x)}</option>' for x in self._sci_examples())
        claims = "".join(f'<option value="{esc(c)}"{" selected" if c == self._cur(A, "claim_id") else ""}>{esc(c)}</option>' for c in ws.status()["claims"])
        body = f"""<p>Replay a science journal through the adapted kernel. Supported contract: paired binary-probability predictions scored by Brier improvement; sequential evidence as a fixed mixture of Hoeffding test supermartingales; a frozen family alpha; pending outcomes, invalidation and exploratory status kept as they are. A journal is data — a JSON event list in the kernel's event format (optionally wrapped with expected_root, links and declarations) of at most {esc(sci_adapter.MAX_INPUT_BYTES // 1024)} KB and {esc(sci_adapter.MAX_EVENTS)} events; nothing in it is executed, opened as a file or fetched. The workbench recomputes every hash and statistic itself; it never trusts a supplied report.</p>
<p class="muted">Kernel {esc(k["schema"])} · kernel identity <code>{esc(k["kernel_sha256"][:16])}…</code> · {esc(k["method"])}</p>
<div class="notice">Monetary amounts and ranges are not probabilities. A financial commitment's IN_RANGE / OUT_OF_RANGE results are not units of a study and yield no scientific improvement. A retrospective record (such as a real-source replay observed after its outcome) can be inspected under an explicit retrospective label; it is never prospective evidence. Imported timestamps and actor labels establish neither commitment-before-outcome nor verified identity.</div>
<h2>Records in this workspace ({esc(len(recs))})</h2><table><tr><th>record</th><th>status · replay status</th><th>family · mode</th><th>claim statuses / refusal codes</th><th>linked claim</th><th>input identity</th><th>actor</th><th>recorded (local action)</th></tr>{rows or '<tr><td colspan="8" class="muted">no scientific record yet</td></tr>'}</table>
<h2>Replay a journal</h2><form class="card" id="form-replay" method="post" action="/sci/replay">{self._csrf_field(A)}
<div class="row"><div><label>Packaged example (fictional fixtures; leave empty to paste your own)</label><select name="example"><option value="">— paste below —</option>{ex}</select></div><div><label>Link to a frozen claim (optional; names its bytes only)</label><select name="claim_id"><option value="">— none —</option>{claims}</select></div><div><label>Actor (attribution label — not authenticated identity; does not establish independent review)</label><input type="text" name="actor" value="{V('actor')}"></div><div><label>Label (optional)</label><input type="text" name="label" value="{V('label')}"></div></div>
<label>Journal input (JSON: an event list, or {{"events": [...], "expected_root": "…", "links": {{"claim_id": "…", "version_digest": "…", "source_hashes": ["…"]}}, "declared": {{"retrospective": true}}}})</label><textarea name="input" rows="8">{V('input')}</textarea>
<label><input type="checkbox" name="simulated" value="1"{self._checked(A, 'simulated')}> This is a simulated test action (automated), not a human's replay</label>
<button type="submit">Replay through the kernel and record</button></form>
<p class="muted">Every replay — supported, exploratory or refused with its specific reasons — is recorded as an append-only event with the input's identity, so it can be inspected, exported and recomputed in a fresh workspace.</p>"""
        return self.page("Scientific report / replay", body)

    def page_sci_record(self, sid: str) -> str:
        r = next((x for x in self.server.ws.sci_records("*") if x["sci_id"] == sid), None)
        if r is None:
            return self.page("No such scientific record", '<div class="err">This record does not exist in this workspace.</div>')
        rep = r.get("report") or {}; k = r["kernel"]
        reasons = "".join(f'<li><b>{esc(x["code"])}</b>: {esc(x["reason"])}</li>' for x in r.get("reasons", []))
        warnings = "".join(f'<li>{esc(w)}</li>' for w in r.get("warnings", []))
        claims = "".join(f'<tr><td>{esc(c["claim_id"])}</td><td><b>{esc(c["status"])}</b></td><td>{esc(c["resolved_units"])} resolved · {esc(len(c["pending_units"]))} pending{(" (" + esc(", ".join(c["pending_units"][:5])) + ")") if c["pending_units"] else ""}</td><td>{esc(c["mean_brier_improvement"])}</td><td>{esc(round(c["current_log_e"], 6))} / max {esc(round(c["max_log_e"], 6))}</td><td>{esc(c["anytime_p_bound"])}</td><td>{esc(c["threshold_crossed"])}</td><td>{esc(c["invalidated_reason"] or "—")}</td><td>{esc(c["contract"]["alpha"])} of {esc(rep.get("family_alpha"))} · min {esc(c["contract"]["min_units"])} · max {esc(c["contract"]["max_units"])} · effect {esc(c["contract"]["minimum_effect"])}</td><td>{esc(c["permission"])}</td></tr>' for c in rep.get("claims", []))
        L = r.get("links") or {}
        link_rows = ""
        if L.get("claim"):
            link_rows += f'<tr><td>claim</td><td>{esc(L["claim"]["claim_id"])}</td><td><b>{esc(L["claim"]["result"])}</b>{(" · RETROSPECTIVE record" if L["claim"].get("retrospective") else "")}{(" · fictional" if L["claim"].get("fictional") else "")}</td></tr>'
        if L.get("version"):
            link_rows += f'<tr><td>version</td><td><code>{esc(L["version"]["version_digest"][:16])}…</code> {esc(L["version"].get("version_id") or "")}</td><td><b>{esc(L["version"]["result"])}</b>{(" — " + esc(L["version"].get("note"))) if L["version"].get("note") else ""}</td></tr>'
        for sh in L.get("sources", []):
            link_rows += f'<tr><td>source</td><td><code>{esc(sh["source_hash"][:16])}…</code></td><td><b>{esc(sh["result"])}</b></td></tr>'
        link_notes = "".join(f'<li>{esc(n)}</li>' for n in L.get("notes", []))
        standing = "".join(f'<li>{esc(x)}</li>' for x in r.get("standing", []))
        lim = "".join(f'<li>{esc(x)}</li>' for x in rep.get("limitations", []))
        cls = "ok" if r["status"] != "INELIGIBLE" else "bad"
        body = f"""<p><b>{esc(r["sci_id"])}</b> · status <b class="{cls}">{esc(r["status"])}</b> · replay status <b class="warn">{esc(r["replay_status"])}</b> · recorded {esc(r["time"]["recorded_at"])} by {esc(r["actor"])} ({esc(r["actor_kind"].replace("_", " "))}){(" · label: " + esc(r.get("label"))) if r.get("label") else ""}{(" · linked claim <a href=/claim/" + esc(urllib.parse.quote(r["claim_id"], safe="")) + ">" + esc(r["claim_id"]) + "</a>") if r.get("claim_id") else ""}</p>
<h2>Input identity</h2><p>input sha256 <code>{esc(r["input_sha256"])}</code> · {esc(r["input_bytes"])} bytes · {esc(len(r["input"]["events"]))} event(s) · expected root {esc(r["input"].get("expected_root") or "none supplied")} · recomputed root {esc(r.get("root_hash") or "—")}</p>
<h2>Kernel and method</h2><p>{esc(k["schema"])} · kernel identity <code>{esc(k["kernel_sha256"])}</code></p><p class="muted">{esc(k["method"])}</p><p class="muted">Supported metric: paired_brier_improvement only. Modules: {esc(", ".join(f"{m} {h[:12]}…" for m, h in k["modules"].items()))}</p>
{"<h2>Why this input is not eligible</h2><ul>" + reasons + "</ul>" if reasons else ""}
{("<h2>Report (recomputed by the kernel)</h2><p>family <b>" + esc(rep.get("family_id")) + "</b> · mode <b>" + esc(rep.get("mode")) + "</b> · registered " + esc(rep.get("registered_at")) + " · family alpha " + esc(rep.get("family_alpha")) + " · events " + esc(rep.get("event_count")) + " · root <code>" + esc((rep.get("root_hash") or "")[:16]) + "…</code> · checkpoint supplied and matched: " + esc(rep.get("checkpoint_matches")) + " · anchor " + esc(rep.get("anchor_status")) + "</p><table><tr><th>claim</th><th>status</th><th>units</th><th>mean Brier improvement</th><th>log e-value current / max</th><th>anytime p bound</th><th>threshold crossed</th><th>invalidated</th><th>allocation</th><th>permission</th></tr>" + claims + "</table><p class=muted>" + esc(rep.get("scope")) + "</p>") if rep else ""}
{"<h2>Warnings</h2><ul>" + warnings + "</ul>" if warnings else ""}
<h2>Links to financial objects</h2>{("<table><tr><th>object</th><th>identity</th><th>result</th></tr>" + link_rows + "</table>") if link_rows else '<p class="muted">no links declared</p>'}<ul>{link_notes}</ul>
<h2>What this establishes and what it does not</h2><ul>{standing}</ul>{"<p class=muted>Kernel limitations:</p><ul>" + lim + "</ul>" if lim else ""}
<p class="muted">{esc(rep.get("not_advice") or NOT_ADVICE)}</p>"""
        return self.page(f"Scientific record {sid}", body)

    def page_notes(self, q) -> str:
        ws = self.server.ws; st = ws.status(); rows = ""
        for cid in st["claims"]:
            s = ws.claim_state(cid)
            for n in (s or {}).get("research_notes", []):
                rows += self._note_row(n).replace("<tr><td>", f'<tr><td><a href="/claim/{esc(urllib.parse.quote(cid, safe=""))}#notes">{esc(cid)}</a><br>', 1)
        body = f"""<p>Every research note in this workspace, across claims: unresolved questions, explanations, next evidence and their corrections. A note is authored text with an actor label; it changes no claim and grants no publication eligibility. Record a note on a claim's page.</p>
<table><tr><th>claim · note</th><th>category</th><th>actor</th><th>version</th><th>unresolved question / explanation</th><th>next evidence</th><th>reason</th><th>evidence</th><th>recorded (local action)</th></tr>{rows or '<tr><td colspan="9" class="muted">no research notes in this workspace</td></tr>'}</table>"""
        return self.page("Research notes", body)

    def page_dataset(self, q) -> str:
        ws = self.server.ws; snap = dataset.build_snapshot(ws); dig = dataset.snapshot_digest(snap); c = snap["counts"]
        prev = export.previous_snapshots(ws); last = next((p for p in reversed(prev) if p["retained"]), None)
        diff = dataset.diff_snapshots(last["snapshot"] if last else None, snap)
        built = q.get("built"); notice = f'<div class="notice">Dataset snapshot export <b>{esc(built)}</b> built. Download it below and verify it in a fresh workspace.</div>' if built and _EXPORT_ID.match(built) else ""
        rows = ""
        for r in snap["rows"]:
            cq = urllib.parse.quote(r["claim_id"], safe=""); s = r["status"]; rv = r["reviewer"]; ot = r["original_target"]
            targets = esc(ot["range"]["low"]) + " – " + esc(ot["range"]["high"]) + " " + esc(ot["unit"]) + " · " + esc(ot["basis"]) + "<br>"
            targets += "".join("<span class=muted>" + esc(x["version_id"]) + ": " + esc(x["range"]["low"]) + " – " + esc(x["range"]["high"]) + "</span><br>" for x in r["revisions"])
            targets += "".join("<span class=muted>" + esc(x["version_id"]) + ": source corrected</span><br>" for x in r["source_corrections"])
            if r["withdrawal"]:
                targets += "<b class=warn>WITHDRAWN</b> (" + esc(r["withdrawal"]["revision_id"]) + ")"
            elig = esc(s["eligibility"][:80]) + ((" (" + esc(s["eligibility_note"]) + ")") if s["eligibility_note"] else "")
            status = ("FICTIONAL" if s["fictional"] else "real source") + "<br>" + ("<span class=warn>RETROSPECTIVE</span>" if s["retrospective"] else "not retrospective") + '<br><span class="muted">eligibility: ' + elig + "</span>"
            outcome = (esc(r["outcome"]["actual"]) + " " + esc(r["outcome"]["unit"])) if r["outcome"] else "<span class=muted>none</span>"
            comp = r["computed"]; direction = (" " + esc(comp["comparison_direction"])) if comp["comparison_direction"] else ""
            computed = "<b>" + esc(comp["result"]) + '</b><br><span class="muted">original ' + esc(comp["original"]) + " · revised " + esc(comp["revised"] or "—") + " · comparison " + esc(comp["comparison"] or "—") + direction + "</span>"
            labels = "<br>".join(esc(l["label"]) + " (" + esc(l["reviewer"][:40]) + "; " + esc(l["attribution"].split(" (")[0]) + ")" for l in rv["labels"]) or "<span class=muted>none</span>"
            labels += ("<br><span class=warn>disagreement: " + esc(len(rv["disagreement"])) + "</span>") if rv["disagreement"] else "<br><span class=muted>no disagreement recorded</span>"
            avail = "<br>".join(esc(x["available_as_of"]) + " <span class=muted>(" + esc(x["availability_precision"].split(" (")[0]) + "; observed " + esc(x["observed_at"] or "—") + ")</span>" for x in r["sources"])
            withheld = "<br>".join(esc(x) for x in r["rights"]["withheld_excerpts"]) or "<span class=muted>none withheld</span>"
            cells = ['<a href="/claim/' + esc(cq) + '">' + esc(r["claim_id"]) + '</a><br><span class="muted">' + esc(r["identifiers"]["current_version"]) + " of " + esc(", ".join(r["identifiers"]["versions"])) + "</span>",
                     esc(r["issuer"]["name"]) + " (" + esc(r["issuer"]["ticker"]) + ')<br><span class="muted">CIK ' + esc(r["issuer"]["cik"]) + "</span>",
                     esc(r["metric"]) + "<br>" + esc(r["fiscal_period"]["label"]) + " (" + esc(r["fiscal_period"]["start"]) + ".." + esc(r["fiscal_period"]["end"]) + ")",
                     status, targets, outcome, computed, labels, "<br>".join(esc(x) for x in r["unresolved_reasons"]) or "—",
                     esc(r["research_notes"]["count"]) + " (" + esc(r["research_notes"]["corrections"]) + " corrections)", avail, withheld,
                     "<br>".join(esc(g) for g in r["coverage_gaps"]) or "—", "<code>" + esc(r["row_digest"][:12]) + "…</code>"]
            rows += "<tr>" + "".join("<td>" + c + "</td>" for c in cells) + "</tr>"
        prev_rows = "".join(f'<tr><td><a href="/exports/{esc(p["export_id"])}.zip">{esc(p["export_id"])}.zip</a></td><td><code>{esc(p["snapshot_digest"])}</code></td><td>{esc(p["rows"])}</td><td>{esc(p["recorded_at"])}</td><td>{"retained" if p["retained"] else "snapshot file missing"}</td></tr>' for p in prev)
        changed = "".join(f'<li>{esc(k)}: {esc(", ".join(v))}</li>' for k, v in diff["changed"].items())
        diff_html = (f'<p>Compared with the last exported snapshot <code>{esc(diff["previous"][:16])}…</code>: added {esc(", ".join(diff["added"]) or "none")}; removed {esc(", ".join(diff["removed"]) or "none")}; changed fields per claim: <ul>{changed or "<li>none</li>"}</ul></p>' if diff["previous"] else '<p class="muted">No earlier exported snapshot to compare with.</p>')
        empty = '<div class="notice"><b>Coverage is empty.</b> This workspace holds no frozen claims, so there are no issuers, rows, outcomes or results to show. Nothing is assumed or sampled.</div>' if snap["empty"] else ""
        body = f"""{notice}<p>A narrow commitments-and-outcomes dataset derived from this workspace's stored records: one row per frozen claim with its identifiers, source versions and lineage, targets and revisions, corrections and withdrawals, disclosed outcome, computed result, reviewer labels and disagreement, unresolved reasons, availability and observation times, rights restrictions, research notes and coverage gaps. Fixture rows are a demonstration; a real-source row is retrospective unless shown otherwise; eligibility is whatever note the workspace holds, never a criteria run. Not a validated dataset product.</p>
{empty}<h2>Snapshot identity</h2><table><tr><th>snapshot digest</th><th>rows</th><th>issuers</th><th>with outcome</th><th>adjudicated</th><th>withdrawn</th><th>incomparable</th><th>fictional / real source</th><th>retrospective</th><th>eligibility recorded</th><th>notes</th><th>withheld excerpts</th></tr>
<tr><td><code>{esc(dig)}</code></td><td>{esc(c["claims"])}</td><td>{esc(c["issuers"])}</td><td>{esc(c["with_outcome"])}</td><td>{esc(c["adjudicated"])}</td><td>{esc(c["withdrawn"])}</td><td>{esc(c["incomparable"])}</td><td>{esc(c["fictional"])} / {esc(c["real_source"])}</td><td>{esc(c["retrospective"])}</td><td>{esc(c["eligibility_recorded"])}</td><td>{esc(c["research_notes"])}</td><td>{esc(c["withheld_excerpts"])}</td></tr></table>
<p class="muted">schema {esc(snap["method"]["dataset_schema"])} · claim schema {esc(snap["method"]["claim_schema"])} · calculator {esc(snap["method"]["calculator"])} · workbench {esc(snap["method"]["workbench"])} · the digest covers the rows, counts, gaps and method only (no generation time) · machine-readable: <a href="/dataset.json">/dataset.json</a></p>
<h2>Rows ({esc(len(snap["rows"]))})</h2><table><tr><th>claim · versions</th><th>issuer</th><th>metric · fiscal period</th><th>status</th><th>original target · revisions · corrections</th><th>outcome</th><th>computed</th><th>reviewer labels · disagreement</th><th>unresolved reasons</th><th>notes</th><th>source availability (precision; observed)</th><th>withheld excerpts</th><th>coverage gaps</th><th>row digest</th></tr>{rows or '<tr><td colspan="14" class="muted">no rows</td></tr>'}</table>
<h2>Coverage gaps and known omissions</h2><ul>{"".join(f"<li>{esc(g)}</li>" for g in snap["coverage_gaps"]) or "<li>no gaps derived (an empty workspace has nothing to cover)</li>"}</ul><p class="muted">Known omissions:</p><ul>{"".join(f"<li>{esc(o)}</li>" for o in snap["known_omissions"])}</ul>
<h2>Calculation rule and supported comparison limits</h2><p>{esc(snap["method"]["comparison_limits"])}</p><p class="muted">{esc(calc.FORMULA)}</p><p class="muted">{esc(calc.NO_INFERENCE)}</p>
<h2>Reproducible snapshots</h2><form class="card" method="post" action="/dataset/export">{self._csrf_field()}<p>Builds a verifiable snapshot zip (every row with the claim content it was derived from). Verify it in a fresh workspace: the verifier re-derives every row and the snapshot identity. Earlier snapshots are retained; the comparison below identifies what changed.</p><button type="submit">Build dataset snapshot export</button></form>
<table><tr><th>download</th><th>snapshot digest</th><th>rows</th><th>built (local action)</th><th>retained</th></tr>{prev_rows or '<tr><td colspan="5" class="muted">no snapshot exported yet</td></tr>'}</table>{diff_html}"""
        return self.page("Dataset coverage", body)

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
        evs = ws.events(); last = evs[-1]["time"]["recorded_at"] if evs else None
        fresh = f'The most recent record here was written {esc(last)}.' if last else "Nothing has been recorded here yet."
        body = f"""{notice}<p>Trace one financial commitment from an exact source through revision, numerical checks, outcome review and an export another researcher can verify. Start at <a href="/source">step 1</a>, or verify a packet from another workspace under <a href="/verify">Verify an export</a>. New here? <a href="/help">Help</a> lists every function with its address.</p>
<p class="muted">This workspace is a local snapshot: it holds only the sources, claims and outcomes registered in it, as of the times shown beside them. It is not a live feed — no filing, price or outcome arrives on its own. {fresh}</p>
<p class="muted">Also: <a href="/notes">research notes</a> (unresolved questions, explanations, next evidence — separate from amendments) and the <a href="/dataset">dataset coverage view</a> derived from this workspace's records.</p>
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
        everything = self.server.ws.events(); idx = availability.index(everything, cut)
        hidden = len([e for e in everything if e["kind"] == "SOURCE_REGISTERED"]) - len(evs)
        def avail_cell(e) -> str:
            ent = idx[e["payload"]["source_id"]]
            fixed = f'<br><span class="warn">corrected to <b>{esc(ent["effective"])}</b></span> <span class="muted">({esc(", ".join(c["payload"]["correction_id"] for c in ent["applied"]))}; the registered value above is retained)</span>' if ent["applied"] else ""
            later = "".join(f'<br><span class="muted">later correction {esc(c["payload"]["correction_id"])} → {esc(c["payload"]["corrected_available_as_of"])}, recorded {esc(c["time"]["recorded_at"])}: not applied at this cutoff</span>' for c in ent["later"])
            return f'<b>{esc(ent["registered"])}</b>{fixed}{later}'
        rows = "".join(f'<tr><td><code>{esc(e["payload"]["source_id"])}</code></td><td>{esc(e["payload"]["source"]["accession"])}<br>{esc(e["payload"]["source"]["form"])}</td><td>{esc(e["payload"]["source"]["filed_at"])}</td><td>{avail_cell(e)}</td><td>{esc(e["time"]["observed_at"])}</td><td>{esc(e["time"]["recorded_at"])}</td><td>{esc(e["payload"]["source"]["rights"])}{" · fictional" if e["payload"]["source"]["fictional"] else ""}</td><td><pre class="excerpt">{esc(e["payload"]["source"]["excerpt"])}</pre><span class="muted">sha256 {esc(e["payload"]["source"]["source_hash"])}</span></td></tr>' for e in evs)
        corr_rows = "".join(f'<tr><td><b>{esc(c["payload"]["correction_id"])}</b>{"<br><span class=warn>recorded after this cutoff — not applied</span>" if c in idx[c["payload"]["source_id"]]["later"] else ""}</td><td><code>{esc(c["payload"]["source_id"])}</code></td><td>{esc(c["payload"]["prior_available_as_of"])}</td><td><b>{esc(c["payload"]["corrected_available_as_of"])}</b><br><span class="muted">{esc(c["payload"]["direction"])}</span></td><td>{esc(c["payload"]["reason"])}</td><td>{esc(c["payload"]["evidence_ref"])}</td><td>{esc(c["payload"]["actor"])}<br><span class="{"warn" if c["payload"]["actor_kind"] == "simulated_test_action" else "muted"}">{esc(c["payload"]["actor_kind"].replace("_", " "))}</span></td><td>{esc(c["time"]["recorded_at"])}</td><td><code>{esc(c["event_hash"][:12])}…</code><br><span class="muted">replaces <code>{esc(c["payload"]["prior_event"][:12])}…</code></span></td></tr>' for c in everything if c["kind"] == availability.KIND)
        done = q.get("corrected"); corr_notice = f'<div class="notice">Availability correction <b>{esc(done)}</b> recorded. The registration it refers to is unchanged; claims citing the source show the corrected view beside their recorded result.</div>' if done and _CORRECTION_ID.match(done) else ""
        AV = "availability"; cur_ref = self._cur(AV, "source_ref")
        ref_opts = "".join(f'<option value="{esc(sid + "@" + ent["effective"])}"{" selected" if sid + "@" + ent["effective"] == cur_ref else ""}>{esc(ent["registration"]["payload"]["source"]["accession"])} · {esc(ent["registration"]["payload"]["source"]["form"])} · filed {esc(ent["registration"]["payload"]["source"]["filed_at"])} · availability now in force {esc(ent["effective"])}{" (registered " + esc(ent["registered"]) + ")" if ent["applied"] else ""}</option>' for sid, ent in availability.index(everything).items())
        corr_html = f"""<h2 id="availability">Correct a source's availability time</h2>{corr_notice}
<p>If the time a registered source became public was entered wrongly, record a correction. It is a new, linked event: the registration, the passage and its digest, the time this workspace observed it, and every frozen claim, outcome and adjudication stay exactly as they were written. Three times are kept apart — the <b>asserted availability</b> (registered, then corrected), the <b>observation</b> by this workspace, and the <b>recording of the correction</b>, which the server stamps itself.</p>
<p><b>Historical views.</b> A correction takes effect for cutoffs at or after the moment it was recorded. A view at an earlier cutoff keeps the value the record held then and lists the correction as a <i>later correction</i> with what it would change — a later correction is never shown as something known at the cutoff, and no historical view is revised silently. Claims citing the source keep their recorded result; the corrected view and anything needing review are shown beside it.</p>
<table><tr><th>correction</th><th>source id</th><th>replaces</th><th>corrected availability</th><th>reason</th><th>evidence reference</th><th>actor</th><th>recorded (local action)</th><th>event · replaces event</th></tr>{corr_rows or '<tr><td colspan="9" class="muted">no availability correction recorded</td></tr>'}</table>
<form class="card" id="form-availability" method="post" action="/source/correct-availability">{self._csrf_field(AV)}
<label>Registered source and the availability now in force</label><select name="source_ref" required><option value="">— choose a registered source —</option>{ref_opts}</select>
<div class="row"><div><label>Corrected availability (UTC, YYYY-MM-DDTHH:MM:SSZ)</label><input type="text" name="corrected_available_as_of" value="{self._val(AV, 'corrected_available_as_of')}"></div><div><label>Actor (attribution label — not authenticated identity; does not establish independent review)</label><input type="text" name="actor" value="{self._val(AV, 'actor')}"></div></div>
<label>Reason for the correction (required)</label><input type="text" name="reason" value="{self._val(AV, 'reason')}">
<label>Evidence reference — where the corrected time comes from, e.g. the EDGAR filing index acceptance line (recorded as text; never fetched)</label><input type="text" name="evidence_ref" value="{self._val(AV, 'evidence_ref')}">
<label><input type="checkbox" name="simulated" value="1"{self._checked(AV, 'simulated')}> This is a simulated test action (automated), not a human's correction</label>
<p class="muted">If someone else corrected this source after you opened the page, your submission is refused as out of date and nothing is written; review their correction and choose the source again.</p>
<button type="submit">Record availability correction</button></form>"""
        A = "register"; V = lambda n, d="": self._val(A, n, d)
        kinds = self._sel("kind", schema.SOURCE_KINDS, self._cur(A, "kind", "filing"), blank=False); rights = self._sel("rights", schema.RIGHTS, self._cur(A, "rights", "FICTIONAL"), blank=False)
        body = f"""<p>Register the exact passage a claim, an amendment or an outcome comes from. The availability timestamp is when the source became public (EDGAR acceptance), never the time you entered it; the workbench records the observation and action times separately. Passages are stored and shown as inert text.</p>
<form class="card" method="get" action="/source"><label>View the sources as they were available at a cutoff (UTC, e.g. 2026-03-01T00:00:00Z) — later sources are hidden, not backdated</label><input type="text" name="as_of" value="{esc(as_of)}"><button type="submit">Apply cutoff</button></form>
{f'<div class="err">{esc(as_of_err)}</div>' if as_of_err else ''}{f'<div class="notice">As-of view at <b>{esc(cut)}</b>: {hidden} source(s) with a later availability are hidden. A correction recorded after this cutoff is listed beside its source but not applied; one recorded at or before it is.</div>' if cut else ''}
<table><tr><th>source id</th><th>accession · form</th><th>filed</th><th>available as of (source; registered, then corrected)</th><th>observed (workspace)</th><th>recorded (local action)</th><th>rights</th><th>passage</th></tr>{rows or '<tr><td colspan="8" class="muted">no sources registered</td></tr>'}</table>
<h2>Register a source</h2><form class="card" id="form-register" method="post" action="/source/register">{self._csrf_field(A)}
<div class="row"><div><label>Kind</label>{kinds}</div><div><label>Form</label><input type="text" name="form" value="{V('form')}" placeholder="8-K EX-99.1"></div><div><label>Accession (EDGAR) or publisher id (PREFIX:publisher:id) for a non-filing</label><input type="text" name="accession" value="{V('accession')}"></div><div><label>URL (optional)</label><input type="text" name="url" value="{V('url')}"></div></div>
<div class="row"><div><label>Filed at (date)</label><input type="date" name="filed_at" value="{V('filed_at')}"></div><div><label>Available as of (UTC, YYYY-MM-DDTHH:MM:SSZ)</label><input type="text" name="available_as_of" value="{V('available_as_of')}"></div><div><label>Observed at (UTC, optional; default now)</label><input type="text" name="observed_at" value="{V('observed_at')}"></div><div><label>Rights</label>{rights}</div></div>
<label>Exact passage (excerpt)</label><textarea name="excerpt" rows="3">{V('excerpt')}</textarea>
<label><input type="checkbox" name="fictional" value="1"{self._checked(A, 'fictional', True)}> Fictional source (demonstration data)</label>
<button type="submit">Register source</button></form>
<h2>Register from an ingestion record</h2><form class="card" id="form-import" method="post" action="/source/import">{self._csrf_field('import')}
<p>The bounded ingestion tool (<code>python -m v8.workbench.ingest</code>; one allow-listed URL per run) runs outside this server, which has no network access of its own. On success it writes <code>&lt;label&gt;.source.json</code> and <code>&lt;label&gt;.provenance.json</code>; on failure it prints <code>[ingest] REFUSED: reason</code>, exits 2 and writes no source record — fix the URL, accession or passage pattern it names and run it again. Paste the <code>.source.json</code> content here to register the passage byte for byte (at most {IMPORT_LIMIT // 1024} KB; the record is data — nothing in it is fetched or executed, and the passage digest is recomputed).</p>
<label>Ingestion source record (JSON)</label><textarea name="record" rows="6">{self._val('import', 'record')}</textarea>
<label>Observed at — the provenance record's retrieved_at (UTC, optional; default now)</label><input type="text" name="record_observed_at" value="{self._val('import', 'record_observed_at')}">
<button type="submit">Register ingested source</button></form>{corr_html}"""
        return self.page("Step 1 — Source", body)

    def page_claim_new(self, q) -> str:
        A = "freeze"; V = lambda n, d="": self._val(A, n, d)
        scales = self._sel("scale_as_stated", money.SCALES, self._cur(A, "scale_as_stated", "millions"), blank=False); bases = self._sel("basis", schema.BASES, self._cur(A, "basis")); rules = self._sel("resolution_rule", list(schema.RESOLUTION_RULES), self._cur(A, "resolution_rule"))
        no_source = "" if self._sources() else '<div class="notice"><b>No source is registered in this workspace yet.</b> A claim must cite the exact registered passage it comes from: <a href="/source">register the source first (step 1)</a>, or load a fictional fixture from the <a href="/">Workspace</a> page. A freeze without a source is refused and nothing is written.</div>'
        body = f"""{no_source}<p>Freeze a fully specified commitment. Every comparability field is mandatory; a missing fiscal period, currency, basis or resolution rule blocks the freeze and every reason is listed. An amendment later creates a new version; the frozen original is never rewritten.</p>
<form class="card" id="form-freeze" method="post" action="/claim/freeze">{self._csrf_field(A)}
<div class="row"><div><label>Claim id</label><input type="text" name="claim_id" value="{V('claim_id')}" placeholder="ZZFX-FY2026-REV-GUIDE"></div><div><label>Issuer name</label><input type="text" name="issuer_name" value="{V('issuer_name')}"></div><div><label>Ticker</label><input type="text" name="issuer_ticker" value="{V('issuer_ticker')}"></div><div><label>CIK (10 digits)</label><input type="text" name="issuer_cik" value="{V('issuer_cik')}"></div></div>
<div class="row"><div><label>Metric</label><input type="text" name="metric" value="{V('metric', 'revenue')}"></div><div><label>Range low (in units, exact)</label><input type="text" name="range_low" value="{V('range_low')}"></div><div><label>Range high (in units, exact)</label><input type="text" name="range_high" value="{V('range_high')}"></div><div><label>Scale as stated in the source</label>{scales}</div></div>
<div class="row"><div><label>Currency (ISO-4217)</label><input type="text" name="currency" value="{V('currency', 'USD')}"></div><div><label>Measurement unit (= currency for money)</label><input type="text" name="unit" value="{V('unit', 'USD')}"></div><div><label>Accounting basis</label>{bases}</div><div><label>Resolution rule</label>{rules}</div></div>
{self._period_fields(A)}
<label>Statement (as made)</label><textarea name="statement" rows="2">{V('statement')}</textarea>
{self._source_select(A)}
<label><input type="checkbox" name="fictional" value="1"{self._checked(A, 'fictional', True)}> Fictional claim (demonstration data)</label>
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
        later = availability.later_at(full, availability.index(ws.events(), cut), cut) if cut else []
        if st is None:
            first = full["versions"][0]["claim"]["source"]; held = availability.index(ws.events(), cut).get(availability.source_id(first), {}).get("effective") or first["available_as_of"]
            return self.page(cid, f'<div class="notice">As-of <b>{esc(cut)}</b>: nothing about this claim was available yet (its first source became available {esc(held)}{"" if held == first["available_as_of"] else ", corrected from the registered " + esc(first["available_as_of"])}).</div>{self._later_corrections_html(later, cut)}<p><a href="/claim/{esc(urllib.parse.quote(cid, safe=""))}">Back to the current view</a></p>')
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
        def avail(s: dict) -> str:
            eff = availability.effective_for(st, s)
            return f'<b>{esc(s["available_as_of"])}</b>' + (f'<br><span class="warn">corrected to <b>{esc(eff)}</b></span><br><span class="muted">the registered value is retained</span>' if eff != s["available_as_of"] else "")
        src_rows = ""
        for v in st["versions"]:
            s = v["claim"]["source"]
            src_rows += f'<tr><td>{esc(v["version_id"])} {esc(v["type"])}</td><td>{esc(s["accession"])} · {esc(s["form"])}</td><td>{esc(s["filed_at"])}</td><td>{avail(s)}</td><td>{times_with_source(v["time"], s)}</td><td><pre class="excerpt">{esc(s["excerpt"])}</pre><span class="muted">sha256 {esc(s["source_hash"])} · rights {esc(s["rights"])}</span></td></tr>'
        if st["withdrawn"]:
            s = st["withdrawn"]["source"]; src_rows += f'<tr><td>{esc(st["withdrawn"]["revision_id"])} WITHDRAWN</td><td>{esc(s["accession"])} · {esc(s["form"])}</td><td>{esc(s["filed_at"])}</td><td>{avail(s)}</td><td>{times_with_source(st["withdrawn"]["time"], s)}</td><td><pre class="excerpt">{esc(s["excerpt"])}</pre></td></tr>'
        if st["outcome"]:
            s = st["outcome"]["source"]; src_rows += f'<tr><td>OUTCOME</td><td>{esc(s["accession"])} · {esc(s["form"])}</td><td>{esc(s["filed_at"])}</td><td>{avail(s)}</td><td>{times_with_source(st["outcome"]["_time"], s)}</td><td><pre class="excerpt">{esc(s["excerpt"])}</pre><span class="muted">sha256 {esc(s["source_hash"])}</span></td></tr>'
        # --- 2 versions
        ver_rows = "".join(f'<tr><td><b>{esc(v["version_id"])}</b><br>{esc(v["type"])}</td><td>{esc(v["claim"]["range"]["low"])} – {esc(v["claim"]["range"]["high"])} {esc(v["claim"]["unit"])}<br><span class="muted">({esc(money.as_stated(money.parse_amount(v["claim"]["range"]["low"]), v["claim"]["scale_as_stated"]))} – {esc(money.as_stated(money.parse_amount(v["claim"]["range"]["high"]), v["claim"]["scale_as_stated"]))})</span></td><td>{esc(v["claim"]["currency"])} / {esc(v["claim"]["unit"])}</td><td>{esc(v["claim"]["basis"])}</td><td>{esc(v["claim"]["fiscal_period"]["label"])} ({esc(v["claim"]["fiscal_period"]["type"])} {esc(v["claim"]["fiscal_period"]["start"])}..{esc(v["claim"]["fiscal_period"]["end"])})</td><td>{esc(v["claim"]["resolution_rule"])}</td><td>{esc(v["claim"]["stated_at"])}</td><td><code>{esc(v["claim"]["_digest"][:16])}…</code>{"<br><span class=muted>supersedes " + esc(v.get("supersedes", "")[:16]) + "…</span>" if v.get("supersedes") else ""}</td><td>{esc(v.get("reason") or "")}</td></tr>' for v in st["versions"])
        # --- 3 comparison
        if cmp is None:
            cmp_html = '<p class="muted">No revision yet: nothing to compare.</p>'
        elif cmp["comparable"]:
            cmp_html = f'<table><tr><th></th><th>original ({esc(orig_eff["version_id"])})</th><th>revised ({esc(revised[-1]["version_id"])})</th><th>delta (revised − original)</th></tr><tr><td>low</td><td>{esc(cmp["a"]["range"]["low"])}</td><td>{esc(cmp["b"]["range"]["low"])}</td><td>{esc(cmp["low_delta"])}</td></tr><tr><td>high</td><td>{esc(cmp["a"]["range"]["high"])}</td><td>{esc(cmp["b"]["range"]["high"])}</td><td>{esc(cmp["high_delta"])}</td></tr><tr><td>midpoint delta</td><td colspan="3">{esc(cmp["midpoint_delta"])} {esc(cmp["unit"])}</td></tr><tr><td>width</td><td>{esc(cmp["width_a"])}</td><td>{esc(cmp["width_b"])}</td><td>{esc(cmp["width_delta"])}</td></tr><tr><td>overlap</td><td colspan="3">{esc(cmp["overlap"])}</td></tr><tr><td>direction</td><td colspan="3"><b>{esc(cmp["direction"])}</b> · metrics comparable: <span class="ok">COMPARABLE</span></td></tr></table><p class="muted">{esc(cmp["note"])}</p>'
        else:
            reasons_li = "".join("<li>" + esc(r["reason"]) + "</li>" for r in cmp["reasons"])
            cmp_html = f'<p class="bad">INCOMPARABLE</p><ul>{reasons_li}</ul><p class="muted">A metric or accounting-basis change yields INCOMPARABLE; no delta is computed.</p>'
        if cmp is not None:
            # the amendment's own notes (explanation / next evidence / preserved source discrepancy) are shown in BOTH branches, linked to their version
            cmp_html += "".join(self._version_notes_html(v) for v in revised)
        cmp_html += self._notes_block(st, full, cut, "comparison", ("unresolved_question", "explanation", "next_evidence"), "Research notes on this comparison")
        # --- 4 calculation
        def ev_html(e, title):
            if e is None:
                return ""
            cls = "ok" if e["result"] == "IN_RANGE" else "bad" if e["result"] == "OUT_OF_RANGE" else "warn"
            rs = "".join(f'<li>{esc(r["code"])}: {esc(r["reason"])}</li>' for r in e["reasons"])
            return f'<div class="card"><h3>{esc(title)} — <span class="{cls}">{esc(e["result"])}</span></h3><table><tr><th>inputs</th><td>low {esc(e["inputs"]["low"])} · high {esc(e["inputs"]["high"])} · actual {esc(e["inputs"]["actual"])} · {esc(e["inputs"]["currency"])}/{esc(e["inputs"]["unit"])} · {esc(e["inputs"]["basis"])} · {esc(e["inputs"]["fiscal_period"]["label"])} · {esc(e["inputs"]["metric"])}</td></tr><tr><th>formula</th><td>{esc(e["formula"])}</td></tr><tr><th>rule · tolerance</th><td>{esc(res["rule"])} · {esc(calc.CALCULATOR)} · tolerance: none (exact decimal arithmetic; both bounds inclusive)</td></tr><tr><th>missing inputs</th><td>{"a comparable disclosed outcome (none recorded)" if e["inputs"]["actual"] is None else "none"}</td></tr><tr><th>midpoint</th><td>{esc(e.get("midpoint"))}</td></tr><tr><th>delta vs midpoint</th><td>{esc(e.get("delta_vs_midpoint"))}</td></tr><tr><th>distance outside</th><td>{esc(e.get("distance_outside"))}</td></tr><tr><th>source links</th><td>claim {esc(e["source_links"]["claim_source"])} · outcome {esc(e["source_links"]["outcome_source"])}</td></tr>{f"<tr><th>reasons</th><td><ul>{rs}</ul></td></tr>" if rs else ""}</table></div>'
        err_divs = "".join("<div class=err>" + esc(r["code"]) + ": " + esc(r["reason"]) + "</div>" for r in res["reasons"])
        calc_html = f'<p>Overall: <b class="{"ok" if res["result"] == "IN_RANGE" else "bad" if res["result"] == "OUT_OF_RANGE" else "warn"}">{esc(res["result"])}</b> · comparison permitted: {esc(res["comparison_permitted"])} · rule {esc(res["rule"])}</p>{err_divs}{ev_html(res["original"], "Original range" + (" (corrected source)" if res["uses_corrected_range"] else ""))}{ev_html(res["revised"], "Revised range")}<p class="notice">{esc(res["no_inference"])}</p>'
        nxt = {"PENDING_OUTCOME": "the claim stays unresolved until a comparable disclosed outcome exists. When the outcome is public, register its passage (step 1) and record it with the form below; until then a research note can say what evidence is awaited. Nothing is estimated in the meantime.",
               "WITHDRAWN_BEFORE_OUTCOME": "a withdrawn commitment takes no outcome and is not a miss. A research note can record what remains unexplained; the withdrawal itself is permanent history."}.get(res["result"])
        if nxt is None and res["result"] in calc.UNRESOLVED:
            nxt = "no pass or miss is computed while the inputs are incompatible (every mismatch is listed above). If the source itself was wrong, record a CORRECTED_SOURCE amendment citing the corrected passage; if the outcome was recorded on another basis, unit or period, record the comparable outcome. Earlier records are kept either way."
        if nxt:
            calc_html += f'<p><b>Unresolved — next:</b> {esc(nxt)}</p>'
        if res["result"] in ("PENDING_OUTCOME", "WITHDRAWN_BEFORE_OUTCOME"):
            calc_html += self._notes_block(st, full, cut, "calculation", None, "Research notes (the outcome is missing or the commitment was withdrawn: a note explains, it never resolves or reopens)")
        # --- 5 history
        hidden = len(full["events"]) - len(st["events"])
        hist_rows = "".join(f'<tr><td>{esc(e["seq"])}</td><td>{esc(e["kind"])}</td><td>{esc(e["payload"].get("version_id") or e["payload"].get("export_id") or e["payload"].get("label") or "")}</td><td><b>{esc(e["time"]["source_available_as_of"] or "—")}</b></td><td>{esc(e["time"]["observed_at"])}</td><td>{esc(e["time"]["recorded_at"])}</td><td><code>{esc(e["event_hash"][:16])}…</code></td><td><code>{esc(e["op_id"])}</code></td></tr>' for e in st["events"])
        hist_html = f"""<form class="card" method="get" action="/claim/{esc(cq)}"><label>Replay as of a cutoff (UTC). Events whose source became available later are hidden; later information never rewrites the original claim or an earlier as-of result.</label><input type="text" name="as_of" value="{esc(as_of_raw)}" placeholder="2026-03-01T00:00:00Z"><button type="submit">Replay</button> <a href="/claim/{esc(cq)}">current view</a></form>
{f'<div class="err">{esc(as_of_err)}</div>' if as_of_err else ''}{f'<div class="notice">As-of view at <b>{esc(cut)}</b>: {hidden} later event(s) hidden. Result at this cutoff: <b>{esc(res["result"])}</b>; versions visible: {esc(", ".join(v["version_id"] for v in st["versions"]))}.</div>' if cut else ''}
<table><tr><th>seq</th><th>event</th><th>ref</th><th>source available as of</th><th>observed (workspace)</th><th>recorded (local action)</th><th>event hash</th><th>operation id</th></tr>{hist_rows}</table>"""
        # --- 5b research notes (separate action; never an amendment)
        notes_html = self._notes_section(cid, cq, st, full, cut)
        # --- 6 adjudication
        adj_rows = "".join(f'<tr><td>{esc(a["reviewer"])}</td><td>{esc(a["rule"])}</td><td><b>{esc(a["label"])}</b>{" <span class=warn>DISPUTED</span>" if a["disputed"] else ""}</td><td>{esc(a["computed_result"])}</td><td>{esc(a["reason"])}</td><td>{esc(a["conflicts"] or "—")}</td><td>{"".join(f"<code>{esc(h[:12])}…</code> " for h in a["evidence"])}</td><td>{esc(a["time"]["recorded_at"])}</td></tr>' for a in st["adjudications"])
        A = "adjudicate"; V = lambda n, d="": self._val(A, n, d)
        ev_opts = "".join(f'<label><input type="checkbox" name="evidence" value="{esc(e["event_hash"])}"{self._checked(A, "evidence", value=e["event_hash"])}> {esc(e["seq"])} {esc(e["kind"])} <code>{esc(e["event_hash"][:12])}…</code></label>' for e in full["events"] + self._correction_events(full) if e["kind"] != "ADJUDICATION_RECORDED")
        labels = self._sel("label", calc.RESULTS, self._cur(A, "label", res["result"]), blank=False)
        blk = availability.block(full)
        adj_corrected = f'<div class="notice"><b>The availability of a cited source was corrected.</b> Computed as recorded: <b>{esc(blk["corrected_view"]["recorded_result"])}</b>; under the corrected availability: <b>{esc(blk["corrected_view"]["result"])}</b>. Earlier adjudications are retained unchanged. A label that differs from the as-recorded result is recorded as Disputed with your reason; the correction event can be ticked as evidence.</div>' if blk and blk["corrected_view"]["result_changes"] else ""
        adj_form = f"""{adj_corrected}<form class="card" id="form-adjudicate" method="post" action="/claim/{esc(cq)}/adjudicate">{self._csrf_field(A)}<h3>Record an adjudication</h3><p class="muted">A review is an append-only record with the reviewer label you type (attribution, not authenticated identity). If your label differs from the computed result, tick Disputed and give the reason: both stay visible and the computed result is not changed. A correction is a further adjudication; earlier ones are retained.</p><div class="row"><div><label>Reviewer identity</label><input type="text" name="reviewer" value="{V('reviewer')}"></div><div><label>Rule applied</label><input type="text" name="rule" value="{V('rule', res['rule'])}"></div><div><label>Label (computed: {esc(res["result"])})</label>{labels}</div></div><fieldset><legend>Evidence (events relied on)</legend>{ev_opts}</fieldset><label>Reason</label><textarea name="reason" rows="2">{V('reason')}</textarea><label>Conflicts (who disagrees and why; kept visible)</label><input type="text" name="conflicts" value="{V('conflicts')}"><label><input type="checkbox" name="disputed" value="1"{self._checked(A, 'disputed')}> Disputed — my label differs from the computed result and I explain why (a differing label without this flag is refused)</label><button type="submit">Record adjudication</button></form>"""
        # --- amendments / outcome forms
        cur = st["current"]["claim"]
        A = "amend"; V = lambda n, d="": self._val(A, n, d)
        bases = self._sel("basis", schema.BASES, self._cur(A, "basis", cur["basis"])); types = self._sel("amend_type", ("REVISED", "WITHDRAWN", "CORRECTED_SOURCE"), self._cur(A, "amend_type", "REVISED"), blank=False)
        amend_form = "" if full["withdrawn"] else f"""<form class="card" id="form-amend" method="post" action="/claim/{esc(cq)}/amend">{self._csrf_field(A)}<h3>Create an amendment</h3><p class="muted">An amendment is a new version appended to the history; the frozen original and every earlier version stay exactly as they were, and a freeze cannot be undone.</p><div class="row"><div><label>Type</label>{types}</div><div><label>New range low</label><input type="text" name="range_low" value="{V('range_low', cur['range']['low'])}"></div><div><label>New range high</label><input type="text" name="range_high" value="{V('range_high', cur['range']['high'])}"></div><div><label>Basis</label>{bases}</div></div><div class="row"><div><label>Currency</label><input type="text" name="currency" value="{V('currency', cur['currency'])}"></div><div><label>Unit</label><input type="text" name="unit" value="{V('unit', cur['unit'])}"></div><div><label>Metric</label><input type="text" name="metric" value="{V('metric', cur['metric'])}"></div></div>{self._period_fields(A, "fp_", cur["fiscal_period"])}<label>Statement (optional; keeps the current one when empty)</label><input type="text" name="statement" value="{V('statement')}"><label>Reason (required)</label><input type="text" name="reason" value="{V('reason')}">{self._source_select(A)}<label>Unresolved explanation (a note, not causal evidence)</label><input type="text" name="explanation_unresolved" value="{V('explanation_unresolved')}"><label>Next evidence needed</label><input type="text" name="next_evidence" value="{V('next_evidence')}"><label>Source discrepancy (verbatim; e.g. the amendment restates the prior range differently from the original — preserved, never corrected)</label><input type="text" name="source_discrepancy" value="{V('source_discrepancy')}"><button type="submit">Record amendment</button></form>"""
        A = "outcome"; V = lambda n, d="": self._val(A, n, d)
        out_form = f"""<form class="card" id="form-outcome" method="post" action="/claim/{esc(cq)}/outcome">{self._csrf_field(A)}<h3>Record the disclosed outcome</h3><div class="row"><div><label>Actual (in units, exact)</label><input type="text" name="actual" value="{V('actual')}"></div><div><label>Currency</label><input type="text" name="currency" value="{V('currency', cur['currency'])}"></div><div><label>Unit</label><input type="text" name="unit" value="{V('unit', cur['unit'])}"></div><div><label>Basis</label>{self._sel("basis", schema.BASES, self._cur(A, "basis", cur["basis"]))}</div><div><label>Metric</label><input type="text" name="metric" value="{V('metric', cur['metric'])}"></div></div>{self._period_fields(A, "fp_", cur["fiscal_period"])}{self._source_select(A)}<label><input type="checkbox" name="comparable" value="1"{self._checked(A, 'comparable', True)}> Recorder declares the outcome comparable (the calculator re-checks every field regardless)</label><button type="submit">Record outcome</button></form>"""
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
<h2 id="source">1 Source</h2><table><tr><th>version</th><th>accession · form</th><th>filed</th><th>available as of</th><th>times</th><th>passage</th></tr>{src_rows}</table>{self._availability_html(st, cut, later)}
<h2 id="claim">2 Typed claim — versions</h2><table><tr><th>version</th><th>range</th><th>currency / unit</th><th>basis</th><th>fiscal period</th><th>rule</th><th>stated</th><th>digest</th><th>reason</th></tr>{ver_rows}</table>{amend_form}
<h2 id="comparison">3 Comparison — original vs revised</h2>{cmp_html}
<h2 id="calculation">4 Calculation</h2>{calc_html}{out_form if not full["withdrawn"] else ""}
<h2 id="history">5 History — as-of replay</h2>{hist_html}
<h2 id="notes">Research notes — unresolved evidence (separate from amendments)</h2>{notes_html}
<h2 id="sci">Scientific records linked to this claim</h2>{self._sci_linked_html(full)}
<h2 id="adjudication">6 Adjudication</h2><table><tr><th>reviewer</th><th>rule</th><th>label</th><th>computed</th><th>reason</th><th>conflicts</th><th>evidence</th><th>recorded</th></tr>{adj_rows or '<tr><td colspan="8" class="muted">no adjudication recorded; the claim stays unresolved</td></tr>'}</table>{adj_form}
<h2 id="export">7 Reproducible export</h2>{exp_html}"""
        return self.page(cid, body, claim_id=cid)

    def page_verify(self, q, result: dict | None, problem: str | None = None) -> str:
        res_html = f'<div class="err"><b>Nothing was verified.</b> {esc(problem)}</div>' if problem else ""
        if result is not None:
            cls = "ok" if result["result"] == "SUCCESS" else "bad"
            checks = "".join(f'<tr><td>{esc(c.get("check"))}</td><td>{esc(c.get("path") or c.get("version") or c.get("seq") or "")}</td><td class="{"ok" if c.get("ok") else ("muted" if c.get("ok") is None else "bad")}">{esc({True: "ok", False: "FAIL", None: "n/a"}[c.get("ok")])}</td><td>{esc(c.get("note") or c.get("observed") or c.get("missing") or "")}</td></tr>' for c in result["checks"])
            rc = result.get("recompute") or {}
            recomp = ("<p>Recomputed: <b>" + esc(rc["result"]) + "</b> · original " + esc(rc.get("original")) + " · revised " + esc(rc.get("revised")) + " · Δ original midpoint " + esc(rc.get("delta_vs_original_midpoint")) + " · Δ revised midpoint " + esc(rc.get("delta_vs_revised_midpoint")) + " · comparison " + esc(rc.get("comparison")) + (" · rows " + esc(rc.get("rows")) + " · snapshot " + esc(str(rc.get("snapshot_digest", ""))[:16]) + "…" if rc.get("result") == "DATASET" else "") + "</p>") if rc else ""
            nxt = {"SUCCESS": "Nothing more is needed. The verification is recorded in this workspace's journal (PACKET_VERIFIED); the packet's content was not merged into this workspace.",
                   "MISMATCH": "This packet is rejected: its bytes or its recomputed results differ from what it declares (the first discrepancy is named above). Do not rely on it. Ask the sender to build the export again and transfer the zip unchanged, then verify the new file here. A verifier never repairs a packet.",
                   "UNSUPPORTED": "This workbench cannot interpret the file (the reason is named above); nothing was imported or reinterpreted. Check that it is an export zip built by a YUCLAW workbench and that this installation is not older than the one that built it."}.get(result["result"], "")
            res_html = f'<h2>Result: <span class="{cls}">{esc(result["result"])}</span></h2><p>{esc(result.get("first_discrepancy") or result.get("meaning") or "")}</p><p><b>Next:</b> {esc(nxt)}</p><p>zip sha256 <code>{esc(result["zip_sha256"])}</code> · canonical digest <code>{esc(result["canonical_digest"])}</code> · claim {esc(result["claim_id"])}</p>{recomp}<table><tr><th>check</th><th>item</th><th>ok</th><th>detail</th></tr>{checks}</table>'
        body = f"""<p>Upload an export zip produced by another workspace. The archive is read in memory within fixed bounds (no extraction), unsafe member names and symlinks are refused, every digest and length is checked, the canonical content is re-serialized, claim digests and event hashes are re-derived, and the calculations are recomputed from the packed versions and outcome. Imported content is data: it is never executed, fetched or merged into this workspace's claims.</p>
<form class="card" method="post" action="/verify" enctype="multipart/form-data">{self._csrf_field()}<label>Export zip</label><input type="file" name="packet"><button type="submit">Verify</button></form>{res_html}"""
        return self.page("Verify an export — fresh workspace", body)

    def page_help(self, q) -> str:
        ws = self.server.ws; claims = ws.status()["claims"]; o = self.server.origin
        links = [("/", "Workspace overview — claims, computed results, fictional fixtures"), ("/source", "1 Source — register a passage or an ingestion record; as-of view"), ("/source#availability", "1 Source — correct a wrong availability time with a linked event (the registration is never edited)"), ("/claim/new", "2 Typed claim — save and freeze a commitment"),
                 ("/notes", "Research notes — every note across claims"), ("/dataset", "Dataset coverage — rows, snapshot identity, snapshot export"), ("/dataset.json", "Dataset snapshot, machine-readable"),
                 ("/sci", "Scientific report / replay"), ("/verify", "Verify an export (use a fresh workspace)"), ("/journal", "Journal — the append-only event log"),
                 ("/help/data", "Data dictionary and dataset card — every stored field, the three times, rights, prohibited interpretations")]
        idx = "".join(f'<li><a href="{esc(h)}">{esc(o + h)}</a> — {esc(t)}</li>' for h, t in links)
        per_claim = "".join(f'<li><a href="/claim/{esc(urllib.parse.quote(c, safe=""))}">{esc(c)}</a>: ' + " · ".join(f'<a href="/claim/{esc(urllib.parse.quote(c, safe=""))}#{esc(k)}">{esc(lbl)}</a>' for k, lbl in STEPS + [("notes", "Research notes")]) + "</li>" for c in claims)
        guide = GUIDE_PATH.read_text(encoding="utf-8") if GUIDE_PATH.is_file() else "The packaged operator guide is missing from this installation."
        body = f"""<p>Where every enabled function is in this running workbench ({esc(o)}), followed by the packaged startup and operator guide. This workspace is a local snapshot of what was registered here and when; it is not a live feed and nothing in it updates on its own.</p>
<h2>Functions in this workspace</h2><ul>{idx}</ul>
<h2>Steps 3–7 and research notes, per claim</h2>{("<ul>" + per_claim + "</ul>") if per_claim else '<p class="muted">No claim is frozen in this workspace yet. Load a fictional fixture on the <a href="/">Workspace</a> page or start at <a href="/source">step 1</a>; each claim page then carries steps 3–7.</p>'}
<h2>Startup and operator guide</h2><p class="muted">Shown as plain text exactly as packaged (<code>v8/workbench/resources/OPERATOR_GUIDE.md</code>). The port numbers in it are examples; this server's address is {esc(o)}.</p><div class="guide">{esc(guide)}</div>"""
        return self.page("Help — functions and operator guide", body)

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

    def post_import(self, form, op_id):
        """Register the source record written by the bounded ingestion tool. The record is data: strict JSON of bounded
        size, only the source fields, validated by the same contract as a typed registration (the passage digest must
        equal sha256 of the excerpt). Nothing in it is opened, fetched or executed."""
        text = form.get("record", "")
        if not text.strip():
            raise ContractError("ingestion record: paste the content of the <label>.source.json file the ingestion tool wrote (if the tool printed REFUSED, no record exists — fix what it names and run it again)")
        if len(text.encode("utf-8")) > IMPORT_LIMIT:
            raise ContractError(f"ingestion record: larger than {IMPORT_LIMIT} bytes; a source record holds one passage, not a document")
        try:
            raw = json.loads(text, object_pairs_hook=sci_adapter._reject_duplicates, parse_constant=sci_adapter._reject_constant)
        except (ValueError, sci_adapter.InputError) as exc:
            raise ContractError(f"ingestion record: not valid JSON ({exc}); paste the whole .source.json file unchanged") from None
        if not isinstance(raw, dict):
            raise ContractError("ingestion record: expected one JSON object (the .source.json file), not a list or a value")
        extra = sorted(set(raw) - set(schema.REQUIRED_SOURCE))
        if extra:
            raise ContractError(f"ingestion record: unsupported field(s) {', '.join(extra[:8])}; paste the .source.json file, not the .provenance.json file")
        self.server.ws.register_source(raw, op_id=op_id, observed_at=_norm_ts(form.get("record_observed_at"), "observed_at"))
        return self._redirect("/source")

    def post_availability(self, form, op_id):
        """Record a source-availability correction. The select carries the source id and the availability the page showed for
        it; if another correction landed since, the store refuses this one as out of date and nothing is written."""
        sid, sep, expected = form.get("source_ref", "").rpartition("@")
        if not sep or not sid:
            raise ContractError("source availability cannot be corrected: source_ref: choose the registered source whose availability is wrong; registered sources are listed in the form")
        raw = {"corrected_available_as_of": _norm_ts(form.get("corrected_available_as_of"), "correction.corrected_available_as_of") or "", "reason": form.get("reason", ""),
               "evidence_ref": form.get("evidence_ref", ""), "actor": form.get("actor", "").strip(), "simulated": form.get("simulated") == "1"}
        ev, _ = self.server.ws.correct_source_availability(sid, raw, expected_prior=expected, op_id=op_id)
        return self._redirect(f"/source?corrected={ev['payload']['correction_id']}#availability")

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

    def post_note(self, cid, form, op_id):
        body = self._last_body_qs
        raw = {"category": form.get("category", ""), "actor": form.get("actor", "").strip(), "reason": form.get("reason", ""), "unresolved_question": form.get("unresolved_question", ""), "next_evidence": form.get("next_evidence", ""),
               "version_ref": form.get("version_ref") or None, "evidence": [v for v in body.get("evidence", []) if re.match(r"^[0-9a-f]{64}$", v)], "supersedes_note": form.get("supersedes_note") or None, "simulated": form.get("simulated") == "1"}
        self.server.ws.record_note(cid, raw, op_id=op_id)
        return self._redirect(f"/claim/{urllib.parse.quote(cid, safe='')}#notes")

    def post_sci(self, form, op_id):
        ex = form.get("example", ""); raw = form.get("input", "")
        if ex:
            if not _SCI_EXAMPLE.match(ex) or not (SCI_EXAMPLES_DIR / f"{ex}.json").is_file() or ex == "template_manifest":
                raise ContractError("example: unknown packaged example")
            raw = (SCI_EXAMPLES_DIR / f"{ex}.json").read_text(encoding="utf-8")
        actor = form.get("actor", "").strip()
        if not actor:
            raise ContractError("actor: an attribution label is required (it is not authenticated identity)")
        try:
            env = sci_adapter.parse_input(raw)
        except sci_adapter.InputError as exc:
            raise ContractError(f"scientific input refused: {exc}") from None
        cid = form.get("claim_id") or None
        if cid and not _CLAIM_ID.match(cid):
            raise ContractError("claim_id: invalid")
        if cid and env.get("links") is None:
            env["links"] = {"claim_id": cid}
        elif cid and "claim_id" not in env["links"]:
            env["links"]["claim_id"] = cid
        link_cid = (env.get("links") or {}).get("claim_id") or None
        res = sci_adapter.classify(env, self.server.ws); ident = sci_adapter.input_identity(env)
        lab = form.get("label", "").strip()[:200] or env.get("label")
        payload = {"input": env, **ident, "status": res["status"], "replay_status": res["replay_status"], "reasons": res["reasons"], "report": res["report"], "report_digest": res["report_digest"], "root_hash": res["root_hash"],
                   "links": res["links"], "warnings": res["warnings"], "kernel": res["kernel"], "standing": res["standing"], "actor": actor, "actor_kind": "simulated_test_action" if form.get("simulated") == "1" else "attribution_label", "label": lab}
        link_target = link_cid if (res["links"].get("claim") or {}).get("result") == "VERIFIED_EXISTS" else None
        ev, _ = self.server.ws.record_sci(payload, claim_id=link_target, op_id=op_id)
        return self._redirect(f"/sci/{ev['payload']['sci_id']}")

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
            self.close_connection = True          # an oversized body was not read; never parse its bytes as the next request
            return self._send(413, self.page_verify({}, None, f"The upload was missing or larger than {UPLOAD_LIMIT // (1024 * 1024)} MB, the most an export zip can be. Choose the export zip itself (exp-….zip as downloaded), not a folder or another archive, and submit again."), extra={"Connection": "close"})
        try:
            mp = Multipart(ct, body)
        except ContractError as exc:
            return self._text(400, f"refused: {exc}")
        if not hmac.compare_digest(mp.fields.get("csrf", ""), self.server.csrf_for(self._sess)):
            return self._text(403, "refused: CSRF token invalid; nothing was written")
        op_id = mp.fields.get("op_id", "")
        if "packet" not in mp.files or not mp.files["packet"][1]:
            return self._send(422, self.page_verify({}, None, "No file was chosen (or the file is empty). Choose the export zip as downloaded from the other workspace and submit again."))
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
