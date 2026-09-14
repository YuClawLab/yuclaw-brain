"""v7 Block C guards: (1) the trading calendar's supported horizon is explicit and unsupported dates
raise rather than guess; (2) N_eff stays PENDING when no pooled statistic is designated — the stored
first-read artifact and the tool's printed constant agree; no numeric N_eff is derivable from the
structure alone. No new research read is performed."""
import json, pathlib, sys, unittest
from datetime import date, timedelta
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tools"))
from v3.u350 import market_calendar as mc  # noqa: E402


class CalendarHorizon(unittest.TestCase):
    def test_range_and_boundaries(self):
        lo, hi = mc.CALENDAR_RANGE
        self.assertEqual((lo, hi), (date(2026, 1, 1), date(2028, 12, 31)))                    # V5: official 2028 schedule registered
        self.assertTrue(mc.is_session(date(2028, 1, 3)))                                      # Monday 3 Jan 2028 is a session (not unsupported merely because the old table stopped at 2027)
        self.assertFalse(mc.is_session(date(2028, 1, 1))); self.assertFalse(mc.is_session(date(2028, 12, 31)))   # Saturday / Sunday
        self.assertTrue(mc.is_session(date(2028, 12, 29)))                                    # last session of 2028 (Friday)
        with self.assertRaises(ValueError) as cm: mc.is_session(date(2029, 1, 2))            # first weekday past the horizon: explicit, not guessed
        self.assertIn("extend HOLIDAYS", str(cm.exception))
        with self.assertRaises(ValueError): mc.is_session(date(2025, 12, 31))
    def test_2028_official_closures_and_early_closes(self):
        for d in (date(2028, 1, 17), date(2028, 2, 21), date(2028, 4, 14), date(2028, 5, 29), date(2028, 6, 19), date(2028, 7, 4), date(2028, 9, 4), date(2028, 11, 23), date(2028, 12, 25)):
            self.assertFalse(mc.is_session(d), d)
        self.assertEqual(sum(1 for d in mc.HOLIDAYS if d.year == 2028), 9)                   # no New Year's Day holiday observed for Saturday 1 Jan 2028
        for d in (date(2028, 7, 3), date(2028, 11, 24)):
            self.assertTrue(mc.is_session(d)); self.assertTrue(mc.is_early_close(d)); self.assertEqual(mc.close_time(d), mc.EARLY_CLOSE)
        self.assertEqual(mc.close_utc(date(2028, 7, 3)).hour, 17)                             # 13:00 EDT = 17:00 UTC
        self.assertEqual(mc.close_utc(date(2028, 7, 5)).hour, 20)                             # 16:00 EDT = 20:00 UTC
        self.assertFalse(mc.is_early_close(date(2028, 7, 5))); self.assertIn("2025-12-23", mc.CALENDAR_SOURCES[2028]); self.assertIn("NYSE", mc.CALENDAR_SOURCES[2028])
        self.assertTrue(mc.is_session(date(2026, 1, 2)))                                      # historical results preserved
    def test_2028_dates_carry_provenance(self):
        src = (REPO / "v3/u350/market_calendar.py").read_text()
        self.assertIn("2025-12-23", src); self.assertIn("rechecked", src)                    # every 2028 date is attributed to the official announcement


class NeffGuard(unittest.TestCase):
    def test_stored_first_read_keeps_neff_pending(self):
        art = json.loads((REPO / "output/oie/layered_dependency_first_read.json").read_text())
        self.assertEqual(art["n_eff"], "PENDING"); self.assertIn("no pooled statistic designated", art["n_eff_printed"])
        self.assertEqual(art["verdict"], "STRUCTURE_PRINTED"); self.assertEqual(art["edge_rule_coverage"]["structural_completeness"], "PARTIAL")
    def test_tool_constant_matches_and_no_numeric_neff_path_without_S(self):
        import yuclaw_layered_dependency as ld
        self.assertEqual(ld.N_EFF_PRINTED, "N_eff: PENDING — no pooled statistic designated (A1.7)")
        src = (REPO / "tools/yuclaw_layered_dependency.py").read_text()
        self.assertIn('"n_eff": "PENDING"', src)
        # components are not independent samples: the docstring commits to DERIVED N_eff only from a designated S
        self.assertIn("never asserted", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
