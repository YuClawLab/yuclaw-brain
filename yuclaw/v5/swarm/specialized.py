"""YUCLAW v5 Layer 1 Day 4 — specialized swarm + C6 risk channel.

run_specialized() drives one filing through:
  1. deterministic specialist spawn (specialists.spawn_specialists, from event_type);
  2. the base Bull/Bear/Skeptic swarm + the spawned specialists, run CONCURRENTLY, all on the
     model-agnostic WORKER_MODEL, all grounded by the same citation verifier;
  3. the C6 RISK CHANNEL — risk_view's aggregated across base + specialists into a separate
     channel (vol/drawdown oriented), with the Insider specialist acting as a risk GATE;
  4. the 70B Synthesis adjudicator, which consumes DIRECTION and RISK as SEPARATE channels:
     the risk channel can demote / flag a name (elevated risk) WITHOUT flipping its direction.

Research-classification only: the risk channel emits an elevated/normal FLAG, never a
buy/sell/short instruction. Synthesis model (70B) is unchanged from Day 2/3.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor

from yuclaw.v5.swarm.agents import (
    AGENT_REGISTRY, MAX_FILING_CHARS, PROMPT_VERSION, SYNTH_MODEL, SYNTH_TIMEOUT,
    build_grounded_brief, ollama_generate, _coerce_view, VIEW_RISK_KEYS,
)
from yuclaw.v5.swarm.specialists import SpecialistAgent, spawn_specialists
from yuclaw.v5.swarm.worker import WORKER_MODEL

ROLES = ("bull", "bear", "skeptic")
_RISK_SCORE = {"low": 0, "medium": 1, "high": 2, "elevated": 2}
_SCORE_LEVEL = {0: "low", 1: "medium", 2: "high"}


# --------------------------------------------------------------------------
# C6 risk channel
# --------------------------------------------------------------------------
def _risk_channel(base: dict, specialists: dict) -> dict:
    """Aggregate risk_view across base + specialists into ONE risk channel, separate from
    direction. Level = max severity seen; flag 'elevated' if any high. The Insider specialist
    is a C6 risk gate: if it fired, its risk drives the flag even when directions stay neutral."""
    drivers: list[str] = []
    scores: list[int] = []
    contributors: dict[str, str] = {}
    for name, res in list(base.items()) + list(specialists.items()):
        rv = (res.get("output") or {}).get("risk_view") or {}
        lvl = (rv.get("level") or "").strip().lower()
        sc = _RISK_SCORE.get(lvl, 0)
        scores.append(sc)
        contributors[name] = lvl or "n/a"
        for d in (rv.get("drivers") or []):
            if str(d).strip():
                drivers.append(str(d).strip())
    max_score = max(scores) if scores else 0
    insider = "insider" in specialists
    insider_lvl = ((specialists.get("insider", {}).get("output") or {}).get("risk_view") or {}).get("level", "")
    insider_gate = insider and _RISK_SCORE.get((insider_lvl or "").lower(), 0) >= 2
    flag = "elevated" if (max_score >= 2 or insider_gate) else "normal"
    return {
        "level": _SCORE_LEVEL[max_score],
        "flag": flag,                       # elevated | normal — a RESEARCH flag, not a trade
        "drivers": sorted(set(drivers))[:8],
        "contributors": contributors,       # which agent/specialist reported which level
        "insider_gate": insider_gate,       # C6: insider-sell cluster forced the flag
    }


# --------------------------------------------------------------------------
# Day-4 synthesis (direction + risk as SEPARATE channels)
# --------------------------------------------------------------------------
DAY4_SYNTHESIS_PROMPT = (
    "You are the SYNTHESIS adjudicator (senior). A base debate (BULL/BEAR/SKEPTIC) plus "
    "event-type SPECIALISTS analysed an SEC filing. A verifier kept only verbatim-grounded "
    "claims (below, with their quotes). A separate RISK CHANNEL aggregates their risk views.\n\n"
    "Reconcile into ONE research assessment with DIRECTION and RISK as SEPARATE channels:\n"
    "  - The RETURN channel is your directional read from the grounded directional claims.\n"
    "  - The RISK channel is volatility/drawdown-oriented. CRITICAL: an elevated risk flag may "
    "DEMOTE or FLAG a name (lower confidence, raise risk level) but must NOT flip its direction. "
    "A name can be \"positive direction, elevated risk\". In particular, an insider-SELL cluster "
    "is a RISK signal only — it must NOT make the direction bearish.\n"
    "This is research classification only — NO buy/sell/short, NO execution.\n\n"
    "Return ONLY a JSON object with EXACTLY these keys:\n"
    '  "synthesis_stance"  — one to two sentences, your reconciled read\n'
    '  "return_channel"    — {"direction": "positive"/"negative"/"neutral"/"mixed",\n'
    '                         "confidence": 0.0-1.0, "horizon": e.g. "1-4w", "rationale": one sentence}\n'
    '  "risk_channel"      — {"level": "low"/"medium"/"high", "flag": "elevated"/"normal",\n'
    '                         "drivers": [..], "rationale": one sentence}\n'
    '  "key_findings"      — array of 2-4 {"finding": one sentence, "quote": a verbatim span from above}\n'
    '  "specialist_notes"  — object mapping each specialist key to one phrase on its contribution\n'
    '  "confidence"        — number 0.0-1.0\n'
    "Output nothing except the JSON object.\n\n"
    "FILING EXCERPT:\n{text}\n\n"
    "GROUNDED DEBATE + SPECIALIST MATERIAL:\n{brief}\n\n"
    "RISK CHANNEL (separate from direction):\n{risk}\n\nJSON:"
)


def _validate_day4_synth(d: dict) -> tuple[dict, list]:
    warns = []
    out = {
        "synthesis_stance": str(d.get("synthesis_stance") or "").strip() or "(none)",
        "return_channel": _coerce_view(d.get("return_channel"),
                                       ("direction", "confidence", "horizon", "rationale"),
                                       {"direction": "neutral", "confidence": None,
                                        "horizon": None, "rationale": None}),
        "risk_channel": _coerce_view(d.get("risk_channel"),
                                     ("level", "flag", "drivers", "rationale"),
                                     {"level": None, "flag": "normal", "drivers": [], "rationale": None}),
        "key_findings": [it for it in (d.get("key_findings") or []) if isinstance(it, dict)],
        "specialist_notes": d.get("specialist_notes") if isinstance(d.get("specialist_notes"), dict) else {},
        "confidence": None,
    }
    try:
        out["confidence"] = max(0.0, min(1.0, float(d.get("confidence"))))
    except (TypeError, ValueError):
        warns.append("bad confidence")
    for k in ("return_channel", "risk_channel", "synthesis_stance"):
        if not d.get(k):
            warns.append(f"missing {k}")
    return out, warns


def _specialist_brief(specialists: dict) -> str:
    lines = []
    for key, res in specialists.items():
        g = res.get("grounding") or {}
        rv = (res.get("output") or {}).get("return_view") or {}
        lines.append(f"=== SPECIALIST:{key.upper()} (return {rv.get('direction','n/a')}; "
                     f"risk {((res.get('output') or {}).get('risk_view') or {}).get('level','n/a')}; "
                     f"grounded {g.get('points_grounded',0)}/{g.get('points_total',0)}) ===")
        for p in [p for p in g.get("points", []) if p.get("grounded")]:
            lines.append(f"  - {p['point']}")
            for q in p.get("quotes", []):
                if q.get("verified"):
                    lines.append(f'      quote: "{q["quote"]}"')
        if not [p for p in g.get("points", []) if p.get("grounded")]:
            lines.append("  (no grounded claims survived)")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def run_specialized(accession: str, narrative_text: str, *, dsn: str = "dbname=yuclaw_events",
                    synthesize: bool = True) -> dict:
    t0 = time.perf_counter()
    spawned = spawn_specialists(accession, dsn, narrative_text=narrative_text)
    spawn_keys = [s["key"] for s in spawned]

    # Build the full worker set: base 3 + spawned specialists.
    agents = {r: AGENT_REGISTRY[r](model=WORKER_MODEL) for r in ROLES}
    for s in spawned:
        agents[f"spec:{s['key']}"] = SpecialistAgent(s["key"], model=WORKER_MODEL)

    t_conc = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(agents)) as ex:
        futures = {name: ex.submit(a.run, narrative_text) for name, a in agents.items()}
        results = {name: f.result() for name, f in futures.items()}
    concurrent_wall = time.perf_counter() - t_conc

    base = {r: results[r] for r in ROLES}
    specialists = {name[5:]: res for name, res in results.items() if name.startswith("spec:")}

    risk_channel = _risk_channel(base, specialists)

    assembled = {
        "accession_number": accession, "prompt_version": PROMPT_VERSION,
        "worker_model": WORKER_MODEL, "spawned": spawned, "spawn_keys": spawn_keys,
        "base": base, "specialists": specialists, "risk_channel": risk_channel,
        "filing_len": len(narrative_text),
    }
    if not synthesize:
        assembled["timings"] = {"concurrent_worker_wall_secs": round(concurrent_wall, 2),
                                "total_secs": round(time.perf_counter() - t0, 2)}
        return assembled

    # 70B synthesis — direction + risk as separate channels.
    brief = build_grounded_brief(base)
    if specialists:
        brief += "\n\n" + _specialist_brief(specialists)
    risk_txt = (f"aggregate level={risk_channel['level']} flag={risk_channel['flag']} "
                f"insider_gate={risk_channel['insider_gate']} drivers={risk_channel['drivers']} "
                f"contributors={risk_channel['contributors']}")
    prompt = (DAY4_SYNTHESIS_PROMPT.replace("{text}", narrative_text[:MAX_FILING_CHARS])
              .replace("{brief}", brief).replace("{risk}", risk_txt))
    raw, elapsed, eval_count = ollama_generate(SYNTH_MODEL, prompt, timeout=SYNTH_TIMEOUT,
                                               num_predict=1024, temperature=0.2)
    sout, swarns = _validate_day4_synth(raw)
    assembled["synthesis"] = {"model": SYNTH_MODEL, "output": sout, "raw": raw,
                              "schema_warnings": swarns, "llama_secs": round(elapsed, 2),
                              "eval_count": eval_count}
    assembled["timings"] = {
        "concurrent_worker_wall_secs": round(concurrent_wall, 2),
        "synthesis_secs": round(elapsed, 2),
        "total_secs": round(time.perf_counter() - t0, 2),
        "worker_secs": {name: results[name]["llama_secs"] for name in results},
    }
    return assembled
