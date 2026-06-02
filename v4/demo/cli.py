"""
`yuclaw demo` — the 3-minute guided journey.

A real signal, traced to its SEC filings, point-in-time replayed, and verified
against the public git-anchored ledger. Uses the live backend when present; with
no backend it replays a bundled frozen capture of the SAME signal — the verify
step recomputes the identical content_hash committed to the public ledger.

    python3 -m v3.cli demo                 # full paced journey
    python3 -m v3.cli demo --no-pause      # no sleeps (CI / piping)
    python3 -m v3.cli demo --ticker AMD --target-date 2026-05-15

Pre-flight resolves the curated date to the nearest committed ledger date so the
final verify step always succeeds.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from typing import Optional

import click
import psycopg2

from v3.proof.verify import verify as proof_verify
from v4.api.builder import DSN, build_response
from v4.api.why_cli import render as render_why
from v4.memo.generator import generate_memo

TICKER = "AMD"
TARGET_DATE = "2026-05-15"   # curated; resolved to nearest ledger date in pre-flight
OLLAMA_URL = "http://localhost:11434/api/tags"


# --------------------------------------------------------------------------- #
# formatting / pacing
# --------------------------------------------------------------------------- #
def _hr() -> None:
    click.secho("─" * 72, dim=True)


def _header(n: int, title: str, budget: str) -> None:
    click.echo()
    click.secho(f"  STEP {n} ", fg="black", bg="cyan", bold=True, nl=False)
    click.secho(f"  {title}", fg="cyan", bold=True, nl=False)
    click.secho(f"   ({budget})", dim=True)
    _hr()


def _cmd(cmd: str) -> None:
    click.secho(f"  $ {cmd}", fg="green", bold=True)
    click.echo()


def _pause(seconds: float, no_pause: bool) -> None:
    if not no_pause:
        time.sleep(seconds)


# --------------------------------------------------------------------------- #
# pre-flight
# --------------------------------------------------------------------------- #
def _ledger_dates(ticker: str) -> list[str]:
    try:
        from v3.proof.ledger import LEDGER_FILE
        if not os.path.exists(LEDGER_FILE):
            return []
        dates: list[str] = []
        for line in open(LEDGER_FILE):
            try:
                b = json.loads(line)
            except Exception:
                continue
            ents = b.get("entries") or b.get("signals") or {}
            keys = ents.keys() if isinstance(ents, dict) else [e.get("ticker") for e in ents]
            if ticker in keys:
                dates.append(b.get("date"))
        return sorted(d for d in dates if d)
    except Exception:
        return []


def _resolve_date(ticker: str, target: str) -> tuple[Optional[str], str]:
    """Return (date, note). Nearest committed+VERIFIED ledger date to `target`."""
    dates = _ledger_dates(ticker)
    if not dates:
        return None, "no ledger entries found for this ticker"
    if target in dates and proof_verify(ticker, target).get("status") == "VERIFIED":
        return target, "exact ledger entry"
    t = date.fromisoformat(target)
    for d in sorted(dates, key=lambda x: abs((date.fromisoformat(x) - t).days)):
        if proof_verify(ticker, d).get("status") == "VERIFIED":
            note = "exact ledger entry" if d == target else f"nearest committed ledger date to {target}"
            return d, note
    return None, "no verifiable ledger entry found"


def _preflight(ticker: str, target: str) -> Optional[tuple[str, datetime]]:
    from v4.demo.fixture_loader import available as fx_available, FIXTURE_TICKER, FIXTURE_DATE
    click.secho("  Pre-flight checks", bold=True)
    offline = False
    # 1. DB — or fall back to the bundled fixture (zero-config first experience)
    try:
        with psycopg2.connect(DSN) as c, c.cursor() as cur:
            cur.execute("SELECT 1")
        click.secho("   ✓ database reachable", fg="green")
    except Exception:
        if fx_available() and ticker.upper() == FIXTURE_TICKER:
            offline = True
            click.secho("   ✓ no backend detected — replaying the bundled demo signal "
                        "offline (zero-config)", fg="green")
        else:
            click.secho(f"   ✗ no backend, and no bundled fixture for {ticker}.", fg="red")
            click.secho(f"     The offline demo covers {FIXTURE_TICKER} only — run plain "
                        f"`yuclaw demo`, or set up Postgres (docs/v4/backend_setup.md).",
                        fg="yellow")
            return None
    # 2. Ledger date (fixed for the bundled signal; resolved from the ledger when live)
    if offline:
        d, note = FIXTURE_DATE, "bundled offline fixture"
    else:
        d, note = _resolve_date(ticker, target)
        if not d:
            click.secho(f"   ✗ {note}", fg="red")
            return None
    click.secho(f"   ✓ ledger entry for {ticker} {d} ({note})", fg="green")
    # 3. Ollama (advisory — demo uses a cached snapshot, no live LLM call)
    try:
        import httpx
        httpx.get(OLLAMA_URL, timeout=3).raise_for_status()
        click.secho("   ✓ Ollama reachable (not needed — demo uses a cached snapshot)", fg="green")
    except Exception:
        click.secho("   ! Ollama not reachable — fine, the demo replays a cached snapshot", fg="yellow")
    as_of = datetime.fromisoformat(f"{d}T23:59:59-06:00")
    return d, as_of


# --------------------------------------------------------------------------- #
# journey
# --------------------------------------------------------------------------- #
def run(ticker: str, target: str, no_pause: bool, show_cascade: bool = False) -> int:
    click.echo()
    click.secho("  ╔" + "═" * 56 + "╗", fg="cyan")
    click.secho("  ║   YUCLAW — 3-Minute Guided Journey" + " " * 21 + "║", fg="cyan", bold=True)
    click.secho("  ╚" + "═" * 56 + "╝", fg="cyan")
    pf = _preflight(ticker, target)
    if not pf:
        return 1
    d, as_of = pf
    cmd_date = d

    # STEP 1 — intro
    _header(1, "What you're about to see", "~15s")
    click.echo("  YUCLAW is an evidence-first financial AI. In ~3 minutes you'll see a")
    click.echo("  real research signal traced to its SEC filings, point-in-time replayed,")
    click.echo("  and independently verified against a public, git-anchored ledger.")
    click.echo()
    click.secho(f"  Subject: {ticker}, frozen at {cmd_date} (a real, committed snapshot).", bold=True)
    _pause(3.0, no_pause)

    # STEP 2 — why (structured)
    _header(2, "The signal, and what drives it", "~30s")
    _cmd(f"yuclaw why {ticker} --as-of {cmd_date}")
    resp = build_response(ticker, as_of=as_of, include_score=False)
    click.echo(render_why(resp, include_score=False))
    click.echo()
    click.secho("  ↑ Every component is explainable; every claim links to a filing.", dim=True)
    _pause(3.5, no_pause)

    # STEP 3 — memo (full evidence trail)
    _header(3, "The full research memo", "~45s")
    _cmd(f"yuclaw memo {ticker} --as-of {cmd_date}")
    memo = generate_memo(ticker, as_of=as_of, include_score=False, n_evidence=20)
    click.echo(memo.markdown)
    _pause(4.0, no_pause)

    # STEP 3.5 — cascade (opt-in via --show-cascade; not part of the default 3-min journey)
    if show_cascade:
        from v4.api.cascade_builder import build_cascade
        from v4.api.cascade_cli import render as render_cascade
        _header("3.5", "How an upstream event cascaded in", "~30s")
        _cmd(f"yuclaw cascade {ticker} --as-of {cmd_date}")
        node = build_cascade(ticker, as_of=as_of, depth=3)
        if node:
            click.echo(render_cascade(node, ticker))
            click.echo()
            click.secho("  ↑ Edge weights are the public supply_chain.py graph — no hidden model.", dim=True)
        else:
            click.secho(f"  No supply-chain cascade reached {ticker} as of {cmd_date}.", fg="yellow")
        _pause(3.0, no_pause)

    # STEP 4 — replay determinism
    _header(4, "Point-in-time replay is deterministic", "~30s")
    _cmd(f"yuclaw verify {ticker} --date {cmd_date}    # recompute from source")
    v = proof_verify(ticker, cmd_date)
    rc = v.get("recomputed_hash", "")
    click.echo(f"  Recomputing the signal's content hash from the source data at {cmd_date}:")
    click.secho(f"    {rc}", fg="magenta", bold=True)
    click.echo("  Same date, same source data → the same hash, every time. That is what")
    click.echo("  makes a YUCLAW signal replayable rather than a black box.")
    _pause(3.0, no_pause)

    # STEP 5 — verify against the public ledger
    _header(5, "Independently verified against the public ledger", "~30s")
    ok = v.get("status") == "VERIFIED"
    commit = (v.get("commit") or {}).get("commit", "?")
    when = (v.get("commit") or {}).get("committed_at", "?")
    click.echo("  The hash committed to the public git-anchored Verified Research Ledger:")
    click.secho(f"    {v.get('ledger_hash','')}", fg="blue")
    click.echo("  matches the hash we just recomputed from the source data:")
    click.secho(f"    {rc}", fg="magenta")
    click.echo()
    if ok:
        click.secho(f"  ✓ VERIFIED — unaltered since it was published (commit {commit}, {when}).",
                    fg="green", bold=True)
    else:
        click.secho(f"  status: {v.get('status')}", fg="yellow", bold=True)
    if resp.ledger_anchor_url:
        click.echo("  Re-verify it yourself: " + click.style(resp.ledger_anchor_url, fg="blue"))
    click.secho("  Anyone can re-run this check — the ledger is public.", bold=True)
    _pause(3.0, no_pause)

    # STEP 6 — teach moments
    _header(6, "Three things that make YUCLAW different", "~30s")
    click.echo("  • " + click.style("Research, not recommendations.", bold=True)
               + " By default, raw scores are hidden —")
    click.echo("    YUCLAW outputs research, not numeric recommendations. Run")
    click.secho(f"    `yuclaw why {ticker} --include-score`", fg="green", nl=False)
    click.echo(" if you want the composite.")
    click.echo("  • " + click.style("Every claim is checkable.", bold=True)
               + " Each evidence item carries an SEC")
    click.echo("    accession_number and a ledger_hash — trace any point to its filing.")
    click.echo("  • " + click.style("Your data, public proof.", bold=True)
               + " Signals live in your local database;")
    click.echo("    their integrity hashes live in the public git-anchored ledger.")
    click.echo()

    # STEP 7 — share hint (optional close)
    _header(7, "Share it — and let anyone re-verify", "~10s")
    click.echo("  Turn this exact, point-in-time signal into a self-contained, verifiable HTML card:")
    click.secho(f"    yuclaw share {ticker} --as-of {cmd_date}", fg="green")
    click.echo("  The card embeds the ledger hash + accession numbers + verify link — host it anywhere,")
    click.echo("  and anyone can confirm it against the public ledger.")
    click.echo()
    _hr()
    click.secho("  That's the journey. Research only — not investment advice.", fg="cyan", bold=True)
    click.echo()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw demo", description="3-minute guided journey.")
    p.add_argument("--ticker", default=TICKER)
    p.add_argument("--target-date", default=TARGET_DATE)
    p.add_argument("--no-pause", action="store_true", help="no sleeps (CI / piping)")
    p.add_argument("--show-cascade", action="store_true",
                   help="add an opt-in Step 3.5 showing the supply-chain cascade tree")
    a = p.parse_args(argv)
    return run(a.ticker.upper(), a.target_date, a.no_pause, show_cascade=a.show_cascade)


if __name__ == "__main__":
    sys.exit(main())
