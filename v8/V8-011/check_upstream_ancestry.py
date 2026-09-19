#!/usr/bin/env python3
"""V8-011 §2 — pre-publication ancestry check (read-only; order record, never packaged).

Fetches the configured origin (a remote READ; nothing is pushed, tagged or dispatched) and answers one question before a
freeze or an authorization: can the candidate still be published to `main` as a plain fast-forward?

  python3 v8/V8-011/check_upstream_ancestry.py [--candidate <sha, default HEAD>] [--observed <sha of the tip last integrated>] [--no-fetch]

Exit 0  origin/main is an ancestor of the candidate: a non-force push would be a fast-forward against the tip seen just now.
Exit 3  STOP — origin/main is not an ancestor of the candidate (upstream moved, or the candidate was rebuilt from elsewhere).
        Nothing is forced, here or anywhere: integrate the new tip by a merge on the integration branch, re-render the
        weekly note, commit, and build and verify a NEW artifact pair bound to the new commit and tree.
The result holds only for the tip observed at the printed time. The nightly page refresh pushes to `main` every day at about
23:00 UTC, so run this again immediately before the freeze and again before the first public write; the publisher's own
push-main stage repeats the same test and pushes without force. Research and education only. Not investment advice.
"""
import argparse, subprocess, sys
from datetime import datetime, timezone

LAST_INTEGRATED = "5edb9e7e8502a11727b6174b8cc62f47107a6a91"          # origin/main as merged in ca96f574 (observed 2026-09-19T10:31:47Z)


def git(*a, check=True):
    return subprocess.run(["git", *a], capture_output=True, text=True, check=check)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--candidate", default="HEAD"); ap.add_argument("--observed", default=LAST_INTEGRATED); ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()
    if not a.no_fetch:
        f = git("fetch", "origin", check=False)
        if f.returncode != 0:
            print(f"STOP — could not fetch origin, so the current upstream tip is unknown: {f.stderr.strip()[:200]}"); return 3
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cand = git("rev-parse", a.candidate).stdout.strip(); tip = git("rev-parse", "origin/main").stdout.strip()
    print(f"observed {now}: origin/main = {tip}\ncandidate          = {cand} (tree {git('rev-parse', cand + '^{tree}').stdout.strip()})")
    if tip != a.observed:
        missing = git("log", "--format=%h %ad %s", "--date=iso", f"{cand}..{tip}").stdout.strip().splitlines()
        print(f"upstream moved since the last integrated tip {a.observed[:12]}: {len(missing)} commit(s) not in the candidate"); [print("   " + m) for m in missing[:20]]
    if git("merge-base", "--is-ancestor", tip, cand, check=False).returncode == 0:
        print("OK — origin/main is an ancestor of the candidate: a non-force push would be a fast-forward against this observed tip only."); return 0
    print("STOP — origin/main is NOT an ancestor of the candidate. Do not force anything. Integrate the new tip by a merge on the integration branch,\n"
          "re-render the weekly note, commit, then build and verify a NEW artifact pair bound to the new commit and tree before any freeze or authorization."); return 3


if __name__ == "__main__":
    sys.exit(main())
