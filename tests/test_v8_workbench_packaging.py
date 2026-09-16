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
        self.assertIn('"v8"', wheel); self.assertIn("v8/V8-001", wheel); self.assertIn("v8/scope", wheel)
        sdist = re.search(r"\[tool\.hatch\.build\.targets\.sdist\]\n(.*?)(\n\[|\Z)", t, re.S).group(1)
        self.assertIn("v8/workbench", sdist); self.assertIn("v8/__init__.py", sdist); self.assertIn("README_PYPI.md", sdist)
        for rec in ("v8/V8-001", "v8/V8-002", "v8/V8-003", "v8/scope"):                       # the sdist builder picks up record READMEs unless excluded (found by the V8-003 clean-install run)
            self.assertIn(f'"{rec}"', sdist.split("exclude")[-1], rec)
        self.assertIn('readme = "README_PYPI.md"', t)

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


if __name__ == "__main__":
    unittest.main()
