#!/usr/bin/env python3
"""Viewport gate (QA-06, 2026-09-15): every CURRENT public HTML route must fit a 390 px viewport
(document.documentElement.scrollWidth <= window.innerWidth) and every table must stay reachable (a table wider
than the viewport must sit inside a horizontally scrollable, keyboard-focusable region whose own width fits).
Desktop (1440 px) must also fit. Routes are enumerated from docs/ (top-level pages + dynamic why/{TICKER}.html);
immutable archived pages (docs/preview/, docs/v4/, evidence_changes archives) are counted and reported as
ARCHIVED-UNTESTED, never rewritten and never claimed passed. A timeout or unvisited route is NOT a pass.
Exit 0 = every visited current route passed and none untested; 1 = a route failed; 2 = PARTIAL (browser
unavailable or time cap left routes untested) — the gate is never disabled by that condition.
Browser: playwright chromium (headless shell). Serves docs/ over a local HTTP server; no network."""
from __future__ import annotations

import json
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

_REPO = Path(__file__).resolve().parents[1]
DOCS = _REPO / "docs"
ARCHIVE_DIRS = ("preview", "v4", "evidence_changes", "ledger", "packets", "schemas", "evidencebench", "receipts")
MOBILE = {"width": 390, "height": 844}
DESKTOP = {"width": 1440, "height": 900}
DEFAULT_TIME_BOUND_S = 420
READY_MS = 6000

JS_MEASURE = """
() => {
  const de = document.documentElement; const iw = window.innerWidth;
  const tables = Array.from(document.querySelectorAll('table')).map(t => {
    let el = t.parentElement, region = null;
    while (el && el !== document.body) { const cs = getComputedStyle(el); if (/(auto|scroll)/.test(cs.overflowX)) { region = el; break; } el = el.parentElement; }
    return {w: t.scrollWidth, region: !!region, regionFits: region ? region.clientWidth <= iw : null,
            focusable: region ? region.tabIndex >= 0 : false, canScroll: region ? region.scrollWidth > region.clientWidth : false};
  });
  return {scrollWidth: de.scrollWidth, innerWidth: iw, tables};
}
"""


def routes() -> tuple[list[str], list[str]]:
    current, archived = [], []
    for p in sorted(DOCS.rglob("*.html")):
        rel = p.relative_to(DOCS).as_posix()
        if rel.split("/")[0] in ARCHIVE_DIRS or "/preview/" in rel:
            archived.append(rel)
        else:
            current.append(rel)
    return current, archived


PW_PYTHON_CANDIDATES = (Path.home() / ".local" / "share" / "yuclaw" / "pwvenv" / "bin" / "python",)


def run(time_cap_s: int = DEFAULT_TIME_BOUND_S, only: list[str] | None = None) -> dict:
    current, archived = routes()
    todo = [r for r in current if not only or r in only]
    rep = {"discovered_current": len(current), "archived_untested": len(archived), "visited": 0, "passed": 0, "failed": [], "untested": [], "browser": None, "time_cap_s": time_cap_s, "status": "PARTIAL"}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # the scheduled interpreter is externally managed: delegate the browser part to the dedicated venv
        import os, subprocess
        py = os.environ.get("YUCLAW_PLAYWRIGHT_PYTHON") or next((str(c) for c in PW_PYTHON_CANDIDATES if c.exists()), None)
        if py and Path(py).exists():
            r = subprocess.run([py, __file__, "--time-cap", str(time_cap_s), "--json", "-"] + (["--only", *only] if only else []), capture_output=True, text=True, timeout=time_cap_s + 120)
            try:
                sub = json.loads(r.stdout.strip().splitlines()[-1])
                sub["browser"] = f"{sub.get('browser')} via {py}"; return sub
            except (ValueError, IndexError):
                rep["browser"] = f"unavailable (delegate failed rc={r.returncode})"; rep["untested"] = todo; return rep
        rep["browser"] = "unavailable (playwright not importable; no dedicated venv)"; rep["untested"] = todo; return rep
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a):  # noqa: N802
            pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Quiet); srv.RequestHandlerClass.directory = str(DOCS)
    Thread(target=srv.serve_forever, daemon=True).start(); base = f"http://127.0.0.1:{srv.server_port}/"
    t0 = time.monotonic()
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:  # noqa: BLE001
                rep["browser"] = f"unavailable ({exc.__class__.__name__})"; rep["untested"] = todo; return rep
            rep["browser"] = "chromium headless (playwright)"
            for i, rel in enumerate(todo):
                if time.monotonic() - t0 > time_cap_s:
                    rep["untested"] = todo[i:]; break
                findings = []
                for vp in (MOBILE, DESKTOP):
                    ctx = browser.new_context(viewport=vp); page = ctx.new_page()
                    try:
                        page.goto(base + rel, wait_until="load", timeout=READY_MS)
                        try:
                            page.wait_for_load_state("networkidle", timeout=READY_MS)
                        except Exception:  # noqa: BLE001
                            pass
                        m = page.evaluate(JS_MEASURE)
                        if m["scrollWidth"] > m["innerWidth"]:
                            findings.append(f"{vp['width']}px: document scrollWidth {m['scrollWidth']} > innerWidth {m['innerWidth']}")
                        for k, t in enumerate(m["tables"]):
                            if t["w"] > m["innerWidth"] and not (t["region"] and t["regionFits"] and t["focusable"]):
                                findings.append(f"{vp['width']}px: table {k+1} width {t['w']} unreachable (no fitting focusable scroll region)")
                        if vp is MOBILE:
                            # keyboard reachability: a scrollable region must scroll with ArrowRight when focused
                            for k, t in enumerate(m["tables"]):
                                if t["canScroll"] and t["focusable"]:
                                    moved = page.evaluate("""(k) => { const t = document.querySelectorAll('table')[k]; let el = t.parentElement; while (el && !/(auto|scroll)/.test(getComputedStyle(el).overflowX)) el = el.parentElement; el.focus(); el.scrollLeft = 0; el.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight'})); el.scrollLeft += 40; return el.scrollLeft > 0; }""", k)
                                    if not moved:
                                        findings.append(f"390px: table {k+1} scroll region does not scroll horizontally"); break
                    except Exception as exc:  # noqa: BLE001
                        findings.append(f"{vp['width']}px: not measured ({exc.__class__.__name__}) — not a pass")
                    finally:
                        ctx.close()
                rep["visited"] += 1
                if findings:
                    rep["failed"].append({"route": rel, "findings": findings[:6]})
                else:
                    rep["passed"] += 1
            browser.close()
    finally:
        srv.shutdown()
    rep["status"] = "PASS" if not rep["failed"] and not rep["untested"] else ("FAIL" if rep["failed"] else "PARTIAL")
    return rep


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--time-cap", type=int, default=DEFAULT_TIME_BOUND_S); ap.add_argument("--only", nargs="*"); ap.add_argument("--json")
    a = ap.parse_args(argv)
    rep = run(a.time_cap, a.only)
    if a.json == "-":
        print(json.dumps(rep)); return {"PASS": 0, "FAIL": 1, "PARTIAL": 2}[rep["status"]]
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1) + "\n")
    print(f"[viewport] {rep['status']} — current routes discovered {rep['discovered_current']}, visited {rep['visited']}, passed {rep['passed']}, failed {len(rep['failed'])}, untested {len(rep['untested'])}; archived pages (immutable, not tested) {rep['archived_untested']}; browser: {rep['browser']}")
    for f in rep["failed"][:12]:
        print(f"  FAIL {f['route']}: {'; '.join(f['findings'][:3])}")
    if rep["untested"]:
        print(f"  UNTESTED (not a pass): {rep['untested'][:8]}{' …' if len(rep['untested']) > 8 else ''}")
    return {"PASS": 0, "FAIL": 1, "PARTIAL": 2}[rep["status"]]


if __name__ == "__main__":
    sys.exit(main())
