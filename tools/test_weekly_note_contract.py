#!/usr/bin/env python3
"""Focused tests for the weekly-note contract v3 (V7-003E-C1, Branch B: nightly refresh,
original live-store rules, as_of = generated at, no cutoff). Standard library only; synthetic
fixtures and a store stub — no database, no live note, no launcher run. Imports the REAL
producer/checker modules from YUCLAW_NOTE_TOOLS (defaults to this file's directory).

The store stub applies ONLY the predicates present in the executed SQL text (accepted status,
created_at::date window, and — if present — a created_at <= cutoff parameter). It models the
store; the counting, parsing and reconciliation code under test is the real module code."""
import contextlib, io, os, pathlib, re, subprocess, sys, tempfile, unittest
from datetime import date, datetime, timedelta, timezone

TOOLS = pathlib.Path(os.environ.get("YUCLAW_NOTE_TOOLS", pathlib.Path(__file__).resolve().parent))
REPO = pathlib.Path(os.environ["YUCLAW_REPO"]) if "YUCLAW_REPO" in os.environ else pathlib.Path(__file__).resolve().parents[1]
for p in (str(TOOLS), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)
import yuclaw_weekly_note as wn      # noqa: E402
import check_weekly_note as cw       # noqa: E402
LAUNCHER = pathlib.Path(os.environ.get("YUCLAW_NOTE_LAUNCHER", REPO / "cron" / "refresh_v3_pages.sh"))

AS_OF = datetime(2026, 9, 8, 23, 1, 5, 123456, tzinfo=timezone.utc)
START, END = date(2026, 9, 2), date(2026, 9, 8)
TIER, CANON = {"T1"}, {"C1", "C2"}


class StoreStub:
    """rows: (ticker, created_at aware datetime, status). execute() applies only the predicates
    that the SQL text contains; fetchall() groups by ticker like the real query."""
    def __init__(self, rows, log): self.rows, self.log, self._res = rows, log, []
    def set_session(self, readonly=True): self.log.append(("set_session", readonly))
    def cursor(self): return self
    def execute(self, sql, params):
        self.log.append((sql, params))
        assert "event_status='accepted'" in sql and "created_at::date BETWEEN %s AND %s" in sql, "original predicates must remain"
        start, end = params[0], params[1]
        cutoff = params[2] if "created_at <= %s" in sql else None
        counts = {}
        for tk, ts, status in self.rows:
            if status != "accepted": continue
            if not (start <= ts.date() <= end): continue
            if cutoff is not None and ts > cutoff: continue
            counts[tk] = counts.get(tk, 0) + 1
        self._res = sorted(counts.items())
    def fetchall(self): return self._res
    def __enter__(self): return self
    def __exit__(self, *a): return False


class StubRegistry:
    def __init__(self, lines=()): self._lines = list(lines)
    def questions(self): return {"Q1": {"status": "OPEN"}}


@contextlib.contextmanager
def universes():
    import v3.universe_tiers as ut
    orig = (ut.evidence_tier_tickers, ut.scoring_universe)
    ut.evidence_tier_tickers, ut.scoring_universe = (lambda: TIER), (lambda: CANON)
    try:
        yield
    finally:
        ut.evidence_tier_tickers, ut.scoring_universe = orig


def note_html(start, end, as_of, canon, tier, runs, *, with_meta=True, as_of_text=None, contract=None, meaning=None):
    head, vis = wn.render_metadata(start, end, as_of)
    if as_of_text is not None:
        head = re.sub(r'(<meta name="yuclaw-note-as-of" content=")[^"]*(">)', lambda m: m.group(1) + as_of_text + m.group(2), head)
    if contract is not None:
        head = re.sub(r'(<meta name="yuclaw-note-contract" content=")[^"]*(">)', lambda m: m.group(1) + contract + m.group(2), head)
    if meaning is not None:
        head = re.sub(r'(<meta name="yuclaw-note-as-of-meaning" content=")[^"]*(">)', lambda m: m.group(1) + meaning + m.group(2), head)
    return (f"<html><head>{head if with_meta else ''}</head><body>"
            f"<p>week of {start} → {end} · auto</p><p>{vis if with_meta else ''}</p>"
            f"<p>{canon + tier} events accepted into the evidence store in the window "
            f"({canon} on scoring-universe names, {tier} on evidence-tier names)</p>"
            f"<p>{runs} recorded runs this week. New protocols:</p><ul><li>none this week</li></ul>"
            f"<p>Supersessions:</p><ul><li>none</li></ul></body></html>")


def run_checker(html, argv, rows):
    """Run the real checker main() on a temp note with a store stub; returns (rc, stdout, log)."""
    log = []
    with tempfile.TemporaryDirectory() as d, universes():
        p = pathlib.Path(d) / "weekly_note.html"; p.write_text(html)
        orig = cw.NOTE; cw.NOTE = p
        import yuclaw_protocol_registry as ypr
        real = ypr.Registry; ypr.Registry = lambda path: StubRegistry()
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                rc = cw.main(argv, connect=lambda: StoreStub(rows, log))
        finally:
            ypr.Registry = real; cw.NOTE = orig
    return rc, out.getvalue(), log


ROWS_BASE = [("C1", datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc), "accepted"),
             ("C2", datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc), "accepted"),
             ("T1", datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc), "accepted"),
             ("C1", datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc), "accepted"),      # out of window
             ("C2", datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc), "accepted"),       # after window (future date)
             ("C1", datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc), "rejected")]      # ineligible status
LATER_THAN_AS_OF = ("C2", AS_OF + timedelta(minutes=5), "accepted")                         # inside window, inserted after generation time


class ModulesUnderTest(unittest.TestCase):
    def test_real_modules_from_expected_dir_and_no_cutoff_in_sql(self):
        self.assertEqual(pathlib.Path(wn.__file__).resolve().parent, TOOLS.resolve())
        self.assertEqual(pathlib.Path(cw.__file__).resolve().parent, TOOLS.resolve())
        self.assertNotIn("created_at <=", wn.EVENTS_COUNT_SQL); self.assertNotIn("as_of", wn.EVENTS_COUNT_SQL.lower())
        self.assertIn("event_status='accepted'", wn.EVENTS_COUNT_SQL); self.assertIn("created_at::date BETWEEN %s AND %s", wn.EVENTS_COUNT_SQL)
        self.assertEqual(wn.count_params(START, END), (START, END))
        self.assertEqual(wn.NOTE_CONTRACT, "v3"); self.assertEqual(wn.AS_OF_MEANING, "generated-at")


class Launcher(unittest.TestCase):
    def test_note_produced_once_every_run_then_checked_with_v3(self):
        text = LAUNCHER.read_text()
        prod = [l for l in text.splitlines() if "tools/yuclaw_weekly_note.py" in l and not l.strip().startswith("#")]
        chk = [l for l in text.splitlines() if "tools/check_weekly_note.py" in l and not l.strip().startswith("#")]
        self.assertEqual(len(prod), 1); self.assertEqual(len(chk), 1)          # once per run, never twice (no Friday double)
        self.assertIn("|| exit 23", prod[0]); self.assertFalse(prod[0].startswith(" "))
        self.assertIn("--require-contract v3", chk[0]); self.assertIn("|| exit 24", chk[0])
        self.assertNotIn("--require-contract v2", text)
        self.assertNotIn('date +%u', text.split("# Weekly evidence note")[-1].split("tools/check_weekly_note.py")[0])
        self.assertLess(text.index(prod[0]), text.index(chk[0]))
    def test_launcher_syntax(self):
        r = subprocess.run(["bash", "-n", str(LAUNCHER)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class Metadata(unittest.TestCase):
    def test_roundtrip_generated_at_full_precision(self):
        h = note_html(START, END, AS_OF, 1, 0, 0)
        m = cw.parse_note_metadata(h)
        self.assertEqual((m["contract"], m["window"], m["as_of"], m["as_of_meaning"]), ("v3", (START, END), AS_OF, "generated-at"))
        self.assertIn("Weekly window · refreshed nightly", h); self.assertIn("generated at, UTC", h); self.assertIn("not a cutoff", h)
        self.assertNotIn("acceptance cutoff", h); self.assertNotIn("frozen", h.lower())
    def test_legacy_note_has_no_metadata_and_none_is_invented(self):
        self.assertIsNone(cw.parse_note_metadata(note_html(START, END, AS_OF, 1, 0, 0, with_meta=False)))
    def test_superseded_v2_cutoff_note_is_rejected_not_reinterpreted(self):
        with self.assertRaises(ValueError) as cm:
            cw.parse_note_metadata(note_html(START, END, AS_OF, 1, 0, 0, contract="v2"))
        self.assertIn("superseded", str(cm.exception))
    def test_wrong_meaning_or_missing_fields_or_malformed_as_of_rejected(self):
        with self.assertRaises(ValueError): cw.parse_note_metadata(note_html(START, END, AS_OF, 1, 0, 0, meaning="acceptance-cutoff"))
        with self.assertRaises(ValueError): cw.parse_note_metadata('<meta name="yuclaw-note-contract" content="v3">')
        with self.assertRaises(ValueError): cw.parse_note_metadata(note_html(START, END, AS_OF, 1, 0, 0, contract="v9"))
        for bad in ("2026-09-08T23:01:05Z", "2026-09-08 23:01:05.123456", ""):
            with self.assertRaises(ValueError, msg=bad): cw.parse_note_metadata(note_html(START, END, AS_OF, 1, 0, 0, as_of_text=bad))
    def test_as_of_must_be_aware_utc(self):
        with self.assertRaises(ValueError): wn.format_as_of(datetime(2026, 9, 8, 1, 2, 3))
        with self.assertRaises(ValueError): wn.format_as_of(AS_OF.astimezone(timezone(timedelta(hours=-6))))


class LiveRecheck(unittest.TestCase):
    def test_1_row_inserted_after_generation_time_is_counted_by_fallback_checker(self):
        rows = ROWS_BASE + [LATER_THAN_AS_OF]
        # the note claims what a LIVE recount sees now: C1 1 + C2 2 = 3 canon, T1 1 tier
        rc, out, log = run_checker(note_html(START, END, AS_OF, 3, 1, 0), ["--require-contract", "v3"], rows)
        self.assertEqual(rc, 0, out)
        sql, params = [x for x in log if isinstance(x[0], str) and x[0].startswith("SELECT")][0]
        self.assertEqual(params, (START, END)); self.assertNotIn("created_at <=", sql)   # no cutoff argument at all
        self.assertIn("live recheck", out)
    def test_1b_a_cutoff_predicate_would_have_excluded_that_row(self):
        # discriminator for the stub itself: the superseded SQL shape excludes the later row
        log = []; s = StoreStub(ROWS_BASE + [LATER_THAN_AS_OF], log)
        s.execute(wn.EVENTS_COUNT_SQL.replace("GROUP BY 1", "AND created_at <= %s GROUP BY 1"), (START, END, AS_OF))
        self.assertEqual(dict(s.fetchall()), {"C1": 1, "C2": 1, "T1": 1})
        s.execute(wn.EVENTS_COUNT_SQL, (START, END)); self.assertEqual(dict(s.fetchall()), {"C1": 1, "C2": 2, "T1": 1})
    def test_2_row_becoming_visible_between_production_and_check_fails_strictly(self):
        with universes():
            g = wn.gather(START, END, connect=lambda: StoreStub(ROWS_BASE, []), registry=StubRegistry())
        self.assertEqual((g["events_canonical"], g["events_tier"]), (2, 1))
        note = note_html(START, END, AS_OF, g["events_canonical"], g["events_tier"], 0)
        rc, out, _ = run_checker(note, ["--require-contract", "v3"], ROWS_BASE + [LATER_THAN_AS_OF])
        self.assertEqual(rc, 1); self.assertIn("events: note 2+1=3 vs store 3+1=4", out); self.assertNotIn("snapshot", out.lower())
    def test_3_unchanged_inputs_reconcile_and_ineligible_rows_stay_excluded(self):
        with universes():
            g = wn.gather(START, END, connect=lambda: StoreStub(ROWS_BASE, []), registry=StubRegistry())
        self.assertEqual((g["events_canonical"], g["events_tier"], g["events"]), (2, 1, 3))   # out-of-window, future, rejected excluded
        rc, out, log = run_checker(note_html(START, END, AS_OF, 2, 1, 0), ["--require-contract", "v3"], ROWS_BASE)
        self.assertEqual(rc, 0, out)
        p_sql = wn.EVENTS_COUNT_SQL; c_sql = [x for x in log if isinstance(x[0], str) and x[0].startswith("SELECT")][0][0]
        self.assertEqual(p_sql, c_sql)                                                          # identical text, independent recount
    def test_stale_41_vs_63_fixture_still_a_mismatch(self):
        self.assertEqual(cw.reconcile({"canon": 33, "tier": 8, "total": 41, "runs": 2, "protos": 0, "sups": 0},
                                      {"canon": 55, "tier": 8}, {"runs": 2, "protos": 0, "sups": 0}),
                         ["events: note 33+8=41 vs store 55+8=63"])


class ScheduledPath(unittest.TestCase):
    def test_4_scheduled_path_rejects_legacy_v2_and_wrong_meaning(self):
        for html, expect in ((note_html(START, END, AS_OF, 1, 0, 0, with_meta=False), "no legacy fallback"),
                             (note_html(START, END, AS_OF, 1, 0, 0, contract="v2"), "superseded"),
                             (note_html(START, END, AS_OF, 1, 0, 0, meaning="acceptance-cutoff"), "generation time"),
                             (note_html(START, END, AS_OF, 1, 0, 0, as_of_text="2026-09-08T23:01:05Z"), "malformed as_of")):
            rc, out, log = run_checker(html, ["--require-contract", "v3"], ROWS_BASE)
            self.assertEqual(rc, 1, out); self.assertIn(expect, out); self.assertFalse([x for x in log if isinstance(x[0], str) and x[0].startswith("SELECT")])
    def test_4b_legacy_note_without_flag_keeps_original_check(self):
        rc, out, log = run_checker(note_html(START, END, AS_OF, 2, 1, 0, with_meta=False), [], ROWS_BASE)
        self.assertEqual(rc, 0, out); self.assertIn("(legacy note)", out)
        self.assertEqual([x for x in log if isinstance(x[0], str) and x[0].startswith("SELECT")][0][1], (START, END))
    def test_window_metadata_must_match_visible_window(self):
        h = note_html(START, END, AS_OF, 2, 1, 0).replace(f"week of {START} → {END}", f"week of {START} → {END + timedelta(days=1)}")
        rc, out, _ = run_checker(h, ["--require-contract", "v3"], ROWS_BASE)
        self.assertEqual(rc, 1); self.assertIn("window metadata", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
