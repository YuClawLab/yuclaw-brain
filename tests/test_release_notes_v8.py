"""V8-008 TB-1: the 8.0.0 Tier-2 notes composition path. Fixed inputs only; every policy record here is a SYNTHETIC TEST
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
SCOPE = {"release": "8.0.0", "enabled_workstreams": ["GOV", "DAT", "CLM", "CHK", "TIM", "SET", "SCI", "UX", "INT", "REL"],
         "minimal_shared_behavior": {"RIV": "comparison only", "ACT": "unresolved/next-evidence only"},
         "experimental_default_off": ["COM", "PRC", "SHD", "EVO"], "deferred": ["CTL", "RES", "RND", "full_RIV", "full_ACT", "VAL_real_user_pilot", "multi_tenant_platform", "managed_customer_accounts", "billing"],
         "backup_policy": {"disclosure": "Backup creation and restoration are not provided in 8.0.0. Restore not demonstrated. Research exports and release artifacts do not establish disaster recovery."},
         "initial_real_corpus": {"max_issuers": 1}}
def scorecard(label, ok=True):
    st = "DEMONSTRATED" if ok else "NOT_DEMONSTRATED"
    return {"mode": label, "score": "7/7" if ok else "6/7", "candidate": {"commit": "d" * 40}, "features": {k: {"status": st} for k in ("research_notes", "dataset", "sci")}}
MATRIX = n8.capability_matrix(scope=SCOPE, steps=list(server.STEPS), scorecards=[scorecard("fixtures"), scorecard("mchp")])
SYN_EXC = "SYNTHETIC TEST FIXTURE WORDING (not the owner's, never a decision): exception for Gate #15 for 8.0.0 only; the requirement is NOT SATISFIED; the gate remains MANUAL_REVIEW. Date 2026-09-16."
BOARD = json.loads((REPO / "docs" / "receipts" / "scoreboard.json").read_text())


def synthetic_policy(route="B", version="8.0.0", accepted=True):
    p = {"version": version, "allocation": {"accepted": accepted, "decision": "D1-ACCEPT" if accepted else "PROPOSED — synthetic fixture", "document_id": "SYNTHETIC-TEST-FIXTURE-NOT-A-DECISION", "sha256": "ab" * 32},
         "gate15": {"route": route}, "activations_active": []}
    if route == "B":
        p["gate15"].update(exception_text=SYN_EXC)
    elif route == "A":
        p["gate15"].update(gate_input="CANDIDATE_GATE_INPUT", gate_15_proposed="GREEN", coverage={"materials_manifest_sha256": "c" * 64, "wheel_sha256": "d" * 64})
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
        for v in ("8.0.1", "8.1.0", "9.0.0", "6.0.1", "8.0.0rc1"):
            self.assertIsNone(gen.notes_composer(v), v)
            text, corr = gen.compose_public_notes(v, V6_STYLE.format(v=v), policy=synthetic_policy(), board=BOARD)
            self.assertEqual(text, V6_STYLE.format(v=v)); self.assertEqual(len(corr), 1); self.assertIn("no supported notes composition path", corr[0])
            with self.assertRaises(ValueError):
                n8.compose(V6_STYLE.format(v=v), version=v, policy=None, board=None, matrix=MATRIX)
        with self.assertRaises(ValueError):
            n8.compose(V6_STYLE.format(v="8.0.0"), version="8.0.0", policy=None, board=None, matrix=MATRIX, patch_changes="x")


class PolicyInputs(unittest.TestCase):
    def test_missing_policy_is_a_visible_draft_and_never_corresponds(self):
        text = compose8(None)
        self.assertIn("Release policy: NOT RECORDED", text); self.assertIn("D1 (allocation) and D2 (Gate #15 route) are pending", text)
        self.assertEqual(n8.check_correspondence(text, None, MATRIX), ["no release-policy record"])

    def test_proposed_allocation_is_not_a_decision(self):
        proposed = synthetic_policy(route=None, accepted=False); proposed["gate15"] = {"route": None}
        text = compose8(proposed); problems = n8.check_correspondence(text, proposed, MATRIX)
        self.assertTrue(any("not recorded as accepted" in p for p in problems), problems)
        self.assertTrue(any("no Gate #15 route" in p for p in problems), problems)

    def test_mismatched_and_contradictory_records_fail(self):
        good = synthetic_policy("B"); text = compose8(good); self.assertEqual(n8.check_correspondence(text, good, MATRIX), [])
        other_doc = copy.deepcopy(good); other_doc["allocation"]["document_id"] = "SYNTHETIC-OTHER-DOCUMENT"
        self.assertIn("allocation document id absent from the notes", n8.check_correspondence(text, other_doc, MATRIX))
        other_text = copy.deepcopy(good); other_text["gate15"]["exception_text"] = SYN_EXC.replace("2026-09-16", "2026-09-17")
        self.assertIn("route B: the owner's exception text is not quoted verbatim", n8.check_correspondence(text, other_text, MATRIX))
        no_text = copy.deepcopy(good); del no_text["gate15"]["exception_text"]
        self.assertTrue(any("not quoted verbatim" in p for p in n8.check_correspondence(compose8(no_text), no_text, MATRIX)))
        route_a_no_input = synthetic_policy("A"); del route_a_no_input["gate15"]["gate_input"]
        self.assertTrue(any("route A" in p for p in n8.check_correspondence(compose8(route_a_no_input), route_a_no_input, MATRIX)))
        v7 = synthetic_policy("B", version="7.0.0")
        self.assertTrue(any("not 8.0.0" in p for p in n8.check_correspondence(compose8(v7), v7, MATRIX)))
        active = copy.deepcopy(good); active["activations_active"] = ["sentinel policy"]
        self.assertTrue(any("sentinel policy" in p for p in n8.check_correspondence(text, active, MATRIX)))

    def test_valid_synthetic_policy_passes_only_correspondence(self):
        for route in ("B", "A"):
            pol = synthetic_policy(route); text = compose8(pol)
            self.assertEqual(n8.check_correspondence(text, pol, MATRIX), [], route)
            self.assertIn("SYNTHETIC-TEST-FIXTURE-NOT-A-DECISION", text)
            if route == "B":
                self.assertIn(f"  > {SYN_EXC}", text); self.assertIn("NOT SATISFIED", text)      # the gate is disclosed as unsatisfied, never as passed
            for name, _ in notes_v7.ACTIVATIONS:
                self.assertIn(f"- {name}: INACTIVE", text)
        # correspondence is a text-vs-record relation only: nothing here reads or changes a gate table or an authorization
        self.assertFalse(hasattr(n8, "release_authorized")); self.assertNotIn("release_authorized", text)

    def test_inconsistent_notes_fail_against_the_same_valid_record(self):
        pol = synthetic_policy("B"); text = compose8(pol)
        cases = {
            "backup disclosure absent or not verbatim": text.replace("Restore not demonstrated.", "Restore demonstrated."),
            "real-data statement": text.replace("replayed RETROSPECTIVELY", "replayed prospectively"),
            "simulated-review attribution missing": text.replace(n8.REVIEW_NOTE, "- Review: reviewed."),
            "human benefit PENDING statement missing": text.replace(n8.BENEFIT_NOTE, "- Human benefit: established."),
            "experimental modules": text.replace("ABSENT from the distribution", "included"),
            "feature account for enabled workstream SET": text.replace("- Dataset coverage:", "- Dataset coverage (with alpha):"),
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
        wider = copy.deepcopy(SCOPE); wider["enabled_workstreams"].append("COM")
        with self.assertRaises(ValueError):
            n8.capability_matrix(scope=wider, steps=list(server.STEPS), scorecards=[scorecard("fixtures")])
        weak = n8.capability_matrix(scope=SCOPE, steps=list(server.STEPS), scorecards=[scorecard("fixtures", ok=False)])
        self.assertFalse(weak["demonstrated"]); pol = synthetic_policy("B"); text = compose8(pol, weak)
        self.assertIn("Journey evidence INCOMPLETE", text); self.assertEqual(n8.check_correspondence(text, pol, weak), [])
        self.assertTrue(any("journey evidence is not complete" in p for p in n8.check_correspondence(text.replace("Journey evidence INCOMPLETE", "Journey evidence"), pol, weak)))

    def test_tier2_rules_and_real_tree_matrix(self):
        text = compose8(synthetic_policy("B"))
        for banned in ("docs/", "registry/", "output/", "tools/", "check_", ".py", "seed", "bootstrap", "CI [", "{'", "generated"):
            self.assertNotIn(banned, text, banned)
        self.assertNotIn("independently replicated", text.lower())
        real = n8.capability_matrix()                                                                # the actual tree: scope file + shipped step inventory + recorded scorecards
        self.assertEqual(real["enabled"], SCOPE["enabled_workstreams"]); self.assertEqual(sorted(real["minimal"]), ["ACT", "RIV"])
        self.assertEqual(real["experimental"], ["COM", "PRC", "SHD", "EVO"]); self.assertTrue(real["demonstrated"], real["evidence"])
        self.assertEqual(n8.check_correspondence(n8.compose(V6_STYLE.format(v="8.0.0"), version="8.0.0", policy=synthetic_policy("A"), board=BOARD), synthetic_policy("A")), [])


if __name__ == "__main__":
    unittest.main()
