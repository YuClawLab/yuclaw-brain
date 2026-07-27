#!/usr/bin/env python3
"""
Form-4 transaction-code taxonomy (ORDER v5.1 Part C) — deterministic,
DISPLAY-ONLY. Zero LLM, zero scoring-path contact: this tool reads
events.source_url, re-fetches each distinct Form-4 XML from EDGAR (none are
stored locally — verified), parses transaction codes with
xml.etree.ElementTree, and writes counts to output/oie/form4_taxonomy.json.
It never writes to the database and nothing here feeds C6 or any signal
(standing rule: C6 inputs untouched).

Code classes (SEC Form 4 transaction codes, form-level aff10b5One checkbox):
  S + 10b5-1 unchecked -> discretionary open-market sale
  S + 10b5-1 checked   -> plan sale (Rule 10b5-1)
  F -> tax-withholding disposition (mechanical)
  M -> option exercise / conversion (mechanical)
  A -> award / grant acquisition (mechanical)
  D -> disposition to issuer
  P -> open-market purchase
  other (G, C, J, ...) -> other
Counts cover BOTH the nonDerivative and derivative transaction tables;
dollar mass (shares x price) is summed from nonDerivative rows only (the
price field on derivative rows is not comparable). The 10b5-1 flag is the
form-level checkbox — one flag per filing, applied to its S rows.

Results are cached per-URL in output/oie/form4_xml_cache.json so reruns do
not refetch EDGAR.
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import psycopg2

from v3.lab.cohort_engine import DSN
from v3.lab.etf_evidence import canada_lens_holdings, overlap_summary
from v3.sources.form4_parser import _fetch

OUT_JSON = _REPO / "output" / "oie" / "form4_taxonomy.json"
CACHE = _REPO / "output" / "oie" / "form4_xml_cache.json"

CLASSES = ["S_discretionary", "S_plan_10b5_1", "F_tax_withholding",
           "M_exercise", "A_award", "D_to_issuer", "P_purchase", "other"]


def _truthy(s):
    return (s or "").strip().lower() in ("1", "true")


def parse_filing(xml_text: str) -> dict:
    """{plan_10b5_1, rows:[{code, table, shares, price}]} or {} on failure."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {}
    plan = False
    rows = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag == "aff10b5One":
            plan = plan or _truthy(el.text)
        if tag in ("nonDerivativeTransaction", "derivativeTransaction"):
            rec = {"code": "", "table": ("nonDeriv" if tag.startswith("nonD")
                                         else "deriv"),
                   "shares": 0.0, "price": 0.0}
            for child in el.iter():
                ctag = child.tag.split("}")[-1]
                if ctag == "transactionCode" and child.text:
                    rec["code"] = child.text.strip()
                elif ctag in ("transactionShares", "transactionPricePerShare"):
                    for v in child.iter():
                        if v.tag.split("}")[-1] == "value" and v.text:
                            try:
                                rec["shares" if ctag == "transactionShares"
                                    else "price"] = float(v.text.strip())
                            except ValueError:
                                pass
                            break
            rows.append(rec)
    return {"plan_10b5_1": plan, "rows": rows}


def classify(code: str, plan: bool) -> str:
    if code == "S":
        return "S_plan_10b5_1" if plan else "S_discretionary"
    return {"F": "F_tax_withholding", "M": "M_exercise", "A": "A_award",
            "D": "D_to_issuer", "P": "P_purchase"}.get(code, "other")


def main() -> int:
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}

    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT ticker, source_url,
                          count(*) AS ingested_events,
                          count(*) FILTER (WHERE (attributes->>'plan_10b5_1')
                                           = 'true') AS ev_plan
                   FROM events WHERE source_type = '4-parsed'
                   GROUP BY 1, 2""")
            ev_rows = cur.fetchall()

    urls = sorted({u for _t, u, _n, _p in ev_rows if u})
    print(f"[taxonomy] {len(urls)} distinct Form-4 filings "
          f"({sum(n for _t, _u, n, _p in ev_rows)} ingested events)")

    fetched = 0
    for u in urls:
        if u in cache:
            continue
        try:
            r = _fetch(u)
            cache[u] = parse_filing(r.text)
        except Exception as exc:               # noqa: BLE001 — record + continue
            cache[u] = {"error": str(exc)[:120]}
        fetched += 1
        if fetched % 50 == 0:
            print(f"[taxonomy] fetched {fetched}…")
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(cache))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache))
    errors = sum(1 for v in cache.values() if "error" in v)
    print(f"[taxonomy] fetch complete: {fetched} new, {errors} errors")

    # per-ticker aggregation
    url_by_ticker: dict = {}
    ingested: dict = {}
    for t, u, n, p in ev_rows:
        if u:
            url_by_ticker.setdefault(t, set()).add(u)
        d = ingested.setdefault(t, {"events": 0, "events_plan": 0})
        d["events"] += n
        d["events_plan"] += int(p or 0)

    per_ticker = {}
    for t, tset in sorted(url_by_ticker.items()):
        counts = {c: 0 for c in CLASSES}
        value = {"S_discretionary": 0.0, "S_plan_10b5_1": 0.0,
                 "F_tax_withholding": 0.0}
        filings, parse_fail = 0, 0
        for u in tset:
            f = cache.get(u) or {}
            if "rows" not in f:
                parse_fail += 1
                continue
            filings += 1
            for r in f["rows"]:
                cls = classify(r["code"], f["plan_10b5_1"])
                counts[cls] += 1
                if cls in value and r["table"] == "nonDeriv":
                    value[cls] += abs(r["shares"] * r["price"])
        per_ticker[t] = {
            "filings": filings, "parse_failures": parse_fail,
            "tx_counts": counts,
            "value_usd": {k: round(v) for k, v in value.items()},
            "ingested_events": ingested[t]["events"],
            "ingested_events_plan_10b5_1": ingested[t]["events_plan"],
        }

    def rollup(tickers, label):
        agg = {c: 0 for c in CLASSES}
        val = {"S_discretionary": 0.0, "S_plan_10b5_1": 0.0,
               "F_tax_withholding": 0.0}
        members = {}
        for t in tickers:
            if t not in per_ticker:
                continue
            members[t] = per_ticker[t]
            for c in CLASSES:
                agg[c] += per_ticker[t]["tx_counts"][c]
            for k in val:
                val[k] += per_ticker[t]["value_usd"][k]
        top3 = sorted(members, key=lambda t: -members[t]["ingested_events"])[:3]
        return {"label": label, "tx_counts": agg,
                "value_usd": {k: round(v) for k, v in val.items()},
                "members": {t: members[t] for t in members},
                "top3_by_events": top3}

    lenses = {"SMH": rollup(overlap_summary()["covered"], "SMH covered sleeve")}
    for lens, hold in canada_lens_holdings().items():
        lenses[lens] = rollup(sorted(hold), f"{lens} covered members")

    payload = {
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "scope": "all ingested Form 4s (events.source_type='4-parsed')",
        "n_filings": len(urls), "n_parse_errors": errors,
        "classes": CLASSES,
        "per_ticker": per_ticker,
        "lenses": lenses,
        "note": ("Deterministic XML parse, display-only; C6/scoring inputs "
                 "untouched. 10b5-1 is the form-level checkbox. Dollar mass "
                 "from nonDerivative rows only."),
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2))
    print(f"[taxonomy] wrote {OUT_JSON}")

    mu = per_ticker.get("MU")
    if mu:
        print(f"[MU] ingested events={mu['ingested_events']} "
              f"(plan-flagged {mu['ingested_events_plan_10b5_1']}) | "
              f"tx: {mu['tx_counts']} | value: {mu['value_usd']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
