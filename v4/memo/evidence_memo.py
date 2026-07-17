"""
Evidence Memo (MVP) — analyst work product over the filings-evidence stream
(usefulness build, 2026-07-16). A PRODUCT feature.

    yuclaw memo --ticker SU [--days 30]

Fixed sections, in order:
  1. Research question   — "What changed in <name>'s filings evidence over the
                            last N days?"
  2. Evidence table      — deterministic, straight from the DB: date, form,
                            exhibit, event type, verified quote, grade,
                            C6 posture, SourceLock status.
  3. Change narrative    — LLM-written, BUT every sentence must carry an
                            event-ID citation; the grounding verifier runs
                            over the memo itself and any uncited claim or
                            unverifiable number FAILS the generation.
  4. Risk-gate note      — whether C6 fired, plus the approved C6 sentence
                            VERBATIM.
  5. Event-study context — matured similar events; CAR labeled supportive /
                            adverse / underpowered as measured.
  6. Honest conclusion   — deterministic, restricted to the locked memo
                            vocabulary (LOCKED_CONCLUSIONS below).

Programmatic lint (tools/check_language.py) runs on every memo's authored
prose — banned words fail generation. Mandatory research-only footer.

GPU discipline: the single LLM call (change narrative) is guarded by
services/gpu-lock (acquire yuclaw → generate → release). On-demand ONLY —
no bulk nightly generation exists or may be added.

Form-4 display enrichment (events.attributes: insider_role, plan_10b5_1) and
same-issuer cluster context appear in the evidence table only. C6's
consumption of insider events is untouched (frozen).
"""
from __future__ import annotations

import html
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import psycopg2

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from tools.check_language import check_research_footer, lint_text  # noqa: E402

DSN = "dbname=yuclaw_events"
GPU_LOCK = _REPO / "services" / "gpu-lock"
C6_DIR = _REPO / "output" / "swarm" / "canada"
OLLAMA_URL = os.environ.get("YUCLAW_V5_OLLAMA_URL", "http://localhost:11434")
MEMO_MODEL = os.environ.get("YUCLAW_MEMO_MODEL", "llama3.1:8b")
GPU_WAIT_SECONDS = int(os.environ.get("YUCLAW_MEMO_GPU_WAIT", "180"))

# The approved C6 sentence — VERBATIM wherever C6 status appears.
from v3.web.useful_blocks import C6_APPROVED_SENTENCE  # noqa: E402

# The locked memo-conclusion vocabulary. The conclusion section may use ONLY
# these phrases (plus counts); it is assembled deterministically, never by
# the LLM. This list is the canonical registry.
LOCKED_CONCLUSIONS = (
    "evidence posture improved",
    "evidence posture weakened",
    "risk-gate elevated",
    "insufficient matured evidence",
    "outside current evidence scope",
    "not statistically proven",
    "underpowered",
)

RESEARCH_FOOTER = (
    "---\n\n*Research and education use only. Not investment advice. Event types, "
    "grades, and postures are research classifications, not recommendations. "
    "Every quoted span is SourceLock-verified against the primary SEC filing.*"
)

_CITE_RE = re.compile(r"\[([A-Za-z0-9_.-]+)\]")
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
# Don't split on abbreviations ("Inc.", "p.m.", "U.S." — any dot-letter-dot
# tail), and don't split between a terminal period and a citation bracket
# ("... 2026. [SU_...]") — both orphan a real sentence from its citation and
# spuriously fail the grounding verifier.
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])(?<!Inc\.)(?<!\.[A-Za-z]\.)\s+(?!\[)")


class MemoGenerationError(RuntimeError):
    """Any lint/grounding/citation failure — the memo is NOT produced."""


# --------------------------------------------------------------------------- #
# grounding verifier (the v5 verifier, loaded by file path — pure stdlib)
# --------------------------------------------------------------------------- #
def _load_grounding():
    path = Path("/home/zhangd2/yuclaw-v5/yuclaw/v5/swarm/grounding.py")
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("v5_grounding", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_GROUNDING = _load_grounding()


def _numbers_verified(sentence: str, corpus: str) -> tuple[bool, list[str]]:
    """Every number in the (citation-stripped) sentence must appear in the
    cited events' verification corpus. Uses the v5 verifier when available."""
    text = _CITE_RE.sub("", sentence)
    if _GROUNDING is not None:
        ok, report = _GROUNDING.verify_numbers(text, [corpus])
        missing = [r["token"] for r in report
                   if isinstance(r, dict) and not r.get("found")]
        return ok, missing
    corpus_norm = corpus.replace(",", "")
    missing = [n for n in _NUM_RE.findall(text)
               if n.replace(",", "") not in corpus_norm]
    return not missing, missing


# --------------------------------------------------------------------------- #
# evidence gathering (deterministic)
# --------------------------------------------------------------------------- #
def _issuer_name(cur, ticker: str) -> str:
    from v3.universe_tiers import evidence_tier_records
    for r in evidence_tier_records():
        if r["ticker"] == ticker:
            return r.get("sec_name", ticker).title()
    return ticker


def _accession_for(cur, source_url: str, event_id: str) -> str | None:
    m = re.search(r"_F4_(\d{18})_", event_id)
    if m:
        a = m.group(1)
        return f"{a[:10]}-{a[10:12]}-{a[12:]}"
    cur.execute("SELECT accession_number FROM events_raw WHERE source_url=%s", (source_url,))
    r = cur.fetchone()
    if r and r[0]:
        return r[0]
    m = re.search(r"/(\d{18})/", source_url)
    if m:
        a = m.group(1)
        return f"{a[:10]}-{a[10:12]}-{a[12:]}"
    return None


def _exhibits_for(cur, accession: str | None) -> str:
    if not accession:
        return "—"
    cur.execute("""SELECT narrative_section FROM yuclaw_v5.swarm_inputs
                   WHERE accession_number=%s ORDER BY 1""", (accession,))
    rows = [r[0] for r in cur.fetchall()]
    return ", ".join(rows) if rows else "—"


def _c6_posture_for(accession: str | None) -> str:
    if not accession:
        return "—"
    f = C6_DIR / f"{accession}.json"
    if not f.exists():
        return "—"
    try:
        rc = json.loads(f.read_text())["risk_channel"]
        return f"{rc['level']} / {rc['flag']}"
    except Exception:
        return "—"


def _ticker_grade(cur, ticker: str) -> str:
    """The same deterministic coverage-depth rule the evidence pages use
    (A: events+prose · B: filings+prose · C: filings only · D: none)."""
    cur.execute("""SELECT count(*) FROM events
                   WHERE ticker=%s AND event_status='accepted'""", (ticker,))
    n_events = cur.fetchone()[0]
    cur.execute("""SELECT count(*) FROM events_raw
                   WHERE ticker=%s AND extraction_status='done'""", (ticker,))
    n_filings = cur.fetchone()[0]
    cur.execute("""SELECT count(*) FROM yuclaw_v5.swarm_inputs si
                   JOIN events_raw er ON er.accession_number = si.accession_number
                   WHERE er.ticker=%s AND si.narrative_section <> 'raw_cover'""", (ticker,))
    n_prose = cur.fetchone()[0]
    if n_events and n_prose:
        return "A (events + prose evidence)"
    if n_filings and n_prose:
        return "B (prose evidence, no accepted events yet)"
    if n_filings:
        return "C (cover-only substrate so far)"
    return "D (no filings ingested yet)"


def _cluster_context(cur, ticker: str, since: datetime) -> dict:
    """Same-issuer insider cluster context — computed live for display only."""
    cur.execute("""
        SELECT count(*) FILTER (WHERE event_type='INSIDER_BUY'),
               count(*) FILTER (WHERE event_type='INSIDER_SELL'),
               count(DISTINCT attributes->>'insider_role') FILTER (WHERE attributes IS NOT NULL),
               count(*) FILTER (WHERE (attributes->>'plan_10b5_1')::boolean)
        FROM events
        WHERE ticker=%s AND event_status='accepted'
          AND event_type IN ('INSIDER_BUY','INSIDER_SELL')
          AND available_as_of >= %s""", (ticker, since))
    b, s, roles, planned = cur.fetchone()
    return {"buys": int(b), "sells": int(s), "distinct_roles": int(roles or 0),
            "plan_10b5_1": int(planned or 0)}


def gather_evidence(ticker: str, days: int, dsn: str = DSN) -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    with psycopg2.connect(dsn) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            grade = _ticker_grade(cur, ticker)
            name = _issuer_name(cur, ticker)
            cur.execute("""
                SELECT event_id, event_type, magnitude, direction, llm_confidence,
                       raw_excerpt, event_status, available_as_of, source_type,
                       source_url, attributes
                FROM events
                WHERE ticker=%s AND event_status='accepted'
                  AND available_as_of >= %s AND available_as_of <= %s
                ORDER BY available_as_of""", (ticker, since, now))
            rows = []
            for r in cur.fetchall():
                (eid, etype, mag, direction, conf, excerpt, status, aao,
                 form, url, attrs) = r
                acc = _accession_for(cur, url, eid)
                rows.append({
                    "event_id": eid, "type": etype, "magnitude": float(mag),
                    "direction": int(direction), "confidence": float(conf),
                    "quote": html.unescape(excerpt or "").strip(),
                    "status": status, "date": aao.date().isoformat(),
                    "form": form, "url": url, "accession": acc,
                    "exhibit": _exhibits_for(cur, acc),
                    "c6_posture": _c6_posture_for(acc),
                    "attributes": attrs or {},
                })
            cluster = _cluster_context(cur, ticker, since)
    return {"ticker": ticker, "name": name, "days": days, "since": since,
            "now": now, "grade": grade, "events": rows, "cluster": cluster}


# --------------------------------------------------------------------------- #
# LLM narrative under gpu-lock (on-demand only — never bulk)
# --------------------------------------------------------------------------- #
def _gpu_acquire() -> bool:
    deadline = time.time() + GPU_WAIT_SECONDS
    while time.time() < deadline:
        r = subprocess.run([str(GPU_LOCK), "acquire", "yuclaw"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return True
        time.sleep(5)
    return False


def _gpu_release() -> None:
    subprocess.run([str(GPU_LOCK), "release", "yuclaw"], capture_output=True)


def _ollama(prompt: str, model: str) -> str:
    r = httpx.post(f"{OLLAMA_URL}/api/generate",
                   json={"model": model, "prompt": prompt, "stream": False,
                         "options": {"temperature": 0.0, "num_predict": 500}},
                   timeout=600.0)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def _narrative_prompt(ev: dict, feedback: str = "") -> str:
    lines = [
        f"[{e['event_id']}] {e['date']} {e['form']} {e['type']} "
        f"direction={e['direction']:+d}: \"{e['quote']}\""
        for e in ev["events"]]
    return f"""You are writing the Change narrative section of a research memo about {ev['name']} ({ev['ticker']}).
Describe what changed in the company's SEC-filings evidence over the last {ev['days']} days, using ONLY the evidence items below.

STRICT RULES — the memo is machine-verified and rejected on any violation:
1. Write 2 to 5 plain-prose sentences. No headers, no bullets, no preamble.
2. EVERY sentence must end with one or more citations in square brackets, placed BEFORE the sentence's final period, e.g. "... on May 5, 2026 [{ev['events'][0]['event_id'] if ev['events'] else 'EVENT_ID'}]."
3. Cite only event IDs from the list below. Never invent an ID.
4. Every number you write must appear verbatim in the quoted text of an event you cite in that same sentence. If unsure, write the sentence without the number.
5. Describe filings evidence only. Never use these words: buy, sell, hold, undervalued, overvalued, top pick, alpha, opportunity, recommend, forecast, outperform, upside, price target. Never give advice or predictions.
6. Neutral research register: state what was filed and classified, nothing more.
7. If a quoted excerpt announces a FUTURE action ("will release", "plans to", "intends to"), describe it as an announcement — "announced it would release ..." — never as if the action already happened. The cited event is the announcement, not the occurrence. Keep the future action's date attached to the action ("announced it would release results on May 5, 2026"), never fronted as if it were the announcement date.
{feedback}
EVIDENCE ITEMS:
{chr(10).join(lines)}

Change narrative:"""


def _date_forms(iso: str) -> str:
    """Digit-core variants of an ISO date so prose dates ('May 5, 2026')
    verify against '2026-05-05' (the verifier compares exact digit cores)."""
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return f"{iso} {d.year} {d.month} {d.day}"
    except ValueError:
        return iso


_FUTURE_VERB_RE = re.compile(r"\bwill\s+([a-z]+)")
_FUTURE_VERB_SKIP = frozenset(("be", "not", "also", "no", "have", "continue", "remain"))


def _verify_narrative(narrative: str, ev: dict) -> list[str]:
    """The grounding verifier over the memo itself. Returns failure notes."""
    failures: list[str] = []
    by_id = {e["event_id"]: e for e in ev["events"]}
    sentences = [s.strip() for s in _SENT_SPLIT_RE.split(narrative.strip()) if s.strip()]
    if not sentences:
        return ["empty narrative"]
    for s in sentences:
        cites = _CITE_RE.findall(s)
        valid = [c for c in cites if c in by_id]
        if not valid:
            failures.append(f"uncited claim (no valid event-ID citation): \"{s[:110]}\"")
            continue
        if len(valid) < len(cites):
            bad = set(cites) - set(valid)
            failures.append(f"invented citation(s) {sorted(bad)} in: \"{s[:110]}\"")
        corpus = " ".join(
            f"{by_id[c]['quote']} {_date_forms(by_id[c]['date'])} {by_id[c]['type']}"
            for c in valid) + f" {ev['days']} {len(ev['events'])}"
        ok, missing = _numbers_verified(s, corpus)
        if not ok:
            failures.append(f"number(s) {missing} not found in cited quotes: \"{s[:110]}\"")
        # Announcement events must never be described as the occurrence itself:
        # a cited quote saying "will <verb>" may not back a sentence claiming
        # "<verb>ed" unless the sentence frames it as an announcement.
        if "announc" not in s.lower():
            for c in valid:
                for verb in _FUTURE_VERB_RE.findall(by_id[c]["quote"].lower()):
                    if verb in _FUTURE_VERB_SKIP:
                        continue
                    if re.search(rf"\b{re.escape(verb)}e?d\b", s.lower()):
                        failures.append(
                            f"announcement event {c} described as the occurrence — "
                            f"write \"announced it would {verb} ...\": \"{s[:110]}\"")
    return failures


def _generate_narrative(ev: dict, model: str) -> str:
    if not ev["events"]:
        return ("No accepted evidence events were recorded in the window; there is "
                "no change to narrate. (Deterministic empty-state text — no LLM call, "
                "no GPU use.)")
    if not _gpu_acquire():
        raise MemoGenerationError(
            f"GPU busy (gpu-lock held) after {GPU_WAIT_SECONDS}s — memo not generated. "
            "Re-run later; memos are on-demand only and never queue bulk work.")
    try:
        feedback = ""
        for attempt in (1, 2):
            narrative = _ollama(_narrative_prompt(ev, feedback), model)
            failures = _verify_narrative(narrative, ev)
            lint = lint_text(narrative, strip=False)
            failures += [f"banned word '{v['word']}' in: \"{v['line'][:90]}\"" for v in lint]
            if not failures:
                return narrative
            feedback = ("PREVIOUS ATTEMPT FAILED VERIFICATION — fix these and rewrite:\n- "
                        + "\n- ".join(failures[:8]) + "\n")
        raise MemoGenerationError(
            "Change narrative failed grounding/lint verification after 2 attempts:\n- "
            + "\n- ".join(failures[:10]))
    finally:
        _gpu_release()


# --------------------------------------------------------------------------- #
# deterministic sections
# --------------------------------------------------------------------------- #
def _n_filings(n: int) -> str:
    return f"{n} filing" + ("" if n == 1 else "s")


def _risk_gate_note(ev: dict) -> str:
    postures = [e["c6_posture"] for e in ev["events"] if e["c6_posture"] != "—"]
    fired = [p for p in postures if p.endswith("/ elevated")]
    if fired:
        state = (f"C6 posture flagged **elevated** on {_n_filings(len(fired))} in the window "
                 f"(risk display; never a directional signal).")
    elif postures:
        state = (f"C6 posture ran on {_n_filings(len(postures))} in the window; "
                 f"no elevated flag.")
    else:
        state = "No C6 posture artifact exists for filings in the window."
    return (f"{state}\n\nC6 out-of-sample status (approved wording): "
            f"{C6_APPROVED_SENTENCE}.")


def _event_study_context(ev: dict) -> str:
    """Matured similar events for the ticker's lens; CAR labeled as measured."""
    try:
        from v3.lab.etf_evidence import CANADA_LENS_KEYS, canada_lens_holdings, compute_canada
        holdings = canada_lens_holdings()
        lens = next((l for l in CANADA_LENS_KEYS if ev["ticker"] in holdings[l]), None)
    except Exception:
        lens = None
    if lens is None:
        return ("No lens-level event study covers this name yet — "
                "insufficient matured evidence for event-study context.")
    entry = __import__("v3.lab.etf_evidence", fromlist=["compute_canada"]).compute_canada()
    e = entry["lenses"][lens]
    mat = e["maturity"]
    es = e.get("event_study", {})
    by_type = es.get("by_type", {})
    memo_types = sorted({x["type"] for x in ev["events"]})
    lines = [f"Lens {lens}: {mat['n_matured']} matured of {mat['n_events']} accepted events."]
    for t in memo_types:
        bt = by_type.get(t)
        if not bt or "peer" not in bt:
            lines.append(f"- {t}: no matured pool yet — underpowered.")
            continue
        pts = bt["peer"]["points"]
        end = next((p for p in reversed(pts) if p["tau"] == max(q["tau"] for q in pts)), None)
        n = bt["peer"].get("n_events", end["n"] if end else 0)
        if not end or n < 10:
            lines.append(f"- {t}: n={n} matured — underpowered.")
            continue
        lo, hi, mean = end["ci_lo"], end["ci_hi"], end["mean_car"]
        if lo > 0:
            label = "supportive (peer-model CAR CI above zero at window end)" if mean > 0 else "adverse"
        elif hi < 0:
            label = "adverse (peer-model CAR CI below zero at window end)"
        else:
            label = "underpowered (peer-model CAR CI spans zero)"
        lines.append(f"- {t}: n={n} matured, peer-model mean CAR {mean:+.1%} at window end — {label}.")
    return "\n".join(lines)


def _conclusion(ev: dict, study_text: str) -> str:
    """Deterministic; LOCKED_CONCLUSIONS phrases only, plus counts."""
    parts: list[str] = []
    events = ev["events"]
    if not events:
        parts.append("insufficient matured evidence")
        parts.append("outside current evidence scope"
                     if ev["grade"].startswith("D") else "not statistically proven")
    else:
        net = sum(e["direction"] for e in events)
        if net > 0:
            parts.append("evidence posture improved")
        elif net < 0:
            parts.append("evidence posture weakened")
        else:
            parts.append("insufficient matured evidence")
        if any(e["c6_posture"].endswith("/ elevated") for e in events):
            parts.append("risk-gate elevated")
        if "underpowered" in study_text:
            parts.append("underpowered")
        parts.append("not statistically proven")
    n = len(events)
    return (f"Over the window ({n} accepted event(s)): " + "; ".join(parts) + ".")


def _evidence_table(ev: dict) -> str:
    if not ev["events"]:
        return "_No accepted evidence events in the window._"
    head = ("| Date | Form | Exhibit | Event type | Verified quote | Grade | C6 posture | SourceLock |\n"
            "|---|---|---|---|---|---|---|---|")
    rows = []
    for e in ev["events"]:
        q = e["quote"].replace("|", "\\|")
        q = (q[:140] + "…") if len(q) > 140 else q
        extra = ""
        a = e["attributes"]
        if a:
            role = a.get("insider_role", "")
            plan = " · 10b5-1 plan" if a.get("plan_10b5_1") else ""
            extra = f" _({role}{plan})_" if role else ""
        rows.append(f"| {e['date']} | {e['form']} | {e['exhibit']} | {e['type']}{extra} "
                    f"| “{q}” | {ev['grade'].split(' ')[0]} | {e['c6_posture']} "
                    f"| {e['status']} |")
    cl = ev["cluster"]
    cluster_line = ""
    if cl["buys"] or cl["sells"]:
        cluster_line = (f"\n\n_Same-issuer insider cluster (window): {cl['buys']} buy / "
                        f"{cl['sells']} sell event(s), {cl['distinct_roles']} distinct role(s), "
                        f"{cl['plan_10b5_1']} under a disclosed 10b5-1 plan — display context "
                        f"only, computed live._")
    return head + "\n" + "\n".join(rows) + cluster_line


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def generate_evidence_memo(ticker: str, days: int = 30, *, model: str = MEMO_MODEL,
                           dsn: str = DSN) -> str:
    ticker = ticker.upper()
    ev = gather_evidence(ticker, days, dsn)
    narrative = _generate_narrative(ev, model)
    study = _event_study_context(ev)
    risk = _risk_gate_note(ev)
    conclusion = _conclusion(ev, study)

    md = f"""# Evidence memo — {ev['name']} ({ticker})

*Window: last {days} days ({ev['since'].date().isoformat()} → {ev['now'].date().isoformat()}) ·
generated {ev['now'].strftime('%Y-%m-%d %H:%M UTC')} · evidence grade {ev['grade']}*

## Research question

What changed in {ev['name']}'s filings evidence over the last {days} days?

## Evidence table

{_evidence_table(ev)}

## Change narrative

{narrative}

## Risk-gate note

{risk}

## Event-study context

{study}

## Honest conclusion

{conclusion}

{RESEARCH_FOOTER}
"""

    # Final lint over the authored prose (table/quotes excluded by scope rules).
    authored = "\n".join([narrative, risk, conclusion,
                          f"What changed in {ev['name']}'s filings evidence over the last {days} days?"])
    violations = lint_text(authored, strip=True)
    if violations:
        raise MemoGenerationError(
            "Memo failed language lint:\n" +
            "\n".join(f"- [{v['word']}] {v['line']}" for v in violations[:10]))
    if not check_research_footer(md):
        raise MemoGenerationError("Memo missing the mandatory research-only footer.")
    return md


__all__ = ["generate_evidence_memo", "MemoGenerationError", "LOCKED_CONCLUSIONS"]
