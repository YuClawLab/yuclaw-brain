#!/bin/sh
# install_precommit_anchor_guard.sh [--uninstall] — repository-scoped, checkout-enrolled, idempotent
# (V7-003F guard; dispatcher v2 for shared-worktree repositories, V7-004 A1).
#   install   : copies tools/hooks/pre-commit into the repository's common hooks dir (only if absent
#               or already ours) and enrolls THIS checkout (physical toplevel path) in local Git
#               metadata: yuclaw.anchorguard.enrolledtoplevel. Other worktrees stay unenforced.
#   --uninstall: removes only our marker hook and this checkout's enrollment.
# Refuses (exit 3): core.hooksPath set, a foreign pre-commit hook, or an enrollment of a different checkout.
set -eu
MARK="yuclaw-anchor-guard v2"
KEY="yuclaw.anchorguard.enrolledtoplevel"
TOP=$(git rev-parse --show-toplevel)
TOP_P=$(cd "$TOP" && pwd -P)
HOOKS=$(git rev-parse --git-path hooks)
case "$HOOKS" in /*) ;; *) HOOKS="$TOP/$HOOKS" ;; esac
DST="$HOOKS/pre-commit"
SRC="$TOP/tools/hooks/pre-commit"
if git config --get core.hooksPath >/dev/null 2>&1; then
    echo "[anchor-guard-install] REFUSE: core.hooksPath is set for this repository; compose manually" >&2; exit 3
fi
if [ "${1:-}" = "--uninstall" ]; then
    if [ -e "$DST" ] && grep -q "$MARK" "$DST"; then rm -f "$DST"; echo "[anchor-guard-install] removed $DST"; fi
    if git config --get-all "$KEY" 2>/dev/null | grep -qx "$TOP_P"; then git config --unset "$KEY" "^$(printf '%s' "$TOP_P" | sed 's/[.[\*^$/]/\\&/g')\$"; echo "[anchor-guard-install] un-enrolled this checkout"; fi
    exit 0
fi
[ -f "$SRC" ] || { echo "[anchor-guard-install] REFUSE: $SRC missing" >&2; exit 3; }
[ -f "$TOP/tools/check_truncation_anchors_staged.py" ] || { echo "[anchor-guard-install] REFUSE: checker missing in this checkout" >&2; exit 3; }
if [ -e "$DST" ] && ! grep -q "$MARK" "$DST"; then
    echo "[anchor-guard-install] REFUSE: a foreign pre-commit hook exists at $DST — not overwritten; compose manually" >&2; exit 3
fi
EXISTING=$(git config --get-all "$KEY" 2>/dev/null || true)
if [ -n "$EXISTING" ] && [ "$EXISTING" != "$TOP_P" ]; then
    echo "[anchor-guard-install] REFUSE: a different checkout is already enrolled; un-enroll it first (no silent re-enrollment)" >&2; exit 3
fi
if [ ! -e "$DST" ] || ! cmp -s "$SRC" "$DST" || [ ! -x "$DST" ]; then
    mkdir -p "$HOOKS"
    cp "$SRC" "$DST.tmp.$$" && chmod 755 "$DST.tmp.$$" && mv "$DST.tmp.$$" "$DST"
    grep -q "$MARK" "$DST" && [ -x "$DST" ] || { echo "[anchor-guard-install] verification failed" >&2; exit 2; }
    echo "[anchor-guard-install] installed $DST"
else
    echo "[anchor-guard-install] hook already installed (identical, executable): $DST"
fi
if [ -z "$EXISTING" ]; then git config --local "$KEY" "$TOP_P"; echo "[anchor-guard-install] enrolled this checkout"; else echo "[anchor-guard-install] checkout already enrolled"; fi
echo "[anchor-guard-install] guard: tools/check_truncation_anchors_staged.py; enforcement limited to the enrolled checkout"
