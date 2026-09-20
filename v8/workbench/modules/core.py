"""Shared foundation of the v8 modules: strict bounded JSON, identifiers, the private vault, module events and times.

Persistence rule (one store, one commit point): a module write is ONE journal event appended under the workspace lock.
Private content goes into the content-addressed vault first (written and fsynced), and the event that names its sha256 is
the commit: a crash between the two leaves an unreferenced vault object and no decision, never a decision without its
content. Nothing here is a backup or a restore facility."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone

from v3.receipts.contracts import ContractError, canonical_json
from v8.workbench.store import Workspace, now_ts

HEX64 = re.compile(r"^[0-9a-f]{64}$")
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
PRINCIPAL_ID = re.compile(r"^[a-z][a-z0-9_.-]{1,39}$")
MAX_TEXT = 8000


class ModuleError(ContractError):
    """A refusal with a FIXED code. The code is what crosses a boundary; the detail is for the local operator's page."""
    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(code + (f": {detail}" if detail else ""))


# ------------------------------------------------------------------ strict, bounded JSON (no floats, no duplicate keys)
def strict_json(data: bytes, *, max_bytes: int, code: str = "INPUT", max_depth: int = 32, max_nodes: int = 20000, max_string: int = 65536):
    """Parse hostile JSON within declared bounds. Size is checked before decoding, nesting before the decoder allocates
    containers; duplicate keys, floats, NaN/Infinity and integers beyond 16 digits are refused. Returns the value."""
    if not isinstance(data, (bytes, bytearray)) or len(data) > max_bytes:
        raise ModuleError(code + "_TOO_LARGE")
    try:
        text = bytes(data).decode("utf-8")
    except UnicodeError:
        raise ModuleError(code + "_INVALID_JSON") from None
    depth, quoted, escaped = 0, False, False
    for ch in text:
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
        elif ch in "[{":
            depth += 1
            if depth > max_depth:
                raise ModuleError(code + "_TOO_DEEP")
        elif ch in "]}":
            depth -= 1
    nodes = [0]

    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ModuleError(code + "_DUPLICATE_KEY")
            out[k] = v
        nodes[0] += len(out) + 1
        if nodes[0] > max_nodes:
            raise ModuleError(code + "_TOO_MANY_VALUES")
        return out

    def whole(num):
        if len(num.lstrip("-")) > 16:
            raise ModuleError(code + "_INTEGER_TOO_LARGE")
        return int(num)

    def refuse(_):
        raise ModuleError(code + "_NONINTEGER_NUMBER")

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_int=whole, parse_float=refuse, parse_constant=refuse)
    except ModuleError:
        raise
    except (ValueError, RecursionError):
        raise ModuleError(code + "_INVALID_JSON") from None

    def walk(v, n=0):
        if isinstance(v, str) and len(v) > max_string:
            raise ModuleError(code + "_STRING_TOO_LONG")
        if isinstance(v, list):
            nodes[0] += len(v)
            if nodes[0] > max_nodes:
                raise ModuleError(code + "_TOO_MANY_VALUES")
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
    walk(value)
    return value


def ident(v, field: str, pat=IDENT) -> str:
    if not isinstance(v, str) or not pat.match(v):
        raise ModuleError("E_IDENTIFIER", f"{field}: identifier required")
    return v


def hex64(v, field: str) -> str:
    if not isinstance(v, str) or not HEX64.match(v):
        raise ModuleError("E_DIGEST", f"{field}: a lowercase sha256 (64 hex characters) is required")
    return v


def text(v, field: str, *, maxlen: int = MAX_TEXT, required: bool = True) -> str:
    v = (v or "").strip() if isinstance(v, str) else ""
    if required and not v:
        raise ModuleError("E_REQUIRED", f"{field} is required")
    if len(v) > maxlen:
        raise ModuleError("E_TOO_LONG", f"{field}: at most {maxlen} characters")
    return v


def fsync_dir(path) -> None:
    """Make a directory entry durable (a new file, or a rename into place). An fsync of the FILE alone does not cover its
    name: after a power cut the journal could otherwise name a private object whose rename was never written."""
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ times (server-recorded action time vs asserted times)
def parse_time(s: str) -> datetime:
    """Both workbench spellings: `YYYY-MM-DDTHH:MM:SSZ` (asserted times) and the journal's microsecond form."""
    if not isinstance(s, str):
        raise ModuleError("E_TIMESTAMP", "UTC timestamp required")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        with contextlib.suppress(ValueError):
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
    raise ModuleError("E_TIMESTAMP", f"{s!r} is not a UTC timestamp YYYY-MM-DDTHH:MM:SSZ")


def norm_time(s: str, field: str) -> str:
    s = (s or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$", s):
        s += ":00Z"
    elif re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", s):
        s += "Z"
    try:
        return parse_time(s).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ModuleError:
        raise ModuleError("E_TIMESTAMP", f"{field}: UTC time YYYY-MM-DDTHH:MM:SSZ required") from None


def now() -> datetime:
    return datetime.now(timezone.utc)


def recorded_at(ev: dict) -> datetime:
    return parse_time(ev["time"]["recorded_at"])


def clock_problem(ws: Workspace, at: datetime | None = None) -> str | None:
    """The server clock must not be behind the journal's newest recorded action: a clock that moved backwards cannot
    decide expiry or ordering. Returns the reason, or None when the clock is usable."""
    at = at or now(); evs = ws.load()["events"]
    if evs and recorded_at(evs[-1]) > at + timedelta(seconds=2):
        return f"the server clock ({at.strftime('%Y-%m-%dT%H:%M:%SZ')}) is behind the newest recorded action ({evs[-1]['time']['recorded_at']})"
    return None


# ------------------------------------------------------------------ private vault (content-addressed, 0600, never exported wholesale)
class Vault:
    def __init__(self, ws: Workspace):
        self.dir = ws.root / "private" / "vault"
        self.dir.mkdir(parents=True, exist_ok=True)
        for d in (self.dir.parent, self.dir):
            with contextlib.suppress(OSError):
                os.chmod(d, 0o700)

    def put_bytes(self, data: bytes) -> str:
        h = sha256_bytes(data); p = self.dir / h
        if not p.exists():
            tmp = self.dir / f".tmp-{h}-{os.getpid()}"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                os.write(fd, data); os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(tmp, p); fsync_dir(self.dir)                # the NAME is durable before any event names this digest
        return h

    def put(self, obj) -> str:
        return self.put_bytes(canonical_json(obj))

    def get_bytes(self, h: str) -> bytes:
        hex64(h, "vault digest"); p = self.dir / h
        if not p.is_file():
            raise ModuleError("E_VAULT_MISSING", f"private object {h[:12]}… is not in this workspace")
        data = p.read_bytes()
        if sha256_bytes(data) != h:
            raise ModuleError("E_VAULT_CORRUPT", f"private object {h[:12]}… does not match its digest")
        return data

    def get(self, h: str):
        return json.loads(self.get_bytes(h).decode("utf-8"))


# ------------------------------------------------------------------ module events
def actor_of(principal: dict | None) -> str:
    """The journal's actor field for an authenticated principal. A display name or a form field is never an actor."""
    return f"principal:{principal['principal_id']}" if principal else "host-operator(cli)"


def events(ws: Workspace, kinds: tuple, *, as_of: str | None = None, evs: list | None = None) -> list[dict]:
    """Module events of the given kinds, cut by the SERVER-RECORDED action time when a historical cutoff is given: a
    later approval, review, correction or revocation never appears as known at an earlier cutoff."""
    evs = ws.load()["events"] if evs is None else evs
    cut = parse_time(norm_time(as_of, "as of")) if as_of else None
    return [e for e in evs if e["kind"] in kinds and (cut is None or recorded_at(e) <= cut)]


def append(ws: Workspace, kind: str, payload: dict, *, op_id: str, principal: dict | None) -> tuple[dict, bool]:
    """Append one module event. Call inside `with ws._locked():` when the decision depends on state read beforehand."""
    with ws._locked():
        return ws._append_unlocked(kind, None, payload, op_id=op_id, observed_at=None, source_available_as_of=None, actor=actor_of(principal))


def next_id(evs: list[dict], kind: str, prefix: str, field: str) -> str:
    n = sum(1 for e in evs if e["kind"] == kind)
    return f"{prefix}{n + 1}"


def prior(evs: list[dict], op_id: str) -> dict | None:
    return next((e for e in evs if e["op_id"] == op_id), None)


# ------------------------------------------------------------------ canonical workbench objects (no second provenance universe)
def claim_ref(ws: Workspace, claim_id: str) -> dict:
    """The canonical identity of a frozen claim as the modules name it: id, current version number and digest, the
    financial contract that decides compatibility, and the source roots it cites. Raises when the claim is not here."""
    ident(claim_id, "claim id"); st = ws.claim_state(claim_id)
    if st is None:
        raise ModuleError("E_UNKNOWN_CLAIM", f"claim {claim_id!r} is not frozen in this workspace")
    from v8.workbench import availability
    cur = st["versions"][-1]; c = cur["claim"]
    contract = {k: c.get(k) for k in ("metric", "currency", "unit", "scale_as_stated", "basis", "fiscal_period")}   # what makes two claims comparable
    roots = sorted({availability.source_id(v["claim"]["source"]) for v in st["versions"] if v["claim"].get("source")})
    return {"claim_id": claim_id, "version": cur.get("version_id"), "version_digest": c.get("_digest") or hashlib.sha256(canonical_json(c)).hexdigest(),
            "contract": contract, "contract_digest": hashlib.sha256(canonical_json(contract)).hexdigest(), "source_roots": roots}


def source_ids(ws: Workspace) -> dict:
    return {e["payload"]["source_id"]: e for e in ws.load()["events"] if e["kind"] == "SOURCE_REGISTERED"}
