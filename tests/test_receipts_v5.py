"""V7-005 acceptance: target-bound exact-release coverage (T1 size-only mismatch), correction placement and
history (T3), one consistent public view (T2), complete nested shapes / read-back, coded public errors (canary
probes), shared storage boundary, shared safe reads (deterministic swaps, FIFO, bounds, BUILD allowlist),
criterion-bound resolution, explain/history CLIs and receipt categories. Synthetic fixtures; the only real
input is the frozen public Lab bundle (offline replay)."""
import contextlib, hashlib, io, json, os, pathlib, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.receipts import counting, export, packet, safeio, scoreboard, storage, target as tgt, verify  # noqa: E402
from v3.receipts.contracts import ContractError, POLICY_VERSION  # noqa: E402
from v3.receipts.store import Store, ReviewAuthorityError  # noqa: E402
from v3.receipts.challenge import ChallengeStore  # noqa: E402
from v3.receipts.decision import DecisionStore  # noqa: E402
from v3.cli import receipts as receipts_cli, challenge as challenge_cli, decision as decision_cli, packet as packet_cli  # noqa: E402
from v3.lab import replay_check  # noqa: E402

T0 = datetime(2026, 9, 20, 12, 0, 0, 1, tzinfo=timezone.utc)
WHEEL = b"SYNTHETIC wheel v5 bytes\n"; SDIST = b"SYNTHETIC sdist v5 bytes.tar\n"


def run(main, argv):
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = main(argv)
    except SystemExit as e:
        rc = e.code
    return rc, out.getvalue(), err.getvalue()


def bind(t, data): h, n = verify.sha256_len(data); return {"artifact_type": t, "sha256": h, "size_bytes": n}


def sub(aid, *, pid="P-A", grp="G-A", proto="prog", obs=T0, data=WHEEL, t="wheel", outcome="REPRODUCED", act="REPLICATION", **extra):
    d = {"schema_version": "receipt-1", "attempt_id": aid, "activity_id": "act", "participant_id": pid, "group_id": grp, "relationship": "UNRELATED",
         "execution_control": "SELF", "assistance": "NONE", "incentive_outcome_dependent": False, "activity_type": act, "outcome": outcome,
         "observed_at": obs.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "artifact_binding": bind(t, data), "release_identity": {"tag": "v7.0.0", "source_sha": "5" * 40},
         "environment": {"os": "SynOS", "python": "3.12"}, "protocol_id": proto}
    d.update(extra); return d


class Fixture:
    """One populated synthetic-provenance-REAL store (test data marked real so public paths can be exercised in a temp dir)."""
    def __init__(self, tmp):
        self.root = pathlib.Path(tmp) / "s"; self.st = Store(self.root); self.st.designate_reviewer("rev", "R", designated=True, now=T0 - timedelta(days=1))   # a FIXED appointment before the fixed reviews: an appointment stamped by the wall clock made six tests fail from 2026-09-20T12:00Z on (V8-017)
        self.tok = pathlib.Path(tmp) / "tok"; self.tok.write_text("R\n"); os.chmod(self.tok, 0o600)
    def full(self, raw, data=WHEEL, state="QUALIFIED", imported=None):
        r = self.st.import_submission(raw, synthetic=False, received_at=imported or T0)
        self.st.add_observation(r["digest"], verify.observe(raw["artifact_binding"], data=data, now=T0))
        self.st.add_review(r["digest"], state, reviewer_role="rev", token="R", now=T0); return r


def target_for(*arts, label="RC", frm="rehearsal-record"):
    return tgt.build_target(label=label, generated_from=frm, tag="v7.0.0", version="7.0.0", source_sha="a" * 40, source_tree="b" * 40, now=T0,
                           artifacts=[{"artifact_type": t, "filename": f"yuclaw-7.0.0.{t}", "sha256": h, "size_bytes": n} for t, h, n in arts])


class TargetCoverage(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.f = Fixture(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_T1_and_target_partition(self):
        hw, nw = verify.sha256_len(WHEEL); hs, ns = verify.sha256_len(SDIST)
        self.f.full(sub("w-ok", pid="P1"))                                                                       # exact wheel
        self.f.full(sub("s-ok", pid="P2", data=SDIST, t="sdist"), data=SDIST)                                    # exact sdist
        old = b"OLD release wheel\n"; self.f.full(sub("old", pid="P3", data=old, release_identity={"tag": "v6.0.1", "source_sha": "6" * 40}), data=old)   # old release, exact bytes of another artifact
        rebuilt = WHEEL + b"x"; self.f.full(sub("rebuilt", pid="P4", data=rebuilt, release_identity={"tag": "v7.0.0", "source_sha": "a" * 40}), data=rebuilt)   # same tag, different bytes
        derived = counting.derive(self.f.st, synthetic=False)
        # T1: same type and hash, wrong length in the target → never qualifies
        t_wrong_len = target_for(("wheel", hw, nw + 1)); cov = tgt.coverage(derived, t_wrong_len)
        self.assertEqual(cov["successful_package_reproductions"], 0); self.assertFalse(cov["per_artifact"][0]["covered"])
        # exact target: wheel + sdist covered by their own receipts only; the old-release and rebuilt receipts never count for the target
        t_ok = target_for(("wheel", hw, nw), ("sdist", hs, ns)); cov = tgt.coverage(derived, t_ok)
        self.assertEqual((cov["artifacts_covered"], cov["artifacts_total"], cov["successful_package_reproductions"]), (2, 2, 2))
        # mismatched type (the wheel bytes declared as sdist in the target) never qualifies; wheel-only target never covers the sdist
        cov = tgt.coverage(derived, target_for(("sdist", hw, nw))); self.assertEqual(cov["successful_package_reproductions"], 0)
        cov = tgt.coverage(derived, target_for(("wheel", hw, nw))); self.assertEqual((cov["artifacts_covered"], cov["artifacts_total"]), (1, 1))
        # program-wide exact-artifact evidence counts every exact package reproduction (4), the target counts 2
        c = counting.counts(derived); self.assertEqual(c["artifacts"]["package_reproductions_successful"], 4)
        board = scoreboard.build(self.f.root, synthetic=False, target=t_ok, now=T0)
        ere = board["columns"]["replications"]["exact_release_evidence"]
        self.assertEqual(ere["program_exact_artifact_evidence"]["successful_package_reproductions"], 4); self.assertEqual(ere["exact_target_evidence"]["successful_package_reproductions"], 2)
        self.assertEqual(board["target"]["state"], "BOUND"); self.assertEqual(board["target"]["label"], "RC"); self.assertEqual(len(board["target"]["artifacts"][0]["sha256"]), 64)
        unbound = scoreboard.build(self.f.root, synthetic=False, now=T0)
        self.assertEqual(unbound["target"]["state"], "UNBOUND"); self.assertIsNone(unbound["columns"]["replications"]["exact_release_evidence"]["exact_target_evidence"]["successful_package_reproductions"])
        # identical RC/final bytes: a FINAL target with the same bytes is covered by the same receipts; a FINAL target from a rehearsal record is refused
        cov = tgt.coverage(derived, target_for(("wheel", hw, nw), label="FINAL", frm="phase2-release-record")); self.assertTrue(cov["per_artifact"][0]["covered"])
        with self.assertRaises(ContractError): target_for(("wheel", hw, nw), label="FINAL", frm="rehearsal-record")
        for bad in ({"target_format": "x"}, dict(t_ok, extra=1)):
            with self.assertRaises(ContractError): tgt.validate_target(bad)
        self.assertEqual(scoreboard.inspect_public(pathlib.Path(self.tmp.name) / "nope.json")["status"], "ABSENT")


class CorrectionPlacementAndHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.f = Fixture(self.tmp.name)
        self.reg = {"protocol_id": "prog", "anchor": "2026-09-15", "registered_at": "2026-09-14T06:00:00.000000Z", "policy_version": POLICY_VERSION}
    def tearDown(self): self.tmp.cleanup()
    def windows(self): return counting.counts(counting.derive(self.f.st, synthetic=False), registration=self.reg)["windows"]
    def test_window_pinned_to_original_lineage(self):
        base = datetime(2026, 9, 15, 6, 0, 0, 0, tzinfo=timezone.utc)
        r27 = self.f.full(sub("d27", pid="P1", obs=base + timedelta(days=27)), imported=base + timedelta(days=27))
        self.assertEqual(list(self.windows()), ["prog/w0"])
        corr = self.f.full(sub("d27", pid="P1", obs=base + timedelta(days=28), supersedes={"digest": r27["digest"], "reason": "reviewed correction"}), imported=base + timedelta(days=28))
        w = self.windows(); self.assertEqual(list(w), ["prog/w0"]); self.assertEqual(w["prog/w0"]["primary_attempts"], 1)               # day 27→28 correction stays in w0
        later = self.f.full(sub("d27", pid="P1", obs=base + timedelta(days=60), supersedes={"digest": corr["digest"], "reason": "later correction"}), imported=base + timedelta(days=60))
        self.assertEqual(list(self.windows()), ["prog/w0"])
        self.f.full(sub("new", pid="P1", obs=base + timedelta(days=28)), imported=base + timedelta(days=28))                            # a NEW attempt is distinct and lands in w1
        w = self.windows(); self.assertEqual(w["prog/w1"]["primary_attempts"], 1); self.assertEqual(w["prog/w0"]["primary_distinct_persons"], 1)
        pre = self.f.full(sub("pre", pid="P2", obs=datetime(2026, 9, 14, 1, 0, 0, 0, tzinfo=timezone.utc)), imported=datetime(2026, 9, 14, 1, 0, 0, 0, tzinfo=timezone.utc))
        self.f.full(sub("pre", pid="P2", obs=base + timedelta(days=3), supersedes={"digest": pre["digest"], "reason": "x"}), imported=base + timedelta(days=3))
        pa = self.f.full(sub("pa", pid="P3", obs=datetime(2026, 9, 14, 12, 0, 0, 0, tzinfo=timezone.utc)), imported=datetime(2026, 9, 14, 12, 0, 0, 0, tzinfo=timezone.utc))
        self.f.full(sub("pa", pid="P3", obs=base + timedelta(days=3), supersedes={"digest": pa["digest"], "reason": "x"}), imported=base + timedelta(days=3))
        self.f.full(sub("foreign", pid="P4", proto="wrong-program", obs=base), imported=base)
        self.f.st.import_submission(sub("new", pid="P1", obs=base + timedelta(days=28)), synthetic=False, received_at=base)               # exact duplicate collapses
        w = self.windows()
        self.assertEqual(w["prog/pre-registration"]["primary_attempts"], 1); self.assertEqual(w["prog/pre-anchor"]["primary_attempts"], 1)
        self.assertEqual(w["unregistered-protocol/wrong-program"]["eligibility"], "other_protocol"); self.assertEqual(w["prog/w1"]["primary_attempts"], 1)
        rows = export.project_many(counting.derive(self.f.st, synthetic=False), self.f.st, mode="public")
        r = [x for x in rows if x["attempt_id"] == "d27"][0]; self.assertTrue(r["corrected"]); self.assertEqual(r["version"], 3); self.assertEqual(r["first_observed_at"], (base + timedelta(days=27)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        self.assertIsNotNone(r["superseded_at"]); self.assertNotIn("receipt_digest", r); self.assertTrue(r["receipt_id"].startswith("r-"))
    def test_T3_eligibility_preserving_supersession(self):
        base = datetime(2026, 9, 15, 6, 0, 0, 0, tzinfo=timezone.utc)
        r = self.f.full(sub("a", pid="P1", obs=base + timedelta(days=2)), imported=base + timedelta(days=2))
        self.f.full(sub("b", pid="P2", obs=base + timedelta(days=3)), imported=base + timedelta(days=3))
        snap_a = scoreboard.build(self.f.root, synthetic=False, registration=self.reg, now=T0)
        self.f.full(sub("a", pid="P1", obs=base + timedelta(days=2), environment={"os": "SynOS 1.1", "python": "3.12"}, supersedes={"digest": r["digest"], "reason": "environment string corrected"}), imported=base + timedelta(days=9))
        snap_b = scoreboard.build(self.f.root, synthetic=False, registration=self.reg, now=T0 + timedelta(days=1))
        h = scoreboard.history(scoreboard.validate_board(snap_a), scoreboard.validate_board(snap_b))
        self.assertEqual(h["receipts_added"], []); self.assertEqual(h["receipts_removed"], []); self.assertFalse(h["window_movement_nonzero"])
        self.assertEqual(len(h["disposition_changes"]), 1); self.assertEqual(h["disposition_changes"][0]["kind"], "receipt_superseded"); self.assertTrue(h["disposition_changes"][0]["eligibility_preserved"])
        self.assertEqual(h["movement"]["qualified"]["delta"], 0); self.assertEqual(h["movement"]["qualified"]["growth_multiplier"], 1.0)
        self.assertEqual(scoreboard.history(scoreboard.validate_board(scoreboard.build(pathlib.Path(self.tmp.name) / "empty", synthetic=False, now=T0)), scoreboard.validate_board(snap_a))["movement"]["attempts"]["growth_multiplier"], "UNDEFINED (zero baseline)")
        # the CLI performs the comparison and refuses absent / incompatible snapshots
        pa, pb = pathlib.Path(self.tmp.name) / "a.json", pathlib.Path(self.tmp.name) / "b.json"; pa.write_bytes(scoreboard.canonical_bytes(snap_a)); pb.write_bytes(scoreboard.canonical_bytes(snap_b))
        rc, out, err = run(receipts_cli.main, ["--store", str(self.f.root), "history", str(pa), str(pb)]); self.assertEqual(rc, 0, err); self.assertEqual(json.loads(out)["receipts_added"], [])
        rc, out, err = run(receipts_cli.main, ["--store", str(self.f.root), "history", str(pa), str(pathlib.Path(self.tmp.name) / "missing.json")]); self.assertEqual(rc, 3); self.assertIn("ABSENT", err)
        bad = json.loads(pb.read_text()); bad["public_schema_version"] = "public-board-schema/0"; pb.write_text(json.dumps(bad))
        rc, out, err = run(receipts_cli.main, ["--store", str(self.f.root), "history", str(pa), str(pb)]); self.assertEqual(rc, 3)


class OneConsistentView(unittest.TestCase):
    def test_T2_byte_equal_payloads_across_surfaces_and_html(self):
        from fastapi.testclient import TestClient
        from v3.api import server
        from v3.mcp import server as mcp_server
        from v3.web import render_scoreboard as rs
        fn = getattr(mcp_server.get_evidence_scoreboard, "fn", None) or mcp_server.get_evidence_scoreboard
        path = REPO / "docs" / "receipts" / "scoreboard.json"; original = path.read_bytes()
        with tempfile.TemporaryDirectory() as d:
            f = Fixture(d); hw, nw = verify.sha256_len(WHEEL)
            f.full(sub("w1", pid="P1")); f.full(sub("f1", pid="P2", outcome="FAILED")); f.full(sub("h1", pid="P3"), state="HELD")
            f.full(sub("wit", pid="P4", act="WITNESS_REVIEW", t="methodology-page", data=b"<p>method</p>", outcome="REVIEWED"), data=b"<p>method</p>")
            cs = ChallengeStore(f.root); cs.create("c1", artifact=bind("wheel", WHEEL), claim_id="k", expected="a", observed="b", synthetic=False, now=T0)
            tp = pathlib.Path(d) / "target.json"; tp.write_text(json.dumps(target_for(("wheel", hw, nw)))); now = "2026-09-20T12:00:00.000001Z"
            try:
                rc, out, err = run(receipts_cli.main, ["--store", str(f.root), "--target", str(tp), "--now", now, "scoreboard", "--out", str(path)]); self.assertEqual(rc, 0, err)
                static = path.read_bytes().rstrip(b"\n")
                rc, out, err = run(receipts_cli.main, ["--store", str(f.root), "--target", str(tp), "--now", now, "scoreboard"]); self.assertEqual(out.rstrip("\n").encode(), static)   # CLI stdout == static file
                with TestClient(server.app) as c:
                    body = c.get("/v1/receipts/scoreboard").json()
                for k in scoreboard.REST_ENVELOPE: body.pop(k, None)                                                   # documented transport envelope only
                self.assertEqual(scoreboard.canonical_bytes(body), static)
                self.assertEqual(scoreboard.canonical_bytes(fn()), static)
                board = json.loads(static); self.assertEqual(board["columns"]["replications"]["attempts"], 3); self.assertEqual(board["columns"]["witnesses"]["receipted"], 1)
                self.assertEqual(board["columns"]["replications"]["exact_release_evidence"]["exact_target_evidence"]["successful_package_reproductions"], 1)
                html = rs.render(scoreboard.validate_board(board), "OK")
                self.assertIn("v7.0.0", html); self.assertIn(hw[:12], html); self.assertIn("CORRECTED", html) if board["columns"]["replications"]["corrected_attempts"] else None
                self.assertIn("witnesses", html); self.assertIn("affiliated", html.lower()); self.assertIn("program-wide", html); self.assertIn("exact-target", html)
            finally:
                path.write_bytes(original)


class PublicBoundary(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.f = Fixture(self.tmp.name); self.f.full(sub("w1")); self.board = scoreboard.build(self.f.root, synthetic=False, now=T0)
    def tearDown(self): self.tmp.cleanup()
    def status(self, b):
        p = pathlib.Path(self.tmp.name) / "b.json"; p.write_text(json.dumps(b)); return scoreboard.inspect_public(p)
    def test_nested_shapes_read_back_and_populated(self):
        ok = self.status(self.board); self.assertEqual(ok["status"], "OK")
        again = self.status(ok["board"]); self.assertEqual(again["status"], "OK"); self.assertEqual(scoreboard.canonical_bytes(again["board"]), scoreboard.canonical_bytes(ok["board"]))   # serialized and read back
        for mutate in (lambda b: b["receipts_public"][0].__setitem__("artifact_binding", None), lambda b: b["receipts_public"][0].__setitem__("artifact_binding", {}),
                       lambda b: b["receipts_public"][0].pop("release_identity"), lambda b: b["receipts_public"][0].__setitem__("release_identity", {"tag": "v7"}),
                       lambda b: b["receipts_public"][0].pop("receipt_id"), lambda b: b["receipts_public"][0].__setitem__("receipt_id", "0" * 64),
                       lambda b: b["target"].__setitem__("state", "BOUND"), lambda b: b["columns"]["witnesses"].__setitem__("state", "OBSERVED")):
            b = json.loads(json.dumps(self.board)); mutate(b); info = self.status(b); self.assertEqual(info["status"], "INVALID"); self.assertTrue(info["code"].startswith("E_"))
        from v3.web import render_scoreboard as rs
        b = json.loads(json.dumps(self.board)); b["receipts_public"][0]["artifact_binding"] = None; info = self.status(b); self.assertIn("UNAVAILABLE", rs.render(info["board"], info["status"]))
    def test_errors_never_echo_inputs(self):
        canary = "CANARY-PRIVATE-7f3e"
        probes = [lambda b: b.__setitem__("source_timestamp", canary), lambda b: b["receipts_public"][0].__setitem__("attempt_id", "bad id " + canary), lambda b: b["receipts_public"][0].__setitem__("observed_at", canary),
                  lambda b: b["columns"]["replications"].__setitem__("attempts", canary), lambda b: b.__setitem__(canary, 1), lambda b: b["definitions"].__setitem__(canary, "x"),
                  lambda b: b["challenges_public"].append({"challenge_id": canary}), lambda b: b["receipts_public"][0]["artifact_binding"].__setitem__("sha256", canary)]
        from fastapi.testclient import TestClient
        from v3.api import server
        from v3.mcp import server as mcp_server
        fn = getattr(mcp_server.get_evidence_scoreboard, "fn", None) or mcp_server.get_evidence_scoreboard
        path = REPO / "docs" / "receipts" / "scoreboard.json"; original = path.read_bytes()
        try:
            for i, mutate in enumerate(probes):
                b = json.loads(json.dumps(self.board)); mutate(b); info = self.status(b)
                self.assertEqual(info["status"], "INVALID", i); self.assertNotIn(canary, json.dumps(info), i); self.assertTrue(info["code"].startswith("E_"), i)
                path.write_text(json.dumps(b))
                with TestClient(server.app) as c:
                    body = c.get("/v1/receipts/scoreboard").json()
                self.assertEqual(body["status"], "UNAVAILABLE", i); self.assertNotIn(canary, json.dumps(body), i); self.assertNotIn(canary, json.dumps(fn()), i)
            path.write_bytes(b"\xff\xfe" + canary.encode("utf-16"))
            with TestClient(server.app) as c:
                body = c.get("/v1/receipts/scoreboard").json()
            self.assertEqual(body["code"], "E_UNREADABLE"); self.assertNotIn(canary, json.dumps(body))
        finally:
            path.write_bytes(original)
    def test_publication_policy_fail_closed_and_public_identity(self):
        orig = export._denylist_terms; export._denylist_terms = lambda: None
        try:
            self.assertFalse(export.text_publishable("hello")[0]); self.assertEqual(export.publication_policy()["denylist"], "UNAVAILABLE")
            with self.assertRaises(ContractError): scoreboard.build(self.f.root, synthetic=False, now=T0)                  # nothing is published without the policy material
        finally:
            export._denylist_terms = orig
        rows = self.board["receipts_public"]; rec = self.f.st.current_submissions()["w1"]
        self.assertEqual(rows[0]["receipt_id"], self.f.st.public_id(rec["digest"])); self.assertNotIn(rec["digest"], json.dumps(self.board))
        self.assertNotEqual(hashlib.sha256(rec["digest"].encode()).hexdigest()[:32], rows[0]["receipt_id"][2:])      # not a keyless hash of the private digest
        self.assertEqual(self.f.st.find(rows[0]["receipt_id"])["digest"], rec["digest"])


class StorageBoundary(unittest.TestCase):
    def test_every_store_kind_and_cli_refuses_public_tree_before_any_write(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d); (d / "release_manifest.json").write_text("{}"); (d / "docs").mkdir(); alias = d / "alias"; os.symlink(d / "docs", alias)
            for bad in (d / "docs" / "store", alias / "store"):
                for cls in (Store, ChallengeStore, DecisionStore):
                    with self.assertRaises(storage.StorageError): cls(bad)
                self.assertFalse(bad.exists())
                with self.assertRaises(storage.StorageError): scoreboard.build(bad, synthetic=True)
                for cli, argv in ((receipts_cli.main, ["--store", str(bad), "--synthetic", "counts"]), (challenge_cli.main, ["--store", str(bad), "--synthetic", "list"]), (decision_cli.main, ["--store", str(bad), "--synthetic", "export"])):
                    rc, out, err = run(cli, argv); self.assertEqual(rc, 1); self.assertIn("E_PUBLIC_TREE", err); self.assertFalse(bad.exists())
            ok = d / "private" / "store"; Store(ok); self.assertTrue(ok.is_dir()); self.assertEqual(oct(ok.stat().st_mode & 0o777), "0o700")
            f = d / "file"; f.write_text("x")
            with self.assertRaises(storage.StorageError): Store(f)
            unreadable = d / "unreadable"; unreadable.mkdir(); os.chmod(unreadable, 0)
            try:
                with self.assertRaises(storage.StorageError) as cm: Store(unreadable)
                self.assertEqual(cm.exception.code, "E_UNAVAILABLE")
            finally:
                os.chmod(unreadable, 0o700)
            with self.assertRaises(storage.StorageError): storage.resolve_store_root(d / "nope", create=False)


class SafeReads(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.d = pathlib.Path(self.tmp.name)
    def tearDown(self): safeio._TEST_HOOK = None; self.tmp.cleanup()
    def test_observation_and_resolution_reads_are_pinned(self):
        root = self.d / "root"; (root / "docs").mkdir(parents=True); (root / "docs" / "a.bin").write_bytes(b"INSIDE"); outside = self.d / "out"; outside.mkdir(); (outside / "a.bin").write_bytes(b"OUTSIDE"); os.chmod(outside / "a.bin", 0)
        swapped = []
        def hook(stage, rel):
            if stage == "dir-opened" and not swapped:
                swapped.append(1); os.rename(root / "docs", self.d / "moved"); os.symlink(outside, root / "docs")
        safeio._TEST_HOOK = hook
        try:
            self.assertEqual(verify.read_under_root(root / "docs" / "a.bin", [root]), b"INSIDE")                   # the pinned chain reads the original inode
        finally:
            os.chmod(outside / "a.bin", 0o600)
        self.assertEqual(swapped, [1])
        with self.assertRaises(safeio.SafeReadError) as cm: verify.read_under_root(root / "docs" / "a.bin", [root])          # static symlink now → refused
        self.assertEqual(cm.exception.code, "E_SYMLINK")
        with self.assertRaises(ContractError): verify.read_under_root(outside / "a.bin", [root])                          # alternate path outside root
        with self.assertRaises(safeio.SafeReadError) as cm: verify.read_under_root(root / "docs" / "missing.bin", [root]); self.assertEqual(cm.exception.code, "E_MISSING")
        fifo = root / "fifo"; os.mkfifo(fifo)
        with self.assertRaises(safeio.SafeReadError) as cm: verify.read_under_root(fifo, [root])
        self.assertEqual(cm.exception.code, "E_NOT_REGULAR")                                                               # a FIFO never blocks and is refused
        big = root / "big.bin"; big.write_bytes(b"x" * 1024)
        with self.assertRaises(safeio.SafeReadError) as cm: safeio.read_under_root(big, root, max_bytes=100)
        self.assertEqual(cm.exception.code, "E_TOO_LARGE")
        orig = safeio.platform_supported; safeio.platform_supported = lambda: (False, "simulated")
        try:
            with self.assertRaises(safeio.SafeReadError) as cm: verify.read_under_root(root / "big.bin", [root])
            self.assertEqual(cm.exception.code, "E_PLATFORM")
        finally:
            safeio.platform_supported = orig
        obs = verify.observe(bind("wheel", b"INSIDE"), path=root / "big.bin", allowed_roots=[root]); self.assertFalse(obs["verified"])
    def test_packet_build_allowlist_enforced_at_read_boundary(self):
        src = self.d / "src"; (src / "docs" / "replay").mkdir(parents=True); (src / "docs" / "packets").mkdir(); (src / "registry").mkdir()
        (src / "release_manifest.json").write_text("{}"); (src / "docs" / "capabilities.json").write_text("{}"); (src / "docs" / "replay" / "lab_replay_bundle.json").write_text("{}")
        private = self.d / "private"; private.mkdir(); (private / "secret.json").write_text('{"secret": "PRIVATE-BYTES"}')
        os.symlink(private / "secret.json", src / "docs" / "evidence_index.json")                                           # an allowed pathname pointing at private bytes
        with self.assertRaises(ValueError) as cm: packet.build(self.d / "pk", repo=src)
        self.assertIn("E_SYMLINK", str(cm.exception)); self.assertFalse((self.d / "pk" / "artifacts" / "docs" / "evidence_index.json").exists())
        os.unlink(src / "docs" / "evidence_index.json"); man = packet.build(self.d / "pk2", repo=src)
        self.assertEqual({f["path"] for f in man["files"] if f["status"] == "INCLUDED"} , {"docs/replay/lab_replay_bundle.json", "docs/capabilities.json", "release_manifest.json"})
        self.assertNotIn("PRIVATE-BYTES", b"".join(p.read_bytes() for p in (self.d / "pk2").rglob("*") if p.is_file()).decode(errors="replace"))
    def test_frozen_packet_still_verifies(self):
        rc, out, err = run(packet_cli.main, ["build", str(self.d / "real"), "--source", str(REPO)]); self.assertEqual(rc, 0, err)
        rc, out, err = run(packet_cli.main, ["verify", str(self.d / "real"), "--json"]); self.assertEqual((rc, json.loads(out)["result"]), (0, "SUCCESS"))


class CriterionBoundResolution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.f = Fixture(self.tmp.name); self.cs = ChallengeStore(self.f.root)
        self.rev = WHEEL + b" revised"; self.ra = bind("wheel", self.rev)
        rec = self.f.full(sub("q", pid="P9", data=self.rev), data=self.rev); self.receipt_digest = rec["digest"]
    def tearDown(self): self.tmp.cleanup()
    def test_wrong_criterion_unknown_verifier_general_and_fix(self):
        self.cs.create("gen", artifact=bind("wheel", WHEEL), claim_id="behaviour-1", expected="prints X", observed="prints Y", synthetic=False, criterion="general", now=T0)
        v = self.cs.verify_revision("gen", revised_artifact=self.ra, method="receipt", receipt_digest=self.receipt_digest, now=T0)
        self.assertEqual(v["result"], "NOT_EVALUATED"); self.assertIn("reviewer evaluation", v["reason"])                       # a qualified receipt cannot resolve a behaviour claim
        with self.assertRaises(ContractError): self.cs.dispose("gen", "RESOLVED", reviewer_role="rev", token="R", revised_artifact=self.ra, revised_bytes=self.rev, verification_id=v["verification_id"])
        with self.assertRaises(ContractError): self.cs.verify_revision("gen", revised_artifact=self.ra, method="bogus")
        ev_bad = self.cs.evaluate("gen", reviewer_role="rev", token="R", outcome="NOT_SATISFIED", statement="output still differs", revised_artifact=self.ra, now=T0)
        with self.assertRaises(ContractError): self.cs.dispose("gen", "RESOLVED", reviewer_role="rev", token="R", revised_artifact=self.ra, revised_bytes=self.rev, evaluation_id=ev_bad["evaluation_id"])
        other = bind("wheel", self.rev + b"2"); ev_other = self.cs.evaluate("gen", reviewer_role="rev", token="R", outcome="SATISFIED", statement="for another artifact", revised_artifact=other, now=T0)
        with self.assertRaises(ContractError): self.cs.dispose("gen", "RESOLVED", reviewer_role="rev", token="R", revised_artifact=self.ra, revised_bytes=self.rev, evaluation_id=ev_other["evaluation_id"])
        self.f.st.designate_reviewer("syn", "S", designated=False)
        with self.assertRaises(ReviewAuthorityError): self.cs.evaluate("gen", reviewer_role="syn", token="S", outcome="SATISFIED", statement="x", revised_artifact=self.ra)   # authority failure
        ev = self.cs.evaluate("gen", reviewer_role="rev", token="R", outcome="SATISFIED", statement="re-ran the documented command; output now X; compared to the original", revised_artifact=self.ra, now=T0)
        r = self.cs.dispose("gen", "RESOLVED", reviewer_role="rev", token="R", revised_artifact=self.ra, revised_bytes=self.rev, evaluation_id=ev["evaluation_id"], now=T0)
        self.assertEqual(r["resolution"]["verification_method"], "reviewer-evaluation"); self.assertEqual(self.cs.public_view(synthetic=False)[0]["criterion"], "general")
        # verifier-backed criterion: receipt method resolves only that criterion, with the exact artifact
        self.cs.create("rep", artifact=bind("wheel", WHEEL), claim_id="repro-1", expected="a", observed="b", synthetic=False, criterion="artifact-reproduction-by-qualified-receipt", now=T0)
        v = self.cs.verify_revision("rep", revised_artifact=self.ra, method="packet-verify", packet_dir=self.tmp.name, now=T0); self.assertEqual(v["result"], "NOT_EVALUATED")   # wrong verifier for the criterion
        v = self.cs.verify_revision("rep", revised_artifact=self.ra, method="receipt", receipt_digest=self.receipt_digest, now=T0); self.assertEqual(v["result"], "SUCCESS"); self.assertEqual(v["verifier"]["module"], "v3.receipts.counting.derive")
        with self.assertRaises(ContractError): self.cs.dispose("rep", "RESOLVED", reviewer_role="rev", token="R", revised_artifact=self.ra, revised_bytes=self.rev, evaluation_id=ev["evaluation_id"])   # evaluation cannot substitute for the verifier
        r = self.cs.dispose("rep", "RESOLVED", reviewer_role="rev", token="R", revised_artifact=self.ra, revised_bytes=self.rev, verification_id=v["verification_id"], now=T0)
        self.assertEqual(r["resolution"]["criterion"], "artifact-reproduction-by-qualified-receipt")
        self.assertEqual(len(self.cs.history("rep")), 2); self.assertEqual(self.cs.history("rep")[0]["disposition"], "OPEN")        # original adverse finding preserved


class ExplainAndCategories(unittest.TestCase):
    def test_explain_cli_and_category_counts(self):
        with tempfile.TemporaryDirectory() as d:
            f = Fixture(d); r = f.full(sub("w1", pid="P1")); f.full(sub("h1", pid="P2"), state="HELD")
            f.full(sub("ref", pid="P3", act="REFUSAL", t="product-response", data=b"refusal response bytes", outcome="REFUSED", private={"request": "PRIVATE REQUEST TEXT"}), data=b"refusal response bytes")
            f.full(sub("aud", pid="P4", act="AUDIT_BREAK_ATTEMPT", outcome="BREAK_FOUND"))
            with self.assertRaises(ContractError): sub_ = f.st.import_submission(sub("bad", act="REFUSAL", t="product-response", data=b"x", outcome="REFUSED", public_note="hi", disclosure_permitted=True), synthetic=False)
            with self.assertRaises(ContractError): f.st.import_submission(sub("bad2", act="WITNESS_REVIEW", outcome="REPRODUCED"), synthetic=False)
            board = scoreboard.build(f.root, synthetic=False, now=T0); cols = board["columns"]
            self.assertEqual((cols["refusals"]["receipted"], cols["refusals"]["qualified"], cols["audits"]["by_outcome"].get("BREAK_FOUND")), (1, 1, 1))
            self.assertEqual(cols["witnesses"]["note"], "receipted: 0 · unreceipted relationships not counted"); self.assertNotIn("PRIVATE REQUEST TEXT", json.dumps(board))
            self.assertEqual(cols["replications"]["attempts"], 2)
            rc, out, err = run(receipts_cli.main, ["--store", str(f.root), "explain", "w1"]); self.assertEqual(rc, 0, err); e = json.loads(out)
            self.assertTrue(e["qualified"]); self.assertEqual(e["counting"]["eligibility"], "unwindowed"); self.assertNotIn("P1", out); self.assertNotIn("private", e)
            rc, out, err = run(receipts_cli.main, ["--store", str(f.root), "explain", "h1"]); e = json.loads(out); self.assertFalse(e["qualified"]); self.assertIn("R_REVIEW_STATE", e["reason_codes"])
            rc, out, err = run(receipts_cli.main, ["--store", str(f.root), "explain", f.st.public_id(r["digest"]), "--private"]); self.assertEqual(json.loads(out)["private"]["participant_id"], "P1")
            rc, out, err = run(receipts_cli.main, ["--store", str(f.root), "explain", "nope"]); self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
