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

PROMPT_VERSION = "v1"

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

# --------------------------------------------------------------------------
# Output schemas (the contract every consumer can rely on)
# --------------------------------------------------------------------------
AGENT_KEYS = ("stance", "key_points", "confidence", "evidence_cited",
              "return_view", "risk_view")
VIEW_RETURN_KEYS = ("direction", "horizon", "rationale")   # direction: positive/negative/neutral/mixed
VIEW_RISK_KEYS = ("level", "drivers", "rationale")          # level: low/medium/high/elevated

_SCHEMA_BLOCK = (
    'Return ONLY a JSON object with EXACTLY these keys:\n'
    '  "stance"         — one sentence stating your overall read of this filing\n'
    '  "key_points"     — array of 2-4 short strings, your strongest points\n'
    '  "confidence"     — number 0.0-1.0, your confidence in this read\n'
    '  "evidence_cited" — array of short quotes/specifics drawn from the filing text\n'
    '  "return_view"    — object {"direction": one of "positive"/"negative"/"neutral"/"mixed",\n'
    '                            "horizon": e.g. "1-4w"/"4-13w", "rationale": one sentence}\n'
    '                     (this is a directional research opinion, NOT a trade recommendation)\n'
    '  "risk_view"      — object {"level": one of "low"/"medium"/"high",\n'
    '                            "drivers": array of short strings, "rationale": one sentence}\n'
    "Output nothing except the JSON object."
)

ROLE_PROMPTS = {
    "bull": (
        "You are the BULL analyst in a research debate. Build the STRONGEST "
        "evidence-based BULLISH case for the company from this SEC filing: what is "
        "constructive, improving, or under-appreciated. Be persuasive but grounded "
        "in the text. Still fill risk_view honestly.\n\n" + _SCHEMA_BLOCK +
        "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
    ),
    "bear": (
        "You are the BEAR analyst in a research debate. Build the STRONGEST "
        "evidence-based BEARISH/cautious case from this SEC filing: what is "
        "deteriorating, concerning, or a red flag. Be persuasive but grounded in "
        "the text. Fill risk_view emphasising the downside drivers.\n\n" + _SCHEMA_BLOCK +
        "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
    ),
    "skeptic": (
        "You are the SKEPTIC in a research debate. Do NOT take a directional side. "
        "Critique the EVIDENCE: what material information is MISSING from this "
        "filing, what cannot be concluded, which claims are unsupported or "
        "ambiguous, and what an analyst would need before trusting any read. Your "
        "confidence should reflect evidence sufficiency, and your return_view "
        "direction should usually be \"neutral\" or \"mixed\" unless the text is "
        "unambiguous.\n\n" + _SCHEMA_BLOCK +
        "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
    ),
}

SYNTHESIS_PROMPT = (
    "You are the SYNTHESIS analyst (senior). Three junior analysts have debated an "
    "SEC filing: a BULL, a BEAR, and a SKEPTIC. Reconcile their views into one "
    "balanced research assessment. Weigh the evidence; do not just average. The "
    "skeptic's missing-evidence points should temper confidence.\n\n"
    "Return ONLY a JSON object with EXACTLY these keys:\n"
    '  "synthesis_stance"  — one to two sentences, your reconciled read\n'
    '  "return_channel"    — object {"direction": "positive"/"negative"/"neutral"/"mixed",\n'
    '                                "confidence": 0.0-1.0, "horizon": e.g. "1-4w",\n'
    '                                "rationale": one sentence}\n'
    '  "risk_channel"      — object {"level": "low"/"medium"/"high", "drivers": [..],\n'
    '                                "rationale": one sentence}\n'
    '  "agent_attribution" — object {"bull": how the bull influenced this (one phrase),\n'
    '                                "bear": .., "skeptic": ..}\n'
    '  "key_risks"         — array of the 2-4 most material risks\n'
    '  "confidence"        — number 0.0-1.0, overall confidence\n'
    "The return_channel is a directional research opinion, NOT a trade "
    "recommendation. Output nothing except the JSON object.\n\n"
    "FILING EXCERPT:\n{text}\n\n"
    "BULL view:\n{bull}\n\nBEAR view:\n{bear}\n\nSKEPTIC view:\n{skeptic}\n\nJSON:"
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


def validate_agent_output(d: dict) -> tuple[dict, list]:
    warns = []
    out = {}
    out["stance"] = str(d.get("stance") or "").strip() or "(no stance)"
    if not d.get("stance"):
        warns.append("missing stance")
    kp = d.get("key_points")
    out["key_points"] = [str(x) for x in kp] if isinstance(kp, list) else ([str(kp)] if kp else [])
    if not out["key_points"]:
        warns.append("empty key_points")
    try:
        out["confidence"] = max(0.0, min(1.0, float(d.get("confidence"))))
    except (TypeError, ValueError):
        out["confidence"] = None
        warns.append("bad confidence")
    ec = d.get("evidence_cited")
    out["evidence_cited"] = [str(x) for x in ec] if isinstance(ec, list) else ([str(ec)] if ec else [])
    out["return_view"] = _coerce_view(d.get("return_view"), VIEW_RETURN_KEYS,
                                      {"direction": "neutral", "horizon": None, "rationale": None})
    out["risk_view"] = _coerce_view(d.get("risk_view"), VIEW_RISK_KEYS,
                                    {"level": None, "drivers": [], "rationale": None})
    if d.get("return_view") is None:
        warns.append("missing return_view")
    if d.get("risk_view") is None:
        warns.append("missing risk_view")
    return out, warns


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
        "agent_attribution": d.get("agent_attribution") if isinstance(d.get("agent_attribution"), dict) else {},
        "key_risks": [str(x) for x in d.get("key_risks")] if isinstance(d.get("key_risks"), list) else [],
        "confidence": None,
    }
    try:
        out["confidence"] = max(0.0, min(1.0, float(d.get("confidence"))))
    except (TypeError, ValueError):
        warns.append("bad confidence")
    for k in ("synthesis_stance", "return_channel", "risk_channel", "agent_attribution"):
        if not d.get(k):
            warns.append(f"missing {k}")
    return out, warns


# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------
class SwarmAgent:
    """Base 8B debate agent. Subclasses set ``role``."""
    role: str = "base"

    def __init__(self, model: str = AGENT_MODEL, *, url: str = OLLAMA_URL,
                 timeout: float = AGENT_TIMEOUT, temperature: float = 0.4):
        self.model, self.url, self.timeout, self.temperature = model, url, timeout, temperature

    def build_prompt(self, filing_text: str) -> str:
        # literal replace (prompts contain JSON-example braces; .format would choke)
        return ROLE_PROMPTS[self.role].replace("{text}", filing_text[:MAX_FILING_CHARS])

    def run(self, filing_text: str) -> dict:
        raw, elapsed, eval_count = ollama_generate(
            self.model, self.build_prompt(filing_text), url=self.url,
            timeout=self.timeout, num_predict=420, temperature=self.temperature)
        out, warns = validate_agent_output(raw)
        return {
            "agent_role": self.role, "prompt_version": PROMPT_VERSION,
            "model": self.model, "output": out, "raw": raw,
            "schema_warnings": warns, "llama_secs": round(elapsed, 2),
            "eval_count": eval_count,
        }


class BullAgent(SwarmAgent):
    role = "bull"


class BearAgent(SwarmAgent):
    role = "bear"


class SkepticAgent(SwarmAgent):
    role = "skeptic"


AGENT_REGISTRY = {"bull": BullAgent, "bear": BearAgent, "skeptic": SkepticAgent}


class SynthesisAgent:
    """70B synthesis over the three agent outputs + the filing."""
    role = "synthesis"

    def __init__(self, model: str = SYNTH_MODEL, *, url: str = OLLAMA_URL,
                 timeout: float = SYNTH_TIMEOUT, temperature: float = 0.2):
        self.model, self.url, self.timeout, self.temperature = model, url, timeout, temperature

    def build_prompt(self, filing_text: str, agent_outputs: dict) -> str:
        def fmt(role):
            o = agent_outputs.get(role, {}).get("output", {})
            return json.dumps(o, ensure_ascii=False)
        return (SYNTHESIS_PROMPT
                .replace("{text}", filing_text[:MAX_FILING_CHARS])
                .replace("{bull}", fmt("bull"))
                .replace("{bear}", fmt("bear"))
                .replace("{skeptic}", fmt("skeptic")))

    def run(self, filing_text: str, agent_outputs: dict) -> dict:
        raw, elapsed, eval_count = ollama_generate(
            self.model, self.build_prompt(filing_text, agent_outputs), url=self.url,
            timeout=self.timeout, num_predict=640, temperature=self.temperature)
        out, warns = validate_synthesis_output(raw)
        return {
            "agent_role": self.role, "prompt_version": PROMPT_VERSION,
            "model": self.model, "output": out, "raw": raw,
            "schema_warnings": warns, "llama_secs": round(elapsed, 2),
            "eval_count": eval_count,
        }
