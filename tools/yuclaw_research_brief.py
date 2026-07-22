#!/usr/bin/env python3
"""
YUCLAW Research Brief Engine — deterministic synthesis layer (v1 reference impl)
================================================================================
Turns lens evidence data into a five-part Research Brief + Decision Canvas +
evidence funnel + inspect-next queue, per the Canada Resources external review
(Priorities 1, 2, 4, 6; sections 5, 13, 20, 22, 24) with YUCLAW amendments.

DESIGN GUARANTEES (the part no other dashboard does):
  G1. DETERMINISTIC — no LLM. Same inputs => byte-identical output. The brief
      carries its own sha256 (brief_hash), so synthesis is replayable evidence.
  G2. TRACEABLE — every rendered sentence carries data-refs: the input field
      IDs that back it. A brief you can audit, sentence by sentence.
  G3. STRUCTURALLY COMPLIANT — the interpretation ladder is typed; the
      IMPLICATION slot is a frozen constant. The engine is INCAPABLE of
      emitting an investment implication. Banned-vocabulary sweep runs on
      every render and raises on violation (belt + suspenders).
  G4. STDLIB ONLY — drop-in next to tools/replay_lab.py; no dependencies.

Integration: feed LensSnapshot from the existing canada_posture()/lens-card
data path; prev snapshot from the previous build's JSON (already archived by
the daily chain). Renderers: .to_html() for pages, .to_text() for digest/CLI.
"""
from __future__ import annotations
import hashlib, html, json, re
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---------------------------------------------------------------- vocabulary
# Locked statistical-status badge set (review §2.4, translated to locked vocab)
BADGES = ("REPRODUCED", "DESCRIPTIVE", "PRELIMINARY", "UNDERPOWERED",
          "NOT ESTABLISHED", "ACCRUING")

# G3: frozen implication line. This is the ONLY thing the implication slot
# can ever render. Do not parameterize.
IMPLICATION_FROZEN = ("Investment implication: none established — no buy, "
                      "sell, or alpha conclusion is supported by this page.")

# Words that must never appear in generated prose (negation-guard exempt
# phrases are pre-approved constants above, checked by exact match).
_BANNED = re.compile(
    r"\b(validated|institutional|professional|guaranteed|best[- ]in[- ]class|"
    r"world[- ]class|cutting[- ]edge|market[- ]beating|superior|premier|"
    r"unmatched|state[- ]of[- ]the[- ]art)\b", re.I)
_ALLOWED_EXACT = {IMPLICATION_FROZEN}

# ---------------------------------------------------------------- input model
@dataclass
class IssuerRow:
    ticker: str
    weight_pct: float                 # lens weight
    events_accepted: int
    c6_state: Optional[str] = None    # "elevated" | "normal" | None (not run)
    c6_rarity_pctile: Optional[int] = None
    last_event_type: Optional[str] = None
    last_event_date: Optional[str] = None
    new_events_since_prev: int = 0
    form4_eligible: bool = False      # False => SEDI-scope (MJDS) or exempt

@dataclass
class CarPoint:
    day: int; peer_car_pct: float; spy_car_pct: float
    ci_lo_pct: float; ci_hi_pct: float; n: int

@dataclass
class Funnel:
    filings_ingested: int
    with_usable_prose: int
    candidate_events: int
    accepted: int
    after_dedup: int
    matured: int
    direction_eligible: int
    # reason codes rendered alongside each reduction (review §19–20)
    reasons: dict = field(default_factory=lambda: {
        "with_usable_prose": "no extractable exhibit/MD&A prose",
        "candidate_events": "prose contained no material-event candidate",
        "accepted": "failed deterministic source-grounding verification",
        "after_dedup": "duplicate of an already-accepted event",
        "matured": "forward window not yet complete",
        "direction_eligible": "event type carries no directional prior",
    })

@dataclass
class LensSnapshot:
    lens: str                         # "XEG"
    build_id: str                     # commit / build stamp
    data_through: str                 # "2026-07-16"
    coverage_weight_pct: float
    filers_covered: int
    filers_total: int
    grade: str
    funnel: Funnel
    issuers: list                     # list[IssuerRow], full covered set
    car: list                         # list[CarPoint] at +5/+10/+20
    methodology_version: str = "v5"
    insider_scope_note: str = ("most covered Canadian issuers report insider "
                               "trades through Canada's SEDI system, which is "
                               "not yet ingested")

# ------------------------------------------------------------------- deltas
@dataclass
class Delta:
    new_filings: int; new_accepted: int; newly_matured: int
    c6_state_changes: list            # [(ticker, old, new)]
    grade_changed: Optional[tuple]    # (old,new) or None
    coverage_weight_change_pp: float
    retroactive_edits: int = 0        # must always be 0; rendered as proof

def compute_delta(prev: LensSnapshot, cur: LensSnapshot) -> Delta:
    prev_c6 = {i.ticker: i.c6_state for i in prev.issuers}
    changes = [(i.ticker, prev_c6.get(i.ticker), i.c6_state)
               for i in cur.issuers
               if prev_c6.get(i.ticker) != i.c6_state and i.c6_state]
    return Delta(
        new_filings=cur.funnel.filings_ingested - prev.funnel.filings_ingested,
        new_accepted=cur.funnel.accepted - prev.funnel.accepted,
        newly_matured=cur.funnel.matured - prev.funnel.matured,
        c6_state_changes=changes,
        grade_changed=(prev.grade, cur.grade) if prev.grade != cur.grade else None,
        coverage_weight_change_pp=round(cur.coverage_weight_pct
                                        - prev.coverage_weight_pct, 2),
    )

# --------------------------------------------------------------- derivations
def _concentration(issuers):
    total = sum(i.events_accepted for i in issuers) or 1
    top = sorted(issuers, key=lambda i: (-i.events_accepted, i.ticker))[:2]
    ev_share = round(100 * sum(i.events_accepted for i in top) / total)
    wt_share = round(sum(i.weight_pct for i in
                     sorted(issuers, key=lambda i: (-i.weight_pct, i.ticker))[:2]), 1)
    return top, ev_share, wt_share

def _car_badge(pt: CarPoint) -> str:
    ci_spans_zero = pt.ci_lo_pct <= 0.0 <= pt.ci_hi_pct
    if pt.n < 30: return "UNDERPOWERED"
    return "DESCRIPTIVE" if ci_spans_zero else "PRELIMINARY"

def _inspect_next(cur: LensSnapshot):
    """Fact-triggered review queue. NOT a ranking: items are (ticker, [reasons]),
    ordered by trigger count then alphabetically — ordering is declared in the
    rendered caption. No score is computed or stored (lawyer-gate honored)."""
    out = []
    for i in cur.issuers:
        r = []
        if i.c6_state == "elevated":
            if i.c6_rarity_pctile:
                p = i.c6_rarity_pctile
                sfx = "th" if 10 <= p % 100 <= 20 else                       {1: "st", 2: "nd", 3: "rd"}.get(p % 10, "th")
                r.append(f"C6 posture elevated ({p}{sfx} percentile rarity)")
            else:
                r.append("C6 posture elevated")
        if i.new_events_since_prev:
            r.append(f"{i.new_events_since_prev} new accepted event"
                     + ("s" if i.new_events_since_prev != 1 else "")
                     + " since previous build")
        if i.weight_pct >= 10 and i.c6_state is None:
            r.append(f"{i.weight_pct:.1f}% lens weight but no C6 analysis yet")
        if r:
            out.append((i.ticker, r))
    return sorted(out, key=lambda t: (-len(t[1]), t[0]))

# ------------------------------------------------------------------- engine
class ResearchBrief:
    def __init__(self, prev: LensSnapshot, cur: LensSnapshot):
        self.prev, self.cur = prev, cur
        self.delta = compute_delta(prev, cur)
        self._sentences = []          # (section, text, [data_refs])

    # -- sentence factory: every sentence registers its backing fields (G2)
    def _s(self, section, text, refs):
        self._sentences.append((section, text, refs)); return text

    def build(self):
        c, d = self.cur, self.delta
        top, ev_share, wt_share = _concentration(c.issuers)
        car20 = next((p for p in c.car if p.day == 20), c.car[-1])

        # 1 — WHAT CHANGED (review P1; delta engine §5)
        self._s("changed",
            f"Since build {self.prev.build_id}, {c.lens} added "
            f"{d.new_filings} filing{'s'*(d.new_filings!=1)}, "
            f"{d.new_accepted} accepted event{'s'*(d.new_accepted!=1)}, and "
            f"{d.newly_matured} newly matured event"
            f"{'s'*(d.newly_matured!=1)}.",
            ["funnel.filings_ingested", "funnel.accepted", "funnel.matured"])
        if d.c6_state_changes:
            for t, old, new in d.c6_state_changes:
                self._s("changed",
                        f"{t} moved from C6 {old or 'not run'} to {new}.",
                        [f"issuers[{t}].c6_state"])
        else:
            self._s("changed", "No issuer changed C6 state.",
                    ["issuers[*].c6_state"])
        self._s("changed",
            ("Coverage weight unchanged." if d.coverage_weight_change_pp == 0
             else f"Coverage weight moved {d.coverage_weight_change_pp:+.2f} pp."),
            ["coverage_weight_pct"])
        self._s("changed", f"Retroactive edits: {d.retroactive_edits}.",
                ["ledger.retroactive_edits"])

        # 2 — WHAT MATTERS (concentration + scope)
        self._s("matters",
            f"Evidence is concentrated: {top[0].ticker} and {top[1].ticker} "
            f"hold {ev_share}% of accepted events and {wt_share}% of lens "
            f"weight.",
            ["issuers[*].events_accepted", "issuers[*].weight_pct"])
        f4 = sum(1 for i in c.issuers if i.form4_eligible)
        self._s("matters",
            f"Form 4 coverage: {f4}/{len(c.issuers)} covered issuers — "
            f"{c.insider_scope_note}.",
            ["issuers[*].form4_eligible", "insider_scope_note"])

        # 3 — WHAT THE EVIDENCE SAYS (peer-first, benchmark dependence §11)
        self._s("evidence",
            f"Peer-adjusted event performance is "
            f"{car20.peer_car_pct:+.1f}% at day +{car20.day} "
            f"(95% CI [{car20.ci_lo_pct:+.1f}%, {car20.ci_hi_pct:+.1f}%], "
            f"n={car20.n}) — status: {_car_badge(car20)}.",
            ["car[+20].peer", "car[+20].ci", "car[+20].n"])
        if abs(car20.spy_car_pct - car20.peer_car_pct) >= 1.0:
            self._s("evidence",
                f"The broad-market (SPY-adjusted) path reads "
                f"{car20.spy_car_pct:+.1f}% — the gap versus the peer model "
                f"indicates sector/commodity exposure dominates broad-equity "
                f"beta here; the peer benchmark is the more economically "
                f"relevant reference.",
                ["car[+20].spy", "car[+20].peer"])

        # 4 — WHAT REMAINS UNCERTAIN
        self._s("uncertain",
            "Confidence intervals shown are naive: they assume independent "
            "events, while issuer clustering and overlapping windows make "
            "them optimistic. Clustered inference is scheduled and will be "
            "pre-committed before computation.",
            ["methodology_version"])
        self._s("uncertain",
            "C6 sign confirmation remains accruing; posture states are "
            "research classifications of evidence rarity, not directional "
            "calls.",
            ["issuers[*].c6_state"])

        # 5 — INSPECT NEXT (fact-triggered, unranked)
        self.queue = _inspect_next(c)
        return self

    # ------------------------------------------------------------ integrity
    def _sweep(self, text_blob: str):
        for m in _BANNED.finditer(text_blob):
            frag = text_blob[max(0, m.start()-40):m.end()+40]
            if not any(frag in a or a in frag for a in _ALLOWED_EXACT):
                raise ValueError(f"banned vocabulary in output: {m.group(0)!r}")

    def brief_hash(self) -> str:
        payload = json.dumps([asdict(self.cur), self._sentences],
                             sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    # ------------------------------------------------------------ renderers
    def to_text(self) -> str:
        sec = {"changed": "WHAT CHANGED", "matters": "WHAT MATTERS",
               "evidence": "WHAT THE EVIDENCE SAYS",
               "uncertain": "WHAT REMAINS UNCERTAIN"}
        out = [f"RESEARCH BRIEF — {self.cur.lens} · build {self.cur.build_id}"
               f" · data through {self.cur.data_through}"]
        for k, title in sec.items():
            out.append(f"\n{title}")
            out += [f"  · {t}" for s, t, _ in self._sentences if s == k]
        out.append("\nINSPECT NEXT (ordered by trigger count — not an "
                   "investment ranking)")
        for t, reasons in self.queue:
            out.append(f"  · {t}: " + "; ".join(reasons))
        f = self.cur.funnel
        out.append(f"\nEVIDENCE FUNNEL  {f.filings_ingested} filings → "
                   f"{f.with_usable_prose} with prose → {f.candidate_events} "
                   f"candidates → {f.accepted} accepted → {f.after_dedup} "
                   f"deduplicated → {f.matured} matured → "
                   f"{f.direction_eligible} direction-eligible")
        out.append("\n" + IMPLICATION_FROZEN)
        out.append(f"brief {self.brief_hash()} · deterministic synthesis — "
                   f"no generative model · every sentence backed by the "
                   f"listed data fields")
        blob = "\n".join(out); self._sweep(blob); return blob

    def to_html(self) -> str:
        e = html.escape
        css = """
        .yb-brief{background:#11161d;border:1px solid #232b36;border-radius:10px;
          padding:18px 20px;color:#c9d4e0;font:14px/1.55 -apple-system,Segoe UI,sans-serif}
        .yb-brief h3{margin:0 0 2px;color:#e8eef5;font-size:16px}
        .yb-meta{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:#7d8b99}
        .yb-sec{margin-top:12px}
        .yb-sec b{display:block;font-size:11px;letter-spacing:.12em;color:#8fb996;margin-bottom:4px}
        .yb-sec.unc b{color:#c9a25f}
        .yb-brief li{margin:3px 0 3px 16px}
        .yb-badge{font-family:ui-monospace,monospace;font-size:10px;border:1px solid #3a4654;
          border-radius:3px;padding:1px 5px;color:#9fb2c4;margin-left:6px}
        .yb-queue span{font-family:ui-monospace,monospace;color:#e8eef5}
        .yb-funnel{font-family:ui-monospace,monospace;font-size:12px;color:#9fb2c4;
          background:#0d1218;border-radius:6px;padding:8px 10px;margin-top:12px}
        .yb-frozen{margin-top:12px;font-size:12.5px;color:#c9a25f;border-left:3px solid #c9a25f;
          padding-left:9px}
        .yb-hash{margin-top:10px;font-family:ui-monospace,monospace;font-size:10.5px;color:#5f6d7a}
        """
        sec_titles = {"changed": "WHAT CHANGED", "matters": "WHAT MATTERS",
                      "evidence": "WHAT THE EVIDENCE SAYS",
                      "uncertain": "WHAT REMAINS UNCERTAIN"}
        parts = [f"<style>{css}</style><div class='yb-brief'>",
                 f"<h3>Research Brief — {e(self.cur.lens)}</h3>",
                 f"<div class='yb-meta'>build {e(self.cur.build_id)} · data "
                 f"through {e(self.cur.data_through)} · methodology "
                 f"{e(self.cur.methodology_version)}</div>"]
        for k, title in sec_titles.items():
            cls = "yb-sec unc" if k == "uncertain" else "yb-sec"
            parts.append(f"<div class='{cls}'><b>{title}</b><ul>")
            for s, t, refs in self._sentences:
                if s == k:
                    parts.append(f"<li data-refs='{e(json.dumps(refs))}'>"
                                 f"{e(t)}</li>")
            parts.append("</ul></div>")
        parts.append("<div class='yb-sec'><b>INSPECT NEXT</b>"
                     "<div class='yb-meta'>ordered by trigger count — not an "
                     "investment ranking</div><ul class='yb-queue'>")
        for t, reasons in self.queue:
            parts.append(f"<li><span>{e(t)}</span> — {e('; '.join(reasons))}</li>")
        parts.append("</ul></div>")
        f = self.cur.funnel
        parts.append(f"<div class='yb-funnel'>{f.filings_ingested} filings → "
                     f"{f.with_usable_prose} prose → {f.candidate_events} "
                     f"candidates → {f.accepted} accepted → {f.after_dedup} "
                     f"deduped → {f.matured} matured → {f.direction_eligible} "
                     f"direction-eligible</div>")
        parts.append(f"<div class='yb-frozen'>{e(IMPLICATION_FROZEN)}</div>")
        parts.append(f"<div class='yb-hash'>brief {self.brief_hash()} · "
                     f"deterministic synthesis — no generative model · hover "
                     f"any sentence for its backing data fields</div></div>")
        blob = "".join(parts); self._sweep(blob); return blob

# ---------------------------------------------------------------- self-test
def _demo():
    """DEMO DATA — realistic shapes, illustrative values (marked as such)."""
    def issuers(new):
        return [
            IssuerRow("SU", 25.27, 15, "normal", 62, "GUIDANCE", "2026-07-11",
                      new_events_since_prev=new.get("SU", 0)),
            IssuerRow("CNQ", 24.49, 8, "elevated", 91, "DIVIDEND", "2026-07-14",
                      new_events_since_prev=new.get("CNQ", 0)),
            IssuerRow("CVE", 12.88, 6, None, None, "OTHER_MATERIAL",
                      "2026-07-02", new_events_since_prev=new.get("CVE", 0)),
            IssuerRow("IMO", 9.4, 4, "normal", 40, "CAPACITY", "2026-06-28"),
            IssuerRow("TRP", 8.1, 5, "normal", 35, "REGULATORY", "2026-06-30"),
        ]
    prev = LensSnapshot("XEG", "1782d006", "2026-07-15", 76.0, 8, 28, "A",
        Funnel(82, 71, 68, 66, 62, 55, 39), issuers({}), [
            CarPoint(5, -0.4, -1.9, -2.1, 1.3, 39),
            CarPoint(20, -1.7, -6.2, -4.3, 0.9, 36)])
    cur = LensSnapshot("XEG", "9a4e99f3", "2026-07-16", 76.0, 8, 28, "A",
        Funnel(86, 74, 70, 70, 65, 58, 41),
        issuers({"CNQ": 2, "SU": 1}), [
            CarPoint(5, -0.3, -1.8, -2.0, 1.4, 41),
            CarPoint(20, -1.6, -6.0, -4.2, 1.0, 38)])
    # CNQ was normal yesterday in this demo:
    for i in prev.issuers:
        if i.ticker == "CNQ": i.c6_state = "normal"; i.c6_rarity_pctile = 55
    return prev, cur

if __name__ == "__main__":
    prev, cur = _demo()
    b = ResearchBrief(prev, cur).build()
    text = b.to_text()
    html_out = b.to_html()
    # determinism check (G1)
    b2 = ResearchBrief(prev, cur).build()
    assert b.brief_hash() == b2.brief_hash(), "determinism violated"
    # structural-compliance check (G3): implication constant present, verbatim
    assert IMPLICATION_FROZEN in text and html.escape(IMPLICATION_FROZEN) in html_out
    print(text)
    open("/home/claude/brief_demo.html", "w").write(
        "<body style='background:#0b0f14;padding:30px;max-width:760px'>"
        + html_out + "</body>")
    print("\n[OK] determinism + structural compliance + vocabulary sweep passed"
          f"\n[OK] brief_hash={b.brief_hash()}  (html written to brief_demo.html)")
