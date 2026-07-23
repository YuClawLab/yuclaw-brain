#!/usr/bin/env python3
"""
Synthesis-layer REAL-DATA runner (owner-directed activation, 2026-07-22).

Builds a LensSnapshot per Canada lens (XEG/ZEO/GDX/URNM) from the SAME live
substrate the public lens cards render (canada_posture / canada_event_maturity
/ output/swarm/canada C6 artifacts / the Lab's event-study internals), then
runs ResearchBrief + ClusteredCAR (+5/+10/+20) + TensionEngine +
DecisionCanvas and renders PREVIEW pages to docs/preview/<lens>_synthesis.html.

Every number is queried — nothing typed by hand. The only hand-authored
mapping is EVENT-TYPE VOCABULARY (DB names -> module tension vocabulary),
which maps categories, not values.

Modes:
    python3 tools/yuclaw_synthesis_run.py                 # full run + previews
    python3 tools/yuclaw_synthesis_run.py --archive-only  # daily-chain snapshot dump

Archives: output/synthesis/<data_through>_<lens>_snapshot.json — tomorrow's
delta baseline. Today (first run) there is no prior archive, so ResearchBrief
runs in current-state-only mode (prev = cur; all deltas render as zero).

The public canada_resources.html is NOT touched by this script.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import psycopg2

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "tools"))

from yuclaw_research_brief import (CarPoint, Funnel, IssuerRow, LensSnapshot,
                                   ResearchBrief)
from yuclaw_evidence_canvas import (ClusteredCAR, DecisionCanvas, TensionEngine,
                                    METHOD_HASH)

from v3.lab.etf_evidence import (CANADA_LENS_KEYS, CAR_POST, CAR_PRE, EST_GAP,
                                 EST_MIN, EST_WIN, MARKET, canada_lens_holdings,
                                 canada_posture, canada_event_maturity,
                                 _daily_returns)
from v3.lab.cohort_engine import DSN, load_prices
from v3.lab.stats import ols

ARCHIVE_DIR = _REPO / "output" / "synthesis"
PREVIEW_DIR = _REPO / "docs" / "preview"
HORIZONS = (5, 10, 20)
RECENT_DAYS = 30  # window for TensionEngine "recent_event_types"

# DB event-type names -> module tension vocabulary (categories, not values).
TYPE_MAP = {
    "DIVIDEND_CHANGE": "DIVIDEND",
    "BUYBACK_ANNOUNCE": "BUYBACK",
    "GUIDANCE_RAISE": "GUIDANCE_RAISE",
    "GUIDANCE_CUT": "GUIDANCE_CUT",
    "REGULATORY_ACTION": "REGULATORY",
    "LITIGATION": "LITIGATION",
}

BANNER = (
    '<div style="background:#3D2B00;border:2px solid #FBA94B;border-radius:10px;'
    'padding:14px 18px;margin-bottom:18px;font-size:13px;color:#FBA94B;font-weight:700">'
    'PREVIEW — real data, not yet part of the daily build. Unlinked page; '
    'delta baseline starts with the next daily snapshot archive.</div>')


def _build_id() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                       capture_output=True, text=True)
    return r.stdout.strip()[:8] if r.returncode == 0 else "unknown"


def _data_through() -> str:
    """Latest Verified Research Ledger block date (queried, not typed)."""
    last = (Path.home() / "yuclaw-trust" / "verified_research_ledger.jsonl"
            ).read_text().strip().rsplit("\n", 1)[-1]
    return json.loads(last)["date"]


def _c6_state() -> dict[str, dict]:
    """ticker -> latest C6 risk-channel posture (same artifacts the public
    page reads). No rarity percentile exists in the artifacts -> None."""
    out: dict[str, dict] = {}
    for f in sorted((_REPO / "output" / "swarm" / "canada").glob("*.json")):
        d = json.loads(f.read_text())
        rc = d.get("risk_channel") or {}
        if d.get("ticker") and rc:
            out[d["ticker"]] = {"flag": rc.get("flag")}
    return out


def _db_issuer_facts(tickers: list[str], data_through: str) -> dict[str, dict]:
    """last event type/date + recent (30d) mapped types + candidate counts."""
    facts: dict[str, dict] = {t: {"recent": set(), "last_type": None,
                                  "last_date": None} for t in tickers}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ON (ticker) ticker, event_type, event_time::date
                   FROM events WHERE event_status='accepted' AND ticker = ANY(%s)
                   ORDER BY ticker, event_time DESC""", (tickers,))
            for tk, et, d in cur.fetchall():
                facts[tk]["last_type"] = et
                facts[tk]["last_date"] = d.isoformat()
            cur.execute(
                """SELECT ticker, event_type FROM events
                   WHERE event_status='accepted' AND ticker = ANY(%s)
                     AND event_time::date > (%s::date - %s * interval '1 day')
                   GROUP BY 1, 2""", (tickers, data_through, RECENT_DAYS))
            for tk, et in cur.fetchall():
                mapped = TYPE_MAP.get(et)
                if mapped:
                    facts[tk]["recent"].add(mapped)
    return facts


def _funnel_counts(tickers: list[str], posture: dict, matured: int) -> Funnel:
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT count(*) FROM events
                   WHERE ticker = ANY(%s) AND event_status IN ('accepted','rejected')""",
                (tickers,))
            candidates = cur.fetchone()[0]
            cur.execute(
                """SELECT count(*) FROM (
                     SELECT DISTINCT ticker, event_type, direction, event_time::date
                     FROM events WHERE event_status='accepted' AND ticker = ANY(%s)) t""",
                (tickers,))
            after_dedup = cur.fetchone()[0]
            cur.execute(
                """SELECT count(*) FROM (
                     SELECT DISTINCT ticker, event_type, direction, event_time::date
                     FROM events WHERE event_status='accepted' AND ticker = ANY(%s)
                       AND direction <> 0) t""", (tickers,))
            directional_dedup = cur.fetchone()[0]
    return Funnel(
        filings_ingested=int(posture["filings_total"]),
        with_usable_prose=int(posture["prose_total"]),
        candidate_events=int(candidates),
        accepted=int(posture["events_total"]),
        after_dedup=int(after_dedup),
        matured=int(matured),
        direction_eligible=int(min(directional_dedup, matured)),
    )


def _lens_grade(members: list[dict]) -> str:
    """Modal member grade letter (ties -> better-coverage letter). Derived,
    not typed."""
    counts: dict[str, int] = {}
    for m in members:
        g = str(m.get("grade", ""))[:1] or "D"
        counts[g] = counts.get(g, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def per_event_cars(lens: str) -> dict[int, list[tuple[str, float, int, str]]]:
    """(issuer, signed peer-model CAR %, day0 trade-date index) per deduped
    directional event at each horizon — the SAME estimation/window/dedup
    methodology as the Lab's event_study (imported constants), reproduced
    per-event so ClusteredCAR can group by issuer and the sample-anatomy
    block can measure calendar window overlap."""
    covered = sorted(canada_lens_holdings()[lens])
    prices, trade_dates = load_prices()
    spy_ret = _daily_returns(prices.get(MARKET, {}), trade_dates)
    tk_ret = {tk: _daily_returns(prices.get(tk, {}), trade_dates) for tk in covered}
    td_index = {d: i for i, d in enumerate(trade_dates)}

    def peer_ret(tk):
        others = [o for o in covered if o != tk]
        out = {}
        for d in trade_dates:
            vals = [tk_ret[o].get(d) for o in others]
            vals = [v for v in vals if v is not None]
            if vals:
                out[d] = sum(vals) / len(vals)
        return out

    peer_by_tk = {tk: peer_ret(tk) for tk in covered}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ticker, event_type, direction, event_time::date
                   FROM events WHERE event_status='accepted' AND ticker = ANY(%s)
                     AND direction <> 0 ORDER BY 4""", (covered,))
            events = cur.fetchall()

    out: dict[int, list[tuple[str, float, int, str]]] = {h: [] for h in HORIZONS}
    for tk, ev_type, direction, ev_date in events:
        day0 = next((d for d in trade_dates if d >= ev_date), None)
        if day0 is None:
            continue
        i0 = td_index[day0]
        est_days = trade_dates[max(0, i0 - EST_GAP - EST_WIN): max(0, i0 - EST_GAP)]
        pairs = [(tk_ret[tk].get(d), peer_by_tk[tk].get(d)) for d in est_days]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if len(pairs) < EST_MIN:
            continue
        reg = ols([a for a, _ in pairs], [b for _, b in pairs])
        if reg is None:
            continue
        cum = 0.0
        car_at: dict[int, float] = {}
        for tau in range(-CAR_PRE, CAR_POST + 1):
            j = i0 + tau
            if not (0 <= j < len(trade_dates)):
                break
            d = trade_dates[j]
            r, m = tk_ret[tk].get(d), peer_by_tk[tk].get(d)
            if r is None or m is None:
                continue
            cum += (r - (reg["alpha"] + reg["beta"] * m)) * int(direction)
            if tau in HORIZONS:
                car_at[tau] = cum
        for h, v in car_at.items():
            out[h].append((tk, round(v * 100.0, 4), i0, ev_type))
    return out


def build_snapshot(lens: str, build_id: str, data_through: str,
                   pooled: dict[int, list[tuple[str, float]]]) -> LensSnapshot:
    p = canada_posture(lens)
    mat = canada_event_maturity(lens)
    c6 = _c6_state()
    tickers = sorted(canada_lens_holdings()[lens])
    facts = _db_issuer_facts(tickers, data_through)

    issuers = []
    for m in sorted(p["members"], key=lambda x: -x["weight_pct"]):
        tk = m["ticker"]
        st = c6.get(tk, {}).get("flag")
        issuers.append(IssuerRow(
            ticker=tk, weight_pct=float(m["weight_pct"]),
            events_accepted=int(m["n_events"]),
            c6_state=st if st in ("elevated", "normal") else st,
            c6_rarity_pctile=None,
            last_event_type=facts[tk]["last_type"],
            last_event_date=facts[tk]["last_date"],
            new_events_since_prev=0,       # current-state-only mode today
            form4_eligible=("Form 4" in str(m.get("insider_scope", ""))),
        ))

    # CarPoints from the SAME per-event pool ClusteredCAR uses (naive stats
    # computed by the module later; here we store mean/naive CI/n per horizon).
    import math as _math
    car_points = []
    for h in HORIZONS:
        ev = pooled[h]
        if not ev:
            continue
        xs = [c for _, c, *_ in ev]
        n = len(xs)
        mean = sum(xs) / n
        sd = (_math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1))
              if n > 1 else 0.0)
        half = 1.959964 * sd / _math.sqrt(n) if n else 0.0
        car_points.append(CarPoint(
            day=h, peer_car_pct=round(mean, 2), spy_car_pct=round(mean, 2),
            ci_lo_pct=round(mean - half, 2), ci_hi_pct=round(mean + half, 2),
            n=n))

    return LensSnapshot(
        lens=lens, build_id=build_id, data_through=data_through,
        coverage_weight_pct=float(p["sec_filer_weight_pct"]),
        filers_covered=int(p["n_covered_names"]),
        filers_total=int(p["n_names_total"]),
        grade=_lens_grade(p["members"]),
        funnel=_funnel_counts(tickers, p, mat["n_matured"]),
        issuers=issuers, car=car_points)


def archive_snapshot(snap: LensSnapshot) -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    out = ARCHIVE_DIR / f"{snap.data_through}_{snap.lens}_snapshot.json"
    out.write_text(json.dumps(asdict(snap), indent=1, default=str))
    return out


# ------------------------------------------------------- preview v2 (№4–№8)
# Everything below is PRESENTATION on top of the registered engines — computed
# from the live DB / current artifacts at build time, nothing hand-typed.
from datetime import date as _date
from html import escape as _e
from statistics import median as _median


def _anatomy(ev3: list, h: int) -> dict | None:
    """Sample anatomy for one horizon pool: unique issuers, median events per
    issuer, top-3 issuer share, calendar window-overlap % (two events overlap
    when their trading-day windows [i0-CAR_PRE, i0+h] intersect)."""
    n = len(ev3)
    if not n:
        return None
    per: dict[str, int] = {}
    for tk, _c, *_ in ev3:
        per[tk] = per.get(tk, 0) + 1
    counts = sorted(per.values(), reverse=True)
    iv = [(i - CAR_PRE, i + h) for _t, _c, i, *_ in ev3]
    overlapping = sum(
        1 for a, (lo, hi) in enumerate(iv)
        if any(b != a and iv[b][0] <= hi and iv[b][1] >= lo for b in range(n)))
    return {"n": n, "issuers": len(per),
            "med_per_issuer": round(_median(counts), 1),
            "top3_share_pct": round(100.0 * sum(counts[:3]) / n),
            "overlap_pct": round(100.0 * overlapping / n)}


def _issuer_aux(tickers: list[str]) -> dict[str, dict]:
    """Per-issuer table upgrades (№6/№8), one read-only DB pass: last filing
    date + latest-filing source status, latest material (non-insider) event,
    distinct accepted event types, last accepted event date, price-history
    completeness over the 30 most recent trade dates."""
    aux: dict[str, dict] = {t: {} for t in tickers}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ON (ticker) ticker, fetched_at::date,
                          (raw_text LIKE source_type || ' filing on %%')
                   FROM events_raw WHERE ticker = ANY(%s)
                   ORDER BY ticker, fetched_at DESC""", (tickers,))
            for tk, d, stub in cur.fetchall():
                aux[tk]["last_filing"] = d.isoformat()
                aux[tk]["source_status"] = ("metadata stub"
                                            if stub else "primary doc fetched")
            cur.execute(
                """SELECT DISTINCT ON (ticker) ticker, event_type, event_time::date
                   FROM events WHERE event_status='accepted' AND ticker = ANY(%s)
                     AND event_type NOT IN ('INSIDER_BUY', 'INSIDER_SELL')
                   ORDER BY ticker, event_time DESC""", (tickers,))
            for tk, et, d in cur.fetchall():
                aux[tk]["material_type"], aux[tk]["material_date"] = et, d.isoformat()
            cur.execute(
                """SELECT ticker, count(DISTINCT event_type), max(event_time::date)
                   FROM events WHERE event_status='accepted' AND ticker = ANY(%s)
                   GROUP BY 1""", (tickers,))
            for tk, ntypes, last in cur.fetchall():
                aux[tk]["n_types"], aux[tk]["last_event"] = int(ntypes), last.isoformat()
            cur.execute(
                "SELECT DISTINCT trade_date FROM price_history "
                "ORDER BY trade_date DESC LIMIT 30")
            recent = [r[0] for r in cur.fetchall()]
            cur.execute(
                """SELECT ticker, count(*) FROM price_history
                   WHERE ticker = ANY(%s) AND close IS NOT NULL
                     AND trade_date = ANY(%s) GROUP BY 1""", (tickers, recent))
            for tk, n in cur.fetchall():
                aux[tk]["px_pct"] = round(100.0 * int(n) / len(recent)) if recent else None
    return aux


def _age_days(thru: str, iso: str | None) -> int | None:
    return (_date.fromisoformat(thru) - _date.fromisoformat(iso)).days if iso else None


_SEC = ('<div style="background:#151A23;border:1px solid #1E232D;border-radius:12px;'
        'padding:20px;margin:18px 0">')
_H = '<div style="font-size:13px;font-weight:700;color:#FFF;margin-bottom:8px">'
_CAP = '<p style="font-size:11px;color:#718096;margin:0 0 10px">'


def _sec_car(infs: list, anat: dict) -> str:
    """№4 — CAR panel: peer-vs-SPY explanation, +5/+10/+20 values printed,
    anatomy beside every horizon. №5 — the anatomy line IS the event-count
    display (no bare n anywhere in this panel)."""
    expl = (
        f"{_CAP}Peer model vs SPY — what these CARs measure: each event's expected "
        f"return is α+β·(equal-weight mean return of the other covered names in this "
        f"lens), estimated over the {EST_WIN} trading days before the event (gap "
        f"{EST_GAP}, minimum {EST_MIN} usable days). The peer model absorbs "
        f"sector-common moves — a commodity swing that lifts every name in the lens "
        f"cancels out — so the residual isolates issuer-specific reaction. A "
        f"SPY-relative CAR answers a different question (movement vs the broad "
        f"market) and widens whenever the sector as a whole moves; the Lab's cohort "
        f"event study reports that variant. All values below are peer-model CARs in "
        f"percent, direction-aligned.</p>")
    rows = []
    for inf in infs:
        an = anat.get(inf.horizon_day) or {}
        rows.append(
            f"<tr><td style='padding:7px 10px;font-weight:700;color:#E2E8F0'>+{inf.horizon_day}d</td>"
            f"<td style='padding:7px 10px;font-family:JetBrains Mono,monospace'>{inf.mean_pct:+.2f}%</td>"
            f"<td style='padding:7px 10px;font-family:JetBrains Mono,monospace'>[{inf.cluster_ci[0]:+.2f}%, {inf.cluster_ci[1]:+.2f}%]</td>"
            f"<td style='padding:7px 10px;font-family:JetBrains Mono,monospace;color:#718096'>[{inf.naive_ci[0]:+.2f}%, {inf.naive_ci[1]:+.2f}%]</td>"
            f"<td style='padding:7px 10px;font-size:11.5px;color:#A0AEC0'>"
            f"{an.get('n', inf.n_events)} events · {inf.n_clusters} unique issuers · "
            f"median {inf.events_per_cluster_median:g} events/issuer · "
            f"top-3 issuer share {inf.top3_cluster_share_pct}% · "
            f"window overlap {an.get('overlap_pct', '—')}%<br>"
            f"<span style='color:#FBA94B'>minimum detectable effect at 80% power: "
            f"±{inf.mde80_pct:.2f}%</span></td></tr>")
    return (f"{_SEC}{_H}CAR panel — clustered inference + sample anatomy</div>{expl}"
            "<table style='width:100%;border-collapse:collapse;font-size:12.5px'>"
            "<tr style='color:#718096;font-size:10.5px;text-transform:uppercase'>"
            "<td style='padding:7px 10px'>Horizon</td><td style='padding:7px 10px'>Mean CAR</td>"
            "<td style='padding:7px 10px'>Cluster CI (primary)</td>"
            "<td style='padding:7px 10px'>Naive CI (comparison)</td>"
            "<td style='padding:7px 10px'>Sample anatomy</td></tr>"
            + "".join(rows) + "</table></div>")


def _sec_types(ev4_20: list, lens: str) -> tuple[str, int]:
    """№2 — event-type decomposition of the pooled CAR at +20: per-type
    mean/CI/n via the registered ClusteredCAR machinery, UNDERPOWERED badges
    where thin. Shows whether the pooled effect concentrates in one event
    type. Returns (html, n_secondary_cells_computed)."""
    from yuclaw_evidence_canvas import badge
    by_type: dict[str, list] = {}
    for tk, c, _i, et in ev4_20:
        by_type.setdefault(et, []).append((tk, c))
    rows, cells = [], 0
    for et, evs in sorted(by_type.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        n = len(evs)
        g = len({t for t, _ in evs})
        if n >= 2 and g >= 2:
            inf = ClusteredCAR(evs, 20).run()
            cells += 1
            b = badge(inf)
            mean = f"{inf.mean_pct:+.2f}%"
            ci = f"[{inf.cluster_ci[0]:+.2f}%, {inf.cluster_ci[1]:+.2f}%]"
            mde = f"±{inf.mde80_pct:.2f}%"
        else:
            b, ci, mde = "UNDERPOWERED", "—", "—"
            mean = f"{sum(c for _, c in evs) / n:+.2f}%"
        bcol = {"UNDERPOWERED": "#FBA94B", "DESCRIPTIVE": "#A0AEC0",
                "PRELIMINARY": "#00E676"}.get(b, "#A0AEC0")
        rows.append(
            f"<tr><td style='padding:6px 10px;color:#E2E8F0'>{_e(et)}</td>"
            f"<td style='padding:6px 10px;font-family:JetBrains Mono,monospace'>{mean}</td>"
            f"<td style='padding:6px 10px;font-family:JetBrains Mono,monospace'>{ci}</td>"
            f"<td style='padding:6px 10px'>{n}</td><td style='padding:6px 10px'>{g}</td>"
            f"<td style='padding:6px 10px;color:{bcol};font-weight:700;font-size:11px'>{b}</td>"
            f"<td style='padding:6px 10px;font-family:JetBrains Mono,monospace;color:#FBA94B'>{mde}</td></tr>")
    return ((f"{_SEC}{_H}Event-type decomposition — pooled CAR at +20d</div>"
             f"{_CAP}Decomposes the pooled +20d CAR by accepted event type — shows whether "
             f"the pooled effect concentrates in a single type. Cluster CI (issuer-clustered, "
             f"registered machinery) where the type has ≥2 events across ≥2 issuers; thin "
             f"types show mean only, badged UNDERPOWERED. MDE = minimum detectable effect at "
             f"80% power.</p>"
             "<table style='width:100%;border-collapse:collapse;font-size:12.5px'>"
             "<tr style='color:#718096;font-size:10.5px;text-transform:uppercase'>"
             "<td style='padding:6px 10px'>Event type</td><td style='padding:6px 10px'>Mean CAR</td>"
             "<td style='padding:6px 10px'>Cluster CI</td><td style='padding:6px 10px'>n</td>"
             "<td style='padding:6px 10px'>Issuers</td><td style='padding:6px 10px'>Badge</td>"
             "<td style='padding:6px 10px'>MDE (80%)</td></tr>"
             + "".join(rows) + "</table></div>"), cells)


def _render_cross_lens(build_id: str, thru: str) -> tuple[Path, int]:
    """№6 — cross-lens issuer view: one table of issuers appearing in more
    than one lens, with per-lens membership + weight and a double-count note.
    Returns (path, n_multi_lens_issuers)."""
    hold = {lens: canada_lens_holdings()[lens] for lens in CANADA_LENS_KEYS}
    issuers: dict[str, dict[str, float]] = {}
    for lens, h in hold.items():
        for tk, w in h.items():
            issuers.setdefault(tk, {})[lens] = w
    multi = {tk: d for tk, d in issuers.items() if len(d) >= 2}
    rows = []
    for tk in sorted(multi, key=lambda k: (-len(multi[k]), k)):
        cells = "".join(
            f"<td style='padding:6px 10px;font-family:JetBrains Mono,monospace'>"
            f"{multi[tk][lens]:.2f}%</td>" if lens in multi[tk]
            else "<td style='padding:6px 10px;color:#718096'>—</td>"
            for lens in CANADA_LENS_KEYS)
        rows.append(f"<tr><td style='padding:6px 10px;font-weight:700;color:#FFF'>{_e(tk)}</td>"
                    f"<td style='padding:6px 10px'>{len(multi[tk])}</td>{cells}</tr>")
    heads = "".join(f"<td style='padding:6px 10px'>{_e(lens)} weight</td>"
                    for lens in CANADA_LENS_KEYS)
    html_out = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>PREVIEW — cross-lens issuers</title>"
        "<body style='background:#0b0f14;color:#E2E8F0;font-family:Inter,sans-serif;"
        "padding:30px;max-width:900px;margin:0 auto'>" + BANNER
        + f"{_SEC}{_H}Cross-lens issuer view — issuers in more than one lens</div>"
        + f"{_CAP}Build {_e(build_id)} · data through {_e(thru)} · membership and weights "
        + f"from the same holdings source the public lens cards use.</p>"
        + "<table style='width:100%;border-collapse:collapse;font-size:12.5px'>"
        + "<tr style='color:#718096;font-size:10.5px;text-transform:uppercase'>"
        + f"<td style='padding:6px 10px'>Issuer</td><td style='padding:6px 10px'>Lenses</td>{heads}</tr>"
        + "".join(rows) + "</table>"
        + "<p style='font-size:12px;color:#FBA94B;margin-top:12px'><strong>Double-count "
        "note:</strong> any future aggregate across lenses must dedup these issuers — "
        "summing per-lens figures counts each of them once per lens they appear in. "
        "Per-lens statistics on this site are within-lens and unaffected.</p>"
        "<p style='font-size:11px;color:#718096'>Research &amp; education only. Not "
        "investment advice. Coverage classifications, not recommendations.</p></body>")
    out = PREVIEW_DIR / "cross_lens_issuers.html"
    out.write_text(html_out)
    return out, len(multi)


_GRADE_ORD = {"A": 4, "B": 3, "C": 2, "D": 1}


def _sec_issuers(members: list[dict], aux: dict, thru: str, lens: str) -> str:
    """№6 — issuer table: client-side sort (weight/events/grade) + filter box;
    latest material event, evidence age, last filing date, source status."""
    rows = []
    for m in members:
        tk = m["ticker"]
        a = aux.get(tk, {})
        g = str(m["grade"])[:1]
        age = _age_days(thru, a.get("last_event"))
        mat = (f"{a['material_type']} · {a['material_date']}"
               if a.get("material_type") else "none accepted yet")
        rows.append(
            f"<tr data-tk='{_e(tk)} {_e(m.get('sec_name', ''))}'>"
            f"<td style='padding:6px 10px;font-weight:700;color:#FFF'>{_e(tk)}</td>"
            f"<td style='padding:6px 10px;color:#A0AEC0;font-size:11.5px'>{_e(str(m.get('sec_name', tk)))}</td>"
            f"<td style='padding:6px 10px' data-v='{m['weight_pct']}'>{m['weight_pct']:.2f}%</td>"
            f"<td style='padding:6px 10px' data-v='{m['n_events']}'>{m['n_events']}</td>"
            f"<td style='padding:6px 10px' data-v='{_GRADE_ORD.get(g, 0)}'>{_e(g)}</td>"
            f"<td style='padding:6px 10px;font-size:11.5px'>{_e(mat)}</td>"
            f"<td style='padding:6px 10px' data-v='{age if age is not None else 99999}'>"
            f"{age if age is not None else '—'}</td>"
            f"<td style='padding:6px 10px;font-size:11.5px'>{_e(a.get('last_filing', '—'))}</td>"
            f"<td style='padding:6px 10px;font-size:11.5px'>{_e(a.get('source_status', 'no filings yet'))}</td>"
            f"</tr>")
    th = ("<th style='padding:6px 10px;text-align:left;color:#718096;font-size:10.5px;"
          "text-transform:uppercase;cursor:{cur};white-space:nowrap' {attr}>{label}</th>")
    heads = "".join([
        th.format(cur="default", attr="", label="Ticker"),
        th.format(cur="default", attr="", label="Issuer"),
        th.format(cur="pointer", attr=f'onclick="synthSort(\'t_{lens}\',2)"', label="Weight ↕"),
        th.format(cur="pointer", attr=f'onclick="synthSort(\'t_{lens}\',3)"', label="Events ↕"),
        th.format(cur="pointer", attr=f'onclick="synthSort(\'t_{lens}\',4)"', label="Grade ↕"),
        th.format(cur="default", attr="", label="Latest material event"),
        th.format(cur="pointer", attr=f'onclick="synthSort(\'t_{lens}\',6)"', label="Evidence age (d) ↕"),
        th.format(cur="default", attr="", label="Last filing"),
        th.format(cur="default", attr="", label="Source status"),
    ])
    return (f"{_SEC}{_H}Issuer table — sortable, filterable</div>"
            f"{_CAP}Material event = latest accepted non-insider event. Evidence age = days "
            f"since the last accepted event of any type, as of {_e(thru)}. Source status "
            f"reflects the most recent filing's document fetch.</p>"
            f"<input placeholder='filter ticker / issuer…' oninput=\"synthFilter('t_{lens}', this.value)\" "
            f"style='background:#0B0E14;border:1px solid #1E232D;border-radius:6px;color:#E2E8F0;"
            f"padding:6px 10px;font-size:12px;margin-bottom:8px;width:240px'>"
            f"<div style='overflow-x:auto'><table id='t_{lens}' "
            f"style='width:100%;border-collapse:collapse;font-size:12.5px'>"
            f"<thead><tr>{heads}</tr></thead><tbody>{''.join(rows)}</tbody></table></div></div>")


def _sec_delta(lens: str) -> str:
    """№7 — per-lens daily delta from the archived snapshots (newest two)."""
    days = sorted(ARCHIVE_DIR.glob(f"????-??-??_{lens}_snapshot.json"))
    if len(days) < 2:
        return (f"{_SEC}{_H}Daily delta</div>{_CAP}fewer than two archived "
                "snapshots — deltas begin with the next daily archive.</p></div>")
    prev, cur = (json.loads(p.read_text()) for p in days[-2:])
    d1, d2 = prev["data_through"], cur["data_through"]
    items = []
    if cur["coverage_weight_pct"] != prev["coverage_weight_pct"]:
        items.append(f"coverage weight {prev['coverage_weight_pct']:.1f}% → "
                     f"{cur['coverage_weight_pct']:.1f}%")
    for k in ("filings_ingested", "with_usable_prose", "candidate_events",
              "accepted", "after_dedup", "matured", "direction_eligible"):
        a, b = prev["funnel"].get(k), cur["funnel"].get(k)
        if isinstance(a, int) and isinstance(b, int) and a != b:
            items.append(f"{k.replace('_', ' ')} {a} → {b} ({b - a:+d})")
    pe = {i["ticker"]: i["events_accepted"] for i in prev["issuers"]}
    for i in cur["issuers"]:
        d = i["events_accepted"] - pe.get(i["ticker"], 0)
        if d:
            items.append(f"{i['ticker']} accepted events {pe.get(i['ticker'], 0)} → "
                         f"{i['events_accepted']} ({d:+d})")
    pc = {c["day"]: c["n"] for c in prev["car"]}
    for c in cur["car"]:
        d = c["n"] - pc.get(c["day"], 0)
        if d:
            items.append(f"matured CAR events at +{c['day']}d: {pc.get(c['day'], 0)} → "
                         f"{c['n']} ({d:+d})")
    body = ("".join(f"<li style='margin:4px 0;color:#A0AEC0;font-size:12.5px'>{_e(x)}</li>"
                    for x in items)
            or "<li style='color:#718096;font-size:12.5px'>no changes between the two days</li>")
    return (f"{_SEC}{_H}Daily delta — {_e(d1)} → {_e(d2)}</div>"
            f"{_CAP}Rendered from the archived snapshots "
            f"(output/synthesis/&lt;date&gt;_{_e(lens)}_snapshot.json) — real day-over-day "
            f"changes, not recomputed history.</p><ul style='list-style:none;padding:0'>"
            f"{body}</ul></div>")


_DIMS = (("coverage", "filings ingested"), ("freshness", "days since last event"),
         ("depth", "prose filings"), ("diversity", "distinct event types"),
         ("price-integrity", "% of last 30 trade dates with a close"))


def _sec_grades(members: list[dict], aux: dict, thru: str) -> str:
    """№8 — grade profile: per letter grade, the dimension breakdown behind
    the coverage classification, as median values + compact bars."""
    groups: dict[str, list[dict]] = {}
    for m in members:
        g = str(m["grade"])[:1]
        a = aux.get(m["ticker"], {})
        age = _age_days(thru, a.get("last_event"))
        groups.setdefault(g, []).append({
            "coverage": m["n_filings"], "freshness": age,
            "depth": m["prose_filings"], "diversity": a.get("n_types", 0),
            "price-integrity": a.get("px_pct"),
        })

    def med(vals):
        vs = [v for v in vals if v is not None]
        return round(_median(vs), 1) if vs else None

    per_grade = {g: {dim: med([r[dim] for r in rows]) for dim, _ in _DIMS}
                 for g, rows in groups.items()}
    maxv = {dim: max((per_grade[g][dim] or 0) for g in per_grade) or 1
            for dim, _ in _DIMS}
    blocks = []
    for g in sorted(per_grade):
        rows = []
        for dim, label in _DIMS:
            v = per_grade[g][dim]
            w = round(88.0 * (v or 0) / maxv[dim])
            shown = "—" if v is None else (f"{v:g}%" if dim == "price-integrity" else f"{v:g}")
            rows.append(
                f"<div style='display:flex;align-items:center;gap:8px;margin:3px 0'>"
                f"<span style='width:110px;font-size:10.5px;color:#718096'>{_e(dim)}</span>"
                f"<span style='display:inline-block;height:7px;width:{w}px;"
                f"background:#00E67655;border-radius:3px'></span>"
                f"<span style='font-size:11px;color:#A0AEC0'>{shown}</span></div>")
        blocks.append(
            f"<div style='flex:1;min-width:200px'>"
            f"<div style='font-weight:800;color:#FFF;margin-bottom:4px'>Grade {_e(g)} "
            f"<span style='color:#718096;font-weight:400;font-size:11px'>"
            f"({len(groups[g])} names, medians)</span></div>{''.join(rows)}</div>")
    return (f"{_SEC}{_H}Grade profile — what each letter is made of</div>"
            f"{_CAP}Coverage classifications, not rankings. Dimension values are medians "
            f"across the names holding each grade: " +
            " · ".join(f"{d} = {l}" for d, l in _DIMS) + ".</p>"
            f"<div style='display:flex;gap:20px;flex-wrap:wrap'>{''.join(blocks)}</div></div>")


_JS = """<script>
function synthSort(tid, col) {
  var tb = document.getElementById(tid).tBodies[0];
  var rows = Array.from(tb.rows);
  var dir = tb.dataset['s' + col] === 'd' ? 1 : -1;
  tb.dataset['s' + col] = dir === 1 ? 'a' : 'd';
  rows.sort(function (a, b) {
    var x = parseFloat(a.cells[col].dataset.v), y = parseFloat(b.cells[col].dataset.v);
    return dir * (x - y);
  });
  rows.forEach(function (r) { tb.appendChild(r); });
}
function synthFilter(tid, q) {
  q = q.toLowerCase();
  Array.from(document.getElementById(tid).tBodies[0].rows).forEach(function (r) {
    r.style.display = r.dataset.tk.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
  });
}
</script>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-only", action="store_true",
                    help="daily-chain mode: dump LensSnapshot JSONs, no previews")
    a = ap.parse_args(argv)

    build_id, thru = _build_id(), _data_through()
    print(f"[synthesis] build {build_id} · data through {thru} · method {METHOD_HASH}")
    run_cells = {"primary": 0, "secondary": 0}

    for lens in CANADA_LENS_KEYS:
        pooled = per_event_cars(lens)
        snap = build_snapshot(lens, build_id, thru, pooled)
        path = archive_snapshot(snap)
        print(f"[synthesis] {lens}: archived {path.name} "
              f"(events@+20: {len(pooled[20])})")
        if a.archive_only:
            continue

        brief = ResearchBrief(snap, snap).build()   # current-state-only today
        infs = [ClusteredCAR([(tk, c) for tk, c, *_ in pooled[h]], h).run()
                for h in HORIZONS if pooled[h]]
        rows = [{"ticker": i.ticker, "c6_state": i.c6_state,
                 "form4_eligible": i.form4_eligible,
                 "recent_event_types":
                     sorted(_db_issuer_facts([i.ticker], thru)[i.ticker]["recent"])}
                for i in snap.issuers]
        tensions = TensionEngine().detect(rows)
        canvas = DecisionCanvas(lens, build_id, thru, infs, tensions, rows)

        # №4–№8 sections (preview v2) — live-computed presentation.
        posture = canada_posture(lens)
        aux = _issuer_aux(sorted(canada_lens_holdings()[lens]))
        anat = {h: _anatomy(pooled[h], h) for h in HORIZONS if pooled[h]}
        types_html, type_cells = _sec_types(pooled[20], lens)
        run_cells["primary"] += len(infs)
        run_cells["secondary"] += 4 * len(infs) + type_cells
        sections = (_sec_car(infs, anat)
                    + types_html
                    + _sec_issuers(posture["members"], aux, thru, lens)
                    + _sec_delta(lens)
                    + _sec_grades(posture["members"], aux, thru))

        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        out = PREVIEW_DIR / f"{lens.lower()}_synthesis.html"
        out.write_text(
            "<!doctype html><meta charset='utf-8'>"
            f"<title>PREVIEW — {lens} synthesis</title>"
            "<body style='background:#0b0f14;color:#E2E8F0;"
            "font-family:Inter,sans-serif;padding:30px;max-width:900px;margin:0 auto'>"
            + BANNER + brief.to_html() + "<hr style='border-color:#1E232D;margin:26px 0'>"
            + canvas.to_html() + "<hr style='border-color:#1E232D;margin:26px 0'>"
            + sections + _JS + "</body>")
        print(f"[synthesis] {lens}: preview -> {out.relative_to(_REPO)}")
        print("\n" + "=" * 74)
        print(brief.to_text())
        print("-" * 74)
        print(canvas.to_text())
        print("=" * 74 + "\n")

    if not a.archive_only:
        # №6 cross-lens issuer view (descriptive; no statistical cells).
        cross_path, n_multi = _render_cross_lens(build_id, thru)
        print(f"[synthesis] cross-lens preview -> {cross_path.relative_to(_REPO)} "
              f"({n_multi} multi-lens issuers)")
        # Record this full run in the protocol registry — every full render
        # computes cluster inferences, so every full render is a run.
        import hashlib as _hl
        h = _hl.sha256()
        for lens in CANADA_LENS_KEYS:
            h.update((PREVIEW_DIR / f"{lens.lower()}_synthesis.html").read_bytes())
        h.update(cross_path.read_bytes())
        from yuclaw_protocol_registry import Registry, Run
        from yuclaw_evidence_canvas import PROTOCOL_ID as _CANVAS_PID
        from datetime import date as _d, datetime as _dt, timezone as _tz
        Registry(str(_REPO / "registry" / "protocols.jsonl")).record_run(Run(
            protocol_id=_CANVAS_PID,
            run_date=_dt.now(_tz.utc).date().isoformat(),
            data_window=f"events through {thru}, 4 lenses x horizons +5/+10/+20 "
                        f"+ per-type decomposition at +20",
            n_primary_cells=run_cells["primary"],
            n_secondary_cells=run_cells["secondary"],
            result_hash=h.hexdigest(),
            note=f"preview render (build {build_id}); secondary = naive/wild/SE/"
                 f"MDE per lens-horizon cell + per-type cluster cells; "
                 f"result_hash = sha256 of the 4 lens previews + cross-lens "
                 f"preview, in render order"))
        print(f"[synthesis] registry: run recorded "
              f"({run_cells['primary']} primary + {run_cells['secondary']} secondary cells)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
