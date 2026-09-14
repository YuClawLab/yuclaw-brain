"""A2 requirements interface (v7 P2): missing S, incompatible units, unsupported variance inputs; never a numeric N_eff."""
import pathlib, sys, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.phase6 import a2_interface as a2  # noqa: E402

FULL = {"S": {"id": "S-synthetic", "definition": "mean capped CAR", "unit": "bps"}, "event_set": {"id": "E4", "count": 12}, "units": "bps", "weights": {"scheme": "equal"},
        "horizon": {"length": 20, "unit": "sessions"}, "variance_basis": "cluster-robust", "rule4_disposition": "NOT_APPLIED", "incident_dependencies": [{"id": "inc-1", "disposition": "CLOSED"}]}


class Interface(unittest.TestCase):
    def test_missing_S_and_unresolved_inputs(self):
        r = a2.validate_requirements({k: v for k, v in FULL.items() if k != "S"}); self.assertEqual(r["status"], "UNRESOLVED"); self.assertIn("S (pooled statistic) not designated", r["unresolved"]); self.assertTrue(r["n_eff"].startswith("NOT_COMPUTED"))
        r = a2.validate_requirements(FULL); self.assertEqual(r["status"], "CANDIDATE_COMPLETE"); self.assertEqual(r["registered_designation"], "NOT_REGISTERED"); self.assertTrue(r["n_eff"].startswith("NOT_COMPUTED"))   # complete facts ≠ registered designation
        r = a2.validate_requirements(dict(FULL, registration={"registered_at": "2026-10-01T00:00:00Z", "registered_by": "owner", "record_id": "reg-1"})); self.assertEqual(r["registered_designation"], "REGISTERED")
        r = a2.validate_requirements(dict(FULL, incident_dependencies=[{"id": "inc-2", "disposition": "OPEN"}])); self.assertIn("open incident dependency: inc-2", r["unresolved"])
        r = a2.validate_requirements(dict(FULL, rule4_disposition="UNRESOLVED")); self.assertIn("rule-4 disposition unresolved", r["unresolved"])
    def test_incompatible_units_and_unsupported_variance(self):
        with self.assertRaises(a2.A2Error): a2.validate_requirements(dict(FULL, units="pct"))                                  # S.unit bps vs pct
        with self.assertRaises(a2.A2Error): a2.validate_requirements(dict(FULL, units="furlongs"))
        with self.assertRaises(a2.A2Error): a2.validate_requirements(dict(FULL, variance_basis="magic"))
        with self.assertRaises(a2.A2Error): a2.validate_requirements(dict(FULL, horizon={"length": 0, "unit": "sessions"}))
        with self.assertRaises(a2.A2Error): a2.validate_requirements(dict(FULL, weights={"scheme": "explicit", "values": [1, -1]}))
        with self.assertRaises(a2.A2Error): a2.validate_requirements(dict(FULL, event_set={"id": "E4", "count": True}, weights={"scheme": "explicit", "values": [float("nan")]}))   # bool count + NaN weight
        with self.assertRaises(a2.A2Error): a2.validate_requirements(dict(FULL, weights={"scheme": "explicit", "values": [1.0] * 3}))                                     # cardinality ≠ event count (12)
        for bad in ({"scheme": "explicit", "values": [float("inf")] * 12}, {"scheme": "explicit", "values": [True] * 12}, {"scheme": "explicit", "values": []}):
            with self.assertRaises(a2.A2Error): a2.validate_requirements(dict(FULL, weights=bad))
    def test_source_metadata_maps_only_what_it_can(self):
        req = a2.from_source_metadata({"event_set_id": "E4", "eligible_events": 12, "horizon_sessions": 20, "open_incidents": ["inc-9"]})
        r = a2.validate_requirements(req); self.assertEqual(r["status"], "UNRESOLVED")
        for label in ("S (pooled statistic) not designated", "units unresolved", "weights unresolved", "variance basis unresolved", "rule-4 disposition unresolved", "open incident dependency: inc-9"):
            self.assertIn(label, r["unresolved"])
        self.assertEqual(r["requirements"]["event_set"], {"id": "E4", "count": 12})


if __name__ == "__main__":
    unittest.main(verbosity=2)
