"""Phase-C protocol fixture checks (v7 P2): schema/dependency validation; unresolved decision rule; no default threshold in code."""
import json, pathlib, re, sys, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.phase_c import spec  # noqa: E402

BASE = {"protocol_id": "phase-c-synthetic", "status": "DRAFT", "populations": {"phase_c_names": 20, "phase_b_names": 79}, "window": {"start_rule": "fresh-after-registration", "sessions": 20},
        "endpoints": [{"id": "reproduction-rate", "kind": "primary"}], "denominator": {"basis": "enrolled-sessions", "fixed_n": 20}, "missing_session_rule": "count-as-failure",
        "statistic": {"id": "rate", "definition": "successful / fixed_n"}, "decision_rule": "UNRESOLVED", "stopping_rule": {"kind": "fixed-window", "text": "stop at window end"}, "controls": ["prior-window comparison"],
        "prior_observation_disclosure": {"disclosed": True, "text": "20 shadow sessions observed before registration"}, "integrity_reference": "registry-chain-verified"}


class Spec(unittest.TestCase):
    def test_draft_unresolved_and_runnable_rules(self):
        r = spec.validate_protocol(BASE); self.assertEqual(r["problems"], []); self.assertIn("decision_rule", r["unresolved"][0]); self.assertFalse(r["runnable"])
        full = dict(BASE, decision_rule={"threshold": 0.9, "comparison": ">=", "rationale": "labelled draft example, not adopted"})
        self.assertFalse(spec.validate_protocol(full)["runnable"])                                                                  # DRAFT never runs
        reg = dict(full, status="REGISTERED", registration={"registered_at": "2026-10-01T00:00:00Z"}); self.assertTrue(spec.validate_protocol(reg)["runnable"])
        self.assertFalse(spec.validate_protocol(dict(full, status="DESIGNATED"))["runnable"])
        for bad in (dict(BASE, window={"start_rule": "backdated", "sessions": 20}), dict(BASE, integrity_reference="integrity threshold"), dict(BASE, decision_rule={"threshold": "0.9"}),
                    dict(BASE, prior_observation_disclosure={"disclosed": False}), dict(BASE, denominator={"basis": "enrolled-sessions", "fixed_n": 0})):
            self.assertTrue(spec.validate_protocol(bad)["problems"])
        self.assertEqual(spec.validate_protocol({})["problems"][0], "missing protocol_id")
    def test_no_default_threshold_constant_in_runnable_code(self):
        src = (REPO / "v3/phase_c/spec.py").read_text()
        self.assertFalse(re.search(r"^[A-Z_]*THRESHOLD[A-Z_]* *= *\d", src, re.M)); self.assertNotIn("0.9", src); self.assertNotIn("90%", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
