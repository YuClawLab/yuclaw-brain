"""Producer-prompt A/B: current (v2) vs tightened (v3) on a real, ground-truthed set.

Ground truth = the corrected-layer (yuclaw_v5.event_type_corrected): events rescued from
OTHER_MATERIAL into an L1 type test RECALL (does the tightened producer catch them AT SOURCE?);
events whose corrected type is OTHER_MATERIAL test PRECISION (does it create FALSE L1 tags?).

The live producer (v2.txt + sourcelock.EVENT_TYPES) is NOT modified — v3 is validated against a
local tightened enum (v2 + FINANCING + EARNINGS_RESULT). Usage:
  python3 -m v3.extract.prompt_ab v2|v3
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import httpx, psycopg2
from v3.extract.event_worker import (OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS,
                                     RAW_TEXT_MAX_CHARS, _FENCE_OPEN, _FENCE_CLOSE)

ENUM_V2 = {"EARNINGS_BEAT","EARNINGS_MISS","GUIDANCE_RAISE","GUIDANCE_CUT","M_AND_A_ANNOUNCE",
           "M_AND_A_CLOSE","REGULATORY_ACTION","EXEC_CHANGE","BUYBACK_ANNOUNCE","DIVIDEND_CHANGE",
           "PRODUCT_LAUNCH","LAWSUIT","PARTNERSHIP","CONTRACT_WIN","LAYOFFS","CAPACITY_CHANGE",
           "INSIDER_BUY","INSIDER_SELL","OTHER_MATERIAL"}
ENUM_V3 = ENUM_V2 | {"FINANCING", "EARNINGS_RESULT"}
L1 = {"EARNINGS_RESULT","EARNINGS_BEAT","GUIDANCE_RAISE","GUIDANCE_CUT","M_AND_A","FINANCING",
      "GOVERNANCE","REGULATORY_ACTION"}
# raw producer tags that map onto an L1 consumer type (the producer's own L1-equivalent vocabulary)
RAW_IS_L1 = {"EARNINGS_RESULT","EARNINGS_BEAT","GUIDANCE_RAISE","GUIDANCE_CUT","FINANCING",
             "M_AND_A_ANNOUNCE","M_AND_A_CLOSE","REGULATORY_ACTION"}


def _build(prompt_tmpl, ticker, st, raw):
    return (prompt_tmpl.replace("{{TICKER}}", ticker).replace("{{SOURCE_TYPE}}", st)
            .replace("{{RAW_TEXT}}", raw[:RAW_TEXT_MAX_CHARS]))


def _extract(prompt):
    r = httpx.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                   "options": {"temperature": 0.0, "num_predict": 600}}, timeout=OLLAMA_TIMEOUT_SECONDS)
    r.raise_for_status()
    t = (r.json().get("response") or "").strip()
    t = _FENCE_CLOSE.sub("", _FENCE_OPEN.sub("", t))
    s = t.find("{")
    if s == -1: return {"no_event": True}
    return json.JSONDecoder().raw_decode(t[s:])[0]


def main() -> int:
    ver = sys.argv[1] if len(sys.argv) > 1 else "v3"
    tmpl = Path(f"v3/extract/prompts/{ver}.txt").read_text()
    enum = ENUM_V2 if ver == "v2" else ENUM_V3  # v3/v4 add FINANCING + EARNINGS_RESULT
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True); cur = cn.cursor()
    # ground-truthed set: rescued-L1 (recall) + genuine OTHER_MATERIAL (precision)
    cur.execute("""
      (SELECT er.raw_id, e.ticker, er.source_type, er.raw_text, cc.corrected_event_type tru
       FROM yuclaw_v5.event_type_corrected cc JOIN public.events e ON e.event_id=cc.event_id
       JOIN public.events_raw er ON er.source_url=e.source_url
       WHERE cc.v4_event_type='OTHER_MATERIAL' AND cc.corrected_event_type IN
         ('FINANCING','EARNINGS_RESULT','M_AND_A','GOVERNANCE') ORDER BY cc.corrected_event_type LIMIT 14)
      UNION ALL
      (SELECT er.raw_id, e.ticker, er.source_type, er.raw_text, cc.corrected_event_type tru
       FROM yuclaw_v5.event_type_corrected cc JOIN public.events e ON e.event_id=cc.event_id
       JOIN public.events_raw er ON er.source_url=e.source_url
       WHERE cc.corrected_event_type='OTHER_MATERIAL' LIMIT 8)""")
    rows = cur.fetchall(); cn.close()
    print(f"=== PRODUCER A/B  prompt={ver}  enum={'V3(+FIN,+EARN)' if ver=='v3' else 'V2'}  N={len(rows)} ===")
    recall_hit = recall_tot = 0
    false_l1 = 0; om_tot = 0; emitted_l1 = 0; emitted_l1_correct = 0
    for rid, tk, st, raw, tru in rows:
        try:
            out = _extract(_build(tmpl, tk, st, raw or ""))
        except Exception as e:
            print(f"  {tk:6} raw_id={rid} FAIL {type(e).__name__}"); continue
        et = (out.get("event_type") or "NO_EVENT") if not out.get("no_event") else "NO_EVENT"
        valid = et in enum or et == "NO_EVENT"
        et_eff = et if valid else "INVALID"
        truth_is_l1 = tru in L1
        emit_is_l1 = et_eff in RAW_IS_L1
        tag = ""
        if truth_is_l1:
            recall_tot += 1
            if emit_is_l1: recall_hit += 1; tag = "recall-HIT"
            else: tag = f"recall-MISS(->{et_eff})"
        else:  # genuine OTHER_MATERIAL
            om_tot += 1
            if emit_is_l1: false_l1 += 1; tag = f"FALSE-L1(->{et_eff})!"
            else: tag = "correctly-not-L1"
        if emit_is_l1:
            emitted_l1 += 1
            if truth_is_l1: emitted_l1_correct += 1
        print(f"  {tk:6} truth={tru:16} emit={et_eff:18} {tag}")
    print(f"\n  RECALL (L1 caught at source): {recall_hit}/{recall_tot} = {recall_hit/max(1,recall_tot):.0%}")
    print(f"  PRECISION (emitted L1 that are truly L1): {emitted_l1_correct}/{max(1,emitted_l1)} = {emitted_l1_correct/max(1,emitted_l1):.0%}")
    print(f"  FALSE L1 tags on genuine OTHER_MATERIAL: {false_l1}/{om_tot}")
    print(f"RESULT {ver} recall={recall_hit}/{recall_tot} precision={emitted_l1_correct}/{max(1,emitted_l1)} false_l1={false_l1}/{om_tot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
