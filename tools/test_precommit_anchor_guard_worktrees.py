#!/usr/bin/env python3
"""Linked-worktree evidence for the dispatcher shim (V7-004 A1). Disposable repositories only.
Reuses the fixture builder from test_precommit_anchor_guard (same directory)."""
import os, pathlib, shutil, subprocess, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_precommit_anchor_guard import Repo, ANCHOR, LEDGER, SRC_V1, SRC_V2, sha, SYNTH_ROOT  # noqa: E402

KEY = "yuclaw.anchorguard.enrolledtoplevel"


class Worktrees(unittest.TestCase):
    def setUp(self):
        self.r = Repo(self._testMethodName); i = self.r.install(); self.assertEqual(i.returncode, 0, i.stderr)
        self.assertEqual(self.r.git("config", "--get", KEY).stdout.decode().strip(), str(self.r.path.resolve()))
        self.wt = SYNTH_ROOT / f"{self._testMethodName}-sibling"
        if self.wt.exists(): shutil.rmtree(self.wt)
        self.r.git("worktree", "add", "-q", "-b", "sibling", str(self.wt))
        self.head0 = self.r.head()
    def wgit(self, *args, env=None, check=True):
        r = subprocess.run(["git", *args], cwd=self.wt, env={**self.r.env, **(env or {})}, capture_output=True)
        if check and r.returncode: raise AssertionError(f"git {args} failed: {r.stderr.decode(errors='replace')}")
        return r
    def whead(self): return self.wgit("rev-parse", "HEAD").stdout.decode().strip()
    def test_enrolled_checkout_enforces_bad_and_good(self):
        self.r.write(ANCHOR, SRC_V2); self.r.git("add", ANCHOR)
        bad = self.r.commit(); self.assertNotEqual(bad.returncode, 0); self.assertIn("drift", bad.stdout.decode() + bad.stderr.decode()); self.assertEqual(self.r.head(), self.head0)
        self.r.write_ledger(sha(SRC_V2)); self.r.git("add", LEDGER)
        good = self.r.commit(); self.assertEqual(good.returncode, 0, good.stderr.decode()); self.assertNotEqual(self.r.head(), self.head0)
    def test_unenrolled_sibling_without_checker_ordinary_and_path_limited_commits_pass(self):
        # sibling drops the checker entirely, then commits an anchored change + doc: dispatcher exits 0 (prior behavior)
        self.wgit("rm", "-q", "-r", "tools"); c0 = self.wgit("commit", "-q", "-m", "sibling: drop tools", check=False)
        self.assertEqual(c0.returncode, 0, c0.stderr.decode()); self.assertFalse((self.wt / "tools").exists())
        (self.wt / ANCHOR).write_bytes(SRC_V2); (self.wt / "docs/readme.md").write_bytes(b"# sibling\n"); self.wgit("add", "-A")
        h = self.whead()
        c1 = self.wgit("commit", "-q", "-m", "sibling: path-limited", "--", "docs/readme.md", check=False); self.assertEqual(c1.returncode, 0, c1.stderr.decode()); self.assertNotEqual(self.whead(), h)
        c2 = self.wgit("commit", "-q", "-m", "sibling: ordinary (anchored change, unenforced)", check=False); self.assertEqual(c2.returncode, 0, c2.stderr.decode())
        self.assertEqual(self.r.head(), self.head0)                                     # enrolled checkout untouched
    def test_alternate_index_propagates_through_git_commit_in_enrolled_checkout(self):
        alt = self.r.path / ".git/alt.index"; env = {"GIT_INDEX_FILE": str(alt)}
        self.r.git("read-tree", "HEAD", env=env); self.r.write(ANCHOR, SRC_V2); self.r.git("add", ANCHOR, env=env); self.r.write(ANCHOR, SRC_V1)
        c = self.r.git("commit", "-q", "-m", "alt index bad", env=env, check=False)
        self.assertNotEqual(c.returncode, 0); self.assertIn("index=alt.index", c.stdout.decode() + c.stderr.decode()); self.assertEqual(self.r.head(), self.head0)
    def test_missing_enrolled_checker_fails_closed(self):
        self.r.git("rm", "-q", "tools/check_truncation_anchors_staged.py")
        c = self.r.commit(); self.assertEqual(c.returncode, 1); self.assertIn("missing tools/check_truncation_anchors_staged.py", c.stderr.decode()); self.assertEqual(self.r.head(), self.head0)
        self.r.git("reset", "-q", "--", "tools/check_truncation_anchors_staged.py"); self.r.git("checkout", "-q", "--", "tools/check_truncation_anchors_staged.py")
    def test_ambiguous_or_unreadable_enrollment_fails_closed(self):
        self.r.git("config", "--add", KEY, str(self.r.path.resolve()) + "-other")
        self.r.write("docs/readme.md", b"# x\n"); self.r.git("add", "docs/readme.md")
        c = self.r.commit(); self.assertEqual(c.returncode, 1); self.assertIn("ambiguous enrollment", c.stderr.decode())
        self.r.git("config", "--unset-all", KEY); self.r.git("config", KEY, str(self.r.path.resolve()) + "-gone")
        c2 = self.r.commit(); self.assertEqual(c2.returncode, 1); self.assertIn("unreadable", c2.stderr.decode())
        self.r.git("config", "--unset-all", KEY); self.r.git("config", KEY, str(self.r.path.resolve()))
        ok = self.r.commit(); self.assertEqual(ok.returncode, 0, ok.stderr.decode())
    def test_reinstall_idempotent_and_different_checkout_enrollment_refused(self):
        a = self.r.install(); self.assertEqual(a.returncode, 0); self.assertIn("already installed", a.stdout); self.assertIn("already enrolled", a.stdout)
        # installing FROM the sibling (which still has the tools) must refuse: a different checkout is enrolled
        s = subprocess.run(["sh", str(self.wt / "tools/install_precommit_anchor_guard.sh")], cwd=self.wt, env=self.r.env, capture_output=True, text=True)
        self.assertEqual(s.returncode, 3); self.assertIn("different checkout is already enrolled", s.stderr)
        self.assertEqual(self.r.git("config", "--get-all", KEY).stdout.decode().split(), [str(self.r.path.resolve())])
        u = self.r.install("--uninstall"); self.assertEqual(u.returncode, 0); self.assertFalse(self.r.hook_path().exists())
        self.assertEqual(self.r.git("config", "--get-all", KEY, check=False).stdout.decode().strip(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
