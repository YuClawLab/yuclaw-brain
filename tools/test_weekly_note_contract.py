#!/usr/bin/env python3
"""Focused tests for the weekly-note contract v2 (V7-003E). Standard library only;
synthetic fixtures and stub connections — no database, no live note, no launcher run.
Imports the REAL producer/checker modules from the directory named by
YUCLAW_NOTE_TOOLS (defaults to this file's directory)."""
import contextlib, io, os, pathlib, re, subprocess, sys, tempfile, unittest
from datetime import date, datetime, timedelta, timezone

TOOLS = pathlib.Path(os.environ.get("YUCLAW_NOTE_TOOLS", pathlib.Path(__file__).resolve().parent))
REPO = pathlib.Path(__file__).resolve().parents[1] if "YUCLAW_NOTE_TOOLS" not in os.environ \
    else pathlib.Path(os.environ["YUCLAW_REPO"])
for p in (str(TOOLS), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)
import yuclaw_weekly_note as wn      # noqa: E402
import check_weekly_note as cw       # noqa: E402
LAUNCHER = pathlib.Path(os.environ.get("YUCLAW_NOTE_LAUNCHER", REPO / "cron" / "refresh_v3_pages.sh"))

AS_OF = datetime(2026, 9, 8, 23, 1, 5, 123456, tzinfo=timezone.utc)
START, END = date(2026, 9, 2), date(2026, 9, 8)


class StubCursor:
    def __init__(self, rows, log): self.rows, self.log = rows, log
    def execute(self, sql, params): self.log.append((sql, params))
    def fetchall(self): return self.rows
    def __enter__(self): return self
    def __exit__(self, *a): return False


class StubConn:
    def __init__(self, rows, log): self.rows, self.log = rows, log
    def set_session(self, readonly=True): self.log.append(("set_session", readonly))
    def cursor(self): return StubCursor(self.rows, self.log)
    def __enter__(self): return self
    def __exit__(self, *a): return False


class StubRegistry:
    def __init__(self, lines): self._lines = lines
    def questions(self): return {"Q1": {"status": "OPEN"}}


def note_html(start, end, as_of, canon, tier, runs, with_meta=True, as_of_text=None):
    head, vis = wn.render_metadata(start, end, as_of)
    if as_of_text is not None:   # replace ONLY the as-of meta value (the window meta also starts with a year)
        head = re.sub(r'(<meta name="yuclaw-note-as-of" content=")[^"]*(">)', lambda m: m.group(1) + as_of_text + m.group(2), head)
    return (f"<html><head>{head if with_meta else ''}</head><body>"
            f"<p>week of {start} → {end} · auto</p><p>{vis if with_meta else ''}</p>"
            f"<p>{canon + tier} events accepted into the evidence store in the window "
            f"({canon} on scoring-universe names, {tier} on evidence-tier names)</p>"
            f"<p>{runs} recorded runs this week. New protocols:</p><ul><li>none this week</li></ul>"
            f"<p>Supersessions:</p><ul><li>none</li></ul></body></html>")


class ModulesUnderTest(unittest.TestCase):
    def test_real_modules_imported_from_expected_directory(self):
        self.assertEqual(pathlib.Path(wn.__file__).resolve().parent, TOOLS.resolve())
        self.assertEqual(pathlib.Path(cw.__file__).resolve().parent, TOOLS.resolve())


class Launcher(unittest.TestCase):
    def test_note_regenerated_every_run_and_gate_requires_v2(self):
        text = LAUNCHER.read_text()
        prod = [l for l in text.splitlines() if "tools/yuclaw_weekly_note.py" in l and not l.strip().startswith("#")]
        chk = [l for l in text.splitlines() if "tools/check_weekly_note.py" in l and not l.strip().startswith("#")]
        self.assertEqual(len(prod), 1); self.assertEqual(len(chk), 1)
        self.assertIn("|| exit 23", prod[0]); self.assertFalse(prod[0].startswith("    "))   # unconditional (not indented under an if)
        self.assertIn("--require-contract v2", chk[0]); self.assertIn("|| exit 24", chk[0])
        # no weekday guard anywhere around the producer
        idx = text.index(prod[0]); before = text[max(0, idx - 400):idx]
        self.assertNotIn('date +%u', before.split("# Weekly evidence note")[-1])
        # producer precedes checker
        self.assertLess(text.index(prod[0]), text.index(chk[0]))
    def test_launcher_syntax(self):
        r = subprocess.run(["bash", "-n", str(LAUNCHER)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class MetadataRoundTrip(unittest.TestCase):
    def test_render_parse_roundtrip_full_precision(self):
        h = note_html(START, END, AS_OF, 1, 0, 0)
        m = cw.parse_note_metadata(h)
        self.assertEqual(m["contract"], "v2"); self.assertEqual(m["window"], (START, END))
        self.assertEqual(m["as_of"], AS_OF)                     # microseconds + UTC preserved
        self.assertIn("Weekly window · refreshed nightly", h); self.assertIn(f"window {START} → {END}", h)
        self.assertIn(wn.AS_OF_MEANING, h)
    def test_legacy_note_has_no_metadata_and_is_not_invented(self):
        self.assertIsNone(cw.parse_note_metadata(note_html(START, END, AS_OF, 1, 0, 0, with_meta=False)))
    def test_malformed_metadata_rejected(self):
        for bad in ("2026-09-08T23:01:05Z", "2026-09-08 23:01:05.123456", "2026-09-08T23:01:05.123456+00:00", ""):
            with self.assertRaises(ValueError, msg=bad):
                cw.parse_note_metadata(note_html(START, END, AS_OF, 1, 0, 0, as_of_text=bad))
        with self.assertRaises(ValueError):
            cw.parse_note_metadata('<meta name="yuclaw-note-contract" content="v2">')   # marker without fields
        with self.assertRaises(ValueError):
            cw.parse_note_metadata('<meta name="yuclaw-note-contract" content="v9">')
    def test_as_of_must_be_aware_utc(self):
        with self.assertRaises(ValueError): wn.format_as_of(datetime(2026, 9, 8, 1, 2, 3))
        with self.assertRaises(ValueError): wn.format_as_of(AS_OF.astimezone(timezone(timedelta(hours=-6))))
        with self.assertRaises(ValueError): wn.count_params(START, END, datetime(2026, 9, 8))


class SharedCutoff(unittest.TestCase):
    def test_producer_and_checker_execute_identical_sql_and_params(self):
        log_p, log_c = [], []
        rows = [("AAPL", 3), ("ZZZ-TIER", 1)]
        wn.evidence_tier_tickers = lambda: {"ZZZ-TIER"}
        wn.scoring_universe = lambda: {"AAPL"}
        import v3.universe_tiers as ut
        orig = (ut.evidence_tier_tickers, ut.scoring_universe)
        ut.evidence_tier_tickers, ut.scoring_universe = (lambda: {"ZZZ-TIER"}), (lambda: {"AAPL"})
        try:
            g = wn.gather(START, END, AS_OF, connect=lambda: StubConn(rows, log_p), registry=StubRegistry([]))
            s = cw.recount_store(START, END, AS_OF, connect=lambda: StubConn(rows, log_c))
        finally:
            ut.evidence_tier_tickers, ut.scoring_universe = orig
        sql_p = [x for x in log_p if isinstance(x[0], str) and x[0].startswith("SELECT")][0]
        sql_c = [x for x in log_c if isinstance(x[0], str) and x[0].startswith("SELECT")][0]
        self.assertEqual(sql_p, sql_c)                            # same text, same params
        self.assertEqual(sql_p[1], (START, END, AS_OF))
        self.assertIn("created_at <= %s", sql_p[0]); self.assertIn("created_at::date BETWEEN %s AND %s", sql_p[0])
        self.assertIn("event_status='accepted'", sql_p[0])
        self.assertEqual((g["events_canonical"], g["events_tier"], g["events"]), (3, 1, 4))
        self.assertEqual(s, {"canon": 3, "tier": 1})
        self.assertIn(("set_session", True), log_p); self.assertIn(("set_session", True), log_c)
    def test_legacy_recount_has_no_cutoff(self):
        log = []
        import v3.universe_tiers as ut
        orig = (ut.evidence_tier_tickers, ut.scoring_universe)
        ut.evidence_tier_tickers, ut.scoring_universe = (lambda: set()), (lambda: {"AAPL"})
        try:
            cw.recount_store(START, END, None, connect=lambda: StubConn([("AAPL", 2)], log))
        finally:
            ut.evidence_tier_tickers, ut.scoring_universe = orig
        sql = [x for x in log if isinstance(x[0], str) and x[0].startswith("SELECT")][0]
        self.assertNotIn("created_at <=", sql[0]); self.assertEqual(sql[1], (START, END))


class Reconcile(unittest.TestCase):
    def test_stale_41_vs_63_fixture_is_a_mismatch_and_refresh_reconciles(self):
        note = {"canon": 33, "tier": 8, "total": 41, "runs": 2, "protos": 0, "sups": 0}
        self.assertEqual(cw.reconcile(note, {"canon": 55, "tier": 8}, {"runs": 2, "protos": 0, "sups": 0}),
                         ["events: note 33+8=41 vs store 55+8=63"])
        refreshed = {"canon": 55, "tier": 8, "total": 63, "runs": 2, "protos": 0, "sups": 0}
        self.assertEqual(cw.reconcile(refreshed, {"canon": 55, "tier": 8}, {"runs": 2, "protos": 0, "sups": 0}), [])
    def test_late_visibility_race_still_fails_strict_equality(self):
        # checker sees one more row with created_at <= as_of than the producer did → mismatch, never hidden
        note = {"canon": 55, "tier": 8, "total": 63, "runs": 2, "protos": 0, "sups": 0}
        self.assertTrue(cw.reconcile(note, {"canon": 56, "tier": 8}, {"runs": 2, "protos": 0, "sups": 0}))
        self.assertTrue(cw.reconcile(note, {"canon": 55, "tier": 8}, {"runs": 3, "protos": 0, "sups": 0}))


class ScheduledPath(unittest.TestCase):
    def _run_main(self, html, argv):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "weekly_note.html"; p.write_text(html)
            orig = cw.NOTE; cw.NOTE = p
            out = io.StringIO()
            try:
                with contextlib.redirect_stdout(out):
                    rc = cw.main(argv, connect=lambda: (_ for _ in ()).throw(AssertionError("DB must not be reached")))
            finally:
                cw.NOTE = orig
            return rc, out.getvalue()
    def test_scheduled_path_rejects_legacy_note_without_fallback(self):
        rc, out = self._run_main(note_html(START, END, AS_OF, 1, 0, 0, with_meta=False), ["--require-contract", "v2"])
        self.assertEqual(rc, 1); self.assertIn("no legacy fallback", out)
    def test_scheduled_path_rejects_malformed_as_of(self):
        rc, out = self._run_main(note_html(START, END, AS_OF, 1, 0, 0, as_of_text="2026-09-08T23:01:05Z"), ["--require-contract", "v2"])
        self.assertEqual(rc, 1); self.assertIn("malformed as_of", out)
    def test_window_metadata_must_match_visible_window(self):
        h = note_html(START, END, AS_OF, 1, 0, 0).replace(f"week of {START} → {END}", f"week of {START} → {END + timedelta(days=1)}")
        rc, out = self._run_main(h, ["--require-contract", "v2"])
        self.assertEqual(rc, 1); self.assertIn("window metadata", out)
    def test_v2_note_reconciles_with_stub_store_using_note_cutoff(self):
        import v3.universe_tiers as ut
        orig = (ut.evidence_tier_tickers, ut.scoring_universe)
        ut.evidence_tier_tickers, ut.scoring_universe = (lambda: {"T1"}), (lambda: {"C1"})
        log = []
        try:
            with tempfile.TemporaryDirectory() as d:
                p = pathlib.Path(d) / "weekly_note.html"
                p.write_text(note_html(START, END, AS_OF, 5, 2, 0)); o = cw.NOTE; cw.NOTE = p
                cw.Registry = None
                out = io.StringIO()
                import yuclaw_protocol_registry as ypr
                real = ypr.Registry; ypr.Registry = lambda path: StubRegistry([])
                try:
                    with contextlib.redirect_stdout(out):
                        rc = cw.main(["--require-contract", "v2"], connect=lambda: StubConn([("C1", 5), ("T1", 2)], log))
                finally:
                    ypr.Registry = real; cw.NOTE = o
        finally:
            ut.evidence_tier_tickers, ut.scoring_universe = orig
        self.assertEqual(rc, 0, out.getvalue()); self.assertIn("contract v2, as_of 2026-09-08T23:01:05.123456Z", out.getvalue())
        sql = [x for x in log if isinstance(x[0], str) and x[0].startswith("SELECT")][0]
        self.assertEqual(sql[1][2], AS_OF)                        # the NOTE's cutoff, not the checker's clock


if __name__ == "__main__":
    unittest.main(verbosity=2)
