#!/usr/bin/env python3
"""
Deploy-verify — push ≠ live (usefulness build, 2026-07-16).

After the daily chain pushes docs/ to GitHub Pages, this script fetches every
public page from the LIVE site and compares content sha-256 against the local
build, polling until they match or the deadline passes. Exit 0 = every listed
artifact is live and byte-identical; exit 1 = at least one is stale/missing.

Probe hardening (2026-08-07, after the 301-body incident): the github.io
URLs 301 to the custom domain, and a probe that doesn't follow redirects
hashes the 162-byte nginx redirect page instead of content. Probes now go
to the canonical https://yuclaw.ca origin, walk any redirect chain hop by
hop, and REFUSE to hash a response when any hop returned 3xx, the final
status is not 200, the final URL is not under https://yuclaw.ca/, or the
body is under 1 KB (every published artifact is larger — a body that
small is a redirect/error page, never content).

Stdlib only. CLI:
    python3 tools/deploy_verify.py                 # poll up to 15 min
    python3 tools/deploy_verify.py --timeout 60    # one-shot-ish check
    python3 tools/deploy_verify.py --paths index.html lane.html
    python3 tools/deploy_verify.py --self-test     # prove the guards catch
                                                   # the old failure mode
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
BASE = "https://yuclaw.ca"           # canonical origin — serves 200 directly
CANONICAL_PREFIX = "https://yuclaw.ca/"
GITHUB_BASE = "https://yuclawlab.github.io/yuclaw-brain"  # 301s to BASE;
                                     # kept ONLY for the --self-test probe
MIN_BODY_BYTES = 1024
MAX_HOPS = 5

# Every public artifact the daily chain publishes (repo-relative under docs/).
DEFAULT_PATHS = [
    "index.html",
    "validation.html",
    "validation_lab.html",
    "etf_evidence.html",
    "xlk_evidence.html",
    "llms.txt",
    "evidence_index.json",
    "weekly_note.html",
    "canada_resources.html",
    "replication.html",
    "todays_evidence.html",
    "c6_posture_current.json",
    "lane.html",
    "signal_review.html",
    "explorer.html",
    "explorer_data.json",
    "sectors.html",
    "tour.html",
    # one generated Why page as the pattern representative (all 79 share
    # the pinned template; site-walk spot-checks 5 nightly)
    "why/AAPL.html",
    "why/AAPL.json",
    "capabilities.json",
    "evidence/verify.json",
    "evidencebench.html",
    "evidencebench/items.jsonl",
    "for_ai_builders.html",
    "trace_su.html",
    "usage.md",
    "examples/evidence_memo_su.md",
    # copy artifacts edited outside the daily renders (2026-07-23 rail
    # extension) — previously checked by hand after copy orders
    "YUCLAW_User_Guide_v5.1.pdf",
    "YUCLAW_User_Guide_v5.1_source.html",
    # versionless guide entry points (ORDER 2026-09-05B B1/B4) — the README
    # and every page link these; the versioned files stay for old links
    "YUCLAW_User_Guide.pdf",
    "YUCLAW_Guide_Utilisateur_FR.pdf",
    # French edition (2026-08-03). The English edition + live pages are
    # canonical per the FR guide's own final disclaimer ("En cas de
    # divergence, l'édition anglaise et les pages en direct font foi").
    "YUCLAW_Guide_Utilisateur_v5.1_FR.pdf",
    "YUCLAW_Guide_Utilisateur_v5.1_FR_source.html",
    "methodology/backfill.md",
    "methodology.html",
    "replay/lab_replay_bundle.json",
    "packets/manifest.json",
    "packets/yuclaw_validation_lab_packet.zip",
    "packets/yuclaw_open_index_evidence_packet.zip",
    "packets/yuclaw_canada_resources_packet.zip",
]

POLL_SECONDS = 30


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface every 3xx as an HTTPError so the chain is walked by hand."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _probe(url: str, follow: bool = True) -> tuple[bytes | None, str | None]:
    """Fetch url like `curl -L`, walking redirects hop by hop.

    Returns (body, None) only when EVERY guard passes:
      - no 3xx anywhere in the chain (a redirect body must never be
        mistaken for content — 2026-08-07 incident),
      - final status 200 at a final URL under https://yuclaw.ca/,
      - body >= 1 KB.
    Otherwise returns (None, reason)."""
    chain: list[int] = []
    for _ in range(MAX_HOPS):
        req = urllib.request.Request(url, headers={
            "User-Agent": "yuclaw-deploy-verify",
            "Cache-Control": "no-cache",
        })
        try:
            with _OPENER.open(req, timeout=30) as r:
                chain.append(r.status)
                body = r.read()
                final_url = r.geturl()
        except urllib.error.HTTPError as e:
            if 300 <= e.code < 400:
                chain.append(e.code)
                loc = e.headers.get("Location")
                if not follow:
                    return None, f"redirect {e.code} (not followed) at {url}"
                if not loc:
                    return None, f"redirect {e.code} without Location at {url}"
                url = urllib.parse.urljoin(url, loc)
                continue
            return None, f"HTTP {e.code} at {url}"
        except Exception as e:                        # noqa: BLE001
            return None, f"fetch error at {url}: {e}"
        if any(300 <= c < 400 for c in chain):
            return None, (f"3xx in chain {chain} — refusing to hash "
                          f"(final {final_url})")
        if chain[-1] != 200:
            return None, f"final status {chain[-1]} at {final_url}"
        if not final_url.startswith(CANONICAL_PREFIX):
            return None, f"final URL {final_url} is not {CANONICAL_PREFIX}…"
        if len(body) < MIN_BODY_BYTES:
            return None, (f"body {len(body)} bytes < {MIN_BODY_BYTES} — "
                          f"refusing to hash (redirect/error page?)")
        return body, None
    return None, f"more than {MAX_HOPS} redirects from {url}"


def _self_test() -> int:
    """Prove the guards catch the old failure mode: a probe of the
    github.io URL WITHOUT following redirects must be refused (that 301's
    162-byte nginx body is what got hashed as 'content' on 2026-08-07),
    and even a followed probe must refuse to hash because of the 3xx hops
    — since HTTPS enforcement (2026-08-07b) the followed chain is
    [301, 301, 200] ending at the canonical httpS URL, and the 3xx-in-
    chain guard must refuse it anyway. The canonical probe must pass."""
    failures = []
    url = f"{GITHUB_BASE}/index.html"
    body, err = _probe(url, follow=False)
    if body is not None or not err or "redirect" not in err:
        failures.append(f"-L-less github.io probe NOT refused (err={err})")
    else:
        print(f"[self-test] OK   -L-less probe refused: {err}")
    body, err = _probe(url, follow=True)
    if (body is not None or not err or "3xx in chain" not in err
            or CANONICAL_PREFIX not in err):
        failures.append(f"followed github.io probe NOT refused by the "
                        f"3xx-in-chain guard despite ending at the "
                        f"canonical https URL (err={err})")
    else:
        print(f"[self-test] OK   followed github.io probe refused: {err}")
    body, err = _probe(f"{BASE}/index.html")
    if body is None:
        failures.append(f"canonical probe failed: {err}")
    else:
        print(f"[self-test] OK   canonical probe passed "
              f"({len(body)} bytes, guards green)")
    for f in failures:
        print(f"[self-test] FAIL {f}", file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify the live site matches the local build")
    p.add_argument("--timeout", type=int, default=900, help="seconds (default 900)")
    p.add_argument("--paths", nargs="*", default=None, help="subset of paths")
    p.add_argument("--self-test", action="store_true",
                   help="prove the probe guards refuse the github.io 301 body")
    args = p.parse_args(argv)
    if args.self_test:
        return _self_test()

    paths = args.paths or DEFAULT_PATHS
    local: dict[str, str] = {}
    missing_local = []
    for rel in paths:
        f = _REPO / "docs" / rel
        if not f.exists():
            missing_local.append(rel)
        else:
            local[rel] = _sha(f.read_bytes())
    if missing_local:
        print(f"[deploy-verify] local build missing: {missing_local}", file=sys.stderr)
        return 1

    pending = dict(local)
    last_err: dict[str, str] = {}
    deadline = time.time() + args.timeout
    while pending:
        for rel in sorted(pending):
            data, err = _probe(f"{BASE}/{rel}")
            if err:
                if last_err.get(rel) != err:      # log each new reason once
                    print(f"[deploy-verify] GUARD {rel}: {err}", file=sys.stderr)
                last_err[rel] = err
                continue
            last_err.pop(rel, None)
            if data is not None and _sha(data) == pending[rel]:
                print(f"[deploy-verify] LIVE  {rel}")
                del pending[rel]
        if not pending:
            break
        if time.time() >= deadline:
            for rel in sorted(pending):
                why = last_err.get(rel, "live content does not match local build")
                print(f"[deploy-verify] STALE {rel} — {why}", file=sys.stderr)
            print(f"[deploy-verify] FAIL: {len(pending)}/{len(paths)} artifacts not live "
                  f"after {args.timeout}s", file=sys.stderr)
            return 1
        time.sleep(POLL_SECONDS)

    print(f"[deploy-verify] OK: all {len(paths)} artifacts live and byte-identical")
    return 0


if __name__ == "__main__":
    sys.exit(main())
