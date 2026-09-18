"""V8-010 §3: practical usability of the local workbench over HTTP — pages are not cached, a refused form comes back
with the user's entries and the same operation identifier (nothing written), the ingestion record import is bounded
data, every form control carries a programmatic label, tables sit in named scroll regions with scoped headers, status
blocks carry a role and a text cue, unresolved and rejected results name a next action, and the packaged operator
guide is served under /help. Markup checks are not browser evidence and not an accessibility certification; the
browser inspection is tools/yuclaw_v8_ui_inspect.py."""
import hashlib, html.parser, json, pathlib, re, subprocess, sys, tempfile, threading, unittest

from tests.test_v8_workbench_server import CLAIM, Client, _src
from v8.workbench import server as S

R = pathlib.Path(__file__).resolve().parents[1]


class _Audit(html.parser.HTMLParser):
    """Collects what the accessibility pass is responsible for."""
    def __init__(self):
        super().__init__(); self.for_ids, self.ids, self.controls, self.th_unscoped, self.tables, self.regions, self.depth_label, self.blocks = set(), [], [], 0, 0, 0, 0, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.append(a["id"])
        if tag == "label":
            self.depth_label += 1
            if a.get("for"):
                self.for_ids.add(a["for"])
        if tag in ("input", "select", "textarea") and a.get("type") != "hidden":
            self.controls.append((a.get("name"), a.get("id"), self.depth_label > 0))
        if tag == "th" and a.get("scope") not in ("col", "row"):
            self.th_unscoped += 1
        if tag == "table":
            self.tables += 1
        if tag == "div" and a.get("class") == "tw" and a.get("role") == "region" and a.get("tabindex") == "0" and a.get("aria-label"):
            self.regions += 1
        if a.get("class") in ("err", "notice"):
            self.blocks.append(a.get("role"))

    def handle_endtag(self, tag):
        if tag == "label":
            self.depth_label -= 1


class TestUsability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-ux-"))
        cls.srv = S.WorkbenchServer(cls.tmp / "A", 0, candidate_commit="cand-test"); threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        S.Handler.log_message = lambda *a, **k: None
        cls.c = Client(cls.srv.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def events(self):
        return len(self.srv.ws.load()["events"])

    def test_01_pages_are_not_cached_and_empty_states_say_what_to_do(self):
        st, h, page = self.c.req("GET", "/claim/new")
        self.assertEqual(h["Cache-Control"], "no-store")                     # the header was swallowed by a comment until V8-010
        self.assertIn(b"No source is registered in this workspace yet", page); self.assertIn(b'href="/source"', page)
        st, h, page = self.c.req("GET", "/"); self.assertIn(b"not a live feed", page); self.assertIn(b"Nothing has been recorded here yet", page)
        st, h, page = self.c.req("GET", "/help"); self.assertEqual(st, 200); self.assertIn(b"An interrupted write", page); self.assertIn(b"No claim is frozen in this workspace yet", page)
        self.assertEqual(self.c.req("GET", "/static/style.css")[1]["Cache-Control"], "no-store")

    def test_02_refused_freeze_keeps_entries_and_operation_identifier(self):
        c = self.c; n0 = self.events()
        self.assertEqual(c.post("/source/register", _src("0000000000-26-000001", "2026-02-10", "2026-02-10T21:05:00Z", "expects full-year 2026 revenue of $110 million to $120 million"))[0], 303)
        bad = dict(CLAIM, source_id=c.sid("0000000000-26-000001"), currency="", fp_label="", basis="", op_id="ui:keep-this-op-id"); bad.pop("resolution_rule")
        st, _, page = c.post("/claim/freeze", bad); text = page.decode()
        self.assertEqual(st, 422); self.assertEqual(self.events(), n0 + 1)                                   # only the source; the refused freeze wrote nothing
        self.assertIn("Blocked — nothing was written", text)
        for reason in ("currency", "fiscal_period.label", "basis", "resolution_rule"):
            self.assertIn(reason, text)
        self.assertIn('href="#form-freeze"', text); self.assertIn('id="form-freeze"', text)
        self.assertIn('name="op_id" value="ui:keep-this-op-id"', text)                                        # the same operation identifier comes back
        self.assertRegex(text, r'name="claim_id"[^>]* value="ZZFX-FY2026-REV-GUIDE"'); self.assertRegex(text, r'name="range_low"[^>]* value="110000000"')
        self.assertIn(">The company expects full-year 2026 revenue of $110 million to $120 million.</textarea>", text)
        self.assertRegex(text, r'<option value="0000000000-26-000001:[0-9a-f]+" selected>')                  # the chosen source stays chosen
        self.assertRegex(text, r'<option value="millions" selected>'); self.assertRegex(text, r'name="fictional" value="1" checked')
        # the corrected resubmission under that identifier succeeds exactly once
        good = dict(CLAIM, source_id=c.sid("0000000000-26-000001"), op_id="ui:keep-this-op-id")
        self.assertEqual(c.post("/claim/freeze", good)[0], 303); self.assertEqual(c.post("/claim/freeze", good)[0], 303); self.assertEqual(self.events(), n0 + 2)

    def test_03_refused_review_keeps_the_reviewers_text_and_evidence(self):
        c = self.c; cid = CLAIM["claim_id"]; ev = self.srv.ws.claim_state(cid)["events"][0]["event_hash"]; n0 = self.events()
        st, _, page = c.post(f"/claim/{cid}/adjudicate", {"reviewer": "R. Viewer", "rule": "RANGE_CONTAINS_ACTUAL", "label": "IN_RANGE", "reason": "my reading of the release", "conflicts": "none known", "evidence": [ev]})
        text = page.decode(); self.assertEqual(st, 422); self.assertEqual(self.events(), n0)
        self.assertIn("differs from the computed result", text); self.assertIn("nothing was written", text); self.assertIn('href="#form-adjudicate"', text)
        self.assertRegex(text, r'name="reviewer"[^>]* value="R. Viewer"'); self.assertIn(">my reading of the release</textarea>", text)
        self.assertRegex(text, rf'name="evidence" value="{ev}" checked'); self.assertRegex(text, r'<option value="IN_RANGE" selected>')
        self.assertIn("Unresolved — next:", text); self.assertIn("register its passage (step 1)", text)      # PENDING_OUTCOME names a valid next action
        # an amendment refused for a missing reason keeps its new range; the frozen version is untouched
        dig = self.srv.ws.claim_state(cid)["versions"][0]["claim"]["_digest"]
        st, _, page = c.post(f"/claim/{cid}/amend", dict(amend_type="REVISED", range_low="105000000", range_high="115000000", basis="GAAP", currency="USD", unit="USD", metric="revenue", fp_label="FY2026", fp_type="FY", fp_start="2026-01-01", fp_end="2026-12-31", reason="", source_id=c.sid("0000000000-26-000001")))
        self.assertEqual(st, 422); self.assertRegex(page.decode(), r'name="range_low"[^>]* value="105000000"'); self.assertEqual(self.events(), n0)
        st8 = self.srv.ws.claim_state(cid); self.assertEqual(len(st8["versions"]), 1); self.assertEqual(st8["versions"][0]["claim"]["_digest"], dig)

    def test_04_ingestion_record_import_is_bounded_data(self):
        c = self.c; n0 = self.events(); ex = "Net sales of $1.0755 billion (fictional test passage; whitespace  preserved)."
        rec = {"kind": "press_release", "form": "press release (test)", "accession": "TEST:publisher:0001", "url": None, "filed_at": "2026-03-01", "available_as_of": "2026-03-01T12:00:00Z", "excerpt": ex,
               "source_hash": hashlib.sha256(ex.encode()).hexdigest(), "fictional": True, "rights": "FICTIONAL"}
        for label, text, needle in (("empty", "", "paste the content"), ("not json", "{oops", "not valid JSON"), ("duplicate key", '{"kind": "a", "kind": "b"}', "duplicate JSON field"), ("a list", "[1]", "expected one JSON object"),
                                    ("the provenance file", json.dumps({"record": "yuclaw-ingestion/1", "retrieved_at": "x"}), "not the .provenance.json file"),
                                    ("a changed passage", json.dumps(dict(rec, excerpt=ex + " ")), "source_hash"), ("oversize", json.dumps(dict(rec, excerpt="x" * S.IMPORT_LIMIT)), "larger than")):
            st, _, page = c.post("/source/import", {"record": text, "record_observed_at": "2026-03-02T08:00:00Z"}); body = page.decode()
            self.assertEqual(st, 422, label); self.assertIn(needle, body, label); self.assertIn("nothing was written", body, label); self.assertEqual(self.events(), n0, label)
            self.assertIn('value="2026-03-02T08:00:00Z"', body, label)                                         # what was entered is still there
        self.assertIn("{oops</textarea>", c.post("/source/import", {"record": "{oops"})[2].decode())
        st, _, _ = c.post("/source/import", {"record": json.dumps(rec), "record_observed_at": "2026-03-02T08:00:00Z"}); self.assertEqual(st, 303); self.assertEqual(self.events(), n0 + 1)
        e = self.srv.ws.events()[-1]; self.assertEqual(e["kind"], "SOURCE_REGISTERED"); self.assertEqual(e["payload"]["source"]["excerpt"], ex); self.assertEqual(e["time"]["observed_at"][:19], "2026-03-02T08:00:00")
        self.assertEqual(e["payload"]["source_id"], "TEST:publisher:0001:" + rec["source_hash"][:16])          # the same identity a typed registration derives

    def test_05_every_page_has_labels_scoped_headers_regions_and_roles(self):
        c = self.c; cid = CLAIM["claim_id"]
        for path in ("/", "/source", "/source?as_of=bad", "/claim/new", f"/claim/{cid}", f"/claim/{cid}?as_of=2026-03-01T00:00:00Z", "/notes", "/dataset", "/sci", "/verify", "/journal", "/help"):
            st, _, page = c.req("GET", path); self.assertEqual(st, 200, path); text = page.decode(); a = _Audit(); a.feed(text)
            self.assertEqual([x for x in a.controls if not (x[2] or x[1] in a.for_ids)], [], path)             # wrapped by its label, or label[for] names its id
            self.assertEqual(len(a.ids), len(set(a.ids)), path); self.assertEqual(a.th_unscoped, 0, path); self.assertEqual(a.regions, a.tables, path)
            self.assertNotIn(None, a.blocks, path)
            for needle in ('<html lang="en">', '<main id="main"', 'class="skip" href="#main"', '<nav aria-label="Workbench functions">', 'name="viewport"', ":focus-visible" if path == "/static/style.css" else "<h1>"):
                self.assertIn(needle, text, path)
        self.assertIn(":focus-visible", c.req("GET", "/static/style.css")[2].decode())
        text = c.req("GET", f"/claim/{cid}")[2].decode()
        for key in ("source", "claim", "comparison", "calculation", "history", "adjudication", "export"):   # the seven steps link straight to their sections
            self.assertIn(f'href="/claim/{cid}#{key}"', text)
        self.assertIn("<b>Error.</b>", c.req("GET", "/source?as_of=bad")[2].decode())                       # an error is named in text, not by colour alone

    def test_06_rejected_upload_and_rejected_packet_name_the_next_action(self):
        c = self.c
        st, _, page = c.upload({"csrf": c.csrf, "op_id": "ui:verify-0001"}, b""); self.assertEqual(st, 422); self.assertIn(b"Nothing was verified", page); self.assertIn(b"Choose the export zip", page)
        st, _, page = c.upload({"csrf": c.csrf, "op_id": "ui:verify-0002"}, b"not a zip at all"); text = page.decode()
        self.assertEqual(st, 200); self.assertRegex(text, r"Result: <span class=\"bad\">(UNSUPPORTED|MISMATCH)</span>"); self.assertIn("<b>Next:</b>", text); self.assertTrue("nothing was imported" in text or "Do not rely on it" in text)

    def test_07_guide_is_packaged_printed_and_truthful_about_the_entry_point(self):
        guide = S.GUIDE_PATH.read_text(encoding="utf-8")
        for needle in ("python -m v8.workbench serve --workspace", "--port 8765", "--port 8766", "http://127.0.0.1:8766/verify", "Ctrl-C", "python -m v8.workbench recover --workspace", "Run recovery",
                       "Backup creation and restoration are not provided in 8.0.0. Restore not demonstrated. Research exports and release artifacts do not establish disaster recovery.", "not a live feed"):
            self.assertIn(needle, guide)
        self.assertFalse(re.search(r"[一-鿿]", guide))
        out = subprocess.run([sys.executable, "-m", "v8.workbench", "guide"], cwd=R, capture_output=True, text=True, timeout=30); self.assertEqual(out.returncode, 0); self.assertEqual(out.stdout, guide)
        for cmd in ("serve", "status", "recover", "verify-export", "guide"):                                  # every command the guide names exists
            self.assertEqual(subprocess.run([sys.executable, "-m", "v8.workbench", cmd, "--help"], cwd=R, capture_output=True, timeout=30).returncode, 0, cmd)
        self.assertEqual(subprocess.run([sys.executable, "-m", "v8.workbench.ingest", "--help"], cwd=R, capture_output=True, timeout=30).returncode, 0)


if __name__ == "__main__":
    unittest.main()
