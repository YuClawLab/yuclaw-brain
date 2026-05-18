CREATE TABLE events (
    event_id              TEXT PRIMARY KEY,
    ticker                TEXT NOT NULL,
    event_type            TEXT NOT NULL,
    magnitude             REAL NOT NULL CHECK (magnitude BETWEEN 0 AND 1),
    direction             INTEGER NOT NULL CHECK (direction IN (-1, 0, 1)),
    event_time            TIMESTAMPTZ NOT NULL,
    source_publish_time   TIMESTAMPTZ NOT NULL,
    source_ingested_time  TIMESTAMPTZ NOT NULL,
    available_as_of       TIMESTAMPTZ NOT NULL,
    source_type           TEXT NOT NULL,
    source_url            TEXT NOT NULL,
    raw_excerpt           TEXT NOT NULL CHECK (length(raw_excerpt) <= 400),
    llm_model             TEXT NOT NULL,
    llm_confidence        REAL NOT NULL CHECK (llm_confidence BETWEEN 0 AND 1),
    llm_reasoning         TEXT,
    content_hash          TEXT NOT NULL,
    signal_impact         REAL,
    parent_event_id       TEXT REFERENCES events(event_id),
    cascade_depth         INTEGER NOT NULL DEFAULT 0,
    sepolia_anchor_tx     TEXT,
    prompt_version        TEXT NOT NULL,
    event_status          TEXT NOT NULL DEFAULT 'accepted',
    reject_reason         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_events_ticker_time ON events (ticker, available_as_of DESC);
CREATE INDEX idx_events_type_time ON events (event_type, available_as_of DESC);
CREATE INDEX idx_events_content_hash ON events (content_hash);
CREATE INDEX idx_events_parent ON events (parent_event_id) WHERE parent_event_id IS NOT NULL;
CREATE UNIQUE INDEX idx_events_dedup ON events (content_hash, ticker, date_trunc('day', available_as_of));

CREATE TABLE events_raw (
    raw_id            BIGSERIAL PRIMARY KEY,
    ticker            TEXT,
    source_type       TEXT NOT NULL,
    source_url        TEXT NOT NULL UNIQUE,
    raw_text          TEXT NOT NULL,
    source_publish_time TIMESTAMPTZ,
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    extraction_status TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX idx_raw_status ON events_raw (extraction_status, fetched_at);

CREATE TABLE rejected_events (
    reject_id         BIGSERIAL PRIMARY KEY,
    raw_id            BIGINT REFERENCES events_raw(raw_id),
    ticker            TEXT,
    reject_reason     TEXT NOT NULL,
    llm_output        JSONB,
    rejected_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE signal_snapshots (
    snapshot_id           TEXT PRIMARY KEY,
    ticker                TEXT NOT NULL,
    signal_time           TIMESTAMPTZ NOT NULL,
    available_as_of       TIMESTAMPTZ NOT NULL,
    signal_label          TEXT NOT NULL,
    total_score           REAL NOT NULL,
    c1_price_momentum     REAL,
    c2_volume_confirm     REAL,
    c3_sector_velocity    REAL,
    c4_macro_regime       REAL,
    c5_oil_rates_fx       REAL,
    c6_event_impact       REAL,
    c7_peer_correlation   REAL,
    c8_cascade_effect     REAL,
    c9_model_trust        REAL,
    evidence_event_ids    TEXT[],
    content_hash          TEXT NOT NULL,
    compliance_payload    JSONB NOT NULL,
    is_backfill           BOOLEAN NOT NULL DEFAULT false,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_snap_ticker_time ON signal_snapshots (ticker, signal_time DESC);
CREATE INDEX idx_snap_available ON signal_snapshots (available_as_of DESC);

CREATE TABLE track_record (
    record_id         TEXT PRIMARY KEY,
    ticker            TEXT NOT NULL,
    signal_time       TIMESTAMPTZ NOT NULL,
    signal_label      TEXT NOT NULL,
    total_score       REAL NOT NULL,
    horizon           TEXT NOT NULL,
    forward_return    REAL,
    max_drawdown      REAL,
    outcome_status    TEXT,
    is_backfill       BOOLEAN NOT NULL DEFAULT false,
    calculated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_track_label_horizon ON track_record (signal_label, horizon, is_backfill);
