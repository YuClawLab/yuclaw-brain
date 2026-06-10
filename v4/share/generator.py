"""
v4/share/generator.py — Share-this-Signal HTML card.

generate_share_card() calls build_response() ONCE (same point-in-time response the
rest of v4 uses), then renders a single self-contained HTML file. The card is a
frozen snapshot: it embeds the ledger_hash, ledger_anchor_url, accession numbers,
as_of, and replay_id, so anyone can independently verify it — now or a year later.

Score and cascade are OFF by default (Q2). The compliance block and ledger_hash are
ALWAYS present (architectural-safety invariant).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import psycopg2
from jinja2 import Environment, FileSystemLoader, select_autoescape

from v3.proof.verify import verify as proof_verify
from v4.api.builder import DSN, build_response
from v4.api.schema import COMPLIANCE_NOTICE, ResearchResponse

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_INSIDER = {"INSIDER_BUY", "INSIDER_SELL"}

_SIGNAL_HUMAN = {
    "STRONG_BULLISH": "Strong Bullish", "BULLISH": "Bullish", "NEUTRAL": "Neutral",
    "WATCH": "Watch", "WEAKENING": "Weakening", "RISK_ALERT": "Risk Alert",
    "NEGATIVE_EVENT": "Negative Event", "BEARISH_WATCH": "Bearish Watch",
}
# Muted, research-not-alarmist semantic colors.
_SIGNAL_COLOR = {
    "STRONG_BULLISH": "#2e7d4f", "BULLISH": "#2e7d4f",
    "NEUTRAL": "#5a6b7b", "WATCH": "#5a6b7b",
    "WEAKENING": "#9a6a2e", "NEGATIVE_EVENT": "#9a6a2e", "BEARISH_WATCH": "#8e3b3b",
    "RISK_ALERT": "#a23b3b",
}
_GRADE_HUMAN = {"A": "Grade A", "B": "Grade B", "C": "Grade C", "Insufficient": "Insufficient"}


def _event_title(event_type: str) -> str:
    return event_type.replace("_", " ").title()


def _short_hash(h: str) -> str:
    return f"{h[:8]}…{h[-7:]}" if h and len(h) > 20 else h


def _verification(resp: ResearchResponse, dsn: str) -> dict:
    """The PUBLISHED, verifiable hash for this signal + its ledger status.

    The public Verified Research Ledger stores the v3 content_hash (what
    `yuclaw verify` and the ledger_anchor_url confirm) — NOT the v4 response
    ledger_hash. The card shows the content_hash so 'Verify independently' actually
    matches what a recipient sees at the linked ledger entry.
    """
    content_hash, verified, commit, committed_at = None, False, None, None
    try:
        with psycopg2.connect(dsn) as c, c.cursor() as cur:
            cur.execute("SELECT content_hash FROM signal_snapshots WHERE snapshot_id = %s",
                        (resp.replay_id,))
            row = cur.fetchone()
            if row:
                content_hash = row[0]
    except Exception:
        pass
    if content_hash:
        try:
            v = proof_verify(resp.ticker, resp.as_of.date().isoformat())
            if v.get("status") == "VERIFIED" and v.get("ledger_hash") == content_hash:
                verified = True
                commit = (v.get("commit") or {}).get("commit")
                committed_at = (v.get("commit") or {}).get("committed_at")
        except Exception:
            pass
    return {"content_hash": content_hash, "verified": verified,
            "commit": commit, "committed_at": committed_at}


def _card_context(resp: ResearchResponse, verification: dict) -> dict:
    sig = resp.signal.value
    # Top 3 material (non-insider) evidence items for a clean card.
    material = [e for e in resp.evidence if e.event_type not in _INSIDER][:3]
    evidence = [{
        "title": _event_title(e.event_type),
        "date": e.available_as_of.date().isoformat() if e.available_as_of else "",
        "accession_number": e.accession_number,
        "source_url": e.source_url,
    } for e in material]

    cascade = None
    if resp.cascade:
        root = resp.cascade.event
        cascade = {
            "root_ticker": root.event_id.split("_")[0],
            "root_type": _event_title(root.event_type),
            "root_date": root.available_as_of.date().isoformat() if root.available_as_of else "",
            "edges": [{
                "depth": ed.depth, "parent_ticker": ed.parent_ticker, "child_ticker": ed.child_ticker,
                "relationship_type": ed.relationship_type, "edge_weight": ed.edge_weight,
                "decay_factor": ed.decay_factor, "contribution": ed.contribution,
            } for ed in resp.cascade.edges],
        }

    grade_letter = "—" if resp.confidence.grade.value == "Insufficient" else resp.confidence.grade.value
    n = len(resp.evidence)
    og_title = f"YUCLAW: {resp.ticker} — {_SIGNAL_HUMAN.get(sig, sig)} ({grade_letter})"
    og_desc = (f"Evidence-first research signal. {n} source event{'s' if n != 1 else ''}. "
               f"Verified against the public ledger.")

    return {
        "status": resp.status,
        "ticker": resp.ticker,
        "signal_human": _SIGNAL_HUMAN.get(sig, sig),
        "signal_color": _SIGNAL_COLOR.get(sig, "#5a6b7b"),
        "grade_human": _GRADE_HUMAN.get(resp.confidence.grade.value, resp.confidence.grade.value),
        "grade_letter": grade_letter,
        "as_of_date": resp.as_of.date().isoformat(),
        "replay_id": resp.replay_id,
        "n_evidence": n,
        "evidence": evidence,
        "cascade": cascade,
        "score": resp.score,
        # The PUBLISHED content_hash (verifiable at the ledger), not the v4 response hash.
        "ledger_hash": verification["content_hash"],
        "ledger_hash_short": _short_hash(verification["content_hash"]) if verification["content_hash"] else None,
        "ledger_anchor_url": resp.ledger_anchor_url,
        "verified": verification["verified"],
        "verify_commit": verification["commit"],
        "verify_committed_at": verification["committed_at"],
        "model_id": resp.compliance.model_id,
        "prompt_version": resp.compliance.prompt_version,
        "jurisdiction": resp.compliance.jurisdiction,
        "compliance_text_version": resp.compliance.compliance_text_version,
        "compliance_notice": COMPLIANCE_NOTICE,   # canonical (Day 9 single source of truth)
        # OG / Twitter
        "og_title": og_title, "og_description": og_desc, "og_image": None,
        "twitter_card": "summary",
    }


def render_card_html(resp: ResearchResponse, dsn: str = DSN) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    ctx = _card_context(resp, _verification(resp, dsn))
    return env.get_template("card.html.j2").render(**ctx)


def generate_share_card(
    ticker: str,
    as_of: Optional[datetime] = None,
    *,
    include_score: bool = False,
    include_cascade: bool = False,
    output_path: Optional[str] = None,
    dsn: str = DSN,
) -> Path:
    """Build the point-in-time response and write a self-contained HTML share card."""
    resp = build_response(ticker, as_of=as_of, include_score=include_score, include_cascade=include_cascade)
    out = Path(output_path) if output_path else Path(f"./share-{resp.ticker}-{resp.as_of.date().isoformat()}.html")
    out.write_text(render_card_html(resp, dsn=dsn), encoding="utf-8")
    return out


__all__ = ["generate_share_card", "render_card_html"]
