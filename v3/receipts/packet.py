"""Offline verification packet (v7) — the principal outsider artifact.

BUILD: collect the PERMITTED public artifacts already on disk (frozen replay bundle, evidence packets
manifest + zips, capabilities.json, the research-chain file, release_manifest.json, the public
replication log), write a MANIFEST with exact sha256 + byte length per file, source/tree identity,
instructions and limitations. Nothing is fetched or recomputed; derived data only.

VERIFY (works without an account or hosted service): (1) validate the manifest STRUCTURE before any
artifact is read — required fields, allowed statuses, full sha256, integer sizes, unique canonical
paths, and a replay target that names exactly one INCLUDED entry; (2) read every INCLUDED artifact
through a containment boundary (no absolute paths, no traversal, no symlink in any component of the
manifest, the artifact root or the artifacts) and recompute sha256 + length — a tampered or missing
artifact fails before any replay runs; (3) call the EXISTING replay path (v3.lab.replay_check._run) on
a PRIVATE copy of the exact verified bytes of the replay target (the bytes replayed are the bytes
verified; a target changed after the check cannot pass); (4) report success / mismatch / unsupported
with the first actionable discrepancy. Integrity and reproduction are reported separately from
PROVENANCE: matching a packet's own manifest never establishes that the packet is an official release
artifact — that needs an independently supplied trusted identity (`trusted=`). This is an operator or
outsider technical check of exact bytes and published statistics; it is never an outsider receipt by
itself, never a new statistical read, never a research interpretation.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import posixpath
import re
import shutil
import stat
import subprocess
import tempfile
import unicodedata
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
FORMAT = "yuclaw-verification-packet/1"
STATUSES = ("INCLUDED", "ABSENT")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
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



class PacketPathError(ValueError):
    """A manifest path or artifact could not be read inside the packet's containment boundary."""


def canonical_relpath(p) -> str | None:
    """Return `p` if it is a canonical, unambiguous, relative POSIX path; else None."""
    if not isinstance(p, str) or not p or len(p) > 512:
        return None
    if "\x00" in p or "\\" in p or any(ord(c) < 0x20 or ord(c) == 0x7F for c in p):
        return None
    if p.startswith(("/", "~")) or unicodedata.normalize("NFC", p) != p or posixpath.normpath(p) != p:
        return None
    parts = p.split("/")
    if any(part in ("", ".", "..") or part != part.strip() for part in parts):
        return None
    return p


def validate_manifest(man) -> tuple[dict | None, str | None]:
    """Structural validation BEFORE any artifact is read. Returns (normalized, None) or (None, error)."""
    if not isinstance(man, dict):
        return None, "manifest is not a JSON object"
    if man.get("packet_format") != FORMAT:
        return None, "unknown packet_format"
    files = man.get("files")
    if not isinstance(files, list):
        return None, "files: list required"
    seen, seen_fold, norm = set(), set(), []
    for i, f in enumerate(files):
        if not isinstance(f, dict):
            return None, f"files[{i}]: object required"
        st = f.get("status")
        if st not in STATUSES:
            return None, f"files[{i}]: status must be one of {list(STATUSES)}"
        want = {"path", "sha256", "size_bytes", "status"} if st == "INCLUDED" else {"path", "status"}
        if set(f) != want:
            return None, f"files[{i}]: keys must be exactly {sorted(want)} for status {st}"
        path = canonical_relpath(f.get("path"))
        if path is None:
            return None, f"files[{i}]: path is not a canonical relative path"
        if path in seen or path.casefold() in seen_fold:
            return None, f"files[{i}]: duplicate or ambiguous path {path!r}"
        seen.add(path); seen_fold.add(path.casefold())
        entry = {"path": path, "status": st}
        if st == "INCLUDED":
            h, n = f.get("sha256"), f.get("size_bytes")
            if not isinstance(h, str) or not _HEX64.match(h):
                return None, f"files[{i}]: sha256 must be 64 lowercase hex"
            if isinstance(n, bool) or not isinstance(n, int) or n < 0:
                return None, f"files[{i}]: size_bytes must be a nonnegative integer (booleans rejected)"
            entry.update(sha256=h, size_bytes=n)
        norm.append(entry)
    target = man.get("replay_target", "docs/replay/lab_replay_bundle.json")
    if canonical_relpath(target) is None:
        return None, "replay_target is not a canonical relative path"
    hits = [e for e in norm if e["path"] == target]
    if not hits:
        return None, f"replay_target {target!r} is not a listed artifact"
    if hits[0]["status"] != "INCLUDED":
        return None, f"replay_target {target!r} is ABSENT at build (a skipped target never qualifies)"
    lim = man.get("limitations", [])
    if not isinstance(lim, list) or any(not isinstance(x, str) for x in lim):
        return None, "limitations: list of strings required"
    src = man.get("source")
    if src is not None and not isinstance(src, dict):
        return None, "source: object or absent"
    return {"files": norm, "replay_target": target, "limitations": lim, "source": src}, None


_TEST_HOOK = None          # tests only: called as _TEST_HOOK(stage, rel) at "dir-opened" / "file-opened"; production leaves it None
_O_DIR = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
_O_FILE = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)


def platform_supported() -> tuple[bool, str]:
    """Descriptor-relative, no-follow opens are the containment mechanism. Without them verification is refused
    (an unsupported platform never silently drops the protection)."""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        return False, "platform lacks O_NOFOLLOW/O_DIRECTORY"
    if os.open not in os.supports_dir_fd or os.fstat is None:
        return False, "platform lacks descriptor-relative open (dir_fd)"
    return True, "ok"


def _is_link(name: str, dir_fd: int | None) -> bool:
    try:
        return stat.S_ISLNK(os.stat(name, dir_fd=dir_fd, follow_symlinks=False).st_mode)
    except OSError:
        return False


def _os_reason(exc: OSError, what: str, rel: str, name: str = "", dir_fd: int | None = None) -> str:
    import errno as _e
    if exc.errno == _e.ENOENT:
        return f"missing artifact {rel}" if what == "artifact" else f"missing directory component in {rel}"
    if exc.errno in (_e.ELOOP, _e.ENOTDIR) and name and _is_link(name, dir_fd):
        return f"symlink component in {rel} (refused; links are never followed)"
    if exc.errno == _e.ELOOP:
        return f"symlink component in {rel} (refused; links are never followed)"
    if exc.errno == _e.ENOTDIR:
        return f"non-directory component in {rel}"
    return f"cannot open {what} {rel} ({exc.__class__.__name__})"


def _open_dir(name: str, dir_fd: int | None, rel: str = "") -> int:
    try:
        return os.open(name, _O_DIR, dir_fd=dir_fd)
    except OSError as exc:
        raise PacketPathError(_os_reason(exc, "directory", rel or name, name, dir_fd)) from None


def _read_contained(root_fd: int, rel: str) -> bytes:
    """Read artifacts/<rel> through a chain of descriptor-relative, no-follow opens rooted at the pinned artifact
    root descriptor: every directory component is opened with O_NOFOLLOW|O_DIRECTORY relative to the previous
    descriptor, the file with O_NOFOLLOW relative to the last one, and the bytes come from that descriptor.
    A path component swapped for a symlink after its descriptor was taken cannot redirect the chain; the final
    descriptor is additionally required to be a regular file."""
    parts = rel.split("/")
    fds = []
    try:
        cur = root_fd
        for part in parts[:-1]:
            cur = _open_dir(part, cur, rel); fds.append(cur)
            if _TEST_HOOK is not None:
                _TEST_HOOK("dir-opened", rel)
        try:
            fd = os.open(parts[-1], _O_FILE, dir_fd=cur)
        except OSError as exc:
            raise PacketPathError(_os_reason(exc, "artifact", rel, parts[-1], cur)) from None
        fds.append(fd)
        if _TEST_HOOK is not None:
            _TEST_HOOK("file-opened", rel)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise PacketPathError(f"artifact {rel} is not a regular file")
        chunks = []
        while True:
            b = os.read(fd, 1 << 20)
            if not b:
                break
            chunks.append(b)
        return b"".join(chunks)
    except OSError as exc:
        raise PacketPathError(f"cannot read artifact {rel} ({exc.__class__.__name__})") from None
    finally:
        for f in fds:
            try:
                os.close(f)
            except OSError:
                pass


def _read_fd(fd: int) -> bytes:
    chunks = []
    while True:
        b = os.read(fd, 1 << 20)
        if not b:
            break
        chunks.append(b)
    return b"".join(chunks)


def load_trusted(path: str | Path) -> dict:
    """An INDEPENDENTLY supplied identity: {path: {sha256, size_bytes}} — accepts the packet-manifest shape
    ({"files": [...]}) obtained through a trusted channel, or a plain mapping."""
    obj = json.loads(Path(path).read_text())
    files = obj.get("files") if isinstance(obj, dict) and isinstance(obj.get("files"), list) else None
    out = {}
    items = files if files is not None else (list(obj.items()) if isinstance(obj, dict) else None)
    if items is None:
        raise ValueError("trusted identity: JSON object required")
    for it in items:
        if files is not None:
            if not isinstance(it, dict) or it.get("status", "INCLUDED") != "INCLUDED":
                continue
            p, h, n = it.get("path"), it.get("sha256"), it.get("size_bytes")
        else:
            p, v = it
            h, n = (v.get("sha256"), v.get("size_bytes")) if isinstance(v, dict) else (None, None)
        if canonical_relpath(p) is None or not isinstance(h, str) or not _HEX64.match(h) or isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError(f"trusted identity: malformed entry for {p!r}")
        out[p] = {"sha256": h, "size_bytes": n}
    if not out:
        raise ValueError("trusted identity: no INCLUDED entries")
    return out


def provenance(man: dict | None, checks: list, trusted: dict | None) -> dict:
    """Reported SEPARATELY from integrity/reproduction. Equality is derived ONLY from artifacts whose ACTUAL bytes
    were observed and equal the manifest (check ok=True) AND are covered by the independently supplied identity.
    Unread, missing, unreadable or mismatched artifacts are never assumed equal; an empty compared set is
    UNVERIFIED, never EQUAL. The compared set is stated explicitly — it is a subset comparison, not a statement
    about a whole release."""
    out = {"manifest_source": (man or {}).get("source"),
           "meaning": "integrity/reproduction concern the packet's own bytes; they never establish an official release artifact or an outsider verification"}
    listed = [e["path"] for e in (man or {}).get("files", []) if e.get("status") == "INCLUDED"]
    observed_ok = {c["path"]: c["observed"] for c in checks if c.get("check") == "sha256+length" and c.get("ok") is True and isinstance(c.get("observed"), dict)}
    unobserved = [p for p in listed if p not in observed_ok]
    if trusted is None:
        out.update(official_artifact_equality="UNVERIFIED", compared_set=[], observed_ok=sorted(observed_ok), unobserved=unobserved,
                   note="no independently supplied trusted identity: origin unverified (the packet's own manifest is not provenance)")
        return out
    compared = sorted(p for p in listed if p in observed_ok and p in trusted)
    equal = [p for p in compared if (trusted[p]["sha256"], trusted[p]["size_bytes"]) == (observed_ok[p]["sha256"], observed_ok[p]["size_bytes"])]
    differs = [p for p in compared if p not in equal]
    uncovered = [p for p in listed if p in observed_ok and p not in trusted]
    if not listed or not compared:
        eq = "UNVERIFIED"
    elif differs:
        eq = "DIFFERS"
    elif unobserved or uncovered:
        eq = "INCOMPLETE"
    else:
        eq = "EQUAL"
    out.update(official_artifact_equality=eq, compared_set=compared, equal=equal, differs=differs, unobserved=unobserved,
               uncovered_by_trusted_identity=uncovered, trusted_entries_not_in_packet=sorted(p for p in trusted if p not in listed), trusted_entries=len(trusted),
               scope="the compared set only (observed bytes ∩ trusted identity); never whole-release equality",
               note={"EQUAL": "every INCLUDED artifact's observed bytes equal the independently supplied identity; still not an outsider receipt",
                     "INCOMPLETE": "every compared artifact equals the trusted identity, but some INCLUDED artifacts were not observed or not covered",
                     "DIFFERS": "at least one observed artifact differs from the trusted identity",
                     "UNVERIFIED": "nothing was compared (no observed bytes covered by the trusted identity)"}[eq])
    return out


def verify(packet_dir: str | Path, *, trusted: dict | None = None) -> dict:
    """Returns {'result': 'SUCCESS'|'MISMATCH'|'UNSUPPORTED', 'first_discrepancy': str|None, 'checks': [...],
    'manifest_digest': ..., 'replay': ..., 'provenance': {...}}. Never raises for a malformed packet."""
    def unsupported(msg, mdig=None, checks=None, man=None):
        return {"result": "UNSUPPORTED", "first_discrepancy": msg, "checks": checks or [], "manifest_digest": mdig,
                "replay": "NOT RUN", "provenance": provenance(man, checks or [], trusted)}
    ok, why = platform_supported()
    if not ok:
        return unsupported(f"refusing to verify: {why}")
    pk = Path(packet_dir)
    if not pk.is_dir():
        return unsupported("packet directory missing")
    try:
        pk_fd = os.open(pk, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        return unsupported(f"packet directory unopenable ({exc.__class__.__name__})")
    root_fd = None
    try:
        try:
            mfd = os.open(MANIFEST, _O_FILE, dir_fd=pk_fd)
        except OSError as exc:
            return unsupported(f"{MANIFEST} missing or is a symlink (refused) [{exc.__class__.__name__}]")
        try:
            if not stat.S_ISREG(os.fstat(mfd).st_mode):
                return unsupported(f"{MANIFEST} is not a regular file")
            raw = _read_fd(mfd)
        except OSError as exc:
            return unsupported(f"manifest unreadable: {exc.__class__.__name__}")
        finally:
            os.close(mfd)
        try:
            man_raw = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            return unsupported(f"manifest unreadable: {exc.__class__.__name__}")
        mdig = hashlib.sha256(raw).hexdigest()
        man, err = validate_manifest(man_raw)
        if err:
            return unsupported(f"manifest invalid: {err}", mdig)
        try:
            root_fd = _open_dir("artifacts", pk_fd, "artifacts")   # pinned: no-follow, must be a directory
        except PacketPathError:
            return unsupported("artifact root missing or is a symlink (refused)", mdig, man=man)
        checks, first, target_bytes = [], None, None
        for f in man["files"]:
            if f["status"] != "INCLUDED":
                checks.append({"path": f["path"], "check": "presence", "ok": None, "note": "absent at build (explicit limitation)"}); continue
            try:
                data = _read_contained(root_fd, f["path"])
            except PacketPathError as exc:
                checks.append({"path": f["path"], "check": "containment", "ok": False, "note": str(exc)}); first = first or str(exc); continue
            h, n = hashlib.sha256(data).hexdigest(), len(data); ok = (h == f["sha256"] and n == f["size_bytes"])
            checks.append({"path": f["path"], "check": "sha256+length", "ok": ok, "observed": {"sha256": h, "size_bytes": n}})
            if not ok:
                first = first or f"byte mismatch at {f['path']}: expected {f['sha256'][:16]}…/{f['size_bytes']} B, observed {h[:16]}…/{n} B"
            elif f["path"] == man["replay_target"]:
                target_bytes = data
    finally:
        for fd in (root_fd, pk_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
    prov = provenance(man, checks, trusted)
    if first:
        return {"result": "MISMATCH", "first_discrepancy": first, "checks": checks, "manifest_digest": mdig, "replay": "NOT RUN (integrity failed first)", "provenance": prov}
    if target_bytes is None:                      # unreachable after validation; defensive — never a silent success
        return unsupported("replay target bytes were not verified", mdig, checks, man)
    from v3.lab import replay_check
    tmp = tempfile.mkdtemp(prefix="yuclaw-packet-verify-")
    try:
        os.chmod(tmp, 0o700)
        priv = Path(tmp) / "verified_replay_target.json"
        priv.write_bytes(target_bytes)
        if hashlib.sha256(priv.read_bytes()).hexdigest() != hashlib.sha256(target_bytes).hexdigest():
            return unsupported("private verified copy could not be written intact", mdig, checks, man)
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                rc = replay_check._run(str(priv))
        except Exception as exc:                  # a malformed bundle must not produce a traceback or a success
            return {"result": "UNSUPPORTED", "first_discrepancy": f"replay raised {exc.__class__.__name__}", "checks": checks, "manifest_digest": mdig,
                    "replay": {"exit": None, "tail": buf.getvalue().strip().splitlines()[-3:]}, "provenance": prov}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = buf.getvalue().strip().splitlines()
    replay = {"exit": rc, "tail": out[-3:], "target": man["replay_target"], "target_sha256": hashlib.sha256(target_bytes).hexdigest(), "target_size_bytes": len(target_bytes),
              "mode": "existing replay_check._run on a PRIVATE copy of the verified bytes (offline; the bytes replayed are the bytes verified)"}
    if rc == 0:
        return {"result": "SUCCESS", "first_discrepancy": None, "checks": checks, "manifest_digest": mdig, "replay": replay, "provenance": prov,
                "meaning": "exact bytes verified and published Lab statistics/ledger roots reproduced from the frozen bundle; not an outsider receipt, not a research interpretation, not proof of official origin"}
    diff = next((l for l in out if "MISMATCH" in l.upper() or "diff" in l.lower() or "≠" in l or "!=" in l), out[-1] if out else "replay returned nonzero")
    return {"result": "MISMATCH", "first_discrepancy": f"replay: {diff}", "checks": checks, "manifest_digest": mdig, "replay": replay, "provenance": prov}
