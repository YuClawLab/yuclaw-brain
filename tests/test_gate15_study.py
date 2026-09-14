"""Gate #15 study tooling (V5 closure): the evaluator enforces its protocol — distinct sessions, cohort bindings by bytes,
finite times, synthetic provenance end to end, trusted-record prerequisites — through the study CLI and adapter."""
import contextlib, io, json, pathlib, sys, tempfile, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tools"))
from v3.study import gate15_schema as S, evaluate as E  # noqa: E402
import yuclaw_gate15_study as tool  # noqa: E402

W = {"label": "REHEARSAL", "artifact_type": "wheel", "sha256": "a" * 64, "size_bytes": 690694}
MAN = "b" * 64


def task(n, *, done=True, minutes=5, miss=(), crit=()):
    spec = S.TASKS[n]
    return {"task": n, "completed": done, "minutes": minutes, "elements": {k: k not in miss for k in spec["elements"]}, "critical": {k: k in crit for k in spec["critical"]}, "note": "synthetic"}


def form(code, mode="EXECUTION", tasks=None, assistance="NONE", wheel=W, man=MAN, synthetic=False, **extra):
    d = {"session_code": code, "mode": mode, "protocol_id": S.PROTOCOL_ID, "materials_manifest_sha256": man, "wheel": wheel, "tasks": [task(i) for i in range(1, 6)] if tasks is None else tasks,
         "assistance": assistance, "relationship": "UNRELATED", "reviewer_role": "study-reviewer", "decided_at": "2026-09-20T00:00:00.000000Z", "synthetic": synthetic}
    d.update(extra); return d


class Evaluator(unittest.TestCase):
    def test_task_rules_and_types(self):
        self.assertEqual(E.score_task(task(1))["result"], "PASS"); self.assertEqual(E.score_task(task(1, miss=("E1.2",)))["result"], "FAIL_INCOMPLETE")
        self.assertEqual(E.score_task(task(1, crit=("C1.1",)))["result"], "FAIL_CRITICAL"); self.assertEqual(E.score_task(task(1, minutes=11))["result"], "INCOMPLETE")
        for bad in (float("nan"), float("inf"), True, -1, 601, "5"):
            with self.assertRaises(E.FormError): E.score_task(task(1, minutes=bad))
        self.assertEqual(E.score_session(form("s1"))["decision"], "PASS"); self.assertEqual(E.score_session(form("s2", tasks=[task(i) for i in range(1, 5)] + [task(5, minutes=12)]))["decision"], "FAIL")
        self.assertEqual(E.score_session(form("s3", assistance="LIVE_HELP"))["decision"], "ASSISTED"); self.assertEqual(E.score_session(form("s4", tasks=[]))["decision"], "MISSING")
        with self.assertRaises(E.FormError): E.score_session(form("s6", wheel={"label": "NONE", "artifact_type": "none", "sha256": None, "size_bytes": None}))   # EXECUTION needs bytes
        with self.assertRaises(E.FormError): E.score_session(form("s7", wheel=dict(W, sha256="short")))
        with self.assertRaises(E.FormError): E.score_session(form("s8", protocol_id="other"))
        with self.assertRaises(E.FormError): E.score_session(form("s9", synthetic="yes"))
        with self.assertRaises(E.FormError): E.score_session(form("s10", extra_field=1))
    def test_duplicates_cohorts_and_no_pooling(self):
        one = E.score_session(form("e1"))
        with self.assertRaises(E.FormError): E.aggregate([one] * 5)                                                                         # one passing session copied five times
        sessions = [E.score_session(form(f"e{i}")) for i in range(3)] + [E.score_session(form("x1", wheel=dict(W, sha256="c" * 64)))]   # a different wheel → another cohort
        agg = E.aggregate(sessions); self.assertEqual(len(agg["cohorts"]), 2); prim = [c for c in agg["cohorts"] if c["cohort"]["wheel_sha256"] == "a" * 64][0]
        self.assertEqual((prim["n_pass"], prim["counts"]["MISSING"], prim["distinct_participants"]), (3, 2, 3)); self.assertEqual(agg["pooled"], "NEVER")
        self.assertFalse(prim["candidate_threshold_met"])
        rc = E.aggregate([E.score_session(form("t1", mode="TRANSCRIPT", wheel={"label": "NONE", "artifact_type": "none", "sha256": None, "size_bytes": None}))]); self.assertFalse(rc["cohorts"][0]["primary"])
    def test_gate_evidence_needs_records_not_flags(self):
        sessions = [E.score_session(form(f"e{i}")) for i in range(5)]; agg = E.aggregate(sessions)
        appts = [{"kind": "appointment", "appointment_id": "d" * 64, "role": "study-reviewer", "status": "DESIGNATED", "designated": True}]
        adoption = {"protocol_id": S.PROTOCOL_ID, "adopted": True, "adopted_by": "owner", "adopted_at": "2026-09-20T00:00:00Z", "kit_sha256": "e" * 64, "materials_manifest_sha256": MAN}
        applic = {"determination": "exempt", "reference": "ref-1", "issued_by": "institution", "date": "2026-09-20", "protocol_id": S.PROTOCOL_ID}
        reviewer = {"role": "study-reviewer", "appointment_id": "d" * 64}
        human = [{"session_code": f"e{i}", "reviewer_role": "study-reviewer", "appointment_id": "d" * 64, "decided_at": "2026-09-20T00:00:00Z"} for i in range(5)]
        out = E.gate_evidence(agg, protocol_adoption=adoption, applicability=applic, reviewer_appointment=reviewer, appointments=appts, human_records=human, sessions=sessions)
        self.assertEqual(out["gate_input"], "CANDIDATE_GATE_INPUT"); self.assertEqual(out["gate_15_proposed"], "GREEN"); self.assertEqual(out["coverage"]["wheel_sha256"], "a" * 64)
        self.assertEqual(E.gate_evidence(agg, protocol_adoption=adoption, applicability=applic, reviewer_appointment={"role": "study-reviewer", "appointment_id": "d" * 64, "status": "DESIGNATED"}, appointments=[], human_records=human, sessions=sessions)["gate_input"], "NOT_A_GATE_INPUT")   # self-declared DESIGNATED, no record
        self.assertEqual(E.gate_evidence(agg, protocol_adoption=dict(adoption, adopted=True, materials_manifest_sha256="f" * 64), applicability=applic, reviewer_appointment=reviewer, appointments=appts, human_records=human, sessions=sessions)["gate_input"], "NOT_A_GATE_INPUT")   # adoption bound to other materials
        self.assertEqual(E.gate_evidence(agg, protocol_adoption=adoption, applicability=applic, reviewer_appointment=reviewer, appointments=appts, human_records=True, sessions=sessions)["gate_input"], "NOT_A_GATE_INPUT")   # a flag is not a record
        syn = [E.score_session(form(f"s{i}", synthetic=True)) for i in range(5)]; out = E.gate_evidence(E.aggregate(syn), protocol_adoption=adoption, applicability=applic, reviewer_appointment=reviewer, appointments=appts, human_records=human, sessions=syn)
        self.assertEqual(out["gate_input"], "NOT_A_GATE_INPUT"); self.assertTrue(out["missing_prerequisites"][0].startswith("synthetic cohort"))
        four = [E.score_session(form(f"e{i}")) for i in range(4)]; out = E.gate_evidence(E.aggregate(four), protocol_adoption=adoption, applicability=applic, reviewer_appointment=reviewer, appointments=appts, human_records=human[:4], sessions=four)
        self.assertEqual(out["gate_input"], "NOT_A_GATE_INPUT"); self.assertTrue(any("distinct participants" in m for m in out["missing_prerequisites"]))
    def test_cli_evaluate_and_gate_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d); forms = d / "forms"; forms.mkdir()
            (forms / "a.json").write_text(json.dumps(form("e1"))); (forms / "b.json").write_text(json.dumps(form("e1")))                 # duplicate code
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                rc = tool.main(["evaluate", str(forms), "--out", str(d / "ev.json")])
            self.assertEqual(rc, 1); self.assertIn("duplicated session codes", err.getvalue())
            (forms / "b.json").write_text(json.dumps(form("e2", tasks=[task(1, minutes=float("nan"))] + [task(i) for i in range(2, 6)])))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                rc = tool.main(["evaluate", str(forms), "--out", str(d / "ev.json")])
            self.assertEqual(rc, 1); self.assertIn("finite", err.getvalue())
            for i in range(5): (forms / f"f{i}.json").write_text(json.dumps(form(f"e{i}", synthetic=True)))
            (forms / "b.json").unlink(); (forms / "a.json").unlink()
            with contextlib.redirect_stdout(io.StringIO()): rc = tool.main(["evaluate", str(forms), "--out", str(d / "ev.json")])
            self.assertEqual(rc, 0); ev = json.loads((d / "ev.json").read_text()); self.assertTrue(ev["aggregate"]["cohorts"][0]["synthetic"])
            appts = d / "appointments.jsonl"; appts.write_text(json.dumps({"kind": "appointment", "appointment_id": "d" * 64, "role": "study-reviewer", "status": "DESIGNATED", "designated": True}) + "\n")
            (d / "adopt.json").write_text(json.dumps({"protocol_id": S.PROTOCOL_ID, "adopted": True, "adopted_by": "owner", "adopted_at": "x", "kit_sha256": "e" * 64, "materials_manifest_sha256": MAN}))
            (d / "app.json").write_text(json.dumps({"determination": "exempt", "reference": "r", "issued_by": "i", "date": "2026-09-20", "protocol_id": S.PROTOCOL_ID})); (d / "rev.json").write_text(json.dumps({"role": "study-reviewer", "appointment_id": "d" * 64}))
            (d / "human.json").write_text(json.dumps([{"session_code": f"e{i}", "reviewer_role": "study-reviewer", "appointment_id": "d" * 64, "decided_at": "x"} for i in range(5)]))
            out = io.StringIO()
            with contextlib.redirect_stdout(out): rc = tool.main(["gate-evidence", str(d / "ev.json"), "--adoption", str(d / "adopt.json"), "--applicability", str(d / "app.json"), "--reviewer", str(d / "rev.json"), "--appointments", str(appts), "--human-records", str(d / "human.json")])
            g = json.loads(out.getvalue()); self.assertEqual(g["gate_input"], "NOT_A_GATE_INPUT"); self.assertTrue(g["missing_prerequisites"][0].startswith("synthetic cohort"))   # synthetic forms never become a gate input, whatever records accompany them
            with contextlib.redirect_stdout(io.StringIO()) as o2: rc = tool.main(["check-docs"])
            self.assertEqual(rc, 0, o2.getvalue())
            with contextlib.redirect_stdout(io.StringIO()): rc = tool.main(["build-packet", str(d / "pk"), "--source", str(REPO), "--mode", "TRANSCRIPT"])
            self.assertEqual(rc, 0); self.assertFalse(any("scoring_key" in str(p) for p in (d / "pk").rglob("*")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
