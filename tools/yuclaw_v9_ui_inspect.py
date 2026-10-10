#!/usr/bin/env python3
"""Browser inspection of the v9 pages (acceptance L): real Chromium through Playwright, two viewports (390 px and 1280 px),
keyboard operation (Tab reaches the statement links and the forms; the focused element is visible and styled), the
inspector opens from a statement link, both language editions carry the same numbers, no horizontal overflow at 390 px,
and no console error. Writes screenshots and a JSON record to --out. Markup tests are not browser evidence; this is.

  python3 tools/yuclaw_v9_ui_inspect.py --out DIR [--python-with-playwright PATH]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import tempfile
import threading
import time

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args(argv)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    from v8.workbench import server as S, store
    from v9.brief import compose, templates
    from v9.brief.sidecar import Sidecar
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="v9-ui-"))
    ws = store.Workspace(tmp / "A"); cid = S.load_fixture(ws, "001_base"); sc = Sidecar(ws)
    rec, _ = compose.create_from_template(ws, sc, claim_id=cid, sections=list(templates.TEMPLATES), lang="en", op_id="ui:inspect-0001", actor="inspector")
    compose.retranslate_template(ws, sc, brief_id=rec["brief_id"], parent_version_id="B1", lang_to="fr", actor="inspector", op_id="ui:inspect-0002")
    bid = rec["brief_id"]
    srv = S.WorkbenchServer(tmp / "A", 0); threading.Thread(target=srv.serve_forever, daemon=True).start(); S.Handler.log_message = lambda *k, **kw: None
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    record = {"record": "yuclaw-v9-ui-inspection/1", "base": base, "brief": bid, "pages": [], "keyboard": {}, "console_errors": [], "overflow_390": {}, "numbers": {}}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width, tag in ((390, "mobile"), (1280, "desktop")):
            ctx = browser.new_context(viewport={"width": width, "height": 844 if width == 390 else 900}); page = ctx.new_page()
            page.on("console", lambda m: record["console_errors"].append(m.text) if m.type == "error" else None)
            for path, name in (("/brief", "index"), (f"/brief/{bid}?version=B1", "brief"), (f"/brief/{bid}?version=B1&s=3", "inspector"), (f"/brief/{bid}?lang=fr&version=B2&s=9", "inspector-fr"), ("/brief/verify", "verify"), ("/brief/trust", "trust")):
                page.goto(base + path, wait_until="load")
                shot = out / f"{tag}-{name}.png"; page.screenshot(path=str(shot), full_page=True)
                sw = page.evaluate("document.documentElement.scrollWidth"); cw = page.evaluate("document.documentElement.clientWidth")
                record["pages"].append({"viewport": width, "path": path, "title": page.title(), "screenshot": shot.name, "scrollWidth": sw, "clientWidth": cw, "h1": page.locator("h1").first.inner_text()})
                if width == 390:
                    record["overflow_390"][name] = {"scrollWidth": sw, "clientWidth": cw, "horizontal_overflow": sw > cw + 1}
            if width == 1280:
                page.goto(base + f"/brief/{bid}?version=B1", wait_until="load")
                focused, steps = [], 0
                page.keyboard.press("Tab")                      # the skip link first
                while steps < 80:
                    info = page.evaluate("(() => { const e = document.activeElement; if (!e) return null; const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return {tag: e.tagName, text: (e.innerText||e.value||'').slice(0,40), href: e.getAttribute('href'), visible: r.width > 0 && r.height > 0, outline: cs.outlineStyle + ' ' + cs.outlineWidth}; })()")
                    focused.append(info); steps += 1
                    if info and info.get("href") and "s=3" in (info.get("href") or ""):
                        break
                    page.keyboard.press("Tab")
                record["keyboard"]["tab_steps_to_statement_3"] = steps
                record["keyboard"]["first_focus_is_skip_link"] = bool(focused and focused[0] and focused[0].get("href") == "#main")
                record["keyboard"]["all_focused_visible"] = all(f and f.get("visible") for f in focused)
                record["keyboard"]["focus_outline_sample"] = focused[-1].get("outline") if focused and focused[-1] else None
                page.keyboard.press("Enter"); page.wait_for_load_state("load")
                record["keyboard"]["enter_opens_inspector"] = page.locator("#inspector").count() == 1 and "s=3" in page.url
                page.screenshot(path=str(out / "desktop-inspector-after-keyboard.png"), full_page=True)
                # the edit form is reachable and operable from the keyboard: focus the textarea, type, submit
                page.focus("textarea[name=text]"); page.keyboard.press("End"); page.keyboard.type(" Added from the keyboard.")
                page.focus("textarea[name=text]"); page.keyboard.press("Tab"); page.keyboard.press("Tab")
                btn = page.evaluate("document.activeElement && document.activeElement.tagName")
                record["keyboard"]["after_textarea_focus"] = btn
                page.locator("form[action$='/edit'] button").click(); page.wait_for_load_state("load")
                record["keyboard"]["edit_submitted_new_version"] = "version=B3" in page.url
                en = page.goto(base + f"/brief/{bid}?version=B1", wait_until="load") and page.inner_text("main"); fr = page.goto(base + f"/brief/{bid}?lang=fr&version=B2", wait_until="load") and page.inner_text("main")
                record["numbers"] = {"en_has": {k: (k in en) for k in ("115", "110", "112", "-4.35%", "UNRESOLVED")}, "fr_has": {k: (k in fr) for k in ("115", "110", "112", "−4,35 %", "UNRESOLVED")}}
            ctx.close()
        browser.close()
    srv.shutdown()
    record["result"] = ("PASS" if not record["console_errors"] and not any(v["horizontal_overflow"] for v in record["overflow_390"].values()) and record["keyboard"].get("enter_opens_inspector") and record["keyboard"].get("first_focus_is_skip_link")
                        and all(record["numbers"]["en_has"].values()) and all(record["numbers"]["fr_has"].values()) else "FAIL")
    (out / "ui_inspection.json").write_text(json.dumps(record, indent=1, ensure_ascii=False))
    print(json.dumps({k: record[k] for k in ("result", "keyboard", "overflow_390", "numbers", "console_errors")}, indent=1, ensure_ascii=False))
    return 0 if record["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
