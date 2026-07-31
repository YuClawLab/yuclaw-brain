#!/usr/bin/env python3
"""
Sector-ETF constituent-weight ingestion (v5.2 Part 3b).

Fetches ISSUER-DISCLOSED daily holdings for the universe's SPDR sector ETFs
(State Street daily holdings XLSX — a published fund disclosure, same class
of source as the SMH snapshot), stores dated snapshots to
data/holdings/<TICKER>.json with as-of date, retrieval timestamp, and source
URL. Weights are used ONLY to derive internal coverage/overlap statistics —
no licensed index data is redistributed (derived overlaps and coverage
shares only, matching the standing Canada-lens rule).

Coverage honesty: IBB (iShares) and SMH (VanEck; existing manual snapshot in
v3/lab/etf_evidence.py) are NOT fetched by this tool — listed as remaining
gaps in the output manifest, not silently skipped.
"""
from __future__ import annotations

import json
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPDR = ["XLK", "XLF", "XLE", "XLV", "XLU", "XLI", "XLY", "XLP", "XLB",
        "XLRE", "XLC", "KRE", "XBI"]
NOT_FETCHED = {"IBB": "iShares — different disclosure endpoint, not yet wired",
               "SMH": "VanEck — existing dated manual snapshot "
                      "(v3/lab/etf_evidence.SMH_HOLDINGS, as of 2026-07-03)"}
URL = ("https://www.ssga.com/library-content/products/fund-data/etfs/us/"
       "holdings-daily-us-en-{t}.xlsx")
OUT_DIR = _REPO / "data" / "holdings"
UA = "Mozilla/5.0 (research; contact vzhang2099@gmail.com)"


def fetch_one(t: str) -> dict | None:
    import openpyxl
    req = urllib.request.Request(URL.format(t=t.lower()),
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        blob = r.read()
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as tf:
        tf.write(blob)
        tf.flush()
        ws = openpyxl.load_workbook(tf.name).active
    rows = list(ws.iter_rows(values_only=True))
    as_of = None
    for row in rows[:5]:
        if row[0] and "As of" in str(row[1] or ""):
            as_of = datetime.strptime(str(row[1]).replace("As of ", ""),
                                      "%d-%b-%Y").date().isoformat()
    hdr_i = next(i for i, row in enumerate(rows)
                 if row[0] == "Name" and "Weight" in [str(c) for c in row])
    w_col = [str(c) for c in rows[hdr_i]].index("Weight")
    t_col = [str(c) for c in rows[hdr_i]].index("Ticker")
    holdings = {}
    for row in rows[hdr_i + 1:]:
        tk, w = row[t_col], row[w_col]
        if not tk or w is None:
            continue
        try:
            holdings[str(tk).strip()] = round(float(w), 4)
        except ValueError:
            continue
    if not holdings or as_of is None:
        return None
    return {"etf": t, "as_of": as_of,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_url": URL.format(t=t.lower()),
            "n_holdings": len(holdings),
            "weight_sum_pct": round(sum(holdings.values()), 2),
            "renormalization": ("weights used only over covered subsets, "
                                "renormalized per analysis; derived "
                                "statistics only"),
            "holdings": holdings}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ok, failed = [], []
    for t in SPDR:
        try:
            snap = fetch_one(t)
            if snap is None:
                raise ValueError("no holdings parsed")
            (OUT_DIR / f"{t}.json").write_text(json.dumps(snap, indent=1))
            ok.append(f"{t} (n={snap['n_holdings']}, as-of {snap['as_of']})")
        except Exception as exc:                    # noqa: BLE001
            failed.append(f"{t}: {str(exc)[:80]}")
    manifest = {"fetched": ok, "failed": failed,
                "not_fetched_disclosed": NOT_FETCHED,
                "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[sector-holdings] fetched {len(ok)}/{len(SPDR)}: {ok}")
    if failed:
        print(f"[sector-holdings] FAILED: {failed}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
