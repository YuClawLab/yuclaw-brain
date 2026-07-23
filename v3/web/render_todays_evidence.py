"""
Render the daily "Today's evidence changes" page (docs/todays_evidence.html)
— Part D of the usefulness build (2026-07-16). Runs in the daily regen chain.

Counts and classifications ONLY — locked vocabulary, zero interpretation:
  new filings ingested · new accepted events · grade changes · C6 posture
  changes · newly matured CAR events · Form-4 arrivals (count + buy/sell
  split) · failed-ingestion notes · ledger root · replay status.

Rolling 30-day archive: docs/evidence_changes/YYYY-MM-DD.json holds each
day's state; diffs (grades, posture, maturity) compare today against the most
recent prior archive day. Archive days beyond 30 are pruned.

CLI: python3 -m v3.web.render_todays_evidence
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

import psycopg2

from v3.web.useful_blocks import VERSION, site_header_html

_REPO = Path(__file__).resolve().parents[2]
OUT = _REPO / "docs" / "todays_evidence.html"
ARCHIVE_DIR = _REPO / "docs" / "evidence_changes"
C6_DIR = _REPO / "output" / "swarm" / "canada"
DSN = "dbname=yuclaw_events"
ARCHIVE_DAYS = 30

DISCLAIMER_LINE = ("Research & education only. Not investment advice. Counts and research "
                   "classifications only — nothing on this page is a recommendation.")


# --------------------------------------------------------------------------- #
# state gathering
# --------------------------------------------------------------------------- #
def _db_counts(today: date) -> dict:
    out: dict = {}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT source_type, count(*) FROM events_raw
                   WHERE (fetched_at AT TIME ZONE 'UTC')::date = %s
                   GROUP BY 1 ORDER BY 1""", (today,))
            out["new_filings"] = {r[0]: int(r[1]) for r in cur.fetchall()}

            cur.execute(
                """SELECT event_type, count(*) FROM events
                   WHERE event_status='accepted'
                     AND (source_ingested_time AT TIME ZONE 'UTC')::date = %s
                   GROUP BY 1 ORDER BY 1""", (today,))
            out["new_events"] = {r[0]: int(r[1]) for r in cur.fetchall()}

            cur.execute(
                """SELECT count(*) FILTER (WHERE event_type='INSIDER_BUY'),
                          count(*) FILTER (WHERE event_type='INSIDER_SELL'),
                          count(DISTINCT split_part(event_id, '_', 1))
                   FROM events
                   WHERE source_type='4-parsed' AND event_status='accepted'
                     AND (source_ingested_time AT TIME ZONE 'UTC')::date = %s""", (today,))
            b, s, nt = cur.fetchone()
            cur.execute(
                """SELECT count(*) FROM events_raw
                   WHERE source_type='4'
                     AND (fetched_at AT TIME ZONE 'UTC')::date = %s""", (today,))
            f4 = cur.fetchone()[0]
            out["form4"] = {"filings": int(f4), "buys": int(b), "sells": int(s),
                            "tickers": int(nt)}

            # Failed-ingestion notes: rows that fell back to a metadata stub
            # (primary-document fetch failed; worker mostly returns no_event).
            cur.execute(
                """SELECT ticker, source_type FROM events_raw
                   WHERE (fetched_at AT TIME ZONE 'UTC')::date = %s
                     AND raw_text LIKE source_type || ' filing on %%'
                   ORDER BY 1""", (today,))
            out["failed_ingestion"] = [{"ticker": r[0], "form": r[1]} for r in cur.fetchall()]
    return out


def _grades_and_maturity() -> tuple[dict, dict, int]:
    """Current evidence-tier grades {ticker: grade}, per-lens maturity, posture count."""
    from v3.lab.etf_evidence import CANADA_LENS_KEYS, canada_event_maturity, canada_posture
    grades: dict[str, str] = {}
    maturity: dict[str, dict] = {}
    for lens in CANADA_LENS_KEYS:
        p = canada_posture(lens)
        for m in p["members"]:
            grades[m["ticker"]] = m["grade"].split(" ")[0]  # letter only
        mat = canada_event_maturity(lens)
        maturity[lens] = {"n_events": mat["n_events"], "n_matured": mat["n_matured"]}
    return grades, maturity, len(list(C6_DIR.glob("*.json"))) if C6_DIR.exists() else 0


def _ledger_tip() -> dict:
    from v3.web.render_validation_lab import _ledger_tip as tip
    return tip()


def _replay_status() -> dict:
    """Run the standalone stdlib verifier against the local published bundle."""
    bundle = _REPO / "docs" / "replay" / "lab_replay_bundle.json"
    if not bundle.exists():
        return {"status": "bundle missing", "exit": None}
    try:
        r = subprocess.run([sys.executable, str(_REPO / "tools" / "replay_lab.py"),
                            str(bundle)], capture_output=True, text=True, timeout=300)
        return {"status": "verified (exit 0)" if r.returncode == 0
                else f"MISMATCH (exit {r.returncode})", "exit": r.returncode}
    except Exception as e:
        return {"status": f"verifier error: {type(e).__name__}", "exit": None}


def gather(today: date) -> dict:
    grades, maturity, n_posture = _grades_and_maturity()
    state = {
        "date": today.isoformat(),
        "counts": _db_counts(today),
        "grades": grades,
        "maturity": maturity,
        "c6_posture_files": n_posture,
        "c6_posture_accessions": sorted(p.stem for p in C6_DIR.glob("*.json")) if C6_DIR.exists() else [],
        "ledger": _ledger_tip(),
        "replay": _replay_status(),
    }
    return state


def _previous_state(today: date) -> dict | None:
    if not ARCHIVE_DIR.exists():
        return None
    days = sorted(p.stem for p in ARCHIVE_DIR.glob("????-??-??.json")
                  if p.stem < today.isoformat())
    if not days:
        return None
    try:
        return json.loads((ARCHIVE_DIR / f"{days[-1]}.json").read_text())
    except Exception:
        return None


def _diffs(state: dict, prev: dict | None) -> dict:
    if not prev:
        return {"baseline": True, "grade_changes": [], "posture_new": [],
                "newly_matured": {}}
    grade_changes = []
    pg = prev.get("grades", {})
    for tk, g in sorted(state["grades"].items()):
        if tk in pg and pg[tk] != g:
            grade_changes.append({"ticker": tk, "from": pg[tk], "to": g})
    posture_new = sorted(set(state["c6_posture_accessions"])
                         - set(prev.get("c6_posture_accessions", [])))
    newly_matured = {}
    pm = prev.get("maturity", {})
    for lens, m in state["maturity"].items():
        delta = m["n_matured"] - pm.get(lens, {}).get("n_matured", m["n_matured"])
        if delta:
            newly_matured[lens] = delta
    return {"baseline": False, "grade_changes": grade_changes,
            "posture_new": posture_new, "newly_matured": newly_matured,
            "prev_date": prev.get("date")}


def _archive(state: dict) -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    (ARCHIVE_DIR / f"{state['date']}.json").write_text(
        json.dumps(state, indent=1, default=str, sort_keys=True))
    days = sorted(ARCHIVE_DIR.glob("????-??-??.json"))
    for p in days[:-ARCHIVE_DAYS]:
        p.unlink()


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def _kv_list(d: dict, empty: str) -> str:
    if not d:
        return f"<span style='color:#718096'>{escape(empty)}</span>"
    return " · ".join(f"{escape(str(k))}×{v}" for k, v in sorted(d.items()))


def _plural(n: int, noun: str, count: bool = True) -> str:
    word = noun + ("" if n == 1 else "s")
    return f"{n} {word}" if count else word


def _form_label(form: str) -> str:
    """Bare numeric SEC form names ("4", "3", "144", "4/A") read ambiguously in
    the "<form>×<count>" list — prefix them with "Form". Display-only; the
    archive JSON keeps the raw form keys."""
    core = form.split("/")[0]
    return f"Form {form}" if core.isdigit() else form


def _panel_rows(state: dict, diffs: dict) -> str:
    """The digest table body for one UTC day — shared by the in-progress
    panel and the last-completed-day panel (rendered from the archive)."""
    c = state["counts"]

    if diffs["baseline"]:
        diff_note = ("<span style='color:#718096'>First archive day — change tracking begins "
                     "tomorrow (no prior day to compare against).</span>")
        grade_html = posture_html = matured_html = diff_note
    else:
        gc = diffs["grade_changes"]
        grade_html = (" · ".join(f"{escape(g['ticker'])}: {escape(g['from'])} → {escape(g['to'])}"
                                 for g in gc)
                      if gc else "<span style='color:#718096'>none</span>")
        pn = diffs["posture_new"]
        posture_html = (" · ".join(f"<code>{escape(a)}</code>" for a in pn)
                        if pn else "<span style='color:#718096'>none</span>")
        nm = diffs["newly_matured"]
        matured_html = (" · ".join(f"{escape(l)}: +{n}" for l, n in sorted(nm.items()))
                        if nm else "<span style='color:#718096'>none</span>")

    f4 = c["form4"]
    fails = c["failed_ingestion"]
    fail_html = (" · ".join(f"{escape(x['ticker'])} ({escape(x['form'])})" for x in fails)
                 if fails else "<span style='color:#718096'>none — all primary documents fetched</span>")

    ledger = state["ledger"]
    replay = state["replay"]
    replay_color = "#00E676" if replay.get("exit") == 0 else "#FBA94B"

    def row(label: str, body: str) -> str:
        return (f"<tr><td style='padding:9px 14px;color:#E2E8F0;font-size:12.5px;font-weight:600;"
                f"white-space:nowrap;vertical-align:top'>{escape(label)}</td>"
                f"<td style='padding:9px 14px;font-size:12.5px;color:#A0AEC0;line-height:1.6'>{body}</td></tr>")

    return "".join([
        row("New filings ingested", _kv_list({_form_label(k): v for k, v in c["new_filings"].items()}, "none")),
        row("New accepted events", _kv_list(c["new_events"], "none")),
        row("Grade changes", grade_html),
        row("C6 posture changes", posture_html),
        row("Newly matured CAR events", matured_html),
        row("Form-4 arrivals", f"{_plural(f4['filings'], 'filing')} → {f4['buys']} buy / {f4['sells']} sell "
                               f"{_plural(f4['buys'] + f4['sells'], 'event', count=False)} across "
                               f"{_plural(f4['tickers'], 'ticker')}"),
        row("Failed-ingestion notes", fail_html),
        row("Ledger root", f"block {escape(str(ledger.get('date')))} · "
                           f"<code>{escape(str(ledger.get('root') or '')[:16])}…</code> · "
                           f"{ledger.get('blocks', '—')} blocks total"),
        row("Replay status", f"<span style='color:{replay_color};font-weight:700'>"
                             f"{escape(replay['status'])}</span> — stdlib verifier vs the published bundle"),
    ])


def render(state: dict, diffs: dict,
           last_state: dict | None, last_diffs: dict | None) -> str:
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = _panel_rows(state, diffs)

    # Last completed UTC day — rendered from the archived daily JSON, so a
    # viewer ahead of UTC (for whom "today" is empty by construction early in
    # the UTC day) always sees one full day of final counts.
    if last_state:
        last_date = last_state["date"]
        last_panel = f"""
    <div class="panel">
      <div class="panel-title">Last completed UTC day ({escape(last_date)}) — final counts</div>
      <p style="font-size:11.5px;color:#718096;margin-bottom:8px">
        Rendered from the archived daily JSON:
        <a href="evidence_changes/{escape(last_date)}.json">evidence_changes/{escape(last_date)}.json</a>
      </p>
      <table><tbody>{_panel_rows(last_state, last_diffs)}</tbody></table>
    </div>"""
    else:
        last_panel = ""

    archive_days = sorted((p.stem for p in ARCHIVE_DIR.glob("????-??-??.json")), reverse=True)
    archive_links = " · ".join(f'<a href="evidence_changes/{d}.json">{d}</a>' for d in archive_days)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YUCLAW — Today's evidence changes ({escape(state['date'])})</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{background:#0B0E14;color:#E2E8F0;font-family:Inter,-apple-system,'Segoe UI',Roboto,sans-serif;font-size:14px}}
  .container{{max-width:900px;margin:0 auto;padding:28px 20px}}
  a{{color:#00E676;text-decoration:none}} a:hover{{text-decoration:underline}}
  code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:'JetBrains Mono',monospace;font-size:11.5px}}
  .header{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:18px}}
  .logo{{font-size:19px;font-weight:800;color:#FFF;letter-spacing:1px}}
  .navlinks a{{margin-left:14px;font-size:12px;color:#A0AEC0}}
  .panel{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px}}
  .panel-title{{font-size:13px;font-weight:700;color:#FFF;margin-bottom:8px}}
  .disclaimer-line{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;margin-bottom:20px;font-size:12px;line-height:1.55;color:#A0AEC0}}
  .footer{{text-align:center;padding:18px;color:#718096;font-size:11px;margin-top:8px}}
  table{{width:100%;border-collapse:collapse}}
  tr{{border-bottom:1px solid #1E232D}}
</style>
</head>
<body>
  <div class="container">
    {site_header_html(subtitle="Today's evidence changes", active="todays_evidence.html")}

    <h1 style="font-size:22px;font-weight:800;color:#FFF;margin-bottom:6px">Today's evidence changes — {escape(state['date'])}</h1>
    <p style="font-size:13px;color:#A0AEC0;margin-bottom:16px;line-height:1.6;max-width:760px">
      What changed in the evidence substrate today, as counts and research classifications —
      zero interpretation. Regenerated in the daily chain; each day archives to a JSON file
      (rolling {ARCHIVE_DAYS} days).
    </p>

    <div class="disclaimer-line"><strong>Disclaimer —</strong> {escape(DISCLAIMER_LINE)}</div>
{last_panel}
    <div class="panel">
      <div class="panel-title">Changes on {escape(state['date'])} (UTC day in progress)</div>
      <p style="font-size:11.5px;color:#718096;margin-bottom:8px">
        UTC day in progress — resets at 00:00 UTC; most filings arrive 13:30–22:00 UTC.
      </p>
      <table><tbody>{rows}</tbody></table>
    </div>

    <div class="panel">
      <div class="panel-title">Archive — rolling {ARCHIVE_DAYS} days (JSON, one file per day)</div>
      <p style="font-size:12px;color:#A0AEC0;line-height:1.8">{archive_links or '<span style="color:#718096">first day — archive begins today</span>'}</p>
    </div>

    <div class="footer">
      YUCLAW Today's Evidence Changes · built {escape(built)} ·
      <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> · research &amp; education only
    </div>
  </div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    today = datetime.now(timezone.utc).date()
    state = gather(today)
    last_state = _previous_state(today)
    diffs = _diffs(state, last_state)
    last_diffs = (_diffs(last_state, _previous_state(date.fromisoformat(last_state["date"])))
                  if last_state else None)
    _archive(state)
    html = render(state, diffs, last_state, last_diffs)
    OUT.write_text(html)
    print(f"[render_todays_evidence] wrote {OUT} ({len(html)} bytes) "
          f"archive={state['date']} replay={state['replay']['status']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
