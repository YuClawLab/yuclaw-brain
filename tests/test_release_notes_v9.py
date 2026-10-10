"""The 9.0.0 notes composer and the release-state generator's 9.x handling: 9.0.0 composes and is bound to a recorded
policy; without a policy the notes say NOT RECORDED; Gate #15 for 9.x is MANUAL_REVIEW unless the owner records a 9.x
decision (the 8.x removal never carries over; a record claiming a pass is refused); correspondence fails on altered
feature lines, missing never-claims or a banned word; other versions have no 9.x path."""
import hashlib, json, pathlib, sys, tempfile, unittest

R = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "tools")); sys.path.insert(0, str(R))
import yuclaw_release_notes_v9 as n9  # noqa: E402
import yuclaw_release_state_v6 as gen  # noqa: E402

V6_STYLE = """# YUCLAW {v}

Research & education only. Not investment advice.

#### Shipped objects
- object one · receipt · status

#### Not in this release
- tail line
"""
BOARD = {"generated_at": "2026-10-10T00:00:00Z", "names": [], "totals": {}}


def scorecard(ok=True):
    return {"record": "yuclaw-v9-scorecard/1", "candidate": "abc123def456", "runs": {"current": {"python": "3.12.3", "passed": 72, "failed": 0, "total": 72, "result": "PASS" if ok else "FAIL"}},
            "selftest": "PASS", "ui_inspection": "PASS", "clean_install": "NOT RUN"}


def policy(version="9.0.0", route="NOT_REQUIRED", sha=None, accepted=True):
    return {"version": version, "allocation": {"document_id": "D1_allocation_9.0.0.json", "sha256": "f" * 64, "decision": "ACCEPTED", "accepted": accepted},
            "gate15": {"route": route, "status": "REMOVED_BY_OWNER", "decision_record_sha256": sha}, "activations_active": [], "activation_records": {}}


def decision_file(tmp: pathlib.Path, status="REMOVED_BY_OWNER", record="yuclaw-v9-release-requirement-decision/1", versions="9.x (v9 releases)"):
    p = tmp / "gate15.json"
    p.write_text(json.dumps({"record": record, "gate": 15, "decided_by": "owner", "status": status, "decision_utc": "2026-10-11T00:00:00Z", "applies_to": {"versions": versions}}))
    return p


class TestNotesV9(unittest.TestCase):
    def test_generator_routes_9_0_0_to_the_v9_composer_and_nothing_else(self):
        self.assertIs(gen.notes_composer("9.0.0"), n9)
        for v in ("9.0.1", "9.1.0", "8.0.2", "9.0.0rc1"):
            self.assertIsNone(gen.notes_composer(v), v)
        with self.assertRaises(ValueError):
            n9.compose(V6_STYLE.format(v="9.0.1"), version="9.0.1", policy=None, board=BOARD, matrix=n9.capability_matrix(scorecard=scorecard()))
        with self.assertRaises(ValueError):
            n9.compose(V6_STYLE.format(v="9.0.0"), version="9.0.0", policy=None, board=BOARD, matrix=n9.capability_matrix(scorecard=scorecard()), patch_changes="- x")

    def test_no_policy_means_a_draft_that_says_so_and_gate15_manual_review(self):
        m = n9.capability_matrix(scorecard=scorecard())
        text = n9.compose(V6_STYLE.format(v="9.0.0"), version="9.0.0", policy=None, board=BOARD, matrix=m)
        self.assertIn("#### New in 9.0.0 — research briefs", text); self.assertIn("Release policy: NOT RECORDED", text); self.assertIn("NO owner decision is recorded for 9.x releases; the 8.x removal does not carry over", text)
        for f in n9.EXPECTED_FEATURES:
            self.assertIn(n9.FEATURE_LINES[f], text)
        self.assertIn(n9.DETECTOR_NOTE, text); self.assertIn(n9.V8_NOTE, text); self.assertIn("Candidate evidence (candidate abc123def456)", text)
        self.assertEqual(n9.check_correspondence(text, None, matrix=m), ["no release-policy record"])
        self.assertIsNone(gen.gate15_requirement("9.0.0")); self.assertEqual(gen.gate15_result("9.0.0", True, None)[0], "MANUAL_REVIEW"); self.assertEqual(gen.gate15_result("9.0.0", False, None)[0], "RED")

    def test_an_8x_removal_or_a_claimed_pass_never_counts_for_9x(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):
            n9.gate15_decision(decision_file(tmp, record="yuclaw-v8-release-requirement-decision/1", versions="8.x (v8 releases)"))
        with self.assertRaises(ValueError):
            n9.gate15_decision(decision_file(tmp, status="PASSED"))
        with self.assertRaises(ValueError):
            gen.gate15_requirement("9.0.0", decision_file(tmp, status="PASSED"))
        m = n9.capability_matrix(scorecard=scorecard())
        text = n9.compose(V6_STYLE.format(v="9.0.0"), version="9.0.0", policy=policy(sha=None), board=BOARD, matrix=m)
        probs = n9.check_correspondence(text, policy(sha=None), matrix=m, decision=None)
        self.assertTrue(any("no owner decision record for 9.x" in p for p in probs), probs)

    def test_a_recorded_9x_decision_binds_the_notes_and_correspondence_is_strict(self):
        tmp = pathlib.Path(tempfile.mkdtemp()); dec = n9.gate15_decision(decision_file(tmp)); self.assertEqual(dec["status"], "REMOVED_BY_OWNER")
        m = n9.capability_matrix(scorecard=scorecard()); pol = policy(sha=dec["sha256"])
        # compose() reads the tree's (absent) decision; bind the disclosure line the way the recorded decision would print it
        text = n9.compose(V6_STYLE.format(v="9.0.0"), version="9.0.0", policy=pol, board=BOARD, matrix=m).replace(n9.gate15_line(pol, None), n9.gate15_line(pol, dec))
        self.assertEqual(n9.check_correspondence(text, pol, matrix=m, decision=dec), [])
        self.assertEqual(gen.gate15_result("9.0.0", True, dec)[0], "REMOVED_BY_OWNER"); self.assertIn("9.x releases", gen.gate15_result("9.0.0", True, dec)[1])
        bad = text.replace(n9.FEATURE_LINES["F4"], n9.FEATURE_LINES["F4"].replace("no live detector or provider connector exists in 9.0", "a live detector connector ships"))
        self.assertTrue(any("F4" in p for p in n9.check_correspondence(bad, pol, matrix=m, decision=dec)))
        self.assertTrue(any("banned" in p for p in n9.check_correspondence(text + "\n- validated by an independent lab", pol, matrix=m, decision=dec)))
        self.assertTrue(any("detector never-claims" in p for p in n9.check_correspondence(text.replace(n9.DETECTOR_NOTE, "- detectors are great"), pol, matrix=m, decision=dec)))
        self.assertTrue(any("Gate #15 is described as passed" in p for p in n9.check_correspondence(text + "\n- Gate #15 PASSED", pol, matrix=m, decision=dec)))
        incomplete = n9.capability_matrix(scorecard=scorecard(ok=False))
        t2 = n9.compose(V6_STYLE.format(v="9.0.0"), version="9.0.0", policy=pol, board=BOARD, matrix=incomplete)
        self.assertIn("Candidate evidence INCOMPLETE", t2)

    def test_scope_record_is_the_five_features_and_the_fixture_numbers(self):
        scope = json.loads(n9.SCOPE_PATH.read_text())
        self.assertEqual(scope["release"], "9.0.0"); self.assertEqual(scope["enabled_features"], list(n9.EXPECTED_FEATURES))
        self.assertEqual(scope["fixture"]["relative_change_percent"], "-4.35"); self.assertIn("human_comprehension_study", scope["excluded_by_owner"]); self.assertIn("backup_or_restore_functionality", scope["excluded_by_owner"])
        self.assertEqual(scope["mission"], "Make financial AI accountable to evidence."); self.assertEqual(scope["vision"], "Become the Science Trust Layer for Financial AI.")
        self.assertFalse((R / "v9" / "policy" / "gate15_release_requirement.json").exists(), "no 9.x gate-15 decision is recorded by the executor; that is the owner's")


if __name__ == "__main__":
    unittest.main()
