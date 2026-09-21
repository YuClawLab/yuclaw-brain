"""8.0.1 C01 — the Validation Lab's sentences are derived from the same numbers as its tables.

8.0.0 said "forward 5d IC +0.09", "the forward 20-day IC is positive on all observed dates" and "2,847 leaf hashes"
while its own tables and the public replay bundle said -0.0277, -0.0399 with 43% positive dates, and 7,192 leaves.
Synthetic rigor dictionaries (positive, negative, zero, unreliable, unavailable) must give prose whose numbers are the
table's numbers, a negative or non-significant result must never read as positive, a changed bundle must change the
staged sentences and nothing else, and the staged page in this tree must agree with the bundle published beside it."""
import copy, json, pathlib, re, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
import sys; sys.path.insert(0, str(REPO))                                        # noqa: E702
from v3.web import lab_prose as L                                               # noqa: E402


def ic(mean, p, share, n, reliable=True):
    return {"mean_ic": mean, "nw_p_value": p, "nw_t_stat": 1.0, "nw_lag": 4, "t_reliable": reliable, "n_dates": n, "ic_positive_share": share}


def rig(ic5, ic20, spread_p=0.4, spread=-0.002, alpha_p=0.2, alpha=-0.001, evaluable=True):
    return {"forward": {"evaluable": evaluable, "window": ["2026-05-20", "2026-09-18"], "n_periods": 82,
                        "spreads": {"top_minus_bottom": {"mean_per_period": spread, "p_value": spread_p}, "top_minus_universe": {"mean_per_period": spread, "p_value": 0.5}},
                        "ic": {"1": ic(0.0, 0.9, 0.5, 87), "5": ic5, "20": ic20}, "market_model": {"vs_universe": {"alpha_per_period": alpha, "p_alpha": alpha_p}, "vs_spy": {"alpha_per_period": alpha, "p_alpha": 0.6}}}}


NEGATIVE = rig(ic(-0.0277, 0.477, 0.47, 83), ic(-0.0399, 0.244, 0.43, 67))
POSITIVE_SIG = rig(ic(0.0912, 0.012, 0.71, 83), ic(0.0503, 0.2, 0.62, 67), spread_p=0.01, spread=0.004)
NEGATIVE_SIG = rig(ic(-0.0912, 0.012, 0.29, 83), ic(-0.0503, 0.2, 0.38, 67), alpha_p=0.003, alpha=-0.004)
ZERO = rig(ic(0.0, 1.0, 0.5, 83), ic(0.0, 1.0, 0.5, 67))
UNRELIABLE = rig(ic(0.09, 0.03, 0.8, 12, reliable=False), ic(0.08, 0.001, 1.0, 4, reliable=False))
UNAVAILABLE = rig(None, None, evaluable=False)
BUNDLE = {"n_leaves": 7192, "built_utc": "2026-09-18 23:02 UTC", "source_commit": "a3b3ed2ebac4"}


class DerivedProse(unittest.TestCase):
    def test_prose_carries_the_tables_numbers_and_never_flips_a_sign(self):
        t = L.rigor_reading(NEGATIVE) + L.ic_not_proven_line(NEGATIVE)
        for needle in ("-0.0399", "positive on 43% of 67 observed dates", "-0.0277", "positive on 47% of 83 observed dates", "not significant at 5%", "no forward spread, IC, or alpha is"):
            self.assertIn(needle, t)
        for wrong in ("+0.09", "all observed dates", "positive on 100%"):
            self.assertNotIn(wrong, t)
        self.assertEqual(L.fmt_ic(-0.027711582), "-0.0277"); self.assertEqual(L.headline(NEGATIVE), "No forward alpha has been statistically proven yet.")

    def test_a_significant_negative_result_is_called_negative_and_a_significant_positive_one_is_not_called_proof(self):
        t = L.rigor_reading(NEGATIVE_SIG); self.assertIn("5-day IC -0.0912 (p = 0.012) — NEGATIVE, adverse to the signal", t); self.assertIn("Every one of them is negative", t); self.assertNotIn("no forward spread, IC, or alpha is", t)
        self.assertIn("NEGATIVE", L.headline(NEGATIVE_SIG)); self.assertIn("NEGATIVE, adverse to the signal", L.ic_not_proven_line(NEGATIVE_SIG))
        t = L.rigor_reading(POSITIVE_SIG); self.assertIn("5-day IC +0.0912 (p = 0.012)", t); self.assertIn("top − bottom decile spread +0.400% per period", t); self.assertIn("One window is not proof", t)
        self.assertIn("not proof of forward alpha", L.headline(POSITIVE_SIG)); self.assertIn("replication pending", L.ic_not_proven_line(POSITIVE_SIG))

    def test_zero_unreliable_and_unavailable_are_said_as_such(self):
        self.assertIn("the forward 20-day IC is +0.0000, positive on 50% of 67 observed dates", L.ic_clause(ZERO["forward"], 20))
        t = L.rigor_reading(UNRELIABLE); self.assertIn("too few independent blocks to test; descriptive only", t); self.assertIn("no forward spread, IC, or alpha is", t)      # an unreliable t is never "significant"
        self.assertEqual(L.forward_significant(UNRELIABLE["forward"]), [])
        t = L.rigor_reading(UNAVAILABLE); self.assertIn("not evaluable yet", t); self.assertIn("insufficient evidence, not a positive and not a negative finding", t)
        self.assertIn("not evaluable yet", L.ic_not_proven_line(UNAVAILABLE)); self.assertIn("nothing about forward alpha is claimed", L.headline(UNAVAILABLE))
        self.assertIn("every statistic and every ledger leaf hash", L.reproducibility_line({})); self.assertIn("7,192 leaf hashes", L.reproducibility_line(BUNDLE)); self.assertIn("built 2026-09-18 23:02 UTC from a3b3ed2ebac4", L.reproducibility_line(BUNDLE))

    def test_the_generator_renders_prose_and_table_from_one_dictionary(self):
        from v3.web import render_validation_lab as R
        full = copy.deepcopy(json.loads((REPO / "docs" / "replay" / "lab_replay_bundle.json").read_text())["expected"]); i20 = full["forward"]["ic"]["20"]   # the complete public dictionary the page is rendered from
        i20.update({"mean_ic": -0.0399, "ic_positive_share": 0.43, "n_dates": 67, "nw_p_value": 0.244, "t_reliable": True})
        html = R.rigor_panel_html(full); self.assertIsNotNone(re.search(r"20-day.*?monospace'>-0\.0399</td>", html, re.S)); self.assertIn(">43%<", html)
        self.assertIn("The forward 20-day IC is -0.0399, positive on 43% of 67 observed dates", html)
        i20.update({"mean_ic": 0.0555, "ic_positive_share": 0.9}); html2 = R.rigor_panel_html(full)                                                 # change the data → table AND prose move together
        self.assertIn("monospace'>+0.0555</td>", html2); self.assertIn("The forward 20-day IC is +0.0555, positive on 90% of 67 observed dates", html2); self.assertNotIn("-0.0399", html2)
        full["forward"]["ic"]["5"].update({"mean_ic": -0.0277, "ic_positive_share": 0.47, "n_dates": 83, "nw_p_value": 0.477, "t_reliable": True})
        p = R.proven_html(82, full, BUNDLE); self.assertIn("7,192 leaf hashes", p); self.assertIn("forward 5d IC -0.0277", p); self.assertNotIn("2,847", p); self.assertNotIn("+0.09 loses", p)
        self.assertIn("No forward alpha has been statistically proven yet.", R.honest_reading_html(NEGATIVE))

    def test_restaging_changes_only_the_derived_sentences_and_a_changed_bundle_changes_them_again(self):
        page = ("<table><tr><td>UNTOUCHED -0.0399</td></tr></table><strong>No forward alpha has been statistically proven yet.</strong>"
                "<li>One-command reproducibility — every statistic + 2,847 leaf hashes re-derive from published data</li><li>IC significance — forward 5d IC +0.09 loses significance after overlap (HAC) correction; 20d descriptive only</li>"
                "<p>Honest reading: at the current sample sizes, <strong>no forward spread</strong>. The forward 20-day IC is positive on\n all observed dates but has too few independent blocks to test. this panel recomputes with them.</p><footer>UNTOUCHED</footer>")
        self.assertEqual(len(L.stale(page, NEGATIVE, BUNDLE)), 4)
        one = L.restage(page, NEGATIVE, BUNDLE); self.assertEqual(L.stale(one, NEGATIVE, BUNDLE), []); self.assertIn("<td>UNTOUCHED -0.0399</td>", one); self.assertIn("<footer>UNTOUCHED</footer>", one); self.assertNotIn("2,847", one); self.assertNotIn("all observed dates", one)
        self.assertEqual(L.restage(one, NEGATIVE, BUNDLE), one)                                                                                 # idempotent
        self.assertEqual(sorted(L.stale(one, POSITIVE_SIG, dict(BUNDLE, n_leaves=7271))), ["headline", "ic-significance", "reproducibility", "rigor-reading"])   # a refreshed bundle makes the old sentences stale …
        two = L.restage(one, POSITIVE_SIG, dict(BUNDLE, n_leaves=7271)); self.assertEqual(L.stale(two, POSITIVE_SIG, dict(BUNDLE, n_leaves=7271)), []); self.assertIn("7,271 leaf hashes", two)   # … and regenerates matching ones
        with self.assertRaises(ValueError):
            L.restage("<p>a page without the fragments</p>", NEGATIVE, BUNDLE)

    def test_the_staged_page_in_this_tree_agrees_with_the_bundle_published_beside_it(self):
        b = json.loads((REPO / "docs" / "replay" / "lab_replay_bundle.json").read_text()); html = (REPO / "docs" / "validation_lab.html").read_text()
        self.assertEqual(L.stale(html, b["expected"], L.bundle_identity(b)), [])
        ic20 = b["expected"]["forward"]["ic"]["20"]; self.assertIn(f"The forward 20-day IC is {ic20['mean_ic']:+.4f}", html); self.assertIn(f"{L.bundle_identity(b)['n_leaves']:,} leaf hashes", html)


if __name__ == "__main__":
    unittest.main()
