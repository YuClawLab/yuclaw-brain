#!/usr/bin/env python3
"""Database routing for the release-state preflight (8.0.1; owner order of 2026-09-21/22: separate database environments).

One generator invocation (tools/yuclaw_release_state_v6.py) runs two kinds of check, each in its own database environment:

  * PRODUCTION-DATA checks read the research database through a session that CANNOT write: libpq `PGOPTIONS` gets
    `-c default_transaction_read_only=on` appended (a later `-c` wins over an earlier one), so every transaction the
    tool opens is read-only at the server — INSERT/UPDATE/DELETE and DDL raise `ReadOnlySqlTransaction` (SQLSTATE 25006),
    whatever the connecting role may do. The ambient connection settings are otherwise kept: production is reached
    the way the release host normally reaches it.
  * WRITE-REQUIRING tests (the repository test suite: the compliance regression creates and deletes API keys and
    request-log rows) run against a DISPOSABLE PostgreSQL 16 node this module creates in a temporary directory —
    private unix socket, no TCP listen address, trust authentication for one throwaway superuser — seeded exactly as
    hosted CI seeds its service: v3/schema.sql, then v3/migrations/*.sql (each tolerated, as the workflow's `|| true`),
    then tests/fixtures/v4_seed.sql. Their environment carries NO production connection material: every libpq
    variable is removed first, and PGPASSFILE / PGSERVICEFILE / PGSYSCONFDIR point into the node's own directory,
    where no password or service file exists.

Nothing here falls back. When the node cannot be created (no PostgreSQL 16 binaries, initdb/pg_ctl/seed failure,
socket path too long) `DisposableNode.start()` raises `DisposableUnavailable` with the observed reason, and the
caller records the write-requiring check as NOT RUN — it never runs that check against the ambient environment.

Research and education only. Not investment advice.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
from typing import Mapping, Optional

# Every variable libpq reads to decide WHERE to connect and HOW to authenticate (plus the URL form some tools honour).
LIBPQ_VARS = ("PGHOST", "PGHOSTADDR", "PGPORT", "PGUSER", "PGDATABASE", "PGPASSWORD", "PGPASSFILE", "PGSERVICE",
              "PGSERVICEFILE", "PGSYSCONFDIR", "PGOPTIONS", "PGSSLMODE", "PGREQUIRESSL", "PGSSLCERT", "PGSSLKEY",
              "PGSSLROOTCERT", "PGCONNECT_TIMEOUT", "PGTARGETSESSIONATTRS", "PGGSSENCMODE", "PGKRBSRVNAME",
              "PGCHANNELBINDING", "PGAPPNAME", "DATABASE_URL")
SECRET_VARS = ("PGPASSWORD", "PGSSLKEY", "DATABASE_URL")          # never recorded, never forwarded to the node
READ_ONLY_OPTION = "-c default_transaction_read_only=on"
NODE_USER = "t"
NODE_DB = "yuclaw_events"                                          # the product's fixed DSN `dbname=yuclaw_events` resolves here
SEED_FILES = ("v3/schema.sql", "v3/migrations/*.sql", "tests/fixtures/v4_seed.sql")   # the hosted workflow's order
MAX_SOCKET_PATH = 100                                              # sun_path is 108 bytes; leave room for .s.PGSQL.<port>.lock


class DisposableUnavailable(RuntimeError):
    """The disposable node could not be provided; the caller must record NOT RUN (no fallback)."""


def find_pg_bindir() -> Optional[pathlib.Path]:
    """PostgreSQL 16 binaries: the Debian/Ubuntu path first (hosted runners and the release host), then PATH."""
    for cand in (pathlib.Path("/usr/lib/postgresql/16/bin"),):
        if (cand / "initdb").exists() and (cand / "pg_ctl").exists():
            return cand
    ctl = shutil.which("pg_ctl")
    if ctl and shutil.which("initdb"):
        return pathlib.Path(ctl).resolve().parent
    return None


def readonly_env(base: Mapping[str, str]) -> dict:
    """The ambient environment with the server-side read-only guard appended to PGOPTIONS (ours is last, so it wins)."""
    env = dict(base)
    prev = env.get("PGOPTIONS", "").strip()
    env["PGOPTIONS"] = (prev + " " + READ_ONLY_OPTION).strip() if prev else READ_ONLY_OPTION
    return env


def strip_libpq(base: Mapping[str, str]) -> dict:
    return {k: v for k, v in base.items() if k not in LIBPQ_VARS}


def disposable_env(base: Mapping[str, str], socket_dir: str, port: int, node_dir: str) -> dict:
    """Environment for a write-requiring subprocess: no production connection material, only the node."""
    env = strip_libpq(base)
    env.update(PGHOST=socket_dir, PGPORT=str(port), PGUSER=NODE_USER, PGCLIENTENCODING="UTF8",
               PGPASSFILE=os.path.join(node_dir, "no-pgpass"),           # does not exist: ~/.pgpass is never consulted
               PGSERVICEFILE=os.path.join(node_dir, "no-pg_service.conf"),
               PGSYSCONFDIR=node_dir,                                     # no system pg_service.conf either
               PGCONNECT_TIMEOUT="10")
    return env


def describe_libpq(env: Mapping[str, str]) -> dict:
    """What the record may say about a check's database environment: names and non-secret routing values only."""
    present = sorted(k for k in LIBPQ_VARS if k in env)
    safe = {k: env[k] for k in ("PGHOST", "PGHOSTADDR", "PGPORT", "PGUSER", "PGDATABASE", "PGOPTIONS", "PGSERVICE") if k in env}
    pgpass_default = os.path.join(os.path.expanduser("~"), ".pgpass")
    passfile = env.get("PGPASSFILE", pgpass_default)
    return {"variables_set": present, "routing": safe,
            "password_material_reachable": bool(env.get("PGPASSWORD")) or os.path.exists(passfile) or bool(env.get("DATABASE_URL")),
            "read_only_guard": READ_ONLY_OPTION in env.get("PGOPTIONS", "")}


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class DisposableNode:
    """A throwaway PostgreSQL 16 node seeded like hosted CI. Use as a context manager or start()/stop()."""

    def __init__(self, repo: pathlib.Path, base_dir: Optional[str] = None, port: Optional[int] = None):
        self.repo = pathlib.Path(repo)
        self.base_dir = base_dir
        self.port = port or 55000 + (os.getpid() % 1000)
        self.bindir = find_pg_bindir()
        self.dir: Optional[str] = None
        self.data = self.log = self.socket_dir = None
        self.started = False
        self.seed: dict = {}

    # -- lifecycle -------------------------------------------------------------------------------------------------
    def start(self) -> "DisposableNode":
        if self.bindir is None:
            raise DisposableUnavailable("PostgreSQL 16 initdb/pg_ctl not present (/usr/lib/postgresql/16/bin or PATH)")
        psql = self.bindir / "psql" if (self.bindir / "psql").exists() else (shutil.which("psql") and pathlib.Path(shutil.which("psql")))
        if not psql:
            raise DisposableUnavailable("psql not present")
        base = self.base_dir or ("/tmp" if os.access("/tmp", os.W_OK) else tempfile.gettempdir())
        self.dir = tempfile.mkdtemp(prefix="v8pg-", dir=base)
        self.data = os.path.join(self.dir, "data"); self.log = os.path.join(self.dir, "postgresql.log")
        self.socket_dir = os.path.join(self.dir, "s"); os.mkdir(self.socket_dir)
        if len(self.socket_dir) > MAX_SOCKET_PATH:
            self._cleanup(); raise DisposableUnavailable(f"socket directory path too long ({len(self.socket_dir)} > {MAX_SOCKET_PATH}): {self.socket_dir}")
        r = subprocess.run([str(self.bindir / "initdb"), "-D", self.data, "-A", "trust", "-U", NODE_USER, "-E", "UTF8", "--locale=C", "--no-instructions"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self._cleanup(); raise DisposableUnavailable("initdb failed: " + (r.stderr or r.stdout)[-300:])
        r = subprocess.run([str(self.bindir / "pg_ctl"), "-D", self.data, "-o", f"-p {self.port} -k {self.socket_dir} -c listen_addresses='' -c log_connections=on",
                            "-l", self.log, "start", "-w"], capture_output=True, text=True)
        if r.returncode != 0:
            self._cleanup(); raise DisposableUnavailable("pg_ctl start failed: " + (r.stderr or r.stdout)[-300:])
        self.started = True
        try:
            self._seed(psql)
        except DisposableUnavailable:
            self.stop(); raise
        return self

    def _psql(self, psql, *args, dbname=NODE_DB):
        env = disposable_env(os.environ, self.socket_dir, self.port, self.dir)
        return subprocess.run([str(psql), "-h", self.socket_dir, "-p", str(self.port), "-U", NODE_USER, "-d", dbname, "-v", "ON_ERROR_STOP=0", "-q", *args],
                              capture_output=True, text=True, env=env, cwd=str(self.repo))

    def _seed(self, psql):
        r = self._psql(psql, "-c", f"CREATE DATABASE {NODE_DB}", dbname="postgres")
        if r.returncode != 0:
            raise DisposableUnavailable("CREATE DATABASE failed: " + (r.stderr or r.stdout)[-300:])
        files = []
        for pat in SEED_FILES:
            files += sorted(self.repo.glob(pat)) if "*" in pat else [self.repo / pat]
        rows = []
        for f in files:
            if not f.exists():
                raise DisposableUnavailable(f"seed file missing: {f.relative_to(self.repo)}")
            r = self._psql(psql, "-f", str(f))
            errors = len(re.findall(r"^psql:.*ERROR:", r.stderr, flags=re.M)) + len(re.findall(r"^ERROR:", r.stderr, flags=re.M))
            rel = str(f.relative_to(self.repo)); tolerated = rel.startswith("v3/migrations/")     # the workflow applies migrations with `|| true`
            rows.append({"file": rel, "sha256": _sha(f), "rc": r.returncode, "errors": errors, "tolerated": tolerated})
            if (r.returncode != 0 or errors) and not tolerated:
                raise DisposableUnavailable(f"seed {rel} failed (rc {r.returncode}, {errors} error line(s)): {r.stderr[-300:]}")
        self.seed = {"order": list(SEED_FILES), "files": rows, "as_hosted_ci": True}

    def stop(self) -> dict:
        """Stop the node, remove its data; return the identity record (connection count from the node's own log)."""
        ident = self.identity()
        if self.started:
            subprocess.run([str(self.bindir / "pg_ctl"), "-D", self.data, "stop", "-m", "fast", "-w"], capture_output=True)
            self.started = False
        self._cleanup()
        return ident

    def _cleanup(self):
        if self.dir:
            shutil.rmtree(self.dir, ignore_errors=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    # -- what the record may know -----------------------------------------------------------------------------------
    def connections(self) -> int:
        if not self.log or not os.path.exists(self.log):
            return 0
        return len(re.findall(r"connection authorized: user=%s database=%s" % (NODE_USER, NODE_DB), pathlib.Path(self.log).read_text(errors="replace")))

    def identity(self) -> dict:
        return {"kind": "disposable PostgreSQL 16 node (private unix socket, no listen address, trust auth, one throwaway superuser)",
                "socket_dir": self.socket_dir, "port": self.port, "database": NODE_DB, "user": NODE_USER,
                "seed": self.seed, "connections_authorized": self.connections(), "started": self.started}

    def env(self, base: Mapping[str, str]) -> dict:
        if not self.started:
            raise DisposableUnavailable("node not started")
        return disposable_env(base, self.socket_dir, self.port, self.dir)
