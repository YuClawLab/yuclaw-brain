"""YUCLAW v5 Layer 1 Day 4 — model-agnostic worker call path.

The worker model is a SINGLE config value (``WORKER_MODEL``). Every worker-tier agent — the
base Bull/Bear/Skeptic AND the event-type specialists — calls ``call_worker()``, which uses the
UNIVERSAL ``/api/chat`` path with thinking disabled:

  * ``think=false`` is a no-op for non-thinking models (``llama3.1:8b``, today's default);
  * it is REQUIRED for thinking models (Gemma 4) — without it the thinking step eats the
    ``num_predict`` budget and ``message.content`` returns empty (the Day-3.5 A/B confound).

So swapping the worker tier to Gemma 4 after the Ollama upgrade is a one-line config change
(``YUCLAW_V5_WORKER_MODEL=gemma4:26b-a4b-it-q4_K_M``), not a rebuild. The 70B Synthesis
adjudicator is a separate model on its own path and is intentionally left unchanged.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import requests

# Default worker is Gemma 4 (the validated +29% grounding win; Order-3 swap 2026-06-25).
# Requires prod Ollama >= 0.20 (now 0.22.1) and WORKER_THINK=false (default below).
# Footprint is safe: WORKER_NUM_CTX=8192 keeps Gemma ~20GiB so it coexists with the
# capped 70B (~46GiB) inside 128GiB. Override via YUCLAW_V5_WORKER_MODEL=llama3.1:8b.
WORKER_MODEL = os.environ.get(
    "YUCLAW_V5_WORKER_MODEL",
    os.environ.get("YUCLAW_V5_AGENT_MODEL", "gemma4:26b-a4b-it-q4_K_M"))
WORKER_URL = os.environ.get(
    "YUCLAW_V5_WORKER_URL",
    os.environ.get("YUCLAW_V5_OLLAMA_URL", "http://localhost:11434")).rstrip("/")
# Disable model "thinking" by default; honored by thinking models, no-op otherwise.
WORKER_THINK = os.environ.get("YUCLAW_V5_WORKER_THINK", "false").lower() in ("1", "true", "yes")
WORKER_NUM_CTX = int(os.environ.get("YUCLAW_V5_NUM_CTX", "8192"))
WORKER_NUM_PREDICT = int(os.environ.get("YUCLAW_V5_AGENT_NUM_PREDICT", "768"))
WORKER_TEMPERATURE = float(os.environ.get("YUCLAW_V5_AGENT_TEMP", "0.4"))
WORKER_TIMEOUT = float(os.environ.get("YUCLAW_V5_AGENT_TIMEOUT", "300"))


def call_worker(prompt: str, *, model: Optional[str] = None, url: Optional[str] = None,
                num_predict: Optional[int] = None, temperature: Optional[float] = None,
                timeout: Optional[float] = None) -> tuple[dict, float, Any]:
    """One worker call via /api/chat + format=json + think flag. Returns
    (parsed_dict, elapsed_secs, eval_count). Raises on empty / non-object output."""
    model = model or WORKER_MODEL
    url = (url or WORKER_URL).rstrip("/")
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False, "format": "json", "think": WORKER_THINK,
        "options": {
            "temperature": WORKER_TEMPERATURE if temperature is None else temperature,
            "num_predict": num_predict or WORKER_NUM_PREDICT,
            "num_ctx": WORKER_NUM_CTX,
        },
    }
    t0 = time.perf_counter()
    r = requests.post(f"{url}/api/chat", json=body, timeout=timeout or WORKER_TIMEOUT)
    elapsed = time.perf_counter() - t0
    r.raise_for_status()
    data = r.json()
    text = (data.get("message", {}).get("content") or "").strip()
    if not text:
        raise RuntimeError(f"{model} returned empty content "
                           f"(thinking model without think=false?)")
    parsed = json.loads(text)  # format=json guarantees valid JSON when content is non-empty
    if not isinstance(parsed, dict) or not parsed:
        raise RuntimeError(f"{model} output not a JSON object: {text[:200]!r}")
    return parsed, elapsed, data.get("eval_count")
