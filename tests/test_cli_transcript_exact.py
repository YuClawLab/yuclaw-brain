"""V8-017 — a STALE README transcript whose version line still matches must not pass unnoticed.

The 8.0.0 release was stopped by the publisher's byte-for-byte transcript comparison: the README recorded the `replay-lab`
output of an older replay bundle, the version line was right, and the only earlier check compared the version. The exact
comparison now lives in tools/cli_transcript.py (`--check --exe`) and runs in the clean-install validation. A fake
executable keeps this test hermetic: its `replay-lab` output depends on the bundle file, like the real one, and its
`check-claim` answers "from the bundled snapshot" only when the tool set YUCLAW_CORPUS=snapshot (the ONE transcript
environment; the real command line is exercised in tests/test_v8_transcript_snapshot_mode.py)."""
import contextlib, io, os, pathlib, re, sys, tempfile, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "tools"))
import cli_transcript as ct                                                     # noqa: E402

VERSION = re.search(r'^version = "([^"]+)"', (REPO / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
FAKE = f"""#!/bin/sh
case "$1" in
  --version) echo "yuclaw {VERSION}";;
  --help) echo "usage: yuclaw <command>";;
  check-claim) if [ "$YUCLAW_CORPUS" = "snapshot" ]; then echo '{{"status": "NO_MATCH", "misses": [], "corpus": {{"mode": "offline_snapshot", "snapshot_generated": "2026-09-01T00:00:00+00:00"}}}}'
               else echo '{{"status": "NO_MATCH", "misses": []}}'; fi;;
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

    def test_a_changed_field_count_fails_and_the_failure_is_diagnosable(self):
        text = self.readme.read_text(); self.assertIn("<3 fields total", text); self.assertIn('"mode": "offline_snapshot"', text)     # the tool ran the command in snapshot mode
        self.readme.write_text(text.replace("<3 fields total", "<2 fields total", 1)); r = ct.examine(self.readme.read_text(), str(self.exe), "fictional.whl", self.d)
        self.assertFalse(r["ok"]); self.assertFalse(r["byte_exact"]); self.assertEqual(r["mode"], "YUCLAW_CORPUS=snapshot"); self.assertTrue(r["answers_from_bundled_snapshot"])
        self.assertIn("<2 fields total", r["expected"][r["first_differing_line"] - r["excerpt_starts_at_line"]]); self.assertIn("<3 fields total", r["actual"][r["first_differing_line"] - r["excerpt_starts_at_line"]])
        self.assertEqual([(c["command"].split()[0], c["exit"]) for c in r["commands"]], [("--version", 0), ("--help", 0), ("check-claim", 0), ("check-claim", 0), ("check-claim", 0), ("replay-lab", 0)])
        self.assertLessEqual(len(r["expected"]), 5); self.assertLessEqual(max(map(len, r["expected"] + r["actual"])), 160)                # bounded
        rc, out = run(["--check", *self.common]); self.assertEqual(rc, 1); self.assertIn("expected (README)", out); self.assertIn("actual (fresh)", out); self.assertIn("exit 0", out)

    def test_an_executable_that_ignores_the_snapshot_selection_is_named_as_such(self):
        node_like = self.d / "yuclaw-old"; node_like.write_text(FAKE.replace('if [ "$YUCLAW_CORPUS" = "snapshot" ]', 'if [ "never" = "snapshot" ]')); os.chmod(node_like, 0o755)
        r = ct.examine(self.readme.read_text(), str(node_like), "fictional.whl", self.d)
        self.assertFalse(r["ok"]); self.assertFalse(r["answers_from_bundled_snapshot"]); self.assertIn("did NOT answer check-claim from the bundled snapshot", r["reason"])


if __name__ == "__main__":
    unittest.main()
