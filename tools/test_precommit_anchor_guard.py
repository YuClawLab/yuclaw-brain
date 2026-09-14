#!/usr/bin/env python3
"""Disposable-repository tests for the staged truncation-anchor guard (V7-003F).
Builds synthetic Git repositories (under ANCHOR_GUARD_SYNTH_DIR or a temp dir), copies the
CANDIDATE tools (validator, staged guard, hook shim, installer) into each fixture repo so the
installed entry runs the real candidate code, and exercises real `git commit` through the hook
plus direct guard invocations with alternate indexes. Fixtures are synthetic; no production
history, no network, no database. Standard library only."""
import hashlib, json, os, pathlib, shutil, stat, subprocess, sys, tempfile, unittest

TOOLS = pathlib.Path(os.environ.get("ANCHOR_GUARD_TOOLS", pathlib.Path(__file__).resolve().parent))
SYNTH_ROOT = pathlib.Path(os.environ.get("ANCHOR_GUARD_SYNTH_DIR", tempfile.mkdtemp(prefix="anchor_guard_synth_")))
SYNTH_ROOT.mkdir(parents=True, exist_ok=True)
CAND_FILES = ["check_truncation_ledger.py", "check_truncation_anchors_staged.py", "hooks/pre-commit", "install_precommit_anchor_guard.sh"]
ANCHOR = "v3/anchored_site.py"
LEDGER = "registry/truncation_ledger.json"
SRC_V1 = b'"""Synthetic anchored module (fixture)."""\nTHRESHOLD_NOTE = "fixture"\n\n\ndef keep(rows):\n    return [r for r in rows if r.get("ok")]\n'
SRC_V2 = b'"""Synthetic anchored module (fixture) - docstring changed only."""\nTHRESHOLD_NOTE = "fixture"\n\n\ndef keep(rows):\n    return [r for r in rows if r.get("ok")]\n'


def sha(b: bytes) -> str: return hashlib.sha256(b).hexdigest()


class Repo:
    """A disposable Git repository with inherited Git context cleared."""
    def __init__(self, name):
        self.path = SYNTH_ROOT / name
        if self.path.exists(): shutil.rmtree(self.path)
        self.path.mkdir(parents=True)
        self.home = SYNTH_ROOT / f"{name}.home"; self.home.mkdir(exist_ok=True)
        base = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        base.update({"HOME": str(self.home), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                     "GIT_TERMINAL_PROMPT": "0", "LANG": "C", "PYTHONDONTWRITEBYTECODE": "1",
                     "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                     "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"})
        self.env = base
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "fixture"); self.git("config", "user.email", "fixture@example.invalid")
        for rel in CAND_FILES:
            dst = self.path / "tools" / rel; dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(TOOLS / rel, dst)
        (self.path / "v3").mkdir(); (self.path / "registry").mkdir(); (self.path / "docs").mkdir()
        self.write(ANCHOR, SRC_V1); self.write("docs/readme.md", b"# fixture\n")
        self.write_ledger(sha(SRC_V1))
        self.git("add", "-A"); self.git("commit", "-q", "-m", "fixture: initial consistent state")
    def git(self, *args, env=None, check=True, input=None):
        r = subprocess.run(["git", *args], cwd=self.path, env={**self.env, **(env or {})}, capture_output=True, input=input)
        if check and r.returncode: raise AssertionError(f"git {args} failed: {r.stderr.decode(errors='replace')}")
        return r
    def write(self, rel, data: bytes):
        p = self.path / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    def write_ledger(self, digest, *, path=ANCHOR, entries=None, raw=None):
        if raw is not None: self.write(LEDGER, raw); return
        led = {"ledger_version": 1, "registered": "2026-09-14", "spec": "fixture", "population_rule": "fixture",
               "entries": entries if entries is not None else [{"site_key": "fixture_site", "reason": "fixture", "count": "n/a", "retained_mass": "n/a",
                          "interpretation_change": "no", "rerun_threshold": "n/a", "anchors": [{"path": path, "sha256": digest}]}],
               "detector_allowlist": {"version": 1, "constants": []}}
        self.write(LEDGER, (json.dumps(led, indent=1) + "\n").encode())
    def head(self): return self.git("rev-parse", "HEAD").stdout.decode().strip()
    def guard(self, env=None):
        return subprocess.run([sys.executable, "-B", str(self.path / "tools/check_truncation_anchors_staged.py")], cwd=self.path,
                              env={**self.env, **(env or {})}, capture_output=True, text=True)
    def validator(self):
        return subprocess.run([sys.executable, "-B", str(self.path / "tools/check_truncation_ledger.py")], cwd=self.path, env=self.env, capture_output=True, text=True)
    def install(self, *args):
        return subprocess.run(["sh", str(self.path / "tools/install_precommit_anchor_guard.sh"), *args], cwd=self.path, env=self.env, capture_output=True, text=True)
    def hook_path(self): return self.path / ".git/hooks/pre-commit"
    def commit(self, *paths, msg="fixture commit"):
        return self.git("commit", "-q", "-m", msg, *(["--"] + list(paths) if paths else []), check=False)
    def index_bytes(self): return (self.path / ".git/index").read_bytes()
    def restore(self, rel):
        """Restore BOTH the index entry (from HEAD) and the working copy for a fixture path."""
        self.git("reset", "-q", "--", rel); self.git("checkout", "-q", "--", rel)


class Installation(unittest.TestCase):
    def test_install_idempotent_uninstall_and_foreign_hook_refused(self):
        r = Repo("install")
        self.assertFalse(r.hook_path().exists())
        a = r.install(); self.assertEqual(a.returncode, 0, a.stderr); self.assertTrue(r.hook_path().exists())
        self.assertTrue(r.hook_path().stat().st_mode & stat.S_IXUSR)
        self.assertEqual((r.hook_path()).read_bytes(), (r.path / "tools/hooks/pre-commit").read_bytes())
        b = r.install(); self.assertEqual(b.returncode, 0); self.assertIn("already installed", b.stdout)
        u = r.install("--uninstall"); self.assertEqual(u.returncode, 0); self.assertFalse(r.hook_path().exists())
        # foreign hook: refused, untouched, still blocks
        foreign = b"#!/bin/sh\necho 'foreign hook says no' >&2\nexit 9\n"
        r.hook_path().write_bytes(foreign); r.hook_path().chmod(0o755)
        f = r.install(); self.assertEqual(f.returncode, 3); self.assertIn("foreign", f.stderr); self.assertEqual(r.hook_path().read_bytes(), foreign)
        r.write("docs/readme.md", b"# fixture 2\n"); r.git("add", "docs/readme.md")
        c = r.commit(); self.assertNotEqual(c.returncode, 0); self.assertIn("foreign hook says no", c.stderr.decode())
        # core.hooksPath set → refused
        r2 = Repo("hookspath"); r2.git("config", "core.hooksPath", ".githooks")
        h = r2.install(); self.assertEqual(h.returncode, 3); self.assertIn("core.hooksPath", h.stderr)


class StagedGuard(unittest.TestCase):
    def setUp(self):
        self.r = Repo(self._testMethodName); self.assertEqual(self.r.install().returncode, 0)
        self.head0 = self.r.head()
    def assert_blocked(self, res, needle):
        self.assertNotEqual(res.returncode, 0, res.stdout.decode() + res.stderr.decode())
        self.assertIn(needle, res.stdout.decode() + res.stderr.decode())
        self.assertEqual(self.r.head(), self.head0)                                  # no HEAD change
    def test_docstring_edit_old_digest_rejected_parent_valid(self):
        v = self.r.validator(); self.assertEqual(v.returncode, 0, v.stdout)           # parent/reference passes
        idx_before = self.r.git("ls-files", "--stage").stdout
        self.r.write(ANCHOR, SRC_V2); self.r.git("add", ANCHOR)
        staged = self.r.git("ls-files", "--stage").stdout
        self.assert_blocked(self.r.commit(), "drift: fixture_site anchor v3/anchored_site.py changed")
        self.assertEqual(self.r.git("ls-files", "--stage").stdout, staged)             # staged content preserved
        self.assertNotEqual(staged, idx_before)
    def test_wrong_staged_source_repaired_working_copy_still_rejected(self):
        self.r.write(ANCHOR, SRC_V2); self.r.git("add", ANCHOR); self.r.write(ANCHOR, SRC_V1)   # working copy repaired, index still V2
        self.assertEqual(self.r.validator().returncode, 0)                            # working-tree gate would pass — the guard must not
        self.assert_blocked(self.r.commit(), "changed")
    def test_matching_staged_pair_passes_despite_different_unstaged_versions(self):
        self.r.write(ANCHOR, SRC_V2); self.r.write_ledger(sha(SRC_V2)); self.r.git("add", ANCHOR, LEDGER)
        self.r.write(ANCHOR, SRC_V1 + b"# unstaged drift\n"); self.r.write("docs/readme.md", b"# dirty unstaged\n")
        g = self.r.guard(); self.assertEqual(g.returncode, 0, g.stdout + g.stderr); self.assertIn("OK", g.stdout)
        c = self.r.commit(); self.assertEqual(c.returncode, 0, c.stderr.decode()); self.assertNotEqual(self.r.head(), self.head0)
        self.assertEqual(sha(self.r.git("cat-file", "blob", f"HEAD:{ANCHOR}").stdout), sha(SRC_V2))
    def test_ledger_only_wrong_digest_then_matching_pair(self):
        self.r.write_ledger("0" * 64); self.r.git("add", LEDGER)
        self.assert_blocked(self.r.commit(), "drift: fixture_site anchor v3/anchored_site.py changed")
        self.r.write(ANCHOR, SRC_V2); self.r.write_ledger(sha(SRC_V2)); self.r.git("add", ANCHOR, LEDGER)
        staged_ledger = self.r.git("rev-parse", f":{LEDGER}").stdout.decode().strip()
        c = self.r.commit(); self.assertEqual(c.returncode, 0, c.stderr.decode())
        self.assertEqual(self.r.git("rev-parse", f"HEAD:{LEDGER}").stdout.decode().strip(), staged_ledger)   # no auto-edit
    def test_deletions_removals_rename_and_type_change_cannot_evade(self):
        self.r.git("rm", "-q", "--cached", LEDGER); self.assert_blocked(self.r.commit(), "missing from the candidate index"); self.r.git("reset", "-q", "--", LEDGER)
        self.r.write_ledger(sha(SRC_V1), entries=[]); self.r.git("add", LEDGER)
        self.assert_blocked(self.r.commit(), "removed: no retirement rule"); self.r.restore(LEDGER)
        self.r.git("rm", "-q", "--cached", ANCHOR); self.assert_blocked(self.r.commit(), "deleted from the candidate index"); self.r.git("reset", "-q", "--", ANCHOR)
        self.r.git("mv", ANCHOR, "v3/renamed_site.py"); self.assert_blocked(self.r.commit(), "renamed/copied")
        self.r.git("mv", "v3/renamed_site.py", ANCHOR)
        os.unlink(self.r.path / ANCHOR); os.symlink("anchored_target.py", self.r.path / ANCHOR); self.r.git("add", ANCHOR)
        res = self.r.commit(); self.assert_blocked(res, "changed type (unsupported)"); self.assertIn("symlink", res.stdout.decode() + res.stderr.decode())
        self.r.restore(ANCHOR)
    def test_unrelated_staged_doc_with_dirty_unstaged_anchor_passes(self):
        self.r.write(ANCHOR, SRC_V2)                                                  # dirty, NOT staged
        self.r.write("docs/readme.md", b"# fixture doc change\n"); self.r.git("add", "docs/readme.md")
        g = self.r.guard(); self.assertEqual(g.returncode, 0); self.assertIn("not triggered", g.stdout)
        c = self.r.commit(); self.assertEqual(c.returncode, 0, c.stderr.decode())
    def test_malformed_ledger_unmerged_stage_missing_blob_whitespace_path_alternate_index(self):
        self.r.write_ledger(None, raw=b"{not json"); self.r.git("add", LEDGER)
        self.assert_blocked(self.r.commit(), "not valid JSON"); self.r.restore(LEDGER)
        # unresolved merge stages on the anchored path
        oid = self.r.git("rev-parse", f":{ANCHOR}").stdout.decode().strip()
        info = f"0 0000000000000000000000000000000000000000\t{ANCHOR}\n100644 {oid} 1\t{ANCHOR}\n100644 {oid} 2\t{ANCHOR}\n".encode()
        self.r.git("update-index", "--index-info", input=info)
        g = self.r.guard(); self.assertEqual(g.returncode, 1); self.assertIn("unresolved merge stages", g.stdout)
        self.r.git("update-index", "--index-info", input=f"100644 {oid} 0\t{ANCHOR}\n".encode())
        # missing blob object referenced by the index → fails closed (exit 2)
        self.r.git("update-index", "--cacheinfo", f"100644,{'1' * 40},{ANCHOR}", check=False)
        self.r.git("update-index", "--add", "--cacheinfo", f"100644,{'1' * 40},{ANCHOR}")
        g = self.r.guard(); self.assertEqual(g.returncode, 2, g.stdout + g.stderr); self.assertIn("fails closed", g.stderr)
        self.r.git("update-index", "--add", "--cacheinfo", f"100644,{oid},{ANCHOR}")
        # whitespace path anchor, consistent → passes
        ws = "v3/with space.py"; self.r.write(ws, SRC_V1)
        base = {"site_key": "fixture_site", "reason": "fixture", "count": "n/a", "retained_mass": "n/a", "interpretation_change": "no", "rerun_threshold": "n/a", "anchors": [{"path": ANCHOR, "sha256": sha(SRC_V1)}]}
        extra = dict(base, site_key="fixture_ws", anchors=[{"path": ws, "sha256": sha(SRC_V1)}])
        self.r.write_ledger(None, entries=[base, extra]); self.r.git("add", ws, LEDGER)   # ADD a whitespace-path anchor (original kept)
        g = self.r.guard(); self.assertEqual(g.returncode, 0, g.stdout + g.stderr)
        self.r.git("reset", "-q"); self.r.restore(LEDGER)
        # alternate index: bad change only in GIT_INDEX_FILE; default index untouched
        alt = self.r.path / ".git/alt.index"; env = {"GIT_INDEX_FILE": str(alt)}
        self.r.git("read-tree", "HEAD", env=env); self.r.write(ANCHOR, SRC_V2); self.r.git("add", ANCHOR, env=env); self.r.write(ANCHOR, SRC_V1)
        ga = self.r.guard(env=env); self.assertEqual(ga.returncode, 1); self.assertIn("index=alt.index", ga.stdout)
        gd = self.r.guard(); self.assertEqual(gd.returncode, 0); self.assertIn("not triggered", gd.stdout)
    def test_path_limited_commit_uses_supplied_candidate_index(self):
        self.r.write(ANCHOR, SRC_V2); self.r.git("add", ANCHOR)                       # bad anchored change staged
        self.r.write("docs/readme.md", b"# partial\n")
        c = self.r.commit("docs/readme.md")                                            # git builds a temporary index for this path only
        self.assertEqual(c.returncode, 0, c.stderr.decode()); self.assertNotEqual(self.r.head(), self.head0)
        self.assertEqual(self.r.git("cat-file", "blob", f"HEAD:{ANCHOR}").stdout, SRC_V1)   # anchored change NOT in that commit
        self.head0 = self.r.head()
        self.assert_blocked(self.r.commit(), "drift")                                  # full commit still blocked
    def test_validator_and_guard_do_not_alter_source_or_index(self):
        self.r.write(ANCHOR, SRC_V2); self.r.git("add", ANCHOR)
        before = (self.r.index_bytes(), (self.r.path / ANCHOR).read_bytes(), (self.r.path / LEDGER).read_bytes())
        self.r.validator(); self.r.guard()
        after = (self.r.index_bytes(), (self.r.path / ANCHOR).read_bytes(), (self.r.path / LEDGER).read_bytes())
        self.assertEqual(before, after)
    def test_refactored_validator_default_behavior_unchanged(self):
        # same tree: OK; docstring edit in the working tree: identical drift finding text as the original rule
        self.assertIn("[truncation-gate] OK", self.r.validator().stdout)
        self.r.write(ANCHOR, SRC_V2)
        v = self.r.validator(); self.assertEqual(v.returncode, 1)
        self.assertIn("FAIL drift: fixture_site anchor v3/anchored_site.py changed — update this ledger entry (and its numbers if the mechanism moved) in the same commit", v.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
