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
        self.assertEqual((lo, hi), (date(2026, 1, 1), date(2027, 12, 31)))
        fn = next(getattr(mc, n) for n in ("is_trading_day", "trading_day", "is_session") if hasattr(mc, n))
        self.assertIsInstance(fn(date(2027, 12, 31)), bool)            # last supported day answers
        with self.assertRaises(ValueError) as cm: fn(date(2028, 1, 3))   # first weekday past the horizon: explicit, not guessed
        self.assertIn("extend HOLIDAYS", str(cm.exception))
        with self.assertRaises(ValueError): fn(date(2025, 12, 31))
    def test_no_2028_dates_without_provenance(self):
        src = (REPO / "v3/u350/market_calendar.py").read_text()
        self.assertNotIn("2028", src.replace("before 2028", ""))          # no guessed 2028 closures in source


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
