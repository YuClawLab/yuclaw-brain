"""8.0.1 C09 — the Universe Explorer's filters and sortable headings have accessible semantics and work from the keyboard.

8.0.0: three <select>s and the ticker input had no accessible name; sorting was `<th onclick>` — no focus, no Enter/Space,
no `aria-sort`. Two layers of check:
  * STATIC (always runs): the staged page's markup — labels bound to every control, <th scope=col> with a real <button> and
    an aria-sort state, a polite status region, no inline event handlers left, no form / named control (the transmit-nothing rule);
  * BROWSER (runs when a Playwright driver is installed; otherwise SKIPPED with that reason): keyboard-only filtering and
    sorting, aria-sort and focus after activation, deterministic order, zero results, reset, the ?sector= link, a 390 px viewport.
These automated checks are not a WCAG or screen-reader certification."""
import json, pathlib, re, unittest
from html.parser import HTMLParser

REPO = pathlib.Path(__file__).resolve().parents[1]; PAGE = REPO / "docs" / "explorer.html"


class Dom(HTMLParser):
    def __init__(self):
        super().__init__(); self.els = []; self.stack = []

    def handle_starttag(self, tag, attrs):
        el = {"tag": tag, "attrs": dict(attrs), "parent": self.stack[-1] if self.stack else None}; self.els.append(el)
        if tag not in ("input", "meta", "link", "br", "img", "option") or tag == "option":
            self.stack.append(el)

    def handle_endtag(self, tag):
        while self.stack and self.stack.pop()["tag"] != tag:
            pass


class Static(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PAGE.read_text(encoding="utf-8"); cls.dom = Dom(); cls.dom.feed(re.sub(r"<script>.*?</script>", "", cls.html, flags=re.S)); cls.els = cls.dom.els

    def test_every_filter_control_has_a_visible_label_bound_to_it(self):
        controls = [e for e in self.els if e["tag"] in ("input", "select")]; self.assertEqual(sorted(e["attrs"]["id"] for e in controls), ["fgr", "flb", "fsc", "ftk"])
        labels = {e["attrs"].get("for") for e in self.els if e["tag"] == "label"}
        for c in controls:
            self.assertIn(c["attrs"]["id"], labels); self.assertNotIn("name", c["attrs"])                     # named, but never a submittable field
        for text in ("Ticker <input", "Signal label <select", "Evidence grade <select", "Sector <select"):
            self.assertIn(text, self.html)
        self.assertNotIn("<form", self.html.lower())

    def test_sortable_headings_are_buttons_in_column_headers_with_a_sort_state(self):
        ths = [e for e in self.els if e["tag"] == "th"]; self.assertEqual(len(ths), 8)
        for th in ths:
            self.assertEqual(th["attrs"].get("scope"), "col"); self.assertIn(th["attrs"].get("aria-sort"), ("none", "ascending", "descending"))
        self.assertEqual([t["attrs"]["aria-sort"] for t in ths].count("descending"), 1)                        # the default order (score, descending) is announced
        btns = [e for e in self.els if e["tag"] == "button" and "sort" in e["attrs"].get("class", "")]; self.assertEqual(len(btns), 8)
        self.assertTrue(all(b["attrs"].get("type") == "button" and b["parent"]["tag"] == "th" and b["attrs"].get("data-key") for b in btns))
        self.assertIsNone(re.search(r"<th[^>]*onclick|\son(click|change|input)=", self.html))                   # no inline handlers left
        status = [e for e in self.els if e["attrs"].get("id") == "count"][0]; self.assertEqual((status["attrs"].get("role"), status["attrs"].get("aria-live")), ("status", "polite"))
        self.assertTrue(any(e["tag"] == "button" and e["attrs"].get("id") == "reset" for e in self.els))


class Browser(unittest.TestCase):
    def test_keyboard_only_filtering_and_sorting(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("no Playwright driver in this environment (the static checks above ran); run with a Playwright-equipped interpreter for the browser check")
        rows_total = len(json.loads((REPO / "docs" / "explorer_data.json").read_text())["rows"])
        with sync_playwright() as pw:
            br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 390, "height": 800}); pg.goto(PAGE.as_uri() + "?sector=Technology"); errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
            tickers = lambda: pg.eval_on_selector_all("#tb tr td:first-child a", "xs => xs.map(x => x.textContent)")
            self.assertEqual(pg.input_value("#fsc"), "Technology"); self.assertTrue(0 < len(tickers()) < rows_total)                       # the deep link still filters
            self.assertEqual(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), True)                              # narrow viewport: the page itself does not scroll sideways
            pg.focus("#reset"); pg.keyboard.press("Enter"); self.assertEqual(len(tickers()), rows_total); self.assertEqual(pg.evaluate("document.activeElement.id"), "ftk")
            for label in ("Ticker", "Signal label", "Evidence grade", "Sector"):
                self.assertEqual(pg.get_by_label(label, exact=False).first.count(), 1, label)                                                   # accessible names resolve in the browser's tree
            btn = pg.get_by_role("button", name="Ticker"); btn.focus(); pg.keyboard.press("Enter")
            self.assertEqual(pg.get_attribute("th:has(button[data-key=ticker])", "aria-sort"), "descending"); self.assertEqual(tickers(), sorted(tickers(), reverse=True))
            self.assertEqual(pg.evaluate("document.activeElement.dataset.key"), "ticker")                                                       # focus stayed on the heading that was used
            pg.keyboard.press("Space"); self.assertEqual(pg.get_attribute("th:has(button[data-key=ticker])", "aria-sort"), "ascending"); self.assertEqual(tickers(), sorted(tickers()))
            self.assertEqual(pg.get_attribute("th:has(button[data-key=score])", "aria-sort"), "none")
            pg.get_by_role("button", name="Sector").focus(); pg.keyboard.press("Enter"); first = tickers(); pg.keyboard.press("Enter"); pg.keyboard.press("Enter"); self.assertEqual(tickers(), first)   # ties break by ticker: the same order every time
            pg.focus("#ftk"); pg.keyboard.type("zzzz"); self.assertEqual(tickers(), []); self.assertIn("No name matches these filters", pg.inner_text("#tb")); self.assertIn("0 of", pg.inner_text("#count"))
            pg.focus("#reset"); pg.keyboard.press("Space"); self.assertEqual(len(tickers()), rows_total); self.assertEqual(pg.get_attribute("th:has(button[data-key=score])", "aria-sort"), "descending")
            pg.focus("#flb"); pg.keyboard.press("ArrowDown"); self.assertLess(len(tickers()), rows_total)                                       # a select operated from the keyboard filters
            pg.click("th button[data-key=score]"); self.assertEqual(pg.get_attribute("th:has(button[data-key=score])", "aria-sort"), "ascending")   # the mouse still works
            br.close()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
