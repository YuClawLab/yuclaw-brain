"""YUCLAW v5 Layer 1 — Worker-tier A/B: llama3.1:8b vs gemma4 as Bull/Bear/Skeptic.

Decides, on YUCLAW's real metrics (grounding rate + citation fidelity), whether Gemma 4 is a
better WORKER model than llama3.1:8b. The 70B is the synthesis model and is NOT under test, so
this harness is agent-only (no synthesis) — that also avoids holding Gemma + 70B co-resident.

Apples-to-apples: SAME prompts (agents.ROLE_PROMPTS + _SCHEMA_BLOCK), SAME deterministic
citation verifier (grounding.grade_agent), SAME narrative inputs (yuclaw_v5.swarm_inputs, the
Day-3 prose-extracted MD&A). Only the worker model + Ollama URL (and, for the confound check,
the /api/generate vs /api/chat path) differ per arm.

Each arm runs against its own Ollama endpoint:
  - 8B arm   -> production Ollama (127.0.0.1:11434)
  - Gemma arm-> isolated Ollama 0.30.9 (127.0.0.1:11500), prod untouched

Usage:
  python3 -m yuclaw.v5.swarm.worker_ab <arm_name> <model> <ollama_url> <use_chat 0|1> \
          <max_chars> <out.json>
"""

from __future__ import annotations

import json
import sys
import time

import psycopg2
import requests

from yuclaw.v5.swarm.agents import (
    ROLE_PROMPTS, MAX_FILING_CHARS, AGENT_NUM_PREDICT, AGENT_TEMPERATURE, NUM_CTX,
    validate_agent_output,
)
from yuclaw.v5.swarm.grounding import grade_agent

ROLES = ("bull", "bear", "skeptic")
# Same 5 filings as Day 3 (narratives already in swarm_inputs).
FILINGS = [
    ("0001645590-26-000052", "8-K/HPE"),
    ("0000320193-26-000013", "10-Q/AAPL"),
    ("0000097745-26-000018", "10-K/TMO"),
    ("0001193125-26-226746", "8-K/AMD"),
    ("0000200406-26-000087", "10-Q/JNJ"),
]


def _narrative(acc: str) -> dict | None:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT narrative_text, source_type, narrative_section, char_len "
                "FROM yuclaw_v5.swarm_inputs WHERE accession_number=%s", (acc,))
    row = cur.fetchone(); cn.close()
    if not row:
        return None
    return {"text": row[0], "source_type": row[1], "section": row[2], "char_len": row[3]}


def call_model(model: str, url: str, prompt: str, use_chat: bool,
               timeout: float = 600.0) -> tuple[str, float, dict]:
    """One worker call. /api/generate = raw prompt (no chat template, the 8B path);
    /api/chat = the model's own chat template applied (the fair path for an instruct model
    whose template differs from Llama's). format=json on both."""
    opts = {"temperature": AGENT_TEMPERATURE, "num_predict": AGENT_NUM_PREDICT, "num_ctx": NUM_CTX}
    t0 = time.perf_counter()
    if use_chat:
        # think=False is REQUIRED for thinking models (Gemma 4): otherwise the thinking
        # step consumes num_predict and message.content comes back empty. Harmless no-op
        # for non-thinking models (llama3.1:8b). This is the Phase-2 confound fix.
        body = {"model": model, "messages": [{"role": "user", "content": prompt}],
                "stream": False, "format": "json", "think": False, "options": opts}
        r = requests.post(f"{url}/api/chat", json=body, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        text = (data.get("message", {}).get("content") or "").strip()
    else:
        body = {"model": model, "prompt": prompt, "stream": False, "format": "json", "options": opts}
        r = requests.post(f"{url}/api/generate", json=body, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        text = (data.get("response") or "").strip()
    return text, time.perf_counter() - t0, data


def run_agent(role: str, filing_text: str, model: str, url: str, use_chat: bool,
              max_chars: int) -> dict:
    prompt = ROLE_PROMPTS[role].replace("{text}", filing_text[:max_chars])
    try:
        text, elapsed, data = call_model(model, url, prompt, use_chat)
    except Exception as e:
        return {"role": role, "error": f"{type(e).__name__}: {e}"[:300]}
    wellformed, raw = True, {}
    try:
        raw = json.loads(text) if text else {}
        if not isinstance(raw, dict) or not raw:
            wellformed = False
    except Exception:
        wellformed = False
    out, warns = validate_agent_output(raw if isinstance(raw, dict) else {})
    g = grade_agent(out, filing_text[:max_chars])
    return {
        "role": role, "wellformed": wellformed, "schema_warnings": warns,
        "grounding_rate": g["grounding_rate"], "points_grounded": g["points_grounded"],
        "points_total": g["points_total"], "citations_total": g["citations_total"],
        "citations_verified": g["citations_verified"], "llama_secs": round(elapsed, 2),
        "raw_chars": len(text), "eval_count": data.get("eval_count"),
        "output_stance": out.get("stance", "")[:160],
        "points": [{"point": p["point"][:120], "grounded": p["grounded"],
                    "reason": p["discard_reason"]} for p in g["points"]],
    }


def main() -> int:
    arm = sys.argv[1]
    model = sys.argv[2]
    url = sys.argv[3].rstrip("/")
    use_chat = sys.argv[4] == "1"
    max_chars = int(sys.argv[5]) if len(sys.argv) > 5 else MAX_FILING_CHARS
    out_path = sys.argv[6] if len(sys.argv) > 6 else f"/tmp/ab_{arm}.json"

    print(f"=== ARM {arm}: model={model} url={url} chat={use_chat} max_chars={max_chars} ===")
    results = []
    for acc, tag in FILINGS:
        nar = _narrative(acc)
        if not nar:
            print(f"  {tag} {acc}: NO narrative in swarm_inputs"); continue
        per = {"acc": acc, "tag": tag, "char_len": nar["char_len"],
               "fed_chars": min(nar["char_len"], max_chars), "agents": {}}
        for role in ROLES:
            r = run_agent(role, nar["text"], model, url, use_chat, max_chars)
            per["agents"][role] = r
            if "error" in r:
                print(f"  {tag:>10} {role:>8}: ERROR {r['error']}")
            else:
                print(f"  {tag:>10} {role:>8}: gr={r['grounding_rate']} "
                      f"grounded={r['points_grounded']}/{r['points_total']} "
                      f"cites={r['citations_verified']}/{r['citations_total']} "
                      f"wf={r['wellformed']} {r['llama_secs']}s")
        results.append(per)

    # roll-up
    summary = {}
    for role in ROLES:
        rates, fid, wf, lat = [], [], [], []
        for p in results:
            a = p["agents"].get(role, {})
            if "error" in a:
                continue
            rates.append(a["grounding_rate"])
            if a["citations_total"]:
                fid.append(a["citations_verified"] / a["citations_total"])
            wf.append(1 if a["wellformed"] else 0)
            lat.append(a["llama_secs"])
        summary[role] = {
            "mean_grounding": round(sum(rates) / len(rates), 3) if rates else None,
            "mean_citation_fidelity": round(sum(fid) / len(fid), 3) if fid else None,
            "wellformed_rate": round(sum(wf) / len(wf), 3) if wf else None,
            "mean_latency_s": round(sum(lat) / len(lat), 1) if lat else None,
        }
    blob = {"arm": arm, "model": model, "url": url, "use_chat": use_chat,
            "max_chars": max_chars, "summary": summary, "per_filing": results}
    with open(out_path, "w") as f:
        json.dump(blob, f, indent=2)
    print("\n=== ARM SUMMARY ===")
    for role in ROLES:
        s = summary[role]
        print(f"  {role:>8}: grounding={s['mean_grounding']} fidelity={s['mean_citation_fidelity']} "
              f"wellformed={s['wellformed_rate']} latency={s['mean_latency_s']}s")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
