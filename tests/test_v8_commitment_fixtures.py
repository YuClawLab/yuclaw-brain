"""V8-001 §5 fixture validation: the fictional commitment fixtures are self-consistent and explicit.
This test validates FIXTURES ONLY (schema, fictional marking, explicit currency/period/basis/availability dates,
range ordering, manifest hashes, and the arithmetic the expected block claims). It exercises no product code and
proves no workbench step — a step counts only when demonstrated through the browser on the integrated candidate."""
import hashlib, json, pathlib, unittest

D = pathlib.Path(__file__).resolve().parent / "fixtures" / "v8" / "commitments"
DATE = "%Y-%m-%d"


def _is_date(s):
    import datetime
    try: datetime.datetime.strptime(s, DATE); return True
    except Exception: return False


def _is_utc_ts(s):
    return isinstance(s, str) and s.endswith("Z") and "T" in s and len(s) == 20


class TestCommitmentFixtures(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((D / "manifest.json").read_text())
        self.fixtures = {e["path"]: json.loads((D / pathlib.Path(e["path"]).name).read_text()) for e in self.manifest["files"]}

    def test_manifest_hashes_and_count(self):
        self.assertEqual(len(self.manifest["files"]), 7)
        for e in self.manifest["files"]:
            b = (D / pathlib.Path(e["path"]).name).read_bytes()
            self.assertEqual(hashlib.sha256(b).hexdigest(), e["sha256"], e["path"]); self.assertEqual(len(b), e["bytes"])
        self.assertEqual({e["variant"] for e in self.manifest["files"]},
                         {"base", "missing_outcome", "withdrawal", "incompatible_basis", "unit_mismatch", "out_of_range_outcome", "corrected_source"})

    def test_every_fixture_is_marked_fictional_and_explicit(self):
        for path, f in self.fixtures.items():
            self.assertEqual(f["schema"], "yuclaw-commitment-fixture/1"); self.assertTrue(f["fictional"]); self.assertIn("FICTIONAL", f["fictional_notice"])
            self.assertEqual(f["issuer"]["ticker"], "ZZFX"); self.assertEqual(f["issuer"]["cik"], "0000000000")
            c = f["claim"]
            self.assertEqual(c["currency"], "USD"); self.assertEqual(c["unit"], "USD"); self.assertEqual(c["basis"], "GAAP")
            self.assertTrue(_is_date(c["fiscal_period"]["start"]) and _is_date(c["fiscal_period"]["end"]) and _is_date(c["stated_at"]))
            self.assertLess(c["range"]["low"], c["range"]["high"])
            for s in [c["source"]] + [r["source"] for r in f["revisions"]] + ([f["outcome"]["source"]] if f["outcome"] else []):
                self.assertTrue(s["fictional"]); self.assertTrue(s["accession"].startswith("0000000000-26-"))
                self.assertTrue(_is_date(s["filed_at"]) and _is_utc_ts(s["available_as_of"]), path)
                self.assertEqual(s["source_hash"], hashlib.sha256(s["excerpt"].encode()).hexdigest())
            self.assertIn("Not investment advice", f["not_advice"])

    def test_expected_block_arithmetic_is_reproducible_from_the_data(self):
        for path, f in self.fixtures.items():
            c, exp, out = f["claim"], f["expected"], f["outcome"]
            revised = [r for r in f["revisions"] if r["type"] == "REVISED"]
            self.assertEqual(exp["history_events"], 1 + len(f["revisions"]) + (1 if out else 0), path)
            withdrawn = any(r["type"] == "WITHDRAWN" for r in f["revisions"])
            if out is None:
                self.assertEqual(exp["adjudication"], "PENDING_OUTCOME"); self.assertFalse(exp["comparison_permitted"]); continue
            if withdrawn:
                self.assertEqual(exp["adjudication"], "WITHDRAWN_BEFORE_OUTCOME"); self.assertFalse(exp["comparison_permitted"]); continue
            if out["basis"] != c["basis"]:
                self.assertEqual(exp["adjudication"], "INCOMPATIBLE_BASIS"); self.assertFalse(out["comparable"]); self.assertFalse(exp["comparison_permitted"]); continue
            if out["unit"] != c["unit"] or out["currency"] != c["currency"]:
                self.assertEqual(exp["adjudication"], "UNIT_MISMATCH"); self.assertFalse(out["comparable"]); self.assertFalse(exp["comparison_permitted"]); continue
            self.assertTrue(out["comparable"] and exp["comparison_permitted"], path)
            a, lo, hi = out["actual"], c["range"]["low"], c["range"]["high"]
            self.assertEqual(exp["original_contains_actual"], lo <= a <= hi)
            self.assertEqual(exp["delta_vs_original_midpoint"], a - (lo + hi) // 2)
            rlo, rhi = revised[-1]["range"]["low"], revised[-1]["range"]["high"]
            self.assertEqual(exp["revised_contains_actual"], rlo <= a <= rhi)
            self.assertEqual(exp["delta_vs_revised_midpoint"], a - (rlo + rhi) // 2)
            self.assertEqual(exp["adjudication"], "IN_RANGE" if exp["revised_contains_actual"] else "OUT_OF_RANGE")

    def test_corrected_source_retains_the_original_record(self):
        f = self.fixtures["tests/fixtures/v8/commitments/007_corrected_source.json"]
        corr = [r for r in f["revisions"] if r["type"] == "CORRECTED_SOURCE"]
        self.assertEqual(len(corr), 1); self.assertEqual(corr[0]["supersedes"]["accession"], f["claim"]["source"]["accession"])
        self.assertIn("never rewritten", corr[0]["supersedes"]["reason"]); self.assertTrue(f["expected"]["uses_corrected_range"])


if __name__ == "__main__":
    unittest.main()
