"""V7-004-V4 closure tests: observed-only provenance equality, descriptor-pinned containment (deterministic
race hook), DESIGNATED-only real dispositions, executed verification records, appointment-evidence resolution
of real reviews, typed prospective eligibility, and the complete constructed public schema at REST/MCP/renderer.
Synthetic fixtures; the only real input is the existing frozen public Lab bundle (offline replay)."""
import contextlib, hashlib, io, json, os, pathlib, sys, tempfile, unittest
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.receipts import packet, counting, verify, scoreboard, export  # noqa: E402
from v3.receipts.contracts import ContractError, POLICY_VERSION  # noqa: E402
from v3.receipts.store import Store, ReviewAuthorityError  # noqa: E402
from v3.receipts.challenge import ChallengeStore  # noqa: E402
from v3.cli import packet as packet_cli, challenge as challenge_cli, receipts as receipts_cli  # noqa: E402
from v3.lab import replay_check  # noqa: E402

T0 = datetime(2026, 9, 14, 12, 0, 0, 1, tzinfo=timezone.utc)
FMT = "yuclaw-verification-packet/1"


def run(main, argv):
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = main(argv)
    except SystemExit as e:
        rc = e.code
    return rc, out.getvalue(), err.getvalue()


def ent(rel, data):
    return {"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data), "status": "INCLUDED"}


def mk(d, name, files, target, arts):
    pk = d / name; (pk / "artifacts").mkdir(parents=True)
    for rel, data in arts.items():
        p = pk / "artifacts" / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    (pk / packet.MANIFEST).write_text(json.dumps({"packet_format": FMT, "files": files, "replay_target": target})); return pk


def sub(aid, *, pid="P-A", grp="G-A", proto="prog", obs=T0, data=b"SYNTHETIC wheel v4\n", outcome="REPRODUCED", **extra):
    h, n = verify.sha256_len(data)
    d = {"schema_version": "receipt-1", "attempt_id": aid, "activity_id": "act", "participant_id": pid, "group_id": grp, "relationship": "UNRELATED",
         "execution_control": "SELF", "assistance": "NONE", "incentive_outcome_dependent": False, "outcome": outcome, "observed_at": obs.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
         "artifact_binding": {"artifact_type": "wheel", "sha256": h, "size_bytes": n}, "release_identity": None, "environment": {"os": "SynOS", "python": "3.12"}, "protocol_id": proto}
    d.update(extra); return d


class ReplaySpy:
    def __init__(self, rc=0): self.calls = []; self.rc = rc
    def __call__(self, path): self.calls.append(pathlib.Path(path).read_bytes()); return self.rc
    def __enter__(self): self._orig = replay_check._run; replay_check._run = self; return self
    def __exit__(self, *a): replay_check._run = self._orig


class ProvenanceEquality(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.d = pathlib.Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_equality_only_from_observed_bytes(self):
        trusted = {"a.json": {"sha256": hashlib.sha256(b"{}").hexdigest(), "size_bytes": 2}}
        r = packet.verify(self.d / "missing", trusted=trusted); self.assertEqual((r["result"], r["provenance"]["official_artifact_equality"]), ("UNSUPPORTED", "UNVERIFIED")); self.assertEqual(r["provenance"]["compared_set"], [])
        pk = mk(self.d, "p1", [ent("a.json", b"{}")], "a.json", {})                                   # listed, missing, claimed digest matches trusted
        r = packet.verify(pk, trusted=trusted); self.assertEqual((r["result"], r["provenance"]["official_artifact_equality"]), ("MISMATCH", "UNVERIFIED")); self.assertEqual(r["provenance"]["unobserved"], ["a.json"])
        pk = mk(self.d, "p2", [ent("a.json", b"{}")], "a.json", {"a.json": b"{}"}); os.chmod(pk / "artifacts" / "a.json", 0)   # unreadable
        try:
            r = packet.verify(pk, trusted=trusted); self.assertEqual(r["provenance"]["official_artifact_equality"], "UNVERIFIED")
        finally:
            os.chmod(pk / "artifacts" / "a.json", 0o600)
        pk = mk(self.d, "p3", [ent("a.json", b"{}")], "a.json", {"a.json": b"{}"})
        with ReplaySpy():
            r = packet.verify(pk, trusted={"a.json": {"sha256": "0" * 64, "size_bytes": 2}}); self.assertEqual((r["result"], r["provenance"]["official_artifact_equality"]), ("SUCCESS", "DIFFERS"))
            r = packet.verify(pk, trusted=trusted); self.assertEqual(r["provenance"]["official_artifact_equality"], "EQUAL"); self.assertEqual(r["provenance"]["compared_set"], ["a.json"])
            pk2 = mk(self.d, "p4", [ent("a.json", b"{}"), ent("b.json", b"[]")], "a.json", {"a.json": b"{}", "b.json": b"[]"})
            r = packet.verify(pk2, trusted=trusted); self.assertEqual(r["provenance"]["official_artifact_equality"], "INCOMPLETE"); self.assertEqual(r["provenance"]["uncovered_by_trusted_identity"], ["b.json"])
            self.assertIn("compared set only", r["provenance"]["scope"])
            pk3 = mk(self.d, "p5", [ent("a.json", b"{}"), ent("b.json", b"[]")], "a.json", {"a.json": b"{}"})   # b missing but claimed digest matches a wider trusted identity
            r = packet.verify(pk3, trusted={**trusted, "b.json": {"sha256": hashlib.sha256(b"[]").hexdigest(), "size_bytes": 2}})
            self.assertEqual((r["result"], r["provenance"]["official_artifact_equality"]), ("MISMATCH", "INCOMPLETE")); self.assertEqual(r["provenance"]["unobserved"], ["b.json"])
        tp = self.d / "t.json"; tp.write_text(json.dumps(trusted))
        with ReplaySpy():
            rc, out, err = run(packet_cli.main, ["verify", str(pk2), "--trusted-manifest", str(tp)]); self.assertEqual(rc, 1); self.assertIn("INCOMPLETE", err)
            rc, out, err = run(packet_cli.main, ["verify", str(pk), "--trusted-manifest", str(tp)]); self.assertEqual(rc, 0, err)


class PinnedContainment(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.d = pathlib.Path(self.tmp.name)
    def tearDown(self): packet._TEST_HOOK = None; self.tmp.cleanup()
    def test_ancestor_swap_after_pin_cannot_redirect_and_outside_is_never_read(self):
        outside = self.d / "outside"; outside.mkdir(); (outside / "t.json").write_bytes(b"OUTSIDE"); os.chmod(outside / "t.json", 0)   # any read attempt would fail loudly
        pk = mk(self.d, "p", [ent("docs/t.json", b"INSIDE!")], "docs/t.json", {"docs/t.json": b"INSIDE!"})
        swapped = []
        def hook(stage, rel):
            if stage == "dir-opened" and not swapped:
                swapped.append(1); os.rename(pk / "artifacts" / "docs", self.d / "moved"); os.symlink(outside, pk / "artifacts" / "docs")
        packet._TEST_HOOK = hook
        try:
            with ReplaySpy() as spy:
                r = packet.verify(pk)
        finally:
            os.chmod(outside / "t.json", 0o600)
        self.assertEqual(swapped, [1]); self.assertEqual(r["result"], "SUCCESS")                     # the pinned chain still names the inside inode
        self.assertEqual(spy.calls, [b"INSIDE!"]); self.assertNotIn("PermissionError", json.dumps(r))   # the outside fixture was never opened
        # static regressions: symlink component now present → refused before any read; traversal; root symlink
        with ReplaySpy() as spy:
            r = packet.verify(pk)
        self.assertEqual(r["result"], "MISMATCH"); self.assertIn("symlink component", r["first_discrepancy"]); self.assertEqual(spy.calls, [])
        pk2 = mk(self.d, "p2", [ent("a.json", b"{}")], "../x.json", {"a.json": b"{}"}); self.assertEqual(packet.verify(pk2)["result"], "UNSUPPORTED")
        pk3 = mk(self.d, "p3", [ent("a.json", b"{}")], "a.json", {"a.json": b"{}"}); os.rename(pk3 / "artifacts", self.d / "mv"); os.symlink(self.d / "mv", pk3 / "artifacts")
        r = packet.verify(pk3); self.assertEqual(r["result"], "UNSUPPORTED"); self.assertIn("artifact root", r["first_discrepancy"])
        pk4 = mk(self.d, "p4", [ent("a.json", b"{}")], "a.json", {"a.json": b"{}"}); os.rename(pk4 / packet.MANIFEST, self.d / "m.json"); os.symlink(self.d / "m.json", pk4 / packet.MANIFEST)
        self.assertEqual(packet.verify(pk4)["result"], "UNSUPPORTED")
    def test_unsupported_platform_refuses(self):
        orig = packet.platform_supported; packet.platform_supported = lambda: (False, "simulated platform without dir_fd")
        try:
            pk = mk(self.d, "p", [ent("a.json", b"{}")], "a.json", {"a.json": b"{}"})
            with ReplaySpy() as spy:
                r = packet.verify(pk)
            self.assertEqual(r["result"], "UNSUPPORTED"); self.assertIn("refusing to verify", r["first_discrepancy"]); self.assertEqual(spy.calls, [])
        finally:
            packet.platform_supported = orig
    def test_valid_frozen_packet_replay_still_works(self):
        rc, out, err = run(packet_cli.main, ["build", str(self.d / "real"), "--source", str(REPO)]); self.assertEqual(rc, 0, err)
        rc, out, err = run(packet_cli.main, ["verify", str(self.d / "real"), "--json"]); res = json.loads(out)
        self.assertEqual((rc, res["result"], res["replay"]["exit"]), (0, "SUCCESS", 0)); self.assertEqual(res["provenance"]["official_artifact_equality"], "UNVERIFIED")


class RealAuthority(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.tmp.name) / "s"; self.st = Store(self.root)
        self.st.designate_reviewer("rev-syn", "S", designated=False); self.st.designate_reviewer("rev-real", "R", designated=True)
        (self.root / "reviewers.json").write_text(json.dumps({"designated": True, "roles": {"legacy": hashlib.sha256(b"L").hexdigest(), **{k: v["token_sha256"] for k, v in self.st.authority()["appointments"].items()}}}))
        self.st.designate_reviewer("rev-syn", "S", designated=False); self.st.designate_reviewer("rev-real", "R", designated=True)   # re-designate after the legacy migration
        self.cs = ChallengeStore(self.root); self.h = hashlib.sha256(b"REAL artifact").hexdigest()
        self.cs.create("real-1", artifact={"artifact_type": "wheel", "sha256": self.h, "size_bytes": 13}, claim_id="claim-real", expected="a", observed="b", synthetic=False, criterion="artifact-reproduction-by-qualified-receipt", now=T0)
        self.cs.create("syn-1", artifact={"artifact_type": "wheel", "sha256": self.h, "size_bytes": 13}, claim_id="claim-syn", expected="a", observed="b", synthetic=True, criterion="artifact-reproduction-by-qualified-receipt", now=T0)
    def tearDown(self): self.tmp.cleanup()
    def test_real_dispositions_need_designated(self):
        self.assertEqual(self.st.authority()["appointments"]["legacy"]["status"], "HELD")
        for role, tok in (("rev-syn", "S"), ("legacy", "L")):
            with self.assertRaises(ReviewAuthorityError): self.cs.dispose("real-1", "REFUTED", reviewer_role=role, token=tok)
        self.assertTrue(self.cs.public_view(synthetic=False)[0]["adverse"])
        with self.assertRaises(ReviewAuthorityError): self.cs.dispose("syn-1", "REFUTED", reviewer_role="legacy", token="L")            # HELD disposes nothing
        self.assertEqual(self.cs.dispose("syn-1", "REFUTED", reviewer_role="rev-syn", token="S", now=T0)["disposed_by"]["authority"], "SYNTHETIC")
        r = self.cs.dispose("real-1", "REFUTED", reviewer_role="rev-real", token="R", now=T0); self.assertEqual(r["disposed_by"]["authority"], "DESIGNATED")
        self.assertFalse(self.cs.public_view(synthetic=False)[0]["adverse"])
        # reviews on REAL receipts: synthetic/held appointments refused at the shared method
        rec = self.st.import_submission(sub("r1"), synthetic=False, received_at=T0)
        with self.assertRaises(ReviewAuthorityError): self.st.add_review(rec["digest"], "QUALIFIED", reviewer_role="rev-syn", token="S")
        with self.assertRaises(ReviewAuthorityError): self.st.add_review(rec["digest"], "QUALIFIED", reviewer_role="legacy", token="L")
        self.assertEqual(self.st.add_review(rec["digest"], "QUALIFIED", reviewer_role="rev-real", token="R", now=T0)["authority"], "DESIGNATED")
    def test_resolution_needs_executed_verification_record(self):
        rev = b"REAL artifact revised"; ra = {"artifact_type": "wheel", "sha256": hashlib.sha256(rev).hexdigest(), "size_bytes": len(rev)}
        kw = dict(reviewer_role="rev-real", token="R", revised_artifact=ra, revised_bytes=rev, now=T0)
        with self.assertRaises(ContractError): self.cs.dispose("real-1", "RESOLVED", verification_id="e" * 64, **kw)                       # unknown reference
        # a real verification record for the WRONG artifact (a receipt binding another artifact)
        other = b"other wheel"; rec = self.st.import_submission(sub("q1", data=other), synthetic=False, received_at=T0)
        self.st.add_observation(rec["digest"], verify.observe(rec["submission"]["artifact_binding"], data=other, now=T0)); self.st.add_review(rec["digest"], "QUALIFIED", reviewer_role="rev-real", token="R", now=T0)
        v_wrong = self.cs.verify_revision("real-1", revised_artifact={"artifact_type": "wheel", "sha256": hashlib.sha256(other).hexdigest(), "size_bytes": len(other)}, method="receipt", receipt_digest=rec["digest"], now=T0)
        self.assertEqual(v_wrong["result"], "SUCCESS")
        with self.assertRaises(ContractError): self.cs.dispose("real-1", "RESOLVED", verification_id=v_wrong["verification_id"], **kw)   # valid record, different revised artifact
        # a record for another challenge
        self.cs.create("real-2", artifact={"artifact_type": "wheel", "sha256": self.h, "size_bytes": 13}, claim_id="claim-real", expected="a", observed="b", synthetic=False, criterion="artifact-reproduction-by-qualified-receipt", now=T0)
        rec2 = self.st.import_submission(sub("q2", data=rev), synthetic=False, received_at=T0)
        self.st.add_observation(rec2["digest"], verify.observe(rec2["submission"]["artifact_binding"], data=rev, now=T0)); self.st.add_review(rec2["digest"], "QUALIFIED", reviewer_role="rev-real", token="R", now=T0)
        v_other = self.cs.verify_revision("real-2", revised_artifact=ra, method="receipt", receipt_digest=rec2["digest"], now=T0); self.assertEqual(v_other["result"], "SUCCESS")
        with self.assertRaises(ContractError): self.cs.dispose("real-1", "RESOLVED", verification_id=v_other["verification_id"], **kw)
        # non-success record (receipt not qualified) leaves resolution unestablished with its reason
        rec3 = self.st.import_submission(sub("q3", data=rev, pid="P-Z"), synthetic=False, received_at=T0)          # no observation, no review
        v_fail = self.cs.verify_revision("real-1", revised_artifact=ra, method="receipt", receipt_digest=rec3["digest"], now=T0)
        self.assertEqual(v_fail["result"], "FAILURE"); self.assertIn("not a qualified successful attempt", v_fail["reason"])
        with self.assertRaises(ContractError): self.cs.dispose("real-1", "RESOLVED", verification_id=v_fail["verification_id"], **kw)
        # the valid path: executed SUCCESS record for this challenge and this revised artifact
        v_ok = self.cs.verify_revision("real-1", revised_artifact=ra, method="receipt", receipt_digest=rec2["digest"], now=T0); self.assertEqual(v_ok["result"], "SUCCESS")
        r = self.cs.dispose("real-1", "RESOLVED", verification_id=v_ok["verification_id"], **kw)
        self.assertEqual(r["resolution"]["verification_id"], v_ok["verification_id"]); self.assertEqual(self.cs.public_view(synthetic=False)[0]["resolution"]["verification_method"], "receipt")
        self.assertEqual(len(self.cs._read(self.cs.f_ver)), 4)                                                                       # records are immutable and retained
        # a synthetic verification cannot serve a real challenge (provenance partition in the receipt method)
        with self.assertRaises(ContractError): self.cs.verify_revision("real-1", revised_artifact={"artifact_type": "sdist", "sha256": "0" * 64, "size_bytes": 1}, method="receipt", receipt_digest="0" * 64)
    def test_packet_verify_method_binds_observed_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d); data = b'{"revised": true}'; pk = mk(d, "pk", [ent("a.json", data)], "a.json", {"a.json": data})
            self.cs.create("bundle-1", artifact={"artifact_type": "bundle", "sha256": "1" * 64, "size_bytes": 5}, claim_id="c", expected="a", observed="b", synthetic=False, criterion="packet-integrity-and-replay", now=T0)
            ra = {"artifact_type": "bundle", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
            with ReplaySpy():
                v = self.cs.verify_revision("bundle-1", revised_artifact=ra, method="packet-verify", packet_dir=pk, now=T0)
                self.assertEqual(v["result"], "SUCCESS"); self.assertEqual(v["evidence"]["observed_path"], "a.json")
                v2 = self.cs.verify_revision("bundle-1", revised_artifact={"artifact_type": "bundle", "sha256": "2" * 64, "size_bytes": 5}, method="packet-verify", packet_dir=pk, now=T0)
                self.assertEqual(v2["result"], "FAILURE"); self.assertIn("not among the packet's observed", v2["reason"])
            with ReplaySpy(rc=1):
                v3 = self.cs.verify_revision("bundle-1", revised_artifact=ra, method="packet-verify", packet_dir=pk, now=T0); self.assertEqual(v3["result"], "FAILURE")
            r = self.cs.dispose("bundle-1", "RESOLVED", reviewer_role="rev-real", token="R", revised_artifact=ra, revised_bytes=data, verification_id=v["verification_id"], now=T0)
            self.assertEqual(r["resolution"]["verification_method"], "packet-verify")
            tok = pathlib.Path(d) / "tok"; tok.write_text("R\n"); os.chmod(tok, 0o600); rp = d / "rev.bin"; rp.write_bytes(data)
            self.cs.create("bundle-2", artifact={"artifact_type": "bundle", "sha256": "1" * 64, "size_bytes": 5}, claim_id="c", expected="a", observed="b", synthetic=False, criterion="packet-integrity-and-replay", now=T0)
            with ReplaySpy():
                rc, out, err = run(challenge_cli.main, ["--store", str(self.root), "verify-revision", "bundle-2", "--revised-type", "bundle", "--revised-sha256", ra["sha256"], "--revised-size-bytes", str(ra["size_bytes"]), "--method", "packet-verify", "--packet", str(pk)])
            self.assertEqual(rc, 0, err); vid = json.loads(out)["verification_id"]
            rc, out, err = run(challenge_cli.main, ["--store", str(self.root), "dispose", "bundle-2", "RESOLVED", "--role", "rev-real", "--token-file", str(tok), "--revised-type", "bundle", "--revised-sha256", ra["sha256"], "--revised-size-bytes", str(ra["size_bytes"]), "--revised-path", str(rp), "--allowed-root", str(d), "--verification-id", "f" * 64]); self.assertEqual(rc, 1); self.assertIn("unknown verification reference", err)
            rc, out, err = run(challenge_cli.main, ["--store", str(self.root), "dispose", "bundle-2", "RESOLVED", "--role", "rev-real", "--token-file", str(tok), "--revised-type", "bundle", "--revised-sha256", ra["sha256"], "--revised-size-bytes", str(ra["size_bytes"]), "--revised-path", str(rp), "--allowed-root", str(d), "--verification-id", vid]); self.assertEqual(rc, 0, err)
    def test_real_reviews_resolve_against_appointment_evidence(self):
        rec = self.st.import_submission(sub("a1"), synthetic=False, received_at=T0); self.st.add_observation(rec["digest"], verify.observe(rec["submission"]["artifact_binding"], data=b"SYNTHETIC wheel v4\n", now=T0))
        with open(self.root / "reviews.jsonl", "a") as fh:                                                                            # legacy ambiguous review line
            fh.write(json.dumps({"kind": "review", "receipt_digest": rec["digest"], "policy_version": POLICY_VERSION, "state": "QUALIFIED", "reviewer_role": "legacy", "authority": "DESIGNATED", "decided_at": "2026-09-14T02:00:00.000000Z", "reason": "legacy"}) + "\n")
        row = counting.derive(self.st, synthetic=False)[0]; self.assertFalse(row["qualified"]); self.assertTrue(any("appointment evidence" in x for x in row["reasons"]))
        first = self.st.add_review(rec["digest"], "QUALIFIED", reviewer_role="rev-real", token="R", now=T0)
        self.assertTrue(counting.derive(self.st, synthetic=False)[0]["qualified"])
        self.st.designate_reviewer("rev-real", "R2", designated=True); self.st.revoke_reviewer("rev-real")                              # credential replaced, then revoked
        row = counting.derive(self.st, synthetic=False)[0]; self.assertTrue(row["qualified"]); self.assertEqual(row["review"]["appointment_id"], first["appointment_id"])   # historical evidence intact
        with self.assertRaises(ReviewAuthorityError): self.st.add_review(rec["digest"], "HELD", reviewer_role="rev-real", token="R2")   # current authority gone
        with open(self.root / "reviews.jsonl", "a") as fh:                                                                            # forged line naming a synthetic appointment
            fh.write(json.dumps({**first, "appointment_id": self.st.authority()["appointments"]["rev-syn"]["appointment_id"], "decided_at": "2026-09-14T13:00:00.000000Z"}) + "\n")
        row = counting.derive(self.st, synthetic=False)[0]; self.assertFalse(row["qualified"]); self.assertTrue(any("not designated" in x for x in row["reasons"]))
        with open(self.root / "reviews.jsonl", "a") as fh:                                                                            # review dated before its appointment
            fh.write(json.dumps({**first, "decided_at": "2020-01-01T00:00:00.000000Z"}) + "\n")
        row = counting.derive(self.st, synthetic=False)[0]; self.assertFalse(row["qualified"]); self.assertTrue(any("before its appointment" in x for x in row["reasons"]))


class TypedEligibility(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.st = Store(pathlib.Path(self.tmp.name) / "s"); self.st.designate_reviewer("rev", "T", designated=False)
    def tearDown(self): self.tmp.cleanup()
    def full(self, aid, obs, imported=None, **kw):
        r = self.st.import_submission(sub(aid, obs=obs, **kw), synthetic=True, received_at=imported or obs)
        self.st.add_observation(r["digest"], verify.observe(r["submission"]["artifact_binding"], data=kw.get("data", b"SYNTHETIC wheel v4\n"), now=T0))
        self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev", token="T", now=T0); return r
    def reg(self, **kw):
        d = {"protocol_id": "prog", "anchor": "2026-09-15", "registered_at": "2026-09-14T06:00:00.000000Z", "policy_version": POLICY_VERSION}; d.update(kw); return d
    def counts(self): return counting.counts(counting.derive(self.st, synthetic=True), registration=self.reg())
    def test_foreign_protocol_starting_with_w_and_typed_flags(self):
        self.full("f1", datetime(2026, 9, 16, 12, 0, 0, 0, tzinfo=timezone.utc), proto="wrong-program", pid="P1"); self.full("w0", datetime(2026, 9, 16, 12, 0, 0, 0, tzinfo=timezone.utc), pid="P2")
        c = self.counts(); w = c["windows"]
        self.assertEqual((w["unregistered-protocol/wrong-program"]["eligibility"], w["unregistered-protocol/wrong-program"]["prospective"]), ("other_protocol", False))
        self.assertEqual((w["prog/w0"]["eligibility"], w["prog/w0"]["prospective"]), ("prospective", True)); self.assertEqual(c["excluded_from_primary"]["other_protocols"], {"wrong-program": 1})
        self.assertEqual(counting.classify(counting.derive(self.st, synthetic=True)[0], self.reg())["eligibility"], "other_protocol")
        board = scoreboard.build(self.st.root, synthetic=True, registration=self.reg()); self.assertEqual(board["columns"]["replications"]["windows"]["unregistered-protocol/wrong-program"]["eligibility"], "other_protocol")
    def test_corrections_cannot_promote_pre_anchor_or_pre_registration(self):
        t1 = datetime(2026, 9, 14, 12, 0, 0, 0, tzinfo=timezone.utc); t2 = datetime(2026, 9, 16, 12, 0, 0, 0, tzinfo=timezone.utc)
        r = self.full("pa", t1); self.assertEqual(list(self.counts()["windows"]), ["prog/pre-anchor"])
        self.full("pa", t2, supersedes={"digest": r["digest"], "reason": "rewrite"}); self.assertEqual(list(self.counts()["windows"]), ["prog/pre-anchor"])
        t0 = datetime(2026, 9, 14, 1, 0, 0, 0, tzinfo=timezone.utc); r2 = self.full("pr", t0, pid="P2")
        self.full("pr", t2, pid="P2", supersedes={"digest": r2["digest"], "reason": "rewrite"}); self.assertEqual(self.counts()["windows"]["prog/pre-registration"]["primary_distinct_persons"], 1)
        r3 = self.full("ok", t2, pid="P3"); self.full("ok", t2, pid="P3", outcome="FAILED", supersedes={"digest": r3["digest"], "reason": "valid correction"})   # within-program correction keeps its window
        c = self.counts(); self.assertEqual(c["windows"]["prog/w0"]["primary_distinct_persons"], 1); self.assertEqual(c["windows"]["prog/w0"]["successful_attempts"], 0); self.assertEqual(c["visible"]["qualified_failed"], 1)
        self.st.import_submission(sub("ok", obs=t2, pid="P3", outcome="FAILED", supersedes={"digest": r3["digest"], "reason": "valid correction"}), synthetic=True, received_at=t2)   # duplicate collapses
        self.assertEqual(self.counts()["attempts"], 3)
    def test_exact_boundaries(self):
        from datetime import timedelta
        base = datetime(2026, 9, 15, 6, 0, 0, 0, tzinfo=timezone.utc)
        self.full("d27", base + timedelta(days=27), pid="P1"); self.full("d28", base + timedelta(days=28), pid="P2")
        w = self.counts()["windows"]; self.assertEqual(w["prog/w0"]["primary_distinct_persons"], 1); self.assertEqual(w["prog/w1"]["primary_distinct_persons"], 1)
        self.assertTrue(all(v["eligibility"] == "prospective" for v in w.values()))


class PublicSchemaBoundary(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.d = pathlib.Path(self.tmp.name); self.board = scoreboard.build(self.d / "s", synthetic=False)
    def tearDown(self): self.tmp.cleanup()
    def status(self, b):
        p = self.d / "b.json"; p.write_text(json.dumps(b)); return scoreboard.inspect_public(p)
    def test_private_and_unknown_fields_rejected_everywhere_without_echo(self):
        ok = self.status(self.board); self.assertEqual(ok["status"], "OK"); self.assertEqual(ok["board"]["public_schema_version"], scoreboard.BOARD_SCHEMA_VERSION)
        cases = []
        b = json.loads(json.dumps(self.board)); b["private"] = {"contact": "PRIVATE-ROOT"}; cases.append(b)
        b = json.loads(json.dumps(self.board)); b["columns"]["replications"]["private"] = {"note": "PRIVATE-NESTED"}; cases.append(b)
        b = json.loads(json.dumps(self.board)); b["columns"]["witnesses"]["extra"] = "PRIVATE-X"; cases.append(b)
        b = json.loads(json.dumps(self.board)); b["columns"]["replications"]["artifacts"]["hidden"] = "PRIVATE-X"; cases.append(b)
        b = json.loads(json.dumps(self.board)); b["columns"]["replications"]["registration"]["contact"] = "PRIVATE-X"; cases.append(b)
        b = json.loads(json.dumps(self.board)); b["definitions"]["secret"] = "PRIVATE-X"; cases.append(b)
        b = json.loads(json.dumps(self.board)); b["columns"]["witnesses"]["state"] = "<b>PRIVATE-X</b>"; cases.append(b)                 # malformed state
        b = json.loads(json.dumps(self.board)); b["columns"]["replications"]["attempts"] = "1"; cases.append(b)                             # malformed count
        b = json.loads(json.dumps(self.board)); b["columns"]["replications"]["qualified"] = 5; cases.append(b)                              # relationship violated
        b = json.loads(json.dumps(self.board)); b["receipts_public"] = [{"schema_version": "receipt-1", "synthetic": False, "attempt_id": "x", "participant": "p-" + "0" * 16, "outcome": "FAILED", "review_state": "RECEIVED", "binding_completeness": "NONE", "qualified": False, "successful": False, "receipt_digest": "0" * 64}]; b["columns"]["replications"]["attempts"] = 1; b["columns"]["replications"]["visible"]["unqualified"] = 1; b["columns"]["refusals"]["count"] = 1; cases.append(b)   # incomplete receipt row
        b = json.loads(json.dumps(self.board)); b["challenges_public"] = [{"challenge_id": "c", "artifact": {"artifact_type": "wheel", "sha256": "0" * 64, "size_bytes": 1}, "claim_id": "k", "disposition": "RESOLVED", "version": 2, "created_at": "2026-09-14T00:00:00.000000Z", "synthetic": False, "disposed_by_authority": "DESIGNATED", "resolution": {"revised_artifact": {"artifact_type": "wheel", "sha256": "1" * 64, "size_bytes": 1}, "verification_method": "label", "original_finding_retained": True}, "adverse": False}]; b["columns"]["challenges"] = {"by_disposition": {"RESOLVED": 1}, "adverse_open": 0, "total": 1, "state": "OBSERVED"}; cases.append(b)   # invalid resolution structure
        b = json.loads(json.dumps(self.board)); b["decisions_public"] = [{"decision_id": "d", "decision": "DISCARD_CLAIM", "packet_manifest_digest": "0" * 64, "claim_id": "k", "decided_at": "2026-09-14T00:00:00.000000Z", "synthetic": False, "context": {"x": "PRIVATE-X"}}]; cases.append(b)
        for i, b in enumerate(cases):
            info = self.status(b); self.assertEqual(info["status"], "INVALID", i); self.assertIsNone(info["board"])
            self.assertNotIn("PRIVATE", info["reason"], i); self.assertNotIn("private", info["reason"].lower().replace("field path", ""), i)
        b = json.loads(json.dumps(self.board)); b["synthetic"] = True; self.assertEqual(self.status(b)["status"], "SYNTHETIC_REFUSED")
        self.assertEqual(scoreboard.inspect_public(self.d / "none.json")["status"], "ABSENT")
    def test_served_object_is_constructed_and_surfaces_agree(self):
        from fastapi.testclient import TestClient
        from v3.api import server
        from v3.mcp import server as mcp_server
        from v3.web import render_scoreboard as rs
        path = REPO / "docs" / "receipts" / "scoreboard.json"; original = path.read_bytes()
        fn = getattr(mcp_server.get_evidence_scoreboard, "fn", None) or mcp_server.get_evidence_scoreboard
        try:
            b = json.loads(json.dumps(self.board)); b["private"] = {"contact": "PRIVATE-ROOT"}; b["columns"]["replications"]["private"] = "PRIVATE-NESTED"; path.write_text(json.dumps(b))
            with TestClient(server.app) as c:
                body = c.get("/v1/receipts/scoreboard").json()
            self.assertEqual(body["status"], "UNAVAILABLE"); self.assertNotIn("PRIVATE", json.dumps(body)); self.assertEqual(fn()["status"], "UNAVAILABLE")
            html = rs.render(None, "INVALID"); self.assertIn("UNAVAILABLE", html); self.assertNotIn("PRIVATE", html)
            path.write_text(json.dumps(self.board))
            with TestClient(server.app) as c:
                body = c.get("/v1/receipts/scoreboard").json()
            self.assertEqual(body["public_schema_version"], scoreboard.BOARD_SCHEMA_VERSION); self.assertEqual(body["columns"]["replications"]["attempts"], 0)
            self.assertEqual(set(body) - {"compliance", "compliance_notice"}, set(fn())); self.assertEqual(body["columns"], fn()["columns"])
            html = rs.render(fn(), "OK"); self.assertIn("attempts=0", html)
            b = json.loads(json.dumps(self.board)); b["receipts_public"] = [{"schema_version": "receipt-1", "synthetic": False, "attempt_id": "x", "participant": "p-" + "0" * 16, "outcome": "FAILED", "review_state": "RECEIVED", "binding_completeness": "NONE", "qualified": False, "successful": False, "receipt_digest": "0" * 64}]
            b["columns"]["replications"]["attempts"] = 1; b["columns"]["replications"]["visible"]["unqualified"] = 1; b["columns"]["refusals"]["count"] = 1; path.write_text(json.dumps(b))
            info = scoreboard.inspect_public(path); self.assertEqual(info["status"], "INVALID"); html = rs.render(info["board"], info["status"]); self.assertIn("UNAVAILABLE", html)   # no KeyError
        finally:
            path.write_bytes(original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
