# V9-001 — browser inspection of the v9 pages (acceptance L)

Produced by `tools/yuclaw_v9_ui_inspect.py` with real Chromium (Playwright) on 2026-10-10 against the candidate branch:
390 px and 1280 px viewports, keyboard operation (skip link first, Tab to a statement link, Enter opens the inspector,
an edit submitted from the keyboard), no horizontal overflow at 390 px, both language editions carrying the same
numbers, no console error. `ui_inspection.json` is the record; the two PNGs are the inspector at both widths.
Record directory, not runtime code: excluded from the wheel and sdist like v8/V8-*.
