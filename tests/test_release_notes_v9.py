"""The 9.x notes composer and the release-state generator's 9.x handling: 9.0.0 composes and is bound to a recorded
policy; 9.0.1 composes as a corrective PATCH of 9.0.0 (scope unchanged + a tracked change list); without a policy the notes
say NOT RECORDED; Gate #15 is MANUAL_REVIEW unless the owner records a decision FOR THAT VERSION (the 8.x removal and the
9.0.0-only exception never carry over; a record claiming a pass is refused); correspondence fails on altered feature lines,
missing never-claims or a banned word; other versions have no 9.x path."""
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


TEXT = "2. OWNER RELEASE-POLICY EXCEPTION — GATE #15, 9.0.0 ONLY\n\nFor 9.0.0 only, I accept an explicit release-policy exception for Gate #15. (synthetic test copy)"


def policy(version="9.0.0", route="EXCEPTION_9_0_0", sha=None, accepted=True, text=TEXT):
    return {"version": version, "allocation": {"document_id": "D1_allocation_9.0.0.json", "sha256": "f" * 64, "decision": "ACCEPTED", "accepted": accepted},
            "gate15": {"route": route, "status": "MANUAL_REVIEW", "decision_record_sha256": sha, "decision_text_sha256": hashlib.sha256(text.encode()).hexdigest()}, "activations_active": [], "activation_records": {}}


def decision_file(tmp: pathlib.Path, status="EXCEPTION_ACCEPTED", record="yuclaw-v9-release-requirement-decision/1", versions="9.0.0 only", gate_result="MANUAL_REVIEW", carried=False, passed=False, text=TEXT):
    p = tmp / "gate15.json"
    p.write_text(json.dumps({"record": record, "gate": 15, "decided_by": "owner", "status": status, "gate_result": gate_result, "decision_utc": "2026-10-10", "applies_to": {"versions": versions, "carried_to_later_releases": carried},
                             "decision_text_verbatim": text, "study": {"run": False, "represented_as_passed": passed}}))
    return p


class TestNotesV9(unittest.TestCase):
    def test_generator_routes_9_0_0_and_its_patch_to_the_v9_composer_and_nothing_else(self):
        self.assertIs(gen.notes_composer("9.0.0"), n9); self.assertIs(gen.notes_composer("9.0.1"), n9)
        for v in ("9.0.2", "9.1.0", "8.0.2", "9.0.0rc1", "9.0.1rc1"):
            self.assertIsNone(gen.notes_composer(v), v)
        with self.assertRaises(ValueError):                                                              # a patch needs its tracked change list
            n9.compose(V6_STYLE.format(v="9.0.1"), version="9.0.1", policy=None, board=BOARD, matrix=n9.capability_matrix(scorecard=scorecard()))
        with self.assertRaises(ValueError):                                                              # the major release has no change list
            n9.compose(V6_STYLE.format(v="9.0.0"), version="9.0.0", policy=None, board=BOARD, matrix=n9.capability_matrix(scorecard=scorecard()), patch_changes="- x")
        with self.assertRaises(ValueError):
            n9.compose(V6_STYLE.format(v="9.1.0"), version="9.1.0", policy=None, board=BOARD, matrix=n9.capability_matrix(scorecard=scorecard()))

    def test_no_policy_means_a_draft_that_says_so_and_gate15_manual_review(self):
        m = n9.capability_matrix(scorecard=scorecard())
        text = n9.compose(V6_STYLE.format(v="9.0.0"), version="9.0.0", policy=None, board=BOARD, matrix=m)
        self.assertIn("#### New in 9.0.0 — research briefs", text); self.assertIn("Release policy: NOT RECORDED", text)
        for f in n9.EXPECTED_FEATURES:
            self.assertIn(n9.FEATURE_LINES[f], text)
        self.assertIn(n9.DETECTOR_NOTE, text); self.assertIn(n9.V8_NOTE, text); self.assertIn("Candidate evidence (candidate abc123def456)", text)
        self.assertIn("clean install NOT RUN.", text)
        m2 = dict(m, clean_install_failed_checks=["readme_transcript_exact"]); m2["evidence"] = dict(m2["evidence"], clean_install="FAIL")
        t2 = n9.feature_account(m2); self.assertIn("clean install FAIL on that pre-freeze candidate (readme transcript exact); the final pair is verified", t2)
        live = n9.capability_matrix()                                                                   # the tree's newest record: V9-003 names its one failing clean-install check
        self.assertEqual(live["clean_install_failed_checks"], ["readme_transcript_exact"]); self.assertNotIn("generated", n9.feature_account(live).lower())
        self.assertEqual(n9.check_correspondence(text, None, matrix=m), ["no release-policy record"])
        self.assertEqual(gen.gate15_result("9.0.0", True, None)[0], "MANUAL_REVIEW"); self.assertEqual(gen.gate15_result("9.0.0", False, None)[0], "RED")

    def test_an_8x_removal_a_claimed_pass_or_a_carried_exception_never_counts_for_9_0_0(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        for bad in (dict(record="yuclaw-v8-release-requirement-decision/1", versions="8.x (v8 releases)"), dict(status="REMOVED_BY_OWNER"), dict(status="PASSED"), dict(gate_result="PASSED"),
                    dict(carried=True), dict(passed=True), dict(versions="9.x")):
            with self.assertRaises(ValueError, msg=str(bad)):
                n9.gate15_decision(decision_file(tmp, **bad))
        with self.assertRaises(ValueError):
            gen.gate15_requirement("9.0.0", decision_file(tmp, status="PASSED"))
        with self.assertRaises(ValueError):
            gen.gate15_requirement("9.0.1", decision_file(tmp))                                       # 9.0.0 only: a later version cannot inherit it
        m = n9.capability_matrix(scorecard=scorecard())
        text = n9.compose(V6_STYLE.format(v="9.0.0"), version="9.0.0", policy=policy(route="NOT_REQUIRED"), board=BOARD, matrix=m)
        probs = n9.check_correspondence(text, policy(route="NOT_REQUIRED"), matrix=m, decision=n9.gate15_decision(decision_file(tmp)))
        self.assertTrue(any("NOT_REQUIRED (8.x) and routes A/B do not apply" in p for p in probs), probs)

    def test_a_recorded_9x_decision_binds_the_notes_and_correspondence_is_strict(self):
        tmp = pathlib.Path(tempfile.mkdtemp()); dec = n9.gate15_decision(decision_file(tmp)); self.assertEqual(dec["status"], "EXCEPTION_ACCEPTED")
        m = n9.capability_matrix(scorecard=scorecard()); pol = policy(sha=dec["sha256"])
        # compose() reads the tree's (absent) decision; bind the disclosure line the way the recorded decision would print it
        tree_dec = n9.gate15_decision()                                                                   # compose() reads the TREE's record; the test binds its synthetic one instead
        text = n9.compose(V6_STYLE.format(v="9.0.0"), version="9.0.0", policy=pol, board=BOARD, matrix=m).replace(n9.gate15_line(pol, tree_dec), n9.gate15_line(pol, dec))
        self.assertEqual(n9.check_correspondence(text, pol, matrix=m, decision=dec), [])
        self.assertEqual(gen.gate15_result("9.0.0", True, dec)[0], "MANUAL_REVIEW"); self.assertIn("explicit release-policy exception for 9.0.0 only", gen.gate15_result("9.0.0", True, dec)[1]); self.assertIn("NOT PASSED", gen.gate15_result("9.0.0", True, dec)[1])
        self.assertIn(TEXT.replace("\n", "\n  "), text)                                                  # the owner's words are in the notes verbatim
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
        rec = json.loads((R / "v9" / "policy" / "gate15_release_requirement.json").read_text())            # the owner's forwarded section 2, recorded verbatim (V9-002)
        self.assertEqual((rec["status"], rec["gate_result"], rec["applies_to"]["versions"], rec["applies_to"]["carried_to_later_releases"]), ("EXCEPTION_ACCEPTED", "MANUAL_REVIEW", "9.0.0 only", False))
        self.assertIn("For 9.0.0 only, I accept an explicit release-policy exception for Gate #15.", rec["decision_text_verbatim"]); self.assertFalse(rec["study"]["represented_as_passed"])
        self.assertEqual(hashlib.sha256(rec["decision_text_verbatim"].encode()).hexdigest(), rec["decision_text_sha256"])
        live = n9.gate15_decision(); self.assertEqual(gen.gate15_requirement("9.0.0")["sha256"], live["sha256"]); self.assertEqual(gen.gate15_result("9.0.0", True, live)[0], "MANUAL_REVIEW")


class TestPatch901(unittest.TestCase):
    """9.0.1 = the 9.0.0 scope and capability account, unchanged, plus a TRACKED patch change list; Gate #15 binds to a 9.0.1 record only."""
    CHANGES = "- Replay verification refuses a missing daily root.\n- Ledger day files keep their bytes."

    def compose(self, pol, changes=CHANGES):
        return n9.compose(V6_STYLE.format(v="9.0.1"), version="9.0.1", policy=pol, board=BOARD, matrix=n9.capability_matrix(scorecard=scorecard()), patch_changes=changes)

    def test_patch_notes_keep_the_scope_and_carry_the_change_list(self):
        pol = policy(version="9.0.1", route="EXCEPTION_9_0_1"); text = self.compose(pol)
        self.assertIn("#### Changed in 9.0.1 — corrective release:", text); self.assertIn("scope unchanged", text); self.assertIn(self.CHANGES, text)
        self.assertIn("#### In the 9.0 line since 9.0.0 — research briefs with traceable AI assistance (local, loopback only; scope unchanged)", text); self.assertNotIn("#### New in 9.0.1", text)
        self.assertIn(n9.PATCH_SCOPE_NOTE.format(version="9.0.1", scope_version="9.0.0"), text)
        for f in n9.EXPECTED_FEATURES:
            self.assertIn(n9.FEATURE_LINES[f], text)
        self.assertIn("NO owner decision is recorded for 9.0.1; the 8.x removal and the 9.0.0-only exception do not carry over", text)   # the tree has no 9.0.1 record
        for missing in ("", "   \n"):
            with self.assertRaises(ValueError):
                self.compose(pol, missing)
        self.assertEqual(n9.gate15_route("9.0.1"), "EXCEPTION_9_0_1"); self.assertEqual(n9.gate15_route("9.0.0"), n9.GATE15_ROUTE)
        self.assertEqual(n9.gate15_decision_path("9.0.0"), n9.GATE15_DECISION); self.assertEqual(n9.gate15_decision_path("9.0.1").name, "gate15_release_requirement_9.0.1.json")

    def test_the_9_0_0_exception_is_never_read_for_9_0_1_and_a_9_0_1_record_binds_strictly(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.assertIsNone(n9.gate15_decision(version="9.0.1"))                                            # no 9.0.1 record in the tree → no decision
        self.assertIsNone(gen.gate15_requirement("9.0.1"))
        with self.assertRaises(ValueError):                                                               # the 9.0.0-only record, read for 9.0.1, is refused
            n9.gate15_decision(decision_file(tmp), version="9.0.1")
        with self.assertRaises(ValueError):
            n9.gate15_decision(n9.GATE15_DECISION, version="9.0.1")
        pol = policy(version="9.0.1", route="EXCEPTION_9_0_1"); text = self.compose(pol)
        probs = n9.check_correspondence(text, pol, matrix=n9.capability_matrix(scorecard=scorecard()))
        self.assertTrue(any("9.0.1 exception record is absent" in p for p in probs), probs)              # unpublishable until the owner decides for 9.0.1
        probs0 = n9.check_correspondence(text, policy(version="9.0.1", route="EXCEPTION_9_0_0"), matrix=n9.capability_matrix(scorecard=scorecard()))
        self.assertTrue(any("nor does another version's exception" in p for p in probs0), probs0)   # the 9.0.0 route word does not fit 9.0.1
        self.assertTrue(any("policy record is for version '9.0.0', not 9.0.1" in p for p in n9.check_correspondence(text, policy(version="9.0.0", route="EXCEPTION_9_0_1"), matrix=n9.capability_matrix(scorecard=scorecard()))))
        dec = n9.gate15_decision(decision_file(tmp, versions="9.0.1 only", text=TEXT.replace("9.0.0", "9.0.1")), version="9.0.1")
        self.assertEqual(gen.gate15_requirement("9.0.1", tmp / "gate15.json")["sha256"], dec["sha256"]); self.assertEqual(gen.gate15_result("9.0.1", True, dec)[0], "MANUAL_REVIEW")
        pol = policy(version="9.0.1", route="EXCEPTION_9_0_1", sha=dec["sha256"], text=TEXT.replace("9.0.0", "9.0.1"))
        bound = self.compose(pol).replace(n9.gate15_line(pol, None, "9.0.1"), n9.gate15_line(pol, dec, "9.0.1"))
        self.assertEqual(n9.check_correspondence(bound, pol, matrix=n9.capability_matrix(scorecard=scorecard()), decision=dec), [])
        self.assertIn("explicit release-policy exception for 9.0.1 only", bound); self.assertNotIn("scope unchanged", n9.compose(V6_STYLE.format(v="9.0.0"), version="9.0.0", policy=None, board=BOARD, matrix=n9.capability_matrix(scorecard=scorecard())))
        self.assertTrue(any("scope is unchanged" in p for p in n9.check_correspondence(bound.replace("scope unchanged", "scope"), pol, matrix=n9.capability_matrix(scorecard=scorecard()), decision=dec)))

    def test_the_tracked_change_list_exists_and_respects_the_public_rules(self):
        t = (R / "docs" / "methodology" / "release_notes_9.0.1_changes.md").read_text()
        self.assertTrue(t.startswith("- ")); self.assertIn("research-export", t); self.assertIn("not present in the published 9.0.0", t); self.assertIn("R10", t)
        for banned in ("docs/", "registry/", "output/", "tools/", "check_", ".py", "seed", "bootstrap", "generated"):
            self.assertNotIn(banned, t, banned)
        import re
        self.assertIsNone(re.search(r"\b(validated|certif(ied|icate)|guarantee[sd]?|alpha|independently replicated)\b", t, re.I))


if __name__ == "__main__":
    unittest.main()
