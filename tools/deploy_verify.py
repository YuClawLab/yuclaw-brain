#!/usr/bin/env python3
"""
Deploy-verify — push ≠ live (usefulness build, 2026-07-16).

After the daily chain pushes docs/ to GitHub Pages, this script fetches every
public page from the LIVE site and compares it against the local build,
polling until they match or the deadline passes. Exit 0 = every listed
artifact is live and byte-identical; exit 1 = at least one is stale/missing.

Probe hardening (2026-08-07, after the 301-body incident): the github.io
URLs 301 to the custom domain, and a probe that doesn't follow redirects
hashes the 162-byte nginx redirect page instead of content. Probes go to
the canonical https://yuclaw.ca origin, walk any redirect chain hop by hop,
and REFUSE to hash a response when any hop returned 3xx, the final status is
not 200, or the final URL is not under https://yuclaw.ca/.

Acceptance contract (V8-001 §3, 2026-09-15). A served body VERIFIES only when
it reproduces the frozen expected artifact identity — the exact sha-256 AND
byte length of the local build — at a clean 200 on the canonical origin, and
passes the artifact-kind check for its extension (JSON parses, JSONL lines
parse, HTML/PDF/ZIP carry their document signature). The former "body under
1 KB is never content" floor (2026-08-07) wrongly rejected genuine short
artifacts — the v7 release target manifest is 730 bytes — so identity
replaces it on every manifest-driven probe. A probe made WITHOUT an expected
identity keeps the 1 KB floor as a conservative legacy guard: there is no
blanket allow for small 200 bodies, and a Content-Type header alone never
verifies anything. Unknown or non-relative manifest paths and artifacts
missing from the local build are rejected before any probe.

Stdlib only. CLI:
    python3 tools/deploy_verify.py                 # poll up to 15 min
    python3 tools/deploy_verify.py --timeout 60    # one-shot-ish check
    python3 tools/deploy_verify.py --paths index.html lane.html
    python3 tools/deploy_verify.py --self-test     # offline identity proofs,
                                                   # then the live redirect probes
    python3 tools/deploy_verify.py --self-test --offline   # no network
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
BASE = "https://yuclaw.ca"           # canonical origin — serves 200 directly
CANONICAL_PREFIX = "https://yuclaw.ca/"
GITHUB_BASE = "https://yuclawlab.github.io/yuclaw-brain"  # 301s to BASE;
                                     # kept ONLY for the --self-test probe
MIN_BODY_BYTES = 1024                # legacy guard for probes WITHOUT an expected identity
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


@dataclass(frozen=True)
class Expected:
    """Frozen identity of one artifact, taken from the local build: the manifest side of the contract."""
    rel: str
    sha256: str
    length: int


def _valid_rel(rel: str) -> bool:
    """A manifest path is a normalised, relative, forward-slash path under docs/ — nothing else."""
    if not rel or rel != rel.strip() or "\\" in rel or rel.startswith("/") or "://" in rel:
        return False
    return all(part and part not in (".", "..") for part in rel.split("/"))


def expected_from_local(paths, docs: Path | None = None) -> tuple[dict[str, Expected], list[str]]:
    """Build the expected-identity manifest from the local build. Invalid or absent paths come back as missing."""
    docs = docs or (_REPO / "docs")
    expected: dict[str, Expected] = {}
    missing: list[str] = []
    for rel in paths:
        f = docs / rel if _valid_rel(rel) else None
        if f is None or not f.is_file():
            missing.append(rel)
            continue
        body = f.read_bytes()
        expected[rel] = Expected(rel=rel, sha256=_sha(body), length=len(body))
    return expected, missing


def _content_kind_ok(rel: str, body: bytes) -> tuple[bool, str | None]:
    """Artifact-kind check by extension — the artifact contract, not the transport's Content-Type header.
    Unknown extensions are governed by identity alone."""
    name = rel.rsplit("/", 1)[-1]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    try:
        if ext == "json":
            json.loads(body.decode("utf-8"))
            return True, None
        if ext == "jsonl":
            for n, line in enumerate(body.decode("utf-8").splitlines(), 1):
                if line.strip():
                    json.loads(line)
            return True, None
        if ext in ("html", "htm"):
            head = body.lstrip()[:16].lower()
            if head.startswith(b"<!doctype html") or b"<html" in body[:1024].lower():
                return True, None
            return False, "html: no document signature (<!doctype html> / <html>)"
        if ext == "pdf":
            return (True, None) if body.startswith(b"%PDF-") else (False, "pdf: no %PDF- signature")
        if ext == "zip":
            return (True, None) if body.startswith(b"PK") else (False, "zip: no PK signature")
        if ext in ("md", "txt"):
            body.decode("utf-8")
            return (True, None) if body else (False, "text: empty body")
    except (UnicodeDecodeError, ValueError) as e:
        return False, f"{ext}: not well-formed ({e.__class__.__name__}: {str(e)[:80]})"
    return True, None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface every 3xx as an HTTPError so the chain is walked by hand."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _probe(url: str, follow: bool = True, expected: Expected | None = None) -> tuple[bytes | None, str | None]:
    """Fetch url like `curl -L`, walking redirects hop by hop.

    Returns (body, None) only when EVERY guard passes:
      - no 3xx anywhere in the chain (a redirect body must never be
        mistaken for content — 2026-08-07 incident),
      - final status 200 at a final URL under https://yuclaw.ca/,
      - with an expected identity: byte length AND sha-256 equal to the
        frozen local artifact, and the artifact-kind check passes;
      - without one (legacy callers): body >= 1 KB.
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
        if expected is None:
            if len(body) < MIN_BODY_BYTES:
                return None, (f"body {len(body)} bytes < {MIN_BODY_BYTES} with no expected identity — "
                              f"refusing to hash (legacy guard; redirect/error page?)")
            return body, None
        got = _sha(body)
        if len(body) != expected.length or got != expected.sha256:
            return None, (f"identity mismatch for {expected.rel}: served {len(body)} bytes sha256 {got[:12]}… "
                          f"!= expected {expected.length} bytes sha256 {expected.sha256[:12]}… — refusing "
                          f"(stale, truncated, wrong content or an error page)")
        ok, why = _content_kind_ok(expected.rel, body)
        if not ok:
            return None, f"artifact-kind check failed for {expected.rel}: {why}"
        return body, None
    return None, f"more than {MAX_HOPS} redirects from {url}"


class _FakeOpener:
    """Offline opener for --self-test: url -> (status, body, location)."""

    class _R:
        def __init__(self, url, status, body):
            self._url, self.status, self._body = url, status, body

        def read(self):
            return self._body

        def geturl(self):
            return self._url

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def __init__(self, routes):
        self.routes = routes

    def open(self, req, timeout=None):
        status, body, location = self.routes[req.full_url]
        if 300 <= status < 400:
            import email.message
            h = email.message.Message()
            h["Location"] = location
            raise urllib.error.HTTPError(req.full_url, status, "redirect", h, io.BytesIO(body))
        if status != 200:
            raise urllib.error.HTTPError(req.full_url, status, "error", None, io.BytesIO(body))
        return self._R(req.full_url, status, body)


def _self_test_offline() -> list[str]:
    """Prove the identity contract without the network: a valid 730-byte artifact verifies; the same
    length with different bytes does not; a small 200 body without an expected identity is still refused
    by the legacy floor; a redirect chain is refused even when it ends at the right bytes."""
    global _OPENER
    failures: list[str] = []
    manifest = json.dumps({"schema": "yuclaw-release-target/1", "note": "x" * 640}).encode()
    manifest = manifest[:730] if len(manifest) >= 730 else manifest + b" " * (730 - len(manifest))
    exp = Expected("packets/manifest.json", _sha(manifest), len(manifest))
    wrong = bytearray(manifest)
    wrong[-1] ^= 0x01
    routes = {
        f"{BASE}/ok.json": (200, manifest, None),
        f"{BASE}/wrong.json": (200, bytes(wrong), None),
        f"{BASE}/tiny.html": (200, b"<html>162-byte-ish redirect page</html>", None),
        f"{BASE}/hop.json": (301, b"<html>301</html>", f"{BASE}/ok.json"),
    }
    saved = _OPENER
    _OPENER = _FakeOpener(routes)
    try:
        body, err = _probe(f"{BASE}/ok.json", expected=exp)
        if body != manifest:
            failures.append(f"valid 730-byte artifact refused: {err}")
        else:
            print("[self-test] OK   730-byte artifact with matching identity verified")
        body, err = _probe(f"{BASE}/wrong.json", expected=exp)
        if body is not None or not err or "identity mismatch" not in err:
            failures.append(f"wrong bytes of the right length NOT refused (err={err})")
        else:
            print("[self-test] OK   same-length wrong bytes refused: identity mismatch")
        body, err = _probe(f"{BASE}/tiny.html")
        if body is not None or not err or "no expected identity" not in err:
            failures.append(f"small body without expected identity NOT refused (err={err})")
        else:
            print("[self-test] OK   small body without expected identity refused (legacy floor)")
        body, err = _probe(f"{BASE}/hop.json", expected=exp)
        if body is not None or not err or "3xx in chain" not in err:
            failures.append(f"redirect-to-correct-bytes NOT refused (err={err})")
        else:
            print("[self-test] OK   redirect chain refused even though it ends at the right bytes")
    finally:
        _OPENER = saved
    return failures


def _self_test(offline: bool = False) -> int:
    """Offline identity proofs first, then (unless --offline) the live redirect proofs: a probe of the
    github.io URL WITHOUT following redirects must be refused (that 301's 162-byte nginx body is what got
    hashed as 'content' on 2026-08-07), a followed probe must be refused by the 3xx-in-chain guard even
    though it ends at the canonical https URL, and a canonical probe of index.html must pass."""
    failures = _self_test_offline()
    if not offline:
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
                   help="prove the identity contract offline, then the live redirect guards")
    p.add_argument("--offline", action="store_true", help="with --self-test: skip the live probes")
    args = p.parse_args(argv)
    if args.self_test:
        return _self_test(offline=args.offline)

    paths = args.paths or DEFAULT_PATHS
    invalid = [rel for rel in paths if not _valid_rel(rel)]
    if invalid:
        print(f"[deploy-verify] invalid manifest path(s): {invalid}", file=sys.stderr)
        return 1
    expected, missing_local = expected_from_local(paths)
    if missing_local:
        print(f"[deploy-verify] local build missing: {missing_local}", file=sys.stderr)
        return 1

    pending = dict(expected)
    last_err: dict[str, str] = {}
    deadline = time.time() + args.timeout
    while pending:
        for rel in sorted(pending):
            data, err = _probe(f"{BASE}/{rel}", expected=pending[rel])
            if err:
                if last_err.get(rel) != err:      # log each new reason once
                    print(f"[deploy-verify] GUARD {rel}: {err}", file=sys.stderr)
                last_err[rel] = err
                continue
            last_err.pop(rel, None)
            if data is not None and _sha(data) == pending[rel].sha256 and len(data) == pending[rel].length:
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
