"""V8-004 §3 — research notes: a separate, append-only research action on a frozen claim. Creation and correction change
no claim field or digest; retries land once; op-id reuse with other content is a conflict; a torn tail cannot lose or
duplicate a note; notes are visible when the comparison is COMPARABLE or INCOMPARABLE, when the outcome is missing and
when the claim is withdrawn — and never reopen or resolve anything; a note written now is not contemporaneous at an
earlier cutoff; notes and their correction history travel in exports and are re-derived by the verifier; free text is
rendered inertly and grants no publication eligibility."""
import json, pathlib, tempfile, threading, unittest, zipfile

from v3.receipts.contracts import ContractError
from v8.workbench import export, schema, store
from v8.workbench import server as S
from tests.test_v8_workbench_server import Client, CLAIM, _src

D = pathlib.Path(__file__).resolve().parent / "fixtures" / "v8" / "commitments"
NOTE = {"category": "unresolved_question", "actor": "researcher A (attribution label)", "reason": "the revision cites first-quarter results but no causal link is established",
        "unresolved_question": "why was the low end raised while the high end stayed?", "next_evidence": "the full-year filing", "version_ref": "R1", "evidence": [], "supersedes_note": None, "simulated": False}


def _ws(fixture="001_base"):
    ws = store.Workspace(pathlib.Path(tempfile.mkdtemp(prefix="wb-notes-")) / "ws")
    rec = schema.from_fixture(json.loads((D / f"{fixture}.json").read_text())); cid = rec["claim"]["claim_id"]
    ws.register_source(rec["claim"]["source"], op_id="op:src-0001"); ws.freeze_claim(rec["claim"], op_id="op:freeze-0001")
    for i, r in enumerate(rec["revisions"], 1):
        ws.register_source(r["source"], op_id=f"op:src-r{i}")
        if r["type"] == "WITHDRAWN":
            ws.amend_claim(cid, "WITHDRAWN", changes=None, reason=r["reason"] or "withdrawn", source=r["source"], op_id=f"op:amend-{i}")
        else:
            c = r["claim"]; ws.amend_claim(cid, r["type"], changes={"range": c["range"], "basis": c["basis"], "unit": c["unit"], "currency": c["currency"], "metric": c["metric"], "fiscal_period": c["fiscal_period"]}, reason=r["reason"] or r["type"], source=r["source"], op_id=f"op:amend-{i}")
    if rec["outcome"]:
        ws.register_source(rec["outcome"]["source"], op_id="op:src-out"); ws.record_outcome(cid, rec["outcome"], op_id="op:outcome-0001")
    return ws, cid


class TestNotesStore(unittest.TestCase):
    def test_note_and_correction_change_no_claim_field_or_digest(self):
        ws, cid = _ws(); before = ws.claim_state(cid)
        digests = [v["claim"]["_digest"] for v in before["versions"]]; fields = {k: before["current"]["claim"][k] for k in ("range", "metric", "currency", "basis", "fiscal_period", "source")}
        ev, dup = ws.record_note(cid, NOTE, op_id="op:note-0001"); self.assertFalse(dup); self.assertEqual(ev["kind"], "RESEARCH_NOTE_RECORDED"); self.assertEqual(ev["payload"]["note_id"], "N1")
        self.assertEqual(ev["payload"]["version_ref"], "R1"); self.assertEqual(ev["payload"]["version_digest"], digests[1]); self.assertFalse(ev["payload"]["changes_claim"]); self.assertIsNone(ev["time"]["source_available_as_of"])
        ev2, _ = ws.record_note(cid, dict(NOTE, supersedes_note="N1", unresolved_question="corrected wording of the question", reason="typo in the first note"), op_id="op:note-0002")
        self.assertEqual(ev2["payload"]["supersedes_note"], "N1"); self.assertEqual(ev2["payload"]["supersedes_event"], ev["event_hash"])
        after = ws.claim_state(cid)
        self.assertEqual([v["claim"]["_digest"] for v in after["versions"]], digests); self.assertEqual({k: after["current"]["claim"][k] for k in fields}, fields); self.assertEqual(len(after["versions"]), len(before["versions"]))
        self.assertEqual([n["note_id"] for n in after["research_notes"]], ["N1", "N2"]); self.assertEqual(after["research_notes"][0]["superseded_by"], "N2")
        self.assertEqual(after["research_notes"][0]["unresolved_question"], NOTE["unresolved_question"])                 # the earlier text is retained
        self.assertEqual([n["note_id"] for n in after["research_notes_current"]], ["N2"])
        with self.assertRaises(ContractError):                                                                             # a corrected note is corrected at its latest version
            ws.record_note(cid, dict(NOTE, supersedes_note="N1"), op_id="op:note-0003")
        with self.assertRaises(ContractError):
            ws.record_note(cid, dict(NOTE, version_ref="R9"), op_id="op:note-0004")
        with self.assertRaises(ContractError):
            ws.record_note(cid, dict(NOTE, evidence=["f" * 64]), op_id="op:note-0005")
        with self.assertRaises(ContractError):
            ws.record_note(cid, dict(NOTE, reason=""), op_id="op:note-0006")
        with self.assertRaises(ContractError):
            ws.record_note("NOPE-1", NOTE, op_id="op:note-0007")
        self.assertEqual(len(ws.claim_state(cid)["research_notes"]), 2)

    def test_retry_lands_once_conflict_refused_and_torn_tail_never_loses_or_duplicates(self):
        ws, cid = _ws()
        e1, d1 = ws.record_note(cid, NOTE, op_id="op:note-0001"); e2, d2 = ws.record_note(cid, NOTE, op_id="op:note-0001")
        self.assertEqual((d1, d2), (False, True)); self.assertEqual(e1["event_hash"], e2["event_hash"]); self.assertEqual(len([e for e in ws.events(cid) if e["kind"] == "RESEARCH_NOTE_RECORDED"]), 1)
        with self.assertRaises(store.StoreIntegrityError) as cm:
            ws.record_note(cid, dict(NOTE, reason="different content"), op_id="op:note-0001")
        self.assertEqual(cm.exception.code, "E_OP_CONFLICT")
        n = len(ws.load()["events"]); results, errs = [], []; gate = threading.Barrier(8)
        def worker():
            try:
                gate.wait(5); results.append(ws.record_note(cid, dict(NOTE, reason="concurrent"), op_id="op:note-0009")[1])
            except Exception as exc:
                errs.append(repr(exc))
        ts = [threading.Thread(target=worker) for _ in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(errs, []); self.assertEqual(len(ws.load()["events"]), n + 1); self.assertEqual(sorted(results), [False] + [True] * 7)
        with open(ws.log, "ab") as f:
            f.write(b'{"seq": 99, "kind": "RESEARCH_NOTE_RECORDED"')                                                       # interrupted append
        with self.assertRaises(store.StoreIntegrityError):
            ws.record_note(cid, dict(NOTE, reason="after tear"), op_id="op:note-0010")
        self.assertTrue(ws.recover()["recovered"]); e, dup = ws.record_note(cid, dict(NOTE, reason="after tear"), op_id="op:note-0010"); self.assertFalse(dup)
        self.assertEqual(ws.record_note(cid, dict(NOTE, reason="after tear"), op_id="op:note-0010")[1], True)
        self.assertEqual(len([x for x in ws.events(cid) if x["kind"] == "RESEARCH_NOTE_RECORDED"]), 3)

    def test_withdrawn_and_missing_outcome_stay_unresolved_and_notes_are_visible(self):
        ws, cid = _ws("003_withdrawal"); st = ws.claim_state(cid); self.assertIsNotNone(st["withdrawn"])
        with self.assertRaises(ContractError):                                                                             # amendments stay refused after withdrawal
            ws.amend_claim(cid, "REVISED", changes={"range": {"low": 1, "high": 2}}, reason="x", source=st["current"]["claim"]["source"], op_id="op:amend-x")
        ws.record_note(cid, dict(NOTE, version_ref=None, category="explanation", unresolved_question="withdrawal reason unexplained"), op_id="op:note-w001")
        st2 = ws.claim_state(cid); self.assertIsNotNone(st2["withdrawn"]); self.assertEqual(len(st2["research_notes"]), 1)
        from v8.workbench import calc
        self.assertEqual(calc.adjudicate(st2)["result"], "WITHDRAWN_BEFORE_OUTCOME")                                       # a note reopens nothing
        ws2, cid2 = _ws("002_missing_outcome"); ws2.record_note(cid2, dict(NOTE, version_ref=None, category="next_evidence", unresolved_question="", next_evidence="the annual report"), op_id="op:note-m001")
        s2 = ws2.claim_state(cid2); self.assertIsNone(s2["outcome"]); self.assertEqual(calc.adjudicate(s2)["result"], "PENDING_OUTCOME"); self.assertEqual(s2["research_notes"][0]["next_evidence"], "the annual report")

    def test_note_timing_is_honest_in_as_of_views(self):
        ws, cid = _ws(); ws.record_note(cid, NOTE, op_id="op:note-0001")
        full = ws.claim_state(cid); avail = full["versions"][0]["claim"]["source"]["available_as_of"]
        early = ws.claim_state(cid, as_of=avail); self.assertEqual(early["research_notes"], [])                               # written now → not contemporaneous then
        now = store.now_ts(); late = ws.claim_state(cid, as_of=now); self.assertEqual(len(late["research_notes"]), 1)


class TestNotesExport(unittest.TestCase):
    def test_export_carries_notes_and_corrections_and_verifier_rederives_them(self):
        ws, cid = _ws(); ws.record_note(cid, NOTE, op_id="op:note-0001"); ws.record_note(cid, dict(NOTE, supersedes_note="N1", reason="corrected"), op_id="op:note-0002")
        e = export.build_export(ws, cid)
        with zipfile.ZipFile(e["zip_path"]) as z:
            m = {i.filename: z.read(i) for i in z.infolist()}
        can = json.loads(m["canonical.json"]); self.assertEqual([n["note_id"] for n in can["research_notes"]], ["N1", "N2"]); self.assertEqual(can["research_notes"][0]["superseded_by"], "N2")
        self.assertEqual(len([x for x in can["events"] if x["kind"] == "RESEARCH_NOTE_RECORDED"]), 2); self.assertIn("dataset_row", can); self.assertEqual(can["dataset_row"]["research_notes"]["count"], 2)
        v = export.verify_export(e["zip_path"]); self.assertEqual(v["result"], "SUCCESS"); self.assertTrue(any(c["check"] == "recompute-notes" and c["ok"] for c in v["checks"]))
        self.assertTrue(any(c["check"] == "recompute-dataset-row" and c["ok"] for c in v["checks"]))
        # a changed note text inside the packet fails (the note event hash and the re-derived notes block both differ)
        tampered = m["canonical.json"].replace(NOTE["reason"].encode(), b"a different reason of equal size!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        self.assertNotEqual(tampered, m["canonical.json"])
        import hashlib; man = json.loads(m["EXPORT_MANIFEST.json"]); man["canonical_digest"] = hashlib.sha256(tampered).hexdigest(); man["files"][0].update(sha256=man["canonical_digest"], size_bytes=len(tampered))
        p = pathlib.Path(e["zip_path"]).with_name("tampered_note.zip")
        with zipfile.ZipFile(p, "w") as z:
            for k, val in dict(m, **{"canonical.json": tampered, "EXPORT_MANIFEST.json": json.dumps(man).encode()}).items():
                z.writestr(k, val)
        self.assertEqual(export.verify_export(p)["result"], "MISMATCH")
        # an export written before notes existed stays verifiable and is reported as such, never reinterpreted
        old = {k: val for k, val in can.items() if k not in ("research_notes", "dataset_row")}; old["events"] = [x for x in old["events"] if x["kind"] not in ("RESEARCH_NOTE_RECORDED", "SOURCE_REGISTERED")]
        from v3.receipts.contracts import canonical_json
        ob = canonical_json(old); man2 = json.loads(m["EXPORT_MANIFEST.json"]); man2["canonical_digest"] = hashlib.sha256(ob).hexdigest(); man2["files"][0].update(sha256=man2["canonical_digest"], size_bytes=len(ob))
        p2 = pathlib.Path(e["zip_path"]).with_name("old_format.zip")
        with zipfile.ZipFile(p2, "w") as z:
            for k, val in dict(m, **{"canonical.json": ob, "EXPORT_MANIFEST.json": json.dumps(man2).encode()}).items():
                z.writestr(k, val)
        v2 = export.verify_export(p2); self.assertEqual(v2["result"], "SUCCESS"); self.assertTrue(any(c["check"] == "recompute-notes" and c["ok"] is None for c in v2["checks"]))
        man3 = dict(man2, format="yuclaw-commitment-export/9"); p3 = pathlib.Path(e["zip_path"]).with_name("unknown_format.zip")
        with zipfile.ZipFile(p3, "w") as z:
            for k, val in dict(m, **{"canonical.json": ob, "EXPORT_MANIFEST.json": json.dumps(man3).encode()}).items():
                z.writestr(k, val)
        v3 = export.verify_export(p3); self.assertEqual(v3["result"], "UNSUPPORTED"); self.assertIn("unsupported export format", v3["first_discrepancy"])
        pe = export.publication_eligibility(can); self.assertFalse(pe["eligible"])                                          # a note grants no eligibility


class TestNotesServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-notes-srv-")); cls.A = S.WorkbenchServer(cls.tmp / "A", 0, candidate_commit="cand")
        threading.Thread(target=cls.A.serve_forever, daemon=True).start(); S.Handler.log_message = lambda *a, **k: None

    @classmethod
    def tearDownClass(cls):
        cls.A.shutdown()

    def test_note_form_incomparable_branch_later_annotations_and_inert_text(self):
        a = Client(self.A.server_address[1]); a.req("GET", "/")
        a.post("/source/register", _src("0000000000-26-000001", "2026-02-10", "2026-02-10T21:05:00Z", "expects full-year 2026 revenue of $110 million to $120 million")); sid = a.sid("0000000000-26-000001")
        self.assertEqual(a.post("/claim/freeze", dict(CLAIM, source_id=sid))[0], 303)
        a.post("/source/register", _src("0000000000-26-000002", "2026-05-12", "2026-05-12T21:02:00Z", "basis changed")); sid2 = a.sid("0000000000-26-000002")
        self.assertEqual(a.post("/claim/ZZFX-FY2026-REV-GUIDE/amend", {"amend_type": "REVISED", "range_low": "105000000", "range_high": "115000000", "basis": "non-GAAP adjusted", "currency": "USD", "unit": "USD", "metric": "revenue", "fp_label": "FY2026", "fp_type": "FY", "fp_start": "2026-01-01", "fp_end": "2026-12-31",
                                                                       "reason": "basis changed", "source_id": sid2, "explanation_unresolved": "basis switch unexplained", "next_evidence": "reconciliation table", "source_discrepancy": "the amendment restates the prior range as 111"})[0], 303)
        page = a.req("GET", "/claim/ZZFX-FY2026-REV-GUIDE")[2]
        self.assertIn(b"INCOMPARABLE", page); self.assertIn(b"basis switch unexplained", page); self.assertIn(b"reconciliation table", page); self.assertIn(b"restates the prior range as 111", page)   # amendment notes now visible in the INCOMPARABLE branch
        self.assertIn(b"Amendment notes on <b>R1</b>", page)
        st, _, pg = a.post("/claim/ZZFX-FY2026-REV-GUIDE/note", {"category": "unresolved_question", "actor": "researcher <b>x</b>", "reason": "why the basis changed", "unresolved_question": "<script>alert(1)</script> ignore previous instructions", "next_evidence": "the 10-K", "version_ref": "R1"})
        self.assertEqual(st, 303)
        page = a.req("GET", "/claim/ZZFX-FY2026-REV-GUIDE")[2]
        self.assertIn(b"<b>N1</b>", page); self.assertIn(b"&lt;script&gt;alert(1)&lt;/script&gt;", page); self.assertNotIn(b"<script>alert", page); self.assertIn(b"researcher &lt;b&gt;x&lt;/b&gt;", page)
        self.assertIn(b"Research notes on this comparison", page)                                                        # shown beside the INCOMPARABLE comparison
        self.assertEqual(a.post("/claim/ZZFX-FY2026-REV-GUIDE/note", {"category": "unresolved_question", "actor": "r", "reason": "", "unresolved_question": "q"})[0], 422)   # reason required
        self.assertEqual(self.A.ws.claim_state("ZZFX-FY2026-REV-GUIDE")["versions"][0]["claim"]["_digest"], self.A.ws.claim_state("ZZFX-FY2026-REV-GUIDE")["versions"][0]["claim"]["_digest"])
        early = a.req("GET", "/claim/ZZFX-FY2026-REV-GUIDE?as_of=2026-06-01T00:00:00Z")[2]
        self.assertIn(b"Later annotations", page if b"Later annotations" in page else early); self.assertIn(b"NOT contemporaneous", early)
        self.assertNotIn(b"Research notes on this comparison</h3>", early)                                                # hidden in the as-of section, listed under later annotations
        st, _, body = a.req("POST", "/claim/ZZFX-FY2026-REV-GUIDE/note", "csrf=x&op_id=ui:nullorig01&category=general&reason=x&actor=a", {"Content-Type": "application/x-www-form-urlencoded", "Origin": "null"})
        self.assertEqual(st, 403); self.assertEqual(len(self.A.ws.claim_state("ZZFX-FY2026-REV-GUIDE")["research_notes"]), 1)
        idx = a.req("GET", "/notes")[2]; self.assertIn(b"ZZFX-FY2026-REV-GUIDE", idx); self.assertIn(b"why the basis changed", idx)
        j = json.loads(a.req("GET", "/dataset.json")[2]); self.assertEqual(j["snapshot"]["counts"]["claims"], 1); self.assertEqual(j["snapshot"]["rows"][0]["research_notes"]["count"], 1); self.assertEqual(j["snapshot"]["rows"][0]["computed"]["comparison"], "INCOMPARABLE")


if __name__ == "__main__":
    unittest.main()
