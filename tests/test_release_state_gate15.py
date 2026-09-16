"""V8-009: the owner removed the Gate #15 human-comprehension study as a mandatory v8 release requirement. The generator
records REMOVED_BY_OWNER (never PASSED/GREEN) for a v8 release with the owner's tracked decision present; 7.x rules and
historical results are unchanged; the retained automated consumer-posture check still turns the gate RED when it fails."""
import json, pathlib, sys, tempfile, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
for p in (str(REPO), str(REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)
import yuclaw_release_state_v6 as gen     # noqa: E402

RECORD = REPO / "v8" / "policy" / "gate15_release_requirement.json"


class Gate15Requirement(unittest.TestCase):
    def test_tracked_owner_decision_record(self):
        d = json.loads(RECORD.read_text())
        self.assertEqual((d["record"], d["gate"], d["status"], d["decided_by"]), ("yuclaw-v8-release-requirement-decision/1", 15, "REMOVED_BY_OWNER", "owner"))
        self.assertIn("remove Gate 15", d["decision_text"]); self.assertIn("8.x", d["applies_to"]["versions"])
        self.assertTrue(any("NOT a pass" in m for m in d["meaning"])); self.assertIn("PENDING", " ".join(d["meaning"]))

    def test_7x_unchanged_and_v8_removed_by_owner(self):
        self.assertIsNone(gen.gate15_requirement("7.0.1")); self.assertIsNone(gen.gate15_requirement("7.0.0"))
        self.assertEqual(gen.gate15_result("7.0.1", True, None), ("MANUAL_REVIEW", "consumer-posture scaffold GREEN (five personas); full-form human comprehension study does not exist"))
        self.assertEqual(gen.gate15_result("7.0.1", False, None)[0], "RED")
        dec = gen.gate15_requirement("8.0.0"); self.assertIsNotNone(dec); self.assertEqual(dec["status"], "REMOVED_BY_OWNER"); self.assertEqual(len(dec["sha256"]), 64)
        result, evidence = gen.gate15_result("8.0.0", True, dec)
        self.assertEqual(result, "REMOVED_BY_OWNER"); self.assertIn("NOT PASSED", evidence); self.assertIn("human benefit PENDING", evidence); self.assertIn(dec["sha256"][:16], evidence)
        self.assertNotIn("GREEN", result); self.assertNotIn("PASSED", result)
        self.assertEqual(gen.gate15_result("8.0.0", False, dec)[0], "RED")                          # the retained automated check still blocks
        self.assertEqual(gen.gate15_result("8.0.0", True, None)[0], "MANUAL_REVIEW")                 # without the owner's record nothing changes

    def test_a_record_claiming_a_pass_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            bad = pathlib.Path(td) / "r.json"; d = json.loads(RECORD.read_text()); d["status"] = "PASSED"; bad.write_text(json.dumps(d))
            with self.assertRaises(ValueError):
                gen.gate15_requirement("8.0.0", bad)
            d["status"] = "REMOVED_BY_OWNER"; d["decided_by"] = "assistant"; bad.write_text(json.dumps(d))
            with self.assertRaises(ValueError):
                gen.gate15_requirement("8.0.0", bad)
            self.assertIsNone(gen.gate15_requirement("7.0.1", bad))                                  # never consulted for 7.x


if __name__ == "__main__":
    unittest.main()
