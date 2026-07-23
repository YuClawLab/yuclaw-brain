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

# Generate fresh pages — output paths default to $REPO_DIR/docs/.
/usr/bin/python3 -m v3.web.render_landing || exit 2
/usr/bin/python3 -m v3.track.render_html || exit 3
# Replay bundle FIRST (usefulness build 2026-07-16): the Lab evidence packet
# bundles it, and the packet manifest must exist before pages render their
# "Download evidence packet" blocks.
/usr/bin/python3 -m v3.lab.replay_export || exit 8
/usr/bin/python3 -m v3.web.evidence_packets || exit 10
# Validation Lab (added 2026-07-05 — was a one-time v4.2 artifact and went
# stale; now rebuilt daily so the page's freshness stamp stays honest).
/usr/bin/python3 -m v3.web.render_validation_lab || exit 6
# AI-ETF Evidence module (added 2026-07-05, Deng Part 2 — same freshness
# contract as the Lab).
/usr/bin/python3 -m v3.web.render_etf_evidence || exit 7
# Canada Resources Evidence — evidence-tier vertical (added 2026-07-14, Phase 2;
# same freshness contract; the tier is never scored — see v3/universe_tiers.py).
/usr/bin/python3 -m v3.web.render_canada_resources || exit 9
# Usefulness-build pages (2026-07-16): daily evidence changes (+30-day
# archive), Suncor trace, replication, positioning. Counts + classifications.
/usr/bin/python3 -m v3.web.render_todays_evidence || exit 11
/usr/bin/python3 -m v3.web.render_trace_su || exit 12
/usr/bin/python3 -m v3.web.render_replication || exit 13
/usr/bin/python3 -m v3.web.render_lane || exit 14

# Synthesis-layer snapshot archive (2026-07-22): per-lens LensSnapshot JSON to
# output/synthesis/ — the delta baseline for research briefs. Box-local only
# (not committed); previews under docs/preview are owner-gated, not rebuilt here.
/usr/bin/python3 tools/yuclaw_synthesis_run.py --archive-only || exit 17

# Language rail (pages mode): regenerated prose must stay inside the locked
# public vocabulary. Hard gate before anything is committed — same contract
# as the deploy-verify gate below (nonzero exit aborts the chain).
/usr/bin/python3 tools/check_language.py --pages docs/*.html || exit 16
# Copy-integrity rail (2026-07-22): clipped decimals, unclosed parens,
# cut-off paragraphs, dead local links — same hard-gate contract.
/usr/bin/python3 tools/check_copy_integrity.py docs/*.html || exit 18

# Protocol-registry chain verify (2026-07-23): the pre-registration ledger
# must load with an intact hash chain — tamper or truncation aborts the chain.
/usr/bin/python3 -c "import sys; sys.path.insert(0, 'tools'); \
from yuclaw_protocol_registry import Registry; \
Registry('registry/protocols.jsonl').verify_chain(); \
print('[registry] chain OK')" || exit 19

# Commit + push from the main checkout. We don't want to fail the cron chain
# if there's literally nothing to commit (signals unchanged between runs).
cd "$REPO_DIR" || { echo "[refresh_v3_pages] cd $REPO_DIR failed"; exit 1; }
/usr/bin/git add docs/index.html docs/validation.html docs/validation_lab.html \
                 docs/etf_evidence.html docs/canada_resources.html \
                 docs/replay/lab_replay_bundle.json \
                 docs/packets docs/todays_evidence.html docs/evidence_changes \
                 docs/trace_su.html docs/replication.html docs/lane.html

if /usr/bin/git diff --cached --quiet; then
    echo "[refresh_v3_pages] no page changes at $TS — skip commit"
    exit 0
fi

/usr/bin/git commit -m "auto: v3.0 page refresh $TS" || exit 4
/usr/bin/git push origin main || exit 5
echo "[refresh_v3_pages] pushed at $TS"

# Deploy-verify: push ≠ live. Poll the public site until every artifact is
# byte-identical with this build (GitHub Pages deploy latency). Non-zero here
# means the site is stale — surfaced in the pipeline log + health monitor.
/usr/bin/python3 tools/deploy_verify.py --timeout 900 || exit 15
echo "[refresh_v3_pages] deploy-verified at $(date -u +'%Y-%m-%d %H:%M UTC')"
