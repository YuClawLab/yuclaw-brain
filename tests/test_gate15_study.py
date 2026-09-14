"""Gate #15 study tooling: deterministic evaluator on SYNTHETIC forms (no human results), gate-evidence adapter
prerequisites, schema/doc consistency, participant packet without the scoring key."""
import json, pathlib, sys, tempfile, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tools"))
from v3.study import gate15_schema as S, evaluate as E  # noqa: E402
import yuclaw_gate15_study as tool  # noqa: E402


def task(n, *, done=True, minutes=5, miss=(), crit=()):
    spec = S.TASKS[n]
    return {"task": n, "completed": done, "minutes": minutes, "elements": {k: k not in miss for k in spec["elements"]}, "critical": {k: k in crit for k in spec["critical"]}, "note": "synthetic"}


def form(code, mode="EXECUTION", tasks=None, assistance="NONE", wheel="REHEARSAL"):
    return {"session_code": code, "mode": mode, "materials_manifest_sha256": "a" * 64, "wheel_label": wheel, "tasks": [task(i) for i in range(1, 6)] if tasks is None else tasks,
            "assistance": assistance, "relationship": "UNRELATED", "reviewer_role": "study-reviewer", "decided_at": "2026-09-20T00:00:00.000000Z"}


class Evaluator(unittest.TestCase):
    def test_task_rules_and_session_decisions(self):
        self.assertEqual(E.score_task(task(1))["result"], "PASS")
        self.assertEqual(E.score_task(task(1, miss=("E1.2",)))["result"], "FAIL_INCOMPLETE")                       # avoiding wrong statements never passes an incomplete answer
        self.assertEqual(E.score_task(task(1, crit=("C1.1",)))["result"], "FAIL_CRITICAL")
        self.assertEqual(E.score_task(task(1, minutes=11))["result"], "INCOMPLETE"); self.assertEqual(E.score_task(task(1, done=False))["result"], "INCOMPLETE")
        self.assertEqual(E.score_session(form("s1"))["decision"], "PASS")
        self.assertEqual(E.score_session(form("s2", tasks=[task(i) for i in range(1, 5)] + [task(5, minutes=12)]))["decision"], "FAIL")   # a timeout cannot slip through
        self.assertEqual(E.score_session(form("s3", assistance="LIVE_HELP"))["decision"], "ASSISTED")                # assistance precedence
        self.assertEqual(E.score_session(form("s4", tasks=[]))["decision"], "MISSING")
        with self.assertRaises(E.FormError): E.score_session(form("s5", tasks=[task(1)]))
        with self.assertRaises(E.FormError): E.score_session(form("s6", wheel="NONE"))
        bad = form("s7"); bad["tasks"][0]["elements"].pop("E1.1")
        with self.assertRaises(E.FormError): E.score_session(bad)
    def test_aggregate_fixed_denominator_no_pooling(self):
        sessions = [E.score_session(form(f"e{i}")) for i in range(3)] + [E.score_session(form("t1", mode="TRANSCRIPT", wheel="NONE"))]
        agg = E.aggregate(sessions); ex = agg["by_mode"]["EXECUTION"]; tr = agg["by_mode"]["TRANSCRIPT"]
        self.assertEqual((ex["n_pass"], ex["denominator"], ex["counts"]["MISSING"]), (3, 5, 2)); self.assertEqual((tr["n_pass"], tr["counts"]["MISSING"]), (1, 4))
        self.assertFalse(ex["candidate_threshold_met"]); self.assertEqual(agg["pooled"], "NEVER"); self.assertEqual(ex["threshold_status"], "UNADOPTED")
        with self.assertRaises(E.FormError): E.aggregate([E.score_session(form(f"e{i}")) for i in range(6)])
    def test_gate_evidence_needs_every_prerequisite(self):
        agg = E.aggregate([E.score_session(form(f"e{i}")) for i in range(5)])
        out = E.gate_evidence(agg, protocol_adoption=None, applicability=None, reviewer_appointment=None, human_records=False)
        self.assertEqual(out["gate_input"], "NOT_A_GATE_INPUT"); self.assertEqual(len(out["missing_prerequisites"]), 4); self.assertEqual(out["gate_15"], "MANUAL_REVIEW (unchanged)")
        full = E.gate_evidence(agg, protocol_adoption={"protocol_id": S.PROTOCOL_ID, "adopted": True}, applicability={"determination": "exempt"}, reviewer_appointment={"status": "DESIGNATED"}, human_records=True)
        self.assertEqual(full["gate_input"], "CANDIDATE_GATE_INPUT"); self.assertEqual(full["gate_15_proposed"], "GREEN"); self.assertEqual(full["coverage"]["wheel_labels"], ["REHEARSAL"])
        self.assertIn("does not transfer", full["coverage"]["note"])
    def test_docs_agree_with_schema_and_packet_has_no_key(self):
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): rc = tool.main(["check-docs"])
        self.assertEqual(rc, 0, buf.getvalue())
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()): rc = tool.main(["build-packet", d + "/pk", "--source", str(REPO), "--mode", "TRANSCRIPT"])
            self.assertEqual(rc, 0); pm = json.loads(pathlib.Path(d, "pk", "participant_manifest.json").read_text())
            self.assertFalse(pm["scoring_key_included"]); self.assertFalse(any("scoring_key" in str(p) for p in pathlib.Path(d, "pk").rglob("*")))
            v = pathlib.Path(d, "pk", "verification_packet", "VERIFY.md").read_text(); self.assertIn("Recorded verify output", v); self.assertIn("Challenge template", v); self.assertIn("[exit 0]", v)


if __name__ == "__main__":
    unittest.main(verbosity=2)
