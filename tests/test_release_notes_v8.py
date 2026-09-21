"""V8-008 TB-1 + V8-009 (Gate #15 requirement removed by the owner): the 8.0.0 Tier-2 notes composition path. Fixed inputs only; every policy record here is a SYNTHETIC TEST
FIXTURE (never an owner decision). Checks: 7.x behaviour preserved; 8.0.0 reaches its own composer instead of the
7.x-only sentinel; missing / proposed / mismatched / contradictory D1-D2 inputs never correspond; unknown versions stay
unsupported; a valid synthetic 8.0.0 policy passes only the correspondence checks while inconsistent notes fail."""
import copy, json, pathlib, sys, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
for p in (str(REPO), str(REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)
import yuclaw_release_notes_v8 as n8            # noqa: E402
import yuclaw_release_state_v6 as gen          # noqa: E402
from v3.release import notes_v7                # noqa: E402
from v8.workbench import server                # noqa: E402

V6_STYLE = """Research & education only. Not investment advice.

### YUCLAW {v} — Evidence-First Financial AI · The Science Trust Layer for Financial AI

Financial AI normally gives you an answer. YUCLAW gives you the evidence, what that evidence can support, what it cannot support, and whether that conclusion survived time.

#### Shipped objects — name · receipt · status

- Object one · sha256 aaaa… · GREEN
- yuclaw {v} package · wheel + sdist sha256 attached to this release · CLI · REST · MCP · SDK

#### Not in this release

- N_eff PENDING
- unaffiliated replications 0

#### Made in Canada

Built in Canada.
"""
SCOPE = {"release": "8.0.0", "enabled_workstreams": ["GOV", "DAT", "CLM", "CHK", "TIM", "SET", "SCI", "UX", "INT", "REL", "SHD", "EVO", "COM", "PRC"],      # the owner's 2026-09-20 scope expansion
         "minimal_shared_behavior": {"RIV": "comparison only", "ACT": "unresolved/next-evidence only"},
         "experimental_default_off": [], "deferred": ["CTL", "RES", "RND", "full_RIV", "full_ACT", "VAL_real_user_pilot", "multi_tenant_platform", "managed_customer_accounts", "billing"],
         "backup_policy": {"disclosure": "Backup creation and restoration are not provided in 8.0.0. Restore not demonstrated. Research exports and release artifacts do not establish disaster recovery."},
         "initial_real_corpus": {"max_issuers": 1}}
def scorecard(label, ok=True):
    st = "DEMONSTRATED" if ok else "NOT_DEMONSTRATED"
    return {"mode": label, "score": "7/7" if ok else "6/7", "candidate": {"commit": "d" * 40}, "features": {k: {"status": st} for k in ("research_notes", "dataset", "sci")}}
MATRIX = n8.capability_matrix(scope=SCOPE, steps=list(server.STEPS), scorecards=[scorecard("fixtures"), scorecard("mchp")])
BOARD = json.loads((REPO / "docs" / "receipts" / "scoreboard.json").read_text())
DECISION = n8.gate15_decision()                                                                        # the owner's tracked v8 decision (REMOVED_BY_OWNER)


def synthetic_policy(route="NOT_REQUIRED", version="8.0.0", accepted=True, record_sha=None):
    """A SYNTHETIC policy record (never an owner decision). NOT_REQUIRED is the only v8 route: Gate #15 bound to the owner's decision record."""
    p = {"version": version, "allocation": {"accepted": accepted, "decision": "D1-ACCEPT" if accepted else "PROPOSED — synthetic fixture", "document_id": "SYNTHETIC-TEST-FIXTURE-NOT-A-DECISION", "sha256": "ab" * 32},
         "gate15": {"route": route}, "activations_active": []}
    if route == "NOT_REQUIRED":
        p["gate15"].update(status="REMOVED_BY_OWNER", decision_record_sha256=record_sha or DECISION["sha256"], decision_utc=DECISION["decision_utc"])
    elif route == "B":
        p["gate15"].update(exception_text="SYNTHETIC EXCEPTION WORDING (never the owner's)")
    elif route == "A":
        p["gate15"].update(gate_input="CANDIDATE_GATE_INPUT", gate_15_proposed="GREEN", coverage={})
    return p


def compose8(policy, matrix=MATRIX):
    return n8.compose(V6_STYLE.format(v="8.0.0"), version="8.0.0", policy=policy, board=BOARD, matrix=matrix)


class Dispatch(unittest.TestCase):
    def test_7x_still_uses_the_v7_composer_unchanged(self):
        self.assertIs(gen.notes_composer("7.0.0"), notes_v7); self.assertIs(gen.notes_composer("7.0.1"), notes_v7)
        pol = {"version": "7.0.0", "allocation": {"accepted": True, "decision": "D1-ACCEPT", "document_id": "SYNTHETIC-V7-FIXTURE", "sha256": "ab" * 32}, "gate15": {"route": "A", "gate_input": "CANDIDATE_GATE_INPUT", "gate_15_proposed": "GREEN", "coverage": {}}, "activations_active": []}
        text, corr = gen.compose_public_notes("7.0.0", V6_STYLE.format(v="7.0.0"), policy=pol, board=BOARD)
        self.assertEqual(corr, []); self.assertIn("#### New in 7.0.0", text); self.assertIn("SYNTHETIC-V7-FIXTURE", text)
        text, corr = gen.compose_public_notes("7.0.0", V6_STYLE.format(v="7.0.0"), policy=None, board=None)
        self.assertEqual(corr, ["no release-policy record"]); self.assertIn("NOT RECORDED", text)

    def test_8_0_0_reaches_the_v8_composer_not_the_sentinel(self):
        self.assertIs(gen.notes_composer("8.0.0"), n8)
        text, corr = gen.compose_public_notes("8.0.0", V6_STYLE.format(v="8.0.0"), policy=None, board=BOARD)
        self.assertNotIn("not a 7.x release", corr); self.assertIn("no release-policy record", corr)
        self.assertIn("#### New in 8.0.0 — the source-to-export commitment workbench", text); self.assertIn("NOT RECORDED", text)
        self.assertIn("source → typed claim → comparison → calculation → history → adjudication → reproducible export", text.replace("1 Source", "source").replace("2 Typed claim", "typed claim").replace("3 Comparison", "comparison").replace("4 Calculation", "calculation").replace("5 History", "history").replace("6 Adjudication", "adjudication").replace("7 Reproducible export", "reproducible export"))

    def test_unknown_versions_have_no_composition_path(self):
        for v in ("8.0.2", "8.1.0", "9.0.0", "6.0.1", "8.0.0rc1", "8.0.1rc1"):                     # 8.0.1 became a supported PATCH of 8.0.0 (owner order of 2026-09-21); nothing else did
            self.assertIsNone(gen.notes_composer(v), v)
            text, corr = gen.compose_public_notes(v, V6_STYLE.format(v=v), policy=synthetic_policy(), board=BOARD)
            self.assertEqual(text, V6_STYLE.format(v=v)); self.assertEqual(len(corr), 1); self.assertIn("no supported notes composition path", corr[0])
            with self.assertRaises(ValueError):
                n8.compose(V6_STYLE.format(v=v), version=v, policy=None, board=None, matrix=MATRIX)
        with self.assertRaises(ValueError):
            n8.compose(V6_STYLE.format(v="8.0.0"), version="8.0.0", policy=None, board=None, matrix=MATRIX, patch_changes="x")


class Patch801(unittest.TestCase):
    """8.0.1 = the 8.0.0 scope and capability account, unchanged, plus a TRACKED patch change list."""
    CHANGES = "- Example repair: a synthetic change line for the composer test.\n- A second synthetic line."

    def compose(self, policy, changes=CHANGES):
        return n8.compose(V6_STYLE.format(v="8.0.1"), version="8.0.1", policy=policy, board=BOARD, matrix=MATRIX, patch_changes=changes)

    def test_the_patch_needs_its_change_list_keeps_the_scope_and_says_so(self):
        self.assertIs(gen.notes_composer("8.0.1"), n8)
        for missing in (None, "", "  \n"):
            with self.assertRaises(ValueError):
                self.compose(synthetic_policy(version="8.0.1"), missing)
        pol = synthetic_policy(version="8.0.1"); text = self.compose(pol)
        self.assertIn("#### Changed in 8.0.1 — patch: defect repairs and clearer entry points (no methodology, statistic, threshold, registration or scope change)", text); self.assertIn(self.CHANGES, text)
        self.assertIn("#### In the 8.0 line since 8.0.0 — the source-to-export commitment workbench (local, loopback only; scope unchanged)", text); self.assertNotIn("#### New in 8.0.1", text)
        self.assertEqual(n8.check_correspondence(text, pol, MATRIX), [])                                  # the unchanged 8.0.0 capability account, limits and activations all still have to be there
        self.assertIn("- 8.0.1 keeps the frozen 8.0.0 scope: every statement below is that scope's own wording and applies to 8.0.1 unchanged.", text); self.assertNotIn("keeps the frozen", compose8(synthetic_policy()))
        self.assertEqual((gen.canada_heading("8.0.1"), gen.canada_heading("8.1.0"), gen.canada_heading("8.0.0"), gen.canada_heading("7.0.1")), ("Built in Canada", "Built in Canada", "Made in Canada", "Made in Canada"))   # published notes keep their heading
        for name, _ in notes_v7.ACTIVATIONS:
            self.assertIn(f"- {name}: INACTIVE", text)
        self.assertIn("human benefit", text.lower()); self.assertNotRegex(text, r"Gate #15[^\n]*\b(PASSED|GREEN|study complete|satisfied)\b")

    def test_a_policy_recorded_for_another_version_never_corresponds(self):
        text = self.compose(synthetic_policy(version="8.0.1"))
        probs = n8.check_correspondence(text, synthetic_policy(version="8.0.0"), MATRIX); self.assertTrue(any("policy record is for version '8.0.0', not 8.0.1" in p for p in probs), probs)   # the 8.0.0 acceptance is never reusable
        probs = n8.check_correspondence(compose8(synthetic_policy()), synthetic_policy(version="8.0.1"), MATRIX); self.assertTrue(any("not 8.0.0" in p for p in probs), probs)
        self.assertTrue(any("scope is unchanged" in p for p in n8.check_correspondence(text.replace("; scope unchanged)", ")"), synthetic_policy(version="8.0.1"), MATRIX)))
        self.assertTrue(any("PROPOSED" in p or "not recorded as accepted" in p for p in n8.check_correspondence(text, synthetic_policy(version="8.0.1", accepted=False), MATRIX)))


class PolicyInputs(unittest.TestCase):
    def test_missing_policy_is_a_visible_draft_and_never_corresponds(self):
        text = compose8(None)
        self.assertIn("Release policy: NOT RECORDED", text); self.assertIn("owner decision D1 (allocation) is pending", text); self.assertIn("requirement REMOVED BY OWNER", text)
        self.assertEqual(n8.check_correspondence(text, None, MATRIX), ["no release-policy record"])

    def test_v8_011_additions_are_in_the_public_body_without_overclaiming(self):
        text = compose8(None)                                                                        # present in the draft too, not only under a policy
        self.assertIn("corrected by a linked, append-only event, never by editing", text); self.assertIn("the original records and earlier historical views stay intact", text)
        self.assertIn("the corrected result is shown separately beside the recorded one", text); self.assertIn("the correction chain is exported for a fresh workspace to recompute", text)
        self.assertIn("Availability times are asserted by the operator, not authenticated.", text)
        self.assertIn("requires the operator's own `SEC_USER_AGENT` setting — required, never defaulted", text); self.assertIn("refused before any request is sent", text)
        self.assertIn("stored-source replay and every other offline function work without it", text)
        self.assertIn("NOT ELIGIBLE under the recorded selection criteria", text); self.assertIn(n8.BENEFIT_NOTE, text); self.assertIn(n8.REVIEW_NOTE, text)
        self.assertNotRegex(text, r"(?i)authenticated (source )?timestamps? (are|is) (provided|established)|prospective(ly)? eligible|study (was )?completed")

    def test_proposed_allocation_is_not_a_decision(self):
        proposed = synthetic_policy(accepted=False)
        text = compose8(proposed); problems = n8.check_correspondence(text, proposed, MATRIX)
        self.assertTrue(any("not recorded as accepted" in p for p in problems), problems)
        routeless = synthetic_policy(route=None)
        self.assertTrue(any("not applicable to a v8 release" in p for p in n8.check_correspondence(compose8(routeless), routeless, MATRIX)))

    def test_mismatched_and_contradictory_records_fail(self):
        good = synthetic_policy(); text = compose8(good); self.assertEqual(n8.check_correspondence(text, good, MATRIX), [])
        other_doc = copy.deepcopy(good); other_doc["allocation"]["document_id"] = "SYNTHETIC-OTHER-DOCUMENT"
        self.assertIn("allocation document id absent from the notes", n8.check_correspondence(text, other_doc, MATRIX))
        for route in ("A", "B"):                                                                     # routes and exception statements do not exist for v8
            pol = synthetic_policy(route)
            self.assertTrue(any("not applicable to a v8 release" in p for p in n8.check_correspondence(compose8(pol), pol, MATRIX)), route)
            self.assertIn("is not applicable to a v8 release", compose8(pol))
        unbound = synthetic_policy(record_sha="0" * 64)                                             # NOT_REQUIRED not bound to the tree's record
        self.assertTrue(any("not bound to the owner's decision record" in p for p in n8.check_correspondence(compose8(unbound), unbound, MATRIX)))
        no_status = synthetic_policy(); del no_status["gate15"]["status"]
        self.assertTrue(any("not bound" in p for p in n8.check_correspondence(compose8(no_status), no_status, MATRIX)))
        v7 = synthetic_policy(version="7.0.0")
        self.assertTrue(any("not 8.0.0" in p for p in n8.check_correspondence(compose8(v7), v7, MATRIX)))
        active = copy.deepcopy(good); active["activations_active"] = ["sentinel policy"]
        self.assertTrue(any("sentinel policy" in p for p in n8.check_correspondence(text, active, MATRIX)))

    def test_valid_synthetic_policy_passes_only_correspondence(self):
        pol = synthetic_policy(); text = compose8(pol)
        self.assertEqual(n8.check_correspondence(text, pol, MATRIX), [])
        self.assertIn("SYNTHETIC-TEST-FIXTURE-NOT-A-DECISION", text)
        self.assertIn("requirement REMOVED BY OWNER for v8 releases on 2026-09-16", text); self.assertIn(DECISION["sha256"][:16], text)
        self.assertIn("no human comprehension study was run and none is claimed — not a pass", text)
        self.assertNotRegex(text, r"Gate #15[^\n]*\b(PASSED|GREEN|study complete|satisfied)\b")            # never reported as passed
        self.assertIn("- Gate #15 human study: INACTIVE — kit ships; no study run; requirement removed by the owner for v8 releases — not a pass; human benefit PENDING", text)
        for name, _ in notes_v7.ACTIVATIONS:
            self.assertIn(f"- {name}: INACTIVE", text)
        passed = text.replace("none is claimed — not a pass", "PASSED")
        self.assertTrue(any("described as passed" in p or "disclosure missing or altered" in p for p in n8.check_correspondence(passed, pol, MATRIX)))
        # correspondence is a text-vs-record relation only: nothing here reads or changes a gate table or an authorization
        self.assertFalse(hasattr(n8, "release_authorized")); self.assertNotIn("release_authorized", text)

    def test_inconsistent_notes_fail_against_the_same_valid_record(self):
        pol = synthetic_policy(); text = compose8(pol)
        cases = {
            "backup disclosure absent or not verbatim": text.replace("Restore not demonstrated.", "Restore demonstrated."),
            "real-data statement": text.replace("replayed RETROSPECTIVELY", "replayed prospectively"),
            "simulated-review attribution missing": text.replace(n8.REVIEW_NOTE, "- Review: reviewed."),
            "human benefit PENDING statement missing": text.replace(n8.BENEFIT_NOTE, "- Human benefit: established."),
            "included-modules statement": text.replace("Including them activates nothing", "Including them activates everything"),
            "feature account for enabled workstream SHD": text.replace("an approved statement is never thereby true", "an approved statement is true"),
            "feature account for enabled workstream PRC": text.replace("and no study was run", "and a study was run"),
            "feature account for enabled workstream SET": text.replace("- Dataset coverage:", "- Dataset coverage (with alpha):"),
            "feature account for enabled workstream TIM": text.replace("never by editing: the original records and earlier historical views stay intact", "by editing the record"),
            "feature account for enabled workstream DAT": text.replace("required, never defaulted: a missing or unusable value is refused before any request is sent", "optional"),
            "banned claim word present": text + "\n- Results are validated.\n",
        }
        for expect, bad in cases.items():
            problems = n8.check_correspondence(bad, pol, MATRIX)
            self.assertTrue(any(expect in p for p in problems), (expect, problems))
        # scope expansion: a feature account for a module the scope does not enable
        narrower = copy.deepcopy(SCOPE); narrower["enabled_workstreams"].remove("SET")
        with self.assertRaises(ValueError):                                                          # the account itself refuses to compose for a scope without SET
            n8.capability_matrix(scope=narrower, steps=list(server.STEPS), scorecards=[scorecard("fixtures")])

    def test_matrix_refuses_wrong_inventory_and_reports_incomplete_evidence(self):
        with self.assertRaises(ValueError):
            n8.capability_matrix(scope=SCOPE, steps=list(server.STEPS)[:-1], scorecards=[scorecard("fixtures")])
        wider = copy.deepcopy(SCOPE); wider["enabled_workstreams"].append("CTL")                                   # a deferred workstream has no feature account: enabling it cannot compose
        with self.assertRaises(ValueError):
            n8.capability_matrix(scope=wider, steps=list(server.STEPS), scorecards=[scorecard("fixtures")])
        weak = n8.capability_matrix(scope=SCOPE, steps=list(server.STEPS), scorecards=[scorecard("fixtures", ok=False)])
        self.assertFalse(weak["demonstrated"]); pol = synthetic_policy(); text = compose8(pol, weak)
        self.assertIn("Journey evidence INCOMPLETE", text); self.assertEqual(n8.check_correspondence(text, pol, weak), [])
        self.assertTrue(any("journey evidence is not complete" in p for p in n8.check_correspondence(text.replace("Journey evidence INCOMPLETE", "Journey evidence"), pol, weak)))

    def test_tier2_rules_and_real_tree_matrix(self):
        text = compose8(synthetic_policy())
        for banned in ("docs/", "registry/", "output/", "tools/", "check_", ".py", "seed", "bootstrap", "CI [", "{'", "generated"):
            self.assertNotIn(banned, text, banned)
        self.assertNotIn("independently replicated", text.lower())
        real = n8.capability_matrix()                                                                # the actual tree: scope file + shipped step inventory + recorded scorecards
        self.assertEqual(real["enabled"], SCOPE["enabled_workstreams"]); self.assertEqual(sorted(real["minimal"]), ["ACT", "RIV"])
        self.assertEqual(real["experimental"], []); self.assertTrue(real["demonstrated"], real["evidence"])                                          # V8-014: the four modules are in the enabled scope, none is experimental
        old_scope = json.loads((REPO / "v8" / "scope" / "v8.0.0-scope.before-expansion-2026-09-15.json").read_text()); self.assertEqual(old_scope["experimental_default_off"], ["COM", "PRC", "SHD", "EVO"])   # history preserved
        with self.assertRaises(ValueError):                                                                                                            # the earlier scope cannot compose the expanded account
            n8.capability_matrix(scope=old_scope, steps=list(server.STEPS), scorecards=[scorecard("fixtures")])
        self.assertIn("Modules SHD / EVO / COM / PRC are INCLUDED", text); self.assertIn("No independent security review has been performed", text); self.assertIn("no human productivity result exists", text)
        self.assertEqual(n8.check_correspondence(n8.compose(V6_STYLE.format(v="8.0.0"), version="8.0.0", policy=synthetic_policy(), board=BOARD), synthetic_policy()), [])


if __name__ == "__main__":
    unittest.main()
