"""V8-015 §2 — subclauses of the 43 R2 acceptance families that the V8-014 tests did not exercise. Each refusal has an
authorized positive counterpart; isolation cases run the REAL restricted worker (never mocked away). Automated fixtures only."""
import io, json, os, pathlib, stat, sys, tempfile, threading, unittest, zipfile
from datetime import timedelta
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from v8_mod_helpers import Client, Server, bundle, load_fixture, principal, workspace     # noqa: E402
from v8.workbench import schema, store                                                      # noqa: E402
from v8.workbench.modules import authz, commons as com, core, evolution as evo, modexport as mx, practice as prc, sandbox, shield, shield_worker as W   # noqa: E402
from v8.workbench.modules.core import ModuleError                                          # noqa: E402

FUTURE = (core.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
CAP = sandbox.capability()
FIX = pathlib.Path(__file__).resolve().parents[1] / "v8" / "workbench" / "resources" / "fixtures"


def code(fn, *a, **k):
    try:
        fn(*a, **k)
    except ModuleError as exc:
        return exc.code
    return "NO_ERROR"


class Boundaries(unittest.TestCase):
    def test_X03_a_session_of_one_server_is_nothing_to_another_and_decisions_are_object_scoped(self):
        wa, wb = workspace("a"), workspace("b"); creds = {}
        for w in (wa, wb):
            adm, creds[(w, "owner")] = principal(w, "owner", ["admin"]); _, creds[(w, "alice")] = principal(w, "alice", ["submit"], by=adm); _, creds[(w, "bob")] = principal(w, "bob", ["submit"], by=adm); _, creds[(w, "rita")] = principal(w, "rita", ["review"], by=adm)
        sa, sb = Server(wa.root), Server(wb.root); self.addCleanup(sa.close); self.addCleanup(sb.close)
        ca = Client(sa); self.assertEqual(ca.login("alice", creds[(wa, "alice")])[0], 200); thief = Client(sb); thief.cookies["wb_auth"] = ca.cookies["wb_auth"]
        self.assertEqual(thief._req("GET", "/shd")[0], 303)                                                                     # workspace A's session id is unknown to workspace B's server
        self.assertEqual(Client(sb).login("alice", creds[(wa, "alice")])[0], 403)                                               # … and so is workspace A's credential
        data, _, _ = bundle(); st, body, _ = ca.upload("/shd/submit", {"title": "alice-bundle-title"}, {"bundle": ("b.zip", data)}, page="/shd"); self.assertIn("SB1", body)
        st, body, loc = ca.post("/shd/admit", {"submission_id": "SB1"}, page="/shd"); did = loc.rsplit("/", 1)[1]; self.assertEqual(st, 200)
        cb = Client(sa); cb.login("bob", creds[(wa, "bob")]); self.assertEqual(cb.get(f"/shd/decision/{did}")[0], 404); self.assertNotIn("alice-bundle-title", cb.get("/shd")[1])     # another submitter: not found, not listed
        st, body, _ = cb.post("/shd/admit", {"submission_id": "SB1"}, page="/shd"); self.assertEqual(st, 403)                       # … and cannot request a decision on it
        cr = Client(sa); cr.login("rita", creds[(wa, "rita")]); self.assertEqual(cr.get(f"/shd/decision/{did}")[0], 200); self.assertIn("alice-bundle-title", cr.get("/shd")[1])      # POSITIVE: a reviewer may

    def test_X05_a_crash_between_the_private_write_and_the_committing_event_commits_nothing(self):
        ws = workspace(); cid, sid = load_fixture(ws); adm, _ = principal(ws, "owner", ["admin"]); cur, _ = principal(ws, "curator", ["review"], by=adm); pat, _ = principal(ws, "pat", ["practice"], by=adm)
        com.set_budget(ws, adm, period_id="p1", review_minutes=60, practice_minutes=60, contributor_packet_cap=5, max_open_tasks=5, op_id="op:budget-001")
        t = prc.freeze_task(ws, cur, title="t", question="q?", claim_id=cid, source_ids=[sid], labels=["A", "B"], reference_label="A", reference_answer="REF", rationale="", provenance="MODEL_ANSWER", declared_curator_qualification="",
                            public_example=True, session_minutes=20, evo_version_id=None, op_id="op:task-00001")["payload"]
        ss = prc.open_session(ws, pat, task_id=t["task_id"], assistance="NONE", assistance_note="", prior_exposure="NOT_SEEN", op_id="op:sess-00001")["payload"]["session_id"]; real = store.Workspace._append_unlocked

        def crash(self_, kind, *a, **k):
            if kind == "PRC_ATTEMPT_COMMITTED":
                raise OSError("simulated crash after the vault write, before the journal append")
            return real(self_, kind, *a, **k)
        kw = dict(judgment="A", reasoning="because", source_refs=[sid], unresolved_note="", op_id="op:attempt-001")
        with mock.patch.object(store.Workspace, "_append_unlocked", crash):
            with self.assertRaises(OSError):
                prc.commit_attempt(ws, pat, ss, **kw)
        self.assertIsNone(prc.state(ws)["sessions"][ss]["attempt"]); self.assertEqual(code(prc.reveal, ws, pat, ss), "E_ATTEMPT_FIRST")          # nothing committed: the comparison stays closed
        prc.commit_attempt(ws, pat, ss, **kw); self.assertEqual(sum(1 for e in ws.load()["events"] if e["kind"] == "PRC_ATTEMPT_COMMITTED"), 1)  # the retry commits exactly once
        self.assertEqual(prc.reveal(ws, pat, ss)["reference_answer"], "REF")
        P = authz.Principals(ws)

        def crash2(self_, kind, *a, **k):
            if kind == "PRINCIPAL_ENROLLED":
                raise OSError("simulated crash")
            return real(self_, kind, *a, **k)
        with mock.patch.object(store.Workspace, "_append_unlocked", crash2):
            with self.assertRaises(OSError):
                P.enroll("ghost", ["admin"], op_id="op:enroll-ghost", by=adm)
        self.assertIn("ghost", json.loads(P.path.read_text())); self.assertNotIn("ghost", P.state()); self.assertIsNone(P.active("ghost"))         # a hash without its journal event authorizes nobody
        _, cred = P.enroll("ghost", ["submit"], op_id="op:enroll-ghost", by=adm); self.assertEqual(P.authenticate("ghost", cred)["caps"], ["submit"])

    def test_S01_a_copied_approval_is_useless_in_another_workspace_even_when_its_root_is_trusted_there(self):
        wa, wb = workspace("a"), workspace("b"); aa, _ = principal(wa, "owner", ["admin"]); ab, _ = principal(wb, "owner", ["admin"]); sub, _ = principal(wb, "alice", ["submit"], by=ab)
        shield.enroll_root(wa, aa, label="A", op_id="op:root-000001"); data, h, srcs = bundle()
        env = shield.issue_approval(wa, aa, bundle_sha256=h, source_sha256s=srcs, purpose="evidence.reference", expires_at=FUTURE, op_id="op:apr-0000001")["payload"]["envelope"]
        shield.enroll_root(wb, ab, label="A's key, enrolled by B's administrator", public_key=env["signer"]["public_key"], op_id="op:root-000002")
        with wb._locked():                                                                                                          # the copied record lands in B's journal (as a careless administrator's import would)
            wb._append_unlocked("SHD_APPROVAL_ISSUED", None, {"approval_id": env["body"]["approval_id"], "envelope": env}, op_id="op:copied-00001", observed_at=None, source_available_as_of=None, actor="principal:owner")
        sid = shield.submit(wb, sub, data, title="copy", op_id="op:sub-0000001")["payload"]["submission_id"]
        self.assertEqual(shield.admit(wb, sub, sid, op_id="op:adm-0000001")["payload"]["code"], "REFUSED_WORKSPACE_MISMATCH")          # signature valid, root trusted — still bound to workspace A
        shield.issue_approval(wb, ab, bundle_sha256=h, source_sha256s=srcs, purpose="evidence.reference", expires_at=FUTURE, op_id="op:apr-0000002") if False else None
        self.assertEqual(code(shield.issue_approval, wb, ab, bundle_sha256=h, source_sha256s=srcs, purpose="evidence.reference", expires_at=FUTURE, op_id="op:apr-0000003"), "E_NO_SIGNING_KEY")   # B holds no private key for that root
        shield.enroll_root(wb, ab, label="B's own", op_id="op:root-000003"); shield.issue_approval(wb, ab, bundle_sha256=h, source_sha256s=srcs, purpose="evidence.reference", expires_at=FUTURE, op_id="op:apr-0000004")
        self.assertEqual(shield.admit(wb, sub, sid, op_id="op:adm-0000002")["payload"]["result"], "ADMITTED")                        # POSITIVE: B's own approval

    def test_S03_hostile_archives_are_rejected_at_the_INTEGRATED_route_by_the_real_worker(self):
        self.assertIsNotNone(CAP["backend"], CAP["closed_reason"]); ws = workspace(); adm, _ = principal(ws, "owner", ["admin"]); sub, _ = principal(ws, "alice", ["submit"], by=adm); shield.enroll_root(ws, adm, label="r", op_id="op:root-000001")
        ok = json.dumps({"schema": W.BUNDLE_SCHEMA, "purpose": "evidence.reference", "evidence": [], "payload": {}})

        def z(members, comp=zipfile.ZIP_STORED):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", comp) as zf:
                for name, body, attr in members:
                    zi = zipfile.ZipInfo(name); zi.external_attr = attr; zi.compress_type = comp; zf.writestr(zi, body)
            return buf.getvalue()
        cases = {"ARCHIVE_MEMBER_NAME_REJECTED": z([("bundle.json", ok, 0o600 << 16), ("../../escape.txt", b"x", 0o600 << 16)]), "ARCHIVE_LINK_OR_SPECIAL_MEMBER": z([("bundle.json", ok, 0o600 << 16), ("evidence/l", b"/etc/passwd", (stat.S_IFLNK | 0o777) << 16)]),
                 "ARCHIVE_RATIO_REJECTED": z([("bundle.json", ok, 0o600 << 16), ("evidence/bomb", b"\0" * (3 << 20), 0o600 << 16)], zipfile.ZIP_DEFLATED), "MANIFEST_DUPLICATE_KEY": bundle(raw_manifest='{"schema":"a","schema":"b"}')[0],
                 "MANIFEST_TOO_DEEP": bundle(raw_manifest="[" * 40 + "]" * 40)[0], "ARCHIVE_INVALID": b"PK\x03\x04 not really a zip"}
        for i, (expect, data) in enumerate(cases.items()):
            import hashlib
            h = hashlib.sha256(data).hexdigest(); sid = shield.submit(ws, sub, data, title=expect, op_id=f"op:sub-hostile{i}")["payload"]["submission_id"]
            shield.issue_approval(ws, adm, bundle_sha256=h, source_sha256s=[], purpose="evidence.reference", expires_at=FUTURE, op_id=f"op:apr-hostile{i}")      # approved, so the worker really opens it
            d = shield.admit(ws, sub, sid, op_id=f"op:adm-hostile{i}")["payload"]; self.assertEqual((d["code"], d["detail"], d["typed_result_sha256"]), ("REFUSED_BUNDLE_REJECTED", expect, None), expect); self.assertEqual(d["isolation"]["backend"], CAP["backend"])

    def test_S07_the_error_channel_is_bounded_too(self):
        self.assertIsNotNone(CAP["backend"]); d = pathlib.Path(tempfile.mkdtemp()); wk = d / "noisy_worker.py"; wk.write_text("import sys\nwhile True:\n    sys.stderr.write('e' * 65536)\n"); inp = d / "in"; inp.write_bytes(b"x")
        r = sandbox._run(CAP["backend"], "verify", inp, worker=wk, wall=20); self.assertEqual(r["status"], "OUTPUT_LIMIT_EXCEEDED"); self.assertLessEqual(len(r["stderr"]), sandbox.MAX_STDERR); self.assertNotEqual(r["rc"], 0)


class EvoComPrc(unittest.TestCase):
    def test_E03_E06_exposure_survives_principal_revocation_and_relabelling_and_requests_show_fulfilment(self):
        ws = workspace(); adm, _ = principal(ws, "owner", ["admin"]); imp, _ = principal(ws, "improver", ["submit"], by=adm); rev, _ = principal(ws, "grader", ["review"], by=adm); root = pathlib.Path(tempfile.mkdtemp())
        for d in ("policy", "grader", "evaldata"):
            (root / d).mkdir()
        (root / "policy" / "p.json").write_text(json.dumps({"tools": {"read_filing": "allow"}, "default": "deny"})); (root / "grader" / "g.json").write_text(json.dumps({"required_allow": ["read_filing"]})); (root / "evaldata" / "c.json").write_text(json.dumps({"cases": []}))
        cfg = {"roots": [str(root)], "components": {"tool_policy": {"mode": "path", "path": str(root / "policy")}, "grader": {"mode": "path", "path": str(root / "grader")}, "evaluation_data": {"mode": "path", "path": str(root / "evaldata")}, "runtime": {"mode": "runtime"}},
               "protocols": {"tool-safety": {"scope": ["tool_policy"], "job": "policy_conformance"}}}
        evo.set_config(ws, adm, cfg, op_id="op:evo-config1"); evo.register_version(ws, imp, version_id="v1", parent_version_id=None, label="first name", op_id="op:evo-reg-v1")
        evo.record_test_access(ws, adm, subject_principal="improver", action="GRANTED", op_id="op:evo-acc-0001"); authz.Principals(ws).revoke("improver", "left the team", op_id="op:revoke-imp01", by=adm)                  # the CREDENTIAL is revoked …
        imp2, _ = principal(ws, "improver2", ["submit"], by=adm); evo.register_version(ws, imp2, version_id="v2-renamed", parent_version_id="v1", label="a new label", op_id="op:evo-reg-v2")
        a = evo.audit(ws, "v2-renamed"); self.assertEqual(a["test_exposure"], ["improver"]); self.assertTrue(any("TEST_EXPOSURE" in g for g in a["gaps"]))                                                          # … the exposure on the lineage is not
        rq = evo.request_reevaluation(ws, imp2, version_id="v2-renamed", protocol_id="tool-safety", reason="after the change", op_id="op:evo-req-0001")["payload"]; self.assertEqual(rq["job"], "policy_conformance")
        srv = Server(ws.root); self.addCleanup(srv.close); _, c = authz.Principals(ws).rotate("owner", op_id="op:rotate-own1", by=None); cl = Client(srv); cl.login("owner", c); self.assertIn("OPEN —", cl.get("/evo")[1])
        __import__("time").sleep(1.1); evo.run_evaluation(ws, rev, version_id="v2-renamed", protocol_id="tool-safety", op_id="op:evo-run-0001"); self.assertIn("FULFILLED by EV1 (PASS)", cl.get("/evo")[1])
        self.assertEqual(code(evo.request_reevaluation, ws, imp2, version_id="v2-renamed", protocol_id="no-such-protocol", reason="x", op_id="op:evo-req-0002"), "E_UNKNOWN")

    def test_C04_concurrent_admission_at_the_cap_boundary_admits_exactly_the_cap(self):
        ws = workspace(); cid, _ = load_fixture(ws); adm, _ = principal(ws, "owner", ["admin"]); sub, _ = principal(ws, "alice", ["submit"], by=adm)
        com.set_budget(ws, adm, period_id="p1", review_minutes=60, practice_minutes=0, contributor_packet_cap=3, max_open_tasks=5, op_id="op:budget-001"); out = []

        def go(i):
            out.append(code(com.submit_direct, ws, sub, claim_id=cid, kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=5, asserts_withdrawn=False, client_packet_id=f"renamed-{i}", op_id=f"op:pk-race-{i:03d}"))
        ts = [threading.Thread(target=go, args=(i,)) for i in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(sorted(out), ["E_CONTRIBUTOR_CAP"] * 5 + ["NO_ERROR"] * 3); self.assertEqual(len(com.state(ws)["packets"]), 3)

    def test_P07_a_claim_amendment_and_an_EVO_successor_annotate_the_session_without_rewriting_it(self):
        ws = workspace(); fx = json.loads((FIX / "001_base.json").read_text()); rec = schema.from_fixture(fx); s0 = rec["claim"]["source"]; ws.register_source(s0, op_id="op:src-0001", observed_at=s0["available_as_of"]); ws.freeze_claim(rec["claim"], op_id="op:frz-0001", observed_at=s0["available_as_of"])
        from v8.workbench import availability
        cid, sid = rec["claim"]["claim_id"], availability.source_id(s0); adm, _ = principal(ws, "owner", ["admin"]); cur, _ = principal(ws, "curator", ["review"], by=adm); pat, _ = principal(ws, "pat", ["practice"], by=adm); imp, _ = principal(ws, "imp", ["submit"], by=adm)
        com.set_budget(ws, adm, period_id="p1", review_minutes=60, practice_minutes=60, contributor_packet_cap=5, max_open_tasks=5, op_id="op:budget-001"); root = pathlib.Path(tempfile.mkdtemp()); (root / "m").mkdir(); (root / "m" / "x.json").write_text("{}")
        evo.set_config(ws, adm, {"roots": [str(root)], "components": {"memory": {"mode": "path", "path": str(root / "m")}}, "protocols": {}}, op_id="op:evo-config1"); evo.register_version(ws, imp, version_id="v1", parent_version_id=None, label="", op_id="op:evo-reg-v1")
        t = prc.freeze_task(ws, cur, title="t", question="q?", claim_id=cid, source_ids=[sid], labels=["A", "B"], reference_label="A", reference_answer="REF", rationale="", provenance="MODEL_ANSWER", declared_curator_qualification="", public_example=True,
                            session_minutes=20, evo_version_id="v1", op_id="op:task-00001")["payload"]
        ss = prc.open_session(ws, pat, task_id=t["task_id"], assistance="NONE", assistance_note="", prior_exposure="NOT_SEEN", op_id="op:sess-00001")["payload"]["session_id"]
        prc.commit_attempt(ws, pat, ss, judgment="A", reasoning="original reasoning", source_refs=[sid], unresolved_note="", op_id="op:attempt-001"); before = prc.session_view(ws, pat, ss)["attempt"]; __import__("time").sleep(1.1)
        r = rec["revisions"][0]; ws.register_source(r["source"], op_id="op:src-rev001", observed_at=r["source"]["available_as_of"]); ws.amend_claim(cid, r["type"], changes={"range": r["claim"]["range"]}, reason="per fixture", source=r["source"], op_id="op:amend-00001", observed_at=r["source"]["available_as_of"])
        (root / "m" / "x.json").write_text('{"changed": 1}'); evo.register_version(ws, imp, version_id="v2", parent_version_id="v1", label="", op_id="op:evo-reg-v2"); v = prc.session_view(ws, pat, ss)
        notes = " | ".join(v["current_interpretation"]); self.assertIn("CLAIM_REVISED", notes); self.assertIn("EVO: version v2 succeeded v1", notes); self.assertEqual(v["attempt"], before)
        self.assertEqual(prc.state(ws)["tasks"][t["task_id"]]["claim"]["version_digest"], t["claim"]["version_digest"])                  # the frozen task still names the version it was frozen on

    def test_P02_a_practitioner_with_other_capabilities_is_labelled_not_confined_and_C04_E02_bounds(self):
        ws = workspace(); cid, sid = load_fixture(ws); adm, _ = principal(ws, "owner", ["admin"]); cur, _ = principal(ws, "curator", ["review"], by=adm); pat, _ = principal(ws, "pat", ["practice"], by=adm); both, _ = principal(ws, "pam", ["practice", "submit"], by=adm)
        com.set_budget(ws, adm, period_id="p1", review_minutes=60, practice_minutes=60, contributor_packet_cap=9, max_open_tasks=9, op_id="op:budget-001")
        t = prc.freeze_task(ws, cur, title="t", question="q?", claim_id=cid, source_ids=[sid], labels=["A", "B"], reference_label="A", reference_answer="REF", rationale="", provenance="MODEL_ANSWER", declared_curator_qualification="", public_example=True,
                            session_minutes=20, evo_version_id=None, op_id="op:task-00001")["payload"]
        a = prc.open_session(ws, pat, task_id=t["task_id"], assistance="NONE", assistance_note="", prior_exposure="NOT_SEEN", op_id="op:sess-00001")["payload"]; b = prc.open_session(ws, both, task_id=t["task_id"], assistance="NONE", assistance_note="", prior_exposure="NOT_SEEN", op_id="op:sess-00002")["payload"]
        self.assertTrue(a["confinement"].startswith("PRACTICE_ONLY")); self.assertTrue(b["confinement"].startswith("NOT_CONFINED")); self.assertIn("submit", b["confinement"])              # truthful label; both still need an attempt before the comparison
        self.assertEqual(code(prc.reveal, ws, both, b["session_id"]), "E_ATTEMPT_FIRST"); self.assertIn("NOT_CONFINED", prc.session_view(ws, both, b["session_id"])["session"]["confinement"])
        with mock.patch.object(com, "MAX_PACKETS", 1):                                                                                                                                   # C-04: the storage bound itself
            com.submit_direct(ws, both, claim_id=cid, kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=5, asserts_withdrawn=False, client_packet_id=None, op_id="op:pk-bound-01")
            self.assertEqual(code(com.submit_direct, ws, both, claim_id=cid, kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=5, asserts_withdrawn=False, client_packet_id=None, op_id="op:pk-bound-02"), "E_STORAGE_BOUND")
        root = pathlib.Path(tempfile.mkdtemp())                                                                                                                                         # E-02: a RUNTIME change invalidates what depends on it
        for d in ("agent", "grader", "evaldata"):
            (root / d).mkdir(); (root / d / "x.json").write_text("{}")
        evo.set_config(ws, adm, {"roots": [str(root)], "components": {"agent_code": {"mode": "path", "path": str(root / "agent")}, "grader": {"mode": "path", "path": str(root / "grader")}, "evaluation_data": {"mode": "path", "path": str(root / "evaldata")}, "runtime": {"mode": "runtime"}},
                                "depends_on": {"agent_code": ["runtime"]}, "protocols": {"agent-json": {"scope": ["agent_code"], "job": "json_wellformed"}}}, op_id="op:evo-config1")
        evo.register_version(ws, both, version_id="v1", parent_version_id=None, label="", op_id="op:evo-reg-v1"); evo.run_evaluation(ws, cur, version_id="v1", protocol_id="agent-json", op_id="op:evo-run-0001")
        real = evo.measure_runtime
        with mock.patch.object(evo, "measure_runtime", lambda: {**real(), "digest": "f" * 64}):                                                                                          # as after a dependency upgrade
            v2 = evo.register_version(ws, both, version_id="v2", parent_version_id="v1", label="", op_id="op:evo-reg-v2")["payload"]
        self.assertEqual(v2["changed_components"], ["runtime"]); r = evo.audit(ws, "v2")["reuse"]["agent-json"]; self.assertEqual(r["decision"], "REEVALUATE"); self.assertIn("runtime", " ".join(r["reasons"]))

    def test_P06_the_export_preview_writes_nothing_and_says_what_cannot_leave(self):
        ws = workspace(); cid, sid = load_fixture(ws); adm, _ = principal(ws, "owner", ["admin"]); cur, _ = principal(ws, "curator", ["review"], by=adm); pat, cred = principal(ws, "pat", ["practice"], by=adm)
        com.set_budget(ws, adm, period_id="p1", review_minutes=60, practice_minutes=60, contributor_packet_cap=5, max_open_tasks=5, op_id="op:budget-001")
        t = prc.freeze_task(ws, cur, title="t", question="q?", claim_id=cid, source_ids=[sid], labels=["A", "B"], reference_label="A", reference_answer="PREVIEW-SECRET", rationale="", provenance="MODEL_ANSWER", declared_curator_qualification="", public_example=False,
                            session_minutes=20, evo_version_id=None, op_id="op:task-00001")["payload"]
        ss = prc.open_session(ws, pat, task_id=t["task_id"], assistance="NONE", assistance_note="", prior_exposure="NOT_SEEN", op_id="op:sess-00001")["payload"]["session_id"]; srv = Server(ws.root); self.addCleanup(srv.close); c = Client(srv); c.login("pat", cred)
        n = len(ws.load()["events"]); st, body, _ = c.post("/modx/preview", {f"sess_{ss}": "1"}, page="/modx"); self.assertEqual(st, 200); self.assertIn("nothing was written", body); self.assertIn("NOT exportable (never revealed in this session)", body)
        self.assertNotIn("PREVIEW-SECRET", body); self.assertEqual(len(ws.load()["events"]), n); self.assertEqual(list(ws.exports.glob("modx-*.zip")), [])
        self.assertEqual(code(mx.preview, ws, pat, modules=[], prc_sessions=["SS999"], withhold_text=False), "E_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
