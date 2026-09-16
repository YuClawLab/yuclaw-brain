"""V8-003 §5 — the PyPI long description is README.md minus the approved-logo picture block, byte-identical elsewhere, and renders."""
import pathlib, subprocess, sys, unittest

R = pathlib.Path(__file__).resolve().parents[1]


class TestReadmePypi(unittest.TestCase):
    def test_check_passes_and_pyproject_points_at_it(self):
        r = subprocess.run([sys.executable, str(R / "tools" / "yuclaw_readme_pypi.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('readme = "README_PYPI.md"', (R / "pyproject.toml").read_text())
        src, dst = (R / "README.md").read_text(), (R / "README_PYPI.md").read_text()
        self.assertIn("<picture>", src); self.assertNotIn("<picture", dst); self.assertNotIn('src="brand/', dst)
        self.assertIn("<!-- MISSION-VISION-CANONICAL:BEGIN -->", dst); self.assertIn("<!-- REPLICATION-SENTENCE-CANONICAL BEGIN -->", dst)
        self.assertEqual(len(src) - len(dst), src.index("<!-- MISSION-VISION-CANONICAL:BEGIN -->") - dst.index("<!-- MISSION-VISION-CANONICAL:BEGIN -->"))   # only bytes before the canonical block were removed


if __name__ == "__main__":
    unittest.main()
