"""The v9 sidecar: a separate, versioned, append-only, digest-chained record log beside the v8 journal.

Why a sidecar. The v8 journal (`commitments.jsonl`) accepts a fixed event vocabulary; an 8.0.1 reader refuses to WRITE an
unknown kind and would silently ignore it on read. v9 therefore never appends to it. Every v9 record goes to
`<workspace>/v9/brief.jsonl`, bound to the v8 workspace identity (`workspace.json`) and to the v8 journal tip observed when
the record was written, so a record can always say which v8 state it was computed against. Private bytes (brief text
views, imported files, raw provider responses) go to the existing content-addressed vault (`private/vault/<sha256>`)
FIRST; the sidecar record naming their digests is the commit point. A process death therefore leaves either an orphan
vault object (harmless, listable, never referenced) or a committed record — never a brief that looks complete but lacks
its inputs: a record whose referenced objects are missing reads as INCOMPLETE.

The rules are the v8 store's: one newline-terminated canonical-JSON line per record; `record_hash` over the whole record,
`prev_hash` chaining; a torn tail refuses writes until `recover()` preserves it; every write carries an `op_id` — a retry
with the same op_id and the same content returns the existing record, different content under the same op_id is a
conflict (E_OP_CONFLICT); the read-decide-append sequence runs under the v8 workspace lock (one lock for both stores,
so v8 and v9 writes never interleave). Measurements of every operation attempt go to `v9/operations.jsonl` (append-only,
not chained: an observation log, not evidence).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

from v3.receipts.contracts import ContractError, canonical_json, digest, format_ts
from v8.workbench.modules.core import Vault
from v8.workbench.store import GENESIS, MAX_LINE, StoreIntegrityError, Workspace, _line_hash

FORMAT = "yuclaw-brief-sidecar/1"
DIRNAME = "v9"
LOG = "brief.jsonl"
META = "sidecar.json"
OPS = "operations.jsonl"
KINDS = ("ARTIFACT_RECORDED", "TEXT_VIEW_RECORDED", "SNAPSHOT_RECORDED", "BRIEF_VERSION_RECORDED", "TRANSFORM_RECORDED", "SPAN_LINK_RECORDED",
         "RECEIPT_IMPORTED", "REPORT_IMPORTED", "CALIBRATION_IMPORTED", "TRUST_ROOT_ENROLLED", "TRUST_ROOT_REVOKED",
         "REVIEW_ITEM_RECORDED", "REVIEW_ITEM_RESOLVED", "PACKET_BUILT", "PACKET_VERIFIED", "RECOVERY")
OUTCOMES = ("COMMITTED", "DUPLICATE", "CONFLICT", "REFUSED", "FAILED", "READ")
_OP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
MAX_OPS_BYTES = 64 << 20


def now_ts() -> str:
    return format_ts(datetime.now(timezone.utc))


class Sidecar:
    def __init__(self, ws: Workspace, *, create: bool = True):
        self.ws = ws
        self.dir = ws.root / DIRNAME
        self.log = self.dir / LOG
        self.meta_path = self.dir / META
        self.ops_path = self.dir / OPS
        if not self.dir.exists():
            if not create:
                raise StoreIntegrityError("E_NO_SIDECAR", "this workspace has no v9 sidecar yet (nothing v9 was recorded here)")
            self.dir.mkdir(mode=0o700)
        with contextlib.suppress(OSError):
            os.chmod(self.dir, 0o700)
        if not self.meta_path.exists():
            if not create:
                raise StoreIntegrityError("E_NO_SIDECAR", "sidecar directory without its metadata")
            self.meta_path.write_text(json.dumps({"format": FORMAT, "workspace_id": ws.meta["workspace_id"], "created_at": now_ts(), "v8_format": ws.meta.get("format")}, indent=1, sort_keys=True) + "\n")
            with contextlib.suppress(OSError):
                os.chmod(self.meta_path, 0o600)
        self.meta = json.loads(self.meta_path.read_text())
        if self.meta.get("format") != FORMAT:
            raise StoreIntegrityError("E_FORMAT", f"sidecar format {self.meta.get('format')!r} is not {FORMAT!r} (unsupported sidecar version; nothing reinterpreted)")
        if self.meta.get("workspace_id") != ws.meta["workspace_id"]:
            raise StoreIntegrityError("E_WORKSPACE_MISMATCH", f"sidecar belongs to workspace {self.meta.get('workspace_id')} but this is {ws.meta['workspace_id']} (a sidecar is never read against another workspace's journal)")
        self.vault = Vault(ws)

    # ------------------------------------------------------------------ reading
    def _raw(self) -> bytes:
        return self.log.read_bytes() if self.log.exists() else b""

    def load(self) -> dict:
        raw = self._raw()
        last_nl = raw.rfind(b"\n")
        durable, tail = (raw[:last_nl + 1], raw[last_nl + 1:]) if last_nl >= 0 else (b"", raw)
        records, prev, seq = [], GENESIS, 0
        for n, line in enumerate(durable.split(b"\n")[:-1], start=1):
            if len(line) > MAX_LINE:
                raise StoreIntegrityError("E_LINE_TOO_LONG", f"sidecar line {n}")
            try:
                rec = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise StoreIntegrityError("E_CORRUPT_LINE", f"sidecar line {n} is not JSON") from None
            if not isinstance(rec, dict) or set(rec) < {"seq", "kind", "brief_id", "op_id", "payload", "time", "actor", "v8_tip", "prev_hash", "record_hash"}:
                raise StoreIntegrityError("E_CORRUPT_LINE", f"sidecar line {n} lacks record fields")
            h = rec["record_hash"]; body = {k: v for k, v in rec.items() if k != "record_hash"}
            if not _HEX64.match(str(h)) or _line_hash(body) != h:
                raise StoreIntegrityError("E_HASH", f"sidecar line {n}: record_hash does not match its content (history rewritten?)")
            if rec["prev_hash"] != prev:
                raise StoreIntegrityError("E_CHAIN", f"sidecar line {n}: prev_hash {str(rec['prev_hash'])[:12]} != tip {prev[:12]}")
            if rec["seq"] != seq + 1:
                raise StoreIntegrityError("E_SEQ", f"sidecar line {n}: seq {rec['seq']} != {seq + 1}")
            if canonical_json(rec) != line:
                raise StoreIntegrityError("E_NONCANONICAL", f"sidecar line {n} is not canonical JSON")
            records.append(rec); prev, seq = h, rec["seq"]
        torn = {"bytes": len(tail), "sha256": hashlib.sha256(tail).hexdigest(), "offset": len(durable)} if tail else None
        return {"records": records, "torn_tail": torn, "tip": prev, "durable_bytes": len(durable)}

    def records(self, kind: str | tuple | None = None, brief_id: str | None = None, recs: list | None = None) -> list[dict]:
        recs = self.load()["records"] if recs is None else recs
        kinds = (kind,) if isinstance(kind, str) else kind
        return [r for r in recs if (kinds is None or r["kind"] in kinds) and (brief_id is None or r["brief_id"] == brief_id)]

    def status(self) -> dict:
        v8 = self.ws.status()
        try:
            st = self.load()
            return {"format": FORMAT, "workspace_id": self.meta["workspace_id"], "records": len(st["records"]), "tip": st["tip"], "torn_tail": st["torn_tail"],
                    "integrity": "TORN_TAIL" if st["torn_tail"] else "OK", "v8": {"integrity": v8["integrity"], "events": v8["events"], "tip": v8.get("tip")},
                    "briefs": sorted({r["brief_id"] for r in st["records"] if r["kind"] == "BRIEF_VERSION_RECORDED"})}
        except StoreIntegrityError as exc:
            return {"format": FORMAT, "workspace_id": self.meta["workspace_id"], "integrity": exc.code, "detail": str(exc), "records": None, "briefs": [], "v8": {"integrity": v8["integrity"]}}

    def prior(self, op_id: str, recs: list | None = None) -> dict | None:
        recs = self.load()["records"] if recs is None else recs
        return next((r for r in recs if r["op_id"] == op_id), None)

    # ------------------------------------------------------------------ private objects (prepared before any record commits them)
    def put_bytes(self, data: bytes) -> str:
        return self.vault.put_bytes(data)

    def put_object(self, obj) -> str:
        return self.vault.put(obj)

    def has(self, h: str) -> bool:
        return isinstance(h, str) and bool(_HEX64.match(h)) and (self.vault.dir / h).is_file()

    def get_bytes(self, h: str) -> bytes:
        return self.vault.get_bytes(h)

    def get_object(self, h: str):
        return self.vault.get(h)

    def missing_objects(self, rec: dict) -> list[str]:
        """Digests a record names under payload.objects that are not in the vault — an INCOMPLETE record."""
        return [h for h in (rec.get("payload", {}).get("objects") or []) if not self.has(h)]

    def orphans(self, limit: int = 1000) -> dict:
        """Vault objects named by no sidecar record and no v8 module event (bounded listing; nothing is deleted here)."""
        named = set()
        for r in self.load()["records"]:
            named.update(r.get("payload", {}).get("objects") or [])
        for e in self.ws.load()["events"]:
            raw = canonical_json(e.get("payload", {})).decode("ascii")
            named.update(re.findall(r"[0-9a-f]{64}", raw))
        out, seen = [], 0
        for p in sorted(self.vault.dir.iterdir()):
            if not _HEX64.match(p.name):
                continue
            seen += 1
            if p.name not in named:
                out.append({"digest": p.name, "bytes": p.stat().st_size})
            if len(out) >= limit:
                break
        return {"objects": seen, "orphans": out, "truncated": len(out) >= limit, "meaning": "an orphan is a prepared object whose commit never happened; listing it deletes nothing, and a referenced object is never an orphan"}

    def remove_orphans(self, digests: list[str]) -> dict:
        """Bounded cleanup: removes only objects that are orphans RIGHT NOW (re-checked under the lock)."""
        with self.ws._locked():
            current = {o["digest"] for o in self.orphans(limit=10000)["orphans"]}
            removed, kept = [], []
            for h in digests:
                if h in current:
                    (self.vault.dir / h).unlink(missing_ok=True); removed.append(h)
                else:
                    kept.append(h)
            return {"removed": removed, "kept_referenced_or_unknown": kept}

    # ------------------------------------------------------------------ writing
    def _append_unlocked(self, kind, brief_id, payload, *, op_id, actor):
        if kind not in KINDS:
            raise ContractError(f"unknown sidecar record kind {kind!r}")
        if not isinstance(op_id, str) or not _OP.match(op_id):
            raise ContractError("op_id: identifier of 8–128 characters [A-Za-z0-9._:-] required")
        v8 = self.ws.load()                                   # raises StoreIntegrityError when the v8 journal is corrupt: never write beside a broken journal
        if v8["torn_tail"]:
            raise StoreIntegrityError("E_TORN_TAIL", "the v8 journal has a torn tail; recover it first")
        st = self.load()
        if st["torn_tail"]:
            raise StoreIntegrityError("E_TORN_TAIL", "the v9 sidecar has a torn tail; run `brief recover` before writing (nothing durable is lost)")
        pdig = digest(payload)
        for r in st["records"]:
            if r["op_id"] == op_id:
                if r["kind"] == kind and digest(r["payload"]) == pdig:
                    return r, True
                raise StoreIntegrityError("E_OP_CONFLICT", f"op_id {op_id!r} was already used for a different operation; a retry must repeat the same content")
        missing = [h for h in (payload.get("objects") or []) if not self.has(h)]
        if missing:
            raise StoreIntegrityError("E_NOT_PREPARED", f"record names {len(missing)} object(s) not yet in the vault; prepare the bytes before committing")
        body = {"seq": len(st["records"]) + 1, "kind": kind, "brief_id": brief_id, "op_id": op_id, "payload": payload, "time": {"recorded_at": now_ts()},
                "actor": actor, "v8_tip": v8["tip"], "v8_seq": len(v8["events"]), "prev_hash": st["tip"]}
        body["record_hash"] = _line_hash(body)
        line = canonical_json(body) + b"\n"; created = not self.log.exists()
        fd = os.open(self.log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            n = os.write(fd, line)
            if n != len(line):
                raise StoreIntegrityError("E_SHORT_WRITE", f"{n} of {len(line)} bytes")
            os.fsync(fd)
        finally:
            os.close(fd)
        if created:
            dfd = os.open(self.dir, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        return body, False

    def append(self, kind, brief_id, payload, *, op_id, actor="host-operator(cli)"):
        with self.ws._locked():
            return self._append_unlocked(kind, brief_id, payload, op_id=op_id, actor=actor)

    def recover(self) -> dict:
        with self.ws._locked():
            st = self.load(); torn = st["torn_tail"]
            if torn is None:
                return {"recovered": False, "reason": "no torn tail"}
            raw = self._raw(); side = self.dir / f"{LOG}.torn.{torn['sha256'][:16]}"
            side.write_bytes(raw[torn["offset"]:])
            with contextlib.suppress(OSError):
                os.chmod(side, 0o600)
            fd = os.open(self.log, os.O_RDWR)
            try:
                os.ftruncate(fd, torn["offset"]); os.fsync(fd)
            finally:
                os.close(fd)
            rec, dup = self._append_unlocked("RECOVERY", None, {"torn_bytes": torn["bytes"], "torn_sha256": torn["sha256"], "preserved_as": side.name,
                                                               "meaning": "an interrupted append left bytes without a terminating newline; they were never a durable record; nothing durable was changed"},
                                             op_id=f"recovery:{torn['sha256'][:24]}", actor="workspace")
            return {"recovered": True, "torn": torn, "record": rec}

    # ------------------------------------------------------------------ measured operations
    def _ops_lines(self) -> list[dict]:
        if not self.ops_path.exists():
            return []
        raw = self.ops_path.read_bytes()
        if len(raw) > MAX_OPS_BYTES:
            raise ContractError("operations log exceeds its bound; archive it before continuing")
        out = []
        for line in raw.split(b"\n"):
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                out.append({"corrupt_line": True})
        return out

    def operations(self) -> list[dict]:
        return self._ops_lines()

    def _write_op(self, rec: dict) -> None:
        line = canonical_json(rec) + b"\n"
        fd = os.open(self.ops_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line); os.fsync(fd)
        finally:
            os.close(fd)

    @contextlib.contextmanager
    def operation(self, task: str, op_id: str, *, actor: str = "host-operator(cli)", surface: str = "cli"):
        """Measure one attempt of one logical operation. The attempt number is the count of earlier attempts with this op_id + 1;
        the outcome is COMMITTED (a new record), DUPLICATE (an idempotent retry), CONFLICT (same op_id, different bytes), REFUSED
        (a contract refusal), FAILED (anything else) or READ (a measured read-only task). Elapsed time is wall-clock milliseconds of
        this attempt; it measures the software, not a person's labour."""
        earlier = sum(1 for o in self._ops_lines() if o.get("op_id") == op_id)
        att = _Attempt(); started = now_ts(); t0 = time.monotonic()
        try:
            yield att
        except StoreIntegrityError as exc:
            att.outcome = "CONFLICT" if exc.code == "E_OP_CONFLICT" else "FAILED"; att.detail = exc.code; raise
        except ContractError as exc:
            att.outcome = "REFUSED"; att.detail = str(exc)[:200]; raise
        except Exception as exc:
            att.outcome = "FAILED"; att.detail = exc.__class__.__name__; raise
        finally:
            ms = int((time.monotonic() - t0) * 1000)
            self._write_op({"op_id": op_id, "task": task, "attempt": earlier + 1, "surface": surface, "actor": actor, "started_at": started, "finished_at": now_ts(),
                            "elapsed_ms": ms, "outcome": att.outcome, "detail": att.detail, "brief_id": att.brief_id})


class _Attempt:
    def __init__(self):
        self.outcome = "COMMITTED"; self.detail = None; self.brief_id = None

    def committed(self, rec: dict, dup: bool, *, brief_id: str | None = None):
        self.outcome = "DUPLICATE" if dup else "COMMITTED"; self.brief_id = brief_id or rec.get("brief_id"); return rec

    def read(self, detail: str | None = None):
        self.outcome = "READ"; self.detail = detail
