"""YUCLAW v5 Layer 1 — swarm agents (Bull / Bear / Skeptic + Synthesis).

Three 8B debate agents argue a filing from distinct angles; a 70B Synthesis
agent reconciles them. Every agent emits structured JSON with BOTH a
``return_view`` and a ``risk_view`` (the risk channel is first-class from Day 1 —
see docs/v5/layer1/design_inputs.md, amendment 3, grounded in the C6
risk-gate finding IC(C6, vol) = -0.317).

This is research infrastructure: agents produce analytical *views* (a bullish
case, a bearish case, an evidence critique), NOT trade recommendations. The
return channel is a directional research opinion (positive/negative/neutral/
mixed), not an instruction to transact.

Ollama call convention reused from the Layer 0 worker (POST /api/generate with
``format: json``). Prompts are versioned v1 scaffolds (PROMPT_VERSION).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import requests

from yuclaw.v5.swarm.grounding import grade_agent
from yuclaw.v5.swarm.worker import call_worker, WORKER_MODEL

PROMPT_VERSION = "v2"

OLLAMA_URL = os.environ.get("YUCLAW_V5_OLLAMA_URL", "http://localhost:11434").rstrip("/")
AGENT_MODEL = os.environ.get("YUCLAW_V5_AGENT_MODEL", "llama3.1:8b")
SYNTH_MODEL = os.environ.get("YUCLAW_V5_MODEL", "yuclaw-llm-70b:latest")
AGENT_TIMEOUT = float(os.environ.get("YUCLAW_V5_AGENT_TIMEOUT", "180"))
SYNTH_TIMEOUT = float(os.environ.get("YUCLAW_V5_LLAMA_TIMEOUT", "300"))
MAX_FILING_CHARS = 6000
# Cap the context window. llama3.1:8b defaults to a 131072-token window which
# balloons the KV cache to ~31GB and forces partial CPU offload (29%/71%),
# serialising concurrent calls. Our prompt+filing is ~2k tokens, so an 8k window
# keeps the model fully on GPU and lets concurrent calls actually parallelise.
# This is a per-REQUEST option (options.num_ctx), not an Ollama service change.
NUM_CTX = int(os.environ.get("YUCLAW_V5_NUM_CTX", "8192"))
# Token budget for an agent's JSON answer. 420 was too tight: when an 8B gets
# verbose in evidence_cited, the format=json grammar runs out of tokens mid-string
# and emits TRUNCATED (invalid) JSON, which json.loads rejects and fails the whole
# filing (observed on the Day-1 3-filing batch: "Unterminated string"). The schema
# is small; 768 gives ~2x headroom. Synthesis keeps its own (640) budget.
AGENT_NUM_PREDICT = int(os.environ.get("YUCLAW_V5_AGENT_NUM_PREDICT", "768"))
# Agent sampling temperature. Lower = less inventive = fewer fabricated quotes.
# Day-2 iteration knob (default 0.4; round 3 tested 0.2).
AGENT_TEMPERATURE = float(os.environ.get("YUCLAW_V5_AGENT_TEMP", "0.4"))
# Token budget for the 70B synthesis answer. The v2 grounded synthesis emits more
# than v1 — key_findings each carry a verbatim quote, plus a disagreements array —
# so the old 640 truncated the JSON on prose filings ("Unterminated string" at
# ~2.7k chars). 1024 gives headroom for the richer, quote-bearing schema.
SYNTH_NUM_PREDICT = int(os.environ.get("YUCLAW_V5_SYNTH_NUM_PREDICT", "1024"))

# --------------------------------------------------------------------------
# Output schemas (the contract every consumer can rely on)
# --------------------------------------------------------------------------
AGENT_KEYS = ("stance", "key_points", "confidence", "return_view", "risk_view")
VIEW_RETURN_KEYS = ("direction", "horizon", "rationale")   # direction: positive/negative/neutral/mixed
VIEW_RISK_KEYS = ("level", "drivers", "rationale")          # level: low/medium/high/elevated

# v2 (Day 2): key_points are GROUNDED objects — each claim must carry >= 1 quote
# copied verbatim from the filing, and any figure in the claim must appear inside
# its quotes. A deterministic verifier (grounding.py) enforces this AFTER the call;
# the prompt tells the model the rules so it self-grounds rather than fabricates.
_SCHEMA_BLOCK = (
    'Return ONLY a JSON object with EXACTLY these keys:\n'
    '  "stance"      — one sentence: your overall read of this filing\n'
    '  "key_points"  — array of 2-4 objects, each exactly:\n'
    '        {"point": "<your claim, one sentence>",\n'
    '         "quotes": ["<text copied VERBATIM from the filing>", ...]}\n'
    '  "confidence"  — number 0.0-1.0, your confidence in this read\n'
    '  "return_view" — object {"direction": one of "positive"/"negative"/"neutral"/"mixed",\n'
    '                          "horizon": e.g. "1-4w"/"4-13w", "rationale": one sentence}\n'
    '                  (a directional research opinion, NOT a trade recommendation)\n'
    '  "risk_view"   — object {"level": one of "low"/"medium"/"high",\n'
    '                          "drivers": array of short strings, "rationale": one sentence}\n'
    '\n'
    'GROUNDING RULES — an automated verifier checks every claim against the filing:\n'
    '  1. Each key_point MUST include at least one quote copied CHARACTER-FOR-\n'
    '     CHARACTER from the FILING text below. Never paraphrase a quote.\n'
    '  2. Any number, percent, or dollar figure in "point" MUST also appear inside\n'
    '     one of that point\'s quotes (so it is literally in the filing).\n'
    '  3. A key_point whose quote is not found verbatim, or whose numbers are not\n'
    '     inside its quotes, is DISCARDED. State only what the text literally says.\n'
    '  4. NEVER invent or reconstruct a quote from memory or what a filing "should"\n'
    '     say. Before writing any quote, find it in the FILING EXCERPT and copy it.\n'
    '     If you cannot find supporting text for a point, DROP the point. ONE\n'
    '     grounded point beats three invented ones — an invented quote is the worst\n'
    '     outcome and is always caught.\n'
    '  5. The excerpt may be mostly data tables, labels, or machine tags with little\n'
    '     prose. Quote whatever real text IS present — a sentence, or a line-item\n'
    '     label together with its number. If little is quotable, return fewer points.\n'
    'Output nothing except the JSON object.'
)

ROLE_PROMPTS = {
    "bull": (
        "You are the BULL analyst in a research debate. Build the STRONGEST "
        "BULLISH case for the company using ONLY what this SEC filing literally "
        "states: what is constructive, improving, or under-appreciated. Every "
        "point must be backed by a verbatim quote from the filing; if you cannot "
        "find a quote for a bullish claim, drop it. Still fill risk_view honestly."
        "\n\n" + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
    ),
    "bear": (
        "You are the BEAR analyst in a research debate. Build the STRONGEST "
        "BEARISH/cautious case using ONLY what this SEC filing literally states: "
        "what is deteriorating, concerning, or a red flag. Every point must be "
        "backed by a verbatim quote from the filing; if you cannot find a quote "
        "for a bearish claim, drop it. Fill risk_view emphasising downside drivers."
        "\n\n" + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
    ),
    "skeptic": (
        "You are the SKEPTIC in a research debate. Do NOT take a directional side. "
        "Critique the EVIDENCE: what material information is MISSING from this "
        "filing, what cannot be concluded, which claims are unsupported or "
        "ambiguous. For each point, quote the filing language you are reacting to "
        "(e.g. the vague or boilerplate passage). Your confidence should reflect "
        "evidence sufficiency, and your return_view direction should usually be "
        "\"neutral\" or \"mixed\" unless the text is unambiguous.\n\n" + _SCHEMA_BLOCK +
        "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
    ),
}

SYNTHESIS_PROMPT = (
    "You are the SYNTHESIS analyst (senior). Three junior analysts debated an SEC "
    "filing: a BULL, a BEAR, and a SKEPTIC. A verifier has already checked their "
    "claims against the filing and kept ONLY the verbatim-grounded ones (shown "
    "below with their verified quotes). Ungrounded claims were DISCARDED and are "
    "listed only so you know what to ignore — never rely on a discarded claim.\n\n"
    "Reconcile the GROUNDED claims into one balanced research assessment. Weigh the "
    "evidence; do not just average. Where the BULL and the BEAR each cite the "
    "filing but read it oppositely, that is legitimate quote-backed DISAGREEMENT — "
    "preserve and surface it; do not paper over it. The skeptic's missing-evidence "
    "points should temper confidence.\n\n"
    "Return ONLY a JSON object with EXACTLY these keys:\n"
    '  "synthesis_stance"  — one to two sentences, your reconciled read\n'
    '  "return_channel"    — object {"direction": "positive"/"negative"/"neutral"/"mixed",\n'
    '                                "confidence": 0.0-1.0, "horizon": e.g. "1-4w",\n'
    '                                "rationale": one sentence}\n'
    '  "risk_channel"      — object {"level": "low"/"medium"/"high", "drivers": [..],\n'
    '                                "rationale": one sentence}\n'
    '  "key_findings"      — array of 2-4 objects {"finding": one sentence,\n'
    '                        "quote": a span copied VERBATIM from the verified quotes\n'
    '                        above that supports it}. Attribute every finding.\n'
    '  "disagreements"     — array (0-3) of objects {"point": what the bull and bear\n'
    '                        read oppositely, "quote": a verbatim span from above}.\n'
    '                        Empty array if there is no genuine quote-backed clash.\n'
    '  "agent_attribution" — object {"bull": one phrase, "bear": .., "skeptic": ..}\n'
    '  "confidence"        — number 0.0-1.0, overall confidence\n'
    "The return_channel is a directional research opinion, NOT a trade "
    "recommendation. Use ONLY the grounded material below. Output nothing except "
    "the JSON object.\n\n"
    "FILING EXCERPT:\n{text}\n\n"
    "GROUNDED DEBATE MATERIAL:\n{brief}\n\nJSON:"
)


# --------------------------------------------------------------------------
# Ollama
# --------------------------------------------------------------------------
def ollama_generate(model: str, prompt: str, *, url: str = OLLAMA_URL,
                    timeout: float = AGENT_TIMEOUT, num_predict: int = 420,
                    temperature: float = 0.4) -> tuple[dict, float, Any]:
    """POST /api/generate with format=json. Returns (parsed, elapsed_s, eval_count)."""
    body = {
        "model": model, "prompt": prompt, "stream": False, "format": "json",
        "options": {"temperature": temperature, "num_predict": num_predict,
                    "num_ctx": NUM_CTX},
    }
    t0 = time.perf_counter()
    resp = requests.post(f"{url}/api/generate", json=body, timeout=timeout)
    elapsed = time.perf_counter() - t0
    resp.raise_for_status()
    data = resp.json()
    text = (data.get("response") or "").strip()
    if not text:
        raise RuntimeError(f"{model} returned an empty response")
    parsed = json.loads(text)  # format=json guarantees valid JSON
    if not isinstance(parsed, dict) or not parsed:
        raise RuntimeError(f"{model} output not a JSON object: {text[:200]!r}")
    return parsed, elapsed, data.get("eval_count")


# --------------------------------------------------------------------------
# Validation / coercion (tolerant: fill gaps, record warnings)
# --------------------------------------------------------------------------
def _coerce_view(v, keys, defaults):
    out = dict(defaults)
    if isinstance(v, dict):
        for k in keys:
            if k in v and v[k] not in (None, ""):
                out[k] = v[k]
    return out


def _coerce_quotes(raw) -> list:
    """Coerce a key_point's quotes into a flat list of strings. Tolerates the
    model emitting a bare string, or [{"quote": ...}] objects instead of strings."""
    quotes = []
    if isinstance(raw, str):
        if raw.strip():
            quotes.append(raw)
    elif isinstance(raw, list):
        for q in raw:
            if isinstance(q, dict):
                qq = q.get("quote") or q.get("text") or q.get("span")
                if qq:
                    quotes.append(str(qq))
            elif q is not None and str(q).strip():
                quotes.append(str(q))
    return quotes


def _coerce_key_points(kp) -> tuple[list, list]:
    """Coerce key_points into the v2 shape [{"point": str, "quotes": [str]}].
    Tolerates a bare-string point (older shape) by attaching no quotes — the
    verifier will then discard it, which is the correct outcome."""
    out, warns = [], []
    if not isinstance(kp, list):
        return out, (["key_points not a list"] if kp else [])
    for item in kp:
        if isinstance(item, dict):
            point = str(item.get("point") or item.get("claim") or "").strip()
            quotes = _coerce_quotes(item.get("quotes") if "quotes" in item
                                    else item.get("evidence"))
        elif isinstance(item, str):
            point, quotes = item.strip(), []
            warns.append("key_point was a bare string (no quotes -> ungrounded)")
        else:
            continue
        if point:
            out.append({"point": point, "quotes": quotes})
    return out, warns


def validate_agent_output(d: dict) -> tuple[dict, list]:
    warns = []
    out = {}
    out["stance"] = str(d.get("stance") or "").strip() or "(no stance)"
    if not d.get("stance"):
        warns.append("missing stance")
    kp, kpw = _coerce_key_points(d.get("key_points"))
    out["key_points"] = kp
    warns += kpw
    if not kp:
        warns.append("empty key_points")
    try:
        out["confidence"] = max(0.0, min(1.0, float(d.get("confidence"))))
    except (TypeError, ValueError):
        out["confidence"] = None
        warns.append("bad confidence")
    out["return_view"] = _coerce_view(d.get("return_view"), VIEW_RETURN_KEYS,
                                      {"direction": "neutral", "horizon": None, "rationale": None})
    out["risk_view"] = _coerce_view(d.get("risk_view"), VIEW_RISK_KEYS,
                                    {"level": None, "drivers": [], "rationale": None})
    if d.get("return_view") is None:
        warns.append("missing return_view")
    if d.get("risk_view") is None:
        warns.append("missing risk_view")
    return out, warns


def _coerce_attr_list(raw, text_key: str) -> list:
    """Coerce key_findings/disagreements into [{<text_key>: str, "quote": str}]."""
    out = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, dict):
            txt = str(item.get(text_key) or item.get("text") or "").strip()
            quote = str(item.get("quote") or item.get("span") or "").strip()
            if txt:
                out.append({text_key: txt, "quote": quote})
        elif isinstance(item, str) and item.strip():
            out.append({text_key: item.strip(), "quote": ""})
    return out


def validate_synthesis_output(d: dict) -> tuple[dict, list]:
    warns = []
    out = {
        "synthesis_stance": str(d.get("synthesis_stance") or "").strip() or "(none)",
        "return_channel": _coerce_view(d.get("return_channel"),
                                       ("direction", "confidence", "horizon", "rationale"),
                                       {"direction": "neutral", "confidence": None,
                                        "horizon": None, "rationale": None}),
        "risk_channel": _coerce_view(d.get("risk_channel"), VIEW_RISK_KEYS,
                                     {"level": None, "drivers": [], "rationale": None}),
        "key_findings": _coerce_attr_list(d.get("key_findings"), "finding"),
        "disagreements": _coerce_attr_list(d.get("disagreements"), "point"),
        "agent_attribution": d.get("agent_attribution") if isinstance(d.get("agent_attribution"), dict) else {},
        "confidence": None,
    }
    try:
        out["confidence"] = max(0.0, min(1.0, float(d.get("confidence"))))
    except (TypeError, ValueError):
        warns.append("bad confidence")
    for k in ("synthesis_stance", "return_channel", "risk_channel", "key_findings"):
        if not d.get(k):
            warns.append(f"missing {k}")
    return out, warns


# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------
class SwarmAgent:
    """Base 8B debate agent. Subclasses set ``role``."""
    role: str = "base"

    def __init__(self, model: str = WORKER_MODEL, *, url: str = OLLAMA_URL,
                 timeout: float = AGENT_TIMEOUT, temperature: float = AGENT_TEMPERATURE):
        self.model, self.url, self.timeout, self.temperature = model, url, timeout, temperature

    def build_prompt(self, filing_text: str) -> str:
        # literal replace (prompts contain JSON-example braces; .format would choke)
        return ROLE_PROMPTS[self.role].replace("{text}", filing_text[:MAX_FILING_CHARS])

    def run(self, filing_text: str) -> dict:
        # Model-agnostic worker path (/api/chat + think:false). WORKER_MODEL is the
        # single config value; the 70B Synthesis adjudicator stays on its own path.
        raw, elapsed, eval_count = call_worker(
            self.build_prompt(filing_text), model=self.model, url=self.url,
            num_predict=AGENT_NUM_PREDICT, temperature=self.temperature, timeout=self.timeout)
        out, warns = validate_agent_output(raw)
        # Ground the output against the SAME text slice the agent read, so quote
        # offsets are consistent. The verifier is deterministic; no LLM here.
        grounding = grade_agent(out, filing_text[:MAX_FILING_CHARS])
        return {
            "agent_role": self.role, "prompt_version": PROMPT_VERSION,
            "model": self.model, "output": out, "raw": raw,
            "schema_warnings": warns, "grounding": grounding,
            "llama_secs": round(elapsed, 2), "eval_count": eval_count,
        }


class BullAgent(SwarmAgent):
    role = "bull"


class BearAgent(SwarmAgent):
    role = "bear"


class SkepticAgent(SwarmAgent):
    role = "skeptic"


AGENT_REGISTRY = {"bull": BullAgent, "bear": BearAgent, "skeptic": SkepticAgent}


def build_grounded_brief(graded_agents: dict) -> str:
    """Render ONLY verbatim-grounded claims (with their verified quotes) per role,
    plus a list of what was excluded, for the synthesis prompt. ``graded_agents``
    maps role -> the agent result dict (carrying ``output`` and ``grounding``)."""
    lines: list[str] = []
    for role in ("bull", "bear", "skeptic"):
        res = graded_agents.get(role) or {}
        g = res.get("grounding") or {}
        rv = (res.get("output") or {}).get("return_view") or {}
        lines.append(f"=== {role.upper()} (return_view direction: "
                     f"{rv.get('direction', 'n/a')}; grounded "
                     f"{g.get('points_grounded', 0)}/{g.get('points_total', 0)}) ===")
        grounded = [p for p in g.get("points", []) if p.get("grounded")]
        if grounded:
            lines.append("GROUNDED claims (use only these):")
            for i, p in enumerate(grounded, 1):
                lines.append(f"  {i}. {p['point']}")
                for q in p.get("quotes", []):
                    if q.get("verified"):
                        lines.append(f'       quote: "{q["quote"]}"')
        else:
            lines.append("GROUNDED claims: (none survived verification)")
        excluded = g.get("discarded_points", [])
        if excluded:
            lines.append("EXCLUDED — unverified, DO NOT USE:")
            for d in excluded:
                lines.append(f"  - {d['point']}  ({d['reason']})")
        lines.append("")
    return "\n".join(lines).strip()


class SynthesisAgent:
    """70B synthesis over the GROUNDED agent claims + the filing."""
    role = "synthesis"

    def __init__(self, model: str = SYNTH_MODEL, *, url: str = OLLAMA_URL,
                 timeout: float = SYNTH_TIMEOUT, temperature: float = 0.2):
        self.model, self.url, self.timeout, self.temperature = model, url, timeout, temperature

    def build_prompt(self, filing_text: str, graded_agents: dict) -> str:
        return (SYNTHESIS_PROMPT
                .replace("{text}", filing_text[:MAX_FILING_CHARS])
                .replace("{brief}", build_grounded_brief(graded_agents)))

    def run(self, filing_text: str, graded_agents: dict) -> dict:
        raw, elapsed, eval_count = ollama_generate(
            self.model, self.build_prompt(filing_text, graded_agents), url=self.url,
            timeout=self.timeout, num_predict=SYNTH_NUM_PREDICT,
            temperature=self.temperature)
        out, warns = validate_synthesis_output(raw)
        # Verify the synthesis's own cited quotes against the filing, then build
        # the proto evidence token: the union of all verified spans.
        synth_quotes = [it["quote"] for it in out["key_findings"] + out["disagreements"]
                        if it.get("quote")]
        synth_grounding = grade_agent(
            {"key_points": [{"point": "synthesis", "quotes": synth_quotes}]},
            filing_text[:MAX_FILING_CHARS])
        return {
            "agent_role": self.role, "prompt_version": PROMPT_VERSION,
            "model": self.model, "output": out, "raw": raw,
            "schema_warnings": warns, "synth_citation_grounding": synth_grounding,
            "llama_secs": round(elapsed, 2), "eval_count": eval_count,
        }
