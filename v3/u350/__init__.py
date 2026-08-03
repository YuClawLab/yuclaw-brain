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


def ensure_namespace() -> None:
    """Idempotent: role, schema, grants, tables."""
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
