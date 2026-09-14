import json, pathlib, sys, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tools"))
import yuclaw_ladder_readiness as lr  # noqa: E402
from v3.universe import etf_class_candidate as etf  # noqa: E402


class Ladder(unittest.TestCase):
    def test_no_rung_is_promotable_without_window_decision_and_phase_c(self):
        r = lr.report(); self.assertTrue(r["constitution_gate5_shadow_requirement"])
        for row in r["rungs"]: self.assertFalse(row["promotable_now"]); self.assertFalse(lr.promote_allowed(row))
        by = {row["target"]: row for row in r["rungs"]}
        self.assertEqual(by[550]["implementation"].split(" ")[0], "VALIDATION_PATH_IMPLEMENTED"); self.assertEqual(by[550]["capacity"], "UNKNOWN (not audited)")
        self.assertEqual(by[350]["capacity"], "OVER_BUDGET"); self.assertEqual(by[150]["capacity"], "WITHIN_BUDGET")
    def test_boundary_promotion_requires_every_dimension(self):
        base = dict(registered_window={"start": "2026-10-01"}, promotion_record={"decided": True}, phase_c_protocol_id="pc-1", capacity_h=1.5)
        self.assertTrue(lr.rung_status(150, **base)["promotable_now"])
        for k in ("registered_window", "promotion_record", "phase_c_protocol_id"):
            self.assertFalse(lr.rung_status(150, **dict(base, **{k: None}))["promotable_now"])
        self.assertFalse(lr.rung_status(350, **dict(base, capacity_h=2.29))["promotable_now"])
        self.assertEqual(lr.rung_status(79, **base)["promotion"], "N/A (canonical)")


class EtfClass(unittest.TestCase):
    def test_statuses_distinct_and_registered_set_empty(self):
        self.assertEqual(etf.ETF_SET_AT_REGISTRATION, frozenset())
        self.assertEqual(etf.classify("SMH", "insider", families_expected={"insider": False}), "NOT_APPLICABLE")
        self.assertEqual(etf.classify("SMH", "flow", families_expected={"flow": True}), "BLOCKED_BY_REGISTRATION")
        self.assertEqual(etf.classify("SMH", "flow", registered_members=frozenset({"SMH"}), families_expected={"flow": True}), "MEMBER")
        self.assertEqual(etf.classify("XLK", "flow", registered_members=frozenset({"SMH"}), families_expected={"flow": True}), "NOT_MEMBER")
    def test_addendum_validation(self):
        good = {"addendum_id": "etf-class-A1", "parent_protocol_id": "bace258b0bbb", "class": "etf", "members": ["SMH", "XLK"], "rationale": "synthetic", "families_expected": {"insider": False, "flow": True}}
        self.assertEqual(etf.validate_addendum(good), [])
        self.assertTrue(etf.validate_addendum(dict(good, members=["smh", "SMH", "SMH"])))
        self.assertTrue(etf.validate_addendum(dict(good, class_="x")) or etf.validate_addendum({k: v for k, v in good.items() if k != "families_expected"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
