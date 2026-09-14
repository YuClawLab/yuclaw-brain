"""Note-snapshot coordinator (v7 candidate; NOT activated — the nightly keeps contract v3 LIVE_RECHECK).

Design (V7-005 §3): ONE exporter transaction in REPEATABLE READ, READ ONLY exports a snapshot; every reader
(the note PRODUCER path and the independent CHECKER path) opens its own transaction at the same isolation level
and imports that snapshot BEFORE its first query; the exporter stays open until all imports completed; the
coordinator's lifetime is bounded and every connection is closed on failure. The registry file identity is
pinned as well (a DB snapshot does not freeze files). The label is an honest generated-at + snapshot-scope
label, never `created_at <= as_of`. Any failure (expiry, import failure, registry drift, strict mismatch) is an
explicit error; there is NO silent fallback to LIVE_RECHECK."""
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
            co.require_equal(a, b)                   # strict equality; registry identity re-checked
            label = co.label()
    `connect()` returns a new psycopg2-style connection (dependency injected: tests use a disposable PostgreSQL 16)."""
    def __init__(self, connect, *, registry_files=(), lifetime_s: float = 120.0, now=None):
        self.connect = connect; self.registry_files = [Path(p) for p in registry_files]; self.lifetime_s = float(lifetime_s)
        self.exporter = None; self.snapshot_id = None; self.exported_at = None; self.registry_identity = {}; self.readers = []; self._t0 = None; self._now = now

    def __enter__(self):
        self._t0 = time.monotonic()
        for p in self.registry_files:
            if not p.exists():
                raise SnapshotError("E_REGISTRY_MISSING", p.name)
            self.registry_identity[str(p)] = _sha(p)
        try:
            cn = self.connect(); cn.autocommit = True                 # explicit BEGIN below owns the transaction (no driver-implicit BEGIN)
            cur = cn.cursor()
            cur.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SELECT pg_export_snapshot()"); self.snapshot_id = cur.fetchone()[0]
            cur.execute("SELECT now()"); self.exported_at = cur.fetchone()[0]
            self.exporter = cn
        except Exception as exc:
            self.close(); raise SnapshotError("E_EXPORT_FAILED", exc.__class__.__name__) from None
        return self

    def _check_lifetime(self):
        if time.monotonic() - self._t0 > self.lifetime_s:
            self.close(); raise SnapshotError("E_SNAPSHOT_EXPIRED", f"coordinator lifetime {self.lifetime_s}s exceeded")

    def read(self, name: str, sql: str, params=None):
        """Run one query in a NEW connection whose transaction imported the exporter's snapshot first."""
        self._check_lifetime()
        if self.exporter is None:
            raise SnapshotError("E_SNAPSHOT_EXPIRED", "exporter transaction is closed")
        cn = None
        try:
            cn = self.connect(); cn.autocommit = True; self.readers.append(cn)
            cur = cn.cursor()
            cur.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            try:
                cur.execute("SET TRANSACTION SNAPSHOT %s", (self.snapshot_id,))          # BEFORE the first query
            except Exception as exc:
                raise SnapshotError("E_IMPORT_FAILED", f"{name}: {exc.__class__.__name__}") from None
            cur.execute(sql, params or ())
            rows = [tuple(r) for r in cur.fetchall()]
            cur.execute("ROLLBACK")
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
        self.require_registry_unchanged()
        if a["snapshot_id"] != b["snapshot_id"] or a["rows"] != b["rows"]:
            self.close(); raise SnapshotError("E_STRICT_MISMATCH", f"{a['reader']} vs {b['reader']}")
        return True

    def label(self) -> dict:
        """Honest generated-at + snapshot scope: NOT a cutoff, NOT `created_at <= as_of`."""
        now = self._now or datetime.now(timezone.utc)
        return {"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "snapshot_id": self.snapshot_id, "snapshot_exported_at_db": str(self.exported_at),
                "scope": "all rows visible to the exported REPEATABLE READ snapshot; registry files pinned by sha256", "registry_identity": dict(self.registry_identity),
                "meaning": "generated-at label with snapshot scope; counts are a consistent read of one snapshot, never a created_at cutoff; no LIVE_RECHECK fallback"}

    def close(self):
        for cn in self.readers:
            try: cn.close()
            except Exception: pass
        self.readers = []
        if self.exporter is not None:
            try: self.exporter.cursor().execute("ROLLBACK")
            except Exception: pass
            try: self.exporter.close()
            except Exception: pass
            self.exporter = None

    def __exit__(self, *exc):
        self.close(); return False
