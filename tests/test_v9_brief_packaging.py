"""v9 packaging: the brief layer ships in the wheel and the sdist (packages / include), its record directories do not, the
packaged quick starts exist in both languages, the clean-install tool requires every v9 module, and the CLI entry points
resolve from the package (not from the checkout)."""
import pathlib, re, subprocess, sys, unittest

R = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "tools"))
import yuclaw_v8_clean_install as ci  # noqa: E402


class TestV9Packaging(unittest.TestCase):
    def test_pyproject_ships_v9_and_excludes_its_records(self):
        t = (R / "pyproject.toml").read_text()
        wheel = t[t.index("[tool.hatch.build.targets.wheel]"):t.index("[tool.hatch.build.targets.sdist]")]
        sdist = t[t.index("[tool.hatch.build.targets.sdist]"):]
        self.assertRegex(wheel, r'packages = \[.*"v9".*\]'); self.assertIn('"v9/V9-*"', wheel.split("exclude")[-1])
        self.assertIn('"v9/__init__.py"', sdist); self.assertIn('"v9/brief"', sdist); self.assertIn('"v9/V9-*"', sdist.split("exclude")[-1])

    def test_required_wheel_lists_every_v9_module_and_the_quick_starts(self):
        mods = sorted(p.relative_to(R).as_posix() for p in (R / "v9" / "brief").glob("*.py"))
        for m in mods:
            self.assertIn(m, ci.REQUIRED_WHEEL, m)
        for q in ("v9/brief/resources/QUICKSTART_EN.md", "v9/brief/resources/QUICKSTART_FR.md"):
            self.assertIn(q, ci.REQUIRED_WHEEL); self.assertTrue((R / q).is_file())
            self.assertIn("Make financial AI accountable to evidence.", (R / q).read_text(encoding="utf-8"))
        self.assertFalse(any(x.startswith("v9/V9-") for x in ci.REQUIRED_WHEEL))

    def test_entry_points_resolve_and_help_names_the_commands(self):
        for cmd in ([sys.executable, "-m", "v9.brief", "--help"], [sys.executable, "-m", "v8.workbench", "brief", "--help"]):
            out = subprocess.run(cmd, cwd=R, capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            for sub in ("example", "create", "import", "show", "edit", "translate", "link", "review", "import-record", "trust", "export", "verify", "measure", "selftest", "guide", "schema"):
                self.assertIn(sub, out.stdout)
        out = subprocess.run([sys.executable, "-m", "v9.brief", "guide", "--lang", "fr"], cwd=R, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0); self.assertIn("Recherche et formation uniquement", out.stdout)


if __name__ == "__main__":
    unittest.main()
