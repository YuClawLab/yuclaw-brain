"""V8-002 §5: reproducible export and fresh-workspace verification — canonical digest excludes operation metadata,
rights filtering, tamper/incomplete/unsafe rejection, recomputation, and publication eligibility kept separate."""
import hashlib, io, json, pathlib, tempfile, unittest, zipfile

from v3.receipts.contracts import canonical_json
from v8.workbench import export, schema, store

D = pathlib.Path(__file__).resolve().parent / "fixtures" / "v8" / "commitments"


class TestExport(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-export-")); self.ws = store.Workspace(self.tmp / "ws")
        rec = schema.from_fixture(json.loads((D / "001_base.json").read_text())); self.cid = rec["claim"]["claim_id"]; r = rec["revisions"][0]
        self.ws.freeze_claim(rec["claim"], op_id="op:freeze-0001")
        self.ws.amend_claim(self.cid, "REVISED", changes={"range": r["claim"]["range"]}, reason="revised", source=r["source"], op_id="op:amend-0001")
        self.ws.record_outcome(self.cid, rec["outcome"], op_id="op:outcome-01")
        st = self.ws.claim_state(self.cid)
        self.ws.record_adjudication(self.cid, reviewer="owner", rule="RANGE_CONTAINS_ACTUAL", evidence=[st["events"][-1]["event_hash"]], reason="agrees", conflicts="", label="IN_RANGE", disputed=False, op_id="op:adj-000001")
        self.exp = export.build_export(self.ws, self.cid, candidate_commit="cand")

    def _members(self, path=None):
        raw = pathlib.Path(path or self.exp["zip_path"]).read_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            return {i.filename: z.read(i) for i in z.infolist()}

    def _rezip(self, members, name="t.zip"):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            for k, d in members.items():
                z.writestr(k, d)
        p = self.tmp / name; p.write_bytes(b.getvalue()); return p

    def test_success_and_canonical_digest_is_operation_independent(self):
        v = export.verify_export(self.exp["zip_path"]); self.assertEqual(v["result"], "SUCCESS", v["first_discrepancy"])
        self.assertEqual(v["recompute"]["result"], "IN_RANGE"); self.assertEqual(v["recompute"]["delta_vs_original_midpoint"], -3000000)
        again = export.build_export(self.ws, self.cid, candidate_commit="cand")
        self.assertEqual(again["canonical_digest"], self.exp["canonical_digest"]); self.assertNotEqual(again["zip_sha256"], self.exp["zip_sha256"])
        man = json.loads(self._members()["EXPORT_MANIFEST.json"]); self.assertEqual(man["candidate"]["commit"], "cand"); self.assertIn("built_at", man)
        can = json.loads(self._members()["canonical.json"]); self.assertNotIn("built_at", json.dumps(can)); self.assertFalse(any(e["kind"] == "EXPORT_BUILT" for e in can["events"]))
        self.assertEqual(len(self.ws.claim_state(self.cid)["exports"]), 2)

    def test_tampered_payload_incomplete_and_forged_results_fail(self):
        m = self._members()
        t = dict(m); t["canonical.json"] = m["canonical.json"].replace(b'"actual":112000000', b'"actual":113000000')
        v = export.verify_export(self._rezip(t)); self.assertEqual(v["result"], "MISMATCH"); self.assertIn("byte mismatch at canonical.json", v["first_discrepancy"])
        t = dict(m); del t["canonical.json"]; v = export.verify_export(self._rezip(t)); self.assertEqual(v["result"], "MISMATCH"); self.assertIn("incomplete", v["first_discrepancy"])
        can = json.loads(m["canonical.json"]); can["results"]["result"] = "OUT_OF_RANGE"; cb = canonical_json(can)
        man = json.loads(m["EXPORT_MANIFEST.json"]); man["canonical_digest"] = hashlib.sha256(cb).hexdigest(); man["files"][0].update(sha256=man["canonical_digest"], size_bytes=len(cb))
        t = dict(m, **{"canonical.json": cb, "EXPORT_MANIFEST.json": json.dumps(man).encode()})
        v = export.verify_export(self._rezip(t)); self.assertEqual(v["result"], "MISMATCH"); self.assertIn("recomputed result IN_RANGE differs", v["first_discrepancy"])
        can = json.loads(m["canonical.json"]); can["versions"][0]["claim"]["range"]["low"] = 113000000; cb = canonical_json(can)
        man["canonical_digest"] = hashlib.sha256(cb).hexdigest(); man["files"][0].update(sha256=man["canonical_digest"], size_bytes=len(cb))
        v = export.verify_export(self._rezip(dict(m, **{"canonical.json": cb, "EXPORT_MANIFEST.json": json.dumps(man).encode()}))); self.assertEqual(v["result"], "MISMATCH"); self.assertIn("claim digest", v["first_discrepancy"])

    def test_unsafe_archives_refused(self):
        b = io.BytesIO(); z = zipfile.ZipFile(b, "w"); z.writestr("../evil", b"x"); z.close(); p = self.tmp / "a.zip"; p.write_bytes(b.getvalue())
        self.assertIn("unsafe member", export.verify_export(p)["first_discrepancy"])
        b = io.BytesIO(); z = zipfile.ZipFile(b, "w"); z.writestr("/abs", b"x"); z.close(); p.write_bytes(b.getvalue()); self.assertIn("unsafe member", export.verify_export(p)["first_discrepancy"])
        b = io.BytesIO(); z = zipfile.ZipFile(b, "w"); zi = zipfile.ZipInfo("link"); zi.external_attr = (0o120777 << 16); z.writestr(zi, "/etc/passwd"); z.close(); p.write_bytes(b.getvalue())
        self.assertIn("symlink", export.verify_export(p)["first_discrepancy"])
        p.write_bytes(b"not a zip"); self.assertEqual(export.verify_export(p)["result"], "UNSUPPORTED")
        b = io.BytesIO(); z = zipfile.ZipFile(b, "w")
        for i in range(export.MAX_MEMBERS + 1):
            z.writestr(f"f{i}", b"x")
        z.close(); p.write_bytes(b.getvalue()); self.assertIn("members", export.verify_export(p)["first_discrepancy"])

    def test_rights_filter_withholds_excerpt_bytes(self):
        ws = store.Workspace(self.tmp / "ws2"); rec = schema.from_fixture(json.loads((D / "001_base.json").read_text()))
        claim = dict(rec["claim"], fictional=False, statement="FY2026 revenue guidance range (authored restatement).", source=dict(rec["claim"]["source"], fictional=False, rights="UNKNOWN"))
        ws.freeze_claim(claim, op_id="op:freeze-0001"); e = export.build_export(ws, self.cid)
        can = json.loads(self._members(e["zip_path"])["canonical.json"])
        self.assertFalse(can["sources"][0]["excerpt_included"]); self.assertNotIn("excerpt", can["sources"][0]); self.assertIsNone(can["versions"][0]["claim"]["source"]["excerpt"])
        self.assertNotIn(rec["claim"]["source"]["excerpt"], self._members(e["zip_path"])["canonical.json"].decode())
        v = export.verify_export(e["zip_path"]); self.assertEqual(v["result"], "SUCCESS")
        self.assertTrue(any(c["check"] == "claim-digest" and c["ok"] is None for c in v["checks"]))
        pe = export.publication_eligibility(can); self.assertFalse(pe["eligible"]); self.assertTrue(any("UNKNOWN" in r for r in pe["reasons"]))

    def test_publication_eligibility_is_separate_and_never_permits(self):
        can = json.loads(self._members()["canonical.json"]); pe = export.publication_eligibility(can)
        self.assertFalse(pe["eligible"]); self.assertFalse(pe["in_packet_permitted_class"]); self.assertTrue(any("PERMITTED class" in r for r in pe["reasons"])); self.assertTrue(any("fictional" in r for r in pe["reasons"]))
        from v3.receipts import packet
        self.assertFalse(any(p.startswith("commitments/") for p in packet.PERMITTED))

    def test_interrupted_build_never_leaves_a_half_zip_under_the_final_name(self):
        zips = sorted(self.ws.exports.glob("*.zip")); self.assertTrue(zips)
        for z in zips:
            self.assertTrue(zipfile.is_zipfile(z)); self.assertFalse(list(self.ws.exports.glob("*.part")))


if __name__ == "__main__":
    unittest.main()
