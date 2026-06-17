"""Day-3.5 Worker A/B — Gemma one-filing smoke + confound check.

Runs Bull/Bear/Skeptic via a chosen worker model/endpoint on ONE 10-Q narrative, printing
grounding AND the raw model output, so a near-zero result can be diagnosed:
  (a) chat-template mismatch  -> well-formed but ungrounded, or odd text on /api/generate;
  (b) genuine failure to cite -> well-formed JSON, real attempt, quotes just not verbatim;
  (c) format/parse issue      -> malformed / empty output, wellformed=False.

Usage: python3 -m yuclaw.v5.swarm.tests.smoke_gemma <model> <url> <use_chat 0|1> [acc] [max_chars]
"""

from __future__ import annotations

import json
import sys

from yuclaw.v5.swarm.worker_ab import _narrative, run_agent, ROLES, MAX_FILING_CHARS

ACC = "0000320193-26-000013"  # AAPL 10-Q


def main() -> int:
    model, url, use_chat = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
    acc = sys.argv[4] if len(sys.argv) > 4 else ACC
    max_chars = int(sys.argv[5]) if len(sys.argv) > 5 else MAX_FILING_CHARS
    nar = _narrative(acc)
    if not nar:
        print(f"no narrative for {acc}"); return 2
    print(f"=== GEMMA SMOKE: {acc} model={model} url={url} chat={use_chat} "
          f"max_chars={max_chars} (narrative {nar['char_len']} chars, {nar['section']}) ===")
    for role in ROLES:
        r = run_agent(role, nar["text"], model, url, use_chat, max_chars)
        if "error" in r:
            print(f"\n--- {role.upper()}: ERROR {r['error']} ---"); continue
        print(f"\n--- {role.upper()}: grounding={r['grounding_rate']} "
              f"grounded={r['points_grounded']}/{r['points_total']} "
              f"cites={r['citations_verified']}/{r['citations_total']} "
              f"wellformed={r['wellformed']} raw_chars={r['raw_chars']} {r['llama_secs']}s ---")
        print(f"stance: {r['output_stance']}")
        for p in r["points"]:
            print(f"  [{'G' if p['grounded'] else 'X'}] {p['point']}"
                  + (f"  ({p['reason']})" if p["reason"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
