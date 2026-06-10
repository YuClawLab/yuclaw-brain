# Post-Funding Follow-ups

Deliberately deferred items that cost money and/or external review. None block the
June 3 / v4.0 ship — they are tracked here (this repo has no GitHub-issue workflow in scope).

---

## 1. Securities-law review of the compliance notice (`draft-v0` → `v1`)

**Status:** placeholder shipping as-is for v4.0. Conservative by design.

**Current text** (`v4/api/schema.py::COMPLIANCE_NOTICE`, version tag `draft-v0`):
> YUCLAW research output. Not investment advice. Past performance does not guarantee future
> results. Signal labels are research classifications, not buy/sell recommendations.

**The swap is a one-line change.** Update the `COMPLIANCE_NOTICE` constant (and bump
`COMPLIANCE_TEXT_VERSION` to `"v1"`) in `v4/api/schema.py`; every downstream surface inherits it
automatically because they all reference the constant (the memo footer renders
`compliance.notice`; the share card renders `compliance_notice`; the OpenAPI + FastAPI
descriptions prepend it; the SDK keeps a verbatim copy in `sdk/yuclaw_py/_compliance.py`;
README/DISCLAIMER quote it). A grep for the current text finds every place to confirm.

The `tests/test_compliance_regression.py` guard ensures the block is never dropped during the swap.

**Plan:**
- **When:** post-funding (the review is not free and should be done once, on near-final wording).
- **Who:** a securities attorney (research-tool / not-investment-advice framing; "research
  classification" labels; the public-ledger verification claims).
- **Cost / time estimate:** ~$2–5K, ~2–4 weeks turnaround.
- **Deliverable:** approved `v1` wording + sign-off that the not-advice posture is sound for the
  "research classifications, not recommendations" model.

---

## 2. Other deferred (v4.1 roadmap, not legal)
- Repoint/rebuild the interactive dashboard as a research-only v4 interface (the v2.x dashboard
  was retired Day 10; the GitHub-Pages landing now points to `pip install yuclaw && yuclaw demo`).
- Multi-LLM extraction + cross-checking; Whisper audio ingestion; larger universe; hosted share
  links; a carefully-scoped public bearish/short research lane (still classifications, never advice).
