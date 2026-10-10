"""v9 acceptance L — the real user surfaces agree because they use one reducer, and the new pages are usable over HTTP:
labels bound to controls, unique ids, scoped headers, named scroll regions, a skip link, focus styles, a narrow-width
rule, no script, informative refusals that keep the operation identifier, Host/Origin/CSRF guards, capability gates,
and both language editions carrying the same numbers. Markup checks are not browser evidence (see tools/yuclaw_v9_ui_inspect.py)."""
import html, json, pathlib, re, subprocess, sys, tempfile, threading, unittest, zipfile

from tests.test_v8_workbench_server import Client
from tests.test_v8_workbench_usability import _Audit
from tests import v8_mod_helpers as H
from v8.workbench import server as S, store
from v9.brief import packet, reducer
from v9.brief.sidecar import Sidecar

R = pathlib.Path(__file__).resolve().parents[1]
CID = "ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base"


def _audit(page: bytes) -> _Audit:
    a = _Audit(); a.feed(page.decode("utf-8")); return a


class TestBriefPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-v9ui-"))
        cls.srv = S.WorkbenchServer(cls.tmp / "A", 0, candidate_commit="cand-test"); threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        S.Handler.log_message = lambda *a, **k: None
        cls.c = Client(cls.srv.server_address[1])
        cls.c.post("/fixtures/load", {"fixture": "001_base"})
        st, h, _ = cls.c.post("/brief/create", {"claim": CID, "section_guidance_change": "1", "section_numerical_comparison": "1", "section_unresolved_interpretation": "1", "lang": "en", "ui_lang": "en"})
        assert st == 303, st
        cls.bid = re.search(r"brf-[0-9a-f]{12}", h["Location"]).group(0)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_01_every_new_page_has_labels_regions_scoped_headers_skip_link_focus_and_no_script(self):
        css = self.c.req("GET", "/static/style.css")[2].decode()
        self.assertIn(":focus-visible", css); self.assertIn("@media (max-width:420px)", css)
        for path in ("/brief", f"/brief/{self.bid}", f"/brief/{self.bid}?s=3", f"/brief/{self.bid}?lang=fr&s=9", "/brief/verify", "/brief/trust", "/brief?lang=fr"):
            st, h, page = self.c.req("GET", path)
            self.assertEqual(st, 200, path); self.assertNotIn(b"<script", page); self.assertIn("default-src 'none'", h["Content-Security-Policy"])
            self.assertIn(b'<a class="skip" href="#main">', page); self.assertIn(b'<main id="main" tabindex="-1">', page); self.assertIn(b'name="viewport"', page)
            a = _audit(page)
            self.assertEqual(a.th_unscoped, 0, path); self.assertEqual(a.tables, a.regions, path); self.assertEqual(len(a.ids), len(set(a.ids)), (path, [i for i in a.ids if a.ids.count(i) > 1][:5]))
            for name, cid, inside in a.controls:
                self.assertTrue(inside or (cid and cid in a.for_ids), (path, name))
            for role in a.blocks:
                self.assertIn(role, ("alert", "status"), path)

    def test_02_both_languages_carry_the_same_numbers_and_limits(self):
        en = self.c.req("GET", f"/brief/{self.bid}?lang=en")[2].decode(); fr = self.c.req("GET", f"/brief/{self.bid}?lang=fr")[2].decode()
        for needle in ("115", "110", "112", "-4.35%", "ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base", "UNRESOLVED", "Make financial AI accountable to evidence.", "Become the Science Trust Layer for Financial AI."):
            self.assertIn(needle, en); self.assertIn(needle, fr)
        self.assertIn("Inspecteur de phrase", self.c.req("GET", f"/brief/{self.bid}?lang=fr&s=3")[2].decode()); self.assertIn("Sentence inspector", self.c.req("GET", f"/brief/{self.bid}?lang=en&s=3")[2].decode())
        self.assertIn("conservent leurs libellés anglais", fr)                       # legacy labels are identified, not hidden
        st, h, _ = self.c.post(f"/brief/{self.bid}/translate", {"version": "B1", "ui_lang": "fr", "to": "fr", "mode": "template"}); self.assertEqual(st, 303)
        frtext = html.unescape(re.search(r'<pre class="excerpt">(.*?)</pre>', self.c.req("GET", f"/brief/{self.bid}?lang=fr&version=B2")[2].decode(), re.S).group(1))
        self.assertIn("−4,35 %", frtext); self.assertIn("115 millions USD", frtext); self.assertIn("La direction a abaissé ses prévisions parce que la demande s’est effondrée.", frtext)

    def test_03_cli_json_html_and_export_agree_because_they_use_one_reducer(self):
        ws = self.srv.ws; sc = Sidecar(ws)
        view = reducer.brief_view(ws, sc, self.bid, "B1", "en")
        page = self.c.req("GET", f"/brief/{self.bid}?version=B1")[2].decode()
        for s in view["statements"]:
            self.assertIn(html.escape(s["text"]), page); self.assertIn(f'<code>{s["substantive_support"]["status"]}</code>', page)
        out = subprocess.run([sys.executable, "-m", "v9.brief", "show", "--workspace", str(self.tmp / "A"), "--brief", self.bid, "--version", "B1", "--json"], cwd=R, capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr); cli = json.loads(out.stdout)
        self.assertEqual([s["substantive_support"]["status"] for s in cli["statements"]], [s["substantive_support"]["status"] for s in view["statements"]])
        self.assertEqual(cli["coverage"], view["coverage"])
        r = packet.build_packet(ws, sc, self.bid, "B1", op_id="t:ui-export-0001")
        with zipfile.ZipFile(r["zip_path"]) as z:
            exported = json.loads(z.read("brief.json")); htm = z.read("brief.html").decode()
        self.assertEqual([s["substantive_support"]["status"] for s in exported["statements"]], [s["substantive_support"]["status"] for s in view["statements"]])
        self.assertEqual(exported["coverage"]["sentence"], view["coverage"]["sentence"]); self.assertIn("-4.35%", htm); self.assertNotIn("<script", htm.lower())

    def test_04_refusals_are_informative_and_keep_the_operation_identifier(self):
        st, h, pg = self.c.post(f"/brief/{self.bid}/link", {"version": "B1", "ui_lang": "en", "start": "1", "end": "0", "role": "analyst_interpretation", "claim": "", "claim_version": "", "note": ""})
        self.assertEqual(st, 422); self.assertIn(b"Refused", pg); self.assertIn(b"nothing was written", pg); self.assertIn(b"start &lt; end", pg)
        st, h, pg = self.c.post(f"/brief/{self.bid}/link", {"version": "B1", "ui_lang": "en", "start": "a", "end": "b", "role": "analyst_interpretation", "claim": "", "claim_version": "", "note": ""})
        self.assertEqual(st, 422); self.assertIn(b"integer UTF-8 byte offsets", pg)
        st, h, pg = self.c.post(f"/brief/{self.bid}/edit", {"version": "B1", "ui_lang": "en", "text": html.unescape(re.search(r'<pre class="excerpt">(.*?)</pre>', self.c.req("GET", f"/brief/{self.bid}?version=B1")[2].decode(), re.S).group(1)), "provenance": "same"})
        self.assertEqual(st, 422); self.assertIn(b"identical to the parent", pg)
        st, h, pg = self.c.req("GET", f"/brief/{self.bid}?s=99"); self.assertEqual(st, 200); self.assertIn(b"does not exist", pg)
        st, h, pg = self.c.req("GET", "/brief/brf-000000000000"); self.assertEqual(st, 422); self.assertIn(b"does not exist", pg)

    def test_05_guards_apply_to_the_new_routes(self):
        import urllib.parse
        body = urllib.parse.urlencode({"csrf": self.c.csrf, "op_id": "ui:aaaaaaaa", "claim": CID, "lang": "en", "section_guidance_change": "1"}); ct = {"Content-Type": "application/x-www-form-urlencoded"}
        self.assertEqual(self.c.req("POST", "/brief/create", body, ct, origin=False)[0], 403)
        self.assertEqual(self.c.req("POST", "/brief/create", body, dict(ct, Origin="http://evil.example"))[0], 403)
        self.assertEqual(self.c.req("POST", "/brief/create", urllib.parse.urlencode({"csrf": "bad", "op_id": "ui:aaaaaaaa", "claim": CID}), ct)[0], 403)
        self.assertEqual(self.c.req("GET", "/brief", headers={"Host": "evil.example"})[0], 400)
        n = len(Sidecar(self.srv.ws).load()["records"])
        self.assertEqual(self.c.req("POST", "/brief/create", body, ct)[0], 303)                      # the same op_id with the same content: no second brief
        self.assertEqual(self.c.req("POST", "/brief/create", body, ct)[0], 303)
        self.assertEqual(len(Sidecar(self.srv.ws).load()["records"]), n + 1)

    def test_06_capabilities_gate_writes_once_principals_exist(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-v9cap-")); ws = store.Workspace(tmp / "W")
        S.load_fixture(ws, "001_base")
        admin, acred = H.principal(ws, "admin1", ["admin"]); prac, pcred = H.principal(ws, "learner1", ["practice"], by=admin); rev, rcred = H.principal(ws, "rev1", ["review"], by=admin)
        srv = H.Server(tmp / "W")
        try:
            anon = H.Client(srv); st, txt, hdr = anon.get("/brief"); self.assertEqual(st, 303); self.assertIn("/login?next=%2Fbrief", hdr.get("location", ""))
            p = H.Client(srv); p.login("learner1", pcred); st, txt, hdr = p.get("/brief"); self.assertEqual(st, 403)        # practice-only is confined
            r = H.Client(srv); r.login("rev1", rcred); st, txt, loc = r.post("/brief/create", {"claim": CID, "section_guidance_change": "1", "lang": "en", "ui_lang": "en"}, page="/brief")
            self.assertEqual(st, 200); self.assertIn("brf-", loc or txt)
            a = H.Client(srv); a.login("admin1", acred); st, txt, loc = a.post("/brief/trust/enroll", {"public_key": "AAAA", "label": "x", "issuer": "", "ui_lang": "en"}, page="/brief/trust", follow=False)
            self.assertEqual(st, 422); self.assertIn("Ed25519", txt)
            st, txt, loc = r.post("/brief/trust/enroll", {"public_key": "AAAA", "label": "x", "issuer": "", "ui_lang": "en"}, page="/brief/trust", follow=False)
            self.assertEqual(st, 403)                                                                                      # review cannot enroll trust
        finally:
            srv.close()


if __name__ == "__main__":
    unittest.main()
