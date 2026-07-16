"""YUCLAW AI-ETF Evidence Module — SMH-class semiconductor theme, done as an
event study on EDGAR-filing constituents.

Scope (stated honestly, and rendered on the page):
  * Theme instrument: SMH (VanEck Semiconductor ETF). Constituent list is a
    DATED public fund-disclosure snapshot (holdings as of 2026-07-03, 26
    holdings, 25 disclosed below; the remaining sliver is undisclosed in the
    free listing). Fund holdings/weights are issuer disclosures, not exchange
    market data — no market-data vendor content is stored or re-published.
  * Evidence coverage = SMH constituents ∩ YUCLAW's 79-ticker universe
    (8 U.S. EDGAR filers). Foreign-domiciled constituents (TSM, ASML, STM,
    NXPI) file 20-F/6-K annually/occasionally, not the 8-K + Form 4 event
    stream this pipeline consumes — they are out of evidence scope, which is
    why foreign-holdings ETFs (e.g. KORU-class country funds) cannot be
    covered by this methodology at all: their constituents produce no EDGAR
    event substrate.

Event study: cumulative abnormal returns (CAR) around accepted L1 evidence
events on covered constituents.
  * DEDUP: multiple filings for the same (ticker, event type, day) — common
    for Form 4 batches — collapse to ONE event observation; both counts are
    reported. Without this, insider-sell clusters pseudo-replicate.
  * TWO abnormal-return models, shown side by side, never averaged:
      - peer model (headline): market = equal-weight of the OTHER covered
        semiconductor constituents that day (excludes the event ticker), so
        the sector melt-up/melt-down factor is removed. This is the fair
        test of whether the evidence adds information BEYOND the theme move.
      - SPY market model (secondary): classic market model; in a strong
        sector regime its "abnormal" return is dominated by the sector
        factor, which is exactly what it shows.
  * Estimation: up to 60 trading days ending 6 days before day 0 (min 30
    obs). Day 0 = first trading day on/after the event timestamp's date.
    CAR window [-5, +20] event-time days. Mean CAR per event type with a
    normal-approximation 95% CI across events, n disclosed at every horizon.
  * Direction-aligned pooled CAR (AR x direction, direction != 0) is the
    "does evidence detection precede full price adjustment" test.
  * Cross-sectional clustering caveat: distinct ticker-days can still share
    calendar days across tickers; CIs assume independence and are therefore
    optimistic. Stated on the page.

RESEARCH STATISTICS ONLY. Derived statistics (returns, CARs, counts, grades);
raw prices never returned. Read-only on the DB.
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from typing import Any

import psycopg2

from v3.lab.cohort_engine import DSN, FORWARD_DAY0, _grade_label, load_prices
from v3.lab.stats import mean as _mean
from v3.lab.stats import ols, stdev

# ---- dated SMH constituent snapshot (issuer fund disclosure) -----------------
SMH_AS_OF = "2026-07-03"
SMH_SOURCE = "VanEck fund holdings disclosure (25 of 26 holdings public in the free listing)"
SMH_HOLDINGS: dict[str, float] = {
    "NVDA": 19.01, "TSM": 9.40, "AVGO": 5.61, "AMD": 5.58, "MU": 5.34,
    "AMAT": 5.33, "ASML": 4.99, "INTC": 4.88, "KLAC": 4.73, "LRCX": 4.68,
    "TXN": 4.56, "MRVL": 4.27, "ADI": 4.23, "QCOM": 3.97, "CDNS": 2.38,
    "SNPS": 1.95, "STM": 1.28, "TER": 1.27, "MPWR": 1.26, "NXPI": 1.24,
    "ALAB": 1.19, "ARM": 1.15, "MCHP": 0.93, "ON": 0.62, "SWKS": 0.16,
}
FOREIGN_DOMICILED = {"TSM", "ASML", "STM", "NXPI"}  # 20-F/6-K filers, no 8-K/Form-4 stream

CAR_PRE, CAR_POST = 5, 20          # CAR window [-5, +20] in event-time trading days
EST_WIN, EST_GAP, EST_MIN = 60, 6, 30  # market-model estimation window parameters
MARKET = "SPY"


def _universe() -> list[str]:
    import json
    from pathlib import Path
    u = json.loads((Path(__file__).resolve().parents[1] / "universe.json").read_text())
    return u["equities"] + u["sector_etfs"] + u["broad_etfs"] + u["macro"]


def overlap_summary() -> dict[str, Any]:
    uni = set(_universe())
    covered = sorted(t for t in SMH_HOLDINGS if t in uni)
    uncovered = sorted(t for t in SMH_HOLDINGS if t not in uni)
    w_cov = sum(SMH_HOLDINGS[t] for t in covered)
    return {
        "etf": "SMH", "as_of": SMH_AS_OF, "source": SMH_SOURCE,
        "n_holdings_disclosed": len(SMH_HOLDINGS),
        "covered": covered, "n_covered": len(covered),
        "covered_weight_pct": round(w_cov, 2),
        "uncovered": uncovered,
        "foreign_uncovered": sorted(FOREIGN_DOMICILED),
        "weights_covered": {t: SMH_HOLDINGS[t] for t in covered},
    }


# ---- current evidence posture -------------------------------------------------
def evidence_rollup() -> dict[str, Any]:
    """Latest forward snapshot per covered constituent + trailing event counts,
    plus a weight-normalized ETF-level rollup. Derived data only."""
    ov = overlap_summary()
    covered = ov["covered"]
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ON (s.ticker)
                       s.ticker, s.signal_time::date, s.signal_label, s.total_score,
                       s.c6_event_impact, s.composite_confidence,
                       COALESCE(array_length(s.evidence_event_ids,1),0),
                       (SELECT count(*) FROM events e
                          WHERE e.event_id = ANY(s.evidence_event_ids)
                            AND e.llm_confidence >= 0.7)
                   FROM signal_snapshots s
                   WHERE s.is_backfill = false AND s.ticker = ANY(%s)
                   ORDER BY s.ticker, s.signal_time DESC""",
                (covered,),
            )
            snap_rows = cur.fetchall()
            cur.execute(
                """SELECT ticker, event_type, count(*),
                          count(*) FILTER (WHERE event_time >= now() - interval '30 days')
                   FROM events
                   WHERE event_status = 'accepted' AND ticker = ANY(%s)
                   GROUP BY 1, 2""",
                (covered,),
            )
            ev_rows = cur.fetchall()

    events_by_tk: dict[str, dict[str, dict[str, int]]] = {}
    for tk, et, n_all, n_30 in ev_rows:
        events_by_tk.setdefault(tk, {})[et] = {"total": int(n_all), "last_30d": int(n_30)}

    members = []
    for tk, as_of, label, score, c6, conf, evc, strong in snap_rows:
        members.append({
            "ticker": tk, "as_of": as_of.isoformat(),
            "label": label, "score": float(score),
            "c6": float(c6) if c6 is not None else None,
            "grade": _grade_label(float(conf) if conf is not None else None,
                                  int(evc or 0), int(strong or 0)),
            "weight_pct": SMH_HOLDINGS[tk],
            "events": events_by_tk.get(tk, {}),
            "events_total": sum(v["total"] for v in events_by_tk.get(tk, {}).values()),
            "events_30d": sum(v["last_30d"] for v in events_by_tk.get(tk, {}).values()),
        })
    members.sort(key=lambda m: -m["weight_pct"])

    w_sum = sum(m["weight_pct"] for m in members) or 1.0
    rollup = {
        "weighted_score": sum(m["score"] * m["weight_pct"] for m in members) / w_sum,
        "weighted_c6": (sum((m["c6"] or 0.0) * m["weight_pct"] for m in members) / w_sum),
        "events_total": sum(m["events_total"] for m in members),
        "events_30d": sum(m["events_30d"] for m in members),
        "as_of": max(m["as_of"] for m in members) if members else None,
        "weight_basis_pct": round(w_sum, 2),
    }
    return {"overlap": ov, "members": members, "rollup": rollup}


# ---- event study ---------------------------------------------------------------
def _daily_returns(px: dict[date, float], dates: list[date]) -> dict[date, float]:
    out = {}
    prev = None
    for d in dates:
        p = px.get(d)
        if p is not None and prev is not None and prev[1] != 0:
            out[d] = p / prev[1] - 1.0
        if p is not None:
            prev = (d, p)
    return out


def event_study(covered: list[str] | None = None,
                insider_note: str | None = None) -> dict[str, Any]:
    """CAR event study over `covered` constituents (default: the SMH overlap).
    Same models/dedup/windows regardless of lens — one methodology, many lenses."""
    if covered is None:
        covered = overlap_summary()["covered"]
    prices, trade_dates = load_prices()
    spy_ret = _daily_returns(prices.get(MARKET, {}), trade_dates)
    tk_ret = {tk: _daily_returns(prices.get(tk, {}), trade_dates) for tk in covered}
    td_index = {d: i for i, d in enumerate(trade_dates)}

    # peer market: for each covered ticker, EW mean of the OTHER covered tickers
    def peer_ret(tk: str) -> dict[date, float]:
        out = {}
        for d in trade_dates:
            vals = [tk_ret[o].get(d) for o in covered if o != tk]
            vals = [v for v in vals if v is not None]
            if vals:
                out[d] = sum(vals) / len(vals)
        return out
    peer_by_tk = {tk: peer_ret(tk) for tk in covered}

    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            # DEDUP at the source: one observation per (ticker, type, direction, day)
            cur.execute(
                """SELECT ticker, event_type, direction, event_time::date AS d,
                          count(*) AS n_filings
                   FROM events
                   WHERE event_status = 'accepted' AND ticker = ANY(%s)
                   GROUP BY 1, 2, 3, 4
                   ORDER BY 4""",
                (covered,),
            )
            events = cur.fetchall()
            cur.execute(
                """SELECT count(*) FROM events
                   WHERE event_status = 'accepted' AND ticker = ANY(%s)""",
                (covered,),
            )
            n_raw_filings = cur.fetchone()[0]

    skipped_est, skipped_range = 0, 0
    per_event: list[dict[str, Any]] = []
    for tk, et, direction, ev_date, n_filings in events:
        # day 0 = first trading day on/after the event date
        day0 = next((d for d in trade_dates if d >= ev_date), None)
        if day0 is None:
            skipped_range += 1
            continue
        i0 = td_index[day0]
        est_days = trade_dates[max(0, i0 - EST_GAP - EST_WIN): max(0, i0 - EST_GAP)]
        ars_by_model: dict[str, dict[int, float]] = {}
        for model, mret in (("peer", peer_by_tk[tk]), ("spy", spy_ret)):
            pairs = [(tk_ret[tk].get(d), mret.get(d)) for d in est_days]
            pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
            if len(pairs) < EST_MIN:
                continue
            reg = ols([a for a, _ in pairs], [b for _, b in pairs])
            if reg is None:
                continue
            ars = {}
            for tau in range(-CAR_PRE, CAR_POST + 1):
                j = i0 + tau
                if 0 <= j < len(trade_dates):
                    d = trade_dates[j]
                    r, m = tk_ret[tk].get(d), mret.get(d)
                    if r is not None and m is not None:
                        ars[tau] = r - (reg["alpha"] + reg["beta"] * m)
            if ars:
                ars_by_model[model] = ars
        if not ars_by_model:
            skipped_est += 1
            continue
        per_event.append({
            "ticker": tk, "type": et, "direction": int(direction),
            "date": ev_date.isoformat(), "n_filings": int(n_filings),
            "ars_peer": ars_by_model.get("peer"), "ars_spy": ars_by_model.get("spy"),
            "era": "backfill" if ev_date < FORWARD_DAY0 else "live",
        })

    def car_curve(evts: list[dict], signed: bool, model: str) -> dict[str, Any]:
        """Mean CAR path with per-tau n and 95% CI across events."""
        key = f"ars_{model}"
        taus = list(range(-CAR_PRE, CAR_POST + 1))
        curves: list[dict[int, float]] = []
        for e in evts:
            ars = e.get(key)
            if not ars:
                continue
            c, cum = {}, 0.0
            sign = e["direction"] if signed else 1
            for tau in taus:
                if tau not in ars:
                    if tau > min(ars):   # path ended (recent event, short window)
                        break
                    continue
                cum += ars[tau] * sign
                c[tau] = cum
            if c:
                curves.append(c)
        pts = []
        for tau in taus:
            vals = [c[tau] for c in curves if tau in c]
            n = len(vals)
            if n == 0:
                continue
            m = _mean(vals)
            se = (stdev(vals) / math.sqrt(n)) if n >= 3 else None
            pts.append({"tau": tau, "mean_car": m, "n": n,
                        "ci_lo": m - 1.96 * se if se is not None else None,
                        "ci_hi": m + 1.96 * se if se is not None else None})
        return {"points": pts, "n_events": len(curves)}

    def both_models(evts: list[dict], signed: bool) -> dict[str, Any]:
        out = {"peer": car_curve(evts, signed, "peer"),
               "spy": car_curve(evts, signed, "spy")}
        out["date_range"] = ([min(e["date"] for e in evts), max(e["date"] for e in evts)]
                             if evts else None)
        return out

    by_type: dict[str, Any] = {}
    type_counts: dict[str, int] = {}
    for e in per_event:
        type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1
    for et, cnt in sorted(type_counts.items(), key=lambda kv: -kv[1]):
        by_type[et] = both_models([e for e in per_event if e["type"] == et], signed=False)

    directional = [e for e in per_event if e["direction"] != 0]
    return {
        "params": {"window": [-CAR_PRE, CAR_POST],
                   "models": {"peer": "EW of the other covered constituents (sector factor removed)",
                              "spy": f"{MARKET} classic market model"},
                   "estimation": f"up to {EST_WIN} trading days ending {EST_GAP} days pre-event, min {EST_MIN} obs",
                   "day0": "first trading day on/after the event timestamp's date",
                   "dedup": "one observation per (ticker, event type, direction, day)"},
        "n_raw_filings": int(n_raw_filings),
        "n_events_deduped": len(events),
        "n_events_used": len(per_event),
        "skipped_insufficient_estimation": skipped_est,
        "skipped_out_of_price_range": skipped_range,
        "by_type": by_type,
        "pooled_directional": both_models(directional, signed=True),
        "pooled_directional_live": both_models([e for e in directional if e["era"] == "live"], signed=True),
        "pooled_directional_backfill": both_models([e for e in directional if e["era"] == "backfill"], signed=True),
        "insider_stream_note": insider_note if insider_note is not None else (
                                "Form 4 (insider) events are a parsed batch covering "
                                "2026-02-18 to 2026-05-15; live Form-4 ingestion is a "
                                "tracked pipeline item, so the live-era sample is 8-K "
                                "derived and small."),
        "price_coverage": [trade_dates[0].isoformat(), trade_dates[-1].isoformat()] if trade_dates else None,
    }


def compute_all() -> dict[str, Any]:
    return {"rollup": evidence_rollup(), "event_study": event_study()}


# ==============================================================================
# Canada Resources evidence lenses (Phase 2, 2026-07-14) — EVIDENCE TIER ONLY.
#
# Per-lens holdings dictionary structure. Primary lenses XEG / ZEO / GDX / URNM;
# EWC is reference-only (NOT a Canada Resources evidence lens); GDXJ is excluded
# (52% SEC-filer coverage with a 68-name silent tail — below the honesty bar).
# Holdings weights come from the committed Phase-1 add-list (issuer/fund
# disclosures, as-of dated) and are used ONLY to derive internal coverage
# statistics — no licensed index data is redistributed.
#
# These names are NOT scored: no composite scores, no signal_snapshots, no Lab
# membership (see v3/universe_tiers.py positive gating). The posture below is
# built from filings evidence (events, prose, grades) alone.
# ==============================================================================

CANADA_LENS_KEYS = ("XEG", "ZEO", "GDX", "URNM")
EWC_REFERENCE_ONLY = "EWC"     # reference lens: broad-Canada context, not an evidence lens
GDXJ_EXCLUDED = "GDXJ"         # excluded: junior-miner coverage/evidence-quality problem

# Measured per-lens coverage from the Phase-1 feasibility study (2026-07-13,
# docs/research/canada_resources/phase1_feasibility.md). "SEC-filer weight" is
# the single measured filings-evidence coverage number for Phase 2 — labeled as
# such, never presented as total-evidence coverage.
CANADA_LENS_META: dict[str, dict[str, Any]] = {
    "XEG": {
        "name": "iShares S&P/TSX Capped Energy Index ETF",
        "theme": "Canadian oil & gas (cap-weighted)",
        "holdings_as_of": "2026-07-10",
        "holdings_source": "BlackRock Canada holdings CSV",
        "sec_filer_weight_pct": 76.0, "n_names_total": 28, "n_names_covered": 8,
        "uncovered_scope": ("TSX-only issuers with no current EDGAR reporting — "
                            "Tourmaline (5.6%), PrairieSky, Peyto, Athabasca and "
                            "peers; their 2026-era '/ADR' CIKs are F-6 depositary "
                            "shells, not reporting companies."),
    },
    "ZEO": {
        "name": "BMO Equal Weight Oil & Gas Index ETF",
        "theme": "Canadian oil & gas (equal-weighted)",
        "holdings_as_of": "2026-07-09",
        "holdings_source": "stockanalysis.com (BMO GAM page unavailable at study time)",
        "sec_filer_weight_pct": 75.0, "n_names_total": 12, "n_names_covered": 9,
        "uncovered_scope": ("TSX-only issuers with no current EDGAR reporting — "
                            "ARC Resources (9.0%), Keyera (8.5%)."),
    },
    "GDX": {
        "name": "VanEck Gold Miners ETF",
        "theme": "Gold miners",
        "holdings_as_of": "2026-03-31",
        "holdings_source": "NPORT-P 0001410368-26-054846 (SEC EDGAR)",
        "sec_filer_weight_pct": 79.0, "n_names_total": 51, "n_names_covered": 28,
        "uncovered_scope": ("ASX/LSE-listed miners with no EDGAR substrate; part of "
                            "the lens weight reports outside SEC jurisdiction."),
    },
    "URNM": {
        "name": "Sprott Uranium Miners ETF",
        "theme": "Uranium miners",
        "holdings_as_of": "2026-03-31",
        "holdings_source": "NPORT-P 0001049169-26-001608 (SEC EDGAR)",
        "sec_filer_weight_pct": 55.0, "n_names_total": 26, "n_names_covered": 9,
        "uncovered_scope": ("Sprott Physical Uranium Trust (13.6% of the lens) does "
                            "not file EDGAR and is a physical trust outside ordinary "
                            "operating-company evidence scope by nature; Kazatomprom "
                            "(LSE GDR), Yellow Cake plc (LSE) and the ASX cohort "
                            "(Paladin, Boss, Deep Yellow, Bannerman) have no EDGAR "
                            "substrate. Coverage is stated at the measured 55% and "
                            "is not inflated beyond measured scope."),
    },
}

_ADDLIST_PATH = (Path(__file__).resolve().parents[2]
                 / "docs" / "research" / "canada_resources" / "addlist_final.json")


def canada_lens_holdings() -> dict[str, dict[str, float]]:
    """lens -> {US-line ticker: lens weight %} for the covered (SEC-filer) names,
    from the committed Phase-1 add-list (single source of truth)."""
    import json
    add = json.loads(_ADDLIST_PATH.read_text())
    out: dict[str, dict[str, float]] = {k: {} for k in CANADA_LENS_KEYS}
    for _cik, v in add["constituents"].items():
        core = [l for l in v["in"] if l in out]
        if not core:      # EWC-/GDXJ-only names (some without US lines) are not lens members
            continue
        tick = v["us_line"].split(":")[1]
        for lens in core:
            out[lens][tick] = float(v["in"][lens])
    return out


def _evidence_tier_meta() -> dict[str, dict[str, Any]]:
    from v3.universe_tiers import evidence_tier_records
    return {r["ticker"]: r for r in evidence_tier_records()}


def canada_posture(lens: str) -> dict[str, Any]:
    """Evidence posture for one Canada lens — filings evidence ONLY (no composite
    scores, no rankings). Insider-derived stats for MJDS/FPI names are EXCLUDED
    (SEDI substrate, not Form 4), never rendered as zero."""
    holdings = canada_lens_holdings()[lens]
    meta = _evidence_tier_meta()
    tickers = sorted(holdings)
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT ticker, source_type, count(*)
                   FROM events_raw WHERE ticker = ANY(%s) AND extraction_status='done'
                   GROUP BY 1, 2""", (tickers,))
            filed = {}
            for tk, st, n in cur.fetchall():
                filed.setdefault(tk, {})[st] = int(n)
            cur.execute(
                """SELECT ticker, event_type, count(*), max(event_time::date),
                          avg(llm_confidence)
                   FROM events
                   WHERE event_status='accepted' AND ticker = ANY(%s)
                   GROUP BY 1, 2""", (tickers,))
            ev = {}
            for tk, et, n, last, conf in cur.fetchall():
                ev.setdefault(tk, {})[et] = {"n": int(n), "last": last.isoformat(),
                                             "avg_conf": float(conf or 0)}
            cur.execute(
                """SELECT er.ticker, count(*)
                   FROM yuclaw_v5.swarm_inputs si
                   JOIN public.events_raw er ON er.accession_number = si.accession_number
                   WHERE er.ticker = ANY(%s) AND si.narrative_section <> 'raw_cover'
                   GROUP BY 1""", (tickers,))
            prose = {tk: int(n) for tk, n in cur.fetchall()}
            # C6 posture (v5 risk channel) where a swarm run exists for a filing
            cur.execute(
                """SELECT er.ticker, so.accession_number,
                          so.grounding_summary->'per_agent' IS NOT NULL
                   FROM yuclaw_v5.swarm_outputs so
                   JOIN public.events_raw er ON er.accession_number = so.accession_number
                   WHERE er.ticker = ANY(%s)""", (tickers,))
            swarm_runs = {}
            for tk, acc, _g in cur.fetchall():
                swarm_runs.setdefault(tk, []).append(acc)

    members = []
    for tk in tickers:
        m = meta.get(tk, {})
        events = ev.get(tk, {})
        n_events = sum(v["n"] for v in events.values())
        n_filings = sum(filed.get(tk, {}).values())
        n_prose = prose.get(tk, 0)
        # Deterministic evidence grade — coverage depth, not desirability:
        #   A: accepted events + exhibit/MD&A prose on file
        #   B: filings ingested + prose, no accepted events yet
        #   C: filings ingested, cover-only substrate so far
        #   D: no filings ingested yet (coverage accrues forward)
        if n_events > 0 and n_prose > 0:
            grade = "A (events + prose evidence)"
        elif n_filings > 0 and n_prose > 0:
            grade = "B (prose evidence, no accepted events yet)"
        elif n_filings > 0:
            grade = "C (cover-only substrate so far)"
        else:
            grade = "D (no filings ingested yet)"
        filer_class = m.get("filer_class", "?")
        # Live substrate counts, not judgments (Form-4 live ingestion 2026-07-16).
        # CANADA_FORM4_TICKERS is the authority for a real Form-4 substrate:
        # ENB/IMO are filer_class=DOMESTIC in tier metadata but Section-16-exempt
        # FPIs — no Form-4 stream exists for them.
        from v3.sources.form4_parser import CANADA_FORM4_TICKERS
        n_insider_ev = sum(v["n"] for et, v in events.items()
                           if et in ("INSIDER_BUY", "INSIDER_SELL"))
        if tk in CANADA_FORM4_TICKERS:
            insider_scope = (f"Form 4 stream, live · {n_insider_ev} insider event(s)"
                             if n_insider_ev else "Form 4 stream, live · none yet")
        elif filer_class == "DOMESTIC":
            insider_scope = ("US-domestic form set, but Section-16-exempt FPI — "
                             "no Form 4 stream")
        else:
            insider_scope = "Outside current evidence scope — SEDI substrate not currently ingested"
        members.append({
            "ticker": tk, "weight_pct": holdings[tk],
            "sec_name": m.get("sec_name", tk), "filer_class": filer_class,
            "listing_quality": m.get("listing_quality", "us_primary"),
            "filings_ingested": filed.get(tk, {}), "n_filings": n_filings,
            "events": events, "n_events": n_events,
            "prose_filings": n_prose, "grade": grade,
            "insider_scope": insider_scope,
            "c6_swarm_runs": len(swarm_runs.get(tk, [])),
        })
    members.sort(key=lambda x: -x["weight_pct"])

    covered_w = sum(holdings.values())
    return {
        "lens": lens, **CANADA_LENS_META[lens],
        "holdings": holdings, "members": members,
        "covered_weight_pct_of_lens": round(covered_w, 2),
        "n_covered_names": len(tickers),
        "events_total": sum(m["n_events"] for m in members),
        "filings_total": sum(m["n_filings"] for m in members),
        "prose_total": sum(m["prose_filings"] for m in members),
    }


def canada_event_maturity(lens: str) -> dict[str, Any]:
    """How many accepted events on this lens have a COMPLETE [-5,+20] post-event
    window in available price history ('matured'). CAR panels render only when
    matured events exist; the study accrues forward — no fabricated history."""
    holdings = canada_lens_holdings()[lens]
    tickers = sorted(holdings)
    prices, trade_dates = load_prices()
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ticker, event_type, direction, event_time::date
                   FROM events WHERE event_status='accepted' AND ticker = ANY(%s)""",
                (tickers,))
            events = cur.fetchall()
    matured = 0
    for tk, _et, _dr, d in events:
        day0_idx = next((i for i, td in enumerate(trade_dates) if td >= d), None)
        if day0_idx is not None and day0_idx + CAR_POST < len(trade_dates):
            matured += 1
    return {"lens": lens, "n_events": len(events), "n_matured": matured}


# CAR panels stay hidden below this per-lens matured-event count — a mean path
# over a handful of events implies a conclusion the sample cannot carry.
CANADA_CAR_MIN_EVENTS = 5


def compute_canada() -> dict[str, Any]:
    """All Canada lenses: posture always; event study ONLY where matured events
    clear CANADA_CAR_MIN_EVENTS (else the renderer shows the honest placeholder)."""
    insider_note = ("Insider-derived statistics are EXCLUDED for MJDS/FPI issuers "
                    "(SEDI substrate in Canada, not Form 4) — excluded means outside "
                    "current evidence scope, not observed absence. A Form 4 stream "
                    "exists only for the US-domestic filers in the lens.")
    out: dict[str, Any] = {"lenses": {}, "reference_only": EWC_REFERENCE_ONLY,
                           "excluded": GDXJ_EXCLUDED}
    for lens in CANADA_LENS_KEYS:
        posture = canada_posture(lens)
        maturity = canada_event_maturity(lens)
        entry: dict[str, Any] = {"posture": posture, "maturity": maturity}
        if maturity["n_matured"] >= CANADA_CAR_MIN_EVENTS:
            entry["event_study"] = event_study(
                covered=sorted(canada_lens_holdings()[lens]), insider_note=insider_note)
        out["lenses"][lens] = entry
    return out


if __name__ == "__main__":
    res = compute_all()
    ov = res["rollup"]["overlap"]
    print(f"SMH coverage: {ov['n_covered']}/{ov['n_holdings_disclosed']} holdings, "
          f"{ov['covered_weight_pct']}% of weight: {ov['covered']}")
    es = res["event_study"]
    print(f"events: raw_filings={es['n_raw_filings']} deduped={es['n_events_deduped']} "
          f"used={es['n_events_used']} skipped_est={es['skipped_insufficient_estimation']}")

    def show(tag, c):
        for model in ("peer", "spy"):
            pts = c[model]["points"]
            if not pts:
                print(f"  {tag:24s} [{model}] no points")
                continue
            last = pts[-1]
            ci = (f"ci=({last['ci_lo']:+.4f},{last['ci_hi']:+.4f})"
                  if last["ci_lo"] is not None else "ci=n/a")
            print(f"  {tag:24s} [{model}] n={c[model]['n_events']:3d} "
                  f"CAR[tau={last['tau']}]={last['mean_car']:+.4f} {ci} n@end={last['n']}")

    for et, c in es["by_type"].items():
        show(et, c)
    for key in ("pooled_directional", "pooled_directional_live", "pooled_directional_backfill"):
        show(key, es[key])
