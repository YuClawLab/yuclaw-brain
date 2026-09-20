"""V8-014 EVO (E-01…E-07) and COM (C-01…C-09) acceptance, plus the X-05 restart/concurrency cases they share. EVO cases
change REAL files under a configured root and let the collector observe them — no hand-edited digest strings. Principals
are automated fixtures. Expected outcomes come from the order; refusals have authorized positive counterparts."""
import json, pathlib, sys, tempfile, threading, unittest
from datetime import timedelta
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from v8_mod_helpers import bundle, load_fixture, principal, workspace          # noqa: E402
from v8.workbench import store                                                  # noqa: E402
from v8.workbench.modules import commons as com, core, evolution as evo, shield  # noqa: E402
from v8.workbench.modules.core import ModuleError                               # noqa: E402

FUTURE = (core.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")


def code(fn, *a, **k):
    try:
        fn(*a, **k)
    except ModuleError as exc:
        return exc.code
    return "NO_ERROR"


class EvoBase(unittest.TestCase):
    POLICY = {"tools": {"read_filing": "allow", "place_order": "deny"}, "default": "deny"}

    def setUp(self):
        self.ws = workspace(); self.admin, _ = principal(self.ws, "owner", ["admin"]); self.imp, _ = principal(self.ws, "improver", ["submit"], by=self.admin)
        self.rev, _ = principal(self.ws, "grader", ["review"], by=self.admin); self.both, _ = principal(self.ws, "impgrader", ["submit", "review"], by=self.admin)
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="v14sys-"))
        for d in ("agent", "policy", "grader", "evaldata", "memory", "data"):
            (self.root / d).mkdir()
        (self.root / "agent" / "agent.py").write_text("print('v1')\n"); (self.root / "memory" / "mem.json").write_text("{}"); (self.root / "data" / "d.csv").write_text("a\n1\n")
        self.write_policy(self.POLICY); (self.root / "grader" / "g.json").write_text(json.dumps({"required_deny": ["place_order"], "required_allow": ["read_filing"]}))
        (self.root / "evaldata" / "cases.json").write_text(json.dumps({"cases": [{"case_id": "c1", "tool": "read_filing", "expect": "allow"}]}))
        self.cfg = {"roots": [str(self.root)], "components": {"model": {"mode": "declared", "value": "provider-alias:latest"}, "agent_code": {"mode": "path", "path": str(self.root / "agent")},
                    "tool_policy": {"mode": "path", "path": str(self.root / "policy")}, "memory": {"mode": "path", "path": str(self.root / "memory")}, "data": {"mode": "path", "path": str(self.root / "data")},
                    "runtime": {"mode": "runtime"}, "grader": {"mode": "path", "path": str(self.root / "grader")}, "evaluation_data": {"mode": "path", "path": str(self.root / "evaldata")}},
                    "depends_on": {"tool_policy": ["agent_code"], "agent_code": ["runtime"]}, "protocols": {"tool-safety": {"scope": ["tool_policy"], "job": "policy_conformance"}, "data-only": {"scope": ["data"], "job": "policy_conformance"}},
                    "authority": {"grader_writer_ids": ["grader"]}}
        evo.set_config(self.ws, self.admin, self.cfg, op_id="op:evo-config1"); self.n = 0

    def write_policy(self, p):
        (self.root / "policy" / "policy.json").write_text(json.dumps(p))

    def reg(self, vid, parent=None, who=None):
        return evo.register_version(self.ws, who or self.imp, version_id=vid, parent_version_id=parent, label=vid, op_id=f"op:evo-reg-{vid}")["payload"]

    def evaluate(self, vid, proto="tool-safety", who=None):
        self.n += 1; return evo.run_evaluation(self.ws, who or self.rev, version_id=vid, protocol_id=proto, op_id=f"op:evo-run-{self.n:03d}")["payload"]


class Evolution(EvoBase):
    def test_E01_inventory_distinguishes_measured_declared_unknown_not_applicable(self):
        v = self.reg("v1"); inv = v["inventory"]
        self.assertEqual(inv["declared"], ["model"]); self.assertIn("runtime", inv["measured"]); self.assertIn("its hash names the string", v["components"]["model"]["detail"])
        cfg = json.loads(json.dumps(self.cfg)); cfg["components"]["memory"] = {"mode": "unknown"}; cfg["components"]["data"] = {"mode": "not_applicable", "justification": "no retrieval data in this system"}
        evo.set_config(self.ws, self.admin, cfg, op_id="op:evo-config2"); v2 = self.reg("v2", "v1")
        self.assertEqual((v2["inventory"]["unknown"], v2["inventory"]["not_applicable"]), (["memory"], ["data"])); self.assertIsNone(v2["components"]["memory"]["digest"])     # no invented hash
        self.assertEqual(code(evo.set_config, self.ws, self.admin, {**cfg, "components": {**cfg["components"], "data": {"mode": "path", "path": "/etc"}}}, op_id="op:evo-config3"), "E_OUTSIDE_ROOTS")
        self.assertEqual(code(evo.set_config, self.ws, self.imp, cfg, op_id="op:evo-config4"), "E_FORBIDDEN")
        (self.root / "agent" / ".env").write_text("SECRET=1"); (self.root / "agent" / "id_rsa").write_text("k"); m = evo.measure_path(self.root / "agent"); self.assertEqual(m["skipped_links_or_secret_names"], 2)   # never read

    def test_E02_E07_real_changes_invalidate_relevant_evidence_and_keep_unrelated_evidence(self):
        self.reg("v1"); self.assertEqual(self.evaluate("v1")["result"], "PASS")
        (self.root / "data" / "d.csv").write_text("a\n2\n"); v2 = self.reg("v2", "v1"); self.assertEqual(v2["changed_components"], ["data"])
        r = evo.audit(self.ws, "v2")["reuse"]["tool-safety"]; self.assertEqual(r["decision"], "REUSE"); self.assertIn("byte-identical", r["reasons"][0])              # unrelated change: justified reuse
        (self.root / "agent" / "agent.py").write_text("print('v3')\n"); v3 = self.reg("v3", "v2"); self.assertEqual(v3["changed_components"], ["agent_code"])
        r = evo.audit(self.ws, "v3")["reuse"]["tool-safety"]; self.assertEqual(r["decision"], "REEVALUATE"); self.assertIn("agent_code", " ".join(r["reasons"]))      # a TRANSITIVE dependency changed
        self.assertEqual(self.evaluate("v3")["result"], "PASS")
        (self.root / "grader" / "g.json").write_text(json.dumps({"required_deny": ["place_order", "wire_money"], "required_allow": ["read_filing"]})); self.reg("v4", "v3")
        r = evo.audit(self.ws, "v4")["reuse"]["tool-safety"]; self.assertEqual(r["decision"], "REEVALUATE"); self.assertIn("grader", " ".join(r["reasons"]))          # a grader change invalidates what it graded
        # E-07: a submitter's metadata cannot drop an edge — the closure comes from the administrator's configuration
        self.assertIn("agent_code", evo.closure(["tool_policy"], evo.state(self.ws)["config"]["depends_on"])); self.assertIn("grader", evo.closure(["data"], {}))
        plan = evo.reevaluation_plan(evo.state(self.ws), "v4"); self.assertEqual(plan["baseline_repeat_everything"], ["data-only", "tool-safety"])

    def test_E07_a_file_swapped_between_collection_and_execution_is_not_evaluated_under_the_old_identity(self):
        self.reg("v1"); self.write_policy({**self.POLICY, "tools": {"read_filing": "allow", "place_order": "allow"}})
        self.assertEqual(code(evo.run_evaluation, self.ws, self.rev, version_id="v1", protocol_id="tool-safety", op_id="op:evo-swap-001"), "REJECTED_SUBJECT_CHANGED")
        self.assertEqual(evo.state(self.ws)["evaluations"], {}); self.reg("v2", "v1"); e = self.evaluate("v2")                                                          # recollected as a NEW identity → evaluated
        self.assertEqual(e["result"], "FAIL"); self.assertEqual(e["subject"]["executed_digests"]["tool_policy"], evo.state(self.ws)["versions"]["v2"]["components"]["tool_policy"]["digest"])

    def test_E01_unknown_required_inventory_blocks_reuse(self):
        self.reg("v1"); self.evaluate("v1"); cfg = json.loads(json.dumps(self.cfg)); cfg["components"]["grader"] = {"mode": "unknown"}
        evo.set_config(self.ws, self.admin, cfg, op_id="op:evo-config5"); self.reg("v2", "v1")
        r = evo.audit(self.ws, "v2"); self.assertEqual(r["reuse"]["tool-safety"]["decision"], "REEVALUATE"); self.assertIn("unknown", r["reuse"]["tool-safety"]["reasons"][0]); self.assertTrue(any(g.startswith("UNKNOWN_INVENTORY grader") for g in r["gaps"]))

    def test_E03_conflicts_through_ancestry_and_persistent_test_exposure(self):
        self.reg("v1", who=self.both); self.reg("v2", "v1")                                                                                                         # `impgrader` improved an ANCESTOR
        self.assertEqual(code(evo.run_evaluation, self.ws, self.both, version_id="v2", protocol_id="tool-safety", op_id="op:evo-conf-001"), "E_CONFLICT")
        self.assertEqual(code(evo.record_review, self.ws, self.both, version_id="v2", decision="REVIEWED_ACCEPTABLE", note="self", op_id="op:evo-conf-002"), "E_CONFLICT")
        self.assertEqual(self.evaluate("v2")["grader_principal"], "grader")                                                                                               # positive counterpart: an independent grader
        evo.record_test_access(self.ws, self.admin, subject_principal="improver", action="GRANTED", op_id="op:evo-acc-0001"); evo.record_test_access(self.ws, self.admin, subject_principal="improver", action="REVOKED", op_id="op:evo-acc-0002")
        a = evo.audit(self.ws, "v2"); self.assertEqual(a["test_exposure"], ["improver"]); self.assertTrue(any("does not erase" in g for g in a["gaps"]))           # revocation does not erase exposure
        cfg = json.loads(json.dumps(self.cfg)); cfg["authority"] = {"grader_writer_ids": ["grader", "improver"]}; evo.set_config(self.ws, self.admin, cfg, op_id="op:evo-config6"); v3 = self.reg("v3", "v2")
        self.assertTrue(v3["authority_changed_from_parent"]); self.assertEqual(evo.audit(self.ws, "v3")["reuse"]["tool-safety"]["decision"], "REEVALUATE")           # authority change: evidence not reused

    def test_E04_a_failure_persists_until_an_authorized_evidence_backed_resolution(self):
        self.write_policy({**self.POLICY, "tools": {"read_filing": "allow", "place_order": "allow"}}); self.reg("v1"); self.assertEqual(self.evaluate("v1")["result"], "FAIL")
        self.write_policy(self.POLICY); self.reg("v2", "v1"); ok = self.evaluate("v2"); self.assertEqual(ok["result"], "PASS")
        a = evo.audit(self.ws, "v2"); self.assertEqual(len(a["open_failures"]), 1); issue = a["open_failures"][0]["issue_id"]                                           # a later PASS erased nothing
        cfg = json.loads(json.dumps(self.cfg)); cfg["protocols"]["tool-safety-renamed"] = cfg["protocols"].pop("tool-safety"); evo.set_config(self.ws, self.admin, cfg, op_id="op:evo-config7"); self.reg("v3", "v2")
        self.assertEqual(len(evo.audit(self.ws, "v3")["open_failures"]), 1)                                                                                           # … nor did a renamed protocol or a new label
        self.reg("x1")                                                                                                                                              # an UNRELATED lineage is not held
        self.assertEqual(evo.audit(self.ws, "x1")["open_failures"], [])
        self.assertEqual(code(evo.resolve_failure, self.ws, self.imp, issue_id=issue, evidence_evaluation_id=ok["evaluation_id"], reason="x", op_id="op:evo-res-0001"), "E_FORBIDDEN")
        self.assertEqual(code(evo.resolve_failure, self.ws, self.admin, issue_id=issue, evidence_evaluation_id="EV1", reason="a FAIL is not evidence", op_id="op:evo-res-0002"), "E_EVIDENCE")
        evo.resolve_failure(self.ws, self.admin, issue_id=issue, evidence_evaluation_id=ok["evaluation_id"], reason="policy restored; trusted-runner PASS on v2", op_id="op:evo-res-0003")
        self.assertEqual(evo.audit(self.ws, "v3")["open_failures"], []); self.assertEqual(len(evo.audit(self.ws, "v1")["open_failures"]), 1)                        # append-only and scoped: v1 stays failed
        self.assertEqual(sum(1 for e in self.ws.load()["events"] if e["kind"] == "EVO_FAILURE_RECORDED"), 1)

    def test_E05_historical_views_use_recorded_time_and_label_backdated_assertions(self):
        self.reg("v1"); __import__("time").sleep(1.1); cut = core.now().strftime("%Y-%m-%dT%H:%M:%SZ"); __import__("time").sleep(1.2)     # cutoffs have one-second resolution
        r = evo.record_review(self.ws, self.rev, version_id="v1", decision="REVIEWED_ACCEPTABLE", note="ok", asserted_review_time="2026-01-01T00:00:00Z", op_id="op:evo-rev-0001")["payload"]
        self.assertTrue(r["asserted_time_label"].startswith("BACKDATED_ASSERTION"))
        self.assertTrue(any(g.startswith("UNREVIEWED_TRANSITION") for g in evo.audit(self.ws, "v1", as_of=cut)["gaps"]))                                            # the later review is NOT known at the earlier cutoff
        self.assertFalse(any(g.startswith("UNREVIEWED_TRANSITION") for g in evo.audit(self.ws, "v1")["gaps"]))

    def test_E06_requests_commitments_eligibility_and_declared_imports(self):
        cid, _ = load_fixture(self.ws); self.reg("v1")
        self.assertEqual(evo.request_reevaluation(self.ws, self.imp, version_id="v1", protocol_id="tool-safety", reason="policy review", op_id="op:evo-req-0001")["payload"]["job"], "policy_conformance")
        evo.link_commitment(self.ws, self.imp, version_id="v1", claim_id=cid, amount="110", currency=None, op_id="op:evo-cmt-0001"); evo.link_commitment(self.ws, self.imp, version_id="v1", claim_id=cid, amount=None, currency=None, op_id="op:evo-cmt-0002")
        a = evo.audit(self.ws, "v1"); self.assertEqual(a["linked_commitments_by_currency"]["USD"], {"known_total": 110, "known_count": 1, "unknown_amount_count": 1, "claims": [cid, cid]})
        self.assertIn("controls no external deployment", a["eligibility"]["scope"]); self.assertEqual(code(evo.link_commitment, self.ws, self.imp, version_id="v1", claim_id="NO-SUCH", amount=None, currency=None, op_id="op:evo-cmt-0003"), "E_UNKNOWN_CLAIM")
        shield.enroll_root(self.ws, self.admin, label="r", op_id="op:root-000001")
        data, h, srcs = bundle(purpose="evo.evaluations", payload={"evaluations": [{"evaluation_id": "ext-1", "version_id": "v1", "protocol_id": "tool-safety", "result": "PASS", "scope_components": ["tool_policy"], "evaluated_at": "2026-09-01T00:00:00Z", "valid_until": "2027-09-01T00:00:00Z"}]})
        sid = shield.submit(self.ws, self.imp, data, title="declared", op_id="op:sub-declared1")["payload"]["submission_id"]
        self.assertEqual(code(evo.import_declared, self.ws, self.imp, "DC1", op_id="op:evo-imp-0001"), "REFUSED_NOT_ADMITTED")                                       # nothing un-admitted reaches EVO
        shield.issue_approval(self.ws, self.admin, bundle_sha256=h, source_sha256s=srcs, purpose="evo.evaluations", expires_at=FUTURE, op_id="op:apr-declared1")
        d = shield.admit(self.ws, self.imp, sid, op_id="op:adm-declared1")["payload"]; self.assertEqual(d["result"], "ADMITTED"); evs = evo.import_declared(self.ws, self.imp, d["decision_id"], op_id="op:evo-imp-0002")
        self.assertEqual(evs[0]["payload"]["origin"], "DECLARED_IMPORT"); self.assertEqual(evo.audit(self.ws, "v1")["reuse"]["tool-safety"]["decision"], "REEVALUATE")   # a declaration is never trusted-runner evidence


class ComBase(unittest.TestCase):
    def setUp(self):
        self.ws = workspace(); self.admin, _ = principal(self.ws, "owner", ["admin"]); self.alice, _ = principal(self.ws, "alice", ["submit"], by=self.admin); self.bob, _ = principal(self.ws, "bob", ["submit"], by=self.admin)
        self.rita, _ = principal(self.ws, "rita", ["review"], by=self.admin); self.ravi, _ = principal(self.ws, "ravi", ["review"], by=self.admin)
        self.c1, self.s1 = load_fixture(self.ws, "001_base", 1); self.c2, self.s2 = load_fixture(self.ws, "008_quarterly", 2); self.n = 0

    def budget(self, review=120, practice=30, cap=6, open_=20, period="p1"):
        self.n += 1; return com.set_budget(self.ws, self.admin, period_id=period, review_minutes=review, practice_minutes=practice, contributor_packet_cap=cap, max_open_tasks=open_, op_id=f"op:budget-{self.n:03d}")

    def pk(self, who, claim, **kw):
        self.n += 1; a = dict(kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=30, asserts_withdrawn=False, client_packet_id=None); a.update(kw)
        return com.submit_direct(self.ws, who, claim_id=claim, op_id=f"op:pk-{self.n:05d}", **a)["payload"]

    def op(self):
        self.n += 1; return f"op:com-{self.n:05d}"


class Commons(ComBase):
    def test_C01_C02_groups_persist_across_restart_and_incompatible_contracts_stay_separate(self):
        self.budget(); a = self.pk(self.alice, self.c1); b = self.pk(self.bob, self.c1); c = self.pk(self.alice, self.c2); u = self.pk(self.bob, self.c1, ancestry="UNKNOWN")
        self.assertEqual(a["group_id"], b["group_id"]); self.assertNotEqual(a["group_id"], c["group_id"]); self.assertNotEqual(a["group_id"], u["group_id"])       # exact identity only; unknown ancestry stays apart
        again = store.Workspace(self.ws.root); s = com.state(again); self.assertEqual(len(s["groups"]), 3); self.assertEqual(sorted(s["groups"][a["group_id"]]["contributors"]), ["alice", "bob"])   # after restart; attribution kept
        d = self.pk(self.alice, self.c1); self.assertTrue(d["duplicate_of_group"]); self.assertEqual(len(com.state(self.ws)["groups"]), 3)                           # a repeat after restart joins, never a new task
        dash = com.dashboard(self.ws); self.assertEqual((dash["packets"], dash["groups"], dash["duplicate_volume"], dash["unknown_ancestry_groups"]), (5, 3, 2, 1))
        self.assertIn(self.s1, dash["shared_roots"])                                                                                                                # one root behind two groups is shown, not counted twice as corroboration
        same = com.submit_direct(self.ws, self.alice, claim_id=self.c1, kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=30, asserts_withdrawn=False, client_packet_id=None, op_id="op:pk-00002")
        self.assertEqual(same["payload"]["packet_id"], a["packet_id"])                                                                                               # idempotent retry of the same operation
        self.assertEqual(code(com.submit_direct, self.ws, self.alice, claim_id="NOPE", kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=1, asserts_withdrawn=False, client_packet_id=None, op_id="op:pk-nope0001"), "E_UNKNOWN_CLAIM")

    def test_C04_caps_count_the_authenticated_principal_and_bound_the_queue(self):
        self.assertEqual(code(com.submit_direct, self.ws, self.alice, claim_id=self.c1, kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=1, asserts_withdrawn=False, client_packet_id=None, op_id="op:pk-nobudget"), "E_NOT_CONFIGURED")
        self.budget(cap=2, open_=1); self.pk(self.alice, self.c1, client_packet_id="name-1"); self.pk(self.alice, self.c1, client_packet_id="a-new-display-name")
        with self.assertRaises(ModuleError) as cm:
            self.pk(self.alice, self.c1, client_packet_id="yet-another-name")
        self.assertEqual(cm.exception.code, "E_CONTRIBUTOR_CAP"); self.assertEqual(self.pk(self.bob, self.c1)["submitter"], "bob")                                   # another principal is unaffected
        with self.assertRaises(ModuleError) as cm:
            self.pk(self.bob, self.c2)                                                                                                                                # a NEW group beyond the open-task bound
        self.assertEqual(cm.exception.code, "E_QUEUE_BOUND")
        with mock.patch.object(com, "RATE_PER_MINUTE", 1):
            with self.assertRaises(ModuleError) as cm:
                self.pk(self.bob, self.c1)
        self.assertEqual(cm.exception.code, "E_RATE"); self.assertEqual(code(com.set_budget, self.ws, self.alice, period_id="p1", review_minutes=9999, practice_minutes=0, contributor_packet_cap=99, max_open_tasks=99, op_id="op:budget-alice"), "E_FORBIDDEN")

    def test_C05_concurrent_reservation_never_double_spends_and_X11_detects_a_disabled_check(self):
        def race(patch_capacity):
            self.setUp(); self.budget(review=60); g1 = self.pk(self.alice, self.c1)["group_id"]; g2 = self.pk(self.alice, self.c2)["group_id"]
            for g in (g1, g2):
                com.set_cost(self.ws, self.rita, group_id_=g, minutes=40, rule="reviewer estimate", op_id=self.op())
            res = {}

            def take(p, g, tag):
                res[tag] = code(com.assign, self.ws, p, g, op_id=f"op:assign-{tag}-{self.n}")
            real = com.plan
            ctx = mock.patch.object(com, "plan", lambda s, now=None: {**real(s, now), "selected": [{"group_id": g["group_id"]} for g in s["groups"].values()]}) if patch_capacity else mock.patch.object(com, "DEFAULT_COST_MINUTES", 30)
            with ctx:
                ts = [threading.Thread(target=take, args=(self.rita, g1, "a")), threading.Thread(target=take, args=(self.ravi, g2, "b"))]; [t.start() for t in ts]; [t.join() for t in ts]
            return res, com.capacity(com.state(self.ws))
        res, cap = race(False); self.assertEqual(sorted(res.values()), ["E_NO_CAPACITY", "NO_ERROR"]); self.assertEqual((cap["reserved"], cap["remaining"], cap["overrun"]), (40, 20, 0))
        res, cap = race(True)                                                                                                                                       # isolated variant with the capacity check disabled …
        with self.assertRaises(AssertionError):
            self.assertEqual(cap["overrun"], 0)                                                                                                                       # … and the same assertion now FAILS: the test detects it

    def test_C05_C06_state_machine_leases_rollover_cancellation_and_three_effort_numbers(self):
        self.budget(review=100); g = self.pk(self.alice, self.c1)["group_id"]; small = self.pk(self.alice, self.c2)["group_id"]
        self.assertEqual(code(com.assign, self.ws, self.alice, g, op_id=self.op()), "E_FORBIDDEN")
        a2, _ = principal(self.ws, "alicerev", ["review", "submit"], by=self.admin); self.pk(a2, self.c1); self.assertEqual(code(com.assign, self.ws, a2, g, op_id=self.op()), "E_CONFLICT")   # a contributor cannot review its own group
        com.assign(self.ws, self.rita, g, op_id=self.op()); self.assertEqual(code(com.work, self.ws, self.ravi, g, "start", op_id=self.op()), "E_FORBIDDEN")
        com.work(self.ws, self.rita, g, "start", op_id=self.op()); __import__("time").sleep(1.1); com.work(self.ws, self.rita, g, "pause", op_id=self.op()); self.assertEqual(code(com.work, self.ws, self.rita, g, "pause", op_id=self.op()), "E_TRANSITION")
        com.declare_effort(self.ws, self.rita, group_id_=g, minutes=12, category="triage", op_id=self.op())
        st = com.state(store.Workspace(self.ws.root))["groups"][g]; self.assertEqual(st["state"], "PAUSED"); self.assertGreaterEqual(st["observed_seconds"], 1)             # resumes after restart with partial work
        real = core.now
        with mock.patch.object(core, "now", lambda: real() + timedelta(hours=5)):
            out = com.recover_leases(self.ws, self.ravi, op_id=self.op())
        self.assertEqual(len(out), 1); st = com.state(self.ws)["groups"][g]; self.assertEqual((st["state"], st["reservation"]), ("QUEUED", None)); self.assertGreaterEqual(st["observed_seconds"], 1)   # lease expiry keeps partial work, frees capacity
        com.assign(self.ws, self.rita, g, op_id=self.op()); self.budget(review=100, period="p2"); st = com.state(self.ws)["groups"][g]                                       # ROLLOVER: back to the queue, history kept
        self.assertEqual(st["state"], "QUEUED"); self.assertIn("ROLLOVER", st["history"][-1]["reason"]); self.assertEqual(com.capacity(com.state(self.ws))["reserved"], 0)
        com.assign(self.ws, self.rita, g, op_id=self.op()); com.work(self.ws, self.rita, g, "start", op_id=self.op()); com.work(self.ws, self.rita, g, "finish", note="reviewed", op_id=self.op())
        com.assign(self.ws, self.ravi, small, op_id=self.op()); com.work(self.ws, self.admin, small, "cancel", note="out of scope", op_id=self.op())
        d = com.dashboard(self.ws); self.assertEqual((d["by_state"]["COMPLETED"], d["by_state"]["CANCELED"]), (1, 1)); self.assertEqual(d["capacity"]["consumed"], 30); self.assertEqual(d["capacity"]["reserved"], 0)
        self.assertEqual(d["effort"]["declared_minutes_by_category"], {"triage": 12}); self.assertEqual(d["effort"]["estimated_minutes_completed"], 30); self.assertGreaterEqual(d["effort"]["server_observed_seconds"], 1)

    def test_C06_C09_fit_smaller_aged_hold_oversized_escalation_urgent_and_budget_cut(self):
        self.budget(review=60); small = self.pk(self.alice, self.c2)["group_id"]; big = self.pk(self.alice, self.c1)["group_id"]                                       # `small` arrives first
        com.set_cost(self.ws, self.rita, group_id_=big, minutes=50, rule="long filing", op_id=self.op()); com.set_cost(self.ws, self.rita, group_id_=small, minutes=20, rule="short", op_id=self.op())
        p = com.plan(com.state(self.ws)); self.assertEqual([r["group_id"] for r in p["selected"]], [small]); self.assertIn("NO_REMAINING_CAPACITY", p["deferred"][0]["reason"]); self.assertEqual(p["unspent_after_plan"], 40)
        self.assertEqual(code(com.assign, self.ws, self.ravi, big, op_id=self.op()), "E_NO_CAPACITY"); com.assign(self.ws, self.ravi, small, op_id=self.op())               # refusal + its positive counterpart
        third, _ = load_fixture(self.ws, "001_base", 3, claim_id="ZZFX-FY2026-REV-GUIDE-B"); g3 = self.pk(self.bob, third, proposed_cost_minutes=5)["group_id"]; com.set_cost(self.ws, self.rita, group_id_=g3, minutes=5, rule="tiny", op_id=self.op())
        p = com.plan(com.state(self.ws)); self.assertEqual([r["group_id"] for r in p["selected"]], [g3])                                                              # the big task does not fit; a smaller later one proceeds
        com.set_cost(self.ws, self.rita, group_id_=big, minutes=500, rule="re-estimated", op_id=self.op()); p = com.plan(com.state(self.ws))
        self.assertIn("OVERSIZED_FOR_BUDGET", next(r["reason"] for r in p["deferred"] if r["group_id"] == big)); self.assertEqual([r["group_id"] for r in p["selected"]], [g3])   # oversized escalates and blocks nothing
        com.set_cost(self.ws, self.rita, group_id_=big, minutes=50, rule="back", op_id=self.op()); real = core.now
        with mock.patch.object(core, "now", lambda: real() + timedelta(hours=30)):                                                                                   # big is now AGED and does not fit → it HOLDS the capacity
            p = com.plan(com.state(self.ws)); self.assertEqual(p["selected"], []); self.assertIn("HELD", next(r["reason"] for r in p["deferred"] if r["group_id"] == g3))   # small late arrivals cannot starve it
            self.assertIn("aged", next(r["reason"] for r in p["deferred"] if r["group_id"] == big))
        self.assertEqual(code(com.override_urgent, self.ws, self.rita, group_id_=big, reason="x", op_id=self.op()), "E_FORBIDDEN"); com.override_urgent(self.ws, self.admin, group_id_=big, reason="regulator deadline", op_id=self.op())
        p = com.plan(com.state(self.ws)); self.assertIn("URGENT_WAITING_FOR_CAPACITY", next(r["reason"] for r in p["deferred"] if r["group_id"] == big))               # an override orders; it creates no capacity
        self.budget(review=10); cap = com.capacity(com.state(self.ws)); self.assertEqual((cap["reserved"], cap["remaining"], cap["overrun"]), (20, 0, 10))              # cut below use: overrun shown, nothing rewritten, never negative
        self.assertTrue(all("BUDGET_OVERRUN" in r["reason"] for r in com.plan(com.state(self.ws))["deferred"])); self.assertEqual(len(cap["revisions"]), 2)

    def test_C08_a_duplicate_submitter_cannot_move_the_scheduling_cost_in_either_direction(self):
        self.budget(); g = self.pk(self.alice, self.c1, proposed_cost_minutes=600)["group_id"]; self.assertEqual(com.state(self.ws)["groups"][g]["cost_minutes"], com.DEFAULT_COST_MINUTES)
        self.assertEqual(code(com.set_cost, self.ws, self.alice, group_id_=g, minutes=1, rule="mine", op_id=self.op()), "E_FORBIDDEN")
        com.set_cost(self.ws, self.rita, group_id_=g, minutes=45, rule="reviewer estimate", op_id=self.op()); self.pk(self.bob, self.c1, proposed_cost_minutes=1); self.pk(self.bob, self.c1, proposed_cost_minutes=600)
        st = com.state(self.ws)["groups"][g]; self.assertEqual(st["cost_minutes"], 45); self.assertEqual(st["proposed_costs"], [600, 1, 600])                         # proposals recorded, authority unchanged
        com.assign(self.ws, self.rita, g, op_id=self.op()); self.assertEqual(com.capacity(com.state(self.ws))["reserved"], 45); self.pk(self.bob, self.c1, proposed_cost_minutes=1)
        self.assertEqual(com.capacity(com.state(self.ws))["reserved"], 45)                                                                                           # a later duplicate cannot shrink the reservation either

    def test_C03_only_an_authorized_dispute_changes_handling_and_history_survives_appeal_and_resolution(self):
        self.budget(); g = self.pk(self.alice, self.c1, asserts_withdrawn=True)["group_id"]; child = self.pk(self.bob, self.c2, derived_from=[self.s1])["group_id"]
        self.assertEqual(com.state(self.ws)["groups"][g]["quarantined_by"], [])                                                                                      # a submitter's "withdrawn" assertion quarantines nothing
        self.assertEqual(code(com.record_dispute, self.ws, self.alice, target_type="source", target=self.s1, dispute_type="WITHDRAWN", reason="I say so", op_id=self.op()), "E_FORBIDDEN")
        before = self.ws.claim_state(self.c1)["versions"][0]["claim"]["source"]["source_hash"]
        dp = com.record_dispute(self.ws, self.rita, target_type="source", target=self.s1, dispute_type="WITHDRAWN", reason="issuer withdrew the release", op_id=self.op())["payload"]["dispute_id"]
        s = com.state(self.ws); self.assertEqual(s["groups"][g]["quarantined_by"], [dp]); self.assertEqual(s["groups"][child]["quarantined_by"], [dp])              # propagated through the declared dependency
        self.assertEqual(code(com.assign, self.ws, self.ravi, g, op_id=self.op()), "E_NO_CAPACITY"); self.assertEqual(self.ws.claim_state(self.c1)["versions"][0]["claim"]["source"]["source_hash"], before)   # source bytes untouched
        com.appeal(self.ws, self.alice, dispute_id=dp, reason="the release is still on the issuer's site", op_id=self.op())
        self.assertEqual(code(com.resolve_dispute, self.ws, self.rita, dispute_id=dp, outcome="LIFTED", reason="x", op_id=self.op()), "E_FORBIDDEN")
        com.resolve_dispute(self.ws, self.admin, dispute_id=dp, outcome="LIFTED", reason="checked: not withdrawn", op_id=self.op()); s = com.state(self.ws)
        self.assertEqual(s["groups"][g]["quarantined_by"], []); d = s["disputes"][dp]; self.assertEqual((len(d["appeals"]), d["resolution"]["outcome"], d["reason"]), (1, "LIFTED", "issuer withdrew the release"))   # nothing erased
        com.assign(self.ws, self.ravi, g, op_id=self.op())                                                                                                            # reversible by new event: work resumes

    def test_C01_intake_from_shield_needs_an_admitted_and_still_approved_bundle(self):
        self.budget(); shield.enroll_root(self.ws, self.admin, label="r", op_id="op:root-000001"); vd = core.claim_ref(self.ws, self.c1)["version_digest"]
        rows = [{"packet_id": f"ext-{i}", "claim_id": self.c1, "claim_version_digest": vd, "source_roots": [self.s1], "kind": "SUMMARY", "ancestry": "KNOWN", "proposed_cost_minutes": 10} for i in range(3)]
        data, h, srcs = bundle(purpose="com.packets", payload={"packets": rows}); sid = shield.submit(self.ws, self.alice, data, title="packets", op_id="op:sub-packets1")["payload"]["submission_id"]
        d0 = shield.admit(self.ws, self.alice, sid, op_id="op:adm-packets0")["payload"]; self.assertEqual(code(com.intake_from_shield, self.ws, self.alice, d0["decision_id"], op_id="op:intake-0001"), "REFUSED_NOT_ADMITTED")
        ap = shield.issue_approval(self.ws, self.admin, bundle_sha256=h, source_sha256s=srcs, purpose="com.packets", expires_at=FUTURE, op_id="op:apr-packets1")["payload"]
        d = shield.admit(self.ws, self.alice, sid, op_id="op:adm-packets1")["payload"]; out = com.intake_from_shield(self.ws, self.alice, d["decision_id"], op_id="op:intake-0002")
        self.assertEqual(len(out), 3); self.assertEqual(len(com.state(self.ws)["groups"]), 1); self.assertEqual(out[0]["payload"]["admission"], {"route": "SHD_ADMITTED", "shd_decision_id": d["decision_id"]})
        self.assertEqual(len(com.intake_from_shield(self.ws, self.alice, d["decision_id"], op_id="op:intake-0002")), 3); self.assertEqual(len(com.state(self.ws)["packets"]), 3)     # idempotent
        shield.revoke_approval(self.ws, self.admin, ap["approval_id"], "withdrawn", op_id="op:rev-packets1"); self.assertEqual(code(com.intake_from_shield, self.ws, self.bob, d["decision_id"], op_id="op:intake-0003"), "REFUSED_APPROVAL_REVOKED")

    def test_C07_the_fifo_comparison_is_reproducible_and_labelled(self):
        arr = [{"key": k, "minutes": m} for k, m in (("A", 30), ("A", 30), ("B", 90), ("C", 20), ("A", 30), ("D", 25))]; a, b = com.simulate(arr, 100), com.simulate(arr, 100)
        self.assertEqual(a, b); self.assertIn("simulation", a["label"]); self.assertIn("nothing about human productivity", a["label"])
        self.assertEqual((a["plain_fifo"]["completed_unique_keys"], a["fifo_exact_dedup"]["completed_unique_keys"], a["commons_rule"]["completed_unique_keys"]), (1, 1, 3)); self.assertEqual(a["plain_fifo"]["minutes_spent_on_duplicates"], 30)


if __name__ == "__main__":
    unittest.main()
