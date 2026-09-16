"""V8-003 §4 — the workbench ships: packaged resources are byte-identical to their sources, and the build configuration
includes the workbench (and excludes the record directories)."""
import hashlib, pathlib, re, sys, unittest

R = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "tools"))
import yuclaw_v8_clean_install as ci  # noqa: E402


class TestPackaging(unittest.TestCase):
    def test_resources_identical_to_sources(self):
        res = R / "v8" / "workbench" / "resources"
        self.assertEqual(hashlib.sha256((res / "CommitmentClaim.v1.json").read_bytes()).hexdigest(), hashlib.sha256((R / "schemas" / "CommitmentClaim.v1.json").read_bytes()).hexdigest())
        src = R / "tests" / "fixtures" / "v8" / "commitments"
        for f in sorted(src.glob("*.json")):
            self.assertEqual((res / "fixtures" / f.name).read_bytes(), f.read_bytes(), f.name)
        self.assertEqual(sorted(p.name for p in (res / "fixtures").glob("*.json")), sorted(p.name for p in src.glob("*.json")))

    def test_build_configuration_ships_the_workbench(self):
        t = (R / "pyproject.toml").read_text()
        wheel = re.search(r"\[tool\.hatch\.build\.targets\.wheel\]\n(.*?)\n\[", t, re.S).group(1)
        self.assertIn('"v8"', wheel); self.assertIn('"v8/V8-*"', wheel); self.assertIn("v8/scope", wheel)      # a pattern: every order record directory, present or future
        sdist = re.search(r"\[tool\.hatch\.build\.targets\.sdist\]\n(.*?)(\n\[|\Z)", t, re.S).group(1)
        self.assertIn("v8/workbench", sdist); self.assertIn("v8/__init__.py", sdist); self.assertIn("README_PYPI.md", sdist)
        for rec in ("v8/V8-*", "v8/scope"):                                                    # the sdist builder picks up record READMEs unless excluded (found by the V8-003 run; V8-004's record shipped until the pattern, found by the V8-005 run)
            self.assertIn(f'"{rec}"', sdist.split("exclude")[-1], rec)
        import fnmatch
        for path in ("v8/V8-001/README.md", "v8/V8-004/packaging.json", "v8/V8-005/README.md", "v8/V8-099/x.json"):
            self.assertTrue(fnmatch.fnmatch(path, "v8/V8-*" + "*") or path.startswith("v8/V8-"), path)
        self.assertIn('readme = "README_PYPI.md"', t)

    def test_packaged_modules_compile_on_minimum_python(self):
        """requires-python >= 3.10: every packaged v8 module must compile on a real 3.10 interpreter when one is installed
        (tools/check_py_minimum.py is a static proxy and missed nested same-quote f-strings twice during V8-003/V8-004)."""
        import shutil, subprocess
        py = shutil.which("python3.10")
        if not py:
            self.skipTest("no python3.10 interpreter on this host")
        files = sorted(str(p) for p in (R / "v8" / "workbench").glob("*.py"))
        r = subprocess.run([py, "-m", "py_compile", *files], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])

    def test_member_inspection_rules(self):
        good = list(ci.REQUIRED_WHEEL) + ["v3/__init__.py", "v8/workbench/resources/README.md"]
        self.assertTrue(ci.inspect_members("wheel", good)["ok"])
        for bad in ("v8/V8-001/README.md", "v8/scope/SCOPE_INDEX.json", "internal/x.json", "tests/test_x.py", "v8/workbench/__pycache__/a.pyc"):
            r = ci.inspect_members("wheel", good + [bad]); self.assertFalse(r["ok"], bad)
        self.assertEqual(ci.inspect_members("wheel", good[1:])["missing_required"], [ci.REQUIRED_WHEEL[0]])
        self.assertFalse(ci.inspect_members("sdist", list(ci.REQUIRED_SDIST) + ["output/x"])["ok"])

    def test_long_description_rules(self):
        base = "Metadata-Version: 2.4\nName: yuclaw\nDescription-Content-Type: text/markdown\n\n# T\n<!-- MISSION-VISION-CANONICAL:BEGIN -->x<!-- MISSION-VISION-CANONICAL:END -->\n"
        self.assertTrue(ci.long_description_ok(base)["ok"])
        self.assertFalse(ci.long_description_ok(base.replace("# T", '<p align="center"><picture><img src="brand/x.svg"></picture></p>'))["ok"])
        self.assertFalse(ci.long_description_ok(base.replace("text/markdown", "text/x-rst"))["ok"])
        self.assertFalse(ci.long_description_ok(base.replace("<!-- MISSION-VISION-CANONICAL:BEGIN -->", ""))["ok"])

    def test_adopt_refuses_mismatched_identity_or_bytes(self):
        """--artifacts adopts a pair only when its identity record names the requested commit and tree and every byte matches."""
        import json, subprocess, sys, tempfile
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-adopt-")); art = tmp / "art"; art.mkdir(); out = tmp / "out"
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=R, capture_output=True, text=True).stdout.strip(); tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=R, capture_output=True, text=True).stdout.strip()
        w, s = b"WHEEL-BYTES", b"SDIST-BYTES"; (art / "yuclaw-7.0.1-py3-none-any.whl").write_bytes(w); (art / "yuclaw-7.0.1.tar.gz").write_bytes(s)
        rec = {"record": "yuclaw-artifact-identity/1", "label": "PRELIMINARY development build", "version": "7.0.1", "commit": head, "tree": tree, "wheel": {"name": "yuclaw-7.0.1-py3-none-any.whl", "sha256": hashlib.sha256(w).hexdigest(), "size": len(w)}, "sdist": {"name": "yuclaw-7.0.1.tar.gz", "sha256": hashlib.sha256(s).hexdigest(), "size": len(s)}, "build_utc": "x", "source_date_epoch": "1580601600", "build_tools": {}}
        def attempt(record):
            (art / "artifact_identity.json").write_text(json.dumps(record)); import shutil; shutil.rmtree(out, ignore_errors=True)
            return subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import yuclaw_v8_clean_install as ci; from pathlib import Path; ci.adopt(sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]))", str(R / "tools"), head, str(art), str(out)], capture_output=True, text=True)
        self.assertIn("binds commit", attempt(dict(rec, commit="0" * 40)).stderr)                      # wrong commit → STOP
        self.assertIn("binds commit", attempt(dict(rec, tree="0" * 40)).stderr)                        # wrong tree → STOP
        bad = json.loads(json.dumps(rec)); bad["wheel"]["sha256"] = "f" * 64; self.assertIn("bytes differ", attempt(bad).stderr)   # wrong bytes → STOP
        bad = json.loads(json.dumps(rec)); bad["sdist"]["size"] = 1; self.assertIn("bytes differ", attempt(bad).stderr)
        self.assertIn("unknown artifact identity", attempt(dict(rec, record="other/1")).stderr)
        (art / "artifact_identity.json").unlink(); import shutil; shutil.rmtree(out, ignore_errors=True)            # no identity record → STOP
        r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import yuclaw_v8_clean_install as ci; from pathlib import Path; ci.adopt(sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]))", str(R / "tools"), head, str(art), str(out)], capture_output=True, text=True)
        self.assertIn("missing", r.stderr)


if __name__ == "__main__":
    unittest.main()
