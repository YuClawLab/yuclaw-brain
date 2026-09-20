"""Local principals and capabilities for the v8 modules. A narrow application boundary, not an account platform.

What it is: a per-workspace registry of principals, each with a generated credential (shown once, stored only as an
scrypt hash), a set of capabilities, an optional expiry and a revocation state; server-side sessions; and the checks every
module route makes. What it proves: WHICH LOCAL CREDENTIAL acted. It does not prove legal identity, human authorship,
reviewer qualification or the truth of anything; two credentials held by one person are not two independent reviewers;
local credentials do not solve collusion or real-world Sybil identity. A host administrator with file access is outside
this boundary by construction.

Authority comes from the server, never from a form: the journal's `actor` is the authenticated principal; a submitted
`actor`, `principal` or display name is ignored. The first administrator is created only from the host command line
(`python -m v8.workbench principals init`): a browser on the loopback port can never enroll itself. No default or
shared password exists and no signing key is embedded.

Primitives (maintained, standard library / OpenSSL): `secrets` for credentials and session identifiers, `hashlib.scrypt`
for credential hashes, `hmac.compare_digest` for comparisons."""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from datetime import timedelta

from v8.workbench.modkinds import AUTH_KINDS
from v8.workbench.modules import core
from v8.workbench.modules.core import ModuleError
from v8.workbench.store import Workspace, now_ts

CAPS = ("admin", "submit", "review", "practice")
CAP_MEANING = {"admin": "administration and approval: principals, SHD trust roots, policy and approvals, budgets, overrides, dispute and failure resolution",
               "submit": "submission: SHD bundles, COM packets, EVO versions and declared evaluations",
               "review": "review: COM review work, EVO review evidence and grading, PRC task curation and feedback",
               "practice": "practice: open a frozen PRC task, commit an attempt, see the comparison afterwards, reflect"}
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}
SESSION_TTL_S, SESSION_IDLE_S = 8 * 3600, 3600
MAX_PRINCIPALS, MAX_SESSIONS, MAX_FAILURES, FAILURE_WINDOW_S = 200, 500, 5, 300
SETUP_STEP = "python -m v8.workbench principals init --workspace <this workspace>   (run by the host operator; it prints the first administrator's credential once)"


def _hash(credential: str, salt: bytes) -> str:
    return hashlib.scrypt(credential.encode("utf-8"), salt=salt, n=SCRYPT["n"], r=SCRYPT["r"], p=SCRYPT["p"], dklen=SCRYPT["dklen"]).hex()


class Principals:
    """The registry. Credential hashes live in `<workspace>/private/principals.json` (0600, atomically replaced); every
    enrollment, rotation and revocation is also a journal event WITHOUT secret material, and authentication requires both:
    a record in the file and a standing enrollment in the journal that no later revocation event cancels."""

    def __init__(self, ws: Workspace):
        self.ws = ws
        self.path = ws.root / "private" / "principals.json"
        self.path.parent.mkdir(exist_ok=True)
        with contextlib.suppress(OSError):
            os.chmod(self.path.parent, 0o700)

    # -- storage
    def _read(self) -> dict:
        if not self.path.is_file():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, reg: dict):
        tmp = self.path.with_name(f".principals-{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, (json.dumps(reg, indent=1, sort_keys=True) + "\n").encode("utf-8")); os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, self.path)

    def configured(self) -> bool:
        return any(e["kind"] == "PRINCIPAL_ENROLLED" for e in self.ws.load()["events"])

    # -- state derived from the journal (the audit record decides; the file only holds the secret half)
    def state(self, as_of: str | None = None) -> dict:
        out: dict = {}
        for e in core.events(self.ws, AUTH_KINDS, as_of=as_of):
            p = e["payload"]; pid = p["principal_id"]
            if e["kind"] == "PRINCIPAL_ENROLLED":
                out[pid] = {"principal_id": pid, "caps": list(p["caps"]), "display_name": p.get("display_name", ""), "enrolled_at": e["time"]["recorded_at"], "enrolled_by": e["actor"],
                            "expires_at": p.get("expires_at"), "credential_id": p["credential_id"], "revoked_at": None, "revoked_reason": None, "declared_role_note": p.get("declared_role_note", "")}
            elif pid in out and e["kind"] == "PRINCIPAL_ROTATED":
                out[pid]["credential_id"] = p["credential_id"]; out[pid]["expires_at"] = p.get("expires_at", out[pid]["expires_at"])
            elif pid in out and e["kind"] == "PRINCIPAL_REVOKED":
                out[pid]["revoked_at"] = e["time"]["recorded_at"]; out[pid]["revoked_reason"] = p.get("reason")
        return out

    def active(self, pid: str, *, at=None) -> dict | None:
        """The principal when it may act NOW: enrolled, not revoked, not expired, clock usable. Read from the journal on every
        call — there is no authorization cache to go stale."""
        p = self.state().get(pid)
        if not p or p["revoked_at"]:
            return None
        at = at or core.now()
        if p["expires_at"] and core.parse_time(p["expires_at"]) <= at:
            return None
        return p

    # -- administration (host operator on the command line, or an authenticated admin principal)
    def _check_by(self, by: dict | None):
        if by is not None and "admin" not in (self.active(by["principal_id"]) or {}).get("caps", []):
            raise ModuleError("E_FORBIDDEN", "enrolling, rotating or revoking a principal needs the admin capability")

    def enroll(self, pid: str, caps, *, display_name: str = "", declared_role_note: str = "", expires_at: str | None = None, op_id: str, by: dict | None) -> tuple[dict, str | None]:
        """Returns (event, credential). The credential is generated here, returned ONCE and never stored or logged. A retry
        with the same op_id returns the existing event and no credential (rotate to obtain a new one)."""
        core.ident(pid, "principal id", core.PRINCIPAL_ID)
        caps = sorted(set(caps))
        if not caps or any(c not in CAPS for c in caps):
            raise ModuleError("E_CAPABILITY", f"capabilities must be chosen from {', '.join(CAPS)}")
        if expires_at:
            expires_at = core.norm_time(expires_at, "expiry")
            if core.parse_time(expires_at) <= core.now():
                raise ModuleError("E_EXPIRY", "the expiry is not in the future")
        with self.ws._locked():
            self._check_by(by)
            evs = self.ws.load()["events"]; done = core.prior(evs, op_id)
            if done is not None and done["kind"] == "PRINCIPAL_ENROLLED" and done["payload"]["principal_id"] == pid:
                return done, None
            st = self.state()
            if pid in st:
                raise ModuleError("E_PRINCIPAL_EXISTS", f"principal {pid!r} already exists; a principal id is never reused (revoke it, or rotate its credential)")
            if len(st) >= MAX_PRINCIPALS:
                raise ModuleError("E_LIMIT", f"at most {MAX_PRINCIPALS} principals per workspace")
            credential = secrets.token_urlsafe(24); salt = secrets.token_bytes(16); h = _hash(credential, salt)
            cred_id = hashlib.sha256(salt + bytes.fromhex(h)).hexdigest()[:16]
            reg = self._read(); reg[pid] = {"salt": salt.hex(), "scrypt": SCRYPT, "hash": h, "credential_id": cred_id}
            self._write(reg)                                              # the secret half first; the journal event is the commit point
            ev, _ = self.ws._append_unlocked("PRINCIPAL_ENROLLED", None, {"principal_id": pid, "caps": caps, "display_name": core.text(display_name, "display name", maxlen=80, required=False),
                                             "declared_role_note": core.text(declared_role_note, "declared role note", maxlen=300, required=False), "expires_at": expires_at or None, "credential_id": cred_id,
                                             "authentication": "local generated credential (scrypt hash held privately); proves which local credential acted, nothing about legal identity or qualification"},
                                             op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(by))
            return ev, credential

    def rotate(self, pid: str, *, expires_at: str | None = None, op_id: str, by: dict | None) -> tuple[dict, str | None]:
        with self.ws._locked():
            self._check_by(by)
            evs = self.ws.load()["events"]; done = core.prior(evs, op_id)
            if done is not None and done["kind"] == "PRINCIPAL_ROTATED":
                return done, None
            st = self.state().get(pid)
            if not st or st["revoked_at"]:
                raise ModuleError("E_UNKNOWN_PRINCIPAL", f"{pid!r} is not an enrolled, unrevoked principal (a revoked principal is never revived)")
            credential = secrets.token_urlsafe(24); salt = secrets.token_bytes(16); h = _hash(credential, salt)
            cred_id = hashlib.sha256(salt + bytes.fromhex(h)).hexdigest()[:16]
            reg = self._read(); reg[pid] = {"salt": salt.hex(), "scrypt": SCRYPT, "hash": h, "credential_id": cred_id}; self._write(reg)
            payload = {"principal_id": pid, "credential_id": cred_id, "previous_credential_id": st["credential_id"]}
            if expires_at:
                payload["expires_at"] = core.norm_time(expires_at, "expiry")
            ev, _ = self.ws._append_unlocked("PRINCIPAL_ROTATED", None, payload, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(by))
            return ev, credential

    def revoke(self, pid: str, reason: str, *, op_id: str, by: dict | None) -> dict:
        with self.ws._locked():
            self._check_by(by)
            st = self.state().get(pid)
            if not st:
                raise ModuleError("E_UNKNOWN_PRINCIPAL", f"{pid!r} is not enrolled here")
            ev, _ = self.ws._append_unlocked("PRINCIPAL_REVOKED", None, {"principal_id": pid, "reason": core.text(reason, "reason", maxlen=500), "credential_id": st["credential_id"],
                                             "meaning": "what this principal did before now stays in the record under its name; it can act no more and is never revived"},
                                             op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(by))
            reg = self._read()
            if reg.pop(pid, None) is not None:
                self._write(reg)
            return ev

    # -- authentication
    def authenticate(self, pid: str, credential: str) -> dict:
        """The active principal, or ModuleError(E_AUTH) with ONE message for every failure (unknown id, wrong credential,
        expired, revoked): the response never says which."""
        fail = ModuleError("E_AUTH", "principal id or credential not accepted")
        if not isinstance(pid, str) or not core.PRINCIPAL_ID.match(pid) or not isinstance(credential, str) or not 8 <= len(credential) <= 200:
            raise fail
        rec = self._read().get(pid)
        salt = bytes.fromhex(rec["salt"]) if rec else b"\x00" * 16
        h = _hash(credential, salt)                                       # always computed: no timing oracle for "unknown id"
        p = self.active(pid)
        if rec is None or p is None or not hmac.compare_digest(h, rec["hash"]) or rec["credential_id"] != p["credential_id"]:
            raise fail
        return p


class Sessions:
    """Server-side authenticated sessions (memory only: a restart signs everyone out). The cookie holds a random identifier;
    the principal is looked up — and re-validated against the journal — on every request."""

    def __init__(self):
        self._lock = threading.Lock(); self._s: dict = {}; self._fail: dict = {}

    def throttle(self, pid: str) -> bool:
        with self._lock:
            now = time.monotonic(); arr = [t for t in self._fail.get(pid, []) if now - t < FAILURE_WINDOW_S]; self._fail[pid] = arr
            return len(arr) >= MAX_FAILURES

    def failed(self, pid: str):
        with self._lock:
            if len(self._fail) > 2000:
                self._fail.clear()
            self._fail.setdefault(pid, []).append(time.monotonic())

    def open(self, principal: dict) -> str:
        sid = secrets.token_hex(32)
        with self._lock:
            now = time.monotonic()
            for k in [k for k, v in self._s.items() if now - v["created"] > SESSION_TTL_S or now - v["seen"] > SESSION_IDLE_S]:
                del self._s[k]
            if len(self._s) >= MAX_SESSIONS:
                raise ModuleError("E_LIMIT", "too many open sessions; sign out elsewhere or restart the server")
            self._s[sid] = {"principal_id": principal["principal_id"], "credential_id": principal["credential_id"], "created": now, "seen": now, "csrf": secrets.token_hex(16)}
        return sid

    def close(self, sid: str):
        with self._lock:
            self._s.pop(sid, None)

    def lookup(self, sid: str, principals: Principals) -> tuple[dict, dict] | None:
        """(principal, session) for a live session whose principal is STILL active with the SAME credential; else None."""
        with self._lock:
            s = self._s.get(sid); now = time.monotonic()
            if s is None or now - s["created"] > SESSION_TTL_S or now - s["seen"] > SESSION_IDLE_S:
                self._s.pop(sid, None); return None
            s["seen"] = now
        p = principals.active(s["principal_id"])
        if p is None or p["credential_id"] != s["credential_id"]:
            self.close(sid); return None
        return p, s


def require(principal: dict | None, cap: str) -> dict:
    """The per-route check. `principal` is what the SERVER authenticated for this request (None = nobody)."""
    if principal is None:
        raise ModuleError("E_SIGN_IN", f"sign in with a principal that holds the {cap} capability")
    if cap not in principal["caps"]:
        raise ModuleError("E_FORBIDDEN", f"principal {principal['principal_id']!r} does not hold the {cap} capability ({CAP_MEANING[cap]})")
    return principal


def conflict(principal: dict, other_ids, what: str):
    """A principal holding several roles is still checked on the particular task."""
    if principal["principal_id"] in set(other_ids):
        raise ModuleError("E_CONFLICT", f"{principal['principal_id']!r} {what}")
