"""Excerpt correction annotations — store, projection and display (QA-05 E2/E3).

Store: registry/excerpt_corrections.jsonl (append-only; one ExcerptCorrection.v1 record per line). Public projection:
docs/evidence/excerpt_corrections.json. Originals are never edited; the original source_hash authenticates the
original bytes only; corrected text carries its own digest; availability of the original is never backdated and
historical labels/scores/features/eligibility/replay inputs are untouched (annotations are a separate validation
domain from root membership/replay)."""
from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
STORE = _REPO / "registry" / "excerpt_corrections.jsonl"
PUBLIC = _REPO / "docs" / "evidence" / "excerpt_corrections.json"


def load() -> list[dict]:
    if not STORE.exists():
        return []
    return [json.loads(l) for l in STORE.read_text().splitlines() if l.strip()]


def by_hash() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in load():
        out.setdefault(r["original"]["source_hash"], []).append(r)
    return out


def annotations_for(objects: list[dict]) -> list[dict]:
    idx = by_hash()
    return [dict(r) for o in objects for r in idx.get(o.get("source_hash"), [])]


def public_projection(out: Path = PUBLIC, stamp: str | None = None) -> int:
    rows = load()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"schema": "ExcerptCorrection.v1", "generated": stamp, "count": len(rows),
                               "policy": "originals retained and hash-authenticated; corrected display text has its own digest and date; a quality flag is SUSPECTED until verified against the primary document; nothing here changes historical labels, scores, features, eligibility or replay inputs",
                               "records": rows}, indent=1) + "\n")
    return len(rows)


def card_html(ticker: str) -> str:
    rows = [r for r in load() if r["original"]["ticker"] == ticker]
    if not rows:
        return ""
    items = []
    for r in rows:
        if r["kind"] == "display_correction" and r["status"] == "CORRECTED":
            items.append(f'<li><span class="k">CORRECTED display excerpt</span> ({escape(r["corrected_at"] or "")}; rules {escape(",".join(r["rule_ids"]))}) — original retained (hash {escape(r["original"]["source_hash"][:12])}…): '
                         f'<em class="excerpt-quote">{escape(r["corrected_excerpt"] or "")}</em> <span class="muted">(corrected-text digest {escape((r["corrected_sha256"] or "")[:12])}…; verified against {escape((r.get("source_location") or {}).get("verified_against") or "primary document")})</span></li>')
        else:
            items.append(f'<li><span class="k">FLAGGED ({escape(r["status"])})</span> excerpt {escape(r["original"]["source_hash"][:12])}… — {escape(r["reason"])} (rules {escape(",".join(r["rule_ids"]))}); original shown unchanged, not yet a correction</li>')
    return ('<div class="card"><h2>Excerpt corrections and quality flags</h2><p class="muted" style="font-size:12.5px">Original excerpts and their hashes are never edited; '
            'a corrected display excerpt is a separate annotation with its own digest and date. Detector hits stay SUSPECTED until verified against the primary document.</p>'
            f'<ul style="font-size:13px;line-height:1.7">{"".join(items)}</ul></div>')
