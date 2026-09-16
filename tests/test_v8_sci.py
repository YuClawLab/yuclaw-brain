"""V8-005 — scientific workbench: the adapted kernel's core cases (from the reference tests, without the old CLI), the
bounded strict input, real replay through the kernel, specific ineligibility reasons, link verification, honest
replay status, protected persistence, and export recomputation in the fresh verifier."""
import copy, hashlib, json, math, pathlib, tempfile, threading, unittest, zipfile
from datetime import datetime, timedelta, timezone

from v3.receipts.contracts import ContractError, canonical_json
from v8.workbench import export, store
from v8.workbench import server as S
from v8.workbench.sci import SCHEMA_VERSION, adapter, kernel_identity
from v8.workbench.sci.contracts import sha256, validate_manifest
from v8.workbench.sci.evidence import inspect_evidence
from v8.workbench.sci.statistics import brier_improvement, by_adjust, log_e_value
from v8.workbench.sci.store import build_events, replay, report
from tests.test_v8_research_notes import _ws
from tests.test_v8_workbench_server import Client

EX = pathlib.Path(S.__file__).resolve().parent / "resources" / "sci"


def h(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def manifest(mode="prospective"):
    return {"schema": SCHEMA_VERSION, "family_id": "extraction-v8", "mode": mode, "family_alpha": .05,
            "claims": [{"claim_id": "source-fidelity", "question": "Does the challenger reduce blinded Brier loss by more than .02?",
                        "population": "new held-out filing questions", "unit_definition": "one source-family audit question",
                        "assumptions": ["Predictions frozen before blind binary adjudication; bounded conditional-mean null."],
                        "metric": "paired_brier_improvement", "baseline_hash": h("baseline"), "candidate_hash": h("candidate"),
                        "alpha": .05, "minimum_effect": .02, "min_units": 20, "max_units": 100}]}


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    def __call__(self):
        return self.now.isoformat()
    def advance(self, seconds=2):
        self.now += timedelta(seconds=seconds)


class Journal:
    """In-memory stand-in for the preview's SQLite journal: the same reducer rules, no database file."""
    def __init__(self, doc, clock):
        self.clock = clock; self.steps = []; self.events = build_events([("register", doc)], self._tick)
    def _tick(self):
        return self.clock()                                                      # the reference journal never advances the clock itself; the tests do
    def append(self, kind, payload):
        state, tip = replay(self.events)
        ev = build_events([("register", self.events[0]["payload"])] + [(e["kind"], e["payload"]) for e in self.events[1:]] + [(kind, payload)], _Replayer(self.events, self._tick))
        self.events = ev; return ev[-1]
    def report(self):
        return report(self.events)


class _Replayer:
    """Clock that re-issues the recorded times of existing events, then a fresh tick for the new one."""
    def __init__(self, events, tick):
        self.times = [e["recorded_at"] for e in events]; self.tick = tick
    def __call__(self):
        return self.times.pop(0) if self.times else self.tick()


def predict(clock, i=0, **kw):
    return dict({"claim_id": "source-fidelity", "unit_id": f"u-{i}", "baseline_probability": .1, "candidate_probability": .9, "source_hashes": [h(i)],
                 "outcome_not_before": (clock.now + timedelta(seconds=1)).isoformat()}, **kw)


def resolve(i=0, **kw):
    return dict({"claim_id": "source-fidelity", "unit_id": f"u-{i}", "outcome": 1, "adjudication_hash": h(f"adjudication-{i}")}, **kw)


def add_unit(j, clock, i, outcome=1):
    j.append("predict", predict(clock, i)); clock.advance(); j.append("resolve", resolve(i, outcome=outcome))


class TestKernelCore(unittest.TestCase):
    """The reference suite's core cases, adapted (no CLI, no SQLite)."""
    def test_numerics(self):
        for bad in (float("nan"), float("inf"), True, ".5", None):
            with self.assertRaises(ValueError):
                brier_improvement(bad, .5, 1)
        for bad in (True, 1.0, -1, 2, "1"):
            with self.assertRaises(ValueError):
                brier_improvement(.5, .5, bad)
        self.assertEqual(brier_improvement(0, 1, 1), 1); self.assertEqual(brier_improvement(0, 1, 0), -1); self.assertEqual(log_e_value(0, 0), 0)
        expected = sum(math.exp(lam * 3 - 5 * lam * lam / 2) for lam in (.0625, .125, .25, .5, 1)) / 5
        self.assertAlmostEqual(math.exp(log_e_value(5, 3)), expected); self.assertTrue(math.isfinite(log_e_value(100000, 100000)))
        n = 16; expectation = sum(math.comb(n, k) * math.exp(log_e_value(n, 2 * k - n)) for k in range(n + 1)) / 2 ** n
        self.assertLessEqual(expectation, 1)                                                           # exact enumeration: the mixture is a supermartingale under the symmetric null
        self.assertEqual([round(x, 12) for x in by_adjust([.01, .04, .03])], [round(x, 12) for x in (.055, .07333333333333333, .07333333333333333)]); self.assertEqual(by_adjust([]), []); self.assertEqual(by_adjust([1, 0, .9]), [1, 0, 1])

    def test_contract_rejections_budget_and_duplicates(self):
        for change in ({"alpha": .051}, {"min_units": 0}, {"max_units": 10}, {"min_units": True}, {"metric": "return"}, {"candidate_hash": "fake"}, {"candidate_hash": h("baseline")}, {"minimum_effect": -1}, {"assumptions": []}, {"unexpected": "silently ignored?"}):
            doc = manifest(); doc["claims"][0].update(change)
            with self.assertRaises(ValueError, msg=str(change)):
                validate_manifest(doc)
        doc = manifest(); doc["claims"].append(dict(doc["claims"][0], claim_id="other"))
        with self.assertRaisesRegex(ValueError, "allocations exceed"):
            validate_manifest(doc)
        doc["claims"][1]["claim_id"] = "source-fidelity"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_manifest(doc)

    def test_ordering_pending_duplicates_and_clock(self):
        clock = Clock(); j = Journal(manifest(), clock); before = j.report()["root_hash"]
        with self.assertRaisesRegex(ValueError, "strictly after"):
            j.append("predict", predict(clock, outcome_not_before=clock()))
        self.assertEqual(j.report()["root_hash"], before)
        j.append("predict", predict(clock))
        with self.assertRaisesRegex(ValueError, "not matured"):
            j.append("resolve", resolve())
        with self.assertRaisesRegex(ValueError, "pending unit"):
            j.append("predict", predict(clock, 1))
        self.assertEqual(j.report()["claims"][0]["status"], "AWAITING_OUTCOME")
        clock.advance(); j.append("resolve", resolve())
        with self.assertRaisesRegex(ValueError, "already resolved"):
            j.append("resolve", resolve())
        with self.assertRaisesRegex(ValueError, "duplicate unit"):
            j.append("predict", predict(clock))
        with self.assertRaisesRegex(ValueError, "reused source"):
            j.append("predict", predict(clock, 1, source_hashes=[h(0)]))
        clock.advance(-100)
        with self.assertRaisesRegex(ValueError, "backwards"):
            j.append("invalidate", {"claim_id": "source-fidelity", "reason": "test"})

    def test_tampering_truncation_and_semantic_replay(self):
        clock = Clock(); j = Journal(manifest(), clock); add_unit(j, clock, 0); exported = j.events; root = j.report()["root_hash"]
        self.assertTrue(report(exported, root)["checkpoint_matches"])
        bad = copy.deepcopy(exported); bad[-1]["payload"]["outcome"] = 0
        with self.assertRaisesRegex(ValueError, "integrity"):
            replay(bad)
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            replay(exported[:-1], root)
        bad = copy.deepcopy(exported); bad[-1]["payload"]["outcome"] = 7; bad[-1]["event_hash"] = sha256({k: v for k, v in bad[-1].items() if k != "event_hash"})
        with self.assertRaisesRegex(ValueError, "outcome"):
            replay(bad)

    def test_statuses_crossing_invalidation_budget_exploratory_minimum(self):
        clock = Clock(); j = Journal(manifest(), clock)
        for i in range(30):
            add_unit(j, clock, i)
        c = j.report()["claims"][0]; self.assertTrue(c["threshold_crossed"]); self.assertEqual(c["status"], "CONDITIONAL_EVIDENCE"); self.assertEqual(c["permission"], "RESEARCH_REVIEW_ONLY"); self.assertLessEqual(c["anytime_p_bound"], .05)
        j.append("invalidate", {"claim_id": "source-fidelity", "reason": "Blinded adjudication failed"}); self.assertEqual(j.report()["claims"][0]["status"], "INVALIDATED")
        with self.assertRaisesRegex(ValueError, "invalidated"):
            j.append("predict", predict(clock, 40))
        doc = manifest(); doc["claims"][0].update(min_units=2, max_units=2); clock = Clock(); j = Journal(doc, clock)
        for i in range(2):
            add_unit(j, clock, i, outcome=0)
        self.assertEqual(j.report()["claims"][0]["status"], "BUDGET_EXHAUSTED_INCONCLUSIVE")
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            j.append("predict", predict(clock, 2))
        clock = Clock(); j = Journal(manifest("exploratory"), clock)
        for i in range(30):
            add_unit(j, clock, i)
        self.assertTrue(j.report()["claims"][0]["threshold_crossed"]); self.assertEqual(j.report()["claims"][0]["status"], "EXPLORATORY_ONLY")
        doc = manifest(); doc["claims"][0]["min_units"] = 50; clock = Clock(); j = Journal(doc, clock)
        for i in range(30):
            add_unit(j, clock, i)
        self.assertEqual(j.report()["claims"][0]["status"], "ACCUMULATING")
        self.assertEqual(report(build_events([("register", manifest())], Clock()))["claims"][0]["status"], "ACCUMULATING")

    def test_evidence_inspection_adapted_to_workspace_sources(self):
        obj = {"accession": "0000000000-26-000001", "source_hash": h("source"), "available_as_of": "2026-09-10T08:00:00+08:00"}
        r = inspect_evidence([obj, dict(obj), dict(obj, available_as_of="2026-09-11T00:00:00Z"), dict(obj, available_as_of="2026-09-09")], "2026-09-10T00:00:00Z")
        self.assertEqual(len(r["eligible_sources"]), 1); self.assertEqual(r["distinct_filings"], 1); self.assertEqual({x["reason"] for x in r["excluded"]}, {"duplicate_source", "not_available_as_of", "missing_or_ambiguous_availability"}); self.assertEqual(r["statistical_status"], "NOT_TESTED")
        self.assertEqual(inspect_evidence([{"available_as_of": "2026-09-10T00:00:00Z", "source_hash": [], "accession": []}], "2026-09-10T00:00:00Z")["excluded"][0]["reason"], "missing_source_identity")

    def test_kernel_identity_is_stable_and_bound_to_module_bytes(self):
        k1, k2 = kernel_identity(), kernel_identity(); self.assertEqual(k1, k2); self.assertEqual(len(k1["kernel_sha256"]), 64); self.assertEqual(set(k1["modules"]), {"contracts.py", "statistics.py", "store.py"})


class TestAdapter(unittest.TestCase):
    def test_strict_bounded_input(self):
        for raw, msg in ((b"", "empty"), (b"[]", "non-empty"), (b'{"events":[{}],"exec":"x"}', "unsupported envelope"), (b'{"events":[{}],"events":[{}]}', "duplicate JSON field"), (b'{"events":[{"a":NaN}]}', "non-finite"), (b'{"events":[1]}', "every event must be an object"),
                         (b'{"events":[{}],"expected_root":"zz"}', "expected_root"), (b'{"events":[{}],"links":{"path":"/etc/passwd"}}', "links"), (b'{"events":[{}],"declared":{"retrospective":"yes"}}', "declared"), (b"x" * (adapter.MAX_INPUT_BYTES + 1), "exceeds"), (b"[" + b"{}," * 2001 + b"{}]", "more than")):
            with self.assertRaisesRegex(adapter.InputError, msg):
                adapter.parse_input(raw)
        env = adapter.parse_input((EX / "example_exploratory_journal.json").read_bytes()); self.assertEqual(len(env["events"]), 61); self.assertEqual(adapter.input_identity(env)["events"], 61)
        deep = b'{"events":[' + b'{"payload":' * 20 + b"{}" + b"}" * 20 + b"]}"
        with self.assertRaisesRegex(adapter.InputError, "nesting"):
            adapter.parse_input(deep)

    def test_kernel_run_specific_reasons_and_supported_examples(self):
        want = {"example_exploratory_journal": ("EXPLORATORY_REPLAY", [], "EXPLORATORY_ONLY"), "example_prospective_pending_journal": ("SUPPORTED_REPLAY", [], "AWAITING_OUTCOME"),
                "refused_monetary_probabilities": ("INELIGIBLE", ["MONETARY_OR_OUT_OF_RANGE_PROBABILITY"], None), "refused_unsupported_metric": ("INELIGIBLE", ["UNSUPPORTED_METRIC"], None), "refused_missing_prediction_pair": ("INELIGIBLE", ["MISSING_PREDICTION_PAIR"], None)}
        for name, (status, codes, cstatus) in want.items():
            k = adapter.kernel_run(adapter.parse_input((EX / f"{name}.json").read_bytes()))
            self.assertEqual(k["status"], status, name); self.assertEqual([r["code"] for r in k["reasons"]], codes, name)
            if cstatus:
                self.assertEqual(k["report"]["claims"][0]["status"], cstatus)
        env = adapter.parse_input((EX / "example_exploratory_journal.json").read_bytes()); bad = copy.deepcopy(env); bad["events"][5]["payload"]["outcome"] = 0
        k = adapter.kernel_run(bad); self.assertEqual(k["status"], "INELIGIBLE"); self.assertEqual(k["reasons"][0]["code"], "INTEGRITY_FAILURE")
        bad = copy.deepcopy(env); bad["expected_root"] = "0" * 64; self.assertEqual(adapter.kernel_run(bad)["reasons"][0]["code"], "CHECKPOINT_MISMATCH")
        bad = copy.deepcopy(env); bad["events"][1]["payload"]["claim_id"] = "other-target"; bad["events"][1]["event_hash"] = sha256({k: v for k, v in bad["events"][1].items() if k != "event_hash"})
        self.assertEqual(adapter.kernel_run(bad)["reasons"][0]["code"], "CHANGED_TARGET")                                 # a rewritten target with a consistent hash is caught by the reducer (unknown claim) before the next event's chain check
        pro = json.loads((EX / "example_prospective_pending_journal.json").read_text()); env2 = adapter.parse_input(json.dumps({"events": pro["events"] + [{"sequence": 7, "kind": "predict", "payload": {"claim_id": "source-fidelity", "unit_id": "u-x", "baseline_probability": .5, "candidate_probability": .5, "source_hashes": [h("z")], "outcome_not_before": "2027-01-01T00:00:00+00:00", "reviewer": "a human"}, "recorded_at": "2026-02-01T00:10:00+00:00", "previous_hash": pro["events"][-1]["event_hash"], "event_hash": "0" * 64}]}))
        self.assertIn("UNSUPPORTED_ADJUDICATION_CLAIM", [r["code"] for r in adapter.kernel_run(env2)["reasons"]])
        money = json.loads((EX / "refused_monetary_probabilities.json").read_text()); money["events"][1]["payload"]["range"] = {"low": 1, "high": 2}
        self.assertIn("MONETARY_RANGE_SUPPLIED", [r["code"] for r in adapter.kernel_run(adapter.parse_input(json.dumps(money)))["reasons"]])

    def test_links_and_replay_status_against_workspace(self):
        ws, cid = _ws("001_base"); st = ws.claim_state(cid)
        env = adapter.parse_input((EX / "example_prospective_pending_journal.json").read_bytes()); env["links"] = {"claim_id": cid, "version_digest": st["versions"][0]["claim"]["_digest"], "source_hashes": [st["versions"][0]["claim"]["source"]["source_hash"], "f" * 64]}
        r = adapter.classify(env, ws)
        self.assertEqual(r["status"], "SUPPORTED_REPLAY"); self.assertEqual(r["replay_status"], "PROSPECTIVE_CLAIMED_NOT_VERIFIED"); self.assertEqual(r["links"]["claim"]["result"], "VERIFIED_EXISTS")
        self.assertEqual(r["links"]["version"]["result"], "TARGET_CHANGED"); self.assertEqual(r["links"]["version"]["version_id"], "V1")                        # V1 was superseded by R1: the target changed
        self.assertEqual([x["result"] for x in r["links"]["sources"]], ["VERIFIED_BYTES", "NOT_FOUND"]); self.assertTrue(any("not units of this study" in n for n in r["links"]["notes"]))
        env["links"]["version_digest"] = st["current"]["claim"]["_digest"]; self.assertEqual(adapter.classify(env, ws)["links"]["version"]["result"], "VERIFIED_BYTES")
        env["links"] = {"claim_id": "NOPE-1"}; self.assertEqual(adapter.classify(env, ws)["links"]["claim"]["result"], "NOT_FOUND")
        env = adapter.parse_input((EX / "example_exploratory_journal.json").read_bytes()); env["declared"] = {"retrospective": True}
        r = adapter.classify(env, ws); self.assertEqual(r["replay_status"], "RETROSPECTIVE_REPLAY"); self.assertTrue(any("not prospective evidence" in w for w in r["warnings"]))
        self.assertEqual(adapter.classify(adapter.parse_input((EX / "example_exploratory_journal.json").read_bytes()), ws)["replay_status"], "EXPLORATORY_REPLAY")


class TestPersistenceAndExport(unittest.TestCase):
    def test_record_retry_safety_and_export_recompute(self):
        ws, cid = _ws("001_base"); env = adapter.parse_input((EX / "example_exploratory_journal.json").read_bytes()); env["links"] = {"claim_id": cid}
        res = adapter.classify(env, ws); ident = adapter.input_identity(env)
        payload = {"input": env, **ident, "status": res["status"], "replay_status": res["replay_status"], "reasons": res["reasons"], "report": res["report"], "report_digest": res["report_digest"], "root_hash": res["root_hash"], "links": res["links"], "warnings": res["warnings"], "kernel": res["kernel"], "standing": res["standing"], "actor": "test", "actor_kind": "simulated_test_action", "label": None}
        e1, d1 = ws.record_sci(payload, claim_id=cid, op_id="op:sci-0001"); e2, d2 = ws.record_sci(payload, claim_id=cid, op_id="op:sci-0001")
        self.assertEqual((d1, d2), (False, True)); self.assertEqual(e1["payload"]["sci_id"], "S1"); self.assertEqual(len(ws.sci_records("*")), 1)
        with self.assertRaises(store.StoreIntegrityError):
            ws.record_sci(dict(payload, actor="other"), claim_id=cid, op_id="op:sci-0001")
        with self.assertRaises(ContractError):
            ws.record_sci(payload, claim_id="NOPE-1", op_id="op:sci-0002")
        digests = [v["claim"]["_digest"] for v in ws.claim_state(cid)["versions"]]
        st = ws.claim_state(cid); self.assertEqual(len(st["sci"]), 1); self.assertEqual([v["claim"]["_digest"] for v in st["versions"]], digests)
        e = export.build_export(ws, cid)
        with zipfile.ZipFile(e["zip_path"]) as z:
            m = {i.filename: z.read(i) for i in z.infolist()}
        can = json.loads(m["canonical.json"]); self.assertEqual(can["sci"][0]["sci_id"], "S1"); self.assertEqual(can["sci"][0]["report"]["claims"][0]["status"], "EXPLORATORY_ONLY")
        v = export.verify_export(e["zip_path"]); self.assertEqual(v["result"], "SUCCESS"); self.assertTrue(any(c["check"] == "recompute-sci" and c["ok"] for c in v["checks"]))
        # semantic tamper inside the packed scientific input (an outcome flipped): the kernel's chain check fails on recompute
        can2 = copy.deepcopy(can); can2["sci"][0]["input"]["events"][5]["payload"]["outcome"] = 0; cb = canonical_json(can2)
        man = json.loads(m["EXPORT_MANIFEST.json"]); man["canonical_digest"] = hashlib.sha256(cb).hexdigest(); man["files"][0].update(sha256=man["canonical_digest"], size_bytes=len(cb))
        p = pathlib.Path(e["zip_path"]).with_name("sci_tampered.zip")
        with zipfile.ZipFile(p, "w") as z:
            for k, val in dict(m, **{"canonical.json": cb, "EXPORT_MANIFEST.json": json.dumps(man).encode()}).items():
                z.writestr(k, val)
        v2 = export.verify_export(p); self.assertEqual(v2["result"], "MISMATCH"); self.assertIn("scientific record S1", v2["first_discrepancy"])
        # numerical tamper of the packed report (mean improvement edited) with a consistent event chain: recompute differs
        can3 = copy.deepcopy(can); can3["sci"][0]["report"]["claims"][0]["mean_brier_improvement"] = 0.99; cb = canonical_json(can3)
        man = json.loads(m["EXPORT_MANIFEST.json"]); man["canonical_digest"] = hashlib.sha256(cb).hexdigest(); man["files"][0].update(sha256=man["canonical_digest"], size_bytes=len(cb))
        p3 = pathlib.Path(e["zip_path"]).with_name("sci_report_tampered.zip")
        with zipfile.ZipFile(p3, "w") as z:
            for k, val in dict(m, **{"canonical.json": cb, "EXPORT_MANIFEST.json": json.dumps(man).encode()}).items():
                z.writestr(k, val)
        self.assertEqual(export.verify_export(p3)["result"], "MISMATCH")
        d = export.build_dataset_export(ws); vd = export.verify_export(d["zip_path"]); self.assertEqual(vd["result"], "SUCCESS"); self.assertTrue(any(c["check"] == "recompute-sci" for c in vd["checks"]))
        old = {k: val for k, val in can.items() if k not in ("sci",)}; ob = canonical_json(old)                            # a pre-SCI export stays verifiable and is reported as such
        man = json.loads(m["EXPORT_MANIFEST.json"]); man["canonical_digest"] = hashlib.sha256(ob).hexdigest(); man["files"][0].update(sha256=man["canonical_digest"], size_bytes=len(ob))
        old["events"] = [x for x in old["events"] if x["kind"] != "SCI_REPLAY_RECORDED"]; ob = canonical_json(old); man["canonical_digest"] = hashlib.sha256(ob).hexdigest(); man["files"][0].update(sha256=man["canonical_digest"], size_bytes=len(ob))
        p4 = pathlib.Path(e["zip_path"]).with_name("pre_sci.zip")
        with zipfile.ZipFile(p4, "w") as z:
            for k, val in dict(m, **{"canonical.json": ob, "EXPORT_MANIFEST.json": json.dumps(man).encode()}).items():
                z.writestr(k, val)
        v4 = export.verify_export(p4); self.assertEqual(v4["result"], "SUCCESS"); self.assertTrue(any(c["check"] == "recompute-sci" and c["ok"] is None for c in v4["checks"]))


class TestSciServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-sci-srv-")); cls.A = S.WorkbenchServer(cls.tmp / "A", 0, candidate_commit="cand")
        threading.Thread(target=cls.A.serve_forever, daemon=True).start(); S.Handler.log_message = lambda *a, **k: None

    @classmethod
    def tearDownClass(cls):
        cls.A.shutdown()

    def test_protected_replay_examples_refusals_and_inert_rendering(self):
        a = Client(self.A.server_address[1]); st, _, page = a.req("GET", "/sci"); self.assertEqual(st, 200); self.assertIn(b"no scientific record yet", page); self.assertIn(b"kernel identity", page)
        st, _, body = a.req("POST", "/sci/replay", "csrf=x&op_id=ui:nullorig02&example=example_exploratory_journal&actor=a", {"Content-Type": "application/x-www-form-urlencoded", "Origin": "null"})
        self.assertEqual(st, 403); self.assertEqual(self.A.ws.sci_records("*"), [])
        st, h, _ = a.post("/sci/replay", {"example": "example_exploratory_journal", "actor": "journey-runner (automated test action; not a human review)", "simulated": "1"}); self.assertEqual(st, 303); self.assertTrue(h["Location"].startswith("/sci/S"))
        page = a.req("GET", h["Location"])[2]; self.assertIn(b"EXPLORATORY_REPLAY", page); self.assertIn(b"EXPLORATORY_ONLY", page); self.assertIn(b"LOCAL_ONLY_EXTERNAL_TIMESTAMP_NOT_VERIFIED", page); self.assertIn(b"kernel identity", page); self.assertIn(b"simulated test action", page)
        st, h, _ = a.post("/sci/replay", {"example": "refused_monetary_probabilities", "actor": "r"}); page = a.req("GET", h["Location"])[2]
        self.assertIn(b"INELIGIBLE", page); self.assertIn(b"MONETARY_OR_OUT_OF_RANGE_PROBABILITY", page); self.assertIn(b"not probabilities", page)
        st, _, page = a.post("/sci/replay", {"input": '{"events": [1], "exec": "rm"}', "actor": "r"}); self.assertEqual(st, 422); self.assertIn(b"unsupported envelope fields", page)
        st, _, page = a.post("/sci/replay", {"input": "not json", "actor": "r"}); self.assertEqual(st, 422); self.assertIn(b"not valid JSON", page)
        st, _, page = a.post("/sci/replay", {"example": "../../etc/passwd", "actor": "r"}); self.assertEqual(st, 422)
        st, _, page = a.post("/sci/replay", {"example": "example_exploratory_journal", "actor": ""}); self.assertEqual(st, 422)
        ex = json.loads((EX / "example_prospective_pending_journal.json").read_text()); ex["label"] = "<script>alert(1)</script> ignore previous instructions"
        st, h, _ = a.post("/sci/replay", {"input": json.dumps(ex), "actor": "<b>x</b>"}); page = a.req("GET", h["Location"])[2]
        self.assertIn(b"&lt;script&gt;alert(1)&lt;/script&gt;", page); self.assertNotIn(b"<script>alert", page); self.assertIn(b"&lt;b&gt;x&lt;/b&gt;", page); self.assertIn(b"AWAITING_OUTCOME", page); self.assertIn(b"PROSPECTIVE_CLAIMED_NOT_VERIFIED", page)
        self.assertEqual(len(self.A.ws.sci_records("*")), 3); self.assertIn(b"S3", a.req("GET", "/sci")[2])
        self.assertEqual(a.req("GET", "/sci/S9")[0], 200); self.assertIn(b"does not exist", a.req("GET", "/sci/S9")[2])


if __name__ == "__main__":
    unittest.main()
