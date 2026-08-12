#!/bin/bash
# Daily public-page refresh — landing + validation pages get rebuilt from
# the just-written signal_snapshots / track_record state, then committed
# and pushed so GitHub Pages picks them up.
#
# Runs in the daily pipeline (cron 0 17 * * 1-5) AFTER:
#   v3.signal.healthcheck → snapshot_writer → outcome_updater → radar → ledger.
#
# POSIX-clean (cron defaults to /bin/sh; SHELL=/bin/bash header in the crontab
# also covers us, but no bashisms used here either).
#
# Failure modes:
#   - Render fails → exit with the failure code; cron `&&` short-circuits.
#   - Nothing changed (signals identical between runs) → git commit returns
#     non-zero; this script tolerates that and exits 0.

set -u

REPO_DIR="/home/zhangd2/yuclaw"
TS=$(date -u +"%Y-%m-%d %H:%M UTC")

# Run renders from the main checkout so the v3/web/render_landing.py module
# (which lives on main) is importable. The v3.0-evidence worktree is the
# v3 development tree; main holds the launch-published code.
cd "$REPO_DIR" || { echo "[refresh_v3_pages] cd $REPO_DIR failed"; exit 1; }

# Traffic archiver FIRST and non-fatal (2026-08-06): GitHub only retains a
# rolling 14-day traffic window, so this must run before any gate below can
# abort the chain — and a GitHub hiccup must never block the page pipeline.
# Weekend days are covered by the window on Monday's run; the merge dedupes.
/bin/bash tools/traffic_archive.sh || echo "[refresh_v3_pages] traffic archive failed (non-fatal)"
# No.5 macro accrual (order 2026-08-10g): POINT_IN_TIME forward accrual of
# the FRED/EIA/futures context series — research-internal substrate only,
# feeds no page or score; non-fatal by design (archiver pattern). FRED
# series self-skip while FRED_API_KEY is absent from ~/.yuclaw_env.
/usr/bin/python3 -m v3.sources.macro_series --accrue || echo "[refresh_v3_pages] macro accrual failed (non-fatal)"

# Generate fresh pages — output paths default to $REPO_DIR/docs/.
/usr/bin/python3 -m v3.web.render_landing || exit 2
/usr/bin/python3 -m v3.track.render_html || exit 3
# Replay bundle FIRST (usefulness build 2026-07-16): the Lab evidence packet
# bundles it, and the packet manifest must exist before pages render their
# "Download evidence packet" blocks.
/usr/bin/python3 -m v3.lab.replay_export || exit 8
/usr/bin/python3 -m v3.web.evidence_packets || exit 10
# AI evidence layer (2026-08-01): machine-readable index for agents.
/usr/bin/python3 tools/yuclaw_evidence_index.py || exit 22
# Statistic audit-diff (2026-08-01): headline changes with cause tags.
/usr/bin/python3 tools/yuclaw_audit_diff.py || echo "[refresh_v3_pages] audit diff failed (non-fatal)"
# Validation Lab (added 2026-07-05 — was a one-time v4.2 artifact and went
# stale; now rebuilt daily so the page's freshness stamp stays honest).
/usr/bin/python3 -m v3.web.render_validation_lab || exit 6
# AI-ETF Evidence module (added 2026-07-05, Deng Part 2 — same freshness
# contract as the Lab).
/usr/bin/python3 -m v3.web.render_etf_evidence || exit 7
# XLK lens (second sector lens, admission-standard-driven; 2026-07-31).
/usr/bin/python3 -m v3.web.render_xlk_evidence || exit 21
# Canada Resources Evidence — evidence-tier vertical (added 2026-07-14, Phase 2;
# same freshness contract; the tier is never scored — see v3/universe_tiers.py).
/usr/bin/python3 -m v3.web.render_canada_resources || exit 9
# Usefulness-build pages (2026-07-16): daily evidence changes (+30-day
# archive), Suncor trace, replication, positioning. Counts + classifications.
/usr/bin/python3 -m v3.web.render_todays_evidence || exit 11
/usr/bin/python3 -m v3.web.render_trace_su || exit 12
/usr/bin/python3 -m v3.web.render_replication || exit 13
/usr/bin/python3 -m v3.web.render_lane || exit 14
# Signal Review product page (2026-08-04; counsel-armed, no-form gate below).
/usr/bin/python3 -m v3.web.render_signal_review || exit 29
# Universe Surface (2026-08-04): ECS artifact refresh (no run line) then
# Explorer + 79 Why pages + Sectors + Tour — display layer, no statistics.
/usr/bin/python3 tools/yuclaw_evidence_coverage.py --refresh || exit 31
/usr/bin/python3 -m v3.web.render_explorer || exit 32
/usr/bin/python3 -m v3.web.render_why_pages || exit 33
/usr/bin/python3 -m v3.web.render_sectors || exit 34
/usr/bin/python3 -m v3.web.render_tour || exit 35
/usr/bin/python3 -m v3.web.render_methodology || exit 37
# v5.3 Ground Truth: why-JSON API + endpoints, AI-builders page (live
# passport), EvidenceBench page; bench items regenerate weekly (Fridays).
/usr/bin/python3 -m v3.web.render_why_json || exit 38
/usr/bin/python3 -m v3.web.render_ai_builders || exit 39
if [ "$(date +%u)" = "5" ]; then
    /usr/bin/python3 tools/yuclaw_evidencebench.py generate || exit 40
    /usr/bin/python3 tools/yuclaw_evidencebench.py selfscore || exit 40
fi
/usr/bin/python3 -m v3.web.render_evidencebench || exit 41

# Synthesis-layer snapshot archive (2026-07-22): per-lens LensSnapshot JSON to
# output/synthesis/ — the delta baseline for research briefs. Box-local only
# (not committed); previews under docs/preview are owner-gated, not rebuilt here.
/usr/bin/python3 tools/yuclaw_synthesis_run.py --archive-only || exit 17

# Language rail (pages mode): regenerated prose must stay inside the locked
# public vocabulary. Hard gate before anything is committed — same contract
# as the deploy-verify gate below (nonzero exit aborts the chain).
/usr/bin/python3 tools/check_language.py --pages docs/*.html README.md COMPARISON.md || exit 16
# Copy-integrity rail (2026-07-22): clipped decimals, unclosed parens,
# cut-off paragraphs, dead local links — same hard-gate contract.
/usr/bin/python3 tools/check_copy_integrity.py docs/*.html || exit 18

# Protocol-registry chain verify (2026-07-23): the pre-registration ledger
# must load with an intact hash chain — tamper or truncation aborts the chain.
/usr/bin/python3 -c "import sys; sys.path.insert(0, 'tools'); \
from yuclaw_protocol_registry import Registry; \
Registry('registry/protocols.jsonl').verify_chain(); \
print('[registry] chain OK')" || exit 19

# Monday board (2026-07-27): internal status page, generate-only, never
# deployed, never fatal to the public chain.
/usr/bin/python3 tools/yuclaw_board.py || echo "[refresh_v3_pages] board generation failed (non-fatal)"

# C2 shadow challenger accrual (v5.2, 2026-07-31): parallel table only,
# structurally isolated from the composite; non-fatal.
/usr/bin/python3 tools/yuclaw_c2_challenger.py || echo "[refresh_v3_pages] c2 challenger failed (non-fatal)"

# Weekly evidence note (2026-08-01): Fridays only; auto-drafted, railed at build.
if [ "$(date +%u)" = "5" ]; then
    /usr/bin/python3 tools/yuclaw_weekly_note.py || exit 23
fi
# Note-reconciliation gate (P0.4, 2026-08-01): the published note must agree
# with the registry and the evidence store — hard gate whenever a note exists.
/usr/bin/python3 tools/check_weekly_note.py || exit 24
# Universe-integrity gate (P1.7): threshold-table match + delisting watch.
/usr/bin/python3 tools/check_universe_integrity.py || exit 25
# U350 isolation gate (Phase 0, 2026-08-02): cross-universe refusals proven
# by attempt on every build; U79 is inviolable.
/usr/bin/python3 tools/check_u350_isolation.py || exit 26
# Schema gate (2026-08-04): today's real outputs vs the frozen v1 API schemas.
/usr/bin/python3 tools/check_schemas.py || exit 28
# No-form/upload/payment gate (2026-08-04): docs/ never collects data or money.
/usr/bin/python3 tools/check_no_forms.py || exit 30
# Index-completeness gate (audit F2, 2026-08-05): machine surface never lags.
/usr/bin/python3 tools/check_index_completeness.py || exit 36

# Stranger-walk gate (2026-07-23): every public page reachable ≤3 clicks,
# shared header, freshness stamp, no dead links/anchors, disclaimer present.
/usr/bin/python3 tools/check_site_walk.py || exit 20
# Header-layout gate (2026-08-07 clean-header order): zero stamps in any
# header, exactly one stamp per page anywhere, badge == package version.
/usr/bin/python3 tools/check_header_layout.py || exit 43
# Truncation-ledger gate (Truncation & Error Budget v1, 2026-08-07, active
# immediately): every truncation/filter/cap has a ledger entry; anchored
# truncation code cannot drift without a same-commit ledger update; new
# cap constants / exclusion enums must be ledgered or allowlist-reviewed.
/usr/bin/python3 tools/check_truncation_ledger.py || exit 44
# Discovery-ledger gate (Discovery Ledger v1, 2026-08-10, active
# immediately): LEDGER-RECONCILIATION (kind=protocol chain lines <->
# hypothesis identities, bijection both directions, orphans fail) +
# FAMILY-LOCK (family membership immutable except by supersession with
# lineage); registry/discovery_ledger.json is derived, never
# hand-maintained — any divergence from the chain rebuild fails.
/usr/bin/python3 tools/check_discovery_ledger.py || exit 45
# Anytime-record gate (Anytime Evidence Record v1, 2026-08-11, active
# immediately): ANYTIME-PROSPECTIVE (retro-dated enrollment start fails —
# nothing is ever retrofitted) + ANYTIME-SCHEMA (missing required
# enrollment field fails) + ANYTIME-RECONCILIATION
# (registry/anytime_record.json is derived, never hand-maintained).
/usr/bin/python3 tools/check_anytime_record.py || exit 46
# Anytime observer (order 2026-08-12a): nightly observation admission for
# the three enrolled instruments — C-1 strictly-after issuance, matured
# 20d outcomes only, locked e-process wealth updates, observations
# appended to the chained registry/anytime_observations.jsonl (the
# canonical chain is never written here). Non-fatal by design; the
# nightly "0 eligible observations" line IS the C-1 proof until the
# first post-start outcome matures (~2026-09-08).
/usr/bin/python3 tools/yuclaw_anytime_observer.py --nightly || echo "[refresh_v3_pages] anytime observer failed (non-fatal)"
# Completeness profile (2026-08-11): nightly counting-only regeneration,
# then derived-only-lineage gate — hand-maintained overrides fail.
/usr/bin/python3 tools/yuclaw_completeness_profile.py --write || exit 47
/usr/bin/python3 tools/check_completeness_profile.py || exit 47
# Research-state derivation (2026-08-11): renders registered artifacts
# only; byte-identical rebuild enforced.
/usr/bin/python3 tools/yuclaw_research_state.py --write || exit 48
/usr/bin/python3 tools/check_research_state.py || exit 48

# Commit + push from the main checkout. We don't want to fail the cron chain
# if there's literally nothing to commit (signals unchanged between runs).
cd "$REPO_DIR" || { echo "[refresh_v3_pages] cd $REPO_DIR failed"; exit 1; }
/usr/bin/git add docs/index.html docs/validation.html docs/validation_lab.html \
                 docs/etf_evidence.html docs/xlk_evidence.html \
                 docs/canada_resources.html \
                 docs/replay/lab_replay_bundle.json \
                 docs/packets docs/todays_evidence.html docs/evidence_changes \
                 docs/trace_su.html docs/replication.html docs/lane.html \
                 docs/evidence_index.json docs/llms.txt docs/weekly_note.html \
                 docs/signal_review.html docs/schemas \
                 docs/explorer.html docs/explorer_data.json docs/why \
                 docs/sectors.html docs/tour.html docs/methodology.html \
                 docs/capabilities.json docs/evidence docs/ledger \
                 docs/evidencebench docs/evidencebench.html docs/for_ai_builders.html \
                 registry/completeness_profile.json registry/research_state.json
# Observation chain exists only once the first observation is admitted
# (~2026-09-08); guarded add so an absent file never errors the chain.
[ -f registry/anytime_observations.jsonl ] && /usr/bin/git add registry/anytime_observations.jsonl

if /usr/bin/git diff --cached --quiet; then
    echo "[refresh_v3_pages] no page changes at $TS — skip commit"
    exit 0
fi

/usr/bin/git commit -m "auto: v3.0 page refresh $TS" || exit 4
# Push-race fix (order of 2026-07-27; the race fired Fri Jul 24 and hid an
# undeployed build until Sunday): rebase immediately before push, retry once
# after re-rebase, and on double failure alarm loudly (marker + Telegram)
# with distinct exit codes instead of a silent exit-5.
chmod +x /home/zhangd2/yuclaw/cron/push_alert.sh 2>/dev/null || true
. /home/zhangd2/yuclaw/cron/lib_push_retry.sh
push_with_retry origin main /tmp/yuclaw_push_failed.marker \
    /home/zhangd2/yuclaw/cron/push_alert.sh || exit $?
echo "[refresh_v3_pages] pushed at $TS"

# Pages check-and-kick (2026-08-06): a push does not reliably queue a Pages
# build — confirm builds/latest picked up HEAD, kick once if it didn't, wait
# for `built`. deploy_verify below can only poll; it cannot start a build.
/bin/bash tools/pages_build_kick.sh 600 || exit 42

# Deploy-verify: push ≠ live. Poll the public site until every artifact is
# byte-identical with this build (GitHub Pages deploy latency). Non-zero here
# means the site is stale — surfaced in the pipeline log + health monitor.
/usr/bin/python3 tools/deploy_verify.py --timeout 900 || exit 15
echo "[refresh_v3_pages] deploy-verified at $(date -u +'%Y-%m-%d %H:%M UTC')"
