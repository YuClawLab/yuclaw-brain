"""
№5 macro/commodity/FX context ingestion (order 2026-08-10g, decision A —
SOURCE NOW). Substrate only: this data feeds NO signal, score, label,
N_eff, story, or public page until a future registered protocol admits a
specific use (registration-before-computation applies to every USE).

Sources and series (the №5 packet scope; licensed sets excluded by the
packet's own recommendation):
  FRED      DCOILWTICO DCOILBRENTEU DEXCAUS DGS10 DGS2 DFF
            (all six are US-government-origin series republished on FRED:
            EIA oil spots, H.10 FX, H.15 rates — cite original source)
  EIA       PET.RWTC.D PET.RBRTE.D NG.RNGWHHD.D (v2 seriesid API)
  yfinance  CL=F NG=F (futures front-month closes)

POINT-IN-TIME NON-NEGOTIABLES (table macro_series):
  every datum: (source, series_id, observation_date, value,
  available_as_of = ingestion time, grade). Backfilled history is
  REFERENCE-grade — macro series get revised, so backfill must never
  masquerade as point-in-time knowledge; forward accrual (--accrue) is
  POINT_IN_TIME-grade. Vintage-true (ALFRED-style) data is NOT ingested
  (the packet is silent on it): the revision caveat is disclosed here and
  in internal/legal_drafts/export_restrictions.md. On re-fetch, an
  unchanged value keeps its original available_as_of; a changed value
  (source revision) updates value + available_as_of and increments
  revision_count — revisions are visible, never silent.

LICENSING / EXPORT (recorded 2026-08-10, see
internal/legal_drafts/export_restrictions.md):
  EIA — US-gov public domain; attribution requested
        ("Source: U.S. Energy Information Administration").
  FRED — API key required; attribution "Source: FRED, Federal Reserve
        Bank of St. Louis"; re-published third-party series require
        original-source citation (our six are US-gov-origin). ToS page
        bot-blocked from this box on 2026-08-10; owner re-verifies in a
        browser when creating the key.
  yfinance — SAME class as v3/track/price_history.py: raw OHLCV is never
        exported; only derived statistics reach any output.

Engineering: deterministic, no GPU (Form-4 pattern); idempotent upserts
keyed (source, series_id, observation_date); bounded backfill
(BACKFILL_START) with --resume; polite pacing (POLITE_DELAY_S between
API calls; FRED documents 120 req/min, EIA is generous, our full run is
~11 requests).

CLI:
    python3 -m v3.sources.macro_series --backfill            # REFERENCE
    python3 -m v3.sources.macro_series --backfill --resume
    python3 -m v3.sources.macro_series --accrue              # POINT_IN_TIME, daily window
    python3 -m v3.sources.macro_series --smoke               # one EIA series end-to-end
    python3 -m v3.sources.macro_series --status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import psycopg2

from v3.sources.edgar_poll import DB_DSN

ENV_PATH = Path.home() / ".yuclaw_env"

# Bounded backfill window start (temporal truncation — ledgered, exit-44
# site macro_backfill_window): ~10.6y is enough for oil-beta factor
# estimation; earlier history adds regime noise, not identification.
BACKFILL_START = date(2016, 1, 1)

POLITE_DELAY_S = 1.0        # pause between API calls (politeness, all APIs)
EIA_PAGE_ROWS = 5000        # EIA v2 documented max rows per request (paged)

# Enumerated series allowlist (ledgered, exit-44 site macro_series_allowlist):
# ingestion refuses anything outside this set — no ad-hoc series creep.
FRED_SERIES = ("DCOILWTICO", "DCOILBRENTEU", "DEXCAUS",
               "DGS10", "DGS2", "DFF")
EIA_SERIES = ("PET.RWTC.D", "PET.RBRTE.D", "NG.RNGWHHD.D")
YF_SERIES = ("CL=F", "NG=F")
ALL_SERIES = tuple(("FRED", s) for s in FRED_SERIES) + \
             tuple(("EIA", s) for s in EIA_SERIES) + \
             tuple(("yfinance", s) for s in YF_SERIES)


def _env() -> dict:
    """Read ~/.yuclaw_env (chmod 600, same as Telegram); last wins."""
    out = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip()
    return out


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": "YUCLAW research (contact: vzhang2099@gmail.com)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


# ------------------------------------------------------------- fetchers
def fetch_fred(series_id: str, start: date, end: date,
               api_key: str) -> list[tuple[date, float]]:
    """FRED series/observations. Missing observations arrive as value '.'
    and are skipped (source-native absence — ledgered as
    macro_missing_value_skip together with EIA nulls)."""
    q = urllib.parse.urlencode({
        "series_id": series_id, "api_key": api_key, "file_type": "json",
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat()})
    body = _get_json(f"https://api.stlouisfed.org/fred/series/"
                     f"observations?{q}")
    out = []
    for o in body.get("observations", []):
        if o.get("value") in (".", "", None):
            continue
        out.append((date.fromisoformat(o["date"]), float(o["value"])))
    return out


def fetch_eia(series_id: str, start: date, end: date,
              api_key: str) -> list[tuple[date, float]]:
    """EIA v2 seriesid compatibility route, paged at EIA_PAGE_ROWS.
    Null values are skipped (source-native absence — ledgered)."""
    out: list[tuple[date, float]] = []
    offset = 0
    while True:
        q = urllib.parse.urlencode({
            "api_key": api_key, "start": start.isoformat(),
            "end": end.isoformat(), "length": EIA_PAGE_ROWS,
            "offset": offset})
        body = _get_json(f"https://api.eia.gov/v2/seriesid/"
                         f"{urllib.parse.quote(series_id)}?{q}")
        rows = (body.get("response") or {}).get("data") or []
        for r in rows:
            v = r.get("value")
            if v is None:
                continue
            p = str(r.get("period"))
            out.append((date.fromisoformat(p), float(v)))
        if len(rows) < EIA_PAGE_ROWS:
            return out
        offset += EIA_PAGE_ROWS
        time.sleep(POLITE_DELAY_S)


def fetch_yf(series_id: str, start: date, end: date) -> list[tuple[date, float]]:
    """Futures daily closes via yfinance (same dependency and posture as
    v3/track/price_history.py; raw values research-internal only).
    NaN closes are skipped (ledgered)."""
    import yfinance as yf
    df = yf.download(series_id, start=start.isoformat(),
                     end=(end + timedelta(days=1)).isoformat(),
                     progress=False, auto_adjust=False, threads=False)
    if df is None or df.empty:
        return []
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df = df.droplevel(axis=1, level=1)
    out = []
    for ts, row in df.iterrows():
        try:
            close = float(row["Close"])
        except (KeyError, TypeError, ValueError):
            continue
        if close != close:  # NaN
            continue
        out.append((ts.date(), close))
    return out


# --------------------------------------------------------------- storage
UPSERT = """
INSERT INTO macro_series
  (source, series_id, observation_date, value, grade)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (source, series_id, observation_date) DO UPDATE SET
  value = EXCLUDED.value,
  fetched_at = now(),
  available_as_of = CASE
      WHEN macro_series.value IS DISTINCT FROM EXCLUDED.value
      THEN now() ELSE macro_series.available_as_of END,
  revision_count = macro_series.revision_count + CASE
      WHEN macro_series.value IS DISTINCT FROM EXCLUDED.value
      THEN 1 ELSE 0 END
"""
# grade is deliberately NOT in the update list: the grade set at first
# ingestion (REFERENCE for backfill, POINT_IN_TIME for accrual) is
# permanent — backfill can never overwrite a point-in-time row's label,
# and re-fetching history never upgrades REFERENCE to POINT_IN_TIME.


def store(conn, source: str, series_id: str,
          rows: list[tuple[date, float]], grade: str) -> int:
    with conn.cursor() as cur:
        for d, v in rows:
            cur.execute(UPSERT, (source, series_id, d, v, grade))
    conn.commit()
    return len(rows)


def _resume_start(conn, source: str, series_id: str) -> date | None:
    with conn.cursor() as cur:
        cur.execute("SELECT max(observation_date) FROM macro_series "
                    "WHERE source=%s AND series_id=%s", (source, series_id))
        m = cur.fetchone()[0]
    return (m - timedelta(days=7)) if m else None


# ------------------------------------------------------------------ runs
def run(sources: list[tuple[str, str]], start: date, end: date,
        grade: str, resume: bool = False) -> dict:
    env = _env()
    fred_key = env.get("FRED_API_KEY", "")
    eia_key = env.get("EIA_KEY", "")
    conn = psycopg2.connect(DB_DSN)
    stats = {"series_ok": 0, "rows_upserted": 0, "skipped_no_key": [],
             "errors": []}
    try:
        for source, sid in sources:
            if (source, sid) not in ALL_SERIES:
                raise ValueError(f"{source}:{sid} outside the enumerated "
                                 f"№5 allowlist — refused")
            s = start
            if resume:
                r = _resume_start(conn, source, sid)
                if r and r > s:
                    s = r
            try:
                if source == "FRED":
                    if not fred_key:
                        stats["skipped_no_key"].append(f"FRED:{sid}")
                        continue
                    rows = fetch_fred(sid, s, end, fred_key)
                elif source == "EIA":
                    if not eia_key:
                        stats["skipped_no_key"].append(f"EIA:{sid}")
                        continue
                    rows = fetch_eia(sid, s, end, eia_key)
                else:
                    rows = fetch_yf(sid, s, end)
            except Exception as e:
                stats["errors"].append(f"{source}:{sid} "
                                       f"{type(e).__name__}: {str(e)[:100]}")
                print(f"[macro_series] {source}:{sid} ERROR "
                      f"{type(e).__name__}: {str(e)[:140]}",
                      file=sys.stderr, flush=True)
                continue
            # Window filter (ledgered with macro_backfill_window): the EIA
            # v2 seriesid compatibility route ignores start/end and returns
            # full history, so the requested window is enforced here for
            # every source — nothing outside [s, end] is ever stored.
            rows = [(d, v) for d, v in rows if s <= d <= end]
            n = store(conn, source, sid, rows, grade)
            stats["series_ok"] += 1
            stats["rows_upserted"] += n
            print(f"[macro_series] {source}:{sid} {n} rows "
                  f"({s}..{end}, {grade})", flush=True)
            time.sleep(POLITE_DELAY_S)
    finally:
        conn.close()
    return stats


def status() -> None:
    conn = psycopg2.connect(DB_DSN)
    with conn.cursor() as cur:
        cur.execute("""SELECT source, series_id, grade, count(*),
                              min(observation_date), max(observation_date),
                              sum(revision_count)
                       FROM macro_series
                       GROUP BY source, series_id, grade
                       ORDER BY source, series_id, grade""")
        for r in cur.fetchall():
            print(f"  {r[0]:9s} {r[1]:14s} {r[2]:14s} rows={r[3]:6d} "
                  f"{r[4]}..{r[5]} revisions={r[6]}")
    conn.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="№5 macro series ingestion "
                                            "(research-internal substrate)")
    m = p.add_mutually_exclusive_group(required=True)
    m.add_argument("--backfill", action="store_true",
                   help=f"REFERENCE-grade history from {BACKFILL_START}")
    m.add_argument("--accrue", action="store_true",
                   help="POINT_IN_TIME forward accrual, rolling 7 days")
    m.add_argument("--smoke", action="store_true",
                   help="one real EIA series end-to-end (May-19 rule)")
    m.add_argument("--status", action="store_true")
    p.add_argument("--resume", action="store_true",
                   help="per-series restart from max(observation_date)-7d")
    p.add_argument("--source", choices=["FRED", "EIA", "yfinance"],
                   help="restrict to one source")
    args = p.parse_args(argv)

    if args.status:
        status()
        return 0

    today = date.today()
    if args.smoke:
        sel = [("EIA", "PET.RWTC.D")]
        st = run(sel, today - timedelta(days=30), today,
                 grade="REFERENCE", resume=False)
    elif args.backfill:
        sel = [x for x in ALL_SERIES
               if not args.source or x[0] == args.source]
        st = run(sel, BACKFILL_START, today, grade="REFERENCE",
                 resume=args.resume)
    else:  # --accrue
        sel = [x for x in ALL_SERIES
               if not args.source or x[0] == args.source]
        st = run(sel, today - timedelta(days=7), today,
                 grade="POINT_IN_TIME", resume=False)
    print(f"[macro_series] DONE: {st}", flush=True)
    return 1 if st["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
