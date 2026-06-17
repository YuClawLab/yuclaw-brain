# v5 Layer 1 — Worker-tier A/B: llama3.1:8b vs Gemma 4 (26B MoE)

Branch `v5-layer1`. Decides, on YUCLAW's real metrics (grounding rate + citation fidelity),
whether **Gemma 4** is a better Bull/Bear/Skeptic **worker** than **llama3.1:8b**. The 70B is
the synthesis model and was **NOT under test** — so this is agent-only (no synthesis), which
also kept Gemma and the 70B from ever being co-resident.

## Setup

- **Worker A:** `llama3.1:8b` on the production Ollama (0.18.0, port 11434).
- **Worker B:** `gemma4:26b-a4b-it-q4_K_M` — MoE, **25.8B total / 3.8B active**, Q4_K_M, 18 GB,
  **262 144 (256K) context**, instruction-tuned. `ollama show` reports `requires 0.20.0`.
- **Production Ollama is 0.18.0, which cannot load any Gemma 4** (support landed in 0.20.0).
  Rather than upgrade the shared production daemon (it serves the resident 70B + cron jobs), an
  **isolated Ollama 0.30.9** was run in user space on **port 11500** with its own
  `OLLAMA_MODELS` dir. The production daemon and its models were never touched. Gemma loaded on
  **GPU (100%)** on the isolated instance.
- **Inputs:** the Day-3 prose-extracted MD&A narratives (`yuclaw_v5.swarm_inputs`) for the same
  5 filings used in the Day-3 validation (8-K HPE/AMD, 10-Q AAPL/JNJ, 10-K TMO). No re-fetch.
- **Identical except the worker model:** same prompts (`agents.ROLE_PROMPTS`), same deterministic
  citation verifier (`grounding.grade_agent`), same 6000-char input window, temp 0.2.

## Phase-2 confound — the result that would have buried Gemma

On the first smoke, Gemma scored **grounding 0.0, wellformed=False on every agent**. Diagnosed
before concluding (as required) — it was a **harness/template confound, not the model**:

- **`/api/generate`** (raw prompt, the 8B path): Gemma started valid JSON then **degenerated into
  a repetition loop** (`{"stance": "...regulatory-drive ... de la de de de de de...`). Classic
  symptom of feeding an instruction-tuned model a prompt without its chat template.
- **`/api/chat`** (Gemma's template) but default thinking on: **empty content** — Gemma 4 is a
  *thinking* model and the thinking step consumed the `num_predict` budget.
- **`/api/chat` + `think:false`**: clean, schema-correct JSON, **grounding 1.0** on the smoke.

**Fix (harness):** call workers via `/api/chat` with `think:false`. For fairness BOTH arms were
then run via `/api/chat` (each model gets its own chat template). `think:false` is a no-op for the
non-thinking 8B. This is exactly the "fixable harness bug, not a verdict on the model" the plan
anticipated — the naive 0.0 was an artifact.

## The A/B (both via /api/chat, 6000-char window, 5 filings)

Mean per-agent across the 5 filings:

| agent | metric | 8B@chat | **Gemma 4@chat** |
|-------|--------|--------:|-----------------:|
| bull    | grounding | 0.58 | **1.00** |
|         | citation fidelity | 0.80 | **1.00** |
|         | latency/agent | 15.3s | **12.6s** |
| bear    | grounding | 0.80 | **0.93** |
|         | citation fidelity | 0.82 | **0.93** |
|         | latency/agent | 17.3s | **9.7s** |
| skeptic | grounding | 0.75 | **0.82** |
|         | citation fidelity | **0.95** | 0.78 |
|         | latency/agent | 17.5s | **11.0s** |
| **mean** | **grounding** | **0.71** | **0.92** |
|          | **citation fidelity** | 0.86 | **0.90** |
|          | **latency/agent** | 16.7s | **11.1s** |
| both | well-formed | 1.00 | 1.00 |

Reference: `8B@generate` (the production path) scored mean grounding 0.64 / fidelity 0.77 —
i.e. switching 8B to `/api/chat` slightly helped it too, so the comparison above is not
flattering Gemma by endpoint choice.

## Context dimension

Gemma's 262K context lets it ingest far more than the 6000-char window. Re-running the Gemma
arm at the **full 16000-char** stored narrative (2.7× the window; `num_ctx` 16384):

| agent | Gemma@6k (grounding / fidelity) | Gemma@16k (grounding / fidelity) |
|-------|-------------------------------:|--------------------------------:|
| bull    | 1.00 / 1.00 | 0.85 / 0.97 |
| bear    | 0.93 / 0.93 | 0.78 / 0.82 |
| skeptic | 0.82 / 0.78 | 0.65 / 0.80 |

Two honest takeaways:

1. **It ingests the larger context cleanly** — 100% well-formed, no chunking, only a modest
   latency bump (~11s → ~13s). The 256K capability is real and works on the GB10; a full 10-K
   MD&A (50–150k chars) would fit in one shot where the 8B (run here at `num_ctx` 8192 to bound
   KV cache) would need chunking.
2. **More context did NOT raise grounding — it slightly lowered the rate.** With more MD&A in
   front of it, Gemma makes *more and bolder* claims (more citations per agent), and a larger
   share of those claims aren't fully verbatim-grounded (usually a figure that sits just outside
   its cited span). Citation *fidelity* stays high. So the 256K window is a **capability for
   future full-document work, not a free grounding win at the current prompt** — exploiting it
   well would need prompt tuning ("ground every claim" scales worse as material grows). The
   apples-to-apples verdict below is at the production 6000-char operating point.

## Verdict

**Gemma 4 (26B MoE) is a clearly better worker than llama3.1:8b on YUCLAW's metrics — adopt it
as the worker tier, pending the Ollama-version decision.** This is not a forced win:

- **Grounding +29%** (0.92 vs 0.71 mean) — driven by the bull going 0.58 → **1.00** and bear
  0.80 → 0.93. The model grounds claims in verbatim MD&A far more reliably.
- **Citation fidelity comparable-to-better** (0.90 vs 0.86). The one place 8B leads is the
  **skeptic** (0.95 vs 0.78) — Gemma's skeptic occasionally cited a near-miss span. Worth a prompt
  tweak, not a blocker.
- **~1.5× faster** (11.1s vs 16.7s/agent) despite being a 26B model — the 4B-active MoE plus the
  GB10 makes it genuinely quicker than the dense 8B.
- **100% well-formed** once the template confound is fixed.

## Footprint (standing Gemma up as the permanent worker tier)

- Gemma resident ≈ **18 GB** vs 8B's ~6 GB (+12 GB).
- Worker + synthesis resident: **Gemma 18 GB + 70B 42 GB ≈ 60 GB** on the 128 GB unified memory
  → ~**59 GB margin** (vs 8B+70B ≈ 48 GB). Comfortable. Workers run sequentially with synthesis,
  so peak is well under this.
- **Adoption cost / blocker:** Gemma 4 needs **Ollama ≥0.20**; production is **0.18.0**. Adopting
  it means either upgrading the production Ollama (a production change, verify the 70B after) or
  keeping a pinned newer Ollama for the worker tier. This is a VinZhang decision — flagged, not
  taken.

## Safety

Branch-only, no deploy. Production Ollama (0.18, 11434) + its models untouched; isolated Ollama
0.30.9 on 11500 with a separate models dir. `public.*` read-only; `swarm_inputs` reused (Day-3).
No Gemma+70B co-residence (agent-only). 70B-heavy steps kept clear of the `:00/:30` cron. main/Lab
worktrees untouched.

## Cross-references
- Harness: `yuclaw/v5/swarm/worker_ab.py`, `tests/smoke_gemma.py`
- Inputs: Day-3 `yuclaw_v5.swarm_inputs` (`docs/v5/layer1/day3.md`)
- Verifier: `yuclaw/v5/swarm/grounding.py`
