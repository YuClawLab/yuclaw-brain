"""Shared helpers for the V8-014 module tests: a real loopback server, separate authenticated browser-like clients,
fictional fixtures. Every principal here is an AUTOMATED TEST FIXTURE — never a person, a reviewer or an owner decision."""
import hashlib, http.client, io, json, pathlib, re, tempfile, threading, urllib.parse, zipfile

REPO = pathlib.Path(__file__).resolve().parents[1]
import sys
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from v8.workbench import schema, server as S, store          # noqa: E402
from v8.workbench.modules import authz, core                 # noqa: E402

FIX = REPO / "v8" / "workbench" / "resources" / "fixtures"


def workspace(name="ws"):
    return store.Workspace(pathlib.Path(tempfile.mkdtemp(prefix="v14t-")) / name)


def principal(ws, pid, caps, by=None):
    P = authz.Principals(ws); _, cred = P.enroll(pid, caps, op_id=f"op:enroll-{pid}", by=by); return P.authenticate(pid, cred), cred


def load_fixture(ws, name="001_base", n=1):
    rec = schema.from_fixture(json.loads((FIX / f"{name}.json").read_text())); s0 = rec["claim"]["source"]
    ws.register_source(s0, op_id=f"op:src-{n:04d}", observed_at=s0["available_as_of"]); ws.freeze_claim(rec["claim"], op_id=f"op:frz-{n:04d}", observed_at=s0["available_as_of"])
    from v8.workbench import availability
    return rec["claim"]["claim_id"], availability.source_id(s0)


def bundle(purpose="evidence.reference", payload=None, files=None, manifest_extra=None, raw_manifest=None):
    files = {"evidence/a.txt": b"fictional evidence text\n"} if files is None else files
    man = {"schema": "yuclaw.shd-bundle/1", "purpose": purpose, "evidence": [{"path": p, "sha256": hashlib.sha256(b).hexdigest(), "size": len(b)} for p, b in sorted(files.items())], "payload": payload or {}}
    man.update(manifest_extra or {}); buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("bundle.json", raw_manifest if raw_manifest is not None else json.dumps(man))
        for p, b in files.items():
            z.writestr(p, b)
    data = buf.getvalue()
    return data, hashlib.sha256(data).hexdigest(), sorted(hashlib.sha256(b).hexdigest() for b in files.values())


class Server:
    def __init__(self, ws_root):
        self.srv = S.WorkbenchServer(ws_root, 0); S.Handler.log_message = lambda *a, **k: None
        self.port = self.srv.server_address[1]; threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown(); self.srv.server_close()


class Client:
    """One browser-like session: its own cookies, the Origin/Host headers a same-origin form post carries."""
    def __init__(self, server):
        self.port = server.port; self.cookies = {}; self.get("/login")

    def _req(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        hd = {"Host": f"127.0.0.1:{self.port}", "Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items())}
        if method == "POST":
            hd["Origin"] = f"http://127.0.0.1:{self.port}"
        hd.update(headers or {}); c.request(method, path, body=body, headers=hd); r = c.getresponse(); data = r.read()
        for k, v in r.getheaders():
            if k.lower() == "set-cookie":
                name, _, rest = v.partition("="); val = rest.split(";", 1)[0]
                if "Max-Age=0" in v:
                    self.cookies.pop(name, None)
                else:
                    self.cookies[name] = val
        c.close(); return r.status, data.decode("utf-8", "replace"), dict((k.lower(), v) for k, v in r.getheaders())

    def get(self, path):
        return self._req("GET", path)

    def tokens(self, page_path):
        st, html_, _ = self.get(page_path); m = re.search(r'name="csrf" value="([0-9a-f]+)"', html_)
        return m.group(1) if m else ""

    def post(self, path, fields, page="/modules", op=None, follow=True):
        import secrets
        f = dict(fields); f["csrf"] = self.tokens(page); f["op_id"] = op or "op:t-" + secrets.token_hex(8)
        st, html_, hd = self._req("POST", path, urllib.parse.urlencode(f), {"Content-Type": "application/x-www-form-urlencoded"})
        if follow and st == 303:
            return (*self.get(hd["location"])[:2], hd["location"])
        return st, html_, hd.get("location")

    def upload(self, path, fields, files, page="/modules", op=None):
        import secrets
        b = "----yuclawtest" + secrets.token_hex(8); f = dict(fields); f["csrf"] = self.tokens(page); f["op_id"] = op or "op:t-" + secrets.token_hex(8); parts = []
        for k, v in f.items():
            parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        for k, (fn, data) in files.items():
            parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n")
        body = b"".join(parts) + f"--{b}--\r\n".encode()
        st, html_, hd = self._req("POST", path, body, {"Content-Type": f"multipart/form-data; boundary={b}"})
        if st == 303:
            return (*self.get(hd["location"])[:2], hd["location"])
        return st, html_, hd.get("location")

    def login(self, pid, cred):
        return self.post("/login", {"principal_id": pid, "credential": cred, "next": "/modules"}, page="/login")
