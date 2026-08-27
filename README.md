# public-data-agent

An AI-native data layer for Norwegian open data.

Today, answering a question with public data means finding the right portal, the right
dataset, the right API, downloading it, combining sources, and doing the analysis by hand.
The goal here is that you describe what you want to find out, in plain language, and the
system finds the right data for you.

> *Which Norwegian municipalities have had strong population growth, high housing
> construction, and relatively few construction companies over the last five years?*

## Current status

Milestone 1 through 11 are in this repo: a local SQLite dataset registry, ingest from
Data.norge / Felles datakatalog, token-overlap search over that file, deterministic
enrichment in a separate `enrichments` table, a sourced search benchmark,
AND-decomposition of multi-token queries, a coverage report after retrieval,
observation-row fetch from two public APIs, one cross-source join, and one
natural-language ask path.

Discovery MVP is milestones 1 through 6. Milestone 7 fetches Oslo PxWeb cells.
Milestone 8 fetches SSB Klass classification rows. Milestone 9 joins those
Klass codes to a national befolkning table. Milestone 10 answers one Oslo-bydel
question from that join. Milestone 11 exports that answer as a stable CSV.
Milestone 12 exposes search, ask, and fetch over stdio MCP. See [MCP.md](MCP.md).
UI is later.
Measured gaps that we are not fixing in that slice live in [GAPS.md](GAPS.md).

Data.norge is the first ingest source, not the product.

## Principles

- **Data first, AI second.** LLMs handle intent, semantics and planning. Retrieval, joins,
  filtering, aggregation and math stay deterministic. The model never guesses factual values.
- **Sources are replaceable.** Data.norge, SSB, BRREG and others are ingestion sources into
  *our* registry. Search runs on the registry, not on someone else's search API.
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

Full catalog. SPARQL lists every `dcat:Dataset` in one query, then the Resource Service
is fetched in batches of 25 at 5 requests/second (published limit: 5 rps, burst 10).
Each batch is written before the next fetch. A killed run can continue: already stored
rows with the same catalog-record `dct:modified` are skipped. The registry is never wiped.

Measured 2026-08-26: 9120 datasets in 3 minutes 14 seconds. If a batch POST fails, that
page falls back to one GET per dataset, which takes closer to half an hour.

```bash
pda ingest --source datanorge --db data/registry.sqlite
```

A later run is incremental. SPARQL `dcat:CatalogRecord` `dct:modified` is compared to the
stored value. Unchanged records are not refetched.

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

`data/registry.sqlite` is local and gitignored. The 2026-08-26 full harvest was 158MB,
over the 50MB commit limit. Counts from that run are in `data/harvest_stats.json` and
`data/harvest_runs.json`. Rebuild:

```bash
pda ingest --source datanorge --db data/registry.sqlite
pda ingest --source datanorge --db data/registry.sqlite   # incremental refresh
pda stats --db data/registry.sqlite
```

Tests and CI use a fixture adapter so they never harvest the live catalog:

```bash
pda ingest --source fixture --fixtures tests/fixtures --db data/registry.sqlite
pytest
```

## Milestone 2: search the registry

Query in, ranked datasets out. Search reads the local SQLite file. It does not
call Data.norge Search.

```bash
pda search "forurensning oslo" --db data/registry.sqlite
pda search "strandsone" --db data/registry.sqlite --limit 10
```

Ranking is token overlap after casefold. Tokens are letters and digits, length
at least 2, including æøå. Weights: title 10, keyword 5, description 2. The
score is the sum of weights for each query token that appears in that field.
`why` lists the field and token for every match.

Each hit uses stored registry fields only. Publisher, license, access, time,
geography, and original links are null plus `missing_fields` when the source
omitted them. Variables are `unknown` unless the harvested payload has an
explicit variable list. Keywords are copied from the payload when present.
Nothing is invented.

This milestone does not add query decomposition, a coverage checker, joins,
a UI, or MCP.

Tests build a three-row fixture registry. CI never opens a 9k live harvest.

### Production harvest (2026-08-26)

Ran on this branch against production SPARQL + Resource Service. Search API was not used.

Endpoints:

- `https://sparql.fellesdatakatalog.digdir.no`
- `https://resource.api.fellesdatakatalog.digdir.no`

| Run | listed | inserted | updated | unchanged | failed | started (UTC) | finished (UTC) |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1 full catalog | 9120 | 9120 | 0 | 0 | 0 | 21:23:21 | 21:26:35 |
| 2 incremental refresh | 9120 | 0 | 0 | 9120 | 0 | 21:26:35 | 21:26:38 |

Run 2 left the registry at 9120 rows. Errors: none on either run.

Missing-reason rates on the 9120 stored rows (field absent upstream, stored null):

| Field | count | % |
| --- | ---: | ---: |
| publisher | 322 | 3.53 |
| license | 585 | 6.41 |
| access_path | 60 | 0.66 |
| issued | 335 | 3.67 |
| modified | 7204 | 78.99 |
| temporal | 707 | 7.75 |
| spatial | 8243 | 90.38 |
| structure | 438 | 4.80 |

`original_source` was present on every row. Title was present on every row.

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

## Milestone 3: metadata enrichment

`pda enrich` reads stored harvest rows and writes one system-generated
`enrichments` row per dataset. It does not write `datasets` or
`harvested_payloads`.

```bash
pda enrich --db data/registry.sqlite
```

`--limit` and `--offset` page the work. `--quiet` hides progress on stderr.
The command prints JSON counts: listed, inserted, updated, unchanged, failed.

Enrichment never overwrites harvest columns. It stores topics, aliases,
geography, time coverage, fields, and template `can_answer` questions.
Topics and aliases are copied from stored theme, losTheme, keyword, and
other-language titles. Geography, time coverage, and fields stay null with
a reason when the harvest row has nothing to copy. `can_answer` uses only
those templates, filled with stored title, publisher, topic, geography, or
temporal start. No LLM, and no invented numbers.

A second run is incremental. The fingerprint is the harvest `payload_hash`.
If it still matches, the enrichment row is counted unchanged and left alone.

### Production enrich (2026-08-26)

Ran against the local 9120-row registry from Milestone 1. No live catalog fetch.

| Run | listed | inserted | updated | unchanged | failed |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 full registry | 9120 | 9120 | 0 | 0 | 0 |
| 2 incremental | 9120 | 0 | 0 | 9120 | 0 |

Every enrichment row has `source=system` and `method=deterministic_from_stored_metadata`.

| Field | nonempty | null with reason |
| --- | ---: | ---: |
| topics | 9088 | 32 empty list |
| aliases | 8848 | 272 empty list |
| geography | 877 | 8243 |
| time coverage | 8982 | 138 |
| fields | 0 | 9120 |
| can_answer | 9120 | 0 |

Geography nonempty 877 matches the harvest rows that stored `spatial_json`. Fields stayed null on every live row because no harvested payload named `variables`, `variableList`, or `variable_list`. Counts are in `data/enrich_proof.json`.

This milestone does not add a UI, joins, MCP, or a search rewrite. It does not invent publishers, licenses, observation values, or missing geography and time.

## Milestone 4: search benchmark

65 questions sourced from the live registry. Every expected dataset id exists
in `data/registry.sqlite`. Every gold reason cites a stored title,
publisher_name, keyword, theme, or description. No invented labels.

Kinds: 24 simple, 11 synonym, 9 indirect, 10 multi, 11 hard.

```bash
python3 tools/build_benchmark_questions.py --db data/registry.sqlite
pda benchmark --db data/registry.sqlite --questions data/benchmark_questions.json --out data/benchmark_results.json
```

The command runs `pda search` in-process (`search()` with limit 10) and writes
Recall@5, Recall@10, MRR, and requirement coverage. Requirement coverage is the
share of listed tokens or publisher tokens that appear in a stored field of any
top-k hit.

Optional Data.norge Search API baseline. No auth. About 10 requests per minute.
Skip it when the endpoint errors or a fair run of the same questions is not
practical.

```bash
pda benchmark --db data/registry.sqlite --questions data/benchmark_questions.json --out data/benchmark_results.json --baseline datanorge
```

### Production scores (2026-08-26)

Ran on the local 9120-row registry. 65 sourced questions.

| System | Recall@5 | Recall@10 | MRR | req. cov@5 | req. cov@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| ours (`pda search`) | 0.769 | 0.800 | 0.702 | 0.869 | 0.885 |
| Data.norge Search API | 0.733 | 0.779 | 0.689 | 0.885 | 0.900 |

By kind, ours: simple Recall@5 1.00, synonym 0.91, multi 0.90, hard 0.36, indirect 0.33.

`forurensning oslo` (q045) is the known one-token gap. The three datasets that store both tokens have Recall@10 0. Requirement coverage is 1.0 because single-token hits still cover each word. The scorer was not rewritten.

Data.norge baseline used `POST https://search.api.fellesdatakatalog.digdir.no/search/datasets` with no auth, 10 requests per minute, 65 of 65 completed. Full rows are in `data/benchmark_results.json`.

`fields=0` from Milestone 3 stays an upstream gap. This milestone does not
invent variable lists. It does not rewrite the scorer. It does not add a
benchmark platform.

Rebuild the registry if the sqlite file is missing, then rerun the commands
above.

## Milestone 5: query decomposition

A multi-token query is split into independent requirements. Each requirement is
scored with the same token-overlap weights as Milestone 2 (title 10, keyword 5,
description 2). A dataset is kept only when every requirement matches. That is
AND, not a new ranker.

Quoted phrases stay one requirement. Remaining tokens are each one requirement.
A requirement can also be satisfied by stored `publisher_name` tokens. That
path is for publisher-shaped queries. It does not invent publishers.

```bash
pda search "forurensning oslo" --db data/registry.sqlite
pda search "forurensning oslo" --db data/registry.sqlite --no-decompose
pda benchmark --db data/registry.sqlite --questions data/benchmark_questions.json --out data/benchmark_results.json
```

`--no-decompose` is the Milestone 2 OR path. The scorer weights are unchanged
either way.

This milestone does not invent gold labels, guess observation values, or parse
intent with an LLM. Theme-only indirect questions still miss when the theme
string is not in title, keyword, or description. Single-token publisher
queries still miss when the publisher name is not in those fields and is only
one token.

Same 65 questions as Milestone 4. Before and after scores are in
`data/benchmark_compare.json`.

### Production scores (2026-08-26)

Same 9120-row registry and the same 65 questions as Milestone 4.

| Run | Recall@5 | Recall@10 | MRR | req. cov@5 | req. cov@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| before (OR, M4) | 0.769 | 0.800 | 0.702 | 0.869 | 0.885 |
| after (AND decompose) | 0.815 | 0.862 | 0.772 | 0.900 | 0.915 |

q045 `forurensning oslo`: Recall@10 0.00 to 1.00. The three gold rows are the top three hits. `why` says `requirements forurensning AND oslo`.

| Kind | Recall@5 before | Recall@5 after | Recall@10 before | Recall@10 after |
| --- | ---: | ---: | ---: | ---: |
| simple | 1.00 | 1.00 | 1.00 | 1.00 |
| synonym | 0.91 | 0.91 | 1.00 | 1.00 |
| multi | 0.90 | 1.00 | 0.90 | 1.00 |
| hard | 0.36 | 0.55 | 0.45 | 0.73 |
| indirect | 0.33 | 0.33 | 0.33 | 0.33 |

Indirect did not move. Theme strings that never appear in title, keyword, or description still miss. That is logged. The token-overlap weights were not changed.

## Milestone 6: coverage checker

After retrieval, `pda search` reports which decomposed requirements the
retrieved rows cover. Coverage is computed from stored title, keyword,
description, and publisher_name. Theme is not a retrieval field.

```bash
pda search "forurensning oslo" --db data/registry.sqlite
pda search "strandsone sparse" --db data/registry.sqlite --no-decompose
```

The JSON includes `coverage.requirements`, `covered`, `missing`, and
`confidence` (covered / requirements). If confidence is below 1.0, one
follow-up search runs per missing requirement. New hits are merged and
re-ranked. A follow-up that would repeat the same query is skipped.

`pda benchmark` uses the same path. Each question row stores coverage and
whether follow-up ran.

This milestone does not add theme to the scorer. Indirect theme-only
questions still miss when the theme string is not in title, keyword, or
description. Single-token publisher queries such as `AtB` still miss.
Those gaps stay logged. Discovery MVP does not load observation rows,
join sources, or expose MCP.

### Production scores (2026-08-26)

Same 9120-row registry and the same 65 questions as Milestone 5.

| Run | Recall@5 | Recall@10 | MRR | req. cov@5 | mean confidence | follow-up ran |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M5 AND | 0.815 | 0.862 | 0.772 | 0.900 |  |  |
| M6 coverage | 0.815 | 0.862 | 0.772 | 0.900 | 0.969 | 0 of 65 |

Follow-up did not move gold-set scores. AND already returns hits that cover every requirement, or the missing requirement is the same single-token query (q040 `ECON`, q042 `AGRI`). A constructed query `abortregisteret blomkålkorallskog` has empty AND, then follow-up raises confidence from 0 to 1 and adds both datasets.

q045 coverage is `forurensning` and `oslo`, confidence 1.0, no follow-up. Hard Recall@5 stays 0.55. Indirect stays 0.33. `AtB` still misses. Proof is in `data/coverage_proof.json`.

```bash
pda ingest --source datanorge --db data/registry.sqlite
pda enrich --db data/registry.sqlite
```

## Milestone 7: first data connector

Retrieve observation rows from a dataset that is already in our registry
and whose stored `access_path` is a public API. Values come from the HTTP
response. The command does not guess numbers.

The product brief asked for population in Oslo 2020-2026. SSB table 07459
is not stored as an `access_path` on a befolkning dataset in the 9120-row
registry. `datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57` (Oslo kommunes
statistikkbank) is. Its access path is a PxWeb UI URL. `pda fetch` rewrites
`/statbank/pxweb/` to `/statbank/api/v1/` and posts a JSON-stat2 query.

```bash
pda fetch --dataset datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57 \
  --table Befolkning/Folkemengde/OK-BEF008.px \
  --from-year 2020 --to-year 2026 \
  --db data/registry.sqlite
```

Rows land in `observations`, with a `fetch_runs` row for the request.
Each observation stores dataset id, publisher, license, access path,
request URL, HTTP status, and `retrieved_at`. The command does not write
`datasets`, `harvested_payloads`, or `enrichments`.

Live run 2026-08-27: HTTP 200, 28 cells, no auth. Oslo total population
2020-2026 from the response is 693494, 697010, 699827, 709037, 717710,
724290, 728714. Proof is `data/connector_proof.json`.

This milestone does not add a second source, a join, a UI, or MCP.

## Milestone 8: second data source

A second registry dataset, not Oslo kommunes statistikkbank. SSB table 07459
is still not an `access_path` on any of the 9120 rows. Stored
`versions/1160.json` (Kommuneinndeling) returns 404. Bydelsinndeling stores
a working Klass GET URL.

```bash
pda fetch --dataset datanorge:0c89041e-ae88-32ef-a765-8e1ccbd64fdd \
  --db data/registry.sqlite
```

`pda fetch` sees `data.ssb.no/api/klass/` and GETs the stored access path.
It copies `classificationItems` into `observations`. Publisher is
STATISTISK SENTRALBYRÅ. No auth.

Live run 2026-08-27: HTTP 200, 42 rows. Sample codes 030101 Gamle Oslo,
030102 Grünerløkka. Proof is `data/connector2_proof.json`.

This milestone does not join the two sources. It does not add a UI or MCP.

## Milestone 9: first cross-source join

OK-BEF008 (Oslo city totals) plus Bydelsinndeling (Klass 1168) do not share a
key to a metric. A join of the city total onto classification names is glue,
not a join. SSB table 07459 is live and has kommune `0301`, but it is still
not a stored `access_path` and it has no bydel codes.

SSB table 11763 is a public no-auth PxWeb befolkning/bydel table. Its Region
codes `030101`..`030117` and `030199` are the same strings Klass 1168 stores.
Names match on the current Oslo bydels (`030101` Gamle Oslo on both sides).
Table 10826 reuses unsuffixed `030101` for the 1988-2003 series
(Bygdøy-Frogner), so it was not used.

```bash
pda join --dataset datanorge:0c89041e-ae88-32ef-a765-8e1ccbd64fdd \
  --table 11763 --year 2025 \
  --db data/registry.sqlite --out data/join_proof.json
```

The command GETs the stored Klass `access_path`, POSTs
`https://data.ssb.no/api/v0/no/table/11763`, and inner-joins on exact
`bydel_code`. Rows land in `joined_rows`, with a `join_runs` row. The command
does not write `datasets`, `harvested_payloads`, or `enrichments`. Klass cells
may still land in `observations` through `pda fetch`. 11763 is not in the
registry, so those cells stay on the join row.

Each joined row stores both source ids, publishers, licenses, access paths,
request URLs, `retrieved_at`, the join key, and why the row matched.

Live run 2026-08-27: both HTTP 200, 18 joined rows, no auth. Sample values
from the responses: `030101` Gamle Oslo 64920, `030102` Grünerløkka 67039.
`030116` Sentrum, `030117` Marka, and `030199` are null in the 11763 body.
A second run was unchanged=18. Proof is `data/join_proof.json`.

This milestone does not add a UI or MCP.

## Milestone 10: one natural-language path

Question in. Then search, join, a YoY rate, and an answer with sources.
The demo question is exact:

`Hvilke Oslo-bydeler er størst og hvilke vokser mest?`

```bash
pda ask "Hvilke Oslo-bydeler er størst og hvilke vokser mest?" \
  --db data/registry.sqlite --out data/ask_proof.json
```

Discovery calls existing `pda search` / `search_report`. Search.py is not
edited. Fetch/join reuses Milestone 9 `pda join` for Klass 1168 and SSB 11763
for 2024 and 2025. YoY calls `methods.derive.derive_yoy` from PR 13 on main.
This slice does not reimplement the rate.

Size is latest-year population from the joined cells. Growth is
`(v_t - v_{t-1}) / v_{t-1}` for the same bydel code. Null populations stay
null. No guessed numbers.

Each ranked row cites publisher, license, access path, request URL, join key,
and why the dataset was picked.

Live run 2026-08-27: both years HTTP 200, 36 joined rows (18+18). Largest
2025 is Grünerløkka 67039, then Gamle Oslo 64920. Fastest YoY 2024-2025 is
Nordre Aker 0.0184, then Bjerke 0.0131. Search ran and returned 10 hits.
Those hits matched `og`. Klass and 11763 were still used because they are
the M9 pair that shares `bydel_code`. Proof is `data/ask_proof.json`.

This milestone does not add a UI or MCP.

## Milestone 11: export the ask result

`pda ask --out` writes JSON when the path ends in `.json`. A `.csv` path
writes a stable table a human can open in Excel or Numbers.

```bash
pda ask "Hvilke Oslo-bydeler er størst og hvilke vokser mest?" \
  --db data/registry.sqlite --out data/ask_export.csv
```

Columns are fixed: `bydel_code`, `name`, `year`, `personer`, `yoy`,
`klass_publisher`, `klass_license`, `ssb_publisher`, `ssb_license`,
`join_key`, `lineage`. Numbers come from the same joined cells as Milestone 10.
Empty `yoy` means the methods helper had no prior year, not a guessed zero.

PR 19 is on main. The CSV writer calls `methods.emit.emit` for the companion
charts. It does not draw its own figure. Charts land in `data/ask_export_charts/`.

Live run 2026-08-27: both years HTTP 200, 15 CSV rows from 36 joined cells.
First row is Grünerløkka 67039. Nordre Aker yoy is 0.0184. Proof is
`data/ask_export.csv` and `data/ask_export_proof.json`.

This milestone does not add a UI or MCP.

## Milestone 12: MCP

`pda mcp` is a stdio server. The tools call the same `search_report`, `ask`,
and `fetch` / `join` functions the CLI already uses. How to run it, and a
Cursor config snippet, live in [MCP.md](MCP.md).

```bash
pda mcp --call search \
  --query "Hvilke Oslo-bydeler er størst og hvilke vokser mest?" \
  --db data/registry.sqlite \
  --limit 5 \
  --out data/mcp_proof.json
```

## Third stored-API fetch

`pda fetch` already GETs a stored SSB Klass JSON URL. The unused live
path after Oslo PxWeb and Klass 1168 is Yrkeskatalogen, Klass version 683.
Kommuneinndeling `versions/1160.json` still returns 404. SSB 07459 is still
not an `access_path`.

```bash
pda fetch --dataset datanorge:1ab99064-d6c1-3bd8-baee-abef991ba251 \
  --table klass \
  --db data/registry.sqlite
pda methods --dataset datanorge:1ab99064-d6c1-3bd8-baee-abef991ba251 \
  --table klass:683 --entity "" --measure "" \
  --db data/registry.sqlite --out /tmp/pda-methods-683
```

Live fetch 2026-08-27: GET `https://data.ssb.no/api/klass/v1/versions/683.json`
HTTP 200, 7127 rows in `observations`, table id `klass:683`. Sample names
from the response: `0111101` MENIG (FORSVARET), `0111102` KORPORAL.
License on each row is the harvested NLOD_2_0 URL. The Klass JSON does not
print a license.

`pda methods` reads those rows from the store and does not call `pda fetch`
again. `methods.clean` drops the names because they are not numeric and
have no period. The command exits 1 with
`no observations matched entity/measure; available=[]`.
Proof is `data/connector3_proof.json`.

## SSB Statbank source

Data.norge is one ingest adapter. `pda ingest --source ssb` is another.
It walks the public PxWeb catalog at `https://data.ssb.no/api/v0/no/table`.
This slice stays in the printed `be` (Befolkning) folder and keeps the
first 8 `type=t` tables in BFS order. Table ids come from the leading
five-digit number SSB prints in each item `text`.

```bash
pda ingest --source ssb --db data/registry.sqlite --limit 8
pda fetch --dataset ssb:06683 --table 06683 \
  --from-year 2023 --to-year 2024 --db data/registry.sqlite
pda methods --dataset ssb:06683 --table 06683 --entity "" --measure "" \
  --db data/registry.sqlite --out /tmp/pda-methods-06683
```

Live ingest 2026-08-27: 8 tables, access paths such as
`https://data.ssb.no/api/v0/no/table/06683`. 07459 was not in that list
and was not written onto a datanorge row. License is null.

Live fetch of 06683: POST 200, 8 cells for 2023 and 2024. Sample values
from the response: Utenlandsadopsjoner 34 then 24, Stebarn 202 then 236.

`pda methods` reads those 8 stored rows and does not call `pda fetch`.
It returns numeric series with YoY. Proof is `data/ssb_source_proof.json`.

The next batch pages the same printed `be` walk:

```bash
pda ingest --source ssb --db data/registry.sqlite --limit 8 --offset 8
pda fetch --dataset ssb:06831 --table 06831 \
  --from-year 2021 --to-year 2022 --db data/registry.sqlite
pda search 06831 --db data/registry.sqlite
```

Live ingest 2026-08-27: 8 more tables (08135, 08136, 08134, 06831, 06854,
14746, 14747, 14748). 07459 was not in that list.

Live fetch of 06831: POST 200, 132 cells for 2021 and 2022. Sample values
from the response: Kvinner 16-19 Samboere 3 then 2, Kvinner 20-24
Samboere 23 then 23.

`pda search 06831` returns `ssb:06831`. Proof is `data/ssb_expand_proof.json`.

## Geonorge Kartkatalog source

`pda ingest --source geonorge` is another replaceable adapter. It searches
the official Kartkatalog list API and keeps Kartverket `W3C:REST` items
under the printed `REST-API` text, capped at 8. Dataset ids are the printed
Uuid. `access_path` is the printed `DistributionUrl`.

```bash
pda ingest --source geonorge --db data/registry.sqlite --limit 8
pda search kommuneinfo --db data/registry.sqlite
pda fetch --dataset geonorge:3fcce35c-759b-4c6e-adb9-f03478c6fb72 \
  --db data/registry.sqlite
```

`pda fetch` GETs the OpenAPI document the stored API root prints, then GETs
a parameter-free collection path from that document (`/kommuner` when
printed). License stays null unless Kartkatalog prints a license URI.

Live ingest 2026-08-27: 8 Kartverket REST-API rows. Live search
`kommuneinfo` returns `geonorge:3fcce35c-759b-4c6e-adb9-f03478c6fb72`.
Live fetch GETs `https://ws.geonorge.no/kommuneinfo/v1/kommuner` HTTP 200,
357 kommune rows. Sample printed values: Våler 3419, Oslo 0301.
`pda methods` is not applicable: the payload is names, not a numeric time
series (`available=[]`). Proof is `data/geonorge_source_proof.json`.

## NVE Magasinstatistikk source

Data.norge and SSB are ingest adapters. `pda ingest --source nve` is another.
It copies GET paths from the official NVE Magasinstatistikk OpenAPI at
`https://biapi.nve.no/magasinstatistikk/swagger/v1/swagger.json`.
This slice keeps at most 10 printed paths. Dataset ids are the printed
operation names. `access_path` is the printed endpoint URL.

```bash
pda ingest --source nve --db data/registry.sqlite --limit 10
pda search magasinstatistikk --db data/registry.sqlite
pda fetch --dataset nve:HentOffentligDataSisteUke --db data/registry.sqlite
```

Live ingest 2026-08-27: 4 printed GET paths, access paths such as
`https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligDataSisteUke`.
License is null.

Live fetch of `HentOffentligDataSisteUke`: GET 200, 45 cells for ISO week 34
of 2026. Sample printed `fyllingsgrad` values: EL area 3 = 0.63724726,
EL area 2 = 0.46631882, VASS area 3 = 0.82981455.

`pda search magasinstatistikk` returns `nve:HentOffentligDataSisteUke`.
The payload is one week across areas, not a time series, so methods
was not used. Proof is `data/nve_source_proof.json`.

## Brønnøysundregistrene Enhetsregisteret source

`pda ingest --source brreg` is another replaceable adapter. It lists the
printed HAL `_links` on the official Enhetsregisteret API root
`https://data.brreg.no/enhetsregisteret/api`, skipping `self`, capped at 10.
Dataset ids are the printed relation names. `access_path` is the printed href.

```bash
pda ingest --source brreg --db data/registry.sqlite --limit 10
pda search organisasjonsformer --db data/registry.sqlite
pda fetch --dataset brreg:organisasjonsformer --db data/registry.sqlite
```

`pda fetch` GETs the stored href. Observation values are copied from printed
scalar fields on the first `_embedded` list of dicts (prefer `kode`, then
`navn`, then `beskrivelse`). License and publisher stay null unless the API
prints them.

Live ingest 2026-08-27: 6 printed HAL relations. Live search
`organisasjonsformer` returns `brreg:organisasjonsformer`. Live fetch GETs
`https://data.brreg.no/enhetsregisteret/api/organisasjonsformer` HTTP 200,
44 organisation-form rows. Sample printed values: AAFY, ADOS, ANNA, ANS, AS.
`pda methods` is not applicable: the payload is codes and names, not a
numeric time series (`available=[]`). Proof is `data/brreg_source_proof.json`.

## Valgdirektoratet Valgresultat source

`pda ingest --source valg` is another replaceable adapter. It lists printed
`_sublinks` hrefs on the official Valgresultat API root
`https://valgresultat.no/api`, capped at 10. Dataset ids are the printed
paths. `access_path` is the printed href joined to that API root.

```bash
pda ingest --source valg --db data/registry.sqlite --limit 10
pda search 2009/st --db data/registry.sqlite
pda fetch --dataset valg:2009/st --db data/registry.sqlite
```

`pda fetch` GETs the stored href. Observation values are copied from printed
`partier[].stemmer.resultat.antall.total`. License and publisher stay null
unless the API prints them.

Live ingest 2026-08-27: 10 printed `_sublinks` hrefs. Live search `2009/st`
returns `valg:2009/st`. Live fetch GETs
`https://valgresultat.no/api/2009/st` HTTP 200, 26 party rows. Sample
printed vote totals: Arbeiderpartiet 949049, SV 166361, Rødt 36219,
Senterpartiet 165006, KrF 148748. `pda methods` is not applicable: one
election year, no prior period for YoY (`no derived yoy_growth values to
chart`). Proof is `data/valg_source_proof.json`.

## Folkehelseinstituttet Statistikk source

`pda ingest --source fhi` is another replaceable adapter. It lists printed
source ids on the official FHI Statistikk Open API
`https://statistikk-data.fhi.no/api/open/v1/Common/source`, capped at 10.
Dataset ids are the printed source ids. `access_path` is the official
`/Table` collection joined to that printed id.

```bash
pda ingest --source fhi --db data/registry.sqlite --limit 10
pda search Abortregisteret --db data/registry.sqlite
pda fetch --dataset fhi:abr --db data/registry.sqlite
```

`pda fetch` GETs the stored table-list URL. Observation values are copied
from printed `tableId`. License stays null unless a source object prints
one. Publisher is copied from printed `publishedBy`.

Live ingest 2026-08-27: 10 printed source ids. Live search
`Abortregisteret` returns `fhi:abr`. Live fetch GETs
`https://statistikk-data.fhi.no/api/open/v1/abr/Table` HTTP 200,
13 table rows. Sample printed table ids: 588, 589, 253, 262, 286.
`pda methods` is not applicable: the payload is a table catalog, not a
numeric time series (`no period in dimensions or period field`).
Proof is `data/fhi_source_proof.json`.

## Mattilsynet Plantevernmidler source

`pda ingest --source mattilsynet` is another replaceable adapter. It lists
printed collection GET paths on the official Mattilsynet Plantevernmidler
OpenAPI `https://api.plantevernmidler.mattilsynet.io/json`, capped at 10.
Templated paths such as `/preparat/{id}` are skipped. Dataset ids are the
printed last path segments. `access_path` is the joined collection URL.

```bash
pda ingest --source mattilsynet --db data/registry.sqlite --limit 10
pda search plantevernmidler --db data/registry.sqlite
pda fetch --dataset mattilsynet:hobby_preparater --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `navn`. License is copied from the printed OpenAPI
`info.license.url` when present. Publisher is `Mattilsynet` only when that
token is printed in `info.description`.

Live ingest 2026-08-27: 10 printed collection GET paths. Live search
`hobbybruk` returns `mattilsynet:hobby_preparater`. Live fetch GETs
`https://api.plantevernmidler.mattilsynet.io/hobby_preparater` HTTP 200,
54 product rows. Sample printed names: ANDERcontrol, Beloukha Garden,
Beloukha Garden RTU, Biltema Ugressdreper, Doff Snegler Stop.
`pda methods` is not applicable: product names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/mattilsynet_source_proof.json`.

## Utdanningsdirektoratet Nasjonalt skoleregister source

`pda ingest --source udir` is another replaceable adapter. It lists printed
collection GET paths on the official Nasjonalt skoleregister OpenAPI
`https://data-nsr.udir.no/swagger/v1/swagger.json`, capped at 10. Templated
paths such as `/enhet/{id}` are skipped. Dataset ids are the printed last
path segments. `access_path` is the printed path joined to the OpenAPI
document origin.

```bash
pda ingest --source udir --db data/registry.sqlite --limit 10
pda search skoletyper --db data/registry.sqlite
pda fetch --dataset udir:skoletyper --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `Navn`. License is copied from the printed OpenAPI
`info.license.url` when present. Publisher stays null: the spec does not
print a publisher name.

Live ingest 2026-08-27: 6 printed collection GET paths. Live search
`skoletyper` returns `udir:skoletyper`. Live fetch GETs
`https://data-nsr.udir.no/skoletyper` HTTP 200, 16 school-type rows.
Sample printed names: Grunnskole, Videregående skole, Offentlig skole,
Privatskole, Kommunal. `pda methods` is not applicable: names, not a
numeric time series (`no observations matched entity/measure; available=[]`).
Proof is `data/udir_source_proof.json`.

## Entur mobility GBFS source

`pda ingest --source entur` is another replaceable adapter. It lists printed
system `id` and `url` values on the official Entur mobility GBFS list
`https://api.entur.io/mobility/v2/gbfs`, capped at 10. Dataset ids are the
printed system ids. `access_path` is the printed system URL.

```bash
pda ingest --source entur --db data/registry.sqlite --limit 10
pda search voistavanger --db data/registry.sqlite
pda fetch --dataset entur:voistavanger --db data/registry.sqlite
```

`pda fetch` GETs the stored system URL, then follows a printed
`vehicle_types` feed URL when the discovery document lists one. Observation
values are copied from printed `name`. License and publisher stay null: the
list API does not print them.

Live ingest 2026-08-27: 10 printed systems. Live search `voistavanger`
returns `entur:voistavanger`. Live fetch GETs
`https://api.entur.io/mobility/v2/gbfs/v2/voistavanger/vehicle_types`
HTTP 200, 2 vehicle-type rows. Sample printed names: Voiager_5, Voiager_4.
`pda methods` is not applicable: vehicle names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/entur_source_proof.json`.

## Fiskeridirektoratet Fartøyregisteret source

`pda ingest --source fiskeridir` is another replaceable adapter. It lists printed
collection GET paths on the official Fartøyregisteret OpenAPI
`https://api.fiskeridir.no/vessel-api/api/openapi`, capped at 10. Templated
paths such as `/vessel-api/api/v1/vessels/{id}` are skipped. Dataset ids are
the printed last path segments. `access_path` is the printed path joined to
the OpenAPI document origin.

```bash
pda ingest --source fiskeridir --db data/registry.sqlite --limit 10
pda search fartøy --db data/registry.sqlite
pda fetch --dataset fiskeridir:vessels --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `name`. License is copied from the printed OpenAPI
`info.license.url` when present. Publisher stays null: the spec does not
print a publisher name.

Live ingest 2026-08-27: 1 printed collection GET path. Live search
`fartøy` returns `fiskeridir:vessels`. Live fetch GETs
`https://api.fiskeridir.no/vessel-api/api/v1/vessels` HTTP 200, 30 vessel
rows. Sample printed names: KVALVIK, SVANHILD, CHANS. `pda methods` is not
applicable: names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/fiskeridir_source_proof.json`.

## Statnett Driftsdata source

`pda ingest --source statnett` is another replaceable adapter. It lists printed
collection GET paths on the official Driftsdata swagger
`https://driftsdata.statnett.no/restapi/swagger/docs/v1`, capped at 10.
Templated paths are skipped. Dataset ids are the printed swagger
`operationId` values so two `LastChanges` paths stay distinct. `access_path`
is the printed swagger `host` + `basePath` + path.

```bash
pda ingest --source statnett --db data/registry.sqlite --limit 10
pda search elspot --db data/registry.sqlite
pda fetch --dataset statnett:ElspotPowerSituation_GetPowerSituations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `elspotId`. License and publisher stay null: the spec does not
print them.

Live ingest 2026-08-27: 10 printed collection GET paths. Live search
`elspot` returns `statnett:ElspotPowerSituation_GetPowerSituations`. Live
fetch GETs
`https://driftsdata.statnett.no/RestApi/ElspotPowerSituation/GetPowerSituations`
HTTP 200, 5 elspot-area rows. Sample printed ids: NO3, NO4, NO1, NO2, NO5.
`pda methods` is not applicable: area ids, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/statnett_source_proof.json`.

## Utdanning.no API source

`pda ingest --source utdanning` is another replaceable adapter. It lists printed
collection GET paths on the official Utdanning.no OpenAPI
`https://api.utdanning.no/openapi.json`, capped at 10. Templated
paths such as `/vgs/skole/{vilbli_org_id}` are skipped. Dataset ids are
the printed last path segments. `access_path` is the printed path joined to
the OpenAPI document origin.

```bash
pda ingest --source utdanning --db data/registry.sqlite --limit 10
pda search stedsvelger --db data/registry.sqlite
pda fetch --dataset utdanning:stedsvelger --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from a printed name field (`fylkenavn`, `tittel`, `name`, `navn`, or
`yrke_navn`) when present. License and publisher stay null: the spec does
not print those fields.

Live ingest 2026-08-27: 10 printed collection GET paths. Live search
`stedsvelger` returns `utdanning:stedsvelger`. Live fetch GETs
`https://api.utdanning.no/arbeidsmarkedskart/stedsvelger` HTTP 200, 24
fylke-name rows. Sample printed names: Jan Mayen, Kontinentalsokkelen,
Oslo. `pda methods` is not applicable: names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/utdanning_source_proof.json`.

## Meteorologisk institutt Metalerts source

`pda ingest --source met` is another replaceable adapter. It lists printed
collection GET paths on the official Metalerts swagger
`https://api.met.no/weatherapi/metalerts/2.0/swagger`, capped at 10.
Templated `{format}` paths are skipped. Dataset ids are the last printed
path segment. `access_path` is the swagger origin + printed `basePath` +
path. License is the printed swagger CC BY 4.0 URL. Publisher stays null.

```bash
pda ingest --source met --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset met:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name`. License is the printed swagger
CC BY 4.0 URL. Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 10 printed collection GET paths. Live search
`locations` returns `met:locations`. Live fetch GETs
`https://api.met.no/weatherapi/metalerts/2.0/locations` HTTP 200, 71
county/area rows. Sample printed names: Oslo, Rogaland, Møre og Romsdal,
Nordland, Østfold. `pda methods` is not applicable: names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/met_source_proof.json`.

## Havforskningsinstituttet OGC API Features source

`pda ingest --source hi` is another replaceable adapter. It lists printed
collections on the official OGC API Features collections document
`https://kart.hi.no/data/ogc/features/v1/collections`, capped at 10.
Dataset ids are the printed collection `id` values. `access_path` is the
printed `application/json` items href.

```bash
pda ingest --source hi --db data/registry.sqlite --limit 10
pda search Strandnot --db data/registry.sqlite
pda fetch --dataset hi:hi_basemap:Strandnot --db data/registry.sqlite
```

`pda fetch` GETs the stored items URL. Observation values are copied from
a printed name field (`navn`, `Description`, `Station`, `title`, `name`,
`id`, or `fid`) when present. Nested geometry is not copied. License and
publisher stay null: the collections document does not print those fields.

Live ingest 2026-08-27: 10 printed collections. Live search `Strandnot`
returns `hi:hi_basemap:Strandnot`. Live fetch GETs
`https://kart.hi.no/data/ogc/features/v1/collections/hi_basemap:Strandnot/items?f=application%2Fjson`
HTTP 200, 163 station rows. Sample printed descriptions: Holme utenfor
Skarsnes, Hvaler; Knudrete fjell nord for strand. `pda methods` is not
applicable: names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/hi_source_proof.json`.

## Kystverket Kystdatahuset source

`pda ingest --source kystverket` is another replaceable adapter. It lists printed
collection GET paths on the official Kystdatahuset OpenAPI
`https://kystdatahuset.no/ws/swagger/v1/swagger.json`, capped at 10.
Templated `{id}` paths are skipped. Dataset ids are the printed OpenAPI
paths. `access_path` is the swagger origin + printed relative server `/ws`
+ path. License is the printed OpenAPI NLOD URL. Publisher stays null.

```bash
pda ingest --source kystverket --db data/registry.sqlite --limit 10
pda search counties --db data/registry.sqlite
pda fetch --dataset kystverket:api/location/counties --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from a printed name field (`countyname`, `label`, `area_name`, `name`,
`title`, or `code`) when present. License is the printed OpenAPI NLOD URL.
Publisher stays null: the spec does not print a publisher field.

Live ingest 2026-08-27: 10 printed collection GET paths. Live search
`counties` returns `kystverket:api/location/counties`. Live fetch GETs
`https://kystdatahuset.no/ws/api/location/counties` HTTP 200, 17
county-name rows. Sample printed names: Agder, Akershus, Buskerud,
Finnmark, Innlandet. `pda methods` is not applicable: names, not a
numeric time series (`no observations matched entity/measure; available=[]`).
Proof is `data/kystverket_source_proof.json`.

## NIBIO IPM Resource Hub Weather source

`pda ingest --source nibio` is another replaceable adapter. It lists printed
collection GET paths on the official NIBIO IPM Resource Hub OpenAPI
`https://irh.nibio.no/weather/openapi.json`, capped at 10. Dataset ids are
the printed path's last segment. `access_path` is the OpenAPI origin plus
the printed path.

```bash
pda ingest --source nibio --db data/registry.sqlite --limit 10
pda search parameters --db data/registry.sqlite
pda fetch --dataset nibio:parameter --db data/registry.sqlite
```

`pda fetch` GETs the stored path. Observation values are copied from a
printed name field (`name`, `title`, `navn`, or `id`) when present. Nested
objects are not copied. License and publisher stay null: the OpenAPI
`info` object does not print those fields.

Live ingest 2026-08-27: 10 printed collection GET paths. Live search
`parameters` returns `nibio:parameter`. Live fetch GETs
`https://irh.nibio.no/weather/parameter` HTTP 200, 44 parameter rows.
Sample printed names: Instantaneous temperature at 2m, Mean air
temperature at 2m, Minimum air temperature at 2m. `pda methods` is not
applicable: names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nibio_source_proof.json`.

## Miljødirektoratet Vannmiljø source

`pda ingest --source miljodir` is another replaceable adapter. It lists printed
collection GET paths on the official Vannmiljø swagger
`https://vannmiljoapi.miljodirektoratet.no/swagger/docs/v1`, capped at 10.
Templated `{id}` paths are skipped. Dataset ids are the printed swagger
`operationId` values. `access_path` is the printed host + basePath + path.
License and publisher stay null: the spec does not print those fields.

```bash
pda ingest --source miljodir --db data/registry.sqlite --limit 10
pda search Medium --db data/registry.sqlite
pda fetch --dataset miljodir:Public_GetMediumList --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from a printed name field (`Name`, `name`, `title`, `MediumID`, or `id`)
when present. License and publisher stay null.

Live ingest 2026-08-27: 10 printed collection GET paths. Live search
`Medium` returns `miljodir:Public_GetMediumList`. Live fetch GETs
`https://vannmiljoapi.miljodirektoratet.no/api/Public/GetMediumList`
HTTP 200, 54 medium-name rows. Sample printed names: Biota bløtdeler,
Biota helkropp, Biota lever, Biota muskelvev, Biota mageinnhold.
`pda methods` is not applicable: names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/miljodir_source_proof.json`.

## Oslo kommune Statistikkbank source

`pda ingest --source oslo` is another replaceable adapter. It lists printed
`type=t` tables on the official Oslo kommune PxWeb catalog
`https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no`, staying
inside the printed `db1` / `Befolkning` subject and capped at 10.
Dataset ids are the printed table ids. `access_path` is the printed
folder URL plus the printed table id.

```bash
pda ingest --source oslo --db data/registry.sqlite --limit 10
pda search BEF008 --db data/registry.sqlite
pda fetch --dataset oslo:OK-BEF008.px --from-year 2024 --to-year 2026 \
  --db data/registry.sqlite
```

`pda fetch` POSTs the stored PxWeb table URL. Observation values are
copied from printed json-stat2 cells. License and publisher stay null:
the table metadata does not print those fields.

Live ingest 2026-08-27: 10 printed befolkning tables. Live search
`BEF008` returns `oslo:OK-BEF008.px`. Live fetch POSTs
`https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no/db1/Befolkning/Folkemengde/OK-BEF008.px`
HTTP 200, 12 cells for 2024-2026. Sample printed Oslo totals:
717710, 724290, 728714. `pda methods` reads those stored numeric
rows and returns YoY. Proof is `data/oslo_source_proof.json`.

## Trondheim kommune Åpne Data source

`pda ingest --source trondheim` is another replaceable adapter. It lists printed
datasets on the official Trondheim Åpne Data export
`https://data.trondheim.kommune.no/api/v3/datasets/export.json`, capped at 10.
Dataset ids are the printed catalog `id` values. `access_path` is the printed
`/api/v3/dataset/:id` URL. License is copied from a printed `licence.url` when
present. Publisher stays null: the catalog does not print a publisher name.

```bash
pda ingest --source trondheim --db data/registry.sqlite --limit 10
pda search Badeplasser --db data/registry.sqlite
pda fetch --dataset trondheim:e736k --db data/registry.sqlite
```

`pda fetch` GETs the stored dataset API URL. Observation values are copied
from printed resource and link titles. Nested QA objects are not copied.

Live ingest 2026-08-27: 9 printed catalog datasets. Live search
`Badeplasser` returns `trondheim:e736k`. Live fetch GETs
`https://data.trondheim.kommune.no/api/v3/dataset/e736k`
HTTP 200, 2 resource/link-title rows. Sample printed titles:
Badeplasser i Trondheimsregionen, Badeplasser.
`pda methods` is not applicable: titles, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/trondheim_source_proof.json`.

## Utdanningsdirektoratet Nasjonalt barnehageregister source

`pda ingest --source nbr` is another replaceable adapter. It lists printed
collection GET paths on the official Nasjonalt barnehageregister OpenAPI
`https://data-nbr.udir.no/swagger/v3/swagger.json`, capped at 10. Templated
paths such as `/v3/enhet/{orgnr}` are skipped. Dataset ids are the printed
last path segments. `access_path` is the printed path joined to the OpenAPI
document origin.

```bash
pda ingest --source nbr --db data/registry.sqlite --limit 10
pda search barnehagekategorier --db data/registry.sqlite
pda fetch --dataset nbr:barnehagekategorier --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `Navn`. License is copied from the printed OpenAPI
`info.license.url` when present. Publisher stays null: the spec does not
print a publisher name.

Live ingest 2026-08-27: 8 printed collection GET paths. Live search
`barnehagekategorier` returns `nbr:barnehagekategorier`. Live fetch GETs
`https://data-nbr.udir.no/v3/barnehagekategorier` HTTP 200, 10
kindergarten-type rows. Sample printed names: Offentlig barnehage,
Kommunal barnehage, Privat barnehage, Fylkeskommunal barnehage,
Statlig barnehage. `pda methods` is not applicable: names, not a
numeric time series (`no observations matched entity/measure; available=[]`).
Proof is `data/nbr_source_proof.json`.

## Norges Bank Open Data source

`pda ingest --source norgesbank` is another replaceable adapter. It lists printed
dataflow ids on the official Norges Bank SDMX list API
`https://data.norges-bank.no/api/dataflow?format=sdmx-json`, capped at 10.
Dataset ids are the printed dataflow ids. `access_path` joins each printed id
to `/api/data/{id}?format=sdmx-json` on the same host.

```bash
pda ingest --source norgesbank --db data/registry.sqlite --limit 10
pda search styringsrenten --db data/registry.sqlite
pda fetch --dataset norgesbank:ANN_KPRA --db data/registry.sqlite
```

`pda fetch` GETs the stored dataflow URL. Observation values are copied from
printed SDMX-JSON observation arrays. License and publisher stay null: the
list API does not print them.

Live ingest 2026-08-27: 10 printed dataflow ids. Live search
`styringsrenten` returns `norgesbank:ANN_KPRA`. Live fetch GETs
`https://data.norges-bank.no/api/data/ANN_KPRA?format=sdmx-json` HTTP 200,
281 key-policy-rate rows. Sample printed values: 13.00 on 1986-01-13,
4.25 on 2026-08-13. `pda methods` is not applicable without editing
`methods/`: `TIME_PERIOD` dates are not a year-like period alias
(`no period in dimensions or period field`). Proof is
`data/norgesbank_source_proof.json`.

## Norsk Polarinstitutt Open Data API source

`pda ingest --source npolar` is another replaceable adapter. It lists printed
service paths on the official Norsk Polarinstitutt service catalog
`https://api.npolar.no/service/?q=*&format=json`, capped at 10. Dataset ids
are the printed service `id` values. `access_path` joins each printed path
to the catalog origin with the same `q=*&format=json` query the catalog
uses to print members.

```bash
pda ingest --source npolar --db data/registry.sqlite --limit 10
pda search Country --db data/registry.sqlite
pda fetch --dataset npolar:country-api --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `name` or `title`. License and publisher stay null: the
service catalog does not print those fields.

Live ingest 2026-08-27: 5 printed service paths. Live search
`Country` returns `npolar:country-api`. Live fetch GETs
`https://api.npolar.no/country/?q=*&format=json` HTTP 200, 100
country-name rows (the catalog's default page). Sample printed names:
North Korea, Oman, Poland, Nauru, Chad.
`pda methods` is not applicable: names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/npolar_source_proof.json`.

## Kartverket Stedsnavn source

`pda ingest --source stedsnavn` is another replaceable adapter. It lists printed
collection GET paths on the official Kartverket Stedsnavn OpenAPI
`https://ws.geonorge.no/stedsnavn/v1/openapi.json`, capped at 10. Dataset ids
are the printed path's last segment. `access_path` is the printed OpenAPI
`servers[0].url` plus the printed path.

```bash
pda ingest --source stedsnavn --db data/registry.sqlite --limit 10
pda search navneobjekttyper --db data/registry.sqlite
pda fetch --dataset stedsnavn:navneobjekttyper --db data/registry.sqlite
```

`pda fetch` GETs the stored path. Observation values are copied from a
printed name field (`navneobjekttype`, `språk`, `name`, `title`, or `navn`)
when present. Nested objects are not copied. License and publisher stay
null: the OpenAPI `info` object does not print those fields.

This source is Kartverket's Stedsnavn search API, not Geonorge Kartkatalog.

Live ingest 2026-08-27: 5 printed collection GET paths (the catalog prints
5, cap 10). Live search `navneobjekttyper` returns
`stedsnavn:navneobjekttyper`. Live fetch GETs
`https://api.kartverket.no/stedsnavn/v1/navneobjekttyper` HTTP 200, 291
navneobjekttype rows. Sample printed names: Militært bygg/anlegg,
Fornøyelsespark, Idrettshall. `pda methods` is not applicable: names, not
a numeric time series (`no observations matched entity/measure;
available=[]`). Proof is `data/stedsnavn_source_proof.json`.

## Sikt DataverseNO source

`pda ingest --source sikt` is another replaceable adapter. It lists printed
titled dataverses on the official Sikt DataverseNO collection catalog
`https://dataverse.no/api/dataverses/:root/contents`, capped at 10. Dataset
ids are the printed collection `id` values. `access_path` keeps the
catalog's own `/api/dataverses/:root/contents` path and substitutes the
printed id for `:root`. Root members without a printed title (datasets)
are left unused.

```bash
pda ingest --source sikt --db data/registry.sqlite --limit 10
pda search TROLLing --db data/registry.sqlite
pda fetch --dataset sikt:3 --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `title` or `identifier`. License and publisher stay null: the
collection catalog does not print those fields.

Live ingest 2026-08-27: 10 printed titled dataverses. Live search
`TROLLing` returns `sikt:3`. Live fetch GETs
`https://dataverse.no/api/dataverses/3/contents` HTTP 200, 254
collection-member rows. Sample printed values: AcqVA Aurora, ASTRID,
S5SXRG, T6KSX4, 2NKJPG.
`pda methods` is not applicable: titles and identifiers, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/sikt_source_proof.json`.

## Statens vegvesen Dataportalen source

`pda ingest --source vegvesen` is another replaceable adapter. It lists printed
package names on the official Statens vegvesen Dataportalen CKAN
`https://dataut.vegvesen.no/api/3/action/package_list`, capped at 10.
Dataset ids are the printed package names. `access_path` is the catalog's
own `package_show?id=` action. License is copied from a printed
`license_url` when it is an http(s) URI. Publisher is copied from a printed
`organization.title` when present.

```bash
pda ingest --source vegvesen --db data/registry.sqlite --limit 10
pda search Artsmangfold --db data/registry.sqlite
pda fetch --dataset vegvesen:artsmangfold --db data/registry.sqlite
```

`pda fetch` GETs the stored package_show URL. Observation values are copied
from printed resource `name` (or `url` when name is empty). Nested objects
are not copied.

This source is Statens vegvesen's CKAN dataportal, not NVDB OpenAPI
(known User-Agent 400 skip) and not Trafikkdata GraphQL.

Live ingest 2026-08-27: 10 printed package names (catalog prints 85,
cap 10). Live search `Artsmangfold` returns `vegvesen:artsmangfold`.
Live fetch GETs
`https://dataut.vegvesen.no/api/3/action/package_show?id=artsmangfold`
HTTP 200, 2 resource-name rows. Sample printed names: Åpne data via
NVDB api (XML), Åpne data via NVDB api (JSON). `pda methods` is not
applicable: resource names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/vegvesen_source_proof.json`.

## Fiskeridirektoratet Kjøperregisteret source

`pda ingest --source buyer` is another replaceable adapter. It lists printed
collection GET paths on the official Kjøperregisteret OpenAPI
`https://api.fiskeridir.no/buyer-api/openapi`, capped at 10. Templated
paths such as `/buyer-api/v1/locations/{locationId}` are skipped. Dataset
ids are the printed last path segments. `access_path` is the printed path
joined to the printed `servers[0].url`. This is a different Fiskeridirektoratet
register from `--source fiskeridir` (Fartøyregisteret).

```bash
pda ingest --source buyer --db data/registry.sqlite --limit 10
pda search kjøpssteder --db data/registry.sqlite
pda fetch --dataset buyer:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `name` when it is a non-empty string, otherwise `locationId`.
License is copied from the printed OpenAPI `info.license.url` when present.
Publisher stays null: the spec does not print a publisher name.

Live ingest 2026-08-27: 1 printed collection GET path. Live search
`kjøpssteder` returns `buyer:locations`. Live fetch GETs
`https://api.fiskeridir.no/buyer-api/v1/locations` HTTP 200, 100
kjøpssted rows. Sample printed values: 200092526, TOR GUNNAR OTTERLEI,
OCEANBLOCK AS, DAG SELNES JOHANSEN.
`pda methods` is not applicable: names and location ids, not a numeric
time series (`no period in dimensions or period field`).
Proof is `data/buyer_source_proof.json`.

## Udir Nasjonalt register for opplæringskontorer source

`pda ingest --source nor` is another replaceable adapter. It lists printed
collection GET paths on the official Nasjonalt register for
opplæringskontorer OpenAPI
`https://data-nor.udir.no/swagger/v4/swagger.json`, capped at 10. Templated
paths such as `/v4/enhet/{organisasjonsnummer}` are skipped. Dataset ids
are the printed last path segments. `access_path` is the printed path
joined to the OpenAPI document origin.

```bash
pda ingest --source nor --db data/registry.sqlite --limit 10
pda search målformer --db data/registry.sqlite
pda fetch --dataset nor:maalformer --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `Navn` on a printed `*Liste` array. License is copied from
the printed OpenAPI `info.license.url` when present. Publisher stays
null: the spec does not print a publisher name.

This source is Udir NOR (`data-nor.udir.no`), not NSR (`--source udir`)
and not NBR (`--source nbr`).

Live ingest 2026-08-27: 6 printed collection GET paths (catalog prints 6,
cap 10). Live search `målformer` returns `nor:maalformer`. Live fetch
GETs `https://data-nor.udir.no/v4/maalformer` HTTP 200, 3 language-name
rows. Sample printed names: Udefinert, Bokmål, Nynorsk. `pda methods`
is not applicable: names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nor_source_proof.json`.

## Fiskeridirektoratet NYTEK source

`pda ingest --source nytek` is another replaceable adapter. It lists printed
collection GET paths on the official NYTEK OpenAPI
`https://api.fiskeridir.no/nytek-public/v3/api-docs`, capped at 10. Templated
paths such as `/api/v3/certificates/{site-nr}` are skipped. Dataset ids are
the printed last path segments. `access_path` is the printed path joined to
the printed `servers[0].url`. This is a different Fiskeridirektoratet
register from `--source fiskeridir` (Fartøyregisteret) and `--source buyer`
(Kjøperregisteret).

```bash
pda ingest --source nytek --db data/registry.sqlite --limit 10
pda search anleggssertifikat --db data/registry.sqlite
pda fetch --dataset nytek:certificates --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `installationCertificate.siteName` when it is a non-empty
string, otherwise `siteNr`. License is copied from the printed OpenAPI
`info.license.url` when present. Publisher stays null: the spec does not
print a publisher name.

Live ingest 2026-08-27: 1 printed collection GET path. Live search
`anleggssertifikat` returns `nytek:certificates`. Live fetch GETs
`https://api.fiskeridir.no/nytek-public/api/v3/certificates` HTTP 200, 20
anleggssertifikat rows. Sample printed values: TRÆLVIKA, MOLLVIKA,
OTERNESET, GISSØYSUNDET S, SKJELLESVIKA.
`pda methods` is not applicable: site names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nytek_source_proof.json`.

## Udir Nasjonalt register for PP-tjenester source

`pda ingest --source npr` is another replaceable adapter. It lists printed
collection GET paths on the official Nasjonalt register for PP-tjenester
OpenAPI `https://data-npr.udir.no/swagger/v4/swagger.json`, capped at 10.
Templated paths such as `/v4/enhet/{organisasjonsnummer}` are skipped.
Dataset ids are the printed last path segments. `access_path` is the
printed path joined to the OpenAPI document origin.

```bash
pda ingest --source npr --db data/registry.sqlite --limit 10
pda search næringskoder --db data/registry.sqlite
pda fetch --dataset npr:naeringskoder --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `Navn` on a printed `*Liste` array. License is copied from
the printed OpenAPI `info.license.url` when present. Publisher stays
null: the spec does not print a publisher name.

This source is Udir NPR (`data-npr.udir.no`), not NSR (`--source udir`),
not NBR (`--source nbr`), and not NOR (`--source nor`).

Live ingest 2026-08-27: 7 printed collection GET paths (catalog prints 7,
cap 10). Live search `næringskoder` returns `npr:naeringskoder`. Live
fetch GETs `https://data-npr.udir.no/v4/naeringskoder` HTTP 200, 1
næringskode-name row. Sample printed name:
Pedagogisk-psykologisk rådgivningstjeneste. `pda methods` is not
applicable: names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/npr_source_proof.json`.

## Udir Nasjonalt register for skolefritidsordningen source

`pda ingest --source nfr` is another replaceable adapter. It lists printed
collection GET paths on the official Nasjonalt register for
skolefritidsordningen OpenAPI
`https://data-nfr.udir.no/swagger/v4/swagger.json`, capped at 10. Templated
paths such as `/v4/enhet/{organisasjonsnummer}` are skipped. Dataset ids
are the printed last path segments. `access_path` is the printed path
joined to the OpenAPI document origin.

```bash
pda ingest --source nfr --db data/registry.sqlite --limit 10
pda search skolefritidsordningskategorier --db data/registry.sqlite
pda fetch --dataset nfr:skolefritidsordningskategorier --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `Navn` on a printed `*Liste` array. License is copied from
the printed OpenAPI `info.license.url` when present. Publisher stays
null: the spec does not print a publisher name.

This source is Udir NFR (`data-nfr.udir.no`), not NSR (`--source udir`),
NBR (`--source nbr`), NOR (`--source nor`), or NPR (`--source npr`).

Live ingest 2026-08-27: 8 printed collection GET paths (catalog prints 8,
cap 10). Live search `skolefritidsordningskategorier` returns
`nfr:skolefritidsordningskategorier`. Live fetch GETs
`https://data-nfr.udir.no/v4/skolefritidsordningskategorier` HTTP 200, 3
kategori-name rows. Sample printed names: Ingen verdi, Offentlig
skolefritidsordning, Privat skolefritidsordning. `pda methods` is not
applicable: names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nfr_source_proof.json`.

## Udir NXR Fellestjeneste source

`pda ingest --source nxr` is another replaceable adapter. It lists printed
collection GET paths on the official NXR Fellestjeneste OpenAPI
`https://data-nxr-fellestjeneste.udir.no/swagger/v2/swagger.json`, capped at 10.
Templated paths such as `/api/v2/enhetinfo/{organisasjonsnummer}` are skipped.
Dataset ids are the printed last path segments. `access_path` is the printed
path joined to the OpenAPI document origin.

```bash
pda ingest --source nxr --db data/registry.sqlite --limit 10
pda search fylkedata --db data/registry.sqlite
pda fetch --dataset nxr:fylkedata --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `Fylkesnavn` / `Kommunenavn` / `Bydelnavn` / `Navn` on a printed
array. License is copied from the printed OpenAPI `info.license.url` when
present. Publisher stays null: the spec does not print a publisher name.

This source is Udir NXR Fellestjeneste (`data-nxr-fellestjeneste.udir.no`),
not NSR (`--source udir`), NBR (`--source nbr`), or NOR (`--source nor`).
Register for lærebedrifter (`data-nlr.udir.no`) requires an authentication
key and is unused.

Live ingest 2026-08-27: 10 printed collection GET paths (catalog prints 21,
cap 10). Live search `fylkedata` returns `nxr:fylkedata`. Live fetch GETs
`https://data-nxr-fellestjeneste.udir.no/api/v2/fylkedata` HTTP 200, 69
county-name rows. Sample printed names: Smaalenenes amt, Østfold,
Akershus amt, Akershus, Christiania amt. `pda methods` is not applicable:
names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nxr_source_proof.json`.

## Udir Barnehagefakta source

`pda ingest --source baf` is another replaceable adapter. It lists printed
collection GET paths on the official Barnehagefakta swagger
`https://www.barnehagefakta.no/swagger/docs/v1`, capped at 10. Templated
paths such as `/api/Barnehage/{id}` are skipped. Dataset ids are the
printed last path segments. `access_path` is the printed path joined to
the printed swagger host.

```bash
pda ingest --source baf --db data/registry.sqlite --limit 10
pda search fylker --db data/registry.sqlite
pda fetch --dataset baf:Fylker --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `fylkesnavn` on a printed `fylker` array, or printed `navn`
on a location list. License and publisher stay null: the swagger does
not print a license URL or publisher name.

This source is Udir Barnehagefakta (`www.barnehagefakta.no`), not NBR
(`--source nbr`), NSR (`--source udir`), NFR (`--source nfr`), or NXR
(`--source nxr`).

Live ingest 2026-08-27: 2 printed collection GET paths (catalog prints 2,
cap 10). Live search `fylker` returns `baf:Fylker`. Live fetch GETs
`https://www.barnehagefakta.no/api/Fylker` HTTP 200, 16 fylkesnavn
rows. Sample printed names: Oslo, Rogaland, Møre og Romsdal, Nordland
- Nordlánnda, Svalbard. `pda methods` is not applicable: names, not a
numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/baf_source_proof.json`.

## Fiskeridirektoratet Offentlig Akvakulturregister source

`pda ingest --source aqua` is another replaceable adapter. It lists printed
collection GET paths on the official Offentlig Akvakulturregister OpenAPI
`https://api.fiskeridir.no/pub-aqua/api/api-docs`, capped at 10. Templated
paths such as `/api/v1/sites/{site-nr}` are skipped. Dataset ids are the
printed last path segments. `access_path` is the printed path joined to
the printed `servers[0].url`. This is a different Fiskeridirektoratet
register from `--source fiskeridir` (Fartøyregisteret), `--source buyer`
(Kjøperregisteret), and `--source nytek` (NYTEK).

```bash
pda ingest --source aqua --db data/registry.sqlite --limit 10
pda search områder --db data/registry.sqlite
pda fetch --dataset aqua:areas --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `name` when it is a non-empty string, otherwise `defaultName`
/ `nbNoName` / `regulationName`. License is copied from the printed
OpenAPI `info.license.url` when present. Publisher stays null: the spec
does not print a publisher name.

This source is Fiskeridirektoratet Offentlig Akvakulturregister
(`api.fiskeridir.no/pub-aqua`), not Fartøyregisteret, Kjøperregisteret,
or NYTEK.

Live ingest 2026-08-27: 10 printed collection GET paths (catalog prints
10, cap 10). Live search `områder` returns `aqua:areas`. Live fetch GETs
`https://api.fiskeridir.no/pub-aqua/api/v1/areas` HTTP 200, 10 area-name
rows. Sample printed names: ARUBA, AFGHANISTAN, ANGOLA, ANGUILLA,
ALBANIA. `pda methods` is not applicable: names, not a numeric time
series (`no observations matched entity/measure; available=[]`).
Proof is `data/aqua_source_proof.json`.

## Fiskeridirektoratet Akvakulturforskning source

`pda ingest --source research` is another replaceable adapter. It lists printed
collection GET paths on the official Akvakulturforskning OpenAPI
`https://api.fiskeridir.no/aqua-research-project-api-public/v3/api-docs`,
capped at 10. Templated paths such as
`/api/v1/research-project/{projectNumber}` are skipped. Dataset ids are
the printed last path segments. `access_path` is the printed path joined
to the printed `servers[0].url`. This is a different Fiskeridirektoratet
register from `--source fiskeridir` (Fartøyregisteret), `--source buyer`
(Kjøperregisteret), `--source nytek` (NYTEK), and `--source aqua`
(Akvakulturregister).

```bash
pda ingest --source research --db data/registry.sqlite --limit 10
pda search forskningsprosjekter --db data/registry.sqlite
pda fetch --dataset research:research-projects --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `name` when it is a non-empty string, otherwise
`projectNumber`. License is copied from the printed OpenAPI
`info.license.url` when present. Publisher stays null: the spec does not
print a publisher name.

Live ingest 2026-08-27: 1 printed collection GET path. Live search
`forskningsprosjekter` returns `research:research-projects`. Live fetch
GETs
`https://api.fiskeridir.no/aqua-research-project-api-public/api/v1/research-projects`
HTTP 200, 80 forskningsprosjekt-name rows. Sample printed values:
Klinisk utprøving av quorum sensing-antagonist på skinnhelse hos
atlantisk laks, Standardising manual louse counts (LusetellingSOP),
Seonguavhengig produksjon av regnbueørret, Nedsenket produksjon av
regnbueørret med luftlomme, Medisinfôr Skretting.
`pda methods` is not applicable: project names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/research_source_proof.json`.

## Fiskeridirektoratet Akvakultursøknader source

`pda ingest --source portal` is another replaceable adapter. It lists printed
collection GET paths on the official Akvakultursøknader OpenAPI
`https://api.fiskeridir.no/aqua-portal-api-public/v3/api-docs`,
capped at 10. Templated paths such as
`/api/v1/application/{applicationNo}` are skipped. Dataset ids are
the printed last path segments. `access_path` is the printed path joined
to the printed `servers[0].url`. This is a different Fiskeridirektoratet
register from `--source fiskeridir` (Fartøyregisteret), `--source buyer`
(Kjøperregisteret), `--source nytek` (NYTEK), `--source aqua`
(Akvakulturregister), and `--source research` (Akvakulturforskning).

```bash
pda ingest --source portal --db data/registry.sqlite --limit 10
pda search akvakultursøknader --db data/registry.sqlite
pda fetch --dataset portal:applications --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `title` when it is a non-empty string, otherwise
`applicationNo`. License is copied from the printed OpenAPI
`info.license.url` when present. Publisher stays null: the spec does not
print a publisher name.

Live ingest 2026-08-27: 1 printed collection GET path. Live search
`akvakultursøknader` returns `portal:applications`. Live fetch GETs
`https://api.fiskeridir.no/aqua-portal-api-public/api/v1/applications`
HTTP 200, 10 søknad-title rows. Sample printed values: HUNDBERGAN,
Segløygrunna, SØRVÆRET, VARHOLMEN, JAMNUNGEN.
`pda methods` is not applicable: application titles, not a numeric time
series (`no observations matched entity/measure; available=[]`).
Proof is `data/portal_source_proof.json`.

## Stavanger Opencom source

`pda ingest --source opencom` is another replaceable adapter. It lists printed
package names on the official Stavanger Opencom CKAN
`https://opencom.no/api/3/action/package_list`, capped at 10. Dataset ids
are those printed names. `access_path` is the catalog's own
`/api/3/action/package_show?id=` action joined to the list origin. This is
a different CKAN portal from `--source vegvesen` (Statens vegvesen
Dataportalen) and `--source trondheim` (Trondheim Åpne Data).

```bash
pda ingest --source opencom --db data/registry.sqlite --limit 10
pda search behovsprofil --db data/registry.sqlite
pda fetch --dataset opencom:04682-behovsprofil-grunnlagsdata --db data/registry.sqlite
```

`pda fetch` GETs the stored `package_show` URL. Observation values are
copied from printed resource `name` when present. Publisher is copied from
printed `organization.title` when present. License is copied from printed
`license_url` when it is an http(s) URI. The first printed packages store
`license_id` only, so license stays null. No license URI is invented.

Live ingest 2026-08-27: 10 printed package names (catalog prints 360,
cap 10). Live search `behovsprofil` returns
`opencom:04682-behovsprofil-grunnlagsdata`. Live fetch GETs
`https://opencom.no/api/3/action/package_show?id=04682-behovsprofil-grunnlagsdata`
HTTP 200, 9 resource-name rows. Sample printed values: 04682_2010.csv,
04682_2011.csv, 04682_2012.csv, 04682_2013.csv, 04682_2014.csv.
`pda methods` is not applicable: resource names, not a numeric time
series (`no observations matched entity/measure; available=[]`).
Proof is `data/opencom_source_proof.json`.

## Sokkeldirektoratet FactMaps DataService source

`pda ingest --source sodir` is another replaceable adapter. It lists printed
layer names on the official Sokkeldirektoratet FactMaps DataService
FeatureServer
`https://factmaps.sodir.no/api/rest/services/DataService/Data/FeatureServer?f=json`,
capped at 10. Dataset ids are the printed layer names. `access_path` is the
printed layer id joined to the FeatureServer origin with the same `f=json`
format the list API uses. This is not Stavanger Opencom (`--source opencom`,
now on main), not Vegvesen Dataportalen (`--source vegvesen`), and not
Kartverket kommuneinfo on Geonorge.

```bash
pda ingest --source sodir --db data/registry.sqlite --limit 10
pda search block --db data/registry.sqlite
pda fetch --dataset sodir:block --db data/registry.sqlite
```

`pda fetch` GETs the stored layer URL. Observation values are copied from
printed field `name` when it is a non-empty string, otherwise `alias`.
Publisher is copied from the printed FeatureServer `copyrightText`. License
stays null: the list document does not print a license URL.

Live ingest 2026-08-27: 10 printed layers (catalog prints 39, cap 10). Live
search `block` returns `sodir:block`. Live fetch GETs
`https://factmaps.sodir.no/api/rest/services/DataService/Data/FeatureServer/1001?f=json`
HTTP 200, 9 field-name rows. Sample printed values: OBJECTID, blcName,
blcNpdidBlock, blcArea, qadName.
`pda methods` is not applicable: field names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/sodir_source_proof.json`.

## Kartverket Kommuneinfo source

`pda ingest --source kommuneinfo` is another replaceable adapter. It lists printed
collection GET paths on the official Kartverket Kommuneinfo OpenAPI
`https://api.kartverket.no/kommuneinfo/v1/openapi.json`, capped at 10.
Dataset ids are the last printed path segment. `access_path` is the
printed path joined to the spec's own `servers[0].url`. This is not
Geonorge Kartkatalog (`--source geonorge`), not Kartverket Stedsnavn
(`--source stedsnavn`), and not Sokkeldirektoratet FactMaps
(`--source sodir`).

```bash
pda ingest --source kommuneinfo --db data/registry.sqlite --limit 10
pda search fylker --db data/registry.sqlite
pda fetch --dataset kommuneinfo:fylker --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed `fylkesnavn` when present. License and publisher
stay null: the OpenAPI document prints neither a license URL nor a
publisher. No license URI is invented.

Live ingest 2026-08-27: 6 printed untemplated GET paths (catalog prints
6, cap 10). Live search `fylker` returns `kommuneinfo:fylker`. Live
fetch GETs `https://api.kartverket.no/kommuneinfo/v1/fylker` HTTP 200,
15 county-name rows. Sample printed values: Troms, Finnmark, Buskerud,
Agder, Rogaland. `pda methods` is not applicable: county names, not a
numeric time series (`no observations matched entity/measure; available=[]`).
Proof is `data/kommuneinfo_source_proof.json`.

## Artsdatabanken Natur i Norge source

`pda ingest --source nin` is another replaceable adapter. It lists printed
collection GET paths on the official Artsdatabanken NiN Kode API OpenAPI
`https://nin-kode-api.artsdatabanken.no/swagger/v3.0/swagger.json`,
capped at 10. Dataset ids are the printed paths. `access_path` is the
printed path joined to the OpenAPI origin. Templated `{kortkode}` paths
are skipped. This is not Kartverket Kommuneinfo (`--source kommuneinfo`,
now on main), not Sokkeldirektoratet FactMaps (`--source sodir`), and not
Stavanger Opencom (`--source opencom`).

```bash
pda ingest --source nin --db data/registry.sqlite --limit 10
pda search allekoder --db data/registry.sqlite
pda fetch --dataset nin:v3.0/typer/allekoder --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed type `navn` when it is a non-empty string. Publisher and
license stay null: the OpenAPI document does not print those fields.

Live ingest 2026-08-27: 6 printed collection GET paths (catalog prints 16
GET paths, 6 untemplated, cap 10). Live search `allekoder` returns
`nin:v3.0/typer/allekoder`. Live fetch GETs
`https://nin-kode-api.artsdatabanken.no/v3.0/typer/allekoder`
HTTP 200, 10 type-name rows. Sample printed values: Bremassiv, Elveløp,
Landformer i fast fjell og løsmasser, Innsjøbasseng, Torvmarksmassiv.
`pda methods` is not applicable: type names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nin_source_proof.json`.

## Norges geologiske undersøkelse OGC API Features source

`pda ingest --source ngu` is another replaceable adapter. It lists printed
dataset ids on the official Norges geologiske undersøkelse OGC API Features
catalog `https://geo.ngu.no/api/features`, capped at 10. Dataset ids are the
printed `apis[].id` values. `access_path` is the printed `landingPageUri`.
This is not Havforskningsinstituttet OGC Features (`--source hi`), not
Geonorge Kartkatalog (`--source geonorge`), not Kartverket Kommuneinfo
(`--source kommuneinfo`, now on main), and not Artsdatabanken NiN
(`--source nin`, now on main). Root `/collections` stays unused: that
path 404s. The catalog's own `apis` array is the printed list.

```bash
pda ingest --source ngu --db data/registry.sqlite --limit 10
pda search ankringsforhold --db data/registry.sqlite
pda fetch --dataset ngu:ankringsforhold --db data/registry.sqlite
```

`pda fetch` GETs the stored landing-page URL. Observation values are copied
from printed link `title` when it is a non-empty string, otherwise `rel`,
otherwise `href`. License and publisher stay null: the catalog prints
neither a license URL nor a structured publisher.

Live ingest 2026-08-27: 10 printed datasets (catalog prints 28, cap 10). Live
search `ankringsforhold` returns `ngu:ankringsforhold`. Live fetch GETs
`https://geo.ngu.no/api/features/ankringsforhold` HTTP 200, 15 link-title
rows. Sample printed values: This document as HTML, OGC API conformance
classes implemented by this server, Access the data (ankringOmr,
Dataavgrensning, GeolAvgrLinje).
`pda methods` is not applicable: link titles, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/ngu_source_proof.json`.

## Kartverket Høydedata source

`pda ingest --source hoydedata` is another replaceable adapter. It lists printed
collection GET paths on the official Kartverket Høydedata OpenAPI
`https://ws.geonorge.no/hoydedata/v1/openapi.json`, capped at 10.
Dataset ids are the last printed path segment. `access_path` is the
printed path joined to the spec's own relative `servers[0].url`
`/hoydedata/v1` on the OpenAPI origin. Templated `{datakilde}` paths
are skipped. This is not Geonorge Kartkatalog (`--source geonorge`),
not Kartverket Stedsnavn (`--source stedsnavn`), not Kartverket
Kommuneinfo (`--source kommuneinfo`), not Artsdatabanken NiN
(`--source nin`), and not NGU OGC Features (`--source ngu`, now on
main).

```bash
pda ingest --source hoydedata --db data/registry.sqlite --limit 10
pda search datakilder --db data/registry.sqlite
pda fetch --dataset hoydedata:datakilder --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed `datakilde` when it is a non-empty string.
License and publisher stay null: the OpenAPI document prints neither
a license URL nor a publisher. No license URI is invented.

Live ingest 2026-08-27: 3 printed untemplated GET paths (catalog prints
5 GET paths, 3 untemplated, cap 10). Live search `datakilder` returns
`hoydedata:datakilder`. Live fetch GETs
`https://ws.geonorge.no/hoydedata/v1/datakilder` HTTP 200, 5 source-name
rows. Sample printed values: dtm1, dom1, dybdekurver, hoydekurver,
innsjohoyde. `pda methods` is not applicable: source names, not a
numeric time series (`no observations matched entity/measure; available=[]`).
Proof is `data/hoydedata_source_proof.json`.

## Meteorologisk institutt Nowcast source

`pda ingest --source nowcast` is another replaceable adapter. It lists printed
collection GET paths on the official MET Nowcast swagger
`https://api.met.no/weatherapi/nowcast/2.0/swagger`, capped at 10.
Templated `{format}` paths are skipped. Dataset ids are the last printed
path segment. `access_path` is the swagger origin + printed `basePath` +
path. License is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Kartverket Høydedata
(`--source hoydedata`, now on main), and not NGU OGC Features
(`--source ngu`). `/classic` and `/complete` stay unused for fetch in
this slice: those printed paths require `lat` and `lon`.

```bash
pda ingest --source nowcast --db data/registry.sqlite --limit 10
pda search FeatureCollection --db data/registry.sqlite
pda fetch --dataset nowcast:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name`. License is the printed swagger
CC BY 4.0 URL. Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 8 printed untemplated GET paths (catalog prints
11 paths, 3 templated, cap 10). Live search `FeatureCollection` returns
`nowcast:locations`. Live fetch GETs
`https://api.met.no/weatherapi/nowcast/2.0/locations` HTTP 200, 1
location-name row. Sample printed value: MEPS area. `pda methods` is not
applicable: a feature name, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nowcast_source_proof.json`.

## Riksantikvaren MABYGIS source

`pda ingest --source riksantikvaren` is another replaceable adapter. It lists printed
layer names on the official Riksantikvaren MABYGIS FeatureServer
`https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_rest_ro/FeatureServer?f=json`,
capped at 10. Dataset ids are the printed layer names. `access_path` is the
printed layer id joined to the FeatureServer origin with the same `f=json`
format the list API uses. This is not MET Nowcast (`--source nowcast`, now
on main), not Kartverket Høydedata (`--source hoydedata`), and not
Sokkeldirektoratet FactMaps (`--source sodir`).

```bash
pda ingest --source riksantikvaren --db data/registry.sqlite --limit 10
pda search Borhull --db data/registry.sqlite
pda fetch --dataset riksantikvaren:Borhull --db data/registry.sqlite
```

`pda fetch` GETs the stored layer URL. Observation values are copied from
printed field `name` when it is a non-empty string, otherwise `alias`.
License and publisher stay null: the list document prints an empty
`copyrightText` and no license URL. No license URI is invented.

Live ingest 2026-08-27: 10 printed layers (catalog prints 29, cap 10). Live
search `Borhull` returns `riksantikvaren:Borhull`. Live fetch GETs
`https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_rest_ro/FeatureServer/0?f=json`
HTTP 200, 25 field-name rows. Sample printed values: X_UTM33, Y_UTM33, Z,
TOP_BOR_MOH, BORE_DIAM.
`pda methods` is not applicable: field names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/riksantikvaren_source_proof.json`.

## Meteorologisk institutt Airqualityforecast source

`pda ingest --source airquality` is another replaceable adapter. It lists printed
collection GET paths on the official MET Airqualityforecast swagger
`https://api.met.no/weatherapi/airqualityforecast/0.1/swagger`, capped at 10.
Templated `{format}` paths and the root `/` path (no printed last segment)
are skipped. Dataset ids are the last printed path segment. `access_path` is
the swagger origin + printed `basePath` + path. License is the printed swagger
CC BY 4.0 URL. Publisher stays null. This is not Metalerts (`--source met`),
not Nowcast (`--source nowcast`), and not Riksantikvaren MABYGIS
(`--source riksantikvaren`, now on main). `/met` stays unused for fetch in this
slice: that printed path requires `station`.

```bash
pda ingest --source airquality --db data/registry.sqlite --limit 10
pda search stations --db data/registry.sqlite
pda fetch --dataset airquality:stations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed station `name`. License is the printed swagger CC BY 4.0 URL.
Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 10 printed untemplated GET paths (catalog prints
11 paths, 1 root path with no last segment, cap 10). Live search
`stations` returns `airquality:stations`. Live fetch GETs
`https://api.met.no/weatherapi/airqualityforecast/0.1/stations` HTTP 200,
82 station-name rows. Sample printed values: Alnabru, Alvim,
Backeparken. `pda methods` is not applicable: station names, not a
numeric time series (`no observations matched entity/measure; available=[]`).
Proof is `data/airquality_source_proof.json`.

## Meteorologisk institutt Tidalwater source

`pda ingest --source tidalwater` is another replaceable adapter. It lists printed
collection GET paths on the official MET Tidalwater swagger
`https://api.met.no/weatherapi/tidalwater/1.1/swagger`, capped at 10.
Templated `{format}` paths and the root `/` path are skipped. Dataset ids
are the last printed path segment. `access_path` is the swagger origin +
printed `basePath` + path. License is the printed swagger CC BY 4.0 URL.
Publisher stays null. This is not Metalerts (`--source met`), not Nowcast
(`--source nowcast`), not Riksantikvaren MABYGIS
(`--source riksantikvaren`), and not MET Airqualityforecast
(`--source airquality`, now on main). `/available` stays unused for fetch
in this slice: that printed path returns XML.

```bash
pda ingest --source tidalwater --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset tidalwater:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name`. License is the printed swagger
CC BY 4.0 URL. Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 6 printed untemplated GET paths with a last-segment
id (catalog prints 8 paths, 1 templated, 1 root). Live search `locations`
returns `tidalwater:locations`. Live fetch GETs
`https://api.met.no/weatherapi/tidalwater/1.1/locations` HTTP 200, 31
location-name rows. Sample printed values: Andenes, Bergen, Oscarsborg.
`pda methods` is not applicable: location names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/tidalwater_source_proof.json`.

## Meteorologisk institutt Oceanforecast source

`pda ingest --source oceanforecast` is another replaceable adapter. It lists printed
collection GET paths on the official MET Oceanforecast swagger
`https://api.met.no/weatherapi/oceanforecast/2.0/swagger`, capped at 10.
Templated `{format}` paths are skipped. Dataset ids are the last printed path
segment. `access_path` is the swagger origin + printed `basePath` + path.
License is the printed swagger CC BY 4.0 URL. Publisher stays null. This is not
Metalerts (`--source met`), not Nowcast (`--source nowcast`), not
Airqualityforecast (`--source airquality`, now on main), not Tidalwater
(`--source tidalwater`, now on main after PR 101), and not Riksantikvaren
MABYGIS (`--source riksantikvaren`). `/complete` and `/mox` stay unused for
fetch in this slice: those printed paths require `lat` and `lon`.

```bash
pda ingest --source oceanforecast --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset oceanforecast:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed feature `name`. License is the printed swagger CC BY 4.0 URL.
Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 7 printed untemplated GET paths (catalog prints
11 paths, 4 templated `{format}` paths skipped, cap 10). Live search
`locations` returns `oceanforecast:locations`. Live fetch GETs
`https://api.met.no/weatherapi/oceanforecast/2.0/locations` HTTP 200, 1
feature-name row. Sample printed value: Oceanforecast area.
`pda methods` is not applicable: feature name, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/oceanforecast_source_proof.json`.

## Meteorologisk institutt Sunrise source

`pda ingest --source sunrise` is another replaceable adapter. It lists printed
collection GET paths on the official MET Sunrise swagger
`https://api.met.no/weatherapi/sunrise/3.0/swagger`, capped at 10.
Templated `{format}` paths and the root `/` path are skipped. Dataset ids
are the last printed path segment. `access_path` is the swagger origin +
printed `basePath` + path. License is the printed swagger CC BY 4.0 URL.
Publisher stays null. This is not Metalerts (`--source met`), not Nowcast
(`--source nowcast`), not MET Airqualityforecast (`--source airquality`),
not MET Tidalwater (`--source tidalwater`, now on main), and not MET
Oceanforecast (`--source oceanforecast`, now on main after PR 102).
`/sun` and `/moon` stay unused for fetch in this slice: those printed
paths require `lat` and `lon`.

```bash
pda ingest --source sunrise --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset sunrise:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name`. License is the printed swagger
CC BY 4.0 URL. Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 6 printed untemplated GET paths (catalog prints
6 paths, cap 10). Live search `locations` returns `sunrise:locations`.
Live fetch GETs `https://api.met.no/weatherapi/sunrise/3.0/locations`
HTTP 200, 1 location-name row. Sample printed value: Whole Earth
Catalogue. `pda methods` is not applicable: one GeoJSON feature name,
not a numeric time series (`no observations matched entity/measure;
available=[]`). Proof is `data/sunrise_source_proof.json`.

## Meteorologisk institutt Radar source

`pda ingest --source radar` is another replaceable adapter. It lists printed
collection GET paths on the official MET Radar swagger
`https://api.met.no/weatherapi/radar/2.0/swagger`, capped at 10.
Templated `{format}` paths are skipped. GET paths that print a required
query parameter (`area`, `type`) stay unused: those are image products,
not a collection list. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path.
License is the printed swagger CC BY 4.0 URL. Publisher stays null. This is not
Metalerts (`--source met`), not Nowcast (`--source nowcast`), not
Airqualityforecast (`--source airquality`), not Tidalwater
(`--source tidalwater`), not Oceanforecast (`--source oceanforecast`),
and not MET Sunrise (`--source sunrise`, now on main after PR 103).
`/available` stays unused for fetch in this slice: that printed path
returns XML.

```bash
pda ingest --source radar --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset radar:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed feature `name`. License is the printed swagger CC BY 4.0 URL.
Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 8 printed untemplated collection GET paths
(catalog prints 71 paths; templated `{format}` paths and image-product
paths with required `area`/`type` skipped, cap 10). Live search
`locations` returns `radar:locations`. Live fetch GETs
`https://api.met.no/weatherapi/radar/2.0/locations` HTTP 200, 15
feature-name rows. Sample printed value: Central Norway.
`pda methods` is not applicable: feature names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/radar_source_proof.json`.

## Meteorologisk institutt Spotwind source

`pda ingest --source spotwind` is another replaceable adapter. It lists printed
collection GET paths on the official MET Spotwind swagger
`https://api.met.no/weatherapi/spotwind/1.1/swagger`, capped at 10.
Templated `{format}` paths and the root `/` path are skipped. Dataset ids
are the last printed path segment. `access_path` is the swagger origin +
printed `basePath` + path. License is the printed swagger CC BY 4.0 URL.
Publisher stays null. This is not Metalerts (`--source met`), not Nowcast
(`--source nowcast`), not MET Airqualityforecast (`--source airquality`),
not MET Tidalwater (`--source tidalwater`), not MET Oceanforecast
(`--source oceanforecast`), not MET Sunrise (`--source sunrise`), and not
MET Radar (`--source radar`, now on main after PR 104).

```bash
pda ingest --source spotwind --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset spotwind:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name`. License is the printed swagger
CC BY 4.0 URL. Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 4 printed untemplated GET paths (catalog prints
4 paths with a last-segment id, cap 10). Live search `locations` returns
`spotwind:locations`. Live fetch GETs
`https://api.met.no/weatherapi/spotwind/1.1/locations` HTTP 200, 15
location-name rows. Sample printed values: DKE, DKW, FE. `pda methods`
is not applicable: GeoJSON feature names, not a numeric time series
(`no observations matched entity/measure; available=[]`). Proof is
`data/spotwind_source_proof.json`.

## Meteorologisk institutt Textforecast source

`pda ingest --source textforecast` is another replaceable adapter. It lists
printed collection GET paths on the official MET Textforecast swagger
`https://api.met.no/weatherapi/textforecast/3.0/swagger`, capped at 10.
Templated `{format}` paths are skipped. GET paths that print a required
query parameter (`forecast`) stay unused: the root `/` path is a filter
search, not a collection list. Dataset ids are the last printed path
segment. `access_path` is the swagger origin + printed `basePath` + path.
License is the printed swagger CC BY 4.0 URL. Publisher stays null. This is
not Metalerts (`--source met`), not Nowcast (`--source nowcast`), not
Airqualityforecast (`--source airquality`), not Tidalwater
(`--source tidalwater`), not Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not Radar (`--source radar`), and
not MET Spotwind (`--source spotwind`, now on main after PR 105).
`/available` stays unused for fetch in this slice: that printed path
returns XML.

```bash
pda ingest --source textforecast --db data/registry.sqlite --limit 10
pda search landoverview --db data/registry.sqlite
pda fetch --dataset textforecast:landoverview --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed feature `area`. License is the printed swagger CC BY 4.0 URL.
Publisher stays null: the spec does not print a publisher.

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
| 7 | First data connector. Observation rows from one public API |
| 8 | Two independent data sources. SSB Klass plus Oslo PxWeb |
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
