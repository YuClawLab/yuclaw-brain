"""ETF addendum-driven classification path (v7 P1): proposed addenda and corrections on synthetic payloads; the
registered set is never mutated; NOT_APPLICABLE vs BLOCKED_BY_REGISTRATION vs PROPOSED_* stay distinct."""
import pathlib, sys, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.universe import etf_class_candidate as etf  # noqa: E402

PAYLOAD = {"addendum_id": "etf-addendum-synthetic-1", "parent_protocol_id": "74c9a12a60e3", "class": "etf", "members": ["SPY", "QQQ"], "rationale": "synthetic proposal",
           "families_expected": {"broad-index": True, "single-name": False}}


class AddendumPath(unittest.TestCase):
    def test_validation_and_proposed_classification(self):
        self.assertEqual(etf.validate_addendum(PAYLOAD), [])
        for bad in (dict(PAYLOAD, members=["spy"]), dict(PAYLOAD, members=[]), dict(PAYLOAD, class_="x"), dict(PAYLOAD, status="REGISTERED"), dict(PAYLOAD, extra=1), dict(PAYLOAD, families_expected={"x": "yes"})):
            self.assertTrue(etf.validate_addendum(bad))
        p = etf.apply_addendum(PAYLOAD); self.assertEqual(p["status"], "PROPOSED"); self.assertFalse(p["provenance"]["registered"]); self.assertEqual(p["chain"], [])
        self.assertEqual(etf.classify("SPY", "broad-index", proposed=p), "PROPOSED_MEMBER"); self.assertEqual(etf.classify("IWM", "broad-index", proposed=p), "PROPOSED_NOT_MEMBER")
        self.assertEqual(etf.classify("AAPL", "single-name", proposed=p), "PROPOSED_NOT_APPLICABLE")                  # a proposal's exemption stays proposed
        self.assertEqual(etf.classify("AAPL", "single-name", proposed=p, families_expected={"single-name": False}), "NOT_APPLICABLE")   # registered family rule → genuine
        self.assertEqual(etf.classify("SPY", "broad-index"), "BLOCKED_BY_REGISTRATION"); self.assertEqual(etf.classify("AAPL", "single-name", families_expected={"single-name": False}), "NOT_APPLICABLE")
        self.assertEqual(etf.classify("SPY", "broad-index", registered_members=frozenset({"SPY"})), "MEMBER"); self.assertEqual(etf.ETF_SET_AT_REGISTRATION, frozenset())   # registered set untouched
        self.assertEqual(etf.classify_all([("SPY", "broad-index"), ("IWM", "broad-index"), ("AAPL", "single-name")], proposed=p), {"PROPOSED_MEMBER": ["SPY"], "PROPOSED_NOT_APPLICABLE": ["AAPL"], "PROPOSED_NOT_MEMBER": ["IWM"]})
        self.assertEqual(etf.classify("SPY", "broad-index"), "BLOCKED_BY_REGISTRATION"); self.assertEqual(etf.REGISTERED_FAMILIES_EXPECTED, {})
    def test_corrections_chain_and_refusals(self):
        p1 = etf.apply_addendum(PAYLOAD)
        with self.assertRaises(ValueError): etf.apply_addendum(dict(PAYLOAD, members=["SPY"]), prior=p1)                          # correction must state supersedes
        wrong = dict(PAYLOAD, members=["SPY"], supersedes={"addendum_sha256": "0" * 64, "reason": "x"})
        with self.assertRaises(ValueError): etf.apply_addendum(wrong, prior=p1)                                                  # wrong prior digest
        fix = dict(PAYLOAD, members=["SPY"], supersedes={"addendum_sha256": p1["addendum_sha256"], "reason": "QQQ removed after review"})
        p2 = etf.apply_addendum(fix, prior=p1); self.assertEqual(p2["chain"], [p1["addendum_sha256"]]); self.assertEqual(etf.classify("QQQ", "broad-index", proposed=p2), "PROPOSED_NOT_MEMBER")
        self.assertEqual(p1["members"], frozenset({"SPY", "QQQ"}))                                                                # prior retained, not erased
        with self.assertRaises(ValueError): etf.apply_addendum(fix)                                                              # supersedes without the prior


if __name__ == "__main__":
    unittest.main(verbosity=2)
