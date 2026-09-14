"""Full-ladder validation on synthetic fixtures (v7 P1): parameterized gates per rung incl. the U550 path,
explicit exclusion reasons, shadow-run/capacity records per rung (never inherited), readiness reasons."""
import json, pathlib, subprocess, sys, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.universe import ladder  # noqa: E402


def cand(t, cik="0001", sessions=300, adv=5e6, fams=("filings", "prices")):
    return {"ticker": t, "cik": cik, "price_sessions": sessions, "adv_usd": adv, "substrate_families": list(fams)}


class Ladder(unittest.TestCase):
    def fixture(self):
        return {"canonical": ["CAN1", "CAN2"], "evidence_only": ["EVO1"],
                "rungs": {"150": {"params": {"min_adv_usd": 1e6}, "candidates": [cand("A"), cand("B"), cand("A"), cand("C", cik=""), cand("D", sessions=100), cand("E", adv=10.0), cand("F", fams=("prices",)), cand("EVO1"), cand("CAN1")],
                                  "shadow_run": {"target": 150, "days_observed": 25, "anomaly_days": 0}, "capacity": {"target": 150, "gpu_h_per_day": 1.52, "ceiling_gpu_h": 2.0, "measured": True}, "fit": {"target": 150, "note": "disclosed"},
                                  "registered_window": {"id": "w"}, "promotion_record": {"id": "p"}, "phase_c_protocol_id": "pc"},
                          "550": {"params": {"min_adv_usd": 5e5}, "candidates": [cand(f"T{i}") for i in range(600)], "shadow_run": None, "capacity": None, "fit": None}}}
    def test_exclusions_and_u550_own_evidence(self):
        out = ladder.validate_ladder(self.fixture())["ladder"]
        r150 = out["150"]; self.assertEqual(r150["status"], "VALIDATED"); self.assertEqual(r150["admitted"], 1)                 # a duplicated ticker is excluded entirely (identity ambiguity)
        ex = r150["excluded"]; self.assertEqual(ex["C"], ["MISSING_CIK"]); self.assertEqual(ex["D"], ["PRICE_HISTORY_SHORT"]); self.assertEqual(ex["E"], ["LIQUIDITY_BELOW_THRESHOLD"])
        self.assertEqual(ex["F"], ["NO_SUBSTRATE_PATH"]); self.assertEqual(ex["EVO1"], ["EVIDENCE_TIER_STOP"]); self.assertEqual(ex["CAN1"], ["CANONICAL_OVERLAP"]); self.assertIn("DUPLICATE_TICKER", ex["A"])
        self.assertEqual(r150["gates"]["G5_SHADOW_RUN"], "PASS"); self.assertTrue(r150["capacity"]["within_ceiling"]); self.assertFalse(r150["ready"]); self.assertIn("admitted names short of target by 147", r150["reasons_not_ready"])
        r550 = out["550"]; self.assertEqual(r550["status"], "VALIDATED"); self.assertEqual(r550["admitted"], 600)
        self.assertEqual(r550["gates"]["G5_SHADOW_RUN"], "MISSING"); self.assertEqual(r550["capacity"]["status"], "UNKNOWN"); self.assertEqual(r550["gates"]["G6_CROSS_SECTIONAL_FIT"], "MISSING")   # nothing inherited from U150
        self.assertFalse(r550["ready"]); self.assertIn("shadow run for this rung missing or anomalous", r550["reasons_not_ready"])
        self.assertEqual(out["250"]["status"], "NO_FIXTURE"); self.assertEqual(out["350"]["status"], "NO_FIXTURE")
    def test_ready_rung_needs_every_dimension(self):
        f = self.fixture(); f["rungs"]["150"]["candidates"] = [cand(f"N{i}") for i in range(148)]
        r = ladder.validate_ladder(f)["ladder"]["150"]; self.assertTrue(r["ready"]); self.assertEqual(r["reasons_not_ready"], [])
        f["rungs"]["150"]["shadow_run"] = {"target": 150, "days_observed": 25, "anomaly_days": 10}
        r = ladder.validate_ladder(f)["ladder"]["150"]; self.assertFalse(r["ready"]); self.assertEqual(r["gates"]["G5_SHADOW_RUN"], "OBSERVED_WITH_ANOMALIES")
    def test_cli_readiness_report_on_fixture(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "f.json"; p.write_text(json.dumps(self.fixture()))
            r = subprocess.run([sys.executable, str(REPO / "tools/yuclaw_ladder_readiness.py"), "--fixture", str(p), "--json"], capture_output=True, text=True, cwd=REPO)
            self.assertEqual(r.returncode, 0, r.stderr); out = json.loads(r.stdout); self.assertIn("ladder", out); self.assertEqual(out["ladder"]["550"]["capacity"]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
