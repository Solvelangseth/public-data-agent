# public-data-agent

An AI-native data layer for Norwegian open data.

Today, answering a question with public data means finding the right portal, the right
dataset, the right API, downloading it, combining sources, and doing the analysis by hand.
The goal here is that you describe what you want to find out, in plain language, and the
system finds the right data for you.

> *Which Norwegian municipalities have had strong population growth, high housing
> construction, and relatively few construction companies over the last five years?*

## Current status

Milestone 1 is in this repo: a local SQLite **dataset registry** and an ingest command
that harvests *metadata* from Data.norge / Felles datakatalog.

Data.norge is the first ingest source, not the product. Search, UI, joins, charts,
observation-row loading, and MCP are out of scope until later milestones.

## Principles

- **Data first, AI second.** LLMs handle intent, semantics and planning. Retrieval, joins,
  filtering, aggregation and math stay deterministic. The model never guesses factual values.
- **Sources are replaceable.** Data.norge, SSB, BRREG and others are ingestion sources into
  *our* registry. Search will run on the registry, not on someone else's search API.
- **Provenance from day one.** Every result can say what it is, who publishes it, why it was
  selected, when it was last updated, how to access it, and under which license.

## Milestone 1: dataset registry

Ingest catalogue metadata into a queryable SQLite file. A second run refreshes by upsert
on a stable id. It does not wipe the registry.

What this milestone does:

- Harvest `dcat:Dataset` membership from the Felles datakatalog SPARQL endpoint
- Fetch the original Resource Service JSON for each dataset
- Store that JSON untouched in `harvested_payloads`
- Project a normalized row into `datasets` (null when the source omitted a field)
- Record publisher, license, access path, and original source, or null plus a missing-reason
- Keep a `harvest_runs` row (started/finished, counts, source, errors)

What it does not do:

- Search or ranking
- UI
- Joins, charts, or loading observation rows
- MCP
- LLM mapping (values and field mapping are deterministic)

### Install

Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

### Ingest

Smoke ingest (a handful of live datasets). Use this when you want to touch production
without walking the whole catalog:

```bash
pda ingest --source datanorge --limit 5 --db data/registry.sqlite
```

Full catalog. SPARQL lists every `dcat:Dataset`, then the Resource Service is fetched in
batches of 25 at 5 requests/second (published limit: 5 rps, burst 10). At ~9k datasets
that is a bit over a minute if the batch endpoint holds. If a batch fails, that page
falls back to one GET per dataset, which takes closer to half an hour.

```bash
pda ingest --source datanorge --db data/registry.sqlite
```

A later run is incremental. SPARQL `dcat:CatalogRecord` `dct:modified` is compared to the
stored value. Unchanged records are not refetched. The registry is upserted, never rebuilt.

```bash
pda ingest --source datanorge --db data/registry.sqlite
pda status --db data/registry.sqlite
```

`--refresh-all` forces a Resource Service fetch for every listed dataset.

`--offset` and `--limit` page a full harvest if you want to run it in chunks:

```bash
pda ingest --source datanorge --db data/registry.sqlite --offset 0 --limit 500
pda ingest --source datanorge --db data/registry.sqlite --offset 500 --limit 500
```

Tests and CI use a fixture adapter so they never harvest the live catalog:

```bash
pda ingest --source fixture --fixtures tests/fixtures --db data/registry.sqlite
pytest
```

### Harvest path (verified 2026-08-26)

| Role | Endpoint | Why |
| --- | --- | --- |
| Membership (system of record) | `https://sparql.fellesdatakatalog.digdir.no` | `SELECT` of `?dataset a dcat:Dataset`. COUNT was 9120, matching Search. |
| Full metadata | `https://resource.api.fellesdatakatalog.digdir.no` | `POST /v1/datasets` with FDK ids, `GET /v1/datasets/{id}`, `GET /v1/datasets/by-uri?uri=...` |
| Not used | `https://search.api.fellesdatakatalog.digdir.no` | Digdir marks Search unstable and rate-limits it around 10 req/min. |

Docs: [SPARQL](https://data.norge.no/en/technical/api/sparql),
[Resource Service](https://data.norge.no/en/technical/api/resource-service).

Ingest reason stored on every Data.norge row:

`listed as dcat:Dataset in Felles datakatalog SPARQL`

The User-Agent is `public-data-agent/0.1 (+https://github.com/Solvelangseth/public-data-agent)`.
429 and 5xx responses are retried. `Retry-After` is honoured.

### Source adapters

`public_data_agent.sources.CatalogSource` is the interface. Milestone 1 ships two
implementations:

| `source_id` | Class | Used for |
| --- | --- | --- |
| `datanorge` | `DataNorgeSource` | Production harvest |
| `fixture` | `FixtureSource` | Tests and CI |

A later source (SSB, BRREG, …) is another class with the same methods. The registry
and harvest runner do not import Data.norge types.

### Registry schema

SQLite file, default path `data/registry.sqlite`. Schema: `src/public_data_agent/schema.sql`.

**`datasets`** is the normalized, queryable table. A missing upstream value is stored as
SQL `NULL`. `missing_fields_json` maps that field name to a deterministic reason string.
We do not invent publisher, license, dates, geography, or access URLs.

| Column | Origin |
| --- | --- |
| `id` | System. `{source_id}:{fdk_id}`, or `{source_id}:uri:{sha256(uri)[:20]}` if no FDK id |
| `source_id` | System. Adapter id (`datanorge`, `fixture`, …) |
| `source_native_id` | Source. FDK id |
| `source_native_uri` | Source. `dcat:Dataset` URI |
| `title`, `title_i18n_json` | Source. Display title prefers `no`, `nb`, `nn`, `en`; all present languages stay in the JSON |
| `description`, `description_i18n_json` | Source |
| `publisher_id`, `publisher_name`, `publisher_uri`, `publisher_json` | Source |
| `license`, `licenses_json` | Source. Dataset-level license, else distribution license URIs |
| `access_path` | Source. First distribution `downloadURL`, else `accessURL`, else `landingPage` |
| `access_rights`, `access_rights_uri` | Source |
| `issued`, `modified` | Source. Dataset `issued` / `modified`, not the catalog-record timestamps |
| `temporal_*`, `spatial_json` | Source |
| `media_types_json`, `formats_json`, `conforms_to_json` | Source. From `fdkFormat` / `conformsTo` |
| `distributions_json`, `landing_pages_json` | Source, projected |
| `ingest_reason` | System. Deterministic rule from the adapter |
| `source_name`, `source_endpoints_json` | System. Human label plus the exact endpoints used |
| `missing_fields_json` | System |
| `payload_hash` | System. SHA-256 of canonical source JSON |
| `source_catalog_modified` | SPARQL catalog-record `dct:modified` (used to skip refetch) |
| `source_harvest_modified` | Source. Resource Service `harvest.modified` |
| `first_ingested_at`, `last_ingested_at`, `last_seen_at`, `last_changed_at` | System |
| `last_harvest_run_id` | System |

**`harvested_payloads`** holds the original JSON (`payload_json`), the exact URL it was
fetched from, and `fetched_at`. Enrichment in later milestones must not write here.

**`harvest_runs`** holds `started_at`, `finished_at`, `status`, `listed` / `inserted` /
`updated` / `unchanged` / `failed`, `source_*`, `limit_applied`, and `errors_json`.

Inspect without extra tools:

```bash
sqlite3 data/registry.sqlite "SELECT id, title, publisher_name, license, access_path FROM datasets LIMIT 10;"
sqlite3 data/registry.sqlite "SELECT id, status, listed, inserted, updated, unchanged, failed FROM harvest_runs;"
```

## Architecture (long term)

1. **Dataset discovery** — find what data exists
2. **Data access** — retrieve the actual rows
3. **Semantic / entity layer** — what the data represents and how datasets relate
4. **Analysis engine** — joins, filtering, feature engineering
5. **Agent layer** — understand the goal, plan the analysis
6. **Interfaces** — web, API, MCP, CSV/Excel, external AI agents

## Later milestones

Natural language in, ranked relevant datasets out. That later MVP still does not answer
the analytical question. It answers: **"which data do I need in order to answer this?"**

| # | Milestone |
|---|---|
| 1 | Dataset registry — ingest catalogue metadata locally |
| 2 | Basic natural-language search |
| 3 | Metadata enrichment |
| 4 | Search benchmark vs. Data.norge |
| 5 | Query decomposition |
| 6 | Coverage checker — **discovery MVP complete** |
| 7 | First data connector |
| 8 | Two independent data sources |
| 9 | First cross-source join |
| 10 | End-to-end natural-language analysis |
| 11 | Visualization and export |
| 12 | MCP server for external agents |
| 13 | User-owned data alongside public data |

## Measuring it

A benchmark of 50–100 manually verified questions, simple, synonym, indirect,
multi-requirement, and hard phrasings, scored on Recall@5, Recall@10, MRR, and
**requirement coverage** for multi-part questions. Data.norge's own AI search is the baseline.

## Definition of success

A user submits a complex question requiring several kinds of information, and the system
understands the requirements, finds concrete relevant datasets, ranks the best ones highly,
explains why, detects what it did *not* cover, searches again where coverage is weak, shows
original sources, and does this clearly better than a plain dataset search box.

The first version does not need to be *"AI that analyzes all Norwegian public data."* It only
needs to prove: **describe what you are trying to find out, and we will find the right data.**

Direction of travel: finding data → accessing data → combining data → analyzing data →
agentic data infrastructure.
