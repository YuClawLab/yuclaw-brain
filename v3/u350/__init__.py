"""U350 expanded-research-universe namespace (Phase 0, 2026-08-02).

HARD RULES enforced here in code, not convention:
  - U79 (the canonical 79-name record) is preserved byte-for-byte; its
    forward record continues untouched and canonical forever.
  - U350 writers CANNOT write into any U79/public table: every U350
    database write goes through u350_connection(), which SET ROLE's to a
    database role whose write privileges on the public schema are REVOKED
    — the refusal is PostgreSQL's, not a code convention.
  - U79 canonical readers cannot see U350 rows: all U350 data lives in the
    dedicated `u350` schema; no canonical reader references that schema.
  - Shadow data is never a forward record; no public claims during shadow.
"""
from __future__ import annotations

import psycopg2

DSN = "dbname=yuclaw_events"
ROLE = "u350_writer"
SCHEMA = "u350"

DDL_ROLE = f"""
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{ROLE}') THEN
    CREATE ROLE {ROLE};
  END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS {SCHEMA} AUTHORIZATION {ROLE};
-- the mechanical refusal: the role may use the public schema for reads
-- only; INSERT/UPDATE/DELETE/TRUNCATE on every public table is revoked.
GRANT USAGE ON SCHEMA public TO {ROLE};
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM {ROLE};
GRANT SELECT ON ALL TABLES IN SCHEMA public TO {ROLE};
GRANT ALL ON SCHEMA {SCHEMA} TO {ROLE};
"""

DDL_TABLES = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.shadow_snapshots (
    snapshot_id text PRIMARY KEY,
    ticker text NOT NULL,
    signal_time timestamptz NOT NULL,
    available_as_of timestamptz NOT NULL,
    signal_label text NOT NULL,
    total_score real NOT NULL,
    components jsonb,
    components_ok int,
    components_total int,
    manifest_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS {SCHEMA}.manifest (
    phase text NOT NULL,
    manifest_hash text NOT NULL,
    locked_at timestamptz NOT NULL DEFAULT now(),
    members jsonb NOT NULL,
    PRIMARY KEY (phase, manifest_hash));
"""


# ---- 8.0.1 (gate 4 repair): verification is separated from provisioning ---------------------------------------------
# The isolation check INSPECTS the existing configuration read-only and fails closed on drift; it never creates a role,
# a schema or a table and never grants or revokes — doing so before testing would repair the very condition under test.
# ensure_namespace() below stays the provisioning function for a disposable test node or a deliberate administrative
# step; no production path calls it.
PUBLIC_WRITE_PRIVILEGES = ("INSERT", "UPDATE", "DELETE", "TRUNCATE")
EXPECTED_DATABASE = "yuclaw_events"                        # what the fixed DSN names; a different current_database() is a routing fault
EXPECTED_TABLES = {                                       # name -> {column: data_type} exactly as DDL_TABLES creates them
    "manifest": {"phase": "text", "manifest_hash": "text", "locked_at": "timestamp with time zone", "members": "jsonb"},
    "shadow_snapshots": {"snapshot_id": "text", "ticker": "text", "signal_time": "timestamp with time zone", "available_as_of": "timestamp with time zone",
                         "signal_label": "text", "total_score": "real", "components": "jsonb", "components_ok": "integer", "components_total": "integer",
                         "manifest_hash": "text", "created_at": "timestamp with time zone"},
}
MANIFEST_KEY = ("phase", "manifest_hash")                 # the primary key that makes a per-run probe identity unique


class ProbeFailure(RuntimeError):
    """The positive control did not prove what it must; the transaction was rolled back before this was raised."""


def inspect_isolation(cn) -> dict:
    """Read-only inspection of the isolation configuration. Returns {"findings": [...], "facts": {...}}; an empty findings
    list means the configuration is exactly the registered one. Nothing is created, granted or revoked here."""
    findings, facts = [], {}
    with cn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user, session_user, inet_server_addr()::text, current_setting('port'), "
                    "current_setting('unix_socket_directories'), current_setting('default_transaction_read_only')")
        db, cu, su, addr, port, sock, ro = cur.fetchone()
        facts["connection"] = {"database": db, "current_user": cu, "session_user": su, "server_addr": addr, "port": port, "unix_socket_directories": sock,
                               "session_read_only": ro}
        if db != EXPECTED_DATABASE:
            findings.append(f"connection: current_database() is {db!r}, expected {EXPECTED_DATABASE!r}")
        cur.execute("SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = %s", (ROLE,))
        row = cur.fetchone()
        if row is None:
            findings.append(f"role {ROLE} does not exist")
            return {"findings": findings, "facts": facts}
        facts["role"] = dict(zip(("superuser", "createrole", "createdb", "bypassrls", "inherit", "login"), row))
        for flag in ("superuser", "createrole", "createdb", "bypassrls"):
            if facts["role"][flag]:
                findings.append(f"role {ROLE} has {flag} — an unexpected attribute")
        cur.execute("SELECT pg_has_role(current_user, %s, 'MEMBER') OR (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)", (ROLE,))
        facts["operator_can_set_role"] = bool(cur.fetchone()[0])
        if not facts["operator_can_set_role"]:
            findings.append(f"the connecting role cannot SET ROLE {ROLE}")
        cur.execute("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = %s", (SCHEMA,))
        row = cur.fetchone()
        if row is None:
            findings.append(f"schema {SCHEMA} does not exist")
        else:
            facts["schema_owner"] = row[0]
            if row[0] != ROLE:
                findings.append(f"schema {SCHEMA} is owned by {row[0]}, expected {ROLE}")
        for table, expected in EXPECTED_TABLES.items():
            cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = %s AND table_name = %s", (SCHEMA, table))
            got = dict(cur.fetchall())
            if not got:
                findings.append(f"table {SCHEMA}.{table} does not exist")
            elif got != expected:
                findings.append(f"table {SCHEMA}.{table} structure differs from the registered definition: "
                                f"missing {sorted(set(expected) - set(got))}, extra {sorted(set(got) - set(expected))}, "
                                f"type mismatch {sorted(c for c in set(got) & set(expected) if got[c] != expected[c])}")
            cur.execute("SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE NOT t.tgisinternal AND n.nspname = %s AND c.relname = %s", (SCHEMA, table))
            n_trig = cur.fetchone()[0]
            facts[f"triggers_on_{table}"] = n_trig
            if n_trig:
                findings.append(f"table {SCHEMA}.{table} carries {n_trig} user trigger(s) — side effects of the probe would not be the registered ones")
        cur.execute("SELECT array_agg(a.attname ORDER BY k.ord) FROM pg_constraint c JOIN pg_class r ON r.oid = c.conrelid JOIN pg_namespace n ON n.oid = r.relnamespace "
                    "CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord) JOIN pg_attribute a ON a.attrelid = r.oid AND a.attnum = k.attnum "
                    "WHERE c.contype = 'p' AND n.nspname = %s AND r.relname = 'manifest'", (SCHEMA,))
        row = cur.fetchone()
        pk = tuple(row[0]) if row and row[0] else ()
        facts["manifest_primary_key"] = list(pk)
        if pk != MANIFEST_KEY:
            findings.append(f"{SCHEMA}.manifest primary key is {list(pk)}, expected {list(MANIFEST_KEY)} — a per-run probe identity is not enforced")
        cur.execute("SELECT has_schema_privilege(%s, 'public', 'USAGE'), has_schema_privilege(%s, 'public', 'CREATE'), "
                    "has_schema_privilege(%s, %s, 'USAGE'), has_schema_privilege(%s, %s, 'CREATE')", (ROLE, ROLE, ROLE, SCHEMA, ROLE, SCHEMA))
        pu, pc, su_, sc = cur.fetchone()
        facts["schema_privileges"] = {"public.USAGE": pu, "public.CREATE": pc, f"{SCHEMA}.USAGE": su_, f"{SCHEMA}.CREATE": sc}
        if not pu:
            findings.append(f"role {ROLE} lacks USAGE on schema public")
        if pc:
            findings.append(f"role {ROLE} has CREATE on schema public — unexpected")
        if not (su_ and sc):
            findings.append(f"role {ROLE} lacks USAGE/CREATE on schema {SCHEMA}")
        cur.execute("SELECT c.relname, has_table_privilege(%s, c.oid, 'SELECT') FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY 1", (ROLE,))
        rows = cur.fetchall()
        writable, no_select = [], []                    # every public table, every write privilege, asked one by one
        for relname, can_select in rows:
            cur.execute("SELECT p FROM unnest(%s::text[]) p WHERE has_table_privilege(%s, %s, p)", (list(PUBLIC_WRITE_PRIVILEGES), ROLE, f"public.{relname}"))
            privs = [r[0] for r in cur.fetchall()]
            if privs:
                writable.append(f"public.{relname}:{'/'.join(privs)}")
            if not can_select:
                no_select.append(f"public.{relname}")
        facts["public_tables"] = len(rows)
        facts["public_tables_writable_by_role"] = writable
        facts["public_tables_without_select"] = no_select
        if writable:
            findings.append(f"role {ROLE} holds write privileges on public tables — unexpected: {', '.join(writable)}")
        if no_select:
            findings.append(f"role {ROLE} lacks SELECT on public tables (the registered configuration grants it): {', '.join(no_select)}")
        cur.execute("SELECT has_table_privilege(%s, %s, 'INSERT'), has_table_privilege(%s, %s, 'DELETE'), has_table_privilege(%s, %s, 'SELECT')",
                    (ROLE, f"{SCHEMA}.manifest", ROLE, f"{SCHEMA}.manifest", ROLE, f"{SCHEMA}.manifest"))
        ins, dele, sel = cur.fetchone()
        facts["manifest_privileges"] = {"INSERT": ins, "DELETE": dele, "SELECT": sel}
        if not (ins and dele and sel):
            findings.append(f"role {ROLE} lacks INSERT/DELETE/SELECT on {SCHEMA}.manifest — the positive control could not run")
        for t in ("events", "signal_snapshots"):
            cur.execute("SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE NOT t.tgisinternal AND n.nspname = 'public' AND c.relname = %s", (t,))
            facts[f"triggers_on_public_{t}"] = cur.fetchone()[0]            # recorded, not a finding: I1/I2 are rolled back
    return {"findings": findings, "facts": facts}


def positive_control(cn, run_id: str, fault=None) -> dict:
    """I3: as the U350 role, insert ONE row that belongs to this run and delete exactly that row, in one transaction.
    `cn` must be a u350_connection() (active role = ROLE). `fault` is a test seam: a callable invoked after the insert
    (it may raise or close the connection) to prove that a failure or interruption leaves no committed row. Any deviation
    rolls the transaction back and raises ProbeFailure; the phase/hash pair of this run is unique by primary key, so a
    collision is an error, never a silent no-op, and pre-existing rows — other probe rows included — are never touched."""
    phase, mhash = f"_probe_{run_id}", run_id
    try:
        with cn.cursor() as cur:
            cur.execute("SELECT current_user")
            who = cur.fetchone()[0]
            if who != ROLE:
                raise ProbeFailure(f"positive control must run as {ROLE}, not {who}")
            cur.execute(f"SELECT count(*) FROM {SCHEMA}.manifest WHERE phase LIKE %s ESCAPE '~'", ("~_probe%",))
            before = cur.fetchone()[0]
            cur.execute(f"INSERT INTO {SCHEMA}.manifest (phase, manifest_hash, members) VALUES (%s, %s, '[]') RETURNING phase, manifest_hash", (phase, mhash))
            got = cur.fetchone()
            if cur.rowcount != 1 or tuple(got) != (phase, mhash):
                raise ProbeFailure(f"insert affected {cur.rowcount} row(s), returned {got}")
            if fault is not None:
                fault()
            cur.execute(f"SELECT count(*) FROM {SCHEMA}.manifest WHERE phase = %s AND manifest_hash = %s", (phase, mhash))
            if cur.fetchone()[0] != 1:
                raise ProbeFailure("the inserted row is not visible to its own transaction")
            cur.execute(f"DELETE FROM {SCHEMA}.manifest WHERE phase = %s AND manifest_hash = %s", (phase, mhash))
            if cur.rowcount != 1:
                raise ProbeFailure(f"delete affected {cur.rowcount} row(s), expected exactly 1")
            cur.execute(f"SELECT count(*) FROM {SCHEMA}.manifest WHERE phase LIKE %s ESCAPE '~'", ("~_probe%",))
            after = cur.fetchone()[0]
            if after != before:
                raise ProbeFailure(f"other probe rows changed: {before} before, {after} after")
        cn.commit()
    except Exception as exc:                          # noqa: BLE001 — every failure path ends in a rollback
        try:
            cn.rollback()
        except Exception:                             # noqa: BLE001 — the connection may already be gone (interruption)
            pass
        if isinstance(exc, ProbeFailure):
            raise
        raise ProbeFailure(f"{type(exc).__name__}: {exc}") from exc
    return {"run_id": run_id, "phase": phase, "manifest_hash": mhash, "inserted": 1, "deleted": 1, "other_probe_rows_before": before, "other_probe_rows_after": after}


def ensure_namespace() -> None:
    """PROVISIONING (not verification): role, schema, grants, tables — idempotent. For a disposable test node or a deliberate
    administrative step. The isolation check no longer calls this: verification inspects, never repairs."""
    with psycopg2.connect(DSN) as cn:
        with cn.cursor() as cur:
            cur.execute(DDL_ROLE)
            cur.execute(DDL_TABLES)
            # tables created by the owner inside u350 must be writable by the role
            cur.execute(f"GRANT ALL ON ALL TABLES IN SCHEMA {SCHEMA} TO {ROLE}")
        cn.commit()


def u350_connection():
    """The ONLY sanctioned write path for U350 code: a connection whose
    active role is mechanically unable to write public-schema tables.

    The SET ROLE is issued in autocommit mode so it is SESSION-scoped: a
    later transaction rollback cannot silently revert the connection to
    the owning superuser (the exact hole the isolation gate's first run
    caught — I1's rollback un-did an in-transaction SET ROLE and I2 then
    ran with superuser privileges)."""
    cn = psycopg2.connect(DSN)
    cn.autocommit = True
    with cn.cursor() as cur:
        cur.execute(f"SET ROLE {ROLE}")
        cur.execute(f"SET search_path TO {SCHEMA}, public")
    cn.autocommit = False
    return cn
