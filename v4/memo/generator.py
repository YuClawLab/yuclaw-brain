"""
v4/memo/generator.py — Memo Generator on the locked v4 schema.

generate_memo() calls build_response() ONCE and renders a Markdown research memo
from that single ResearchResponse — no second queries, the schema is the source
of truth. Three modes, chosen from the response:

  full              — status='ok' and grade A/B/C: the standard memo.
  evidence_limited  — status='ok' and grade Insufficient: shorter, conservative
                      "evidence-limited research note" with prominent caveats (Q5/ChatGPT review).
  no_data           — status='no_data': an honest "no research available" note.

RISK_ALERT signals lead with the `overlay_trigger` event as the headline (Q3).
Q2: with include_score=False (default for the memo's score-off behavior), the memo
uses qualitative language and never prints the raw composite score.

Architectural-safety: read-only via build_response; surfaces only already-public
fields (raw_excerpt is the SourceLock-verified text; component internals are not exposed).
"""
from __future__ import annotations

import html
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from v4.api.builder import DSN, build_response
from v4.api.schema import (
    Component,
    EvidenceGrade,
    Evidence,
    ResearchResponse,
    SignalLabel,
)

MEMO_N_EVIDENCE = 20   # Q2: memos request 20 (builder default is 10), capped at 50.
MEMO_N_EVIDENCE_MAX = 50


class MemoOutput(BaseModel):
    ticker: str
    as_of: datetime
    signal: SignalLabel
    grade: EvidenceGrade
    mode: str = Field(..., description="full | evidence_limited | no_data")
    markdown: str
    response: ResearchResponse


# --------------------------------------------------------------------------- #
# language helpers
# --------------------------------------------------------------------------- #
_SIGNAL_HUMAN = {
    "STRONG_BULLISH": "Strong Bullish", "BULLISH": "Bullish", "NEUTRAL": "Neutral",
    "WATCH": "Watch", "WEAKENING": "Weakening", "RISK_ALERT": "Risk Alert",
    "NEGATIVE_EVENT": "Negative Event", "BEARISH_WATCH": "Bearish Watch",
}
_GRADE_HUMAN = {
    "A": "Grade A (strong, corroborated evidence)",
    "B": "Grade B (adequate evidence)",
    "C": "Grade C (thin / single-source evidence)",
    "Insufficient": "Insufficient (not enough evidence to stand behind)",
}


def _signal_human(s: SignalLabel) -> str:
    return _SIGNAL_HUMAN.get(s.value, s.value)


def _qual(score: float) -> str:
    if score >= 0.5: return "strongly positive"
    if score >= 0.2: return "positive"
    if score > -0.2: return "roughly neutral"
    if score > -0.5: return "negative"
    return "strongly negative"


def _event_human(event_type: str) -> str:
    return event_type.replace("_", " ").title()


def _short(h: str, n: int = 12) -> str:
    return (h or "")[:n]


def _clean_excerpt(s: Optional[str]) -> str:
    """Decode HTML entities (e.g. &#160;, &#8220;) for human-readable display.

    Display-only: SourceLock R7 already verified the stored excerpt upstream; this
    does not change what was verified, only how the verified text is shown.
    """
    return html.unescape(s).strip() if s else ""


_INSIDER = {"INSIDER_BUY", "INSIDER_SELL"}


# --------------------------------------------------------------------------- #
# section renderers
# --------------------------------------------------------------------------- #
def _render_evidence_item(i: int, e: Evidence) -> str:
    line = f"{i}. **{_event_human(e.event_type)}**"
    if e.available_as_of:
        line += f" — {e.available_as_of.date().isoformat()}"
    ex = _clean_excerpt(e.raw_excerpt)
    if ex:
        line += f"\n   > {ex}"
    prov = f"[source]({e.source_url})"
    if e.accession_number:
        prov += f" · accession `{e.accession_number}`"
    prov += f" · ledger `{_short(e.ledger_hash)}…`"
    line += f"\n   {prov}"
    return line


def _render_evidence_trail(evidence: list[Evidence]) -> str:
    """Material events numbered in full; insider Form-4 events collapsed to one rollup."""
    material = [e for e in evidence if e.event_type not in _INSIDER]
    insider = [e for e in evidence if e.event_type in _INSIDER]
    if not material and not insider:
        return "_No qualifying source events in window._"
    lines = [_render_evidence_item(i + 1, e) for i, e in enumerate(material)]
    if insider:
        recent = max(insider, key=lambda e: e.available_as_of)
        snippet = _clean_excerpt(recent.raw_excerpt)
        snippet = (snippet[:90] + "…") if len(snippet) > 90 else snippet
        lines.append(
            f"{len(material) + 1}. **Insider activity (Form 4)** — {len(insider)} transaction(s) in window; "
            f"capped contribution to C6 Event Impact (not a standalone signal). "
            f"Most recent: {snippet} ([source]({recent.source_url}))"
        )
    return "\n\n".join(lines)


def _render_anatomy(components: list[Component], include_score: bool, brief: bool) -> str:
    # Order by contribution magnitude (|score|·weight); show implemented first.
    impl = [c for c in components if c.implemented]
    stubs = [c for c in components if not c.implemented]
    impl.sort(key=lambda c: abs(c.score) * c.weight, reverse=True)
    lines: list[str] = []
    shown = impl[:4] if brief else impl
    for c in shown:
        head = f"- **{c.name} ({c.key.upper()})** — {_qual(c.score)}"
        if include_score:
            head += f" (score {c.score:+.2f}, confidence {c.confidence:.2f}, weight {c.weight:.2f})"
        if c.rationale:
            head += f". {c.rationale}"
        lines.append(head)
    if brief and len(impl) > 4:
        lines.append(f"- _…and {len(impl) - 4} more components._")
    for c in stubs:
        lines.append(f"- **{c.name} ({c.key.upper()})** — _not yet implemented._")
    return "\n".join(lines)


def _render_compliance(resp: ResearchResponse) -> str:
    c = resp.compliance
    return (f"_{c.notice}_\n\n"
            f"Jurisdiction: {c.jurisdiction} · Extraction: `{c.model_id}` / prompt `{c.prompt_version}` · "
            f"Compliance text version: `{c.compliance_text_version}`.")


def _provenance_footer(resp: ResearchResponse) -> str:
    anchor = f" · [ledger entry]({resp.ledger_anchor_url})" if resp.ledger_anchor_url else ""
    return (f"Point-in-time as of **{resp.as_of.isoformat()}** · replay_id `{resp.replay_id}` · "
            f"ledger_hash `{_short(resp.ledger_hash, 16)}…`{anchor}")


# --------------------------------------------------------------------------- #
# mode renderers
# --------------------------------------------------------------------------- #
def _render_no_data(resp: ResearchResponse) -> str:
    return (
        f"# {resp.ticker} — No Research Available\n\n"
        f"{resp.limitations[0]}\n\n"
        f"There is no signal to report for this ticker at the requested time. This is an "
        f"honest empty state, not a hidden or suppressed result.\n\n"
        f"---\n\n## Compliance Notice\n\n{_render_compliance(resp)}\n"
    )


def _render_risk_alert(resp: ResearchResponse, include_score: bool) -> str:
    t = resp.overlay_trigger
    head = f"# ⚠️ {resp.ticker} — Risk Alert\n\n"
    if t:
        head += (f"**Headline event — {_event_human(t.event_type)}"
                 f"{(' (' + t.available_as_of.date().isoformat() + ')') if t.available_as_of else ''}:**\n\n")
        if t.raw_excerpt:
            head += f"> {_clean_excerpt(t.raw_excerpt)}\n\n"
        prov = f"[source]({t.source_url})"
        if t.accession_number:
            prov += f" · accession `{t.accession_number}`"
        head += prov + "\n\n"
    head += (f"This research signal is flagged **RISK ALERT** ({resp.signal_overlay}). The risk overlay "
             f"intentionally overrides the underlying composite classification because a material "
             f"regulatory or legal event was detected in the trailing window.\n\n")
    body = (
        f"**Evidence Quality:** {_GRADE_HUMAN[resp.confidence.grade.value]}\n\n"
        f"## Signal Anatomy\n\n{_render_anatomy(resp.components, include_score, brief=False)}\n\n"
        f"## Evidence Trail\n\n{_render_evidence_trail(resp.evidence)}\n"
        + "\n\n## Limitations\n\n" + "\n".join(f"- {l}" for l in resp.limitations)
        + f"\n\n---\n\n{_provenance_footer(resp)}\n\n## Compliance Notice\n\n{_render_compliance(resp)}\n"
    )
    return head + body


def _render_evidence_limited(resp: ResearchResponse, include_score: bool) -> str:
    n = len(resp.evidence)
    return (
        f"# {resp.ticker} — Evidence-Limited Research Note\n\n"
        f"> ⚠️ **Limited evidence.** This note rests on **{n} source "
        f"event{'s' if n != 1 else ''}** (Evidence {_GRADE_HUMAN[resp.confidence.grade.value]}). "
        f"It is preliminary; treat the classification below as low-conviction and subject to change "
        f"as more filings arrive.\n\n"
        f"**Working classification:** {_signal_human(resp.signal)}"
        + (f" — composite score {resp.score:+.3f}" if include_score and resp.score is not None else "")
        + "\n\n"
        f"## What little we have\n\n{_render_evidence_trail(resp.evidence)}\n"
        + "\n\n## Signal Anatomy (partial)\n\n"
        + _render_anatomy(resp.components, include_score, brief=True)
        + "\n\n## Limitations\n\n" + "\n".join(f"- {l}" for l in resp.limitations)
        + f"\n\n---\n\n{_provenance_footer(resp)}\n\n## Compliance Notice\n\n{_render_compliance(resp)}\n"
    )


def _synthesis(resp: ResearchResponse) -> str:
    impl = [c for c in resp.components if c.implemented and abs(c.score) > 1e-9]
    n = len(resp.evidence)
    grade = _GRADE_HUMAN[resp.confidence.grade.value].split(" (")[0]
    base = (f"{resp.ticker}'s research signal is **{_signal_human(resp.signal)}** on {grade} evidence "
            f"({n} corroborating source event{'s' if n != 1 else ''}).")
    if not impl:
        return base
    pos = sorted([c for c in impl if c.score > 0], key=lambda c: c.score * c.weight, reverse=True)
    neg = sorted([c for c in impl if c.score < 0], key=lambda c: c.score * c.weight)
    if pos and neg:
        base += (f" The picture is mixed: **{pos[0].name}** is {_qual(pos[0].score)}, "
                 f"offset by **{neg[0].name}** ({_qual(neg[0].score)}) — which is why the composite "
                 f"lands at {_signal_human(resp.signal).lower()} rather than directional.")
    elif pos:
        base += f" The constructive read is led by **{pos[0].name}** ({_qual(pos[0].score)})."
    else:
        base += f" The cautious read is led by **{neg[0].name}** ({_qual(neg[0].score)})."
    return base


def _render_full(resp: ResearchResponse, include_score: bool) -> str:
    head = (
        f"# {resp.ticker} — {_signal_human(resp.signal)}\n\n"
        f"**Evidence Quality:** {_GRADE_HUMAN[resp.confidence.grade.value]}"
        + (f" · **Composite score:** {resp.score:+.3f}" if include_score and resp.score is not None else "")
        + "\n\n"
        f"{_synthesis(resp)}\n\n"
    )
    body = (
        f"## Signal Anatomy\n\n{_render_anatomy(resp.components, include_score, brief=False)}\n\n"
        f"## Evidence Trail\n\n{_render_evidence_trail(resp.evidence)}\n"
        + "\n\n## Limitations\n\n" + "\n".join(f"- {l}" for l in resp.limitations)
        + f"\n\n---\n\n{_provenance_footer(resp)}\n\n## Compliance Notice\n\n{_render_compliance(resp)}\n"
    )
    return head + body


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def generate_memo(
    ticker: str,
    as_of: Optional[datetime] = None,
    *,
    include_score: bool = False,
    n_evidence: int = MEMO_N_EVIDENCE,
    dsn: str = DSN,
) -> MemoOutput:
    """Build the ResearchResponse once and render a Markdown research memo from it."""
    n = max(1, min(n_evidence, MEMO_N_EVIDENCE_MAX))
    resp = build_response(ticker, as_of=as_of, include_score=include_score, n_evidence=n, dsn=dsn)

    if resp.status == "no_data":
        mode, md = "no_data", _render_no_data(resp)
    elif resp.signal == SignalLabel.RISK_ALERT:
        mode, md = "full", _render_risk_alert(resp, include_score)
    elif resp.confidence.grade == EvidenceGrade.INSUFFICIENT:
        mode, md = "evidence_limited", _render_evidence_limited(resp, include_score)
    else:
        mode, md = "full", _render_full(resp, include_score)

    return MemoOutput(
        ticker=resp.ticker, as_of=resp.as_of, signal=resp.signal,
        grade=resp.confidence.grade, mode=mode, markdown=md, response=resp,
    )


__all__ = ["generate_memo", "MemoOutput", "MEMO_N_EVIDENCE"]
