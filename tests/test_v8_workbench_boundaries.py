"""V8-003 §2 — implementation boundary review with regression evidence: null Origin, refused requests close the connection,
concurrent and retried writes, torn-tail recovery over HTTP, the bounded ingestion allow-list, no network client in the server,
archive limits, forged comparison blocks, discrepancy notes, non-filing sources and their rights, the retrospective banner."""
import http.client, io, json, pathlib, re, socket, tempfile, threading, unittest, urllib.parse, zipfile

from v3.receipts.contracts import canonical_json
from v8.workbench import export, ingest, schema, store
from v8.workbench import server as S
from tests.test_v8_workbench_server import Client, CLAIM, PERIOD, _src

D = pathlib.Path(__file__).resolve().parent / "fixtures" / "v8" / "commitments"


class TestHttpBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-bnd-")); cls.A = S.WorkbenchServer(cls.tmp / "A", 0, candidate_commit="cand")
        threading.Thread(target=cls.A.serve_forever, daemon=True).start(); S.Handler.log_message = lambda *a, **k: None

    @classmethod
    def tearDownClass(cls):
        cls.A.shutdown()

    def test_null_origin_is_rejected_and_writes_nothing(self):
        a = Client(self.A.server_address[1]); a.req("GET", "/"); n0 = len(self.A.ws.load()["events"])
        body = urllib.parse.urlencode({"csrf": a.csrf, "op_id": "ui:nullorigin1", "kind": "filing"})
        st, _, data = a.req("POST", "/source/register", body, {"Content-Type": "application/x-www-form-urlencoded", "Origin": "null"})
        self.assertEqual(st, 403); self.assertIn(b"Origin", data); self.assertEqual(len(self.A.ws.load()["events"]), n0)

    def test_refused_requests_close_the_connection(self):
        """A refused POST whose body the server never read must not leave that body (or anything pipelined after it) to
        be parsed as the next request on the same connection: the response says Connection: close and the socket is
        closed right after it. Checked on a raw socket (http.client would silently reopen a connection)."""
        port = self.A.server_address[1]; c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("POST", "/source/register", body="x" * (S.FORM_LIMIT + 1), headers={"Host": f"127.0.0.1:{port}", "Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/x-www-form-urlencoded", "Cookie": "wb_session=" + "a" * 32})
        r = c.getresponse(); r.read(); self.assertEqual(r.status, 413); self.assertEqual(r.getheader("Connection"), "close"); c.close()
        with socket.create_connection(("127.0.0.1", port), timeout=10) as sk:
            head = (f"POST /source/register HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nOrigin: http://127.0.0.1:{port}\r\nContent-Type: application/x-www-form-urlencoded\r\n"
                    f"Cookie: wb_session={'a' * 32}\r\nContent-Length: {S.FORM_LIMIT + 1}\r\n\r\n").encode()
            smuggled = b"csrf=x&op_id=ui:smuggle0001&kind=filing\r\n" + f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode()   # a short body + a pipelined request
            sk.sendall(head + smuggled)
            buf = b""
            while True:
                try:
                    chunk = sk.recv(65536)
                except (ConnectionResetError, socket.timeout):
                    break
                if not chunk:
                    break
                buf += chunk
        self.assertTrue(buf.startswith(b"HTTP/1.1 413 "), buf[:80]); self.assertIn(b"\r\nConnection: close\r\n", buf)
        self.assertEqual(buf.count(b"HTTP/1.1 "), 1, "the pipelined GET after the refused body was answered")             # exactly one response, then EOF
        self.assertEqual(buf.count(b"<!doctype html>"), 0)
        st, hdr, _ = Client(port).req("POST", "/source/register", "x=1", {"Content-Type": "application/x-www-form-urlencoded"}, origin=False)
        self.assertEqual(st, 403); self.assertEqual(hdr.get("Connection"), "close")

    def test_torn_tail_over_http_then_recover_then_resubmit_once(self):
        a = Client(self.A.server_address[1]); a.req("GET", "/")
        a.post("/source/register", _src("0000000000-26-000001", "2026-02-10", "2026-02-10T21:05:00Z", "expects full-year 2026 revenue of $110 million to $120 million")); sid = a.sid("0000000000-26-000001")
        with open(self.A.ws.log, "ab") as f:
            f.write(b'{"seq": 99, "kind": "CLAIM_FROZEN"')
        st, _, page = a.req("GET", "/"); self.assertEqual(st, 200); self.assertIn(b"E_TORN_TAIL", page); self.assertIn(b"Run recovery", page)
        st, _, page = a.post("/claim/freeze", dict(CLAIM, claim_id="TORN-1", source_id=sid)); self.assertIn(b"E_TORN_TAIL", page); self.assertIsNone(self.A.ws.claim_state("TORN-1"))
        st, h, _ = a.post("/recover", {}); self.assertEqual(st, 303); self.assertEqual(self.A.ws.status()["integrity"], "OK")
        _, _, pg = a.req("GET", "/"); op = re.search(rb'name="op_id" value="([^"]+)"', pg).group(1).decode()
        self.assertEqual(a.post("/claim/freeze", dict(CLAIM, claim_id="TORN-1", source_id=sid, op_id=op))[0], 303)
        self.assertEqual(a.post("/claim/freeze", dict(CLAIM, claim_id="TORN-1", source_id=sid, op_id=op))[0], 303)     # browser resubmit: same op_id → duplicate, no second event
        self.assertEqual(len([e for e in self.A.ws.events("TORN-1") if e["kind"] == "CLAIM_FROZEN"]), 1)

    def test_retrospective_banner_only_when_sources_were_observed_after_the_outcome(self):
        a = Client(self.A.server_address[1]); a.req("GET", "/")
        for acc, filed, avail, ex in (("0000000000-26-000031", "2025-02-10", "2025-02-10T21:05:00Z", "expects x"), ("0000000000-26-000033", "2026-02-09", "2026-02-09T21:10:00Z", "x was 112")):
            a.post("/source/register", _src(acc, filed, avail, ex))
        s1, s3 = a.sid("0000000000-26-000031"), a.sid("0000000000-26-000033")
        a.post("/claim/freeze", dict(CLAIM, claim_id="RETRO-1", fp_label="FY2025", fp_start="2025-01-01", fp_end="2025-12-31", source_id=s1))
        page = a.req("GET", "/claim/RETRO-1")[2]; self.assertNotIn(b"RETROSPECTIVE REPLAY", page)              # no outcome yet
        a.post("/claim/RETRO-1/outcome", dict(PERIOD, fp_label="FY2025", fp_start="2025-01-01", fp_end="2025-12-31", actual="112000000", currency="USD", unit="USD", basis="GAAP", metric="revenue", source_id=s3, comparable="1"))
        page = a.req("GET", "/claim/RETRO-1")[2]; self.assertIn(b"RETROSPECTIVE REPLAY", page)
        self.assertEqual(a.post("/fixtures/load", {"fixture": "001_base"})[0], 303)
        page = a.req("GET", "/claim/ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base")[2]; self.assertNotIn(b"RETROSPECTIVE REPLAY", page)   # fixture observed_at == availability


class TestStoreConcurrency(unittest.TestCase):
    def setUp(self):
        self.ws = store.Workspace(pathlib.Path(tempfile.mkdtemp(prefix="wb-conc-")) / "ws")
        self.rec = schema.from_fixture(json.loads((D / "001_base.json").read_text()))

    def test_concurrent_distinct_operations_all_land_once_and_chain_verifies(self):
        errs = []
        def worker(i):
            try:
                self.ws.register_source(dict(self.rec["claim"]["source"], accession=f"0000000000-26-{i:06d}"), op_id=f"op:conc-{i:04d}")
            except Exception as exc:
                errs.append(repr(exc))
        ts = [threading.Thread(target=worker, args=(i,)) for i in range(24)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(errs, []); st = self.ws.load(); self.assertEqual(len(st["events"]), 24); self.assertIsNone(st["torn_tail"]); self.assertEqual(len({e["op_id"] for e in st["events"]}), 24)

    def test_concurrent_same_operation_lands_exactly_once(self):
        """Retries of ONE operation from many threads at once (a browser resubmit storm): exactly one durable event,
        every other call answered as the duplicate — never 'already frozen', never a conflict, never an exception.
        Before the fix the unlocked read of the prior event could race the append of another thread."""
        n = 16; results, errs = [], []; gate = threading.Barrier(n)
        def worker():
            try:
                gate.wait(5); results.append(self.ws.freeze_claim(self.rec["claim"], op_id="op:same-000001")[1])
            except Exception as exc:
                errs.append(repr(exc))
        for it in range(3):                                                                             # repeated to shake out interleavings; later rounds are all retries
            results.clear(); errs.clear(); gate.reset()
            ts = [threading.Thread(target=worker) for _ in range(n)]
            [t.start() for t in ts]; [t.join() for t in ts]
            first = 1 if it == 0 else 0
            self.assertEqual(errs, []); self.assertEqual(len(self.ws.load()["events"]), 1); self.assertEqual(results.count(False), first); self.assertEqual(results.count(True), n - first)


class TestIngestBoundaries(unittest.TestCase):
    class FakeResp:
        def __init__(self, body, url, ctype="text/html"):
            self.body, self.url, self.status = body, url, 200; self.headers = {"Content-Type": ctype}
        def read(self, n=-1): return self.body if n < 0 else self.body[:n]
        def geturl(self): return self.url
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class FakeOpener:
        def __init__(self, body=b"<html>x</html>", final=None): self.body, self.final = body, final
        def open(self, req, timeout=None):
            return TestIngestBoundaries.FakeResp(self.body, self.final or req.full_url)

    def test_allow_list_scheme_and_bounds(self):
        with self.assertRaises(ingest.IngestError):
            ingest.fetch("http://www.sec.gov/x", opener=self.FakeOpener())                              # https only
        with self.assertRaises(ingest.IngestError):
            ingest.fetch("https://evil.example/x", opener=self.FakeOpener())                             # host not allow-listed
        with self.assertRaises(ingest.IngestError):
            ingest.fetch("https://www.sec.gov/x", opener=self.FakeOpener(b"x" * (ingest.MAX_BYTES + 1)))  # body bound
        with self.assertRaises(ingest.IngestError):
            ingest.fetch("https://www.sec.gov/x", opener=self.FakeOpener(final="https://evil.example/y"))  # final host outside the list
        got = ingest.fetch("https://www.sec.gov/x", opener=self.FakeOpener(b"<p>ok</p>")); self.assertEqual(got["bytes"], 9); self.assertTrue(got["retrieved_at"].endswith("Z"))

    def test_cross_host_redirect_refused(self):
        h = ingest._NoCrossHostRedirect(); req = ingest.urllib.request.Request("https://www.sec.gov/a")
        with self.assertRaises(ingest.IngestError):
            h.redirect_request(req, None, 302, "Found", {}, "https://evil.example/b")

    def test_server_module_has_no_network_client(self):
        src = (pathlib.Path(__file__).resolve().parents[1] / "v8" / "workbench" / "server.py").read_text()
        for needle in ("urllib.request", "http.client", "socket.create_connection", "import requests", "urlopen("):
            self.assertNotIn(needle, src)
        self.assertNotIn("ingest", src)                                                                  # the ingestion tool is never imported by the server


class TestExportBoundaries(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-exb-")); self.ws = store.Workspace(self.tmp / "ws")
        self.rec = schema.from_fixture(json.loads((D / "001_base.json").read_text())); self.cid = self.rec["claim"]["claim_id"]

    def test_compression_ratio_bomb_refused(self):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("EXPORT_MANIFEST.json", bytes(4 << 20))
        p = self.tmp / "bomb.zip"; p.write_bytes(b.getvalue()); self.assertIn("compression ratio", export.verify_export(p)["first_discrepancy"])

    def test_forged_comparison_block_fails_recompute(self):
        r = self.rec["revisions"][0]; self.ws.freeze_claim(self.rec["claim"], op_id="op:freeze-0001")
        self.ws.amend_claim(self.cid, "REVISED", changes={"range": r["claim"]["range"]}, reason="revised", source=r["source"], op_id="op:amend-0001"); e = export.build_export(self.ws, self.cid)
        with zipfile.ZipFile(e["zip_path"]) as z:
            m = {i.filename: z.read(i) for i in z.infolist()}
        can = json.loads(m["canonical.json"]); can["comparison"]["direction"] = "RAISED"; cb = canonical_json(can)
        man = json.loads(m["EXPORT_MANIFEST.json"]); man["canonical_digest"] = export._sha(cb); man["files"][0].update(sha256=man["canonical_digest"], size_bytes=len(cb))
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            for k, v in dict(m, **{"canonical.json": cb, "EXPORT_MANIFEST.json": json.dumps(man).encode()}).items():
                z.writestr(k, v)
        p = self.tmp / "forged.zip"; p.write_bytes(b.getvalue()); v = export.verify_export(p); self.assertEqual(v["result"], "MISMATCH"); self.assertIn("comparison", v["first_discrepancy"])

    def test_discrepancy_note_preserved_and_press_release_rights(self):
        pr = dict(self.rec["revisions"][0]["source"], kind="press_release", form="press release", accession="IR:ir.example.com:1315", fictional=False, rights="COMPANY_PRESS_RELEASE")
        bad = dict(pr, rights="SEC_PUBLIC_FILING"); self.assertTrue(any("SEC_PUBLIC_FILING applies" in x for x in schema.check_source(bad)[1]))
        self.assertTrue(any("publisher identifier" in x for x in schema.check_source(dict(pr, accession="1315"))[1]))
        claim = dict(self.rec["claim"], fictional=False, source=dict(self.rec["claim"]["source"], fictional=False, rights="SEC_PUBLIC_FILING"))
        self.ws.freeze_claim(claim, op_id="op:freeze-0001")
        self.ws.amend_claim(self.cid, "REVISED", changes={"range": {"low": 105000000, "high": 115000000}}, reason="raised low end", source=pr,
                            notes={"explanation_unresolved": "n/a", "next_evidence": "10-K", "source_discrepancy": "the revision restates the prior low end as 111 while the original states 110; both preserved"}, op_id="op:amend-0001")
        st = self.ws.claim_state(self.cid); self.assertIn("both preserved", st["versions"][1]["notes"]["source_discrepancy"])
        e = export.build_export(self.ws, self.cid)
        with zipfile.ZipFile(e["zip_path"]) as z:
            can = json.loads(z.read("canonical.json"))
        self.assertIn("both preserved", can["versions"][1]["notes"]["source_discrepancy"])
        srcs = {s["accession"]: s for s in can["sources"]}
        self.assertTrue(srcs["0000000000-26-000001"]["excerpt_included"]); self.assertFalse(srcs["IR:ir.example.com:1315"]["excerpt_included"]); self.assertIn("COMPANY_PRESS_RELEASE", srcs["IR:ir.example.com:1315"]["excerpt_withheld_reason"])
        self.assertNotIn(pr["excerpt"], json.dumps(can)); self.assertEqual(export.verify_export(e["zip_path"])["result"], "SUCCESS")
        pe = export.publication_eligibility(can); self.assertFalse(pe["eligible"])


if __name__ == "__main__":
    unittest.main()
