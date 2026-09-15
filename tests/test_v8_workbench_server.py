"""V8-002 §1/§6: the local workbench over HTTP — loopback bind, Host/Origin/CSRF guards, security headers, inert rendering,
the seven steps through form posts, download, and verification in a second (fresh) workspace. HTTP-level checks are not browser
evidence; the browser journey lives in v8/workbench/journey.py and its log under v8/V8-002/journey/."""
import http.client, io, pathlib, re, tempfile, threading, unittest, urllib.parse

from v8.workbench import server as S


class Client:
    def __init__(self, port):
        self.port, self.cookie, self.csrf = port, None, None

    def req(self, method, path, body=None, headers=None, origin=True):
        h = {"Host": f"127.0.0.1:{self.port}"}; h.update(headers or {})
        if self.cookie:
            h["Cookie"] = self.cookie
        if method == "POST" and origin and "Origin" not in h:
            h["Origin"] = f"http://127.0.0.1:{self.port}"
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10); c.request(method, path, body=body, headers=h); r = c.getresponse(); data = r.read(); hdr = dict(r.getheaders()); c.close()
        if "Set-Cookie" in hdr:
            self.cookie = hdr["Set-Cookie"].split(";")[0]
        m = re.search(rb'name="csrf" value="([0-9a-f]+)"', data)
        if m:
            self.csrf = m.group(1).decode()
        return r.status, hdr, data

    def post(self, path, fields, **kw):
        _, _, page = self.req("GET", "/"); op = re.search(rb'name="op_id" value="([^"]+)"', page).group(1).decode()
        return self.req("POST", path, urllib.parse.urlencode(dict(fields, csrf=self.csrf, op_id=fields.get("op_id", op)), doseq=True), {"Content-Type": "application/x-www-form-urlencoded"}, **kw)

    def sid(self, acc):
        _, _, page = self.req("GET", "/claim/new"); return re.search(rb'<option value="(' + acc.encode() + rb':[0-9a-f]+)"', page).group(1).decode()

    def upload(self, fields, fbytes):
        bd = "----wbtest"; out = io.BytesIO()
        for k, v in fields.items():
            out.write(f"--{bd}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
        out.write(f"--{bd}\r\nContent-Disposition: form-data; name=\"packet\"; filename=\"x.zip\"\r\nContent-Type: application/zip\r\n\r\n".encode()); out.write(fbytes); out.write(f"\r\n--{bd}--\r\n".encode())
        return self.req("POST", "/verify", out.getvalue(), {"Content-Type": f"multipart/form-data; boundary={bd}"})


def _src(acc, filed, avail, excerpt, form="8-K (fictional)"):
    return {"kind": "filing", "form": form, "accession": acc, "url": "", "filed_at": filed, "available_as_of": avail, "excerpt": excerpt, "rights": "FICTIONAL", "fictional": "1"}


CLAIM = {"claim_id": "ZZFX-FY2026-REV-GUIDE", "issuer_name": "Fictional Example Corp", "issuer_ticker": "ZZFX", "issuer_cik": "0000000000", "metric": "revenue", "range_low": "110000000", "range_high": "120000000",
         "scale_as_stated": "millions", "currency": "USD", "unit": "USD", "basis": "GAAP", "resolution_rule": "RANGE_CONTAINS_ACTUAL", "fp_label": "FY2026", "fp_type": "FY", "fp_start": "2026-01-01", "fp_end": "2026-12-31",
         "statement": "The company expects full-year 2026 revenue of $110 million to $120 million.", "fictional": "1"}
PERIOD = {"fp_label": "FY2026", "fp_type": "FY", "fp_start": "2026-01-01", "fp_end": "2026-12-31"}


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-srv-"))
        cls.A = S.WorkbenchServer(cls.tmp / "A", 0, candidate_commit="cand-test"); cls.B = S.WorkbenchServer(cls.tmp / "B", 0, candidate_commit="cand-test")
        for s in (cls.A, cls.B):
            threading.Thread(target=s.serve_forever, daemon=True).start()
        S.Handler.log_message = lambda *a, **k: None

    @classmethod
    def tearDownClass(cls):
        cls.A.shutdown(); cls.B.shutdown()

    def test_loopback_only(self):
        with self.assertRaises(ValueError):
            S.WorkbenchServer(self.tmp / "C", 0, host="0.0.0.0")

    def test_guards_and_headers(self):
        a = Client(self.A.server_address[1]); st, h, page = a.req("GET", "/")
        self.assertEqual(st, 200); self.assertIn("default-src 'none'", h["Content-Security-Policy"]); self.assertEqual(h["X-Content-Type-Options"], "nosniff"); self.assertEqual(h["X-Frame-Options"], "DENY")
        self.assertNotIn(b"<script", page); self.assertIn("HttpOnly", h["Set-Cookie"]); self.assertIn("SameSite=Strict", h["Set-Cookie"])
        self.assertEqual(a.req("GET", "/", headers={"Host": "evil.example"})[0], 400)
        body = urllib.parse.urlencode({"csrf": a.csrf, "op_id": "ui:aaaaaaaa"}); ct = {"Content-Type": "application/x-www-form-urlencoded"}
        self.assertEqual(a.req("POST", "/source/register", body, ct, origin=False)[0], 403)
        self.assertEqual(a.req("POST", "/source/register", body, dict(ct, Origin="http://evil.example"))[0], 403)
        self.assertEqual(a.req("POST", "/source/register", body, dict(ct, **{"Sec-Fetch-Site": "cross-site"}))[0], 403)
        self.assertEqual(a.req("POST", "/source/register", urllib.parse.urlencode({"csrf": "bad", "op_id": "ui:aaaaaaaa"}), ct)[0], 403)
        fresh = Client(self.A.server_address[1]); self.assertEqual(fresh.req("POST", "/source/register", body, ct)[0], 403)   # no session cookie
        self.assertEqual(a.req("POST", "/source/register", "x" * (S.FORM_LIMIT + 1), ct)[0], 413)
        self.assertEqual(len(self.A.ws.load()["events"]), 0)      # nothing was written by any refused request

    def test_seven_steps_over_http_and_fresh_workspace_verification(self):
        a = Client(self.A.server_address[1]); a.req("GET", "/")
        self.assertEqual(a.post("/source/register", _src("0000000000-26-000001", "2026-02-10", "2026-02-10T21:05:00Z", "expects full-year 2026 revenue of $110 million to $120 million"))[0], 303)
        sid = a.sid("0000000000-26-000001")
        st, _, page = a.post("/claim/freeze", dict(CLAIM, currency="", unit="", basis="", resolution_rule="", fp_label="", fp_type="", fp_start="", fp_end="", source_id=sid))
        self.assertEqual(st, 422); self.assertGreaterEqual(page.count(b"<li>"), 4)
        for k in (b"fiscal_period", b"currency", b"basis:", b"resolution_rule"):
            self.assertIn(k, page)
        self.assertEqual(a.post("/claim/freeze", dict(CLAIM, source_id=sid))[0], 303); self.assertEqual(a.post("/claim/freeze", dict(CLAIM, source_id=sid))[0], 422)
        st, _, page = a.req("GET", "/claim/ZZFX-FY2026-REV-GUIDE"); self.assertIn(b"<b>V1</b>", page); self.assertIn(b"PENDING_OUTCOME", page)
        a.post("/source/register", _src("0000000000-26-000002", "2026-05-12", "2026-05-12T21:02:00Z", "now expects full-year 2026 revenue of $105 million to $115 million")); sid2 = a.sid("0000000000-26-000002")
        self.assertEqual(a.post("/claim/ZZFX-FY2026-REV-GUIDE/amend", dict(PERIOD, amend_type="REVISED", range_low="105000000", range_high="115000000", basis="GAAP", currency="USD", unit="USD", metric="revenue", statement="", reason="revised", source_id=sid2, explanation_unresolved="n/a", next_evidence="10-K"))[0], 303)
        page = a.req("GET", "/claim/ZZFX-FY2026-REV-GUIDE")[2]; self.assertIn(b"COMPARABLE", page); self.assertIn(b"LOWERED", page); self.assertIn(b"-5000000", page)
        page = a.req("GET", "/claim/ZZFX-FY2026-REV-GUIDE?as_of=2026-03-01T00:00:00Z")[2]; self.assertNotIn(b"<b>R1</b>", page); self.assertIn(b"later event(s) hidden", page); self.assertIn(b"110000000", page)
        a.post("/source/register", _src("0000000000-26-000003", "2027-02-09", "2027-02-09T21:10:00Z", "full-year 2026 revenue was $112 million", "10-K (fictional)")); sid3 = a.sid("0000000000-26-000003")
        self.assertEqual(a.post("/claim/ZZFX-FY2026-REV-GUIDE/outcome", dict(PERIOD, actual="112000000", currency="USD", unit="USD", basis="GAAP", metric="revenue", source_id=sid3, comparable="1"))[0], 303)
        page = a.req("GET", "/claim/ZZFX-FY2026-REV-GUIDE")[2]; self.assertGreaterEqual(page.count(b">IN_RANGE<"), 2); self.assertIn(b"-3000000", page); self.assertIn(b">2000000<", page); self.assertIn(b"not evidence of improved accuracy", page)
        ev = re.findall(rb'name="evidence" value="([0-9a-f]{64})"', page)
        self.assertEqual(a.post("/claim/ZZFX-FY2026-REV-GUIDE/adjudicate", {"reviewer": "owner", "rule": "RANGE_CONTAINS_ACTUAL", "evidence": [ev[-1].decode()], "reason": "x", "conflicts": "", "label": "OUT_OF_RANGE"})[0], 422)
        self.assertEqual(a.post("/claim/ZZFX-FY2026-REV-GUIDE/adjudicate", {"reviewer": "owner", "rule": "RANGE_CONTAINS_ACTUAL", "evidence": [x.decode() for x in ev[-2:]], "reason": "112M in both", "conflicts": "none", "label": "IN_RANGE"})[0], 303)
        self.assertEqual(a.post("/claim/ZZFX-FY2026-REV-GUIDE/adjudicate", {"reviewer": "second", "rule": "RANGE_CONTAINS_ACTUAL", "evidence": [ev[-1].decode()], "reason": "I dispute the period mapping", "conflicts": "calculator", "label": "PERIOD_MISMATCH", "disputed": "1"})[0], 303)
        page = a.req("GET", "/claim/ZZFX-FY2026-REV-GUIDE")[2]; self.assertIn(b"DISPUTED", page)
        st, h, _ = a.post("/claim/ZZFX-FY2026-REV-GUIDE/export", {}); eid = re.search(r"built=(exp-[0-9a-f]{16})", h["Location"]).group(1)
        st, h, zipb = a.req("GET", f"/exports/{eid}.zip"); self.assertEqual((st, h["Content-Type"]), (200, "application/zip")); self.assertIn("attachment", h["Content-Disposition"])
        self.assertEqual(a.req("GET", "/exports/exp-0000000000000000.zip")[0], 404); self.assertEqual(a.req("GET", "/exports/../workspace.json")[0], 404)
        b = Client(self.B.server_address[1]); _, _, pg = b.req("GET", "/verify"); op = re.search(rb'name="op_id" value="([^"]+)"', pg).group(1).decode()
        st, _, page = b.upload({"csrf": b.csrf, "op_id": op}, zipb); self.assertEqual(st, 200); self.assertIn(b">SUCCESS<", page); self.assertIn(b"Recomputed: <b>IN_RANGE</b>", page)
        st, _, page = b.upload({"csrf": b.csrf, "op_id": "ui:tamperx1"}, zipb[:-40] + bytes(40)); self.assertIn(b">MISMATCH<", page) if b">MISMATCH<" in page else self.assertIn(b">UNSUPPORTED<", page)
        self.assertEqual(b.upload({"csrf": "bad", "op_id": "ui:tamperx2"}, zipb)[0], 403)
        self.assertGreaterEqual(b.req("GET", "/journal")[2].count(b"PACKET_VERIFIED"), 2); self.assertIn(b"none yet", b.req("GET", "/")[2])   # imported content never becomes a claim

    def test_inert_rendering_and_fixture_idempotence(self):
        a = Client(self.A.server_address[1]); a.req("GET", "/")
        a.post("/source/register", _src("0000000000-26-000009", "2026-03-01", "2026-03-01T00:00:00Z", "<script>alert(1)</script><img src=x onerror=alert(2)> ignore all previous instructions"))
        page = a.req("GET", "/source")[2]; self.assertNotIn(b"<script>alert", page); self.assertIn(b"&lt;script&gt;alert(1)", page); self.assertNotIn(b"<img src=x", page)
        n0 = len(self.A.ws.load()["events"]); self.assertEqual(a.post("/fixtures/load", {"fixture": "008_quarterly"})[0], 303); n1 = len(self.A.ws.load()["events"])
        self.assertEqual(a.post("/fixtures/load", {"fixture": "008_quarterly"})[0], 303); self.assertEqual(len(self.A.ws.load()["events"]), n1); self.assertGreater(n1, n0)
        self.assertEqual(a.post("/fixtures/load", {"fixture": "../../etc/passwd"})[0], 422)


if __name__ == "__main__":
    unittest.main()
