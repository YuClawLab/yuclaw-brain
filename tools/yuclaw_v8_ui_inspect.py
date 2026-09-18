#!/usr/bin/env python3
"""Workbench UI inspection (UX-11) — automated DOM checks on the real pages in Chromium: keyboard reachability and order,
visible focus, programmatic field labels, table headers, page-level horizontal overflow at a phone-width viewport, status
text that does not depend on colour, document language/title/landmarks/heading order.

    <playwright venv>/bin/python tools/yuclaw_v8_ui_inspect.py --out <dir> [--candidate <sha>]

Test-time tool only (never packaged). What it is NOT: a human study, a screen-reader session, a usability review or an
accessibility certification. It records what a script could observe. Research and education only. Not investment advice.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone

_REPO = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from v8.workbench import server as S  # noqa: E402

NARROW = {"width": 375, "height": 800}
WIDE = {"width": 1280, "height": 900}

PAGE_JS = r"""
() => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const controls = [...document.querySelectorAll('input:not([type=hidden]), select, textarea')].filter(vis);
  const name = c => (c.labels && c.labels.length) || c.getAttribute('aria-label') || c.getAttribute('aria-labelledby');
  const unnamed = controls.filter(c => !name(c)).map(c => c.tagName.toLowerCase() + '[name=' + c.getAttribute('name') + ']');
  const orphanLabels = [...document.querySelectorAll('label')].filter(l => !l.control).map(l => l.textContent.trim().slice(0, 60));
  const tables = [...document.querySelectorAll('table')];
  const thNoScope = [...document.querySelectorAll('th')].filter(t => !t.getAttribute('scope')).length;
  const tablesNoWrap = tables.filter(t => { const p = t.parentElement; return !(p && getComputedStyle(p).overflowX === 'auto'); }).length;
  const tablesNoHeader = tables.filter(t => !t.querySelector('th')).length;
  const heads = [...document.querySelectorAll('h1,h2,h3,h4')].map(h => +h.tagName[1]);
  let headSkips = 0; for (let i = 1; i < heads.length; i++) if (heads[i] - heads[i-1] > 1) headSkips++;
  const status = [...document.querySelectorAll('.ok,.bad,.warn')].filter(vis);
  const statusNoText = status.filter(s => !s.textContent.trim()).length;
  const blocks = [...document.querySelectorAll('.err,.notice')].filter(vis);
  const blocksNoRole = blocks.filter(b => !b.getAttribute('role')).length;
  const focusable = [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [tabindex]:not([tabindex="-1"])')].filter(vis);
  return {title: document.title, lang: document.documentElement.getAttribute('lang'), h1: document.querySelectorAll('h1').length, main: document.querySelectorAll('main').length,
          nav_labelled: [...document.querySelectorAll('nav')].every(n => n.getAttribute('aria-label')), skip_link: !!document.querySelector('a[href="#main"]'),
          controls: controls.length, unnamed_controls: unnamed, orphan_labels: orphanLabels, tables: tables.length, th_without_scope: thNoScope, tables_not_in_scroll_region: tablesNoWrap,
          tables_without_header_cells: tablesNoHeader, heading_level_skips: headSkips, status_elements: status.length, status_without_text: statusNoText, message_blocks: blocks.length,
          message_blocks_without_role: blocksNoRole, focusable: focusable.length,
          overflow_px: document.documentElement.scrollWidth - document.documentElement.clientWidth};
}
"""

FOCUS_JS = r"""
() => { const e = document.activeElement; if (!e || e === document.body) return null; const s = getComputedStyle(e);
  const all = [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [tabindex]:not([tabindex="-1"])')];
  return {index: all.indexOf(e), tag: e.tagName.toLowerCase(), name: e.getAttribute('name') || e.getAttribute('href') || e.textContent.trim().slice(0, 30), outline_style: s.outlineStyle, outline_width: s.outlineWidth, box_shadow: s.boxShadow}; }
"""


def _tab_walk(page, limit: int) -> dict:
    """Press Tab from the top of the document; record every stop, whether its focus indicator is visible, and whether
    every visible focusable element was reached in document order."""
    page.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
    expected = page.evaluate("""() => [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [tabindex]:not([tabindex="-1"])')].filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }).length""")
    # radio groups and the like do not occur in the workbench; every focusable element is its own tab stop
    stops = []; invisible = []
    for _ in range(min(expected + 2, limit)):
        page.keyboard.press("Tab")
        f = page.evaluate(FOCUS_JS)
        if f is None:
            break
        if stops and f == stops[0] and len(stops) >= expected:
            break
        stops.append(f)
        if f["outline_style"] == "none" or f["outline_width"] in ("0px", ""):
            if f["box_shadow"] in ("none", ""):
                invisible.append(f)
    idx = [f["index"] for f in stops]; in_order = all(b >= a for a, b in zip(idx, idx[1:]))      # a date input holds several inner stops on one element
    return {"expected_stops": expected, "reached": len(stops), "walk_truncated_at": limit if expected + 2 > limit else None, "all_reached": len(stops) >= min(expected, limit), "stops_without_visible_focus": invisible[:10],
            "first_stop": stops[0] if stops else None, "in_document_order": in_order}


def inspect_page(page, base: str, path: str, label: str, tab_limit: int) -> dict:
    page.set_viewport_size(WIDE); page.goto(base + path)
    wide = page.evaluate(PAGE_JS)
    tab = _tab_walk(page, tab_limit)
    page.set_viewport_size(NARROW); page.goto(base + path)
    narrow = page.evaluate(PAGE_JS)
    return {"page": label, "path": path, "wide": wide, "keyboard": tab, "narrow_overflow_px": narrow["overflow_px"], "narrow_viewport": NARROW}


def findings(rec: dict) -> list[str]:
    w = rec["wide"]; k = rec["keyboard"]; out = []
    if w["lang"] != "en": out.append("html lang is not 'en'")
    if w["h1"] != 1: out.append(f"{w['h1']} h1 elements")
    if not w["main"]: out.append("no <main> landmark")
    if not w["nav_labelled"]: out.append("nav without an accessible name")
    if not w["skip_link"]: out.append("no skip-to-content link")
    if w["unnamed_controls"]: out.append(f"{len(w['unnamed_controls'])} form control(s) without a programmatic label: {', '.join(w['unnamed_controls'][:8])}")
    if w["orphan_labels"]: out.append(f"{len(w['orphan_labels'])} <label> element(s) bound to no control: {'; '.join(w['orphan_labels'][:5])}")
    if w["th_without_scope"]: out.append(f"{w['th_without_scope']} header cell(s) without scope")
    if w["tables_without_header_cells"]: out.append(f"{w['tables_without_header_cells']} table(s) without header cells")
    if w["tables_not_in_scroll_region"]: out.append(f"{w['tables_not_in_scroll_region']} table(s) outside a horizontal scroll region")
    if w["heading_level_skips"]: out.append(f"{w['heading_level_skips']} heading level skip(s)")
    if w["status_without_text"]: out.append(f"{w['status_without_text']} coloured status element(s) without text")
    if w["message_blocks_without_role"]: out.append(f"{w['message_blocks_without_role']} error/notice block(s) without a role")
    if not k["all_reached"]: out.append(f"keyboard: {k['reached']} of {k['expected_stops']} focusable elements reached by Tab")
    if not k["in_document_order"]: out.append("keyboard: Tab order departs from document order")
    if rec.get("entries_retained") is False: out.append("a refused form did not come back with the entered values")
    if k["stops_without_visible_focus"]: out.append(f"keyboard: {len(k['stops_without_visible_focus'])} stop(s) without a visible focus indicator")
    if rec["narrow_overflow_px"] > 0: out.append(f"page scrolls horizontally by {rec['narrow_overflow_px']} px at {NARROW['width']} px width")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--out", required=True); ap.add_argument("--candidate"); ap.add_argument("--tab-limit", type=int, default=120)
    a = ap.parse_args(argv)
    from playwright.sync_api import sync_playwright
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    cand = a.candidate or subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO, capture_output=True, text=True).stdout.strip() or None
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "v8/workbench"], cwd=_REPO, capture_output=True, text=True).stdout.strip())
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-inspect-"))
    srv = S.WorkbenchServer(tmp / "ws", 0, candidate_commit=cand); threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = srv.origin; pages = []
    with sync_playwright() as p:
        br = p.chromium.launch(); page = br.new_page(viewport=WIDE)
        pages.append(inspect_page(page, base, "/", "workspace (empty)", a.tab_limit))
        pages.append(inspect_page(page, base, "/claim/new", "typed claim form (no source registered yet)", a.tab_limit))
        for fx in ("001_base", "002_missing_outcome", "004_incompatible_basis"):
            page.set_viewport_size(WIDE); page.goto(base + "/"); page.select_option("select[name=fixture]", fx); page.click("text=Load fixture")
        page.goto(base + "/"); hrefs = page.eval_on_selector_all("a[href^='/claim/']", "els => els.map(e => e.getAttribute('href'))")
        base_claim = next(h for h in hrefs if "-001-" in h); pending = next(h for h in hrefs if "-002-" in h); incomparable = next(h for h in hrefs if "-004-" in h)
        # one scientific record so /sci/S1 exists
        page.goto(base + "/sci"); page.select_option("select[name=example]", "example_exploratory_journal"); page.fill("input[name=actor]", "ui-inspection (automated)"); page.check("input[name=simulated]"); page.click("text=Replay through the kernel and record")
        # a refused form: a freeze with a source chosen and a claim id typed but every comparability field missing
        page.goto(base + "/claim/new"); page.fill("input[name=claim_id]", "KEEP-THIS-ENTRY"); page.fill("textarea[name=statement]", "kept statement"); page.select_option("select[name=source_id]", index=1)
        page.click("text=Save and freeze claim"); err = page.evaluate(PAGE_JS); err_url = page.url; text = page.locator("body").inner_text()
        kept = page.input_value("input[name=claim_id]") == "KEEP-THIS-ENTRY" and page.input_value("textarea[name=statement]") == "kept statement" and "nothing was written" in text and "fiscal_period" in text
        err_tab = _tab_walk(page, a.tab_limit); page.set_viewport_size(NARROW); err_narrow = page.evaluate(PAGE_JS)["overflow_px"]; page.set_viewport_size(WIDE)
        pages.append({"page": "refused freeze (comparability fields missing)", "path": err_url.replace(base, ""), "wide": err, "keyboard": err_tab, "narrow_overflow_px": err_narrow, "narrow_viewport": NARROW, "entries_retained": kept})
        for path, label in (("/", "workspace (three fixtures)"), ("/source", "step 1 source"), ("/source?as_of=2026-02-01T00:00:00Z", "step 1 source as-of view"), ("/claim/new", "step 2 typed claim form"),
                            (base_claim, "claim page (base fixture: steps 1-7)"), (base_claim + "?as_of=2026-03-01T00:00:00Z", "claim page as-of replay"), (pending, "claim page (missing outcome)"),
                            (incomparable, "claim page (incomparable basis)"), ("/notes", "research notes"), ("/dataset", "dataset coverage"), ("/sci", "scientific report"), ("/sci/S1", "scientific record"),
                            ("/verify", "verify an export"), ("/journal", "journal"), ("/help", "operator guide (in-app)")):
            r = page.goto(base + path)
            if r is not None and r.status == 404:
                pages.append({"page": label, "path": path, "absent": True}); continue
            pages.append(inspect_page(page, base, path, label, a.tab_limit))
        br.close()
    srv.shutdown(); srv.server_close()
    for rec in pages:
        rec["findings"] = [] if rec.get("absent") else findings(rec)
    total = sum(len(r["findings"]) for r in pages)
    log = {"record": "yuclaw-v8-ui-inspection/1", "recorded_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "candidate_commit": cand, "workbench_tree_dirty": dirty,
           "method": "Chromium via Playwright; DOM evaluation at 1280x900; Tab walk from the document top; page-level horizontal overflow at 375x800",
           "is_not": "a human study, a screen-reader session, a usability review or an accessibility certification; colour contrast and reading order were not measured by this script",
           "pages": pages, "pages_inspected": len([r for r in pages if not r.get("absent")]), "findings_total": total}
    (out / "ui_inspection.json").write_text(json.dumps(log, indent=1) + "\n")
    for rec in pages:
        print(f"[ui-inspect] {rec['page']}: " + ("ABSENT" if rec.get("absent") else ("clean" if not rec["findings"] else " | ".join(rec["findings"]))))
    print(f"[ui-inspect] findings {total} across {log['pages_inspected']} page(s) → {out / 'ui_inspection.json'}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
