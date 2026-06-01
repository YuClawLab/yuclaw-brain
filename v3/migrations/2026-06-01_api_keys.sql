-- Migration: API keys + lite request metering (v4 Day 8).
-- REST-only metering. CLI / MCP-stdio / in-process build_response are NEVER metered
-- (preserves the open-source self-hostable thesis). Added to the yuclaw_events DB.
-- Transactional + reversible (DOWN block at the bottom).

BEGIN;

CREATE TABLE IF NOT EXISTS api_keys (
    key_id      text PRIMARY KEY,                 -- public id, e.g. 'yk_AbC123…'
    key_hash    text NOT NULL,                    -- SHA-256 of the full secret (secret itself never stored)
    owner_email text,
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz,                      -- NULL = no expiry
    is_active   boolean NOT NULL DEFAULT true
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys (key_hash);

CREATE TABLE IF NOT EXISTS request_logs (
    id          bigserial PRIMARY KEY,
    key_id      text REFERENCES api_keys(key_id), -- NULL for anonymous (IP-metered) traffic
    client_ip   text,                             -- set for anonymous requests
    endpoint    text NOT NULL,
    ticker      text,
    status_code int NOT NULL,
    ts          timestamptz NOT NULL DEFAULT now()
);
-- Fast daily-count lookups (UTC day) for quota checks.
CREATE INDEX IF NOT EXISTS idx_reqlog_key_day
    ON request_logs (key_id, (date_trunc('day', ts AT TIME ZONE 'UTC')));
CREATE INDEX IF NOT EXISTS idx_reqlog_ip_day
    ON request_logs (client_ip, (date_trunc('day', ts AT TIME ZONE 'UTC')));

COMMIT;

-- ---------------------------------------------------------------------------
-- DOWN (rollback), run manually if needed:
--   BEGIN;
--   DROP TABLE IF EXISTS request_logs;
--   DROP TABLE IF EXISTS api_keys;
--   COMMIT;
