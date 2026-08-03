#!/usr/bin/env python3
"""
Identity spine (U350 Part 2) — permanent internal IDs for every covered
security. Ticker is display; issuer_id/security_id are identity. New
tables only (public schema gains tables; no existing U79 table is touched).

  issuer_identity(issuer_id, cik, legal_name, country, filer_class,
                  sic_code, sic_desc, source, recorded_at)
  security_identity(security_id, issuer_id, ticker, exchange,
                    security_type, tier, recorded_at)
  corporate_action_lineage(lineage_id, security_id, action_type,
                           effective_date, detail, note_path, recorded_at)
    — every membership add/remove/ticker-change/merger/delisting appends a
      lineage row AND requires a policy-invocation note (chain-enforced by
      check_universe_integrity U3).

issuer_id = "ISS-" + sha256(cik)[:12] when a CIK exists, else
"ISS-" + sha256("noncik:"+ticker)[:12] (indexes / non-filers, reason
recorded). security_id = "SEC-" + sha256(ticker+"|"+exchange)[:12].
IDs are deterministic and permanent; display fields may change, IDs never.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import psycopg2

DSN = "dbname=yuclaw_events"
UA = "research vzhang2099@gmail.com"

DDL = """
CREATE TABLE IF NOT EXISTS issuer_identity (
    issuer_id text PRIMARY KEY, cik text, legal_name text,
    country text, filer_class text, sic_code text, sic_desc text,
    source text, recorded_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS security_identity (
    security_id text PRIMARY KEY, issuer_id text REFERENCES issuer_identity,
    ticker text NOT NULL, exchange text, security_type text, tier text,
    recorded_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS corporate_action_lineage (
    lineage_id bigserial PRIMARY KEY,
    security_id text REFERENCES security_identity,
    action_type text NOT NULL, effective_date date, detail text,
    note_path text, recorded_at timestamptz NOT NULL DEFAULT now());
"""


def _iid(cik, ticker):
    if cik:
        return "ISS-" + hashlib.sha256(cik.encode()).hexdigest()[:12]
    return "ISS-" + hashlib.sha256(f"noncik:{ticker}".encode()).hexdigest()[:12]


def _sid(ticker, exchange):
    return "SEC-" + hashlib.sha256(f"{ticker}|{exchange or ''}".encode()).hexdigest()[:12]


def sec_tickers() -> dict:
    req = urllib.request.Request(
        "https://www.sec.gov/files/company_tickers_exchange.json",
        headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    out = {}
    for row in d["data"]:
        cik, name, ticker, exch = row
        out[ticker] = {"cik": f"{cik:010d}", "name": name, "exchange": exch}
    return out


def sic_for(cik: str):
    try:
        req = urllib.request.Request(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        time.sleep(0.15)
        return (d.get("sic") or None, d.get("sicDescription") or None,
                (d.get("addresses", {}).get("business", {}) or {}).get(
                    "stateOrCountryDescription"))
    except Exception:                             # noqa: BLE001
        return None, None, None


def main() -> int:
    u = json.loads((_REPO / "v3" / "universe.json").read_text())
    sec = sec_tickers()
    rows = []
    for key, sec_type in (("equities", "common_stock"),
                          ("sector_etfs", "etf"), ("broad_etfs", "etf"),
                          ("macro", "macro_instrument")):
        for tk in u.get(key, []):
            meta = sec.get(tk, {})
            rows.append({"ticker": tk, "tier": "scoring",
                         "security_type": sec_type,
                         "cik": meta.get("cik"),
                         "name": meta.get("name"),
                         "exchange": meta.get("exchange"),
                         "filer_class": ("domestic" if meta.get("cik")
                                         else "non_filer")})
    for r in u.get("evidence_tier", []):
        rows.append({"ticker": r["ticker"], "tier": "evidence",
                     "security_type": "common_stock", "cik": r["cik"],
                     "name": r.get("sec_name"),
                     "exchange": (r.get("exchanges") or [None])[0],
                     "filer_class": r.get("filer_class", "unknown")})

    with psycopg2.connect(DSN) as cn:
        with cn.cursor() as cur:
            cur.execute(DDL)
            n_new_i = n_new_s = 0
            for r in rows:
                iid = _iid(r["cik"], r["ticker"])
                cur.execute("SELECT 1 FROM issuer_identity WHERE issuer_id=%s",
                            (iid,))
                if cur.fetchone() is None:
                    sic, sicd, country = (sic_for(r["cik"])
                                          if r["cik"] else (None, None, None))
                    cur.execute(
                        """INSERT INTO issuer_identity (issuer_id, cik,
                           legal_name, country, filer_class, sic_code,
                           sic_desc, source) VALUES
                           (%s,%s,%s,%s,%s,%s,%s,'sec_submissions+universe')""",
                        (iid, r["cik"], r["name"], country,
                         r["filer_class"], sic, sicd))
                    n_new_i += 1
                sid = _sid(r["ticker"], r["exchange"])
                cur.execute("SELECT 1 FROM security_identity "
                            "WHERE security_id=%s", (sid,))
                if cur.fetchone() is None:
                    cur.execute(
                        """INSERT INTO security_identity (security_id,
                           issuer_id, ticker, exchange, security_type, tier)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (sid, iid, r["ticker"], r["exchange"],
                         r["security_type"], r["tier"]))
                    cur.execute(
                        """INSERT INTO corporate_action_lineage
                           (security_id, action_type, effective_date, detail)
                           VALUES (%s,'initial_backfill',%s,
                                   'identity spine backfill 2026-08-02')""",
                        (sid, datetime.now(timezone.utc).date()))
                    n_new_s += 1
        cn.commit()
    with psycopg2.connect(DSN) as cn:
        with cn.cursor() as cur:
            cur.execute("SELECT count(*), count(cik), count(sic_code) "
                        "FROM issuer_identity")
            ni, ncik, nsic = cur.fetchone()
            cur.execute("SELECT tier, count(*) FROM security_identity GROUP BY 1")
            tiers = dict(cur.fetchall())
    print(f"[identity] issuers={ni} (cik {ncik}, sic {nsic}) · "
          f"securities={tiers} · new this run: {n_new_i}i/{n_new_s}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
