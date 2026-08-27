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
