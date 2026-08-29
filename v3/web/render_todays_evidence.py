"""
Render the daily "Today's evidence changes" page (docs/todays_evidence.html)
— Part D of the usefulness build (2026-07-16). Runs in the daily regen chain.

Counts and classifications ONLY — locked vocabulary, zero interpretation:
  new filings ingested · new accepted events · grade changes · C6 posture
  changes · newly matured CAR events · Form-4 arrivals (count + buy/sell
  split) · failed-ingestion notes · ledger root · replay status.

Rolling 30-day archive: docs/evidence_changes/YYYY-MM-DD.json holds each
day's state; diffs (grades, maturity) compare today against the most recent
prior archive day. Archive days beyond 30 are pruned.

C6 posture set (ORDER 2026-08-29B, effective 2026-08-29): the CUMULATIVE
accession set lives at docs/c6_posture_current.json (mutable, always latest;
{as_of, files, set_sha256, accessions}); each daily file carries ONLY a
"c6_posture" block {files, set_sha256, added_today, removed_today,
current_url} — a true one-day delta. set_sha256 = sha256 of the sorted UNIQUE
accession strings (byte-lexicographic, UTF-8) joined with "\n", no trailing
newline. Temporal coupling (MICRO 2026-08-29C): the delta is computed against
the PREVIOUS ENDPOINT whenever it exists and parses, with the base labeled
explicitly — delta_since = previous.as_of, delta_span_days = calendar days
(a same-UTC-day rerun reconstructs the base exactly from today's own recorded
delta). Only a missing/corrupt/undated previous endpoint publishes
added_today/removed_today = null with delta_status UNAVAILABLE. Files dated < 2026-08-29 keep the
legacy inline c6_posture_accessions / c6_posture_files keys and are never
rewritten. The current set is computed ONCE per run (single snapshot) and the
endpoint, the daily block and the HTML all derive from it.

CLI: python3 -m v3.web.render_todays_evidence
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

import psycopg2

from v3.web.useful_blocks import footer_stamp_html, build_footer, freshness_strip, VERSION, site_header_html

_REPO = Path(__file__).resolve().parents[2]
OUT = _REPO / "docs" / "todays_evidence.html"
ARCHIVE_DIR = _REPO / "docs" / "evidence_changes"
C6_DIR = _REPO / "output" / "swarm" / "canada"
DSN = "dbname=yuclaw_events"
ARCHIVE_DAYS = 30
C6_CURRENT = _REPO / "docs" / "c6_posture_current.json"
C6_CURRENT_URL = "/c6_posture_current.json"
POSTURE_SCHEMA_CUTOVER = date(2026, 8, 29)   # daily files >= this carry c6_posture
DAILY_KEY_ORDER = ("date", "counts", "c6_posture", "grades", "ledger", "maturity", "replay")
GAP_STATUS = "UNAVAILABLE (previous endpoint missing/corrupt/undated)"

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


def _grades_and_maturity() -> tuple[dict, dict]:
    """Current evidence-tier grades {ticker: grade}, per-lens maturity."""
    from v3.lab.etf_evidence import CANADA_LENS_KEYS, canada_event_maturity, canada_posture
    grades: dict[str, str] = {}
    maturity: dict[str, dict] = {}
    for lens in CANADA_LENS_KEYS:
        p = canada_posture(lens)
        for m in p["members"]:
            grades[m["ticker"]] = m["grade"].split(" ")[0]  # letter only
        mat = canada_event_maturity(lens)
        maturity[lens] = {"n_events": mat["n_events"], "n_matured": mat["n_matured"]}
    return grades, maturity


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


# --------------------------------------------------------------------------- #
# C6 posture set — single snapshot, pinned hash, fail-closed one-day delta
# --------------------------------------------------------------------------- #
def posture_set_sha256(accessions) -> str:
    """HASH DEFINITION (ORDER 2026-08-29B): sorted UNIQUE accession strings,
    byte-lexicographic order (locale-independent), UTF-8, joined with "\n",
    NO trailing newline; sha256 of those bytes."""
    uniq = sorted({a.encode("utf-8") for a in accessions})
    return hashlib.sha256(b"\n".join(uniq)).hexdigest()


def c6_snapshot() -> list[str]:
    """The current cumulative C6 posture accession set — computed ONCE per
    run; every artifact (endpoint, daily block, HTML) derives from it."""
    if not C6_DIR.exists():
        return []
    return sorted({p.stem for p in C6_DIR.glob("*.json")})


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def previous_posture_set(today: date, current_endpoint: dict | None = None,
                         today_daily: dict | None = None) -> tuple[set[str] | None, str | None, str]:
    """(yesterday-or-earlier set, its as_of date, reason) — MICRO 2026-08-29C:
    the delta is published against the PREVIOUS ENDPOINT whenever it exists
    and parses, with the base labeled explicitly (delta_since / delta_span_days
    in the block). UNAVAILABLE only when the endpoint is missing, corrupt or
    undated. The endpoint is captured BEFORE it is overwritten.

    Same-UTC-day rerun (endpoint.as_of == today; the chain can run more than
    once per day): the base is reconstructed EXACTLY as endpoint.accessions
    - today.added_today + today.removed_today from the daily file already
    written today, keeping that file's delta_since; if that recorded delta was
    itself unavailable, so is this one."""
    ep = current_endpoint if current_endpoint is not None else (
        _load_json(C6_CURRENT) if C6_CURRENT.exists() else None)
    if ep is None:
        return None, None, "previous endpoint missing (c6_posture_current.json absent or unparseable)"
    as_of, acc = ep.get("as_of"), ep.get("accessions")
    if not isinstance(acc, list) or not all(isinstance(a, str) for a in acc):
        return None, None, f"previous endpoint corrupt (accessions not a list of strings; as_of={as_of!r})"
    try:
        as_of_d = date.fromisoformat(str(as_of))
    except (TypeError, ValueError):
        return None, None, f"previous endpoint undated (as_of={as_of!r})"
    if as_of_d > today:
        return None, None, f"previous endpoint dated in the future (as_of={as_of})"
    if as_of_d == today:
        td = today_daily if today_daily is not None else _load_json(
            ARCHIVE_DIR / f"{today.isoformat()}.json")
        blk = (td or {}).get("c6_posture") or {}
        add, rem, since = blk.get("added_today"), blk.get("removed_today"), blk.get("delta_since")
        if (td or {}).get("date") == today.isoformat() and isinstance(add, list) \
                and isinstance(rem, list) and blk.get("set_sha256") == ep.get("set_sha256"):
            if not isinstance(since, str):      # 29B-era block: base was date-1 by construction
                since = (today - timedelta(days=1)).isoformat()
            prev = (set(acc) - set(add)) | set(rem)
            return prev, since, (f"same-day rerun: base {since} reconstructed from endpoint "
                                 f"as_of={as_of} minus today's recorded delta (+{len(add)}/-{len(rem)})")
        # Today's recorded delta is unusable: the last archived file dated
        # before today whose set is recoverable (legacy inline array) is a
        # truthful, explicitly labeled base. Archived files are read, never written.
        for prior in sorted(ARCHIVE_DIR.glob("????-??-??.json"), reverse=True):
            if prior.stem >= today.isoformat():
                continue
            pj = _load_json(prior)
            if pj and pj.get("date") == prior.stem and isinstance(pj.get("c6_posture_accessions"), list):
                return set(pj["c6_posture_accessions"]), prior.stem, (
                    f"same-day rerun, today's recorded delta unavailable; base = archived "
                    f"evidence_changes/{prior.stem}.json (legacy inline set)")
        return None, None, (f"same-day rerun but today's recorded delta unavailable and no "
                            f"archived file with a recoverable set (endpoint as_of={as_of})")
    return set(acc), as_of_d.isoformat(), f"previous endpoint as_of={as_of}"


def build_posture_block(snapshot: list[str], prev: set[str] | None,
                        since: str | None, reason: str, today: date) -> dict:
    blk: dict = {"files": len(snapshot), "set_sha256": posture_set_sha256(snapshot)}
    if prev is None or since is None:
        blk["added_today"] = None
        blk["removed_today"] = None
        blk["delta_since"] = None
        blk["delta_span_days"] = None
        blk["delta_status"] = GAP_STATUS
        print(f"[render_todays_evidence] !!! C6 POSTURE DELTA UNAVAILABLE — {reason}; "
              f"publishing added_today/removed_today = null (fail-closed)", file=sys.stderr, flush=True)
        print(f"[render_todays_evidence] !!! C6 POSTURE DELTA UNAVAILABLE — {reason}", flush=True)
    else:
        cur = set(snapshot)
        span = (today - date.fromisoformat(since)).days
        blk["added_today"] = sorted(cur - prev)
        blk["removed_today"] = sorted(prev - cur)
        blk["delta_since"] = since
        blk["delta_span_days"] = span
        blk["delta_status"] = "OK"
        print(f"[render_todays_evidence] c6 posture delta since {since} (span {span}d; {reason}): "
              f"+{len(blk['added_today'])} / -{len(blk['removed_today'])} "
              f"(files={len(snapshot)})", flush=True)
    blk["current_url"] = C6_CURRENT_URL
    return blk


def build_endpoint(today: date, snapshot: list[str]) -> dict:
    return {"as_of": today.isoformat(), "files": len(snapshot),
            "set_sha256": posture_set_sha256(snapshot), "accessions": list(snapshot)}


def gather(today: date, snapshot: list[str] | None = None,
           prev_set: set[str] | None = None, prev_since: str | None = None,
           prev_reason: str = "") -> dict:
    grades, maturity = _grades_and_maturity()
    if snapshot is None:
        snapshot = c6_snapshot()
    parts = {
        "date": today.isoformat(),
        "counts": _db_counts(today),
        "c6_posture": build_posture_block(snapshot, prev_set, prev_since, prev_reason, today),
        "grades": grades,
        "ledger": _ledger_tip(),
        "maturity": maturity,
        "replay": _replay_status(),
    }
    return {k: parts[k] for k in DAILY_KEY_ORDER}   # explicit human-first key order


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
        return {"baseline": True, "grade_changes": [], "newly_matured": {}}
    grade_changes = []
    pg = prev.get("grades", {})
    for tk, g in sorted(state["grades"].items()):
        if tk in pg and pg[tk] != g:
            grade_changes.append({"ticker": tk, "from": pg[tk], "to": g})
    newly_matured = {}
    pm = prev.get("maturity", {})
    for lens, m in state["maturity"].items():
        delta = m["n_matured"] - pm.get(lens, {}).get("n_matured", m["n_matured"])
        if delta:
            newly_matured[lens] = delta
    return {"baseline": False, "grade_changes": grade_changes,
            "newly_matured": newly_matured, "prev_date": prev.get("date")}


def _archive(state: dict) -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    # No sort_keys: DAILY_KEY_ORDER is the canonical (human-first) order.
    (ARCHIVE_DIR / f"{state['date']}.json").write_text(
        json.dumps(state, indent=1, default=str))
    days = sorted(ARCHIVE_DIR.glob("????-??-??.json"))
    for p in days[:-ARCHIVE_DAYS]:
        p.unlink()


def _write_endpoint(endpoint: dict, path: Path | None = None) -> None:
    (path or C6_CURRENT).write_text(json.dumps(endpoint, indent=1))


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def _posture_html(state: dict, prev: dict | None) -> str:
    """Counts + delta + link ONLY — the accession array appears nowhere in
    HTML. New-format states render their c6_posture block; legacy archived
    states (< 2026-08-29) render counts derived from their inline arrays."""
    blk = state.get("c6_posture")
    if blk is not None:
        sha = escape(str(blk.get("set_sha256", "")))
        head = (f"{blk['files']} files in the current set · set_sha256 "
                f"<code>{sha}</code>")
        if blk.get("added_today") is None:
            delta = (f"<span style='color:#FBA94B;font-weight:700'>delta {escape(str(blk.get('delta_status')))}"
                     f"</span>")
        else:
            delta = (f"since {escape(str(blk.get('delta_since')))} ({blk.get('delta_span_days')}d span): "
                     f"+{len(blk['added_today'])} added / −{len(blk['removed_today'])} removed")
        return (f"{head} · {delta} · <a href='c6_posture_current.json'>current set (JSON)</a>")
    n = state.get("c6_posture_files", 0)
    cur = set(state.get("c6_posture_accessions", []))
    if prev is None or "c6_posture_accessions" not in prev:
        return f"{n} files in the set (legacy inline list in the archived JSON)"
    pv = set(prev["c6_posture_accessions"])
    return (f"{n} files in the set · +{len(cur - pv)} added / −{len(pv - cur)} removed vs "
            f"{escape(str(prev.get('date')))} (legacy inline list in the archived JSON)")


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


def _panel_rows(state: dict, diffs: dict, prev: dict | None = None) -> str:
    """The digest table body for one UTC day — shared by the in-progress
    panel and the last-completed-day panel (rendered from the archive)."""
    c = state["counts"]
    posture_html = _posture_html(state, prev)

    if diffs["baseline"]:
        diff_note = ("<span style='color:#718096'>First archive day — change tracking begins "
                     "tomorrow (no prior day to compare against).</span>")
        grade_html = matured_html = diff_note
    else:
        gc = diffs["grade_changes"]
        grade_html = (" · ".join(f"{escape(g['ticker'])}: {escape(g['from'])} → {escape(g['to'])}"
                                 for g in gc)
                      if gc else "<span style='color:#718096'>none</span>")
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
        row("C6 posture set", posture_html),
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
           last_state: dict | None, last_diffs: dict | None,
           last_prev: dict | None = None) -> str:
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = _panel_rows(state, diffs, last_state)

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
      <table><tbody>{_panel_rows(last_state, last_diffs, last_prev)}</tbody></table>
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
      <p style="font-size:11.5px;color:#718096;margin-top:8px;line-height:1.6">
        Files before 2026-08-29 carry the cumulative posture list inline; from 2026-08-29 the current set
        lives at <a href="c6_posture_current.json">/c6_posture_current.json</a> and daily files carry deltas.
        Schema and hash definition: <a href="for_ai_builders.html#evidence-changes">for AI builders</a>.
      </p>
    </div>

    <div class="footer">
      YUCLAW Today's Evidence Changes ·
      <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> · research &amp; education only
    </div>
  </div>
{footer_stamp_html(freshness_strip())}
{build_footer()}
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    today = datetime.now(timezone.utc).date()
    # 4c SINGLE SNAPSHOT — computed once; endpoint, daily block, HTML derive from it.
    snapshot = c6_snapshot()
    # 4a capture the existing endpoint BEFORE it is overwritten (no read-after-write).
    prev_endpoint = _load_json(C6_CURRENT) if C6_CURRENT.exists() else None
    today_daily = _load_json(ARCHIVE_DIR / f"{today.isoformat()}.json")
    prev_set, since, reason = previous_posture_set(today, prev_endpoint, today_daily)
    state = gather(today, snapshot, prev_set, since, reason)
    endpoint = build_endpoint(today, snapshot)
    last_state = _previous_state(today)
    diffs = _diffs(state, last_state)
    last_prev = _previous_state(date.fromisoformat(last_state["date"])) if last_state else None
    last_diffs = _diffs(last_state, last_prev) if last_state else None
    _archive(state)
    _write_endpoint(endpoint)
    html = render(state, diffs, last_state, last_diffs, last_prev)
    OUT.write_text(html)
    print(f"[render_todays_evidence] wrote {OUT} ({len(html)} bytes) "
          f"archive={state['date']} c6_files={endpoint['files']} "
          f"set_sha256={endpoint['set_sha256'][:16]}… "
          f"delta={state['c6_posture']['delta_status']} "
          f"replay={state['replay']['status']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
