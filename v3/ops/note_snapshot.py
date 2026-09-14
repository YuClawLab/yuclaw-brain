"""Note-snapshot coordinator (v7 candidate; NOT activated — the nightly keeps contract v3 LIVE_RECHECK).

Design (V7-005 §3): ONE exporter transaction in REPEATABLE READ, READ ONLY exports a snapshot; every reader
(the note PRODUCER path and the independent CHECKER path) opens its own transaction at the same isolation level
and imports that snapshot BEFORE its first query; the exporter stays open until all imports completed. Every
allocated connection is registered for cleanup the moment it exists (setup/import/read/expiry failures all
close everything). The lifetime is enforced by bounded connect/statement/lock/idle timeouts inside PostgreSQL,
not only by a check before potentially blocking I/O; expiry is re-checked at completion (equality/label). The
registry file identity is pinned as well (a DB snapshot does not freeze files). The label is an honest
generated-at + snapshot-scope label, never `created_at <= as_of`. There is NO silent fallback to LIVE_RECHECK."""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path


class SnapshotError(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(f"{code}" + (f": {detail}" if detail else ""))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Coordinator:
    """Usage:
        with Coordinator(connect, registry_files=[...], lifetime_s=120) as co:
            a = co.read("producer", sql, params)     # each reader: own connection + imported snapshot
            b = co.read("checker", sql, params)
            co.require_equal(a, b)                   # strict equality; registry identity + expiry re-checked
            label = co.label()
    `connect()` returns a new psycopg2-style connection (dependency injected; the caller should pass a bounded
    connect_timeout). All statements run under statement/lock/idle timeouts derived from the lifetime."""
    def __init__(self, connect, *, registry_files=(), lifetime_s: float = 120.0, now=None):
        self.connect = connect; self.registry_files = [Path(p) for p in registry_files]; self.lifetime_s = float(lifetime_s)
        self.exporter = None; self.snapshot_id = None; self.exported_at = None; self.registry_identity = {}; self.connections = []; self._t0 = None; self._now = now; self.closed = False

    # ---- bounded connections
    def _open(self):
        """Allocate a connection and REGISTER it before any statement runs (cleanup on every later failure)."""
        cn = None
        try:
            cn = self.connect()
            self.connections.append(cn)
            cn.autocommit = True
            ms = max(1, int(self.remaining_s() * 1000))
            cur = cn.cursor()
            cur.execute(f"SET statement_timeout = {ms}"); cur.execute(f"SET lock_timeout = {ms}"); cur.execute(f"SET idle_in_transaction_session_timeout = {ms}")
            return cn
        except Exception as exc:
            if cn is not None and cn not in self.connections:
                self.connections.append(cn)
            self.close(); raise SnapshotError("E_CONNECT_FAILED", exc.__class__.__name__) from None

    def remaining_s(self) -> float:
        return self.lifetime_s - (time.monotonic() - self._t0)

    def _check_lifetime(self, stage: str):
        if self.remaining_s() <= 0:
            self.close(); raise SnapshotError("E_SNAPSHOT_EXPIRED", f"{stage}: coordinator lifetime {self.lifetime_s}s exceeded")

    def __enter__(self):
        self._t0 = time.monotonic()
        for p in self.registry_files:
            if not p.exists():
                raise SnapshotError("E_REGISTRY_MISSING", p.name)
            self.registry_identity[str(p)] = _sha(p)
        self._check_lifetime("setup")
        cn = self._open()
        try:
            cur = cn.cursor()
            cur.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SELECT pg_export_snapshot()"); self.snapshot_id = cur.fetchone()[0]
            cur.execute("SELECT now()"); self.exported_at = cur.fetchone()[0]
            self.exporter = cn
        except Exception as exc:
            self.close(); raise SnapshotError("E_EXPORT_FAILED", exc.__class__.__name__) from None
        return self

    def read(self, name: str, sql: str, params=None):
        """Run one query in a NEW bounded connection whose transaction imported the exporter's snapshot first."""
        if self.closed or self.exporter is None:
            raise SnapshotError("E_SNAPSHOT_EXPIRED", f"{name}: exporter transaction is closed")
        self._check_lifetime(name)
        cn = self._open()
        try:
            cur = cn.cursor()
            cur.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            try:
                cur.execute("SET TRANSACTION SNAPSHOT %s", (self.snapshot_id,))          # BEFORE the first query
            except Exception as exc:
                raise SnapshotError("E_IMPORT_FAILED", f"{name}: {exc.__class__.__name__}") from None
            try:
                cur.execute(sql, params or ())
                rows = [tuple(r) for r in cur.fetchall()]
            except Exception as exc:
                code = "E_READ_TIMEOUT" if "timeout" in str(exc).lower() or "canceling statement" in str(exc).lower() else "E_READ_FAILED"
                raise SnapshotError(code, f"{name}: {exc.__class__.__name__}") from None
            cur.execute("ROLLBACK")
            self._check_lifetime(name + ":complete")
            return {"reader": name, "snapshot_id": self.snapshot_id, "rows": rows}
        except SnapshotError:
            self.close(); raise
        except Exception as exc:
            self.close(); raise SnapshotError("E_READ_FAILED", f"{name}: {exc.__class__.__name__}") from None

    def require_registry_unchanged(self):
        for p in self.registry_files:
            if not p.exists() or _sha(p) != self.registry_identity[str(p)]:
                self.close(); raise SnapshotError("E_REGISTRY_DRIFT", p.name)

    def require_equal(self, a: dict, b: dict):
        self._check_lifetime("equality")
        self.require_registry_unchanged()
        if a["snapshot_id"] != b["snapshot_id"] or a["rows"] != b["rows"]:
            self.close(); raise SnapshotError("E_STRICT_MISMATCH", f"{a['reader']} vs {b['reader']}")
        return True

    def label(self) -> dict:
        """Honest generated-at + snapshot scope: NOT a cutoff, NOT `created_at <= as_of`."""
        self._check_lifetime("label")
        now = self._now or datetime.now(timezone.utc)
        return {"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "snapshot_id": self.snapshot_id, "snapshot_exported_at_db": str(self.exported_at),
                "scope": "all rows visible to the exported REPEATABLE READ snapshot; registry files pinned by sha256", "registry_identity": dict(self.registry_identity),
                "meaning": "generated-at label with snapshot scope; counts are a consistent read of one snapshot, never a created_at cutoff; no LIVE_RECHECK fallback"}

    def close(self):
        self.closed = True
        for cn in self.connections:
            try: cn.cursor().execute("ROLLBACK")
            except Exception: pass
            try: cn.close()
            except Exception: pass
        self.connections = []; self.exporter = None

    def __exit__(self, *exc):
        self.close(); return False
