"""Phase-5 contribution anatomy on SYNTHETIC why-JSON: rounding reconciliation, gated zero contributions, negatives, mismatch reporting; the published example is read only to show that no weights are published."""
import json, pathlib, subprocess, sys, tempfile, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.anatomy.contribution import AnatomyError, decompose, reconcile  # noqa: E402


class Anatomy(unittest.TestCase):
    def test_reconcile_gated_negative_and_rounding(self):
        why = {"components": {"c1": 0.5, "c2": 0.9, "c3": -0.2}, "score": round(0.5 * 1.0 * 0.4 + 0 + (-0.2) * 0.5 * 0.3, 4)}   # c2 gated → 0
        an = decompose(why, {"weights": {"c1": 0.4, "c2": 0.3, "c3": 0.3}, "confidence": {"c1": 1.0, "c2": 0.2, "c3": 0.5}, "gates": {"c2": "confidence-gated"}})
        rows = {r["component"]: r for r in an["contributions"]}
        self.assertEqual(rows["c2"]["contribution"], 0.0); self.assertTrue(rows["c2"]["gated"]); self.assertEqual(rows["c2"]["gate_reason"], "confidence-gated"); self.assertLess(rows["c3"]["contribution"], 0)
        self.assertEqual(reconcile(an)["verdict"], "RECONCILED")
        why_bad = dict(why, score=why["score"] + 0.01); self.assertEqual(reconcile(decompose(why_bad, {"weights": {"c1": 0.4, "c2": 0.3, "c3": 0.3}, "confidence": {"c1": 1.0, "c2": 0.2, "c3": 0.5}, "gates": {"c2": "g"}}))["verdict"], "TOTAL_MISMATCH")
        an["expected_contributions"] = {"c1": 0.2, "c3": 0.1}; r = reconcile(an); self.assertEqual(r["verdict"], "COMPONENT_MISMATCH"); self.assertEqual(r["mismatches"][0]["component"], "c3")
        zero = decompose({"components": {"c1": 0.0}, "score": 0.0}, {"weights": {"c1": 1.0}, "confidence": {"c1": 1.0}}); self.assertEqual(reconcile(zero)["verdict"], "RECONCILED")
        single = decompose({"components": {"c1": 0.123456789}, "score": 0.1235}, {"weights": {"c1": 1.0}, "confidence": {"c1": 1.0}}); self.assertEqual(reconcile(single)["verdict"], "RECONCILED")   # rounding of the composite tolerated
        with self.assertRaises(AnatomyError): decompose(why, {"weights": {"c1": 0.4}, "confidence": {"c1": 1.0}})
        with self.assertRaises(AnatomyError): decompose(why, {"weights": {"c1": 0.4, "c2": 0.3, "c3": 0.3}, "confidence": {"c1": 2.0, "c2": 0.2, "c3": 0.5}})
    def test_command_and_published_example_without_weights(self):
        with tempfile.TemporaryDirectory() as d:
            w = pathlib.Path(d) / "why.json"; w.write_text(json.dumps({"components": {"c1": 0.5}, "score": 0.25})); a = pathlib.Path(d) / "an.json"; a.write_text(json.dumps({"weights": {"c1": 0.5}, "confidence": {"c1": 1.0}}))
            r = subprocess.run([sys.executable, str(REPO / "tools/yuclaw_contribution_anatomy.py"), str(w), "--anatomy", str(a)], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("RECONCILED", r.stdout)
            r = subprocess.run([sys.executable, str(REPO / "tools/yuclaw_contribution_anatomy.py"), str(REPO / "docs/why/AAPL.json")], capture_output=True, text=True); self.assertEqual(r.returncode, 3); self.assertIn("NOT_POSSIBLE", r.stdout)   # published example: weights not published


if __name__ == "__main__":
    unittest.main(verbosity=2)
