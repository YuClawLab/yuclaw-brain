"""Nightly status adapter tests (v7): fixture logs only; fake Pages reader and fake transport."""
import pathlib, sys, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.ops import nightly_status as ns  # noqa: E402

LAUNCHER = "python3 -m v3.web.render_landing || exit 2\n/usr/bin/python3 tools/check_weekly_note.py --require-contract v3 || exit 24\n/usr/bin/python3 tools/check_truncation_ledger.py || exit 44\n/usr/bin/python3 tools/deploy_verify.py --timeout 900 || exit 15\n"
SUCCESS = ["[render_landing] wrote docs/index.html (1 bytes, 79 signals)", "[registry] chain OK", "[note-gate] reconciled: 64 events", "[truncation-gate] OK — 13 ledger entries",
           "[refresh_v3_pages] pushed at 2026-09-08 23:00 UTC", "[deploy-verify] OK: all 41 artifacts live and byte-identical", "[refresh_v3_pages] deploy-verified at 2026-09-08 23:02 UTC"]
FAIL_TRUNC = ["[render_landing] wrote docs/index.html (1 bytes, 79 signals)", "[registry] chain OK", "[consumer-posture] OK — five personas green", "[truncation-gate] 1 finding(s):", "  FAIL drift: evidence_tier_boundary anchor v3/universe_tiers.py changed"]
FAIL_DEPLOY = ["[render_landing] wrote docs/index.html (1 bytes, 79 signals)", "[registry] chain OK", "[refresh_v3_pages] pushed at 2026-09-04 23:00 UTC", "[deploy-verify] STALE YUCLAW_User_Guide.pdf — live content does not match local build", "[deploy-verify] FAIL: 1/41 artifacts not live after 900s"]
INTERRUPTED = ["[render_landing] wrote docs/index.html (1 bytes, 79 signals)", "[registry] chain OK"]


class Adapter(unittest.TestCase):
    def setUp(self): self.exits = ns.exit_table(LAUNCHER)
    def test_exit_table(self):
        self.assertEqual(self.exits["tools/check_truncation_ledger.py"], 44); self.assertEqual(self.exits["tools/deploy_verify.py"], 15); self.assertEqual(self.exits["v3.web.render_landing"], 2)
    def test_success_failure_interruption_and_stale(self):
        log = SUCCESS + FAIL_TRUNC + FAIL_DEPLOY + INTERRUPTED
        segs = ns.segment_runs(log); self.assertEqual(len(segs), 4)
        s1 = ns.classify_run(log, segs[0], self.exits); self.assertEqual(s1.state, "COMPLETED"); self.assertTrue(s1.pushed and s1.deploy_verified); self.assertEqual(s1.start_stamp, "2026-09-08 23:00 UTC")
        s2 = ns.classify_run(log, segs[1], self.exits); self.assertEqual(s2.state, "FAILED"); self.assertEqual(s2.failing_gate, "truncation-gate"); self.assertEqual(s2.exit_code, 44); self.assertFalse(s2.pushed); self.assertEqual(s2.last_ok_stage, "consumer-posture")
        s3 = ns.classify_run(log, segs[2], self.exits); self.assertEqual(s3.state, "FAILED"); self.assertTrue(s3.pushed); self.assertFalse(s3.deploy_verified); self.assertEqual(s3.failing_gate, "deploy-verify"); self.assertEqual(s3.exit_code, 15)
        s4 = ns.classify_run(log, segs[3], self.exits); self.assertEqual(s4.state, "INTERRUPTED_OR_RUNNING")
        stale = ns.classify_run(log + ["[render_landing] wrote next run"], segs[3], self.exits); self.assertEqual(stale.state, "STALE")
    def test_build_reader_and_transport_failures_stay_explicit(self):
        log = SUCCESS; st = ns.classify_run(log, ns.segment_runs(log)[0], self.exits)
        st = ns.attach_build(st, lambda sha: {"status": "errored", "commit": sha}, "abc"); self.assertEqual(st.build["status"], "errored"); self.assertEqual(st.state, "COMPLETED")
        def boom(sha): raise RuntimeError("api down")
        st = ns.attach_build(st, boom, "abc"); self.assertIn("error", st.build)
        rep = ns.deliver({"state": st.state}, lambda r: False); self.assertEqual(rep["delivery"], "DELIVERY_FAILED"); self.assertEqual(rep["state"], "COMPLETED")
        rep = ns.deliver({"state": "FAILED"}, lambda r: (_ for _ in ()).throw(RuntimeError("no network"))); self.assertEqual(rep["delivery"], "DELIVERY_FAILED"); self.assertEqual(rep["state"], "FAILED")
        rep = ns.deliver({"state": "FAILED"}, lambda r: True); self.assertEqual(rep["delivery"], "DELIVERED"); self.assertEqual(rep["state"], "FAILED")   # delivery never upgrades a failure
    def test_real_launcher_exit_table_covers_known_gates(self):
        t = ns.exit_table((REPO / "cron/refresh_v3_pages.sh").read_text())
        self.assertEqual(t.get("tools/check_truncation_ledger.py"), 44); self.assertEqual(t.get("tools/check_weekly_note.py"), 24); self.assertEqual(t.get("tools/yuclaw_weekly_note.py"), 23); self.assertEqual(t.get("tools/deploy_verify.py"), 15)


class Preview(unittest.TestCase):
    def test_preview_states_identity_and_delivery_never_upgrade(self):
        import json, os, subprocess, tempfile
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d); launcher = d / "launcher.sh"; launcher.write_text(LAUNCHER)
            self.assertEqual(ns.preview(d / "missing.log", launcher)["state"], "NO_LOG")                                # missing evidence is explicit
            (d / "empty.log").write_text("no runs here\n"); self.assertEqual(ns.preview(d / "empty.log", launcher)["state"], "NO_RUN_FOUND")
            repo = d / "repo"; repo.mkdir(); subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example", "commit", "-q", "--allow-empty", "-m", "auto: v3.0 page refresh 2026-09-08 23:00 UTC"], check=True)
            sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
            (d / "ok.log").write_text("\n".join(SUCCESS) + "\n"); rep = ns.preview(d / "ok.log", launcher, repo)
            self.assertEqual(rep["run"]["state"], "COMPLETED"); self.assertEqual(rep["identity"]["run_commit"], sha); self.assertEqual(len(rep["identity"]["launcher_sha256"]), 64)
            self.assertTrue(rep["delivery"].startswith("NOT_ATTEMPTED")); self.assertIsNone(rep["run"]["build"]["status"])
            (d / "int.log").write_text("\n".join(SUCCESS + INTERRUPTED) + "\n"); rep = ns.preview(d / "int.log", launcher, repo)
            self.assertEqual(rep["run"]["state"], "INTERRUPTED_OR_RUNNING"); self.assertIsNone(rep["identity"]["run_commit"])          # no stamp → no commit inferred
            (d / "fail.log").write_text("\n".join(FAIL_TRUNC) + "\n"); rep = ns.preview(d / "fail.log", launcher, repo, builds_reader=lambda s: {"status": "errored"})
            self.assertEqual((rep["run"]["state"], rep["run"]["exit_code"], rep["run"]["failing_gate"]), ("FAILED", 44, "truncation-gate"))
            self.assertIsNone(rep["run"]["build"]["status"]); self.assertIn("no commit", rep["run"]["build"]["note"])                    # a run that failed before its push has no commit to query
            failed_preview = rep
            rep = ns.preview(d / "ok.log", launcher, repo, builds_reader=lambda s: {"status": "errored", "commit": s}); self.assertEqual(rep["run"]["build"]["status"], "errored")
            delivered = ns.deliver(failed_preview, lambda r: False); self.assertEqual(delivered["delivery"], "DELIVERY_FAILED"); self.assertEqual(delivered["run"]["state"], "FAILED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
