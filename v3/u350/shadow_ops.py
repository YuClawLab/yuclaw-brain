#!/usr/bin/env python3
"""
U350 Phase-A shadow operations (Part 4). Shadow data is NEVER a forward
record; no public claims during shadow. Every write goes to the u350
schema; the GPU drain yields to ALL U79 work.

Mechanism — schema twins, not code forks:
  The canonical extractor and the canonical composite scorer are reused
  BYTE-FOR-BYTE by running them in a subprocess as the LOGIN-enabled
  `u350_writer` role with `search_path=u350,public`. Unqualified table
  references then resolve to the u350 twin when one exists
  (price_history, events, events_raw, rejected_events) and fall back to
  the canonical table for reads that have no twin (signal_snapshots for
  C8, track_record for C9 — where a shadow ticker is simply absent and
  the component self-masks at zero confidence, exactly as designed).
  Because the role's INSERT/UPDATE/DELETE on every public table is
  REVOKED (P0), a stray unqualified write physically cannot reach the
  canonical record — the refusal is PostgreSQL's, not a convention.

Subcommands:
  ensure    create u350 twins + LOGIN for the role (idempotent)
  prices    rolling 7-day close/volume refresh for Phase-A members
  ingest    EDGAR submissions sweep for shadow CIKs (2-day lookback);
            Form 4 recorded deterministically, prose forms queued into
            u350.events_raw
  drain     bounded LLM extraction of u350.events_raw — runs ONLY when
            the gpu-lock is free AND the canonical events_raw backlog is
            empty (U79 starves shadow, never the reverse); hard cap per
            run
  score     point-in-time shadow snapshot per member via the canonical
            composite (subprocess, twins); writes u350.shadow_snapshots
  guards    scoring-completeness (>=95% component-day floor) +
            label-anomaly (extreme-label share vs U79 same day)
  calendar  Phase-A clock (15-20 trading days from first snapshot)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import psycopg2

from v3.u350 import DSN, ROLE, SCHEMA, u350_connection
from v3.u350.market_calendar import (is_session, latest_completed_session,
                                     session_of, session_window_utc)

UA = "YuClawLab vzhang2199@gmail.com"
PGPASS = Path.home() / ".pgpass"
DRAIN_CAP = 12                # filings per drain run — bounded GPU budget
PROSE_FORMS = {"8-K", "10-Q", "10-K", "6-K", "20-F", "40-F"}

TWIN_DDL = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.events_raw
    (LIKE public.events_raw INCLUDING ALL);
CREATE TABLE IF NOT EXISTS {SCHEMA}.events
    (LIKE public.events INCLUDING ALL);
CREATE TABLE IF NOT EXISTS {SCHEMA}.rejected_events
    (LIKE public.rejected_events INCLUDING ALL);
-- LIKE INCLUDING ALL copies serial DEFAULTs that point at the PUBLIC
-- sequences, which the role is (correctly) refused. Twins get their own.
CREATE SEQUENCE IF NOT EXISTS {SCHEMA}.events_raw_raw_id_seq;
ALTER TABLE {SCHEMA}.events_raw ALTER COLUMN raw_id
    SET DEFAULT nextval('{SCHEMA}.events_raw_raw_id_seq');
-- Order 2026-08-28C FIX 1: rejected_events inherited the PUBLIC sequence
-- default too (root cause of 19 rc=1 drains). Twin sequence, owned by
-- the twin column; setval handled by the FIX-1 DDL, not here.
CREATE SEQUENCE IF NOT EXISTS {SCHEMA}.rejected_events_reject_id_seq;
ALTER SEQUENCE {SCHEMA}.rejected_events_reject_id_seq
    OWNED BY {SCHEMA}.rejected_events.reject_id;
ALTER TABLE {SCHEMA}.rejected_events ALTER COLUMN reject_id
    SET DEFAULT nextval('{SCHEMA}.rejected_events_reject_id_seq');
"""


def _members(cur):
    cur.execute(f"SELECT members FROM {SCHEMA}.manifest WHERE phase='A' "
                f"ORDER BY locked_at DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise SystemExit("no Phase-A manifest locked — run admission first")
    return row[0]


def shadow_members():
    with u350_connection() as cn:
        with cn.cursor() as cur:
            return [m for m in _members(cur) if m["origin"] == "shadow"]


def cmd_ensure() -> int:
    import secrets
    with psycopg2.connect(DSN) as cn:
        with cn.cursor() as cur:
            cur.execute(TWIN_DDL)
            cur.execute(f"GRANT ALL ON ALL TABLES IN SCHEMA {SCHEMA} "
                        f"TO {ROLE}")
            cur.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA "
                        f"{SCHEMA} TO {ROLE}")
            cur.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname=%s",
                        (ROLE,))
            if not cur.fetchone()[0]:
                pw = secrets.token_urlsafe(24)
                cur.execute(f"ALTER ROLE {ROLE} LOGIN PASSWORD %s", (pw,))
                line = f"localhost:5432:yuclaw_events:{ROLE}:{pw}\n"
                existing = PGPASS.read_text() if PGPASS.exists() else ""
                kept = [l for l in existing.splitlines(keepends=True)
                        if f":{ROLE}:" not in l]
                PGPASS.write_text("".join(kept) + line)
                PGPASS.chmod(0o600)
                print("[ensure] LOGIN enabled for role; ~/.pgpass updated "
                      "(box-local, never in git)")
        cn.commit()
    print("[ensure] u350 twins ready (events_raw, events, rejected_events)")
    return 0


def _twin_env() -> dict:
    env = os.environ.copy()
    env["PGHOST"] = "localhost"
    env["PGUSER"] = ROLE
    env["PGOPTIONS"] = f"-c search_path={SCHEMA},public"
    return env


def cmd_prices() -> int:
    import pandas as pd
    import yfinance as yf
    tickers = sorted({m["ticker"] for m in shadow_members()})
    start = (date.today().toordinal() - 10)
    start = date.fromordinal(start).isoformat()
    df = yf.download([t.replace(".", "-") for t in tickers], start=start,
                     progress=False, auto_adjust=False, group_by="ticker",
                     threads=True)
    rows = []
    for t in tickers:
        yt = t.replace(".", "-")
        try:
            sub = df[yt][["Close", "Volume"]].dropna(subset=["Close"])
        except KeyError:
            continue
        for dt, r in sub.iterrows():
            rows.append((t, dt.date(), float(r["Close"]),
                         int(r["Volume"]) if pd.notna(r["Volume"]) else None))
    with u350_connection() as cn:
        with cn.cursor() as cur:
            cur.executemany(
                f"""INSERT INTO {SCHEMA}.price_history
                    (ticker, trade_date, close, volume) VALUES (%s,%s,%s,%s)
                    ON CONFLICT (ticker, trade_date) DO UPDATE
                    SET close=EXCLUDED.close, volume=EXCLUDED.volume""", rows)
        cn.commit()
    print(f"[prices] {len(rows)} rows refreshed for {len(tickers)} "
          f"shadow names")
    return 0


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def cmd_ingest() -> int:
    members = shadow_members()
    cutoff = date.fromordinal(date.today().toordinal() - 2).isoformat()
    n_queued = n_f4 = 0
    with u350_connection() as cn:
        with cn.cursor() as cur:
            for m in members:
                cik = m.get("cik")
                if not cik:
                    continue
                try:
                    s = _fetch_json("https://data.sec.gov/submissions/"
                                    f"CIK{cik}.json")
                except Exception as exc:              # noqa: BLE001
                    print(f"  ! {m['ticker']}: {exc}")
                    continue
                r = s.get("filings", {}).get("recent", {})
                for form, acc, fdate, pdoc in zip(
                        r.get("form", []), r.get("accessionNumber", []),
                        r.get("filingDate", []),
                        r.get("primaryDocument", [])):
                    if fdate < cutoff:
                        break
                    if form == "4":
                        n_f4 += 1     # deterministic path; recorded, no GPU
                    if form not in PROSE_FORMS:
                        continue
                    url = ("https://www.sec.gov/Archives/edgar/data/"
                           f"{int(cik)}/{acc.replace('-', '')}/{pdoc}")
                    cur.execute(f"SELECT 1 FROM {SCHEMA}.events_raw "
                                f"WHERE accession_number=%s", (acc,))
                    if cur.fetchone():
                        continue
                    # fetch the primary document text (poller convention:
                    # tag-stripped, capped at 8000 chars)
                    try:
                        req = urllib.request.Request(
                            url, headers={"User-Agent": UA})
                        with urllib.request.urlopen(req, timeout=30) as rr:
                            html = rr.read().decode("utf-8", "replace")
                        import re as _re
                        text = _re.sub(r"<[^>]+>", " ", html)
                        text = _re.sub(r"\s+", " ", text).strip()[:8000]
                        time.sleep(0.15)
                    except Exception as exc:          # noqa: BLE001
                        print(f"  ! doc fetch {m['ticker']} {acc}: {exc}")
                        continue
                    cur.execute(
                        f"""INSERT INTO {SCHEMA}.events_raw (ticker,
                            source_type, source_url, raw_text,
                            source_publish_time, extraction_status,
                            accession_number)
                            VALUES (%s,%s,%s,%s,%s,'pending',%s)""",
                        (m["ticker"], form, url, text or "(empty)",
                         fdate, acc))
                    n_queued += 1
                time.sleep(0.15)
        cn.commit()
    print(f"[ingest] queued {n_queued} prose filings; saw {n_f4} Form 4s "
          f"(deterministic path) across {len(members)} shadow names")
    return 0


def cmd_drain() -> int:
    # yield to ALL U79 work: gpu-lock must be free AND canonical backlog
    # empty; otherwise exit 0 quietly (shadow starves first, by design)
    lock = subprocess.run(["/home/zhangd2/yuclaw/services/gpu-lock",
                           "status"], capture_output=True, text=True)
    if "free" not in (lock.stdout + lock.stderr).lower():
        print("[drain] gpu-lock busy — yielding to U79, no shadow drain")
        return 0
    with psycopg2.connect(DSN) as cn:
        with cn.cursor() as cur:
            cur.execute("SELECT count(*) FROM public.events_raw "
                        "WHERE extraction_status='pending'")
            if cur.fetchone()[0]:
                print("[drain] canonical events_raw backlog nonempty — "
                      "yielding to U79, no shadow drain")
                return 0
    r = subprocess.run(
        [sys.executable, "-m", "v3.extract.event_worker",
         "--batch", str(DRAIN_CAP), "--once"],
        env=_twin_env(), cwd=str(_REPO), capture_output=True, text=True,
        timeout=3600)
    # Order 2026-08-28C FIX 2a: the worker's rc IS the drain's rc, and both
    # stream tails go to the shadow log every run (19 silent rc=1 days).
    print(f"[drain] bounded shadow drain (cap {DRAIN_CAP}) rc={r.returncode}")
    for name, stream in (("stdout", r.stdout), ("stderr", r.stderr)):
        lines = (stream or "").strip().splitlines()[-20:]
        print(f"[drain] worker {name} tail ({len(lines)} lines):")
        for line in lines:
            print(f"   {line}")
    return r.returncode


def cmd_score() -> int:
    members = shadow_members()
    as_of = datetime.now(timezone.utc)
    # Order 2026-08-28C FIX 3a: the snapshot date is the latest COMPLETED
    # NYSE session (registered calendar), never as_of's UTC date — the
    # Sunday ignition pass minted TICKER_20260803 ids and the real Aug-3
    # pass was silently ON-CONFLICT-dropped (zero-row trading day).
    session = latest_completed_session(as_of)
    attempted = inserted = skipped = 0
    committed = False
    cn = u350_connection()
    try:
        with cn.cursor() as cur:
            for m in members:
                tk = m["ticker"]
                attempted += 1
                r = subprocess.run(
                    [sys.executable, "-m", "v3.signal.composite",
                     "--ticker", tk, "--json"],
                    env=_twin_env(), cwd=str(_REPO), capture_output=True,
                    text=True, timeout=180)
                if r.returncode != 0:
                    print(f"  ! {tk}: scorer rc={r.returncode} "
                          f"{(r.stderr or '').strip().splitlines()[-1:]}")
                    continue
                out = json.loads(r.stdout)
                comps = out["components"]
                ok = sum(1 for c in comps.values()
                         if not c.get("not_implemented")
                         and c.get("confidence", 0) > 0)
                sid = f"{tk}_{session.strftime('%Y%m%d')}"
                cur.execute(
                    f"""INSERT INTO {SCHEMA}.shadow_snapshots
                        (snapshot_id, ticker, signal_time, available_as_of,
                         signal_label, total_score, components,
                         components_ok, components_total, manifest_hash)
                        SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,
                               (SELECT manifest_hash FROM {SCHEMA}.manifest
                                WHERE phase='A' ORDER BY locked_at DESC
                                LIMIT 1)
                        ON CONFLICT (snapshot_id) DO NOTHING""",
                    (sid, tk, as_of, as_of, out["label"],
                     out["total_score"], json.dumps(comps, default=str),
                     ok, 9))
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    skipped += 1
        cn.commit()
        committed = True
    except Exception as exc:                          # noqa: BLE001
        cn.rollback()
        print(f"[score] session {session} committed_inserted=0 "
              f"transaction_rolled_back=true error={str(exc)[:200]}")
        return 1
    finally:
        cn.close()
    # FIX 3b: counts printed only after commit; N is the run's eligible set.
    print(f"[score] session {session}: committed_inserted {inserted} / "
          f"skipped {skipped} / attempted {attempted} "
          f"(skipped = already committed for this session; "
          f"u350.shadow_snapshots)")
    scored = inserted + skipped
    return 0 if (committed and scored == attempted and attempted) else 1


# price-derived components that must compute every shadow day; evidence
# components (c2, c6, c8, c9) self-mask on absence and are exempt.
# A component-day whose rationale carries a STRUCTURAL marker is out of
# the component's coverage by construction (e.g. C7's peer-cohort map is
# a U79-only table — extending it would change U79 names' own C7 via the
# cohort majorities, which is forbidden). Structural inactivity is
# DISCLOSED, never counted as a completeness failure; a component that
# computed on some days and missed others is a real failure.
ALWAYS_ON = ("c1", "c3", "c4", "c5", "c7")
STRUCTURAL_MARKERS = ("no sector cohort", "not yet implemented")


def cmd_guards() -> int:
    problems = []
    with u350_connection() as cn:
        with cn.cursor() as cur:
            cur.execute(f"""SELECT ticker, components
                            FROM {SCHEMA}.shadow_snapshots""")
            per: dict[str, list] = {}
            for tk, comps in cur.fetchall():
                per.setdefault(tk, []).append(comps)
            structural: dict[str, int] = {}
            for tk, days in per.items():
                for cid in ALWAYS_ON:
                    ok = miss = struct = 0
                    for d in days:
                        c = d.get(cid) or {}
                        if c.get("confidence", 0) > 0:
                            ok += 1
                        elif any(mk in (c.get("rationale") or "")
                                 for mk in STRUCTURAL_MARKERS):
                            struct += 1
                        else:
                            miss += 1
                    if struct == len(days):
                        structural[cid] = structural.get(cid, 0) + 1
                        continue        # disclosed below, not a failure
                    if ok / max(ok + miss, 1) < 0.95:
                        problems.append(
                            f"COMPONENT_INCOMPLETE {tk}.{cid}: computed "
                            f"{ok}/{ok + miss} active shadow days (<95%)")
            # label anomaly: extreme-label share today vs U79 same day
            lo, hi = session_window_utc(latest_completed_session())
            cur.execute(f"""SELECT signal_label FROM
                {SCHEMA}.shadow_snapshots
                WHERE signal_time >= %s AND signal_time < %s""", (lo, hi))
            sh = [r[0] for r in cur.fetchall()]
            cur.execute("""SELECT signal_label FROM public.signal_snapshots
                WHERE signal_time::date = (SELECT max(signal_time::date)
                                           FROM public.signal_snapshots)""")
            u79 = [r[0] for r in cur.fetchall()]
    if sh and u79:
        ext = {"STRONG_BULLISH", "BEARISH_WATCH"}
        s_sh = sum(1 for x in sh if x in ext) / len(sh)
        s_79 = sum(1 for x in u79 if x in ext) / len(u79)
        if s_sh > max(3 * s_79, 0.10) and len(sh) >= 10:
            problems.append(
                f"LABEL_ANOMALY: shadow extreme-label share {s_sh:.2f} vs "
                f"U79 {s_79:.2f} (>3x and >10%) — investigate before any "
                f"Phase-B consideration")
    if problems:
        print("SHADOW GUARDS FLAGGED:")
        for p in problems:
            print(f"  · {p}")
        return 1
    for cid, n in sorted(structural.items()):
        print(f"[guards] disclosure — {cid} STRUCTURALLY_INACTIVE for {n} "
              f"shadow names (out of the component's coverage map by "
              f"construction; extending the map would alter U79 scores)")
    print(f"[guards] OK — completeness floor met on {len(per) if per else 0}"
          f" names; no label anomaly (shadow n={len(sh)}, U79 n={len(u79)})")
    return 0


def sessions_with_rows() -> list[date]:
    """Distinct NYSE sessions that have committed shadow rows: each row is
    attributed to the latest completed session at its signal_time (so the
    Sunday-evening ignition rows belong to Fri 2026-07-31, not to Aug 3).
    Order 2026-08-28C FIX 3c: the day clock counts these and nothing else."""
    with u350_connection() as cn:
        with cn.cursor() as cur:
            cur.execute(f"SELECT DISTINCT signal_time FROM "
                        f"{SCHEMA}.shadow_snapshots")
            times = [r[0] for r in cur.fetchall()]
    return sorted({session_of(t) for t in times})


def cmd_calendar() -> int:
    sessions = sessions_with_rows()
    if not sessions:
        print("[calendar] Phase-A clock not started (no snapshots yet)")
        return 0
    first, n = sessions[0], len(sessions)
    # disclosed missing sessions: sessions inside the span with zero rows
    missing, d = [], first
    while d <= sessions[-1]:
        if is_session(d) and d not in sessions:
            missing.append(d.isoformat())
        d = date.fromordinal(d.toordinal() + 1)
    print(f"[calendar] Phase-A clock: day {n} of 15-20 trading days "
          f"(first session with rows {first}; sessions with committed "
          f"rows counted, zero-row sessions disclosed not counted: "
          f"{missing or 'none'}); success = system verification "
          f"(completeness, isolation, guards), not performance")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"ensure": cmd_ensure, "prices": cmd_prices, "ingest": cmd_ingest,
          "drain": cmd_drain, "score": cmd_score, "guards": cmd_guards,
          "calendar": cmd_calendar}.get(cmd)
    if fn is None:
        print("usage: ensure|prices|ingest|drain|score|guards|calendar")
        sys.exit(2)
    sys.exit(fn())
