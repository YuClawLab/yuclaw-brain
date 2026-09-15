"""Excerpt quality (QA-05, 2026-09-15): shared detector rules, display finalization and the forward gate.

An explanatory excerpt must carry the event: prose from the filing, entity-decoded, ending at a clause/sentence
boundary — never a bare HTML entity fragment ("... the &") and never XBRL context/taxonomy tokens instead of
event-bearing prose. The rules here are used identically by (a) the bounded corpus scan (tools/yuclaw_excerpt_scan.py),
(b) the display finalizer for CURRENT pages (entity decoding + boundary trim — a presentation change only), and
(c) the forward extraction gate R9 in sourcelock (a runtime/methodology-input change: OFF by default —
YUCLAW_EXCERPT_QUALITY_GATE=record|reject — activated only through the applicable registration/activation step).
A detector hit is SUSPECTED until a correction is verified against the primary document."""
from __future__ import annotations

import html as _html
import os
import re

RULES = {
    "entity_fragment_end": re.compile(r"(&|&amp;|&#\d*|&[a-zA-Z]{1,6})\s*$"),
    "entity_inside": re.compile(r"&(amp|nbsp|quot|apos|lt|gt|#\d+|#x[0-9a-fA-F]+|[a-z]{2,6});"),
    "xbrl_context": re.compile(r"\b(us-gaap|dei|ifrs-full|srt|xbrli|ix|iso4217|country|stpr)[:_](?=[A-Za-z])|\bcontextRef\b|\bunitRef\b"),
    "taxonomy_url": re.compile(r"https?://(fasb\.org|xbrl\.sec\.gov|www\.xbrl\.org|xbrl\.fasb\.org)"),
    "context_id_soup": re.compile(r"\b\d{10}\b.*\b(Member|Axis|Domain)\b|\b(Member|Axis|Domain)\b.*\b\d{4}-\d{2}-\d{2}\b.*\b\d{4}-\d{2}-\d{2}\b"),
    "zero_width": re.compile(r"[​‌‍﻿]"),
    "operator_tail": re.compile(r"[\(\$@,;:/-]\s*$"),
}
EVENT_PROSE_RULES = ("xbrl_context", "taxonomy_url", "context_id_soup")
GATE_ENV = "YUCLAW_EXCERPT_QUALITY_GATE"


def assess(excerpt: str) -> list[str]:
    """Rule ids that fire on the excerpt (empty = clean under these rules; not a proof of quality)."""
    t = excerpt or ""
    return [r for r, rx in RULES.items() if rx.search(t)]


def is_event_bearing(excerpt: str) -> bool:
    """False when the excerpt is context/taxonomy data rather than prose (XBRL rules) or has no alphabetic sentence."""
    if any(r in EVENT_PROSE_RULES for r in assess(excerpt)):
        return False
    letters = sum(c.isalpha() for c in excerpt or "")
    return letters >= 20 and letters / max(len(excerpt or ""), 1) >= 0.45


def finalize_display(excerpt: str) -> str:
    """Presentation-only finalization: decode entities, drop zero-width chars, collapse whitespace, and trim a
    dangling entity/operator tail back to the last clause boundary. Never adds text; never changes stored bytes."""
    t = _html.unescape(excerpt or "")
    t = RULES["zero_width"].sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    for _ in range(3):
        if RULES["entity_fragment_end"].search(t) or RULES["operator_tail"].search(t):
            cut = max(t.rfind("."), t.rfind(";"), t.rfind(")"), t.rfind(","))
            t = (t[:cut + 1] if cut > 20 else t.rsplit(" ", 1)[0]).rstrip(" &($/@-")
        else:
            break
    return t


_IX_DATA_BLOCKS_RE = re.compile(r"<ix:hidden\b.*?</ix:hidden>|<xbrli:context\b.*?</xbrli:context>|<xbrli:unit\b.*?</xbrli:unit>|<ix:resources\b.*?</ix:resources>", re.I | re.S)


def strip_ix_data_blocks(raw_html: str) -> str:
    """Forward repair candidate (QA-05 E5): remove iXBRL context/unit/hidden/resources blocks — the source of
    context-token soup outside <ix:header> — before prose extraction. NOT wired into the paired live-ingestion
    modules (v3/extract/narrative.py and its v5 twin must stay byte-consistent); wiring both copies is the
    registered activation step for this methodology-input change."""
    return _IX_DATA_BLOCKS_RE.sub(" ", raw_html or "")


def gate_mode() -> str:
    m = os.environ.get(GATE_ENV, "off").strip().lower()
    return m if m in ("off", "record", "reject") else "off"


def gate(excerpt: str) -> tuple[bool, str | None]:
    """Forward gate R9 for sourcelock: (accept, reason). OFF → always accept; RECORD → accept but report;
    REJECT → refuse non-event-bearing or fragment excerpts."""
    hits = assess(excerpt)
    bad = [h for h in hits if h in EVENT_PROSE_RULES or h == "entity_fragment_end"]
    if not bad:
        return True, None
    mode = gate_mode()
    if mode == "reject":
        return False, "R9_excerpt_quality:" + ",".join(bad)
    return True, ("R9_excerpt_quality_recorded:" + ",".join(bad)) if mode == "record" else None
