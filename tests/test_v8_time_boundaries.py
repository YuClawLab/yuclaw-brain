"""V8-010 (TIM-10, TIM-08): historical views at time boundaries — a cutoff one second before availability hides the source, the
availability second itself shows it, a day boundary in UTC is a boundary; a timestamp with a non-UTC offset, without a zone or
naming an impossible date is refused (never converted, never a crash); a source registered long after it became public
(backdated metadata) is placed by its availability in as-of views while the workspace's own observation time stays separate,
and such a record is labelled a retrospective reconstruction."""
import json, pathlib, tempfile, threading, unittest

from tests.test_v8_workbench_server import Client, _src
from v3.receipts.contracts import ContractError
from v8.workbench import dataset, schema, server as S, store

D = pathlib.Path(__file__).resolve().parent / "fixtures" / "v8" / "commitments"


class TestTimeBoundaries(unittest.TestCase):
    def setUp(self):
        self.ws = store.Workspace(pathlib.Path(tempfile.mkdtemp(prefix="wb-time-")) / "ws")
        self.rec = schema.from_fixture(json.loads((D / "001_base.json").read_text())); self.cid = self.rec["claim"]["claim_id"]

    def test_cutoff_is_inclusive_at_the_availability_second_and_utc_day_boundaries_hold(self):
        src = dict(self.rec["claim"]["source"], available_as_of="2026-02-11T00:00:00Z"); claim = dict(self.rec["claim"], source=src)
        self.ws.register_source(src, op_id="op:src-000001"); self.ws.freeze_claim(claim, op_id="op:freeze-0001")
        self.assertIsNone(self.ws.claim_state(self.cid, "2026-02-10T23:59:59Z"))                         # the evening before, in UTC: not yet known
        self.assertIsNotNone(self.ws.claim_state(self.cid, "2026-02-11T00:00:00Z")); self.assertIsNotNone(self.ws.claim_state(self.cid, "2026-02-11T00:00:00.000001Z"))
        self.assertEqual(len(self.ws.events(None, "2026-02-10T23:59:59.999999Z")), 0)

    def test_offsets_missing_zones_and_impossible_dates_are_refused_not_converted(self):
        src = self.rec["claim"]["source"]
        for ts in ("2026-02-10T21:05:00+08:00", "2026-02-10T21:05:00-07:00", "2026-02-10T21:05:00", "2026-02-10 21:05:00Z", "2026-02-30T00:00:00Z", "2026-02-10T24:00:00Z", "2026-13-01T00:00:00Z"):
            with self.assertRaises(ContractError, msg=ts):
                schema.parse_ts(ts)                                                                       # a ContractError, never a bare ValueError from the date library
            with self.assertRaises(ContractError, msg=ts):
                self.ws.register_source(dict(src, available_as_of=ts), op_id="op:src-" + ts[-8:].replace(":", "").replace("+", "p").replace("-", "m"))
        self.assertEqual(len(self.ws.load()["events"]), 0)

    def test_backdated_registration_is_placed_by_availability_and_labelled_retrospective(self):
        rec = self.rec; late = "2027-06-01T10:00:00Z"                                                     # everything is observed long after it became public
        r = rec["revisions"][0]
        for s_, op in ((rec["claim"]["source"], "a"), (r["source"], "b"), (rec["outcome"]["source"], "c")):
            self.ws.register_source(s_, op_id=f"op:src-late-{op}", observed_at=late)
        self.ws.freeze_claim(rec["claim"], op_id="op:freeze-0001", observed_at=late)
        self.ws.amend_claim(self.cid, "REVISED", changes={"range": r["claim"]["range"]}, reason="revised", source=r["source"], op_id="op:amend-0001", observed_at=late)
        self.ws.record_outcome(self.cid, rec["outcome"], op_id="op:outcome-01", observed_at=late)
        before = self.ws.claim_state(self.cid, "2026-03-01T00:00:00Z")                                    # after the original, before the revision became public
        self.assertEqual([v["version_id"] for v in before["versions"]], ["V1"]); self.assertIsNone(before["outcome"])
        self.assertEqual(before["versions"][0]["claim"]["range"]["low"], 110000000)                       # later knowledge never rewrites the original
        ev = before["events"][0]["time"]; self.assertEqual(ev["observed_at"][:19], late[:19]); self.assertEqual(ev["source_available_as_of"], rec["claim"]["source"]["available_as_of"])
        row = dataset.build_snapshot(self.ws)["rows"][0]; self.assertTrue(row["status"]["retrospective"]); self.assertIn("observed", row["status"]["retrospective_reason"])
        # the export of the backdated history verifies and recomputes; the three times travel apart inside it
        from v8.workbench import export
        x = export.build_export(self.ws, self.cid, op_id="op:export-0001"); v = export.verify_export(x["zip_path"])
        self.assertEqual(v["result"], "SUCCESS"); self.assertEqual(v["recompute"]["result"], "IN_RANGE"); self.assertEqual(v["canonical_digest"], x["canonical_digest"])

    def test_the_same_refusals_over_http(self):
        srv = S.WorkbenchServer(self.ws.root.parent / "http", 0); threading.Thread(target=srv.serve_forever, daemon=True).start(); S.Handler.log_message = lambda *a, **k: None
        try:
            c = Client(srv.server_address[1])
            st, _, page = c.req("GET", "/source?as_of=2026-02-30T00:00:00Z"); self.assertEqual(st, 200); self.assertIn(b"is not a real UTC date and time", page)
            st, _, page = c.req("GET", "/source?as_of=2026-02-10T21:05:00%2B08:00"); self.assertEqual(st, 200); self.assertIn(b"is not a UTC timestamp", page)
            st, _, page = c.post("/source/register", _src("0000000000-26-000001", "2026-02-10", "2026-02-30T21:05:00Z", "a passage")); text = page.decode()
            self.assertEqual(st, 422); self.assertIn("is not a real UTC date and time", text); self.assertIn("nothing was written", text); self.assertIn('value="2026-02-30T21:05:00Z"', text); self.assertIn(">a passage</textarea>", text)
            self.assertEqual(len(srv.ws.load()["events"]), 0)
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
