"""V8-011 (TIM-08): a wrong source-availability time is corrected with a linked, append-only event — never by editing the record.

Focused cases: a correction to a LATER and to an EARLIER time; the historical view before and after the correction was recorded
(a later correction is listed as later, never applied to an earlier cutoff, and never makes a source known earlier); a retried,
a conflicting and an out-of-date correction; the recomputed result and retrospective status shown beside the unchanged record;
the correction chain verified from an export in a fresh workspace, with altered counterparts refused; the browser action under
the existing session, Origin and CSRF controls."""
import io, json, pathlib, tempfile, threading, unittest, zipfile
from unittest import mock

from tests.test_v8_workbench_server import Client
from v3.receipts.contracts import ContractError, canonical_json
from v8.workbench import availability, calc, dataset, export, schema, server as S, store

D = pathlib.Path(__file__).resolve().parent / "fixtures" / "v8" / "commitments"
WHY = {"reason": "the registered time was the press-release dateline, not the EDGAR acceptance time", "evidence_ref": "EDGAR filing index, acceptance line (fictional fixture)", "actor": "test researcher"}


def at(ts):
    """The server's local action time while a correction is recorded (it is never supplied by the caller)."""
    return mock.patch.object(store, "now_ts", lambda: ts)


def load(ws, name, observed=None):
    rec = schema.from_fixture(json.loads((D / f"{name}.json").read_text())); cid = rec["claim"]["claim_id"]; n = [0]
    def op(tag):
        n[0] += 1; return f"op:{tag}-{n[0]:04d}"
    seen = lambda s: observed or s["available_as_of"]
    ws.register_source(rec["claim"]["source"], op_id=op("src"), observed_at=seen(rec["claim"]["source"])); ws.freeze_claim(rec["claim"], op_id=op("freeze"), observed_at=seen(rec["claim"]["source"]))
    for r in rec["revisions"]:
        ws.register_source(r["source"], op_id=op("src"), observed_at=seen(r["source"]))
        if r["type"] == "WITHDRAWN":
            ws.amend_claim(cid, "WITHDRAWN", changes=None, reason="withdrawn", source=r["source"], op_id=op("amend"), observed_at=seen(r["source"]))
        else:
            ws.amend_claim(cid, r["type"], changes={"range": r["claim"]["range"]}, reason="revised", source=r["source"], op_id=op("amend"), observed_at=seen(r["source"]))
    if rec["outcome"]:
        ws.register_source(rec["outcome"]["source"], op_id=op("src"), observed_at=seen(rec["outcome"]["source"])); ws.record_outcome(cid, rec["outcome"], op_id=op("outcome"), observed_at=seen(rec["outcome"]["source"]))
    return rec, cid


def retamper(zip_path, mutate, member="canonical.json"):
    """A counterpart of an export whose content was altered AND whose declared digests were recomputed to match, so that only
    the content checks — not the plain byte check — can refuse it."""
    with zipfile.ZipFile(zip_path) as z:
        members = {n: z.read(n) for n in z.namelist()}
    can = json.loads(members[member]); mutate(can); members[member] = canonical_json(can)
    man = json.loads(members["EXPORT_MANIFEST.json"]); dig = export._sha(members[member]); man["canonical_digest"] = dig
    for f in man["files"]:
        if f["path"] == member:
            f["sha256"], f["size_bytes"] = dig, len(members[member])
    members["EXPORT_MANIFEST.json"] = (json.dumps(man, indent=1, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")
    out = pathlib.Path(tempfile.mkdtemp(prefix="wb-tamper-")) / "tampered.zip"
    with zipfile.ZipFile(out, "w") as z:
        for n, b in members.items():
            z.writestr(n, b)
    return out


class TestAvailabilityCorrection(unittest.TestCase):
    def setUp(self):
        self.ws = store.Workspace(pathlib.Path(tempfile.mkdtemp(prefix="wb-avail-")) / "ws")

    def corrections(self):
        return [e for e in self.ws.load()["events"] if e["kind"] == availability.KIND]

    # ------------------------------------------------------------------ later; the view before and after the correction was recorded
    def test_later_correction_applies_from_its_recorded_time_and_is_only_listed_before_it(self):
        rec, cid = load(self.ws, "002_missing_outcome"); src = rec["claim"]["source"]; sid = availability.source_id(src)          # registered available 2026-02-10T21:05:00Z
        before = self.ws.log.read_bytes(); digest0 = self.ws.claim_state(cid)["versions"][0]["claim"]["_digest"]
        with at("2026-02-11T00:00:00.000000Z"):
            ev, dup = self.ws.correct_source_availability(sid, dict(WHY, corrected_available_as_of="2026-02-12T09:00:00Z"), expected_prior=src["available_as_of"], op_id="op:correct-0001")
        self.assertFalse(dup); p = ev["payload"]
        self.assertEqual((p["correction_id"], p["direction"], p["prior_available_as_of"], p["corrected_available_as_of"]), ("AC1", "LATER", src["available_as_of"], "2026-02-12T09:00:00Z"))
        self.assertTrue(self.ws.log.read_bytes().startswith(before))                                       # every earlier durable line is byte-identical: nothing was edited
        reg = next(e for e in self.ws.load()["events"] if e["kind"] == "SOURCE_REGISTERED" and e["payload"]["source_id"] == sid)
        self.assertEqual((p["registration_event"], p["prior_event"], p["source_hash"]), (reg["event_hash"], reg["event_hash"], src["source_hash"]))
        self.assertEqual(reg["payload"]["source"]["available_as_of"], src["available_as_of"]); self.assertEqual(reg["time"]["observed_at"], src["available_as_of"])
        self.assertIsNone(ev["time"]["source_available_as_of"]); self.assertEqual(ev["time"]["recorded_at"], "2026-02-11T00:00:00.000000Z")   # three times apart; the recording time is the server's
        # BEFORE the correction was recorded: the view keeps what the record held then, and lists the correction as later
        early = self.ws.claim_state(cid, "2026-02-10T22:00:00Z"); self.assertIsNotNone(early)
        self.assertEqual([len(early["availability"][sid][k]) for k in ("applied", "later")], [0, 1])
        self.assertNotIn(availability.KIND, [e["kind"] for e in self.ws.events(None, "2026-02-10T22:00:00Z")])
        note = availability.later_at(self.ws.claim_state(cid), availability.index(self.ws.events(), "2026-02-10T22:00:00Z"), "2026-02-10T22:00:00Z")
        self.assertEqual([(x["correction_id"], x["public_as_held"], x["public_under_correction"]) for x in note], [("AC1", True, False)])
        # AFTER it was recorded: the corrected availability cuts the view — not yet public at noon on the 11th, public from the corrected second
        self.assertIsNone(self.ws.claim_state(cid, "2026-02-11T12:00:00Z")); self.assertIsNone(self.ws.claim_state(cid, "2026-02-12T08:59:59Z"))
        self.assertIsNotNone(self.ws.claim_state(cid, "2026-02-12T09:00:00Z"))
        now = self.ws.claim_state(cid)
        self.assertEqual(now["versions"][0]["claim"]["_digest"], digest0); self.assertEqual(now["versions"][0]["claim"]["source"]["available_as_of"], src["available_as_of"])   # the frozen claim still says what it said
        self.assertEqual(availability.effective_for(now, src), "2026-02-12T09:00:00Z")

    # ------------------------------------------------------------------ earlier: a later correction never makes a source known earlier
    def test_earlier_correction_never_turns_a_later_record_into_earlier_knowledge(self):
        rec, cid = load(self.ws, "002_missing_outcome"); src = rec["claim"]["source"]; sid = availability.source_id(src)
        with at("2026-03-01T00:00:00.000000Z"):
            ev, _ = self.ws.correct_source_availability(sid, dict(WHY, corrected_available_as_of="2026-02-10T13:30:00Z"), expected_prior=src["available_as_of"], op_id="op:correct-0001")
        self.assertEqual(ev["payload"]["direction"], "EARLIER")
        cut = "2026-02-10T18:00:00Z"                                                                       # between the corrected and the registered time, before the correction existed
        self.assertIsNone(self.ws.claim_state(cid, cut)); self.assertEqual(self.ws.events(None, cut), [])
        note = availability.later_at(self.ws.claim_state(cid), availability.index(self.ws.events(), cut), cut)
        self.assertEqual([(x["public_as_held"], x["public_under_correction"]) for x in note], [(False, True)])   # listed as later knowledge; the view is not rewritten
        after = self.ws.claim_state(cid, "2026-03-02T00:00:00Z")
        self.assertEqual(after["availability"][sid]["effective"], "2026-02-10T13:30:00Z"); self.assertEqual(len(after["availability"][sid]["applied"]), 1)
        n = len(self.ws.load()["events"])
        with self.assertRaisesRegex(ContractError, "precedes the source's filing date"):
            self.ws.correct_source_availability(sid, dict(WHY, corrected_available_as_of="2026-02-09T23:00:00Z"), expected_prior="2026-02-10T13:30:00Z", op_id="op:correct-0002")
        self.assertEqual(len(self.ws.load()["events"]), n)

    # ------------------------------------------------------------------ retried, conflicting and out-of-date corrections
    def test_retry_conflict_stale_update_and_concurrent_corrections(self):
        rec, cid = load(self.ws, "002_missing_outcome"); src = rec["claim"]["source"]; sid = availability.source_id(src)
        raw = dict(WHY, corrected_available_as_of="2026-02-12T09:00:00Z")
        e1, d1 = self.ws.correct_source_availability(sid, raw, expected_prior=src["available_as_of"], op_id="op:correct-0001")
        e2, d2 = self.ws.correct_source_availability(sid, raw, expected_prior=src["available_as_of"], op_id="op:correct-0001")          # the same operation again: no second durable event
        self.assertEqual((d1, d2, e1["event_hash"]), (False, True, e2["event_hash"])); self.assertEqual(len(self.corrections()), 1)
        with self.assertRaises(store.StoreIntegrityError) as cm:                                           # the same operation identifier with different content is a conflict
            self.ws.correct_source_availability(sid, dict(raw, corrected_available_as_of="2026-02-13T09:00:00Z"), expected_prior=src["available_as_of"], op_id="op:correct-0001")
        self.assertEqual(cm.exception.code, "E_OP_CONFLICT")
        with self.assertRaisesRegex(ContractError, "now reads 2026-02-12T09:00:00Z"):                        # prepared against the registered value, which is no longer in force
            self.ws.correct_source_availability(sid, dict(raw, corrected_available_as_of="2026-02-13T09:00:00Z"), expected_prior=src["available_as_of"], op_id="op:correct-0002")
        for bad, why in ((dict(raw), "equals the availability already in force"), (dict(raw, reason="", evidence_ref="", actor=""), "correction.reason: required; correction.evidence_ref: required; correction.actor: required"),
                         (dict(raw, corrected_available_as_of="2026-02-30T09:00:00Z"), "not a real UTC date"), (dict(raw, corrected_available_as_of="2026-02-12T09:00:00+08:00"), "not RFC3339 UTC")):
            with self.assertRaisesRegex(ContractError, why):
                self.ws.correct_source_availability(sid, bad, expected_prior="2026-02-12T09:00:00Z", op_id="op:correct-0003")
        with self.assertRaisesRegex(ContractError, "choose a registered source"):
            self.ws.correct_source_availability("0000000000-26-999999:" + "0" * 16, raw, expected_prior="", op_id="op:correct-0004")
        self.assertEqual(len(self.corrections()), 1)
        e3, _ = self.ws.correct_source_availability(sid, dict(raw, corrected_available_as_of="2026-02-11T08:00:00Z"), expected_prior="2026-02-12T09:00:00Z", op_id="op:correct-0005")
        self.assertEqual((e3["payload"]["correction_id"], e3["payload"]["prior_event"], e3["payload"]["prior_available_as_of"], e3["payload"]["registered_available_as_of"]), ("AC2", e1["event_hash"], "2026-02-12T09:00:00Z", src["available_as_of"]))
        self.assertIsNone(availability.chain_problem(self.ws.load()["events"]))
        # two people correct the same source from the same page: exactly one is recorded, the other is refused as out of date
        results = []
        def go(i):
            try:
                self.ws.correct_source_availability(sid, dict(raw, corrected_available_as_of=f"2026-02-1{3 + i}T09:00:00Z"), expected_prior="2026-02-11T08:00:00Z", op_id=f"op:race-{i:06d}"); results.append("recorded")
            except ContractError:
                results.append("refused")
        ts = [threading.Thread(target=go, args=(i,)) for i in range(2)]; [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(sorted(results), ["recorded", "refused"]); self.assertEqual(len(self.corrections()), 3); self.assertEqual(self.ws.status()["integrity"], "OK")

    # ------------------------------------------------------------------ eligibility recomputed beside the record, never over it
    def test_corrected_view_is_recomputed_beside_the_record_and_flags_what_needs_review(self):
        rec, cid = load(self.ws, "003_withdrawal"); st = self.ws.claim_state(cid); wsrc = st["withdrawn"]["source"]; sid = availability.source_id(wsrc)
        self.assertEqual(calc.adjudicate(st)["result"], "WITHDRAWN_BEFORE_OUTCOME")
        adj, _ = self.ws.record_adjudication(cid, reviewer="test reviewer", rule="RANGE_CONTAINS_ACTUAL", evidence=[st["events"][0]["event_hash"]], reason="withdrawn before the outcome", conflicts="", label="WITHDRAWN_BEFORE_OUTCOME", disputed=False, op_id="op:adjudicate-01")
        row0 = dataset.build_snapshot(self.ws)["rows"][0]; self.assertNotIn("availability_corrections", row0)
        ev, _ = self.ws.correct_source_availability(sid, dict(WHY, corrected_available_as_of="2027-03-01T00:00:00Z"), expected_prior=wsrc["available_as_of"], op_id="op:correct-0001")   # the withdrawal became public AFTER the outcome
        now = self.ws.claim_state(cid); blk = availability.block(now); v = blk["corrected_view"]
        self.assertEqual(calc.adjudicate(now)["result"], "WITHDRAWN_BEFORE_OUTCOME")                        # the as-recorded calculation is what it was
        self.assertEqual(v["recorded_result"], "WITHDRAWN_BEFORE_OUTCOME"); self.assertIn(v["result"], ("IN_RANGE", "OUT_OF_RANGE")); self.assertTrue(v["result_changes"]); self.assertTrue(blk["needs_review"])
        self.assertIn("WITHDRAWN_AFTER_OUTCOME", [r["code"] for r in blk["corrected_results"]["reasons"]])
        self.assertTrue({"RESULT_CHANGES", "ADJUDICATION_PREDATES_CORRECTION", "AVAILABILITY_AFTER_OBSERVATION"} <= {r["code"] for r in blk["review"]})
        self.assertEqual([a["event_hash"] for a in now["adjudications"]], [adj["event_hash"]]); self.assertEqual(now["adjudications"][0]["computed_result"], "WITHDRAWN_BEFORE_OUTCOME")   # retained unchanged
        row = dataset.build_snapshot(self.ws)["rows"][0]
        self.assertEqual(row["computed"], row0["computed"]); self.assertEqual(row["withdrawal"], row0["withdrawal"]); self.assertEqual(row["availability_corrections"]["corrected_view"]["result"], v["result"])
        self.assertTrue(any(g.startswith("source availability corrected after registration") for g in row["coverage_gaps"]))
        # a further review may cite the correction event; a label that differs from the as-recorded result is still a declared dispute
        with self.assertRaisesRegex(ContractError, "differs from the computed result"):
            self.ws.record_adjudication(cid, reviewer="test reviewer", rule="RANGE_CONTAINS_ACTUAL", evidence=[ev["event_hash"]], reason="corrected view", conflicts="", label=v["result"], disputed=False, op_id="op:adjudicate-02")
        a2, _ = self.ws.record_adjudication(cid, reviewer="test reviewer", rule="RANGE_CONTAINS_ACTUAL", evidence=[ev["event_hash"]], reason="the withdrawal was public only after the outcome (AC1)", conflicts="as-recorded result differs", label=v["result"], disputed=True, op_id="op:adjudicate-03")
        self.assertEqual(a2["payload"]["availability_corrected_view"], {"result": v["result"], "result_changes": True, "corrections": ["AC1"]}); self.assertEqual(a2["payload"]["computed_result"], "WITHDRAWN_BEFORE_OUTCOME")

    def test_a_correction_never_upgrades_a_retrospective_record(self):
        rec, cid = load(self.ws, "001_base", observed="2027-06-01T10:00:00Z"); osrc = rec["outcome"]["source"]            # everything observed long after it was public: RETROSPECTIVE
        self.assertTrue(dataset.build_snapshot(self.ws)["rows"][0]["status"]["retrospective"])
        self.ws.correct_source_availability(availability.source_id(osrc), dict(WHY, corrected_available_as_of="2027-07-01T00:00:00Z"), expected_prior=osrc["available_as_of"], op_id="op:correct-0001")
        blk = availability.block(self.ws.claim_state(cid)); v = blk["corrected_view"]
        self.assertEqual((v["recorded_retrospective"], v["recomputed_retrospective"], v["retrospective"]), (True, False, True))
        self.assertIn("RETROSPECTIVE_STATUS_RETAINED", [r["code"] for r in blk["review"]])
        row = dataset.build_snapshot(self.ws)["rows"][0]; self.assertTrue(row["status"]["retrospective"]); self.assertEqual(dataset.build_snapshot(self.ws)["counts"]["retrospective"], 1)

    # ------------------------------------------------------------------ export: the chain travels, a fresh workspace recomputes it, altered counterparts are refused
    def test_export_carries_the_chain_and_a_fresh_workspace_verifies_it_while_tampered_counterparts_are_refused(self):
        rec, cid = load(self.ws, "003_withdrawal"); st = self.ws.claim_state(cid); wsrc = st["withdrawn"]["source"]; sid = availability.source_id(wsrc)
        plain = export.build_export(self.ws, cid, op_id="op:export-0001")                                   # before any correction
        with zipfile.ZipFile(plain["zip_path"]) as z:
            can0 = json.loads(z.read("canonical.json"))
        self.assertNotIn("source_availability", can0); self.assertNotIn("availability_corrections", can0["dataset_row"])
        self.ws.correct_source_availability(sid, dict(WHY, corrected_available_as_of="2027-03-01T00:00:00Z"), expected_prior=wsrc["available_as_of"], op_id="op:correct-0001")
        x = export.build_export(self.ws, cid, op_id="op:export-0002"); v = export.verify_export(x["zip_path"])
        self.assertEqual(v["result"], "SUCCESS", v["first_discrepancy"]); self.assertEqual(v["recompute"]["result"], "WITHDRAWN_BEFORE_OUTCOME")
        self.assertEqual([c["ok"] for c in v["checks"] if c["check"] == "recompute-source-availability"], [True])
        with zipfile.ZipFile(x["zip_path"]) as z:
            can = json.loads(z.read("canonical.json"))
        kinds = [e["kind"] for e in can["events"]]; self.assertIn(availability.KIND, kinds)
        reg = next(e for e in can["events"] if e["kind"] == "SOURCE_REGISTERED" and e["payload"]["source_id"] == sid); self.assertEqual(reg["payload"]["source"]["available_as_of"], wsrc["available_as_of"])   # the original registration travels unchanged
        blk = can["source_availability"]; self.assertEqual(blk["effect_rule"], availability.EFFECT_RULE); self.assertEqual(blk["sources"][0]["registration"]["event_hash"], reg["event_hash"]); self.assertEqual(blk["sources"][0]["effective_available_as_of"], "2027-03-01T00:00:00Z")
        self.assertEqual(can["results"], can0["results"]); self.assertTrue(blk["corrected_view"]["result_changes"])      # the recorded results are what they were; the corrected view sits beside them
        # the export made before the correction still verifies, under the schema it recorded (no block, nothing reinterpreted)
        v0 = export.verify_export(plain["zip_path"]); self.assertEqual(v0["result"], "SUCCESS"); self.assertEqual([c["ok"] for c in v0["checks"] if c["check"] == "recompute-source-availability"], [None])
        def corr(c):
            return next(e for e in c["events"] if e["kind"] == availability.KIND)
        def change_value(c):
            corr(c)["payload"]["corrected_available_as_of"] = "2026-08-05T00:00:00Z"
        def change_value_and_rehash(c):
            e = corr(c); e["payload"]["corrected_available_as_of"] = "2026-08-05T00:00:00Z"; e["event_hash"] = store._line_hash({k: v for k, v in e.items() if k != "event_hash"})
        def relink(c):
            e = corr(c); e["payload"]["registration_event"] = "0" * 64; e["payload"]["prior_event"] = "0" * 64; e["event_hash"] = store._line_hash({k: v for k, v in e.items() if k != "event_hash"})
        def backdate(c):
            e = corr(c); e["time"]["source_available_as_of"] = "2026-01-01T00:00:00Z"; e["event_hash"] = store._line_hash({k: v for k, v in e.items() if k != "event_hash"})
        def change_block(c):
            c["source_availability"]["corrected_view"]["result"] = "WITHDRAWN_BEFORE_OUTCOME"; c["source_availability"]["corrected_view"]["result_changes"] = False; c["source_availability"]["review"] = []; c["source_availability"]["needs_review"] = False
        def drop_block(c):
            del c["source_availability"]
        def drop_event(c):
            c["events"] = [e for e in c["events"] if e["kind"] != availability.KIND]
        for mutate, why in ((change_value, "event_hash does not match"), (change_value_and_rehash, "source availability block differs"), (relink, "not the packed registration"), (backdate, "carries no source availability of its own"),
                            (change_block, "source availability block differs"), (drop_block, "source availability block differs"), (drop_event, "source availability block differs")):
            r = export.verify_export(retamper(x["zip_path"], mutate)); self.assertEqual(r["result"], "MISMATCH", mutate.__name__); self.assertIn(why, r["first_discrepancy"], mutate.__name__)
        # the dataset snapshot carries the same chain per claim and is recomputed the same way
        ds = export.build_dataset_export(self.ws, op_id="op:export-0003"); self.assertEqual(export.verify_export(ds["zip_path"])["result"], "SUCCESS")
        def change_row(c):
            c["snapshot"]["rows"][0]["availability_corrections"]["corrected_view"]["result"] = "WITHDRAWN_BEFORE_OUTCOME"
        r = export.verify_export(retamper(ds["zip_path"], change_row, member="dataset.json")); self.assertEqual(r["result"], "MISMATCH")
        # and through a FRESH workspace's browser endpoint: success for the export, refusal for the altered counterpart, nothing merged
        srv = S.WorkbenchServer(self.ws.root.parent / "fresh", 0); threading.Thread(target=srv.serve_forever, daemon=True).start(); S.Handler.log_message = lambda *a, **k: None
        try:
            c = Client(srv.server_address[1]); _, _, page = c.req("GET", "/verify"); op = lambda: store.new_op_id("ui")
            st_, _, page = c.upload({"csrf": c.csrf, "op_id": op()}, pathlib.Path(x["zip_path"]).read_bytes()); self.assertIn(b"Result: <span class=\"ok\">SUCCESS", page); self.assertIn(b"recompute-source-availability", page)
            st_, _, page = c.upload({"csrf": c.csrf, "op_id": op()}, retamper(x["zip_path"], change_value_and_rehash).read_bytes()); self.assertIn(b"MISMATCH", page); self.assertIn(b"source availability block differs", page)
            self.assertEqual(srv.ws.status()["claims"], [])
        finally:
            srv.shutdown(); srv.server_close()

    def test_an_unrelated_claim_keeps_its_export_identity(self):
        rec, cid = load(self.ws, "003_withdrawal"); wsrc = self.ws.claim_state(cid)["withdrawn"]["source"]
        other = dict(rec["claim"], claim_id="ZZFX-FY2026-OTHER", source=dict(rec["claim"]["source"], accession="0000000000-26-000777", excerpt="another fictional passage", source_hash=__import__("hashlib").sha256(b"another fictional passage").hexdigest()))
        self.ws.register_source(other["source"], op_id="op:src-other1", observed_at=other["source"]["available_as_of"]); self.ws.freeze_claim(other, op_id="op:freeze-other", observed_at=other["source"]["available_as_of"])
        d0 = export.build_export(self.ws, "ZZFX-FY2026-OTHER", op_id="op:export-0001")["canonical_digest"]
        self.ws.correct_source_availability(availability.source_id(wsrc), dict(WHY, corrected_available_as_of="2027-03-01T00:00:00Z"), expected_prior=wsrc["available_as_of"], op_id="op:correct-0001")
        self.assertEqual(export.build_export(self.ws, "ZZFX-FY2026-OTHER", op_id="op:export-0002")["canonical_digest"], d0)   # a correction elsewhere changes nothing here

    # ------------------------------------------------------------------ the browser action: session, Origin, CSRF, validation, retry, stale refusal
    def test_the_browser_action_uses_the_existing_controls(self):
        rec, cid = load(self.ws, "003_withdrawal"); wsrc = self.ws.claim_state(cid)["withdrawn"]["source"]; sid = availability.source_id(wsrc); ref = f"{sid}@{wsrc['available_as_of']}"
        srv = S.WorkbenchServer(self.ws.root, 0); threading.Thread(target=srv.serve_forever, daemon=True).start(); S.Handler.log_message = lambda *a, **k: None
        try:
            c = Client(srv.server_address[1]); _, _, page = c.req("GET", "/source"); self.assertIn(b'id="form-availability"', page); self.assertIn(ref.encode(), page)
            fields = {"source_ref": ref, "corrected_available_as_of": "2027-03-01T00:00:00Z", "reason": WHY["reason"], "evidence_ref": WHY["evidence_ref"], "actor": WHY["actor"], "op_id": "ui:correction-http-0001"}
            st, _, body = c.post("/source/correct-availability", fields, origin=False); self.assertEqual(st, 403); self.assertIn(b"nothing was written", body)
            st, _, body = c.req("POST", "/source/correct-availability", __import__("urllib.parse").parse.urlencode(dict(fields, csrf="0" * 32)), {"Content-Type": "application/x-www-form-urlencoded"}); self.assertEqual(st, 403); self.assertIn(b"CSRF token invalid", body)
            st, _, body = c.post("/source/correct-availability", dict(fields, corrected_available_as_of="2027-02-30T00:00:00Z", reason="")); text = body.decode()
            self.assertEqual(st, 422); self.assertIn("Blocked — nothing was written", text); self.assertIn("is not a real UTC date and time", text); self.assertIn('value="' + WHY["actor"] + '"', text)   # refused with the entries kept
            self.assertEqual(self.corrections(), [])
            st, hdr, _ = c.post("/source/correct-availability", fields); self.assertEqual(st, 303); self.assertEqual(hdr["Location"], "/source?corrected=AC1#availability")
            st, hdr, _ = c.post("/source/correct-availability", fields); self.assertEqual(st, 303); self.assertEqual(len(self.corrections()), 1)                       # the same operation again: still one durable event
            st, _, body = c.post("/source/correct-availability", dict(fields, corrected_available_as_of="2027-04-01T00:00:00Z", op_id="ui:correction-http-0002")); text = body.decode()
            self.assertEqual(st, 422); self.assertIn("now reads 2027-03-01T00:00:00Z", text); self.assertEqual(len(self.corrections()), 1)                              # the page it came from is out of date: refused
            _, _, page = c.req("GET", "/source?corrected=AC1"); text = page.decode(); self.assertIn("Availability correction <b>AC1</b> recorded", text); self.assertIn("corrected to <b>2027-03-01T00:00:00Z</b>", text); self.assertIn(wsrc["available_as_of"], text)
            _, _, page = c.req("GET", f"/claim/{cid}"); text = page.decode()
            self.assertIn("Source availability corrections", text); self.assertIn("as recorded: WITHDRAWN_BEFORE_OUTCOME", text); self.assertIn("RESULT_CHANGES", text); self.assertIn("Overall: <b class=\"warn\">WITHDRAWN_BEFORE_OUTCOME</b>", text)
            _, _, page = c.req("GET", f"/claim/{cid}?as_of=2026-09-01T00:00:00Z"); text = page.decode()                                                         # a cutoff before the correction was recorded
            self.assertIn("Later corrections — recorded after this cutoff", text); self.assertIn("NOT applied to the as-of view", text); self.assertNotIn("corrected to <b>2027-03-01", text)
            _, _, page = c.req("GET", "/source?as_of=2026-09-01T00:00:00Z"); self.assertIn(b"not applied at this cutoff", page)
            _, _, page = c.req("GET", "/journal"); self.assertIn(availability.KIND.encode(), page)
        finally:
            srv.shutdown(); srv.server_close()


if __name__ == "__main__":
    unittest.main()
