"""8.0.1 C05/C10 — the workbench is reachable as `yuclaw workbench …`, and its selftest runs from the package alone.

`yuclaw workbench` is a thin delegate: same parser, same output and the same exit codes as `python -m v8.workbench`;
showing help starts no server and creates nothing. The selftest uses the packaged fixtures and the real server, export
and verification code in a temporary workspace (no pytest, no repository files); where no isolation backend passes its
live probe it reports the SHD route CLOSED and checks that it is — and `--require-isolation` then FAILS, never skips."""
import json, os, pathlib, subprocess, sys, tempfile, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]


def run(args, cwd, env_extra=None):
    env = dict(os.environ, PYTHONPATH=str(REPO), HOME=str(cwd), TMPDIR=str(cwd)); env.update(env_extra or {})
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=600, cwd=str(cwd), env=env)
    return r.returncode, r.stdout, r.stderr


class Entry(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="v801-entry-"))

    def test_the_top_level_help_lists_the_workbench_and_its_help_names_the_four_modules_and_creates_nothing(self):
        rc, out, _ = run(["-m", "v3.cli", "--help"], self.tmp); self.assertEqual(rc, 0); self.assertIn("workbench", out); self.assertIn("SHD/EVO/COM/PRC", out)
        rc, out, _ = run(["-m", "v3.cli", "workbench", "--help"], self.tmp); self.assertEqual(rc, 0); flat = " ".join(out.split())
        for needle in ("usage: yuclaw workbench", "127.0.0.1 only", "SHD Distillation Shield", "EVO Evolution Evidence Audit", "COM Research Commons Guard", "PRC Independent Practice", "Linux with Landlock", "Showing help starts nothing"):
            self.assertIn(needle, flat)
        self.assertEqual([p.name for p in self.tmp.iterdir() if p.name not in (".cache",)], [])                                       # no workspace, no credential, no server state

    def test_the_delegate_and_the_module_form_agree_on_output_and_exit_codes(self):
        missing = str(self.tmp / "no-such-workspace")
        for args in (["--help"], [], ["verify-export", str(self.tmp / "absent.zip")], ["status", "--workspace", missing], ["guide"], ["definitely-not-a-command"]):
            a = run(["-m", "v8.workbench", *args], self.tmp); b = run(["-m", "v3.cli", "workbench", *args], self.tmp)
            norm = lambda t: t.replace("python3 -m v8.workbench", "PROG").replace("yuclaw workbench", "PROG").replace(" " * 24, " ").split()
            self.assertEqual(a[0], b[0], args); self.assertEqual(norm(a[1]), norm(b[1]), args)
            if a[0] == 2:
                self.assertIn("usage:", a[2] + b[2])
        self.assertFalse((self.tmp / "no-such-workspace").exists())


class Selftest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="v801-selftest-"))

    def test_it_runs_from_the_package_alone_compares_with_recorded_results_and_cleans_up(self):
        rc, out, err = run(["-m", "v3.cli", "workbench", "selftest", "--json"], self.tmp); self.assertEqual(rc, 0, out[-1500:] + err[-500:]); r = json.loads(out)
        self.assertEqual(r["result"], "PASS"); names = " | ".join(c["name"] for c in r["checks"])
        for needle in ("recorded result (IN_RANGE)", "recorded result (OUT_OF_RANGE)", "incompatible comparison stays refused", "fresh workspace over HTTP", "one changed figure is rejected", "409 refusal", "fails closed", "SHD:", "temporary selftest state was removed"):
            self.assertIn(needle, names)
        self.assertIn("repository test suite", r["not_run"]); self.assertEqual([p for p in self.tmp.glob("yuclaw-selftest-*")], [])
        rc2, out2, _ = run(["-m", "v8.workbench", "selftest"], self.tmp); self.assertEqual(rc2, 0); self.assertIn("[selftest] PASS", out2)
        src = (REPO / "v8" / "workbench" / "selftest.py").read_text(); self.assertNotIn("import pytest", src); self.assertNotIn('"tests/', src)

    def test_without_a_verified_isolation_backend_the_route_is_reported_closed_and_require_isolation_fails(self):
        pin = {"YUCLAW_SHD_BACKEND": "bwrap"}                                                                                           # pinning never skips the probe; bubblewrap is verified on no host
        rc, out, _ = run(["-m", "v8.workbench", "selftest", "--json"], self.tmp, pin); r = json.loads(out)
        if r["isolation"]["backend"] == "bwrap":
            self.skipTest("bubblewrap passed its live probe on this host, so the unsupported-host path cannot be staged here")
        self.assertEqual((rc, r["result"]), (0, "PASS")); self.assertIsNone(r["isolation"]["backend"]); self.assertIn("CLOSED on this host", r["isolation"]["shd_admission_route"])
        self.assertTrue(any("CLOSED (fail-closed), not skipped" in c["name"] and c["ok"] for c in r["checks"])); self.assertFalse(any("verified a fictional bundle" in c["name"] for c in r["checks"]))
        rc, out, _ = run(["-m", "v8.workbench", "selftest", "--json", "--require-isolation"], self.tmp, pin); r = json.loads(out)
        self.assertEqual((rc, r["result"]), (1, "FAIL")); self.assertTrue(any("--require-isolation" in c["name"] and not c["ok"] and "not a skip" in c["detail"] for c in r["checks"]))


if __name__ == "__main__":
    unittest.main()
