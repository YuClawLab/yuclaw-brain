#!/usr/bin/env python3
"""
C6 specialized live runner (restoration order, 2026-07-31) — closes the
never-wired gap found by the Jul-30 first read: risk-channel artifacts were
only ever produced by hand-run batches (all 34 in one window on 2026-07-14);
no live path existed.

Behavior:
  - Selects qualifying filings: evidence-tier tickers (v3.universe_tiers),
    filing date >= FORWARD_ONLY_FROM (2026-07-31 — the Jul-16..30 backlog is
    a Part-C owner decision and is NEVER touched by this runner),
    extraction complete, narrative present in yuclaw_v5.swarm_inputs.
  - Runs yuclaw-v5 run_specialized (base swarm + specialists + risk channel
    + synthesis) and persists the artifact to output/swarm/canada/
    <accession>.json in the standing schema, plus computed_at.
  - IDEMPOTENT: an existing artifact file is never overwritten or recomputed.
  - Invoked from event_worker_guarded.sh AFTER a successful worker batch —
    inside the same GPU coordination slot (standing gpu-lock contract);
    bounded per invocation (--max, default 2) so the 15-min timer cadence
    holds; the queue drains across ticks.
  - --out-dir and --accession exist for the scratch negative test ONLY;
    production artifacts always land in output/swarm/canada/.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_V5 = Path.home() / "yuclaw-v5"
# Parent process imports ONLY from the main repo; _V5 is used exclusively as
# the subprocess cwd/PYTHONPATH (both projects ship `yuclaw` and `v3`
# packages that shadow each other — in-process mixing cannot work).
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import psycopg2

FORWARD_ONLY_FROM = date(2026, 7, 31)
OUT_DIR = _REPO / "output" / "swarm" / "canada"
DSN = "dbname=yuclaw_events"


def qualifying(limit: int):
    from v3.universe_tiers import evidence_cik_map
    tickers = sorted(evidence_cik_map())
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT r.accession_number, r.ticker, r.source_type,
                          r.source_publish_time::date
                   FROM events_raw r
                   JOIN yuclaw_v5.swarm_inputs s
                     ON s.accession_number = r.accession_number
                   WHERE r.ticker = ANY(%s)
                     AND r.source_publish_time::date >= %s
                     AND r.extraction_status <> 'pending'
                   GROUP BY 1, 2, 3, 4
                   ORDER BY 4""", (tickers, FORWARD_ONLY_FROM))
            rows = cur.fetchall()
    return [r for r in rows if not (OUT_DIR / f"{r[0]}.json").exists()][:limit]


def narrative(accession: str) -> str | None:
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT narrative_text FROM yuclaw_v5.swarm_inputs
                   WHERE accession_number = %s
                   ORDER BY char_len DESC NULLS LAST LIMIT 1""", (accession,))
            row = cur.fetchone()
    return row[0] if row else None


def run_one(accession: str, ticker: str, form: str, out_dir: Path) -> Path | None:
    out = out_dir / f"{accession}.json"
    if out.exists():
        print(f"[c6-live] {accession} artifact exists — idempotent skip")
        return None
    text = narrative(accession)
    if not text:
        print(f"[c6-live] {accession} no narrative in swarm_inputs — skip")
        return None
    # run_specialized executes in an ISOLATED subprocess with v5-only
    # PYTHONPATH: the main repo's regular `yuclaw` package shadows the v5
    # namespace package, so in-process import cannot work (root cause of the
    # first negative-test failure — kept isolated by design, matching how
    # the Jul-14 batch invocations ran).
    import os
    import subprocess
    import tempfile
    t0 = time.perf_counter()
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
        tf.write(text)
        tpath = tf.name
    bridge = (
        "import json, sys\n"
        "from yuclaw.v5.swarm.specialized import run_specialized\n"
        "acc, tpath = sys.argv[1], sys.argv[2]\n"
        "text = open(tpath).read()\n"
        "print(json.dumps(run_specialized(acc, text)))\n")
    env = dict(os.environ, PYTHONPATH=str(_V5))
    try:
        r = subprocess.run([sys.executable, "-c", bridge, accession, tpath],
                           cwd=str(_V5), env=env, capture_output=True,
                           text=True, timeout=1800)
    finally:
        os.unlink(tpath)
    if r.returncode != 0:
        print(f"[c6-live] {accession} specialized subprocess FAILED: "
              f"{r.stderr.strip()[-300:]}")
        return None
    full = json.loads(r.stdout.strip().splitlines()[-1])
    artifact = {
        "ticker": ticker, "form": form, "accession_number": accession,
        "grounding_by_agent": {name: r.get("grounding")
                               for name, r in {**full["base"],
                                               **{f"spec:{k}": v for k, v
                                                  in full["specialists"].items()}}.items()},
        "spawn_keys": full["spawn_keys"],
        "risk_channel": full["risk_channel"],
        "filing_len": full["filing_len"],
        "secs": round(time.perf_counter() - t0, 1),
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "live_path": "c6_specialized_live",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=1))
    rc = full["risk_channel"]
    print(f"[c6-live] {accession} ({ticker} {form}) -> {out.name} "
          f"flag={rc.get('flag')} level={rc.get('level')} "
          f"({artifact['secs']}s)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=2)
    ap.add_argument("--out-dir", default=str(OUT_DIR),
                    help="TEST ONLY — production always uses output/swarm/canada")
    ap.add_argument("--accession", default=None,
                    help="TEST ONLY — run one specific accession")
    a = ap.parse_args()
    out_dir = Path(a.out_dir)

    if a.accession:
        with psycopg2.connect(DSN) as cn:
            cn.set_session(readonly=True)
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT ticker, source_type FROM events_raw
                       WHERE accession_number = %s LIMIT 1""", (a.accession,))
                row = cur.fetchone()
        if not row:
            print(f"[c6-live] unknown accession {a.accession}")
            return 1
        run_one(a.accession, row[0], row[1], out_dir)
        return 0

    todo = qualifying(a.max)
    if not todo:
        print("[c6-live] no qualifying filings without artifacts "
              f"(forward-only from {FORWARD_ONLY_FROM})")
        return 0
    for acc, tk, form, _d in todo:
        run_one(acc, tk, form, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
