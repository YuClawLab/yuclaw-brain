"""V8-017 — a STALE README transcript whose version line still matches must not pass unnoticed.

The 8.0.0 release was stopped by the publisher's byte-for-byte transcript comparison: the README recorded the `replay-lab`
output of an older replay bundle, the version line was right, and the only earlier check compared the version. The exact
comparison now lives in tools/cli_transcript.py (`--check --exe`) and runs in the clean-install validation. A fake
executable keeps this test hermetic: its `replay-lab` output depends on the bundle file, like the real one."""
import contextlib, io, os, pathlib, re, sys, tempfile, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "tools"))
import cli_transcript as ct                                                     # noqa: E402

VERSION = re.search(r'^version = "([^"]+)"', (REPO / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
FAKE = f"""#!/bin/sh
case "$1" in
  --version) echo "yuclaw {VERSION}";;
  --help) echo "usage: yuclaw <command>";;
  check-claim) echo '{{"status": "NO_MATCH", "misses": []}}';;
  replay-lab) echo "Replay bundle built $(cat "$2")"; echo "[forward] fictional numbers for $(cat "$2")";;
esac
"""


def run(argv) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = ct.main(argv)
    return rc, buf.getvalue()


class ExactTranscript(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="v17-transcript-")); (self.d / "docs" / "replay").mkdir(parents=True); self.bundle = self.d / "docs" / "replay" / "lab_replay_bundle.json"
        self.bundle.write_text("2026-09-14 01:37 UTC"); self.exe = self.d / "yuclaw"; self.exe.write_text(FAKE); os.chmod(self.exe, 0o755); self.readme = self.d / "README.md"
        self.readme.write_text(f"# fictional\n\n{ct.BEGIN}\npending\n{ct.END}\n\nafter\n"); self.common = ["--exe", str(self.exe), "--wheel", "fictional.whl", "--readme", str(self.readme), "--repo", str(self.d)]
        self.assertEqual(run([*self.common, "--write"])[0], 0)

    def test_matching_generated_output_passes(self):
        rc, out = run(["--check", *self.common]); self.assertEqual(rc, 0, out); self.assertIn("equals a fresh transcript", out)
        self.assertEqual(ct.compare(self.readme.read_text(), str(self.exe), "fictional.whl", self.d)[0], True)
        self.assertEqual(run(["--check", "--readme", str(self.readme)])[0], 0)                                  # the older version-only check is unchanged

    def test_a_refreshed_bundle_makes_the_block_stale_while_the_version_line_still_matches(self):
        self.bundle.write_text("2026-09-18 23:02 UTC")                                                          # what every production refresh does to the real bundle
        self.assertIn(f"yuclaw {VERSION}", ct.recorded_block(self.readme.read_text()))                          # the version line is still right …
        self.assertEqual(run(["--check", "--readme", str(self.readme)])[0], 0)                                  # … so the version-only check passes (the gap that reached the release)
        rc, out = run(["--check", *self.common]); self.assertEqual(rc, 1, out)                                   # the exact comparison does not
        self.assertIn("first differing line", out); self.assertIn("2026-09-14", out); self.assertIn("2026-09-18", out)
        self.assertEqual(run([*self.common, "--write"])[0], 0); self.assertEqual(run(["--check", *self.common])[0], 0)   # regenerating (never hand-editing) repairs it

    def test_a_hand_edit_of_any_non_version_line_fails_and_a_missing_block_fails(self):
        text = self.readme.read_text(); self.readme.write_text(text.replace("[exit 0]", "[exit 1]", 1)); rc, out = run(["--check", *self.common]); self.assertEqual(rc, 1, out)
        self.readme.write_text("# no markers here\n"); ok, why = ct.compare(self.readme.read_text(), str(self.exe), "fictional.whl", self.d); self.assertFalse(ok); self.assertIn("no CLI-TRANSCRIPT block", why)


if __name__ == "__main__":
    unittest.main()
