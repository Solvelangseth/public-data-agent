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

-- enrichments: one system-generated row per dataset, projected from stored
-- harvest fields. Never write datasets or harvested_payloads from this table.
CREATE TABLE IF NOT EXISTS enrichments (
    dataset_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,              -- always 'system'
    method TEXT NOT NULL,              -- e.g. 'deterministic_from_stored_metadata'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    topics_json TEXT,
    aliases_json TEXT,
    geography_json TEXT,
    time_coverage_json TEXT,
    fields_json TEXT,
    can_answer_json TEXT,
    missing_json TEXT NOT NULL,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

-- observations: cells retrieved from a public API. Never write
-- harvested_payloads or enrichments from this table. A missing datasets
-- row may be inserted as identity-only so the FK holds; never overwrite
-- an existing harvest row.
CREATE TABLE IF NOT EXISTS fetch_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    table_id TEXT NOT NULL,
    request_url TEXT NOT NULL,
    request_method TEXT NOT NULL,
    request_body_json TEXT,
    http_status INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    listed INTEGER NOT NULL DEFAULT 0,
    inserted INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    unchanged INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    -- series: which connector projection produced this row. One dataset_id can
    -- hold several projections of the same upstream table (a raw full fetch and
    -- a joined subset), and their dimension names differ. Without this column
    -- they blend into one pool and a filter valid for one silently matches none.
    series TEXT,
    table_id TEXT NOT NULL,
    measure TEXT NOT NULL,
    value_json TEXT,
    dimensions_json TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    request_url TEXT NOT NULL,
    http_status INTEGER NOT NULL,
    publisher_name TEXT,
    license TEXT,
    access_path TEXT,
    source_native_uri TEXT,
    fetch_run_id INTEGER NOT NULL,
    UNIQUE (dataset_id, table_id, measure, dimensions_json),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id),
    FOREIGN KEY (fetch_run_id) REFERENCES fetch_runs(id)
);

-- joined_rows: output of a cross-source join. Never write datasets,
-- harvested_payloads, enrichments, or observations from these tables.
CREATE TABLE IF NOT EXISTS join_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    join_key TEXT NOT NULL,
    left_dataset_id TEXT,
    right_dataset_id TEXT,
    left_request_url TEXT NOT NULL,
    right_request_url TEXT NOT NULL,
    left_http_status INTEGER,
    right_http_status INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    listed INTEGER NOT NULL DEFAULT 0,
    inserted INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    unchanged INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT
);

CREATE TABLE IF NOT EXISTS joined_rows (
    id TEXT PRIMARY KEY,
    join_run_id INTEGER NOT NULL,
    join_key TEXT NOT NULL,
    join_key_value TEXT NOT NULL,
    why_matched TEXT NOT NULL,
    left_dataset_id TEXT,
    right_dataset_id TEXT,
    left_publisher_name TEXT,
    right_publisher_name TEXT,
    left_license TEXT,
    right_license TEXT,
    left_access_path TEXT,
    right_access_path TEXT,
    left_request_url TEXT,
    right_request_url TEXT,
    left_retrieved_at TEXT,
    right_retrieved_at TEXT,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (join_run_id) REFERENCES join_runs(id)
);

-- printed_table_urls: PxWeb/JSON-stat table endpoints copied from harvest
-- text. Never write harvested_payloads or overwrite datasets.access_path.
CREATE TABLE IF NOT EXISTS printed_table_urls (
    dataset_id TEXT NOT NULL,
    url TEXT NOT NULL,
    kind TEXT NOT NULL,
    found_in TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (dataset_id, url),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

-- embeddings: a vector per dataset, for ranking only. An embedding can
-- reorder candidates and add ones lexical overlap missed. It can never
-- authorise a fetch or supply a value: those still come from connectors.
-- text_hash records what was embedded, so a re-harvest can re-embed only
-- the rows whose text actually changed.
CREATE TABLE IF NOT EXISTS embeddings (
    dataset_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL,
    text_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

CREATE INDEX IF NOT EXISTS idx_datasets_source ON datasets(source_id);
CREATE INDEX IF NOT EXISTS idx_datasets_publisher ON datasets(publisher_id);
CREATE INDEX IF NOT EXISTS idx_harvest_runs_source ON harvest_runs(source_id, started_at);
CREATE INDEX IF NOT EXISTS idx_observations_dataset ON observations(dataset_id, table_id);
CREATE INDEX IF NOT EXISTS idx_joined_rows_key ON joined_rows(join_key, join_key_value);
CREATE INDEX IF NOT EXISTS idx_printed_table_urls_dataset ON printed_table_urls(dataset_id);

-- ---------------------------------------------------------------------------
-- Resource index and widened record store.
--
-- The goal these serve is finding the correct data, across every domain rather
-- than statistics alone. Two things were missing for that.
--
-- First, nothing recorded what a dataset can actually return. `datasets` holds
-- what a catalogue said about it -- title, publisher, a link -- and a title is
-- a poor way to find a table. A question about building costs missed twelve
-- fetchable building-cost tables because search could only read their names.
-- The resource_* tables record the shape: which fields a resource exposes,
-- which values those fields carry, which identifier schemes it uses, and what
-- it has been verified to return.
--
-- Second, every stored row was an observation -- (measure, value, dimensions).
-- That fits a statistical cell and nothing else. A company from Brønnøysund, a
-- building from Kartverket and a parliamentary decision are not measures of
-- anything. Forcing them into that shape is what made an early connector store
-- table ids as observation values. `records` widens the store to hold them
-- while keeping one provenance spine across every kind.
--
-- `datasets` and `observations` are unchanged and still in use. New connectors
-- write `records`; the statistics already stored migrate later, deliberately,
-- rather than in the same change that introduces the target.

-- What a dataset can actually return, and how to ask for it. A row here is a
-- claim we have verified, not a guess from a URL pattern.
CREATE TABLE IF NOT EXISTS resource_capability (
    dataset_id TEXT PRIMARY KEY,
    -- observations | entities | features | documents | lookup | unverified | none
    capability TEXT NOT NULL,
    record_kind TEXT,                          -- what `records.kind` it produces
    endpoint TEXT,                             -- URL that returns data, not a landing page
    request_method TEXT,                       -- GET or POST
    period_start TEXT,                         -- earliest period the resource covers
    period_end TEXT,
    source_modified_at TEXT,                   -- publisher's own timestamp, for refresh
    verified_at TEXT,                          -- when it was last seen to return real data
    verified_sample_count INTEGER,             -- how many records that check actually saw
    notes TEXT,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

-- The fields a resource exposes: dimensions of a table, columns of a register,
-- properties of a feature collection.
CREATE TABLE IF NOT EXISTS resource_fields (
    dataset_id TEXT NOT NULL,
    field_code TEXT NOT NULL,
    field_label TEXT,
    -- key | period | measure | attribute | geometry -- says how the field may be
    -- used, so a caller can find the period field without guessing at its name.
    field_role TEXT,
    value_count INTEGER,                       -- distinct values, where bounded
    PRIMARY KEY (dataset_id, field_code),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

-- The values a field carries. This is what lets search match on what is *in* a
-- resource rather than only on how someone titled it, and it is why a question
-- naming a municipality can find a table that never mentions one in its name.
CREATE TABLE IF NOT EXISTS resource_field_values (
    dataset_id TEXT NOT NULL,
    field_code TEXT NOT NULL,
    value_code TEXT NOT NULL,
    value_label TEXT,
    PRIMARY KEY (dataset_id, field_code, value_code),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

-- Which published identifier schemes a resource speaks. Two resources naming
-- the same scheme can be related to each other; one that names none cannot be,
-- and saying so is more useful than discovering it during a failed join.
CREATE TABLE IF NOT EXISTS resource_keys (
    dataset_id TEXT NOT NULL,
    -- klass:1168 | klass:131 | brreg:orgnr | matrikkel:bygningsnummer | ...
    scheme TEXT NOT NULL,
    field_code TEXT,                           -- which field carries it
    coverage_count INTEGER,                    -- how many of the scheme's codes appear
    PRIMARY KEY (dataset_id, scheme),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

-- One row per retrieved record, whatever its shape.
--
-- The identity constraint is deliberately wide. Keyed on less, rows that differ
-- by a breakdown or by what they measure collapse onto one id and overwrite each
-- other: a join once reported 7,200 rows and stored 36 that way, reporting
-- success throughout. Everything that can make two records different is in the
-- key.
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    kind TEXT NOT NULL,                        -- observation | entity | feature | document
    -- Which connector projection wrote this, for the same reason
    -- observations.series exists: one dataset can hold several projections whose
    -- field names differ, and unseparated they blend into one unusable pool.
    series TEXT,

    -- What the record is about. The scheme generalises the geography codes that
    -- statistics share to any published identifier, so an org number and a
    -- municipality code are the same kind of handle.
    subject_scheme TEXT,
    subject_code TEXT,
    subject_label TEXT,
    period TEXT,

    -- Quantitative payload. Null for kinds that do not measure anything.
    measure TEXT,
    value_num REAL,                            -- indexed numeric access
    value_json TEXT,                           -- the value exactly as published
    -- A publisher's marker where a value is withheld. Kept apart from the value
    -- because ":" stored as data lets a later mean count a censored cell.
    suppressed TEXT,

    attributes_json TEXT NOT NULL,             -- dimensions, columns or properties
    geometry_json TEXT,                        -- features only

    -- Provenance. Identical across every kind; this is the trust boundary.
    retrieved_at TEXT NOT NULL,
    request_url TEXT NOT NULL,
    http_status INTEGER NOT NULL,
    publisher_name TEXT,
    license TEXT,
    fetch_run_id INTEGER NOT NULL,

    UNIQUE (dataset_id, kind, series, subject_code, period, measure, attributes_json),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id),
    FOREIGN KEY (fetch_run_id) REFERENCES fetch_runs(id)
);

CREATE INDEX IF NOT EXISTS records_dataset_kind ON records (dataset_id, kind);
-- "everything known about this municipality / this company", across domains.
CREATE INDEX IF NOT EXISTS records_subject ON records (subject_scheme, subject_code);
CREATE INDEX IF NOT EXISTS records_series ON records (dataset_id, series);
-- "which resources carry organisation numbers", answered without a crawl.
CREATE INDEX IF NOT EXISTS resource_keys_scheme ON resource_keys (scheme);
-- "which resources contain this code", which is how a question reaches a table
-- whose title never mentions the thing being asked about.
CREATE INDEX IF NOT EXISTS resource_field_values_code ON resource_field_values (value_code);
CREATE INDEX IF NOT EXISTS resource_capability_kind ON resource_capability (capability);
