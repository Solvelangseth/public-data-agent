-- Dataset registry (Milestone 1).
--
-- datasets: normalized, queryable fields we extracted. Null means the
-- source did not have the value. missing_fields_json says which required
-- fields were absent and why. System-generated columns are marked below.
--
-- harvested_payloads: the untouched Resource Service (or adapter) JSON,
-- stored separately so later enrichment cannot overwrite what we harvested.
--
-- harvest_runs: one row per ingest invocation.

CREATE TABLE IF NOT EXISTS harvest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_endpoints_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    listed INTEGER NOT NULL DEFAULT 0,
    inserted INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    unchanged INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    limit_applied INTEGER,
    errors_json TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,                       -- system: source_id + native id
    source_id TEXT NOT NULL,                   -- system: adapter id
    source_native_id TEXT,                     -- FDK id, or source equivalent
    source_native_uri TEXT,                    -- dcat:Dataset URI
    title TEXT,
    title_i18n_json TEXT,
    description TEXT,
    description_i18n_json TEXT,
    publisher_id TEXT,
    publisher_name TEXT,
    publisher_uri TEXT,
    publisher_json TEXT,
    license TEXT,                              -- primary license URI
    licenses_json TEXT,                        -- all license URIs we saw
    access_path TEXT,                          -- primary access/download URL
    access_rights TEXT,
    access_rights_uri TEXT,
    issued TEXT,
    modified TEXT,
    temporal_start TEXT,
    temporal_end TEXT,
    temporal_json TEXT,
    spatial_json TEXT,
    media_types_json TEXT,
    formats_json TEXT,
    conforms_to_json TEXT,
    distributions_json TEXT,
    landing_pages_json TEXT,
    ingest_reason TEXT NOT NULL,               -- system: deterministic rule
    source_name TEXT NOT NULL,                 -- system: human source label
    source_endpoints_json TEXT NOT NULL,       -- system: exact endpoints used
    missing_fields_json TEXT NOT NULL,         -- system: field -> reason
    payload_hash TEXT NOT NULL,                -- system
    source_catalog_modified TEXT,              -- SPARQL catalog-record modified
    source_harvest_modified TEXT,              -- payload harvest.modified
    first_ingested_at TEXT NOT NULL,           -- system
    last_ingested_at TEXT NOT NULL,            -- system
    last_seen_at TEXT NOT NULL,                -- system
    last_changed_at TEXT NOT NULL,             -- system
    last_harvest_run_id INTEGER,
    UNIQUE (source_id, source_native_uri),
    FOREIGN KEY (last_harvest_run_id) REFERENCES harvest_runs(id)
);

CREATE TABLE IF NOT EXISTS harvested_payloads (
    dataset_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    fetched_from TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

CREATE INDEX IF NOT EXISTS idx_datasets_source ON datasets(source_id);
CREATE INDEX IF NOT EXISTS idx_datasets_publisher ON datasets(publisher_id);
CREATE INDEX IF NOT EXISTS idx_harvest_runs_source ON harvest_runs(source_id, started_at);
