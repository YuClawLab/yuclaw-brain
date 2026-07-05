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
# Validation Lab (added 2026-07-05 — was a one-time v4.2 artifact and went
# stale; now rebuilt daily so the page's freshness stamp stays honest).
/usr/bin/python3 -m v3.web.render_validation_lab || exit 6
# AI-ETF Evidence module + Lab replay bundle (added 2026-07-05, Deng Part 2 —
# same freshness contract as the Lab).
/usr/bin/python3 -m v3.web.render_etf_evidence || exit 7
/usr/bin/python3 -m v3.lab.replay_export || exit 8

# Commit + push from the main checkout. We don't want to fail the cron chain
# if there's literally nothing to commit (signals unchanged between runs).
cd "$REPO_DIR" || { echo "[refresh_v3_pages] cd $REPO_DIR failed"; exit 1; }
/usr/bin/git add docs/index.html docs/validation.html docs/validation_lab.html \
                 docs/etf_evidence.html docs/replay/lab_replay_bundle.json

if /usr/bin/git diff --cached --quiet; then
    echo "[refresh_v3_pages] no page changes at $TS — skip commit"
    exit 0
fi

/usr/bin/git commit -m "auto: v3.0 page refresh $TS" || exit 4
/usr/bin/git push origin main || exit 5
echo "[refresh_v3_pages] pushed at $TS"
