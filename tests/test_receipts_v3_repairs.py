"""V7-004-V3 repair tests: packet containment/validation/private-copy replay, appointment-bound reviewer
authority, observation binding, registration-aware counting, trusted challenge dispositions, decision
context, board validation, CLI failure paths and credential input. Synthetic fixtures; the only real
inputs are the public frozen artifacts already on disk (read-only). No DB, no network."""
import contextlib, hashlib, io, json, os, pathlib, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.receipts import packet, counting, verify, export, scoreboard, credentials  # noqa: E402
from v3.receipts.contracts import ContractError, POLICY_VERSION  # noqa: E402
from v3.receipts.store import Store, ReviewAuthorityError  # noqa: E402
from v3.receipts.challenge import ChallengeStore  # noqa: E402
from v3.receipts.decision import DecisionStore  # noqa: E402
from v3.cli import packet as packet_cli, receipts as receipts_cli, challenge as challenge_cli, decision as decision_cli  # noqa: E402
from v3.lab import replay_check  # noqa: E402

T0 = datetime(2026, 9, 14, 12, 0, 0, 1, tzinfo=timezone.utc)
D0 = T0 - timedelta(days=1)                      # appointments precede the fixed review clock T0 (wall-clock independent)
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


def sub(aid, *, pid="P-A", grp="G-A", proto="proto-A", obs=T0, data=b"SYNTHETIC wheel v3\n", outcome="REPRODUCED", **extra):
    h, n = verify.sha256_len(data)
    d = {"schema_version": "receipt-1", "attempt_id": aid, "activity_id": "act", "participant_id": pid, "group_id": grp, "relationship": "UNRELATED",
         "execution_control": "SELF", "assistance": "NONE", "incentive_outcome_dependent": False, "outcome": outcome, "observed_at": obs.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
         "artifact_binding": {"artifact_type": "wheel", "sha256": h, "size_bytes": n}, "release_identity": None, "environment": {"os": "SynOS", "python": "3.12"}, "protocol_id": proto}
    d.update(extra); return d


class ReplaySpy:
    """Records whether/what the replay saw; never runs a real replay."""
    def __init__(self, rc=0, swap=None): self.calls = []; self.rc = rc; self.swap = swap
    def __call__(self, path):
        self.calls.append(pathlib.Path(path).read_bytes())
        if self.swap: self.swap()
        return self.rc
    def __enter__(self): self._orig = replay_check._run; replay_check._run = self; return self
    def __exit__(self, *a): replay_check._run = self._orig


class PacketBoundary(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.d = pathlib.Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def mk(self, name, files, target="a.json", artifacts=None):
        pk = self.d / name; (pk / "artifacts").mkdir(parents=True)
        for rel, data in (artifacts or {}).items():
            p = pk / "artifacts" / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        (pk / packet.MANIFEST).write_text(json.dumps({"packet_format": FMT, "files": files, "replay_target": target}))
        return pk
    def test_invalid_packets_never_reach_replay(self):
        outside = self.d / "outside.json"; outside.write_bytes(b"{}")
        ext = self.d / "ext"; ext.mkdir(); (ext / "t.json").write_bytes(b"{}")
        cases = {
            "empty files + unlisted target": self.mk("p1", [], "x/b.json", {"x/b.json": b"{}"}),
            "absolute target": self.mk("p2", [ent("a.json", b"{}")], str(outside), {"a.json": b"{}"}),
            "traversal target": self.mk("p3", [ent("a.json", b"{}")], "../outside.json", {"a.json": b"{}"}),
            "duplicate entries": self.mk("p5", [ent("a.json", b"{}"), ent("a.json", b"{}")], "a.json", {"a.json": b"{}"}),
            "case-ambiguous duplicate": self.mk("p5b", [ent("a.json", b"{}"), ent("A.json", b"{}")], "a.json", {"a.json": b"{}", "A.json": b"{}"}),
            "bool size": self.mk("p6", [{"path": "a.json", "sha256": "0" * 64, "size_bytes": True, "status": "INCLUDED"}], "a.json", {"a.json": b"{}"}),
            "short hash": self.mk("p7", [{"path": "a.json", "sha256": "abc", "size_bytes": 2, "status": "INCLUDED"}], "a.json", {"a.json": b"{}"}),
            "bad status": self.mk("p8", [{"path": "a.json", "status": "SKIPPED"}], "a.json", {"a.json": b"{}"}),
            "absent target": self.mk("p9", [{"path": "a.json", "status": "ABSENT"}], "a.json"),
            "files not a list": self.mk("p10", {"a": 1}, "a.json"),
            "non-canonical spelling": self.mk("p11", [ent("./a.json", b"{}")], "./a.json", {"a.json": b"{}"}),
        }
        for label, pk in cases.items():
            with ReplaySpy() as spy:
                r = packet.verify(pk)
            self.assertEqual(r["result"], "UNSUPPORTED", label); self.assertEqual(spy.calls, [], label); self.assertIn("first_discrepancy", r)
        # symlink ancestor: listed, hash matches through the link, but a component is a symlink → containment failure, replay never runs
        pk = self.mk("p4", [ent("docs/t.json", b"{}")], "docs/t.json"); os.symlink(ext, pk / "artifacts" / "docs")
        with ReplaySpy() as spy:
            r = packet.verify(pk)
        self.assertEqual(r["result"], "MISMATCH"); self.assertIn("symlink component", r["first_discrepancy"]); self.assertEqual(spy.calls, [])
        # symlinked artifact root and symlinked manifest
        pk = self.mk("p12", [ent("a.json", b"{}")], "a.json"); os.rename(pk / "artifacts", self.d / "moved"); os.symlink(self.d / "moved", pk / "artifacts")
        with ReplaySpy() as spy:
            r = packet.verify(pk)
        self.assertEqual(r["result"], "UNSUPPORTED"); self.assertIn("artifact root", r["first_discrepancy"]); self.assertEqual(spy.calls, [])
        pk = self.mk("p13", [ent("a.json", b"{}")], "a.json", {"a.json": b"{}"}); os.rename(pk / packet.MANIFEST, self.d / "m.json"); os.symlink(self.d / "m.json", pk / packet.MANIFEST)
        self.assertEqual(packet.verify(pk)["result"], "UNSUPPORTED")
        # wrong size / wrong hash / missing artifact → MISMATCH before replay
        for label, files, arts in (("wrong size", [dict(ent("a.json", b"{}"), size_bytes=3)], {"a.json": b"{}"}),
                                   ("wrong hash", [dict(ent("a.json", b"{}"), sha256="1" * 64)], {"a.json": b"{}"}),
                                   ("missing artifact", [ent("a.json", b"{}")], {})):
            with ReplaySpy() as spy:
                r = packet.verify(self.mk("m-" + label.replace(" ", "_"), files, "a.json", arts))
            self.assertEqual(r["result"], "MISMATCH", label); self.assertEqual(spy.calls, [], label); self.assertEqual(r["replay"], "NOT RUN (integrity failed first)")
        # not a JSON object / unreadable manifest / missing dir: controlled UNSUPPORTED, no traceback
        pk = self.d / "p14"; (pk / "artifacts").mkdir(parents=True); (pk / packet.MANIFEST).write_bytes(b"\xff\xfe not json")
        self.assertEqual(packet.verify(pk)["result"], "UNSUPPORTED"); self.assertEqual(packet.verify(self.d / "nope")["result"], "UNSUPPORTED")
    def test_valid_packet_replays_private_copy_of_verified_bytes(self):
        pk = self.mk("ok", [ent("a.json", b'{"k": 1}'), {"path": "opt.json", "status": "ABSENT"}], "a.json", {"a.json": b'{"k": 1}'})
        target = pk / "artifacts" / "a.json"
        with ReplaySpy(swap=lambda: target.write_bytes(b"CHANGED")) as spy:       # a replacement at replay time cannot be what is replayed
            r = packet.verify(pk)
        self.assertEqual(r["result"], "SUCCESS"); self.assertEqual(spy.calls, [b'{"k": 1}']); self.assertEqual(target.read_bytes(), b"CHANGED")
        self.assertEqual(r["replay"]["target_sha256"], hashlib.sha256(b'{"k": 1}').hexdigest()); self.assertIn("PRIVATE copy", r["replay"]["mode"])
        self.assertEqual([c for c in r["checks"] if c["path"] == "opt.json"][0]["ok"], None)                          # explicit limitation, not a failure
        self.assertEqual(r["provenance"]["official_artifact_equality"], "UNVERIFIED")                                     # no trusted identity supplied
        target.write_bytes(b'{"k": 1}')                                                                                    # restore the bytes; now test the replay outcomes
        with ReplaySpy(rc=1) as spy:
            self.assertEqual(packet.verify(pk)["result"], "MISMATCH")
        def boom(path): raise RuntimeError("malformed bundle")
        orig = replay_check._run; replay_check._run = boom
        try:
            r = packet.verify(pk); self.assertEqual(r["result"], "UNSUPPORTED"); self.assertIn("replay raised RuntimeError", r["first_discrepancy"])
        finally:
            replay_check._run = orig
    def test_provenance_separate_from_integrity(self):
        pk = self.mk("prov", [ent("a.json", b"{}")], "a.json", {"a.json": b"{}"})
        with ReplaySpy():
            eq = packet.verify(pk, trusted={"a.json": {"sha256": hashlib.sha256(b"{}").hexdigest(), "size_bytes": 2}})
            diff = packet.verify(pk, trusted={"a.json": {"sha256": "0" * 64, "size_bytes": 2}})
            part = packet.verify(pk, trusted={"b.json": {"sha256": "0" * 64, "size_bytes": 2}})
        self.assertEqual((eq["result"], eq["provenance"]["official_artifact_equality"]), ("SUCCESS", "EQUAL"))
        self.assertEqual((diff["result"], diff["provenance"]["official_artifact_equality"]), ("SUCCESS", "DIFFERS"))   # integrity holds; origin differs
        self.assertEqual(part["provenance"]["official_artifact_equality"], "UNVERIFIED")                               # V4: nothing compared → never equal
        tp = self.d / "trusted.json"; tp.write_text(json.dumps({"files": [ent("a.json", b"{}")]}))
        with ReplaySpy():
            rc, out, err = run(packet_cli.main, ["verify", str(pk), "--trusted-manifest", str(tp)]); self.assertEqual(rc, 0, err)
            tp.write_text(json.dumps({"a.json": {"sha256": "0" * 64, "size_bytes": 2}}))
            rc, out, err = run(packet_cli.main, ["verify", str(pk), "--trusted-manifest", str(tp)]); self.assertEqual(rc, 1); self.assertIn("provenance", err)
            tp.write_text("not json"); rc, out, err = run(packet_cli.main, ["verify", str(pk), "--trusted-manifest", str(tp)]); self.assertEqual(rc, 3)
    def test_shipped_cli_rejections_and_real_frozen_bundle_replay(self):
        pk = self.mk("cli", [], "x.json", {"x.json": b"{}"})
        with ReplaySpy() as spy:
            rc, out, err = run(packet_cli.main, ["verify", str(pk), "--json"])
        self.assertEqual(rc, 3); self.assertEqual(json.loads(out)["result"], "UNSUPPORTED"); self.assertEqual(spy.calls, [])
        rc, out, err = run(packet_cli.main, ["verify", str(self.d / "missing")]); self.assertEqual(rc, 3)
        rc, out, err = run(packet_cli.main, ["build", str(self.d / "out"), "--source", str(self.d)]); self.assertEqual(rc, 3)
        # ONE real offline replay of the existing frozen public Lab bundle through the repaired valid path (no spy)
        rc, out, err = run(packet_cli.main, ["build", str(self.d / "real"), "--source", str(REPO)]); self.assertEqual(rc, 0, err)
        rc, out, err = run(packet_cli.main, ["verify", str(self.d / "real"), "--json"]); res = json.loads(out)
        self.assertEqual(rc, 0, out); self.assertEqual(res["result"], "SUCCESS"); self.assertEqual(res["replay"]["exit"], 0)
        self.assertEqual(res["replay"]["target"], "docs/replay/lab_replay_bundle.json"); self.assertEqual(res["provenance"]["official_artifact_equality"], "UNVERIFIED")
        self.assertNotIn("internal/", json.dumps(res))


class ReviewerAppointments(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.st = Store(pathlib.Path(self.tmp.name) / "s")
    def tearDown(self): self.tmp.cleanup()
    def rec(self, aid="a1", synthetic=False, **kw):
        r = self.st.import_submission(sub(aid, **kw), synthetic=synthetic, received_at=T0)
        self.st.add_observation(r["digest"], verify.observe(r["submission"]["artifact_binding"], data=kw.get("data", b"SYNTHETIC wheel v3\n"), now=T0)); return r
    def test_designation_belongs_to_the_appointment(self):
        self.st.designate_reviewer("rev-syn", "TOKEN-SYN", designated=False, now=D0)
        r = self.rec(); rs = self.rec("s1", synthetic=True)
        self.assertEqual(self.st.add_review(rs["digest"], "QUALIFIED", reviewer_role="rev-syn", token="TOKEN-SYN", now=T0)["authority"], "SYNTHETIC")
        self.st.designate_reviewer("rev-real", "TOKEN-REAL", designated=True, now=D0)
        again = self.st.add_review(rs["digest"], "QUALIFIED", reviewer_role="rev-syn", token="TOKEN-SYN", now=T0)
        self.assertEqual(again["authority"], "SYNTHETIC")                                     # no promotion of another role
        with self.assertRaises(ReviewAuthorityError): self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev-syn", token="TOKEN-SYN")   # V4: synthetic authority never touches a real receipt
        real = self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev-real", token="TOKEN-REAL", now=T0)
        self.assertEqual(real["authority"], "DESIGNATED"); self.assertNotEqual(real["appointment_id"], again["appointment_id"])
        self.assertTrue(counting.derive(self.st, synthetic=False)[0]["qualified"])
        with self.assertRaises(ReviewAuthorityError): self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev-real", token="TOKEN-SYN")   # wrong credential
        with self.assertRaises(ReviewAuthorityError): self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev-syn", token="TOKEN-REAL")
    def test_credential_replacement_revocation_and_history_untouched(self):
        self.st.designate_reviewer("rev", "OLD", designated=True, now=D0); r = self.rec()
        first = self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev", token="OLD", now=T0)
        new = self.st.designate_reviewer("rev", "NEW", designated=True, now=D0)
        self.assertEqual(new["supersedes_appointment_id"], first["appointment_id"]); self.assertNotIn("token_sha256", new)
        with self.assertRaises(ReviewAuthorityError): self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev", token="OLD")
        self.assertEqual(self.st.review_for(r["digest"])["appointment_id"], first["appointment_id"])                   # history untouched
        self.assertEqual(self.st.add_review(r["digest"], "HELD", reviewer_role="rev", token="NEW", now=T0)["appointment_id"], new["appointment_id"])
        self.st.revoke_reviewer("rev")
        with self.assertRaises(ReviewAuthorityError): self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev", token="NEW")
        for line in (self.st.root / "appointments.jsonl").read_text().splitlines() + (self.st.root / "reviewers.json").read_text().splitlines():
            self.assertNotIn("OLD", line.replace("HOLD", "")); self.assertNotIn("NEW", line)                        # tokens never at rest in clear
    def test_legacy_shared_boolean_is_held_never_inferred(self):
        (self.st.root / "reviewers.json").write_text(json.dumps({"designated": True, "roles": {"legacy-rev": hashlib.sha256(b"LT").hexdigest()}}))
        r = self.rec()
        with self.assertRaises(ReviewAuthorityError): self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="legacy-rev", token="LT", now=T0)   # V4: HELD reviews nothing
        self.assertFalse(counting.derive(self.st, synthetic=False)[0]["qualified"])
        self.assertEqual(self.st.authority()["appointments"]["legacy-rev"]["status"], "HELD")
        self.st.designate_reviewer("legacy-rev", "LT2", designated=True, now=D0)
        self.assertEqual(self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="legacy-rev", token="LT2", now=T0)["authority"], "DESIGNATED")
        pub = export.project(counting.derive(self.st, synthetic=False)[0], self.st, mode="public"); self.assertEqual(pub["review_authority"], "DESIGNATED")
    def test_policy_bound_designation_and_changed_receipt(self):
        self.st.designate_reviewer("rev", "T", designated=True, policy_version="receipt-policy-other", now=D0)
        r = self.rec()
        with self.assertRaises(ReviewAuthorityError): self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev", token="T")
        self.st.designate_reviewer("rev", "T", designated=True, now=D0); self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev", token="T", now=T0)
        self.assertTrue(counting.derive(self.st, synthetic=False)[0]["qualified"])
        r2 = self.st.import_submission(sub("a1", outcome="FAILED", supersedes={"digest": r["digest"], "reason": "correction"}), synthetic=False, received_at=T0)
        self.assertIsNone(self.st.review_for(r2["digest"])); self.assertFalse(counting.derive(self.st, synthetic=False)[0]["qualified"])
    def test_observation_binding_and_forged_inputs(self):
        self.st.designate_reviewer("rev", "T", designated=True, now=D0)
        r = self.st.import_submission(sub("o1"), synthetic=False, received_at=T0)
        b = r["submission"]["artifact_binding"]
        with self.assertRaises(ContractError): self.st.add_observation("0" * 64, verify.observe(b, data=b"x", now=T0))                       # unknown receipt
        forged = dict(verify.observe(b, now=T0), verified=True)                                                                            # unavailable bytes marked verified
        with self.assertRaises(ContractError): self.st.add_observation(r["digest"], forged)
        other = verify.observe({"artifact_type": "sdist", "sha256": "1" * 64, "size_bytes": 5}, data=b"12345", now=T0)                    # different artifact
        with self.assertRaises(ContractError): self.st.add_observation(r["digest"], other)
        smug = dict(verify.observe(b, data=b"wrong bytes", now=T0)); smug["verified"] = True                                               # observed != claimed but flagged
        with self.assertRaises(ContractError): self.st.add_observation(r["digest"], smug)
        self.st.add_observation(r["digest"], verify.observe(b, now=T0)); self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev", token="T", now=T0)
        row = counting.derive(self.st, synthetic=False)[0]; self.assertEqual(row["binding_completeness"], "UNVERIFIED"); self.assertFalse(row["qualified"])
        self.st.add_observation(r["digest"], verify.observe(b, data=b"SYNTHETIC wheel v3\n", now=T0))
        self.assertTrue(counting.derive(self.st, synthetic=False)[0]["qualified"])


class RegisteredCounting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.st = Store(pathlib.Path(self.tmp.name) / "s"); self.st.designate_reviewer("rev", "T", designated=False, now=D0)
    def tearDown(self): self.tmp.cleanup()
    def full(self, aid, imported=T0, **kw):
        r = self.st.import_submission(sub(aid, **kw), synthetic=True, received_at=imported)
        data = kw.get("data", b"SYNTHETIC wheel v3\n")
        self.st.add_observation(r["digest"], verify.observe(r["submission"]["artifact_binding"], data=data, now=T0))
        self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev", token="T", now=T0); return r
    def reg(self, **kw):
        d = {"protocol_id": "proto-A", "anchor": "2026-09-14", "registered_at": "2026-09-14T06:00:00.000000Z", "policy_version": POLICY_VERSION}; d.update(kw); return d
    def counts(self, reg): return counting.counts(counting.derive(self.st, synthetic=True), registration=reg)
    def test_protocols_never_reassigned_and_populations_kept(self):
        self.full("a", pid="P1", grp="G1"); self.full("b", pid="P2", grp="G2", proto="proto-B"); self.full("f", pid="P3", grp="G3", outcome="FAILED"); self.full("i", pid="P4", grp="G4", outcome="INCONCLUSIVE")
        c = self.counts(self.reg())
        self.assertEqual((c["attempts"], c["qualified"], c["successful"]), (4, 4, 2))                                     # totals stay the visible population (both protocols)
        self.assertEqual(c["windows"]["proto-A/w0"]["primary_distinct_persons"], 3); self.assertEqual(c["windows"]["proto-A/w0"]["successful_distinct_persons"], 1)
        self.assertEqual(c["windows"]["unregistered-protocol/proto-B"]["primary_distinct_persons"], 1); self.assertFalse(c["windows"]["unregistered-protocol/proto-B"]["prospective"])
        self.assertEqual(c["excluded_from_primary"]["other_protocols"], {"proto-B": 1}); self.assertEqual(c["by_protocol"]["proto-B"]["qualified"], 1)
        self.assertEqual((c["visible"]["qualified_failed"], c["visible"]["qualified_inconclusive"]), (1, 1))
        u = self.counts(None); self.assertEqual(set(u["windows"]), {"unwindowed"}); self.assertEqual(u["registration"]["status"], "PENDING")
    def test_prospective_rule_pre_registration_same_day_and_lineage(self):
        early = datetime(2026, 9, 14, 1, 0, 0, 0, tzinfo=timezone.utc)                       # same UTC day, BEFORE the 06:00Z registration instant
        self.full("pre", pid="P1", obs=early, imported=early)
        self.full("post", pid="P2", obs=datetime(2026, 9, 14, 7, 0, 0, 0, tzinfo=timezone.utc), imported=datetime(2026, 9, 14, 7, 0, 0, 0, tzinfo=timezone.utc))
        c = self.counts(self.reg())
        self.assertEqual(c["windows"]["proto-A/pre-registration"]["primary_distinct_persons"], 1); self.assertEqual(c["windows"]["proto-A/w0"]["primary_distinct_persons"], 1)
        self.assertEqual(c["excluded_from_primary"]["pre_registration"], 1)
        # a correction that rewrites the timestamp forward cannot move the attempt into the prospective floor
        cur = self.st.current_submissions()["pre"]
        r2 = self.st.import_submission(sub("pre", pid="P1", obs=datetime(2026, 9, 14, 8, 0, 0, 0, tzinfo=timezone.utc), supersedes={"digest": cur["digest"], "reason": "rewrite"}),
                                       synthetic=True, received_at=datetime(2026, 9, 14, 8, 0, 0, 0, tzinfo=timezone.utc))
        self.st.add_observation(r2["digest"], verify.observe(r2["submission"]["artifact_binding"], data=b"SYNTHETIC wheel v3\n", now=T0)); self.st.add_review(r2["digest"], "QUALIFIED", reviewer_role="rev", token="T", now=T0)
        c = self.counts(self.reg()); self.assertEqual(c["windows"]["proto-A/pre-registration"]["primary_distinct_persons"], 1); self.assertEqual(c["windows"]["proto-A/w0"]["primary_distinct_persons"], 1)
        # observed after registration but imported before it (impossible legitimately) is also pre-registration
        self.full("imp", pid="P9", obs=datetime(2026, 9, 14, 9, 0, 0, 0, tzinfo=timezone.utc), imported=early)
        self.assertEqual(self.counts(self.reg())["windows"]["proto-A/pre-registration"]["primary_distinct_persons"], 2)
    def test_exact_28_day_boundaries_and_pre_anchor(self):
        base = datetime(2026, 9, 20, 6, 0, 0, 0, tzinfo=timezone.utc)
        reg = self.reg(anchor="2026-09-20", registered_at="2026-09-14T06:00:00.000000Z")
        self.full("d27", pid="P1", obs=base + timedelta(days=27), imported=base); self.full("d28", pid="P2", obs=base + timedelta(days=28), imported=base)
        self.full("d0", pid="P3", obs=base, imported=base); self.full("pa", pid="P4", obs=datetime(2026, 9, 16, 6, 0, 0, 0, tzinfo=timezone.utc), imported=datetime(2026, 9, 16, 6, 0, 0, 0, tzinfo=timezone.utc))
        c = self.counts(reg)
        self.assertEqual(c["windows"]["proto-A/w0"]["primary_distinct_persons"], 2); self.assertEqual(c["windows"]["proto-A/w1"]["primary_distinct_persons"], 1)
        self.assertEqual(c["windows"]["proto-A/pre-anchor"]["primary_distinct_persons"], 1); self.assertEqual(c["excluded_from_primary"]["pre_anchor"], 1)
    def test_same_person_across_versions_and_duplicates_dedup(self):
        self.full("v1", pid="P1", grp="G1"); self.full("v2", pid="P1", grp="G1", data=b"SYNTHETIC wheel v3 rebuilt\n")
        self.st.import_submission(sub("v1", pid="P1", grp="G1"), synthetic=True, received_at=T0)                  # exact duplicate collapses
        c = self.counts(self.reg()); w = c["windows"]["proto-A/w0"]
        self.assertEqual((c["attempts"], w["primary_attempts"], w["primary_distinct_persons"], w["primary_distinct_groups"]), (2, 2, 1, 1))
        self.assertEqual(c["artifacts"]["successful_cohort_artifacts"], 2)
    def test_invalid_registration_rejected(self):
        self.full("a")
        for bad in ({"protocol_id": "proto-A", "anchor": "2026-09-14"},                                                            # anchor alone is not adoption
                    self.reg(policy_version="other"), self.reg(anchor="2026-09-13"), self.reg(anchor="nope"), self.reg(registered_at="2026-09-14"),
                    self.reg(extra=1), "proto-A"):
            with self.assertRaises(ContractError): self.counts(bad)
        board = scoreboard.build(self.st.root, synthetic=True, registration=self.reg())
        self.assertEqual(board["columns"]["replications"]["state"], "REGISTERED"); self.assertIn("proto-A/w0", board["columns"]["replications"]["windows"])


class ChallengeDecisionBoundaries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.tmp.name) / "s"; self.st = Store(self.root)
        self.st.designate_reviewer("rev-syn", "T", designated=False, now=D0); self.cs = ChallengeStore(self.root)
        self.h = hashlib.sha256(b"SYNTHETIC artifact").hexdigest()
        self.cs.create("ch-1", artifact={"artifact_type": "wheel", "sha256": self.h, "size_bytes": 18}, claim_id="claim-1", expected="exit 0", observed="exit 1", synthetic=True, criterion="artifact-reproduction-by-qualified-receipt", now=T0)
        self.tokf = pathlib.Path(self.tmp.name) / "tok"; self.tokf.write_text("T\n"); os.chmod(self.tokf, 0o600)
    def tearDown(self): self.tmp.cleanup()
    def test_no_untrusted_self_resolution(self):
        for disp in ("CONFIRMED", "REFUTED", "RESOLVED"):
            with self.assertRaises(ContractError): self.cs.dispose("ch-1", disp)                                              # no authority
            with self.assertRaises(ReviewAuthorityError): self.cs.dispose("ch-1", disp, reviewer_role="rev-syn", token="WRONG")
        w = self.cs.dispose("ch-1", "WITHDRAWN", reason="challenger retracts", now=T0); self.assertEqual(w["disposed_by"]["kind"], "challenger")
        self.assertEqual(self.cs.public_view(synthetic=True)[0]["disposed_by_authority"], "challenger")
        c = self.cs.dispose("ch-1", "CONFIRMED", reviewer_role="rev-syn", token="T", now=T0); self.assertEqual(c["disposed_by"]["authority"], "SYNTHETIC")
    def test_resolution_needs_actual_revised_bytes_and_structured_test(self):
        rev = b"SYNTHETIC artifact revised"; ra = {"artifact_type": "wheel", "sha256": hashlib.sha256(rev).hexdigest(), "size_bytes": len(rev)}
        # an EXECUTED verification record (receipt method on a qualified successful synthetic receipt binding the revised artifact)
        rec = self.st.import_submission({"schema_version": "receipt-1", "attempt_id": "rv", "activity_id": "act", "participant_id": "P", "group_id": None, "relationship": "UNRELATED", "execution_control": "SELF", "assistance": "NONE",
                                         "incentive_outcome_dependent": False, "outcome": "REPRODUCED", "observed_at": "2026-09-14T01:00:00.000000Z", "artifact_binding": ra, "release_identity": None, "environment": {}, "protocol_id": "syn"}, synthetic=True, received_at=T0)
        self.st.add_observation(rec["digest"], verify.observe(ra, data=rev, now=T0)); self.st.add_review(rec["digest"], "QUALIFIED", reviewer_role="rev-syn", token="T", now=T0)
        vid = self.cs.verify_revision("ch-1", revised_artifact=ra, method="receipt", receipt_digest=rec["digest"], now=T0)["verification_id"]
        with self.assertRaises(ContractError): self.cs.dispose("ch-1", "RESOLVED", reviewer_role="rev-syn", token="T", revised_artifact=ra, verification_id=vid)                     # digest alone
        with self.assertRaises(ContractError): self.cs.dispose("ch-1", "RESOLVED", reviewer_role="rev-syn", token="T", revised_artifact=ra, revised_bytes=b"other", verification_id=vid)   # bytes ≠ claim
        with self.assertRaises(ContractError): self.cs.dispose("ch-1", "RESOLVED", reviewer_role="rev-syn", token="T", revised_artifact=ra, revised_bytes=rev, verification_id="re-tested ok")   # label
        with self.assertRaises(ContractError): self.cs.dispose("ch-1", "RESOLVED", reviewer_role="rev-syn", token="T", revised_artifact=ra, revised_bytes=rev, verification_id="f" * 64)   # unknown record
        same = {"artifact_type": "wheel", "sha256": self.h, "size_bytes": 18}
        with self.assertRaises(ContractError): self.cs.dispose("ch-1", "RESOLVED", reviewer_role="rev-syn", token="T", revised_artifact=same, revised_bytes=b"SYNTHETIC artifact", verification_id=vid)
        r = self.cs.dispose("ch-1", "RESOLVED", reviewer_role="rev-syn", token="T", revised_artifact=ra, revised_bytes=rev, verification_id=vid, now=T0)
        self.assertTrue(r["resolution"]["revised_observation"]["verified"]); self.assertEqual(r["resolution"]["original_finding_retained"], True)
        view = self.cs.public_view(synthetic=True)[0]; self.assertEqual(view["resolution"]["verification_method"], "receipt"); self.assertNotIn("private", json.dumps(view))
        rc, out, err = run(challenge_cli.main, ["--store", str(self.root), "--synthetic", "dispose", "ch-1", "CONFIRMED", "--role", "rev-syn", "--token", "T"]); self.assertEqual(rc, 1); self.assertIn("--token-file", err); self.assertNotIn("REJECTED: T\n", err)
    def test_decision_context_private_permission_and_malformed_json(self):
        ds = DecisionStore(self.root); dig = "b" * 64
        with self.assertRaises(ContractError): ds.record("d1", "DISCARD_CLAIM", packet_manifest_digest=dig, claim_id="c", context="text", synthetic=True)
        with self.assertRaises(ContractError): ds.record("d1", "DISCARD_CLAIM", packet_manifest_digest=dig, claim_id="c", context={"nested": {"a": 1}}, synthetic=True)
        ds.record("d1", "DISCARD_CLAIM", packet_manifest_digest=dig, claim_id="c", context={"note": "SYNTHETIC private"}, export_permitted=True, synthetic=True, now=T0)
        ex = ds.export(synthetic=True); self.assertEqual(len(ex), 1); self.assertNotIn("context", ex[0]); self.assertNotIn("SYNTHETIC private", json.dumps(ex)); self.assertEqual(ds.export(synthetic=False), [])
        self.assertIn("not evidence of investment benefit", ds.all()[0]["disclaimer"])
        rc, out, err = run(decision_cli.main, ["--store", str(self.root), "--synthetic", "record", "d2", "DISCARD_CLAIM", "--packet-manifest-digest", dig, "--claim-id", "c", "--context", "{bad"]); self.assertEqual(rc, 1); self.assertIn("malformed JSON", err)
        rc, out, err = run(decision_cli.main, ["--store", str(self.root), "--synthetic", "record", "d3", "DISCARD_CLAIM", "--packet-manifest-digest", dig, "--claim-id", "c", "--context", '"str"']); self.assertEqual(rc, 1)


class SurfacesAndCli(unittest.TestCase):
    def test_board_validation_absent_invalid_synthetic(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "b.json"
            self.assertEqual(scoreboard.inspect_public(p)["status"], "ABSENT")
            p.write_text("{not json"); self.assertEqual(scoreboard.inspect_public(p)["status"], "INVALID")
            p.write_text(json.dumps(scoreboard.build(pathlib.Path(d) / "s", synthetic=True))); self.assertEqual(scoreboard.inspect_public(p)["status"], "SYNTHETIC_REFUSED")
            board = scoreboard.build(pathlib.Path(d) / "s", synthetic=False); p.write_text(json.dumps(board)); self.assertEqual(scoreboard.inspect_public(p)["status"], "OK")
            bad = json.loads(json.dumps(board)); bad["columns"]["replications"]["attempts"] = "<script>"; p.write_text(json.dumps(bad)); self.assertEqual(scoreboard.inspect_public(p)["status"], "INVALID")
            bad = json.loads(json.dumps(board)); bad["receipts_public"] = [{"attempt_id": "<img onerror=x>", "smuggled": 1}]; p.write_text(json.dumps(bad)); self.assertEqual(scoreboard.inspect_public(p)["status"], "INVALID")
            bad = json.loads(json.dumps(board)); del bad["columns"]["witnesses"]; p.write_text(json.dumps(bad)); self.assertEqual(scoreboard.inspect_public(p)["status"], "INVALID")
            from v3.web import render_scoreboard as rs
            html = rs.render(None, "INVALID"); self.assertIn("UNAVAILABLE", html); self.assertNotIn("=0", html)
            html = rs.render(None, "ABSENT"); self.assertIn("PENDING", html)
            html = rs.render(board, "OK"); self.assertIn("attempts=0", html); self.assertNotIn("<script>", html)
    def test_rest_and_mcp_report_unavailable_not_zero_for_invalid_file(self):
        from fastapi.testclient import TestClient
        from v3.api import server
        from v3.mcp import server as mcp_server
        path = REPO / "docs" / "receipts" / "scoreboard.json"; original = path.read_bytes()
        try:
            path.write_text("{broken")
            with TestClient(server.app) as c:
                body = c.get("/v1/receipts/scoreboard").json(); self.assertEqual(body["status"], "UNAVAILABLE"); self.assertNotIn("columns", body)
            fn = getattr(mcp_server.get_evidence_scoreboard, "fn", None) or mcp_server.get_evidence_scoreboard
            self.assertEqual(fn()["status"], "UNAVAILABLE")
        finally:
            path.write_bytes(original)
        with TestClient(server.app) as c:
            body = c.get("/v1/receipts/scoreboard").json(); self.assertIn("columns", body); self.assertFalse(body["synthetic"])
    def test_receipts_cli_failure_paths_and_token_sources(self):
        with tempfile.TemporaryDirectory() as d:
            st = str(pathlib.Path(d) / "s")
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "import", str(pathlib.Path(d) / "missing.json")]); self.assertEqual(rc, 1); self.assertIn("cannot read", err)
            bad = pathlib.Path(d) / "bad.json"; bad.write_text("{nope"); rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "import", str(bad)]); self.assertEqual(rc, 1); self.assertIn("malformed JSON", err)
            sp = pathlib.Path(d) / "sub.json"; sp.write_text(json.dumps(sub("cli-1"))); rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "import", str(sp)]); self.assertEqual(rc, 0, err); dig = json.loads(out)["digest"]
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "observe", dig, "--path", str(pathlib.Path(d) / "nofile"), "--allowed-root", d]); self.assertEqual(rc, 1); self.assertNotIn("Traceback", err)
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "observe", "0" * 64]); self.assertEqual(rc, 1)
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "review", dig, "QUALIFIED", "--role", "rev", "--token", "T"]); self.assertEqual(rc, 1); self.assertIn("--token-file", err); self.assertNotIn("Traceback", err)
            Store(st).designate_reviewer("rev", "T", designated=False, now=D0)
            tokf = pathlib.Path(d) / "tok"; tokf.write_text("T\n"); os.chmod(tokf, 0o644)
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "review", dig, "QUALIFIED", "--role", "rev", "--token-file", str(tokf)]); self.assertEqual(rc, 1); self.assertIn("chmod 0600", err)
            os.chmod(tokf, 0o600); rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "review", dig, "QUALIFIED", "--role", "rev", "--token-file", str(tokf)]); self.assertEqual(rc, 0, err); self.assertNotIn("\"T\"", out)
            rfd, wfd = os.pipe(); os.write(wfd, b"T"); os.close(wfd)
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "review", dig, "HELD", "--role", "rev", "--token-fd", str(rfd)]); os.close(rfd); self.assertEqual(rc, 0, err)
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "review", dig, "HELD", "--role", "rev", "--token-file", str(tokf), "--token-fd", "0"]); self.assertEqual(rc, 1)
            regf = pathlib.Path(d) / "reg.json"; regf.write_text(json.dumps({"protocol_id": "p", "anchor": "2026-09-14"}))
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "--registration", str(regf), "counts"]); self.assertEqual(rc, 1); self.assertIn("not evidence of adoption", err)
            rc, out, err = run(receipts_cli.main, ["--store", str(REPO / "docs" / "receipts" / "x"), "--synthetic", "counts"]); self.assertEqual(rc, 1); self.assertIn("E_PUBLIC_TREE", err)
            self.assertFalse((REPO / "docs" / "receipts" / "x").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
