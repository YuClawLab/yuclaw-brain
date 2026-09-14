"""Offline verification packet (v7) — the principal outsider artifact.

BUILD: collect the PERMITTED public artifacts already on disk (frozen replay bundle, evidence packets
manifest + zips, capabilities.json, the research-chain file, release_manifest.json, the public
replication log), write a MANIFEST with exact sha256 + byte length per file, source/tree identity,
instructions and limitations. Nothing is fetched or recomputed; derived data only.

VERIFY (works without an account or hosted service): recompute every file's sha256 + length against
the manifest FIRST — a tampered or missing artifact fails before any replay runs; then call the
EXISTING replay path (v3.lab.replay_check._run) on the packet's own copy of the frozen bundle and
report success / mismatch / unsupported with the first actionable discrepancy. This is an operator
or outsider technical check of exact bytes and published statistics; it is never an outsider receipt
by itself, never a new statistical read, never a research interpretation.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
PERMITTED = [                                   # repo-relative; derived/public artifacts only
    "docs/replay/lab_replay_bundle.json",
    "docs/packets/manifest.json",
    "docs/packets/yuclaw_validation_lab_packet.zip",
    "docs/packets/yuclaw_open_index_evidence_packet.zip",
    "docs/packets/yuclaw_canada_resources_packet.zip",
    "docs/capabilities.json",
    "docs/evidence_index.json",
    "docs/replication/replication_log.json",
    "registry/protocols.jsonl",
    "release_manifest.json",
]
NEVER = ("internal/", ".env", "yuclaw_env", "docs/YUCLAW_User_Guide_v6", "docs/guide/")
MANIFEST = "PACKET_MANIFEST.json"
INSTRUCTIONS = "VERIFY.md"
LIMITS = [
    "Derived, public artifacts only: no raw vendor price rows, no filing bodies, no private records.",
    "Verification establishes exact bytes and reproduces published Lab statistics/ledger roots from the frozen bundle; it does not establish scientific validity, independence, or any investment conclusion.",
    "A successful verify by the project's own operator is NOT an outsider receipt. Outsider receipts require the receipt workflow (yuclaw receipts) and a designated review.",
    "The frozen bundle is the one published at the manifest's source commit; a later site state can differ legitimately.",
    "Research and education only — not investment advice.",
]


def _sha_len(p: Path) -> tuple[str, int]:
    b = p.read_bytes(); return hashlib.sha256(b).hexdigest(), len(b)


def _git(*a, cwd: Path = _REPO) -> str:
    r = subprocess.run(["git", "--no-optional-locks", *a], cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def source_root(explicit: str | Path | None = None) -> Path:
    """The checkout that holds the public artifacts: an explicit --source, else the package's own
    repo when run from a checkout, else the current directory (installed-wheel use)."""
    if explicit is not None:
        cand = Path(explicit)
        if (cand / "release_manifest.json").exists() and (cand / "docs").is_dir():
            return cand
        raise ValueError("--source is not a YUCLAW checkout with public artifacts (no silent fallback to another tree)")
    for cand in (_REPO, Path.cwd()):
        if (cand / "release_manifest.json").exists() and (cand / "docs").is_dir():
            return cand
    raise ValueError("no YUCLAW checkout with public artifacts found: pass --source <checkout>")


def build(out_dir: str | Path, *, repo: Path | None = None, now: datetime | None = None) -> dict:
    repo = source_root(repo)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    files = []
    for rel in PERMITTED:
        if any(rel.startswith(n) for n in NEVER):
            raise ValueError(f"refusing to package {rel}")
        src = repo / rel
        if not src.exists():
            files.append({"path": rel, "status": "ABSENT"}); continue
        dst = out / "artifacts" / rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, dst)
        h, n = _sha_len(dst); files.append({"path": rel, "sha256": h, "size_bytes": n, "status": "INCLUDED"})
    man = {"packet_format": "yuclaw-verification-packet/1", "built_at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
           "source": {"head": _git("rev-parse", "HEAD", cwd=repo), "tree": _git("rev-parse", "HEAD^{tree}", cwd=repo), "describe": _git("describe", "--tags", "--always", cwd=repo), "root": "checkout (path not recorded)"},
           "files": files, "limitations": LIMITS, "verify": "yuclaw packet verify <packet_dir>  (or: python3 -m v3.cli.packet verify <packet_dir>)",
           "replay_target": "docs/replay/lab_replay_bundle.json", "not_advice": "Research and education only. Not investment advice."}
    (out / MANIFEST).write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    (out / INSTRUCTIONS).write_text(instructions(man))
    return man


def instructions(man: dict) -> str:
    rows = "\n".join(f"| {f['path']} | {f.get('sha256', '—')} | {f.get('size_bytes', '—')} | {f['status']} |" for f in man["files"])
    return f"""# YUCLAW offline verification packet

Built {man['built_at']} from source `{man['source']['head']}` (tree `{man['source']['tree']}`).

## What you can establish with this packet
1. **Exact bytes** — every file below is bound by SHA-256 and byte length. `verify` recomputes them first; any change fails before anything runs.
2. **Reproduction of published statistics** — `verify` then runs the project's existing replay check on the packet's copy of the frozen Lab bundle and reports the first discrepancy if any.
3. **What it does not establish** — see limitations. Report a failure with the manifest digest and the first discrepancy line; do not edit the packet.

## Files
| path | sha256 | bytes | status |
|---|---|---|---|
{rows}

## Limitations
""" + "\n".join(f"- {l}" for l in man["limitations"]) + "\n\n## How to verify (no account, no service)\n\n```\n" + man["verify"] + "\n```\n"


def verify(packet_dir: str | Path) -> dict:
    """Returns {'result': 'SUCCESS'|'MISMATCH'|'UNSUPPORTED', 'first_discrepancy': str|None, 'checks': [...], 'manifest_digest': ...}."""
    pk = Path(packet_dir); mp = pk / MANIFEST
    if not mp.exists():
        return {"result": "UNSUPPORTED", "first_discrepancy": f"{MANIFEST} missing", "checks": [], "manifest_digest": None}
    try:
        man = json.loads(mp.read_text())
    except Exception as exc:
        return {"result": "UNSUPPORTED", "first_discrepancy": f"manifest unreadable: {exc}", "checks": [], "manifest_digest": None}
    mdig = hashlib.sha256(mp.read_bytes()).hexdigest()
    if man.get("packet_format") != "yuclaw-verification-packet/1":
        return {"result": "UNSUPPORTED", "first_discrepancy": "unknown packet_format", "checks": [], "manifest_digest": mdig}
    checks, first = [], None
    for f in man.get("files", []):
        if f.get("status") != "INCLUDED":
            checks.append({"path": f["path"], "check": "presence", "ok": None, "note": "absent at build"}); continue
        p = pk / "artifacts" / f["path"]
        if ".." in f["path"].split("/") or f["path"].startswith("/"):
            checks.append({"path": f["path"], "check": "path", "ok": False}); first = first or f"unsafe path {f['path']}"; continue
        if not p.is_file() or p.is_symlink():
            checks.append({"path": f["path"], "check": "presence", "ok": False}); first = first or f"missing artifact {f['path']}"; continue
        h, n = _sha_len(p); ok = (h == f["sha256"] and n == f["size_bytes"])
        checks.append({"path": f["path"], "check": "sha256+length", "ok": ok, "observed": {"sha256": h, "size_bytes": n}})
        if not ok:
            first = first or f"byte mismatch at {f['path']}: expected {f['sha256'][:16]}…/{f['size_bytes']} B, observed {h[:16]}…/{n} B"
    if first:
        return {"result": "MISMATCH", "first_discrepancy": first, "checks": checks, "manifest_digest": mdig, "replay": "NOT RUN (integrity failed first)"}
    bundle = pk / "artifacts" / man.get("replay_target", "docs/replay/lab_replay_bundle.json")
    if not bundle.exists():
        return {"result": "UNSUPPORTED", "first_discrepancy": "replay target not in packet", "checks": checks, "manifest_digest": mdig}
    from v3.lab import replay_check
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = replay_check._run(str(bundle))
    out = buf.getvalue().strip().splitlines()
    replay = {"exit": rc, "tail": out[-3:], "mode": "existing replay_check._run on the packet's bundle copy (offline)"}
    if rc == 0:
        return {"result": "SUCCESS", "first_discrepancy": None, "checks": checks, "manifest_digest": mdig, "replay": replay,
                "meaning": "exact bytes verified and published Lab statistics/ledger roots reproduced from the frozen bundle; not an outsider receipt, not a research interpretation"}
    diff = next((l for l in out if "MISMATCH" in l.upper() or "diff" in l.lower() or "≠" in l or "!=" in l), out[-1] if out else "replay returned nonzero")
    return {"result": "MISMATCH", "first_discrepancy": f"replay: {diff}", "checks": checks, "manifest_digest": mdig, "replay": replay}
