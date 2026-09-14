import json, pathlib, sys, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tools"))
import yuclaw_capacity_assessment as ca  # noqa: E402


class Capacity(unittest.TestCase):
    def test_measured_inferred_unknown_separated(self):
        out = ca.assess(ca.DEFAULT)
        self.assertEqual(out["measured"]["350"]["basis"], "MEASURED"); self.assertTrue(out["inferred"]["550"]["basis"].startswith("INFERRED")); self.assertAlmostEqual(out["inferred"]["550"]["gpu_h_per_day"], 2.65, places=2)
        self.assertEqual(out["verdicts"]["150"], "WITHIN_CEILING"); self.assertEqual(out["verdicts"]["350"], "OVER_CEILING"); self.assertEqual(out["verdicts"]["550"], "OVER_CEILING (inferred)")
        self.assertTrue(out["operator_hours"]["basis"].startswith("UNKNOWN")); self.assertEqual(out["rtx_pro_6000"]["status"], "NOT_COMMISSIONED"); self.assertGreaterEqual(len(out["commissioning_checklist"]), 5)
        out2 = ca.assess(dict(ca.DEFAULT, operator_hours_per_week=6, ceiling_gpu_h=None)); self.assertEqual(out2["operator_hours"]["basis"], "SUPPLIED"); self.assertEqual(out2["verdicts"]["150"], "NO_CEILING")


if __name__ == "__main__":
    unittest.main(verbosity=2)
