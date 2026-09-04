# YUCLAW — system architecture, operations, hardware

Moved from the README (2026-08-03) to keep the front page short. Read from
the live systemd units and `crontab -l`, not aspirational.

## System architecture

```
v3/
  signal/      9-component composite (C1..C9), supply-chain graph, cascade engine
  sources/     SEC EDGAR poller + backfill + Form 4 deterministic parser
  extract/     LLM extraction + SourceLock Guard + prose-first acquisition + live reclassify
  lab/         Validation Lab engines: cohorts, rigor stats, event study, replay bundle
  replay/      Time-machine replay engine
  track/       price_history + outcome_updater + In-Sample Validation panels
  proof/       Verified Research Ledger writer + verifier
  radar/       Change detector + Telegram / Email / Slack adapters
  api/         FastAPI REST server
  mcp/         FastMCP stdio server (7 tools)
  cli/         why / replay / replay-lab / validation / brief / watch / verify / profile
yuclaw/v5/     ClawFactory Layers 0–1: job queue, specialist swarm, grounding verifier
services/      systemd units + guarded worker + heartbeat + network self-heal
sdk/           yuclaw — public SDK (pip install yuclaw)
tools/         replay_lab.py — standalone stdlib reproduction script; protocol
               registry; language/site/universe gates
docs/methodology/   Methodology + limitations + leak audit + Lab methodology
```

## Operations — what's actually running

- **EDGAR poller** — systemd, always-on; 5-minute submissions sweep across the
  132-ticker coverage universe (79-name scoring universe + 53-filer evidence
  tier) resolving to ~110 distinct EDGAR CIKs (ETF share classes share
  issuer-trust CIKs; some macro instruments have no EDGAR CIK).
- **Event worker** — systemd timer, every 15 min, GPU-guarded: 70B extraction +
  SourceLock + live reclassify + prose-first persistence. Exits cleanly when
  the box is busy.
- **Daily pipeline** — weekdays 17:00 MDT: healthcheck → snapshots → outcomes →
  radar → ledger → page regeneration (landing, validation, Lab, evidence
  lenses, replay bundle) → gate suite (language rail, copy integrity,
  registry chain-verify, site walk, universe integrity) → deploy verify
  against the live site.
- **Health monitor** — every 30 min: prices, ingestion sweep age, Lab build age
  (staleness alarm), disk; writes an alert file on any failure.
- **Off-box heartbeat** — every 5 min: gist check-in + GitHub Actions dead-man
  watcher.
- **Network self-heal** — every 5–10 min: link/tailscale recovery; never touches
  a healthy link.
- **Telegram broadcast** — daily 07:35 MDT signal digest to `@yuclaw_signals`.
- **Research crons** — hourly–nightly: oil intelligence, sentiment archive,
  swarm debate (research-side, orthogonal to the signal pipeline).

## Hardware

- **GPU:** NVIDIA Grace Blackwell GB10 (128 GB unified memory), single box.
- **Models resident:** Llama 3.1 70B (Q4_K_M, 42 GB weights, ≈46 GB resident
  with its pinned context budget) + Gemma 4 26B A4B (17 GB weights, ≈20 GB
  resident) — both served by one local Ollama daemon under an explicit GPU
  mutex + memory-cap contract.
- **All local.** No cloud LLM calls anywhere in the pipeline. SEC EDGAR is the
  only external data source for the evidence layer.

## Made in Canada

YUCLAW is developed and operated in Canada by FarJasper Stories Canada, from Calgary, Alberta, on owner-controlled hardware.

---

*Research and education only — not investment advice. Signal labels are
research classifications, not buy/sell recommendations.*
