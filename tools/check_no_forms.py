#!/usr/bin/env python3
"""
No-form / no-upload / no-payment gate (Signal Review order, 2026-08-04) —
the counsel-armed state made mechanical: nothing anywhere in docs/ may
collect data or money. Asserts across every docs/**/*.html:

  F1  no <form element
  F2  no <input, <textarea, <select, or type="file" upload element
  F3  no payment integration marker (stripe, paypal, checkout.js,
      braintree, square, "credit card", data-price, buy-now)

Exit 0 green / 1 violation. Runs in the daily chain as a hard gate.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"

F1 = re.compile(r"<form\b", re.I)
# F2: collectable inputs only — the documented transmit-nothing
# exemption. A bare <input> or <select> with no name attribute is a
# client-side widget (preview filter boxes; the Explorer's filter/sort
# controls) — with <form> banned outright by F1 it has nowhere to
# submit, and F3 covers payment scripts. NAMED inputs/selects,
# textareas, and file inputs are always violations.
F2 = re.compile(r"<input\b[^>]*\bname=|<select\b[^>]*\bname=|"
                r"<textarea\b|type=[\"']file[\"']", re.I)
F3 = re.compile(r"stripe|paypal|braintree|checkout\.js|squareup|"
                r"credit card|data-price|buy-now|add.to.cart", re.I)


def main() -> int:
    problems = []
    for p in sorted(DOCS.rglob("*.html")):
        t = p.read_text(errors="replace")
        rel = p.relative_to(DOCS)
        for label, rx in (("F1 form", F1), ("F2 input/upload", F2),
                          ("F3 payment marker", F3)):
            m = rx.search(t)
            if m:
                line = t[:m.start()].count("\n") + 1
                problems.append(f"{rel}:{line}: {label} — "
                                f"'{m.group(0)[:40]}'")
    if problems:
        print("NO-FORM GATE FAILED (docs/ must never collect data or "
              "money):")
        for p in problems:
            print(f"  · {p}")
        return 1
    n = len(list(DOCS.rglob("*.html")))
    print(f"[no-form-gate] OK — {n} html files: zero form/upload/payment "
          f"elements anywhere in docs/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
