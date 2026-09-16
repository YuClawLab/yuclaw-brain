"""V8-004 §4 — dataset coverage: rows derived from actual stored records, honest empty coverage, deterministic snapshot
identity (no generation time), retained earlier snapshots with an explicit diff, a verifiable dataset export that the
fresh verifier re-derives row by row, and installed resources (nothing read from the checkout)."""
import json, pathlib, tempfile, unittest, zipfile

from v3.receipts.contracts import canonical_json
from v8.workbench import dataset, export, store
from v8.workbench import server as S
from tests.test_v8_research_notes import _ws, NOTE
from tests.test_v8_workbench_server import Client

D = pathlib.Path(__file__).resolve().parent / "fixtures" / "v8" / "commitments"


class TestDataset(unittest.TestCase):
    def test_empty_workspace_has_empty_coverage_and_a_stable_identity(self):
        ws = store.Workspace(pathlib.Path(tempfile.mkdtemp(prefix="wb-ds-")) / "ws"); snap = dataset.build_snapshot(ws)
        self.assertTrue(snap["empty"]); self.assertEqual(snap["rows"], []); self.assertEqual(snap["counts"]["claims"], 0); self.assertEqual(snap["counts"]["issuers"], 0)
        self.assertEqual(dataset.snapshot_digest(snap), dataset.snapshot_digest(dataset.build_snapshot(ws)))
        self.assertNotIn("derived_at", json.dumps(snap)); self.assertNotIn("generated", json.dumps(snap))
        e = export.build_dataset_export(ws); v = export.verify_export(e["zip_path"]); self.assertEqual(v["result"], "SUCCESS"); self.assertTrue(v["recompute"]["empty"])

    def test_rows_derive_from_records_across_fixture_shapes(self):
        rows = {}
        for fx in ("001_base", "002_missing_outcome", "003_withdrawal", "004_incompatible_basis", "006_out_of_range", "007_corrected_source"):
            ws, cid = _ws(fx)
            if fx == "001_base":
                ws.record_note(cid, NOTE, op_id="op:note-0001"); ws.record_adjudication(cid, reviewer="journey-runner (automated test action; not a human review)", rule="RANGE_CONTAINS_ACTUAL", evidence=[], reason="r", conflicts="", label="IN_RANGE", disputed=False, op_id="op:adj-0001")
                ws.record_adjudication(cid, reviewer="second reviewer", rule="RANGE_CONTAINS_ACTUAL", evidence=[], reason="dissent", conflicts="disagrees", label="OUT_OF_RANGE", disputed=True, op_id="op:adj-0002")
            snap = dataset.build_snapshot(ws); self.assertEqual(len(snap["rows"]), 1); rows[fx] = snap["rows"][0]
        r = rows["001_base"]; self.assertEqual(r["computed"]["result"], "IN_RANGE"); self.assertEqual(r["computed"]["comparison"], "COMPARABLE"); self.assertEqual(r["computed"]["comparison_direction"], "LOWERED")
        self.assertEqual(r["research_notes"]["count"], 1); self.assertEqual(len(r["reviewer"]["labels"]), 2); self.assertEqual(r["reviewer"]["labels"][0]["attribution"], "simulated test action"); self.assertEqual(len(r["reviewer"]["disagreement"]), 1)
        self.assertTrue(r["status"]["fictional"]); self.assertFalse(r["status"]["retrospective"]); self.assertEqual(r["status"]["eligibility"], "NOT_RECORDED"); self.assertEqual(r["identifiers"]["versions"], ["V1", "R1"])
        self.assertEqual(rows["002_missing_outcome"]["computed"]["result"], "PENDING_OUTCOME"); self.assertIn("no outcome recorded (PENDING_OUTCOME)", rows["002_missing_outcome"]["coverage_gaps"]); self.assertIsNone(rows["002_missing_outcome"]["outcome"])
        self.assertIsNotNone(rows["003_withdrawal"]["withdrawal"]); self.assertEqual(rows["003_withdrawal"]["computed"]["result"], "WITHDRAWN_BEFORE_OUTCOME"); self.assertIn("withdrawn", rows["003_withdrawal"]["coverage_gaps"])
        self.assertEqual(rows["004_incompatible_basis"]["computed"]["result"], "INCOMPATIBLE_BASIS"); self.assertFalse(rows["004_incompatible_basis"]["computed"]["comparison_permitted"]); self.assertTrue(any("basis" in x for x in rows["004_incompatible_basis"]["unresolved_reasons"]))
        self.assertIn("result unresolved: INCOMPATIBLE_BASIS", rows["004_incompatible_basis"]["coverage_gaps"])            # the INCOMPARABLE comparison row is covered by the server test (basis-changed amendment)
        self.assertEqual(rows["006_out_of_range"]["computed"]["result"], "OUT_OF_RANGE"); self.assertEqual(len(rows["007_corrected_source"]["source_corrections"]), 1)
        for row in rows.values():
            self.assertTrue(all(s["availability_precision"].startswith("second") for s in row["sources"] if s["kind"] == "filing")); self.assertTrue(all(s["observed_at"] for s in row["sources"]))
            self.assertEqual(row["row_digest"], dataset._sha(canonical_json({k: v for k, v in row.items() if k != "row_digest"})))

    def test_eligibility_and_retrospective_status_come_from_records_not_code(self):
        ws, cid = _ws("001_base")
        real = dict(ws.claim_state(cid)["current"]["claim"])
        self.assertEqual(dataset.build_snapshot(ws)["rows"][0]["status"]["eligibility"], "NOT_RECORDED")
        ws.record_note(cid, dict(NOTE, category="eligibility", version_ref=None, unresolved_question="", next_evidence="", reason="NOT_ELIGIBLE_UNDER_V8_001_CRITERIA (criterion 1: not in the v7 corpus)", simulated=True), op_id="op:elig-0001")
        row = dataset.build_snapshot(ws)["rows"][0]; self.assertTrue(row["status"]["eligibility"].startswith("NOT_ELIGIBLE_UNDER_V8_001_CRITERIA")); self.assertEqual(row["status"]["eligibility_note"], "N1"); self.assertNotIn("eligibility not recorded in this workspace", row["coverage_gaps"])
        self.assertIn(real["issuer"]["name"], json.dumps(row))                                                                 # the issuer comes from the record

    def test_corrected_record_retains_earlier_snapshot_and_identifies_the_change(self):
        ws, cid = _ws("001_base"); e1 = export.build_dataset_export(ws); s1 = dataset.build_snapshot(ws)
        ws.record_note(cid, NOTE, op_id="op:note-0001"); s2 = dataset.build_snapshot(ws)
        self.assertNotEqual(dataset.snapshot_digest(s1), dataset.snapshot_digest(s2))
        prev = export.previous_snapshots(ws); self.assertEqual(len(prev), 1); self.assertTrue(prev[0]["retained"]); self.assertEqual(prev[0]["snapshot_digest"], dataset.snapshot_digest(s1))
        d = dataset.diff_snapshots(prev[0]["snapshot"], s2); self.assertEqual(d["changed"], {cid: ["research_notes"]}); self.assertEqual(d["added"], []); self.assertEqual(d["previous"], dataset.snapshot_digest(s1))
        e2 = export.build_dataset_export(ws); self.assertNotEqual(e1["snapshot_digest"], e2["snapshot_digest"]); self.assertEqual(len(export.previous_snapshots(ws)), 2)
        self.assertEqual(export.verify_export(e1["zip_path"])["result"], "SUCCESS")                                              # the earlier snapshot still verifies

    def test_dataset_export_rows_are_rederived_and_tampering_is_caught(self):
        ws, cid = _ws("001_base"); ws.record_note(cid, NOTE, op_id="op:note-0001"); e = export.build_dataset_export(ws)
        v = export.verify_export(e["zip_path"]); self.assertEqual(v["result"], "SUCCESS"); self.assertEqual(v["recompute"]["rows"], 1); self.assertTrue(any(c["check"] == "recompute-rows" and c["ok"] for c in v["checks"]))
        with zipfile.ZipFile(e["zip_path"]) as z:
            m = {i.filename: z.read(i) for i in z.infolist()}
        can = json.loads(m["dataset.json"]); can["snapshot"]["rows"][0]["computed"]["result"] = "OUT_OF_RANGE"; cb = canonical_json(can)
        import hashlib; man = json.loads(m["EXPORT_MANIFEST.json"]); man["canonical_digest"] = hashlib.sha256(cb).hexdigest(); man["files"][0].update(sha256=man["canonical_digest"], size_bytes=len(cb))
        p = pathlib.Path(e["zip_path"]).with_name("forged_row.zip")
        with zipfile.ZipFile(p, "w") as z:
            for k, val in dict(m, **{"dataset.json": cb, "EXPORT_MANIFEST.json": json.dumps(man).encode()}).items():
                z.writestr(k, val)
        v2 = export.verify_export(p); self.assertEqual(v2["result"], "MISMATCH"); self.assertIn("do not reproduce", v2["first_discrepancy"])

    def test_dataset_page_empty_state_and_rows_over_http(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-ds-srv-")); A = S.WorkbenchServer(tmp / "A", 0, candidate_commit="cand"); S.Handler.log_message = lambda *a, **k: None
        import threading; threading.Thread(target=A.serve_forever, daemon=True).start()
        try:
            a = Client(A.server_address[1]); st, _, page = a.req("GET", "/dataset"); self.assertEqual(st, 200); self.assertIn(b"Coverage is empty", page); self.assertIn(b"no rows", page); self.assertNotIn(b"ZZFX", page)
            self.assertEqual(a.post("/fixtures/load", {"fixture": "001_base"})[0], 303)
            page = a.req("GET", "/dataset")[2]; self.assertNotIn(b"Coverage is empty", page); self.assertIn(b"ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base", page); self.assertIn(b"FICTIONAL", page); self.assertIn(b"IN_RANGE", page)
            st, h, _ = a.post("/dataset/export", {}); self.assertEqual(st, 303); eid = h["Location"].split("built=")[1]
            st, h, zb = a.req("GET", f"/exports/{eid}.zip"); self.assertEqual(st, 200)
            page = a.req("GET", "/dataset")[2]; self.assertIn(eid.encode(), page); self.assertIn(b"retained", page)
            pathlib.Path(tmp / "d.zip").write_bytes(zb); self.assertEqual(export.verify_export(tmp / "d.zip")["result"], "SUCCESS")
        finally:
            A.shutdown()

    def test_installed_resources_only(self):
        src = pathlib.Path(S.__file__).read_text() + pathlib.Path(dataset.__file__).read_text() + pathlib.Path(export.__file__).read_text()
        self.assertNotIn('"tests" /', src.replace('_REPO / "tests"', ""))                                                      # no runtime read of the checkout's tests tree
        self.assertIn('parent / "resources"', pathlib.Path(export.__file__).read_text())


if __name__ == "__main__":
    unittest.main()
