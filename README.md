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

Live ingest 2026-08-27: 10 printed untemplated collection GET paths
(catalog prints 21 paths; templated `{format}` paths and the root `/`
path with required `forecast` skipped, cap 10). Live search
`landoverview` returns `textforecast:landoverview`. Live fetch GETs
`https://api.met.no/weatherapi/textforecast/3.0/landoverview` HTTP 200,
35 feature-area rows. Sample printed value: Østlandet.
`pda methods` is not applicable: area names and forecast text, not a
numeric time series (`no observations matched entity/measure;
available=[]`). Proof is `data/textforecast_source_proof.json`.

## Meteorologisk institutt Icemap source

`pda ingest --source icemap` is another replaceable adapter. It lists printed
collection GET paths on the official MET Icemap swagger
`https://api.met.no/weatherapi/icemap/1.0/swagger`, capped at 10.
Templated `{format}` paths are skipped. GET paths that print a required
query parameter (`area`) stay unused: those are image products, not a
collection list. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path.
License is the printed swagger CC BY 4.0 URL. Publisher stays null. This is
not Metalerts (`--source met`), not Nowcast (`--source nowcast`), not
Airqualityforecast (`--source airquality`), not Tidalwater
(`--source tidalwater`), not Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not Textforecast
(`--source textforecast`, now on main after PR 106), and not Lane B
NCAgalewarnings (`--source ncagalewarnings`, open PR 107).
`/available` stays unused for fetch in this slice: that printed path
returns XML.

```bash
pda ingest --source icemap --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset icemap:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed feature `name`. License is the printed swagger CC BY 4.0 URL.
Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 6 printed untemplated collection GET paths
(catalog prints 10 paths; templated `{format}` paths and image-product
paths with required `area` skipped). Live search `locations` returns
`icemap:locations`. Live fetch GETs
`https://api.met.no/weatherapi/icemap/1.0/locations` HTTP 200, 6
location-name rows. Sample printed values: Nord-Norge, Nord-Europa,
Nord-Skandinavia. `pda methods` is not applicable: GeoJSON feature
names, not a numeric time series (`no observations matched
entity/measure; available=[]`). Proof is `data/icemap_source_proof.json`.

## Meteorologisk institutt NCAgalewarnings source

`pda ingest --source ncagalewarnings` is another replaceable adapter. It lists printed
collection GET paths on the official MET NCAgalewarnings swagger
`https://api.met.no/weatherapi/ncagalewarnings/1.0/swagger`, capped at 10.
Templated `{format}` paths are skipped. Dataset ids are the last printed
path segment. `access_path` is the swagger origin + printed `basePath` +
path. License is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`, now on main after PR 105), not
MET Textforecast (`--source textforecast`, now on main after PR 106), and
not MET Icemap (`--source icemap`, now on main after PR 108).

```bash
pda ingest --source ncagalewarnings --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset ncagalewarnings:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name`. License is the printed swagger
CC BY 4.0 URL. Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 8 printed untemplated GET paths (catalog prints
8 paths with a last-segment id, cap 10). Live search `locations` returns
`ncagalewarnings:locations`. Live fetch GETs
`https://api.met.no/weatherapi/ncagalewarnings/1.0/locations` HTTP 200, 8
location-name rows. Sample printed values: Stad, Hustadvika, Folda 1.
`pda methods` is not applicable: GeoJSON feature names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/ncagalewarnings_source_proof.json`.

## Meteorologisk institutt Tafmetar source

`pda ingest --source tafmetar` is another replaceable adapter. It lists printed
collection GET paths on the official MET Tafmetar swagger
`https://api.met.no/weatherapi/tafmetar/1.0/swagger`, capped at 10.
Templated `{format}` paths are skipped. GET paths that print a required
query parameter (`icao`, `content`, `content_type`) stay unused: those
are TAF/METAR products, not a collection list. Dataset ids are the last
printed path segment. `access_path` is the swagger origin + printed
`basePath` + path. License is the printed swagger CC BY 4.0 URL.
Publisher stays null. This is not Metalerts (`--source met`), not Nowcast
(`--source nowcast`), not Airqualityforecast (`--source airquality`),
not Tidalwater (`--source tidalwater`), not Oceanforecast
(`--source oceanforecast`), not MET Sunrise (`--source sunrise`), not
Radar (`--source radar`), not MET Spotwind (`--source spotwind`), not
Textforecast (`--source textforecast`), not Icemap (`--source icemap`,
now on main after PR 108), and not NCAgalewarnings
(`--source ncagalewarnings`, now on main after PR 107). `/changelog`
and `/schema` stay unused for fetch in this slice: those printed paths
return RSS/XML.

```bash
pda ingest --source tafmetar --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset tafmetar:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed feature `name`. License is the printed swagger CC BY 4.0 URL.
Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 5 printed untemplated collection GET paths
(catalog prints 14 paths; templated `{format}` paths and TAF/METAR
product paths with required `icao` skipped). Live search `locations`
returns `tafmetar:locations`. Live fetch GETs
`https://api.met.no/weatherapi/tafmetar/1.0/locations` HTTP 200, 52
airport-name rows. Sample printed values: KRISTIANSUND/ KVERNBERGET,
NOTODDEN, SANDANE/ANDA. `pda methods` is not applicable: GeoJSON
feature names, not a numeric time series (`no observations matched
entity/measure; available=[]`). Proof is `data/tafmetar_source_proof.json`.

## Meteorologisk institutt Subseasonal source

`pda ingest --source subseasonal` is another replaceable adapter. It lists printed
collection GET paths on the official MET Subseasonal swagger
`https://api.met.no/weatherapi/subseasonal/1.0/swagger`, capped at 10.
Templated `{format}` paths are skipped. Dataset ids are the last printed
path segment. `access_path` is the swagger origin + printed `basePath` +
path. License is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET NCAgalewarnings
(`--source ncagalewarnings`, now on main after PR 107), and not MET
Tafmetar (`--source tafmetar`, now on main after PR 109). `/complete`
prints required `lat`/`lon` so it stays unused for fetch.

```bash
pda ingest --source subseasonal --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset subseasonal:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name`. License is the printed swagger
CC BY 4.0 URL. Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 6 printed untemplated GET paths (catalog prints
6 paths with a last-segment id, cap 10). Live search `locations` returns
`subseasonal:locations`. Live fetch GETs
`https://api.met.no/weatherapi/subseasonal/1.0/locations` HTTP 200, 1
location-name row. Sample printed value: MEPS area.
`pda methods` is not applicable: GeoJSON feature names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/subseasonal_source_proof.json`.

## Meteorologisk institutt Geosatellite source

`pda ingest --source geosatellite` is another replaceable adapter. It lists printed
collection GET paths on the official MET Geosatellite swagger
`https://api.met.no/weatherapi/geosatellite/1.4/swagger`, capped at 10.
Templated `{format}` paths and the root `/` image product (no last path
segment) are skipped. Optional `area` / `size` / `type` / `time` query
filters are not invented. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null. This is not
Metalerts (`--source met`), not Nowcast (`--source nowcast`), not
Airqualityforecast (`--source airquality`), not Tidalwater
(`--source tidalwater`), not Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not Radar (`--source radar`), not
MET Spotwind (`--source spotwind`), not Textforecast
(`--source textforecast`), not Icemap (`--source icemap`), not
NCAgalewarnings (`--source ncagalewarnings`), not Tafmetar
(`--source tafmetar`, now on main after PR 109), and not Subseasonal
(`--source subseasonal`, now on main after PR 110). `/available` stays unused for fetch in this slice:
that printed path returns XML.

```bash
pda ingest --source geosatellite --db data/registry.sqlite --limit 10
pda search featurecollection --db data/registry.sqlite
pda fetch --dataset geosatellite:features --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from the printed GeoJSON feature `datetime`; the printed feature `id`
stays a dimension. License is the printed swagger CC BY 4.0 URL.
Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 5 printed untemplated collection GET paths
(catalog prints 8 paths; templated `{format}` paths and root `/` skipped).
Live search `featurecollection` returns `geosatellite:features`. Live
fetch GETs `https://api.met.no/weatherapi/geosatellite/1.4/features`
HTTP 200, 2710 printed feature rows (2708 inserted; 2 duplicate
feature ids stayed unchanged). Sample printed values: datetime
2026-08-25T22:00:00Z with ids Mediterranean-Sea-IR-20260825220000,
Europe-IR-20260825220000, Africa-IR-20260825220000. `pda methods` is
not applicable: GeoJSON feature timestamps, not a numeric time series
(`no observations matched entity/measure; available=[]`). Proof is
`data/geosatellite_source_proof.json`.

## Meteorologisk institutt Metgm source

`pda ingest --source metgm` is another replaceable adapter. It lists printed
collection GET paths on the official MET Metgm swagger
`https://api.met.no/weatherapi/metgm/1.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
and not MET Geosatellite (`--source geosatellite`, now on main after
PR 111). The root product path prints required `area`/`time` so it
stays unused for fetch. `/available` prints XML so it stays unused
for fetch.

```bash
pda ingest --source metgm --db data/registry.sqlite --limit 10
pda search featurecollection --db data/registry.sqlite
pda fetch --dataset metgm:features --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 5 printed untemplated GET paths (catalog prints
5 paths with a last-segment id and no required query parameter, cap 10).
Live search `featurecollection` returns `metgm:features`. Live fetch GETs
`https://api.met.no/weatherapi/metgm/1.0/features` HTTP 200, 112
feature-id cells (16 inserted / 96 updated on shared datetime
dimensions). Sample printed value:
`ostland2_F_20260823_2100Z_0_NOR0_1150E_6150N`.
`pda methods` is not applicable: GeoJSON feature ids, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/metgm_source_proof.json`.

## Meteorologisk institutt Subjectiveforecast source

`pda ingest --source subjectiveforecast` is another replaceable adapter. It lists printed
collection GET paths on the official MET Subjectiveforecast swagger
`https://api.met.no/weatherapi/subjectiveforecast/1.0/swagger`, capped at 10.
Templated `{format}` paths and the root `/` image product (no last path
segment; required `product` query) are skipped. Optional `content_type` /
`product` / `param` query filters are not invented. Dataset ids are the last
printed path segment. `access_path` is the swagger origin + printed `basePath`
+ path. License is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`), not
Airqualityforecast (`--source airquality`), not Tidalwater
(`--source tidalwater`), not Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not Radar (`--source radar`), not
MET Spotwind (`--source spotwind`), not Textforecast
(`--source textforecast`), not Icemap (`--source icemap`), not
NCAgalewarnings (`--source ncagalewarnings`), not Tafmetar
(`--source tafmetar`), not Subseasonal (`--source subseasonal`), not
Geosatellite (`--source geosatellite`, now on main after PR 111), and not
Metgm (`--source metgm`, now on main after PR 112). `/available` stays unused for fetch
in this slice: that printed path returns XML.

```bash
pda ingest --source subjectiveforecast --db data/registry.sqlite --limit 10
pda search featurecollection --db data/registry.sqlite
pda fetch --dataset subjectiveforecast:features --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from the printed GeoJSON feature `datetime`; the printed feature `id`
stays a dimension. License is the printed swagger CC BY 4.0 URL.
Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 5 printed untemplated collection GET paths
(catalog prints 7 paths; templated `{format}` paths and root `/` skipped).
Live search `featurecollection` returns `subjectiveforecast:features`. Live
fetch GETs `https://api.met.no/weatherapi/subjectiveforecast/1.0/features`
HTTP 200, 12 printed feature rows. Sample printed values: datetime
2026-08-25T18:00:00Z with id analyse_20260825T18,
2026-08-26T00:00:00Z with id analyse_20260826T00. `pda methods` is
not applicable: GeoJSON feature timestamps, not a numeric time series
(`no observations matched entity/measure; available=[]`). Proof is
`data/subjectiveforecast_source_proof.json`.

`pda ingest --source polarsatellite` is another replaceable adapter. It lists printed
collection GET paths on the official MET Polarsatellite swagger
`https://api.met.no/weatherapi/polarsatellite/1.1/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`, now on main after PR 112), and not MET
Subjectiveforecast (`--source subjectiveforecast`, now on main after
PR 113). The root product path prints required `satellite` so it stays
unused for fetch. `/available` prints XML so it stays unused for fetch.

```bash
pda ingest --source polarsatellite --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset polarsatellite:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 8 printed untemplated GET paths (catalog prints
8 paths with a last-segment id and no required query parameter, cap 10).
Live search `locations` returns `polarsatellite:locations`. Live fetch GETs
`https://api.met.no/weatherapi/polarsatellite/1.1/locations` HTTP 200, 8
location-name cells. Sample printed value: `IS`.
`pda methods` is not applicable: GeoJSON location names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/polarsatellite_source_proof.json`.

## Kartverket Transformering source

`pda ingest --source transformering` is another replaceable adapter. It lists printed
collection GET paths on the official Kartverket Transformering OpenAPI
`https://ws.geonorge.no/transformering/v1/openapi.json`, capped at 10.
Templated paths and GET operations that print required query parameters
(`/transformer` requires `x`/`y`/`fra`/`til`) are skipped. Optional
`kategori` / `system` query filters are not invented. Dataset ids are the
last printed path segment. `access_path` is the printed path joined to the
spec's own relative `servers[0].url` `/transformering/v1` on the OpenAPI
origin. License and publisher stay null: the spec does not print a license
URL or publisher name. This is not Kartverket Høydedata (`--source hoydedata`),
not Kartverket Kommuneinfo (`--source kommuneinfo`), not Kartverket
Stedsnavn (`--source stedsnavn`), not Geonorge Kartkatalog
(`--source geonorge`), and not MET Polarsatellite
(`--source polarsatellite`, now on main after PR 114).

```bash
pda ingest --source transformering --db data/registry.sqlite --limit 10
pda search koordinatsystemer --db data/registry.sqlite
pda fetch --dataset transformering:projeksjoner --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `name`. License and publisher stay null.

This source is Kartverket Transformering (`ws.geonorge.no/transformering`),
not Høydedata, Kommuneinfo, Stedsnavn, Geonorge Kartkatalog, or
Polarsatellite.

Live ingest 2026-08-27: 1 printed untemplated collection GET path
(catalog prints 2 paths; `/transformer` required-parameter GET skipped).
Live search `koordinatsystemer` returns `transformering:projeksjoner`.
Live fetch GETs `https://ws.geonorge.no/transformering/v1/projeksjoner`
HTTP 200, 130 printed projection-name rows. Sample printed values:
ETRS89 Geografisk 2D (EPSG 4258), ETRS89 Geografisk 3D (EPSG 4937),
ETRS89 Geografisk NN2000 (EPSG 5942). `pda methods` is not applicable:
projection names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/transformering_source_proof.json`.

`pda ingest --source soundprofile` is another replaceable adapter. It lists printed
collection GET paths on the official MET Soundprofile swagger
`https://api.met.no/weatherapi/soundprofile/1.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`, now on main after PR 114), and not Kartverket
Transformering (`--source transformering`, now on main after PR 115). The
root product path prints required `location` so it stays unused for fetch.
`/available` prints XML so it stays unused for fetch.

```bash
pda ingest --source soundprofile --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset soundprofile:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 8 printed untemplated GET paths (catalog prints
8 paths with a last-segment id and no required query parameter, cap 10).
Live search `locations` returns `soundprofile:locations`. Live fetch GETs
`https://api.met.no/weatherapi/soundprofile/1.0/locations` HTTP 200, 48
location-name cells. Sample printed value: `N5627_E00627`.
`pda methods` is not applicable: GeoJSON location names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/soundprofile_source_proof.json`.

`pda ingest --source gribfiles` is another replaceable adapter. It lists printed
collection GET paths on the official MET Gribfiles swagger
`https://api.met.no/weatherapi/gribfiles/1.1/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`), not Kartverket Transformering
(`--source transformering`), and not MET Soundprofile
(`--source soundprofile`, now on main after PR 116). The root product
path prints required `area` and `content` so it stays unused for fetch.
`/current`, `/waves`, and `/weather` print required `area` so they stay
unused for fetch. `/available` prints XML so it stays unused for fetch.

```bash
pda ingest --source gribfiles --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset gribfiles:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 5 printed untemplated GET paths (catalog prints
5 paths with a last-segment id and no required query parameter, cap 10).
Live search `locations` returns `gribfiles:locations`. Live fetch GETs
`https://api.met.no/weatherapi/gribfiles/1.1/locations` HTTP 200, 9
location-name cells. Sample printed value: `N-NORTHSEA`.
`pda methods` is not applicable: GeoJSON location names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/gribfiles_source_proof.json`.

## MET Metgc source

`pda ingest --source metgc` is another replaceable adapter. It lists printed
collection GET paths on the official MET Metgc swagger
`https://api.met.no/weatherapi/metgc/1.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`), not Kartverket Transformering
(`--source transformering`), not MET Soundprofile
(`--source soundprofile`, now on main after PR 116), and not MET
Gribfiles (`--source gribfiles`, now on main after PR 117). The root
product path prints required `area`/`time` so it stays unused for fetch.
`/available` prints XML so it stays unused for fetch.

```bash
pda ingest --source metgc --db data/registry.sqlite --limit 10
pda search featurecollection --db data/registry.sqlite
pda fetch --dataset metgc:features --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 5 printed untemplated GET paths (catalog prints
5 paths with a last-segment id and no required query parameter, cap 10).
Live search `featurecollection` returns `metgc:features`. Live fetch GETs
`https://api.met.no/weatherapi/metgc/1.0/features` HTTP 200, 112
feature-id cells. Sample printed value:
`ostland_F_20260823_2100Z_0_NOR0_1150E_6150N`.
`pda methods` is not applicable: GeoJSON feature ids with datetime
properties, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/metgc_source_proof.json`.

`pda ingest --source oslofjord` is another replaceable adapter. It lists printed
collection GET paths on the official MET Oslofjord swagger
`https://api.met.no/weatherapi/oslofjord/0.1/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`), not Kartverket Transformering
(`--source transformering`), not MET Soundprofile
(`--source soundprofile`), not MET Gribfiles (`--source gribfiles`, now
on main after PR 117), and not MET Metgc (`--source metgc`, now on main
after PR 118). The root product path prints required `area` so it stays
unused for fetch. `/available` prints XML so it stays unused for fetch.

```bash
pda ingest --source oslofjord --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset oslofjord:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 6 printed untemplated GET paths (catalog prints
6 paths with a last-segment id and no required query parameter, cap 10).
Live search `locations` returns `oslofjord:locations`. Live fetch GETs
`https://api.met.no/weatherapi/oslofjord/0.1/locations` HTTP 200, 5
location-name cells. Sample printed value: `Drammensfjorden`.
`pda methods` is not applicable: GeoJSON location names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/oslofjord_source_proof.json`.

## MET Isobaricgrib source

`pda ingest --source isobaricgrib` is another replaceable adapter. It lists printed
collection GET paths on the official MET Isobaricgrib swagger
`https://api.met.no/weatherapi/isobaricgrib/1.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`), not Kartverket Transformering
(`--source transformering`), not MET Soundprofile
(`--source soundprofile`), not MET Gribfiles (`--source gribfiles`),
not MET Metgc (`--source metgc`), and not MET Oslofjord
(`--source oslofjord`, now on main after PR 119). `/grib1` and `/grib2`
print required `area` so they stay unused for fetch. `/available`
prints XML so it stays unused for fetch.

```bash
pda ingest --source isobaricgrib --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset isobaricgrib:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 7 printed untemplated GET paths (catalog prints
7 paths with a last-segment id and no required query parameter, cap 10).
Live search `locations` returns `isobaricgrib:locations`. Live fetch GETs
`https://api.met.no/weatherapi/isobaricgrib/1.0/locations` HTTP 200, 2
location-name cells. Sample printed value: `EUROPE`.
`pda methods` is not applicable: GeoJSON location names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/isobaricgrib_source_proof.json`.

## MET Offshoremaps source

`pda ingest --source offshoremaps` is another replaceable adapter. It lists printed
collection GET paths on the official MET Offshoremaps swagger
`https://api.met.no/weatherapi/offshoremaps/1.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`), not Kartverket Transformering
(`--source transformering`), not MET Soundprofile
(`--source soundprofile`), not MET Gribfiles (`--source gribfiles`),
not MET Metgc (`--source metgc`), not MET Oslofjord
(`--source oslofjord`), and not MET Isobaricgrib
(`--source isobaricgrib`, now on main after PR 120). The root product
path and `/helicopterlightningobservations`,
`/helicoptersignificantwaveheight`, and
`/helicoptertriggeredlightningindex` print required `area` so they stay
unused for fetch. `/available` prints XML so it stays unused for fetch.

```bash
pda ingest --source offshoremaps --db data/registry.sqlite --limit 10
pda search features --db data/registry.sqlite
pda fetch --dataset offshoremaps:features --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 5 printed untemplated GET paths (catalog prints
5 paths with a last-segment id and no required query parameter, cap 10).
Live search `featurecollection` returns `offshoremaps:features`. Live fetch
GETs `https://api.met.no/weatherapi/offshoremaps/1.0/features` HTTP 200,
208 feature-id cells. Sample printed value: `MidNorway_obs_20260827T18`.
`pda methods` is not applicable: GeoJSON feature ids, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/offshoremaps_source_proof.json`.

## MET Turbulence source

`pda ingest --source turbulence` is another replaceable adapter. It lists printed
collection GET paths on the official MET Turbulence swagger
`https://api.met.no/weatherapi/turbulence/2.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`), not Kartverket Transformering
(`--source transformering`), not MET Soundprofile
(`--source soundprofile`), not MET Gribfiles (`--source gribfiles`),
not MET Metgc (`--source metgc`), not MET Oslofjord
(`--source oslofjord`), not MET Isobaricgrib
(`--source isobaricgrib`), and not MET Offshoremaps
(`--source offshoremaps`, now on main after PR 121). The root product
path, `/cross_section`, and `/map` print required `icao` so they stay
unused for fetch. `/available` prints XML so it stays unused for fetch.

```bash
pda ingest --source turbulence --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset turbulence:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 6 printed untemplated GET paths (catalog prints
6 paths with a last-segment id and no required query parameter, cap 10).
Live search `locations` returns `turbulence:locations`. Live fetch GETs
`https://api.met.no/weatherapi/turbulence/2.0/locations` HTTP 200, 19
location-name cells. Sample printed value: `ORSTA-VOLDA/HOVDEN`.
`pda methods` is not applicable: GeoJSON location names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/turbulence_source_proof.json`.

## MET NLAroutes source

`pda ingest --source nlaroutes` is another replaceable adapter. It lists printed
collection GET paths on the official MET NLAroutes swagger
`https://api.met.no/weatherapi/nlaroutes/1.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`), not Kartverket Transformering
(`--source transformering`), not MET Soundprofile
(`--source soundprofile`), not MET Gribfiles (`--source gribfiles`),
not MET Metgc (`--source metgc`), not MET Oslofjord
(`--source oslofjord`), not MET Isobaricgrib (`--source isobaricgrib`),
not MET Offshoremaps (`--source offshoremaps`), and not MET Turbulence
(`--source turbulence`, now on main after PR 122). The root product
path prints required `name`/`time`/`type`, `/timegraph` prints required
`location`/`time`, and `/vcross` prints required `route`/`time`, so they
stay unused for fetch. `/available` prints XML so it stays unused for
fetch.

```bash
pda ingest --source nlaroutes --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset nlaroutes:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 8 printed untemplated GET paths (catalog prints
8 paths with a last-segment id and no required query parameter, cap 10).
Live search `locations` returns `nlaroutes:locations`. Live fetch GETs
`https://api.met.no/weatherapi/nlaroutes/1.0/locations` HTTP 200, 154
location-name cells. Sample printed value: `BANAK`.
`pda methods` is not applicable: GeoJSON location names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/nlaroutes_source_proof.json`.

## MET Sigcharts source

`pda ingest --source sigcharts` is another replaceable adapter. It lists printed
collection GET paths on the official MET Sigcharts swagger
`https://api.met.no/weatherapi/sigcharts/2.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. The root product path has no last-segment id, so
it is not listed. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`), not Kartverket Transformering
(`--source transformering`), not MET Soundprofile
(`--source soundprofile`), not MET Gribfiles (`--source gribfiles`),
not MET Metgc (`--source metgc`), not MET Oslofjord
(`--source oslofjord`), not MET Isobaricgrib
(`--source isobaricgrib`), not MET Offshoremaps
(`--source offshoremaps`), not MET Turbulence
(`--source turbulence`), and not MET NLAroutes
(`--source nlaroutes`, now on main after PR 123). `/available` prints XML
so it stays unused for fetch.

```bash
pda ingest --source sigcharts --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset sigcharts:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 6 printed untemplated GET paths (catalog prints
6 paths with a last-segment id and no required query parameter, cap 10).
Live search `locations` returns `sigcharts:locations`. Live fetch GETs
`https://api.met.no/weatherapi/sigcharts/2.0/locations` HTTP 200, 2
location-name cells. Sample printed value: `Nordic`.
`pda methods` is not applicable: GeoJSON location names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/sigcharts_source_proof.json`.

## MET Volcanicashforecast source

`pda ingest --source volcanicashforecast` is another replaceable adapter. It
lists printed collection GET paths on the official MET Volcanicashforecast
swagger `https://api.met.no/weatherapi/volcanicashforecast/0.1/swagger`,
capped at 10. Templated `{format}` paths and GET operations that print
required query parameters are skipped. The root product path has no
last-segment id so it is skipped. Dataset ids are the last printed path
segment. `access_path` is the swagger origin + printed `basePath` + path.
License is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`), not Kartverket Transformering
(`--source transformering`), not MET Soundprofile
(`--source soundprofile`), not MET Gribfiles (`--source gribfiles`),
not MET Metgc (`--source metgc`), not MET Oslofjord
(`--source oslofjord`), not MET Isobaricgrib (`--source isobaricgrib`),
not MET Offshoremaps (`--source offshoremaps`), not MET Turbulence
(`--source turbulence`), not MET NLAroutes (`--source nlaroutes`),
and not MET Sigcharts (`--source sigcharts`, now on main after PR 124).
`/changelog` prints RSS and `/healthz` prints plain text, so they stay
unused for fetch. `/resources` prints a JSON array of file paths and
stays unused for this first fetch.

```bash
pda ingest --source volcanicashforecast --db data/registry.sqlite --limit 10
pda search something --db data/registry.sqlite
pda fetch --dataset volcanicashforecast:reftimes --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from the printed `/reftimes` JSON array. License is the printed swagger
CC BY 4.0 URL. Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 4 printed untemplated GET paths (catalog prints
4 paths with a last-segment id and no required query parameter, cap 10).
Live search `something` returns `volcanicashforecast:reftimes`. Live fetch
GETs `https://api.met.no/weatherapi/volcanicashforecast/0.1/reftimes`
HTTP 200, 27 printed reftime cells. Sample printed value:
`2026-06-09T11:00:00Z`. `pda methods` is not applicable: printed reftime
strings, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/volcanicashforecast_source_proof.json`.

`pda ingest --source routeforecast` is another replaceable adapter. It lists printed
collection GET paths on the official MET Routeforecast swagger
`https://api.met.no/weatherapi/routeforecast/2.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. The root product path prints required `route`, so
it is not listed. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path. License
is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`), not Kartverket Transformering
(`--source transformering`), not MET Soundprofile
(`--source soundprofile`), not MET Gribfiles (`--source gribfiles`),
not MET Metgc (`--source metgc`), not MET Oslofjord
(`--source oslofjord`), not MET Isobaricgrib
(`--source isobaricgrib`), not MET Offshoremaps
(`--source offshoremaps`), not MET Turbulence
(`--source turbulence`), not MET NLAroutes
(`--source nlaroutes`), not MET Sigcharts
(`--source sigcharts`), and not MET Volcanicashforecast
(`--source volcanicashforecast`, now on main after PR 125). `/available` prints XML
so it stays unused for fetch.

```bash
pda ingest --source routeforecast --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset routeforecast:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 8 printed untemplated GET paths (catalog prints
8 paths with a last-segment id and no required query parameter, cap 10).
Live search `locations` returns `routeforecast:locations`. Live fetch GETs
`https://api.met.no/weatherapi/routeforecast/2.0/locations` HTTP 200, 42
location-name cells. Sample printed value: `ENBJ-ENHF`.
`pda methods` is not applicable: GeoJSON location names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/routeforecast_source_proof.json`.

## Kartverket Den norske los source

`pda ingest --source norskelos` is another replaceable adapter. It lists
printed collection ids on the official Kartverket Den norske los OGC API
Features catalog `https://dnl.kartverket.no/api/ogc/v1/collections`,
capped at 10. Collections that print no id or no items GET href are
skipped. Dataset ids are the last printed collection-id segment.
`access_path` is the printed GeoJSON items href. License is the printed
OpenAPI CC BY 4.0 URL. Publisher stays null. This is not Metalerts
(`--source met`), not Nowcast (`--source nowcast`), not MET
Airqualityforecast (`--source airquality`), not Kartverket Kommuneinfo
(`--source kommuneinfo`), not Kartverket Hoydedata
(`--source hoydedata`), not Kartverket Stedsnavn
(`--source stedsnavn`), not Kartverket Transformering
(`--source transformering`), not NGU OGC Features (`--source ngu`),
not MET Volcanicashforecast (`--source volcanicashforecast`, now on
main after PR 125), and not MET Routeforecast (`--source routeforecast`,
now on main after PR 126).

```bash
pda ingest --source norskelos --db data/registry.sqlite --limit 10
pda search place --db data/registry.sqlite
pda fetch --dataset norskelos:place --db data/registry.sqlite
```

`pda fetch` GETs the stored collection items URL. Observation values are
copied from printed GeoJSON feature `title`. License is the printed
OpenAPI CC BY 4.0 URL. Publisher stays null: the catalog does not print
a publisher field.

Live ingest 2026-08-27: 2 printed collections (catalog prints 2
collections with an items GET href, cap 10). Live search `place`
returns `norskelos:place`. Live fetch GETs
`https://dnl.kartverket.no/api/ogc/v1/collections/dennorskelos/place/items?f=json`
HTTP 200, 50 printed place-title rows. Sample printed value: Fillan.
`pda methods` is not applicable: GeoJSON place titles, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/norskelos_source_proof.json`.

`pda ingest --source locationforecast` is another replaceable adapter. It lists printed
collection GET paths on the official MET Locationforecast swagger
`https://api.met.no/weatherapi/locationforecast/2.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Forecast paths `/classic`, `/compact`, and
`/complete` print required `lat` and `lon`, so they are not listed.
Dataset ids are the last printed path segment. `access_path` is the
swagger origin + printed `basePath` + path. License is the printed
swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not Nowcast (`--source nowcast`),
not MET Airqualityforecast (`--source airquality`), not MET Tidalwater
(`--source tidalwater`), not MET Oceanforecast (`--source oceanforecast`),
not MET Sunrise (`--source sunrise`), not MET Radar (`--source radar`),
not MET Spotwind (`--source spotwind`), not MET Textforecast
(`--source textforecast`), not MET Icemap (`--source icemap`), not MET
NCAgalewarnings (`--source ncagalewarnings`), not MET Tafmetar
(`--source tafmetar`), not MET Subseasonal (`--source subseasonal`),
not MET Geosatellite (`--source geosatellite`), not MET Metgm
(`--source metgm`), not MET Subjectiveforecast
(`--source subjectiveforecast`), not MET Polarsatellite
(`--source polarsatellite`), not Kartverket Transformering
(`--source transformering`), not MET Soundprofile
(`--source soundprofile`), not MET Gribfiles (`--source gribfiles`),
not MET Metgc (`--source metgc`), not MET Oslofjord
(`--source oslofjord`), not MET Isobaricgrib
(`--source isobaricgrib`), not MET Offshoremaps
(`--source offshoremaps`), not MET Turbulence
(`--source turbulence`), not MET NLAroutes
(`--source nlaroutes`), not MET Sigcharts
(`--source sigcharts`), not MET Volcanicashforecast
(`--source volcanicashforecast`), not MET Routeforecast
(`--source routeforecast`, now on main after PR 126), not Kartverket
Den norske los (`--source norskelos`, now on main after PR 127), and
not MET Aviationforecast or MET Sigmets.

```bash
pda ingest --source locationforecast --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset locationforecast:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-27: 5 printed untemplated GET paths (catalog prints
5 paths with a last-segment id and no required query parameter, cap 10).
Live search `locations` returns `locationforecast:locations`. Live fetch GETs
`https://api.met.no/weatherapi/locationforecast/2.0/locations` HTTP 200, 2
location-name cells. Sample printed value: `ECMWF area`.
`pda methods` is not applicable: GeoJSON location names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/locationforecast_source_proof.json`.

## Kartverket Register source

`pda ingest --source georegister` is another replaceable adapter. It lists
printed collection GET paths on the official Kartverket Register swagger
`https://register.geonorge.no/swagger/docs/v1`, capped at 10. Templated
paths and GET operations that print required parameters are skipped.
Dataset ids are the last printed path segment. `access_path` is the
printed swagger host plus path. License stays null: the swagger does not
print a license URL. Publisher stays null. This is not Geonorge
Kartkatalog (`--source geonorge`), not Kartverket Kommuneinfo
(`--source kommuneinfo`), not Kartverket Stedsnavn
(`--source stedsnavn`), not Kartverket Hoydedata
(`--source hoydedata`), not Kartverket Transformering
(`--source transformering`), not Kartverket Den norske los
(`--source norskelos`), and not MET Locationforecast
(`--source locationforecast`, now on main after PR 128).

```bash
pda ingest --source georegister --db data/registry.sqlite --limit 10
pda search municipalities --db data/registry.sqlite
pda fetch --dataset georegister:kommuner --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed JSON `Name`. License stays null. Publisher stays
null: the swagger does not print a publisher field.

Live ingest 2026-08-28: 6 printed collection GET paths (swagger prints
6 untemplated GET paths with no required parameters, cap 10). Live
search `municipalities` returns `georegister:kommuner`. Live fetch GETs
`https://register.geonorge.no/api/v2/organisasjoner/kommuner`
HTTP 200, 357 printed municipality-name rows. Sample printed value:
Utsira kommune. `pda methods` is not applicable: municipality names,
not a numeric time series (`no observations matched entity/measure;
available=[]`). Proof is `data/georegister_source_proof.json`.

`pda ingest --source nortaxa` is another replaceable adapter. It lists printed
collection GET paths on the official Artsdatabanken Nortaxa swagger
`https://nortaxa.artsdatabanken.no/swagger/v1/swagger.json`, capped at 10.
Templated `{id}` paths and GET operations that print required query
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed path. Publisher and license
stay null: the swagger document does not print those fields.
This is not Artsdatabanken Natur i Norge (`--source nin`), not MET
Locationforecast (`--source locationforecast`), and not Kartverket
Register (`--source georegister`, now on main after PR 129).

```bash
pda ingest --source nortaxa --db data/registry.sqlite --limit 10
pda search Ranks --db data/registry.sqlite
pda fetch --dataset nortaxa:RankList --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed JSON `name` when present, otherwise `displayName`, `title`,
or `id`. Publisher and license stay null: the spec does not print them.

Live ingest 2026-08-28: 9 printed untemplated GET paths (catalog prints
9 paths with a last-segment id and no required query parameter, cap 10).
Live search `Ranks` returns `nortaxa:RankList`. Live fetch GETs
`https://nortaxa.artsdatabanken.no/api/v1/Lists/RankList` HTTP 200, 25
rank-name cells. Sample printed value: `Kingdom`.
`pda methods` is not applicable: taxonomic rank names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/nortaxa_source_proof.json`.

## Artsdatabanken Artskart source

`pda ingest --source artskart` is another replaceable adapter. It lists
printed collection GET paths on the official Artskart swagger
`https://artskart.artsdatabanken.no/publicapi/swagger/docs/v1`, capped at 10.
Templated paths and GET operations that print required parameters are
skipped. Dataset ids are the last printed path segment. `access_path` is
the printed swagger host plus `basePath` plus path. License stays null:
the swagger does not print a license URL. Publisher stays null. This is
not Artsdatabanken Natur i Norge (`--source nin`), not Artsdatabanken
Nortaxa (`--source nortaxa`, now on main after PR 130), not Kartverket
Register (`--source georegister`), and not MET Locationforecast
(`--source locationforecast`, now on main after PR 128).

```bash
pda ingest --source artskart --db data/registry.sqlite --limit 10
pda search observation --db data/registry.sqlite
pda fetch --dataset artskart:list --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed JSON `ScientificName`. License stays null. Publisher
stays null: the swagger does not print a publisher field.

Live ingest 2026-08-28: 5 printed collection GET paths (swagger prints
5 untemplated GET paths with no required parameters, cap 10). Live
search `observation` returns `artskart:list`. Live fetch GETs
`https://artskart.artsdatabanken.no/publicapi/api/observations/list`
HTTP 200, 20 printed scientific-name rows. Sample printed value:
Myriospora scabrida. `pda methods` is not applicable: scientific names,
not a numeric time series (`no observations matched entity/measure;
available=[]`). Proof is `data/artskart_source_proof.json`.

`pda ingest --source lister` is another replaceable adapter. It lists
printed collection GET paths on the official Artsdatabanken Assessments
swagger `https://lister.artsdatabanken.no/swagger/v1/swagger.json`,
capped at 10. Templated paths and GET operations that print required
parameters are skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger document origin plus the printed path.
License stays null: the swagger does not print a license URL. Publisher
stays null. This is not Artskart (`--source artskart`, now on main after
PR 131), not Nortaxa (`--source nortaxa`), not Natur i Norge
(`--source nin`), and not Kartverket Register (`--source georegister`).

```bash
pda ingest --source lister --db data/registry.sqlite --limit 10
pda search naturetypesassessment2025 --db data/registry.sqlite
pda fetch --dataset lister:naturetypesassessment2025 --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed OData `value` records, keeping printed `name`.
License stays null. Publisher stays null: the swagger does not print a
publisher field.

Live ingest copies the swagger-printed untemplated GET paths with no
required parameters (cap 10). Live search `naturetypesassessment2025`
returns `lister:naturetypesassessment2025`. Live fetch GETs
`https://lister.artsdatabanken.no/odata/v1/naturetypesassessment2025`
HTTP 200 and copies printed nature-type names. `pda methods` is not
applicable: nature-type names, not a numeric time series. Proof is
`data/lister_source_proof.json`.

## Kartverket OGC Coverages source

`pda ingest --source ogccoverages` is another replaceable adapter. It lists
printed collection GET paths on the official Kartverket OGC Coverages
OpenAPI `https://kartverket-ogc-api.azurewebsites.net/openapi?f=json`,
capped at 10. The root path (no last-segment id), templated paths, POST
execution, and GET operations that print required parameters are skipped.
Dataset ids are the printed path without a leading slash so two
`/coverage` suffixes stay distinct. `access_path` is the printed OpenAPI
server URL plus path. License is copied from the printed OpenAPI CC BY
4.0 URL. Publisher stays null: contact name Kartverket stays in harvested
OpenAPI info and is not copied as a publisher. This is not Kartverket
Hoydedata (`--source hoydedata`), not Geonorge Kartkatalog
(`--source geonorge`), not Kartverket Register
(`--source georegister`), not Kartverket Den norske los
(`--source norskelos`), not Artsdatabanken Nortaxa
(`--source nortaxa`), not Artsdatabanken Artskart
(`--source artskart`, now on main after PR 131), and not Artsdatabanken
Lister (`--source lister`, now on main after PR 133).

```bash
pda ingest --source ogccoverages --db data/registry.sqlite --limit 10
pda search Collections --db data/registry.sqlite
pda fetch --dataset ogccoverages:collections --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed JSON `title` when present, otherwise `name` or `id`. License
is the printed OpenAPI CC BY 4.0 URL. Publisher stays null.

Live ingest 2026-08-28: 10 printed untemplated GET paths (catalog prints
13 paths with a last-segment id and no required parameter, cap 10).
Live search `Collections` returns `ogccoverages:collections`. Live fetch
GETs `https://kartverket-ogc-api.azurewebsites.net/collections`
HTTP 200, 2 collection-title cells. Sample printed value:
`DTM 10 Terrengmodell (UTM32)`.
`pda methods` is not applicable: collection titles, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/ogccoverages_source_proof.json`.

## Brønnøysundregistrene Regnskapsregisteret source

`pda ingest --source regnskap` is another replaceable adapter. It lists
printed collection GET paths on the official Regnskapsregisteret OpenAPI
`https://data.brreg.no/regnskapsregisteret/regnskap/v3/api-docs`,
capped at 10. Templated paths and GET operations that print required
parameters are skipped. Dataset ids are the printed path without a
leading slash. `access_path` is the printed OpenAPI server URL plus
path. License stays null: the OpenAPI prints no license URL. Publisher
stays null: the OpenAPI prints no publisher field. This is not
Enhetsregisteret (`--source brreg`). Open PRs at pickup were empty.
Lane B (`bc-876ee4c8`) was probing Udir NLR (`data-nlr.udir.no`) and
was not selected.

```bash
pda ingest --source regnskap --db data/registry.sqlite --limit 10
pda search log --db data/registry.sqlite
pda fetch --dataset regnskap:regnskapsregisteret/regnskap/log --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed JSON filenames or other scalars. License stays
null. Publisher stays null.

Live ingest 2026-08-28: 4 printed untemplated GET paths (catalog
prints 4 paths with a last-segment id and no required parameter).
Live search `log` returns `regnskap:regnskapsregisteret/regnskap/log`.
Live fetch GETs `https://data.brreg.no/regnskapsregisteret/regnskap/log`
HTTP 200, 2190 filename cells. Sample printed value:
`20180102202758-masse.xml`.
`pda methods` is not applicable: filename strings, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/regnskap_source_proof.json`.

`pda ingest --source cristin` is another replaceable adapter. It lists
printed collection GET paths on the official Cristin v2 documentation
`https://api.cristin.no/v2/`, capped at 10. Templated `{id}` / `{pid}`
paths are skipped. Optional `?{parameters}` on a printed title is not
treated as a required query. Dataset ids are the printed paths so
`results/categories` stays distinct from `projects/categories`.
`access_path` is the documentation origin plus the printed path.
License stays null: the documentation does not print a license URL.
Publisher stays null. This is not Sikt DataverseNO (`--source sikt`),
not Artsdatabanken Assessments (`--source lister`), not Kartverket
OGC Coverages (`--source ogccoverages`, now on main after PR 132),
and not Regnskapsregisteret (`--source regnskap`, now on main after
PR 135).

```bash
pda ingest --source cristin --db data/registry.sqlite --limit 10
pda search countries --db data/registry.sqlite
pda fetch --dataset cristin:countries --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed JSON records, keeping printed localized `name`.
License stays null. Publisher stays null: the documentation does not
print a publisher field.

Live ingest copies the documentation-printed untemplated GET paths
(cap 10). Live search `countries` returns `cristin:countries`. Live
fetch GETs `https://api.cristin.no/v2/countries` HTTP 200 and copies
printed country names. `pda methods` is not applicable: country names,
not a numeric time series. Proof is `data/cristin_source_proof.json`.

## Fiskeridirektoratet Omregningsfaktorer source

`pda ingest --source omregning` is another replaceable adapter. It lists
printed collection GET paths on the official Omregningsfaktorer OpenAPI
`https://api.fiskeridir.no/conversion-factor-api/swagger/api`,
capped at 10. Templated paths and GET operations that print required
parameters are skipped. Dataset ids are the printed last path segment.
`access_path` is the printed OpenAPI server URL plus path. License stays
null: the OpenAPI prints no license URL. Publisher stays null: the
OpenAPI prints no publisher field. This is not Fartøyregisteret
(`--source fiskeridir`), Kjøperregisteret (`--source buyer`), NYTEK
(`--source nytek`), Akvakulturregister (`--source aqua`),
Akvakulturforskning (`--source research`), Akvakultursøknader
(`--source portal`), Regnskapsregisteret (`--source regnskap`),
or Cristin (`--source cristin`, now on main after PR 134).

```bash
pda ingest --source omregning --db data/registry.sqlite --limit 10
pda search omregningsfaktorer --db data/registry.sqlite
pda fetch --dataset omregning:search --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed JSON `fish` codes or other scalars. License stays
null. Publisher stays null.

Live ingest 2026-08-28: 1 printed untemplated GET path (catalog
prints 1 path with a last-segment id and no required parameter).
Live search `omregningsfaktorer` returns `omregning:search`.
Live fetch GETs
`https://api.fiskeridir.no/conversion-factor-api/api/v1/conversionfactors/search`
HTTP 200, 1950 conversion-factor cells. Sample printed value: `0102`.
`pda methods` is not applicable: fish-code strings, not a numeric
time series (`no period in dimensions or period field`).
Proof is `data/omregning_source_proof.json`.

## Havforskningsinstituttet OGC Coverages source

`pda ingest --source hicoverages` is another replaceable adapter. It lists
printed `application/json` GET hrefs on the official Havforskningsinstituttet
OGC Coverages landing page `https://kart.hi.no/data/ogc/coverages/v1`,
capped at 10. `self` / `alternate` links, HTML links, and the OpenAPI
service-desc (non-JSON type) are skipped. Dataset ids are the printed
last path segment so `/collections` stays distinct from `/conformance`.
`access_path` is the printed landing-page href, including the printed
`f=application/json` query. License stays null: the landing page prints
no license URL. Publisher stays null. This is not Havforskningsinstituttet
OGC Features (`--source hi`) and not Kartverket OGC Coverages
(`--source ogccoverages`).

```bash
pda ingest --source hicoverages --db data/registry.sqlite --limit 10
pda search collections --db data/registry.sqlite
pda fetch --dataset hicoverages:collections --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed JSON `title` when present, otherwise `name` or `id`. License
stays null. Publisher stays null.

Live ingest 2026-08-28: 2 printed application/json GET hrefs (catalog
prints conformance and collections; cap 10). Live search `collections`
returns `hicoverages:collections`. Live fetch GETs
`https://kart.hi.no/data/ogc/coverages/v1/collections?f=application%2Fjson`
HTTP 200, 32 collection-title cells. Sample printed value: `reprojected`.
`pda methods` is not applicable: collection titles, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/hicoverages_source_proof.json`.

## Fiskeridirektoratet Miljøundersøkelser source

`pda ingest --source envreportreg` is another replaceable adapter. It lists
printed collection GET paths on the official Miljøundersøkelser OpenAPI
`https://api.fiskeridir.no/envreportreg-public/v3/api-docs`,
capped at 10. Templated paths and GET operations that print required
parameters are skipped. Dataset ids are the printed path without a
leading slash so v1 and v2 search stay distinct. `access_path` is the
printed OpenAPI server URL plus path. License is copied from the printed
OpenAPI license URL. Publisher stays null: the OpenAPI prints no
publisher field. This is not Fartøyregisteret (`--source fiskeridir`),
Kjøperregisteret (`--source buyer`), NYTEK (`--source nytek`),
Akvakulturregister (`--source aqua`), Akvakulturforskning
(`--source research`), Akvakultursøknader (`--source portal`),
Omregningsfaktorer (`--source omregning`), or Havforskningsinstituttet
OGC Coverages (`--source hicoverages`, now on main after PR 137).

```bash
pda ingest --source envreportreg --db data/registry.sqlite --limit 10
pda search miljørapporter --db data/registry.sqlite
pda fetch --dataset envreportreg:api/v2/report/search --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed JSON `siteName` values or other scalars. License is
copied from the printed OpenAPI URL. Publisher stays null.

Live ingest 2026-08-28: 2 printed untemplated GET paths (catalog
prints 2 paths with a last-segment id and no required parameter).
Live search `miljørapporter` returns `envreportreg:api/v2/report/search`
(and the v1 twin). Live fetch GETs
`https://api.fiskeridir.no/envreportreg-public/api/v2/report/search`
HTTP 200, 100 miljørapport cells. Sample printed value: `TORANGSKJERET`.
`pda methods` is not applicable: site-name strings, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/envreportreg_source_proof.json`.

## Havforskningsinstituttet OGC Maps source

`pda ingest --source himaps` is another replaceable adapter. It lists
printed `application/json` GET hrefs on the official Havforskningsinstituttet
OGC Maps landing page `https://kart.hi.no/data/ogc/maps/v1`,
capped at 10. `self` / `alternate` links, HTML links, and the OpenAPI
service-desc (non-JSON type) are skipped. Dataset ids are the printed
last path segment so `/collections` stays distinct from `/conformance`.
`access_path` is the printed landing-page href, including the printed
`f=application/json` query. License stays null: the landing page prints
no license URL. Publisher stays null. This is not Havforskningsinstituttet
OGC Features (`--source hi`) and not Havforskningsinstituttet OGC Coverages
(`--source hicoverages`).

```bash
pda ingest --source himaps --db data/registry.sqlite --limit 10
pda search collections --db data/registry.sqlite
pda fetch --dataset himaps:collections --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed JSON `title` when present, otherwise `name` or `id`. License
stays null. Publisher stays null.

Live ingest 2026-08-28: 2 printed application/json GET hrefs (catalog
prints conformance and collections; cap 10). Live search `collections`
returns `himaps:collections`. Live fetch GETs
`https://kart.hi.no/data/ogc/maps/v1/collections?f=application%2Fjson`
HTTP 200, 173 collection-title cells. Sample printed value: `reprojected`.
`pda methods` is not applicable: collection titles, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/himaps_source_proof.json`.

## Stortinget åpne data source

`pda ingest --source stortinget` is another replaceable adapter. It lists
printed untemplated `/eksport/` collection hrefs on the official Stortinget
technical documentation
`https://data.stortinget.no/dokumentasjon-og-hjelp/teknisk-dokumentasjon/`,
capped at 10. Printed example URIs that include a query string (required
parameters) are skipped. Dataset ids are the printed last path segment.
`access_path` is the documentation origin plus path plus the documented
`format=json` parameter. License stays null: the documentation prints no
license URL. Publisher stays null: the documentation prints no publisher
field. This is not Cristin (`--source cristin`), not Fiskeridirektoratet
Miljøundersøkelser (`--source envreportreg`), not Havforskningsinstituttet
OGC Coverages (`--source hicoverages`), and not Havforskningsinstituttet
OGC Maps (`--source himaps`, now on main after PR 139).

```bash
pda ingest --source stortinget --db data/registry.sqlite --limit 10
pda search stortingsperioder --db data/registry.sqlite
pda fetch --dataset stortinget:stortingsperioder --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed JSON `navn` when present, otherwise `id`, `fornavn`, or
`etternavn`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 8 printed untemplated `/eksport/` hrefs (catalog
prints 8 collection paths with a last-segment id and no query string).
Live search `stortingsperioder` returns `stortinget:stortingsperioder`.
Live fetch GETs
`https://data.stortinget.no/eksport/stortingsperioder?format=json`
HTTP 200, 21 stortingsperiode cells. Sample printed value: `2025-2029`.
`pda methods` is not applicable: period-id strings, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/stortinget_source_proof.json`.

## Havforskningsinstituttet OGC Styles source

`pda ingest --source histyles` is another replaceable adapter. It lists
printed `application/json` GET hrefs on the official Havforskningsinstituttet
OGC Styles landing page `https://kart.hi.no/data/ogc/styles/v1`,
capped at 10. `self` / `alternate` links, HTML links, and the OpenAPI
service-desc (non-JSON type) are skipped. Dataset ids are the printed
last path segment so `/styles` stays distinct from `/conformance`.
`access_path` is the printed landing-page href, including the printed
`f=application/json` query. License stays null: the landing page prints
no license URL. Publisher stays null. This is not Havforskningsinstituttet
OGC Features (`--source hi`), not Havforskningsinstituttet OGC Coverages
(`--source hicoverages`), and not Havforskningsinstituttet OGC Maps
(`--source himaps`).

```bash
pda ingest --source histyles --db data/registry.sqlite --limit 10
pda search styles --db data/registry.sqlite
pda fetch --dataset histyles:styles --db data/registry.sqlite
```

`pda fetch` GETs the stored styles URL. Observation values are copied
from printed JSON `title` when present, otherwise `name` or `id`. License
stays null. Publisher stays null.

Live ingest 2026-08-28: 2 printed application/json GET hrefs (catalog
prints conformance and styles; cap 10). Live search `styles`
returns `histyles:styles`. Live fetch GETs
`https://kart.hi.no/data/ogc/styles/v1/styles?f=application%2Fjson`
HTTP 200, 238 style-title cells. Sample printed value: `Spredningssimulering torsk`.
`pda methods` is not applicable: style titles, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/histyles_source_proof.json`.

## Havforskningsinstituttet OGC Tiles source

`pda ingest --source hitiles` is another replaceable adapter. It lists
printed `application/json` GET hrefs on the official Havforskningsinstituttet
OGC Tiles landing page `https://kart.hi.no/data/ogc/tiles/v1`,
capped at 10. `self` / `alternate` links, HTML links, and the OpenAPI
service-desc (non-JSON type) are skipped. Dataset ids are the printed
last path segment so `/tileMatrixSets` stays distinct from `/conformance`.
`access_path` is the printed landing-page href, including the printed
`f=application/json` query. License stays null: the landing page prints
no license URL. Publisher stays null. This is not Havforskningsinstituttet
OGC Features (`--source hi`), not Havforskningsinstituttet OGC Coverages
(`--source hicoverages`), not Havforskningsinstituttet OGC Maps
(`--source himaps`), not Stortinget åpne data (`--source stortinget`),
and not Havforskningsinstituttet OGC Styles (`--source histyles`, now
on main after PR 141).

```bash
pda ingest --source hitiles --db data/registry.sqlite --limit 10
pda search matrix --db data/registry.sqlite
pda fetch --dataset hitiles:tileMatrixSets --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed JSON `title` when present, otherwise `name` or `id`. License
stays null. Publisher stays null.

Live ingest 2026-08-28: 3 printed application/json GET hrefs (catalog
prints conformance, collections, and tileMatrixSets; cap 10). Live search
`matrix` returns `hitiles:tileMatrixSets`. Live fetch GETs
`https://kart.hi.no/data/ogc/tiles/v1/tileMatrixSets?f=application%2Fjson`
HTTP 200, 143 tile-matrix-set title cells. Sample printed value: `3575`.
`pda methods` is not applicable: tile-matrix-set titles, not a numeric
time series (`no derived yoy_growth values to chart`).
Proof is `data/hitiles_source_proof.json`.

## Fiskeridirektoratet Miljørapporter source

`pda ingest --source miljorapporter` is another replaceable adapter. It lists
printed collection GET paths on the official Miljørapporter OpenAPI
`https://api.fiskeridir.no/miljorapporter-api/v3/api-docs`,
capped at 10. Templated paths and GET operations that print required
parameters are skipped. Dataset ids are the printed path without a
leading slash so `env-reports` stays distinct from `env-report-overviews`.
`access_path` is the printed OpenAPI server URL plus path. License is
copied from the printed OpenAPI license URL. Publisher stays null: the
OpenAPI prints no publisher field. The document prints a global Keycloak
scheme; collection GET operations print no operation security. Live GET
of those printed paths is HTTP 200 with no token. No token is sent. This
is not Fartøyregisteret (`--source fiskeridir`), Kjøperregisteret
(`--source buyer`), NYTEK (`--source nytek`), Akvakulturregister
(`--source aqua`), Akvakulturforskning (`--source research`),
Akvakultursøknader (`--source portal`), Omregningsfaktorer
(`--source omregning`), Miljøundersøkelser (`--source envreportreg`),
or Havforskningsinstituttet OGC Styles (`--source histyles`), or
Havforskningsinstituttet OGC Tiles (`--source hitiles`, now on main
after PR 142).

```bash
pda ingest --source miljorapporter --db data/registry.sqlite --limit 10
pda search env-reports --db data/registry.sqlite
pda fetch --dataset miljorapporter:api/v1/env-reports --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed JSON `siteName` values or other scalars. License is
copied from the printed OpenAPI URL. Publisher stays null.

Live ingest 2026-08-28: 3 printed untemplated GET paths (catalog
prints env-reports, env-report-overviews, and ping; cap 10). Live
search `getEnvReports` returns `miljorapporter:api/v1/env-reports`.
Live fetch GETs
`https://api.fiskeridir.no/miljorapporter-api/api/v1/env-reports`
HTTP 200, 100 miljørapport cells. Sample printed value: `Leivsethammran`.
`pda methods` is not applicable: site-name strings, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/miljorapporter_source_proof.json`.

## NVE GIS source

`pda ingest --source nvegis` is another replaceable adapter. It lists
printed MapServer services on the official NVE ArcGIS REST catalog
`https://gis3.nve.no/map/rest/services?f=json`, capped at 10. Folders,
empty names, and empty types are skipped. Dataset ids are the printed
last path segment of `name` so `/Fjellskred1/MapServer` stays distinct
from `/Nettanlegg3/MapServer`. `access_path` is the printed name plus
type plus the catalog's `f=json` query. License stays null: the catalog
prints no license URL. Publisher stays null. This is not NVE
Magasinstatistikk (`--source nve`), not Havforskningsinstituttet OGC
Tiles (`--source hitiles`), and not Fiskeridirektoratet Miljørapporter
(`--source miljorapporter`, now on main after PR 143).

```bash
pda ingest --source nvegis --db data/registry.sqlite --limit 10
pda search Fjellskred1 --db data/registry.sqlite
pda fetch --dataset nvegis:Fjellskred1 --db data/registry.sqlite
```

`pda fetch` GETs the stored MapServer URL. Observation values are copied
from printed JSON `name` when present, otherwise `mapName`, `title`, or
`id`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 5 printed MapServer services (catalog prints
Fjellskred1, Nettanlegg3, Skredfaresoner3, SnoskredAktsomhetLosneOmr,
and SnoskredAktsomhet; cap 10). Live search `Fjellskred1` returns
`nvegis:Fjellskred1`. Live fetch GETs
`https://gis3.nve.no/map/rest/services/Fjellskred1/MapServer?f=json`
HTTP 200, 30 layer-name cells. Sample printed value: `Overvaking_fjellskred`.
`pda methods` is not applicable: layer names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/nvegis_source_proof.json`.

## Kystverket navigasjonsvarsler source

`pda ingest --source navwarnings` is another replaceable adapter. It lists
printed collection GET paths on the official Kystverket Data API OpenAPI
`https://api.kystverket.no/openapi.json`, capped at 10. Templated paths
and GET operations with required parameters are skipped. Dataset ids are
the printed last path segment so `/data/navigationwarnings/coastal/`
stays distinct from `/data/navigationwarnings/navareaxix/`.
`access_path` is the OpenAPI document origin plus the printed path.
License stays null: the OpenAPI prints no license URL. Publisher stays
null. This is not Kystdatahuset (`--source kystverket`) and not NVE GIS
(`--source nvegis`, now on main after PR 144).

```bash
pda ingest --source navwarnings --db data/registry.sqlite --limit 10
pda search coastal --db data/registry.sqlite
pda fetch --dataset navwarnings:coastal --db data/registry.sqlite
```

`pda fetch` GETs the stored Data API URL. Observation values are copied
from printed JSON `location` when present, otherwise `warningnumber`,
`message_no`, `message_en`, or `eventid`. License stays null. Publisher
stays null.

Live ingest 2026-08-28: 3 printed untemplated GET paths (catalog
prints coastal, navareaxix, and dadjokes; cap 10). Live search `coastal`
returns `navwarnings:coastal`. Live fetch GETs
`https://api.kystverket.no/data/navigationwarnings/coastal/`
HTTP 200, 7 location-name cells. Sample printed value: `Rekefjordboen`.
`pda methods` is not applicable: location names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/navwarnings_source_proof.json`.

## Kartverket Havnedata source

`pda ingest --source havnedata` is another replaceable adapter. It lists
printed collection GET paths on the official Kartverket Havnedata OpenAPI
`https://ogcapitest.kartverket.no/rest/services/havnedata3_0/api?f=json`,
capped at 10. The root path, templated paths, and GET operations that
print required parameters are skipped. Dataset ids are the printed path
without a leading slash so `collections` stays distinct from
`collections/avfallspunkt`. `access_path` is the printed OpenAPI server
URL plus path. License stays null: the OpenAPI prints no license URL.
Publisher stays null: the OpenAPI prints no publisher field. The
document prints no security scheme. Live GET of those printed paths is
HTTP 200 with no token. No token is sent. This is not Kartverket OGC
Coverages (`--source ogccoverages`), Den norske los
(`--source norskelos`), Kartverket Register (`--source georegister`),
Stedsnavn (`--source stedsnavn`), Kommuneinfo (`--source kommuneinfo`),
Høydedata (`--source hoydedata`), Transformering
(`--source transformering`), Fiskeridirektoratet Miljørapporter
(`--source miljorapporter`, now on main after PR 143), NVE GIS
(`--source nvegis`, now on main after PR 144), or Kystverket
navigasjonsvarsler (`--source navwarnings`, now on main after PR 146).

```bash
pda ingest --source havnedata --db data/registry.sqlite --limit 10
pda search avfallspunkt --db data/registry.sqlite
pda fetch --dataset havnedata:collections --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed JSON `title` values or other scalars. License stays
null. Publisher stays null.

Live ingest 2026-08-28: 10 printed untemplated GET paths (catalog
prints conformance, collections, and collection metadata; cap 10). Live
search `avfallspunkt` returns `havnedata:collections/avfallspunkt`.
Live fetch GETs
`https://ogcapitest.kartverket.no/rest/services/havnedata3_0/collections`
HTTP 200, 22 collection title cells. Sample printed value:
`administrativthavneområde`. `pda methods` is not applicable: collection
titles, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/havnedata_source_proof.json`.

## Miljødirektoratet GIS source

`pda ingest --source miljogis` is another replaceable adapter. It lists
printed MapServer services on the official Miljødirektoratet ArcGIS REST
catalog `https://kart.miljodirektoratet.no/arcgis/rest/services?f=json`,
capped at 10. FeatureServer rows with the same printed name, folders,
and entries with no name or type are skipped. Dataset ids are the
printed last path segment of `name` so `anadrome_laksefisk` stays
distinct from `artfunksjon`. `access_path` keeps the printed name,
MapServer type, and the catalog `f=json` query. License stays null:
the catalog prints no license URL. Publisher stays null. This is not
Vannmiljø (`--source miljodir`), not NVE GIS (`--source nvegis`), not
Kystverket navigasjonsvarsler (`--source navwarnings`, now on main
after PR 146), and not Kartverket Havnedata (`--source havnedata`, now
on main after PR 145).

```bash
pda ingest --source miljogis --db data/registry.sqlite --limit 10
pda search anadrome_laksefisk --db data/registry.sqlite
pda fetch --dataset miljogis:anadrome_laksefisk --db data/registry.sqlite
```

`pda fetch` GETs the stored MapServer URL. Observation values are copied
from printed JSON `name` when present, otherwise `mapName`, `title`, or
`id`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 10 printed MapServer services (catalog prints
21 MapServer names; cap 10 starts at anadrome_laksefisk through
naturtyper_hb13). Live search `anadrome_laksefisk` returns
`miljogis:anadrome_laksefisk`. Live fetch GETs
`https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/MapServer?f=json`
HTTP 200, 10 layer-name cells. Sample printed value:
`anadrome_vandringshinder_laks`.
`pda methods` is not applicable: layer names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/miljogis_source_proof.json`.

## Kartverket Høydedata GIS source

`pda ingest --source hoydegis` is another replaceable adapter. It lists
printed name+type services on the official Kartverket Høydedata ArcGIS
REST catalog `https://hoydedata.no/arcgis/rest/services?f=json`, capped
at 10. Folders and entries with no name or type are skipped. Dataset
ids are the printed last path segment of `name` so `Arealstatistikk`
stays distinct from `DTM`. `access_path` keeps the printed name, printed
type, and the catalog `f=json` query. License stays null: the catalog
prints no license URL. Publisher stays null. This is not Kartverket
Høydedata OpenAPI (`--source hoydedata`), not Miljødirektoratet GIS
(`--source miljogis`, now on main after PR 147), and not NVE GIS
(`--source nvegis`).

```bash
pda ingest --source hoydegis --db data/registry.sqlite --limit 10
pda search DTM --db data/registry.sqlite
pda fetch --dataset hoydegis:DTM --db data/registry.sqlite
```

`pda fetch` GETs the stored service URL. Observation values are copied
from printed JSON `name` when present, otherwise `mapName`, `title`, or
`id`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 10 printed services (catalog prints 35
name+type rows; cap 10 starts at Arealstatistikk through dummy32).
Live search `DTM` returns `hoydegis:DTM`. Live fetch GETs
`https://hoydedata.no/arcgis/rest/services/DTM/ImageServer?f=json`
HTTP 200, 1 service-name cell. Sample printed value: `DTM`.
`pda methods` is not applicable: a service name, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/hoydegis_source_proof.json`.

## Norsk Polarinstitutt GIS source

`pda ingest --source npigis` is another replaceable adapter. It lists
printed MapServer services on the official Norsk Polarinstitutt ArcGIS
REST Basisdata catalog
`https://geodata.npolar.no/arcgis/rest/services/Basisdata?f=json`,
capped at 10. The folder name `Basisdata` is printed on the root
services catalog. Empty names and empty types are skipped. Dataset ids
are the printed last path segment of `name` so
`/NP_Basiskart_Svalbard_WMS/MapServer` stays distinct from
`/NP_Basiskart_JanMayen_WMS/MapServer`. `access_path` is the printed
name plus type plus the catalog's `f=json` query. License stays null:
the catalog prints no license URL. Publisher stays null. This is not
the NPI Open Data API (`--source npolar`), not NVE GIS
(`--source nvegis`), not Kartverket Havnedata (`--source havnedata`),
not Miljødirektoratet GIS (`--source miljogis`, now on main after
PR 147), and not Kartverket Høydedata GIS (`--source hoydegis`, now on
main after PR 149).

```bash
pda ingest --source npigis --db data/registry.sqlite --limit 10
pda search JanMayen_WMS --db data/registry.sqlite
pda fetch --dataset npigis:NP_Basiskart_Svalbard_WMS --db data/registry.sqlite
```

`pda fetch` GETs the stored MapServer URL. Observation values are copied
from printed JSON `name` when present, otherwise `mapName`, `title`, or
`id`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 10 printed MapServer services (catalog prints
FKB and Basiskart services for Svalbard and Jan Mayen; cap 10). Live
search `JanMayen_WMS` returns `npigis:NP_Basiskart_JanMayen_WMS`. Live
fetch GETs
`https://geodata.npolar.no/arcgis/rest/services/Basisdata/NP_Basiskart_Svalbard_WMS/MapServer?f=json`
HTTP 200, 46 layer-name cells. Sample printed value:
`S0_Svalbard_Stedsnavn`. `pda methods` is not applicable: layer names,
not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/npigis_source_proof.json`.

## NVE GIS 2 source

`pda ingest --source nve2gis` is another replaceable adapter. It lists
printed name+type services on the official NVE gis2 ArcGIS REST
mapservice catalog `https://gis2.nve.no/arcgis/rest/services/mapservice?f=json`,
capped at 10. The folder name `mapservice` is printed on the root
services catalog. Folders and entries with no name or type are skipped.
Dataset ids are the printed last path segment of `name` so `AlphaBeta`
stays distinct from `NGUFjellskred`. `access_path` keeps the printed
name, printed type, and the catalog `f=json` query. License stays null:
the catalog prints no license URL. Publisher stays null. This is not
NVE Magasinstatistikk (`--source nve`) and not NVE GIS
(`--source nvegis`).

```bash
pda ingest --source nve2gis --db data/registry.sqlite --limit 10
pda search AlphaBeta --db data/registry.sqlite
pda fetch --dataset nve2gis:AlphaBeta --db data/registry.sqlite
```

`pda fetch` GETs the stored service URL. Observation values are copied
from printed JSON `name` when present, otherwise `mapName`, `title`, or
`id`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 8 printed services (catalog prints 8 name+type
rows; cap 10 copies all 8). Live search `NGUFjellskred` returns
`nve2gis:NGUFjellskred`. Live fetch GETs
`https://gis2.nve.no/arcgis/rest/services/mapservice/AlphaBeta/MapServer?f=json`
HTTP 200, 4 layer-name cells. Sample printed value: `Utlopspunkt`.
`pda methods` is not applicable: layer names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nve2gis_source_proof.json`.

## Norsk Polarinstitutt Temadata GIS source

`pda ingest --source npitema` is another replaceable adapter. It lists
printed MapServer services on the official Norsk Polarinstitutt ArcGIS
REST Temadata catalog
`https://geodata.npolar.no/arcgis/rest/services/Temadata?f=json`,
capped at 10. The folder name `Temadata` is printed on the root
services catalog. Empty names and empty types are skipped. Dataset ids
are the printed last path segment of `name` so
`/F_Biogeographic_Zones_Svalbard/MapServer` stays distinct from
`/F_Reinsdyrhabitat/MapServer`. `access_path` is the printed name plus
type plus the catalog's `f=json` query. License stays null: the catalog
prints no license URL. Publisher stays null. This is not the NPI Open
Data API (`--source npolar`), not NPI Basisdata GIS (`--source npigis`,
now on main after PR 148), not NVE GIS (`--source nvegis`), not NVE GIS 2
(`--source nve2gis`, now on main after PR 150), and not Kartverket
Høydedata GIS (`--source hoydegis`).

```bash
pda ingest --source npitema --db data/registry.sqlite --limit 10
pda search Reinsdyrhabitat --db data/registry.sqlite
pda fetch --dataset npitema:F_Biogeographic_Zones_Svalbard --db data/registry.sqlite
```

`pda fetch` GETs the stored MapServer URL. Observation values are copied
from printed JSON `name` when present, otherwise `mapName`, `title`, or
`id`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 10 printed MapServer services (catalog prints
fauna, geology, and habitat services for Svalbard; cap 10). Live
search `Reinsdyrhabitat` returns `npitema:F_Reinsdyrhabitat`. Live
fetch GETs
`https://geodata.npolar.no/arcgis/rest/services/Temadata/F_Biogeographic_Zones_Svalbard/MapServer?f=json`
HTTP 200, 1 layer-name cell. Sample printed value:
`Biogeografiske soner`. `pda methods` is not applicable: layer names,
not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/npitema_source_proof.json`.

## NVE Mapservices source

`pda ingest --source nvemap` is another replaceable adapter. It lists
printed name+type services on the official NVE ArcGIS REST Mapservices
catalog `https://gis3.nve.no/map/rest/services/Mapservices?f=json`,
capped at 10. The folder name `Mapservices` is printed on the root
services catalog. Folders and entries with no name or type are skipped.
Dataset ids are the printed last path segment of `name` so
`Administrasjon2` stays distinct from `Administrasjon`. `access_path`
keeps the printed name, printed type, and the catalog `f=json` query.
License stays null: the catalog prints no license URL. Publisher stays
null. This is not NVE Magasinstatistikk (`--source nve`), not NVE GIS
(`--source nvegis`), and not NVE GIS 2 (`--source nve2gis`).

```bash
pda ingest --source nvemap --db data/registry.sqlite --limit 10
pda search Administrasjon2 --db data/registry.sqlite
pda fetch --dataset nvemap:Administrasjon2 --db data/registry.sqlite
```

`pda fetch` GETs the stored service URL. Observation values are copied
from printed JSON `name` when present, otherwise `mapName`, `title`, or
`id`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 10 printed services (catalog prints 64
name+type rows; cap 10 copies the first 10). Live search
`Avrenning9120` returns `nvemap:Avrenning9120`. Live fetch GETs
`https://gis3.nve.no/map/rest/services/Mapservices/Administrasjon2/MapServer?f=json`
HTTP 200, 13 layer-name cells. Sample printed value: `NVE Region`.
`pda methods` is not applicable: layer names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nvemap_source_proof.json`.

## Norsk Polarinstitutt ArcticSDI GIS source

`pda ingest --source arcticsdi` is another replaceable adapter. It lists
printed MapServer services on the official Norsk Polarinstitutt ArcGIS
REST ArcticSDI catalog
`https://geodata.npolar.no/arcgis/rest/services/ArcticSDI?f=json`,
capped at 10. The folder name `ArcticSDI` is printed on the root
services catalog. Empty names and empty types are skipped. Dataset ids
are the printed last path segment of `name` so
`/ArcticSDI_NO_JAN/MapServer` stays distinct from
`/ArcticSDI_NO_SVA/MapServer`. `access_path` is the printed name plus
type plus the catalog's `f=json` query. License stays null: the catalog
prints no license URL. Publisher stays null. This is not the NPI Open
Data API (`--source npolar`), not NPI Basisdata GIS (`--source npigis`),
not NPI Temadata GIS (`--source npitema`, now on main after PR 151),
and not NVE Mapservices (`--source nvemap`, now on main after PR 152).

```bash
pda ingest --source arcticsdi --db data/registry.sqlite --limit 10
pda search ArcticSDI_NO_SVA --db data/registry.sqlite
pda fetch --dataset arcticsdi:ArcticSDI_NO_JAN --db data/registry.sqlite
```

`pda fetch` GETs the stored MapServer URL. Observation values are copied
from printed JSON `name` when present, otherwise `mapName`, `title`, or
`id`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 2 printed MapServer services (catalog prints
Jan Mayen and Svalbard ArcticSDI services; cap 10 copies both). Live
search `ArcticSDI_NO_SVA` returns `arcticsdi:ArcticSDI_NO_SVA`. Live
fetch GETs
`https://geodata.npolar.no/arcgis/rest/services/ArcticSDI/ArcticSDI_NO_JAN/MapServer?f=json`
HTTP 200, 13 layer-name cells. Sample printed value:
`GeographicalNames`. `pda methods` is not applicable: layer names,
not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/arcticsdi_source_proof.json`.

## Fiskeridirektoratet GIS source

`pda ingest --source fiskerigis` is another replaceable adapter. It lists
printed name+type services on the official Fiskeridirektoratet ArcGIS REST
catalog `https://gis.fiskeridir.no/arcgis/rest/services?f=json`, capped at
10. Folders and entries with no name or type are skipped. Dataset ids are
the printed last path segment of `name` so `AIS_density_Norge_2016` stays
distinct from `AIS_Route_Density_2020`. `access_path` keeps the printed
name, printed type, and the catalog `f=json` query. License stays null:
the catalog prints no license URL. Publisher stays null. This is not
Fartøyregisteret (`--source fiskeridir`), not Kjøperregisteret
(`--source buyer`), not NYTEK (`--source nytek`), not Akvakulturregister
(`--source aqua`), not NVE Mapservices (`--source nvemap`), and not Norsk
Polarinstitutt ArcticSDI (`--source arcticsdi`).

```bash
pda ingest --source fiskerigis --db data/registry.sqlite --limit 10
pda search AIS_density_Norge_2016 --db data/registry.sqlite
pda fetch --dataset fiskerigis:AIS_density_Norge_2016 --db data/registry.sqlite
```

`pda fetch` GETs the stored service URL. Observation values are copied
from printed JSON `name` when present, otherwise `mapName`, `title`, or
`id`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 10 printed services (catalog prints 22 name+type
MapServer rows; cap 10 copies the first 10). Live search
`AIS_density_Norge_2016` returns `fiskerigis:AIS_density_Norge_2016`.
Live fetch GETs
`https://gis.fiskeridir.no/arcgis/rest/services/AIS_density_Norge_2016/MapServer?f=json`
HTTP 200, 1 layer-name cell. Sample printed value: `AIS density Norge 2016`.
`pda methods` is not applicable: layer names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/fiskerigis_source_proof.json`.

## Norsk Polarinstitutt Basisdata Intern GIS source

`pda ingest --source npiintern` is another replaceable adapter. It lists
printed MapServer services on the official Norsk Polarinstitutt ArcGIS
REST Basisdata_Intern catalog
`https://geodata.npolar.no/arcgis/rest/services/Basisdata_Intern?f=json`,
capped at 10. The folder name `Basisdata_Intern` is printed on the root
services catalog. Empty names and empty types are skipped. Dataset ids
are the printed last path segment of `name` so
`/NP_Antarktis_WMTS_3031/MapServer` stays distinct from
`/NP_Lokalstyret_WMS_25833/MapServer`. `access_path` is the printed name
plus type plus the catalog's `f=json` query. License stays null: the
catalog prints no license URL. Publisher stays null. This is not the
NPI Open Data API (`--source npolar`), not NPI Basisdata GIS
(`--source npigis`), not NPI Temadata GIS (`--source npitema`), not NPI
ArcticSDI GIS (`--source arcticsdi`, now on main after PR 153), not NVE
Mapservices (`--source nvemap`), and not Fiskeridirektoratet GIS
(`--source fiskerigis`, now on main after PR 154).

```bash
pda ingest --source npiintern --db data/registry.sqlite --limit 10
pda search NP_Lokalstyret_WMS_25833 --db data/registry.sqlite
pda fetch --dataset npiintern:NP_Antarktis_WMTS_3031 --db data/registry.sqlite
```

`pda fetch` GETs the stored MapServer URL. Observation values are copied
from printed JSON `name` when present, otherwise `mapName`, `title`, or
`id`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 10 printed MapServer services (catalog prints
24; cap 10 copies the first 10 in document order). Live search
`NP_Lokalstyret_WMS_25833` returns `npiintern:NP_Lokalstyret_WMS_25833`.
Live fetch GETs
`https://geodata.npolar.no/arcgis/rest/services/Basisdata_Intern/NP_Antarktis_WMTS_3031/MapServer?f=json`
HTTP 200, 20 layer-name cells. Sample printed value: `Stedsnavn_DML`.
`pda methods` is not applicable: layer names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/npiintern_source_proof.json`.

## SSB PxWebApi 2 source

`pda ingest --source ssbv2` is another replaceable adapter. It lists
printed tables on the official Statistisk sentralbyrå PxWebApi 2 catalog
`https://data.ssb.no/api/pxwebapi/v2/tables`, capped at 10. Dataset ids
are the printed table `id`. `access_path` is the printed `data` href
(`outputFormat=json-stat2`). License stays null: the catalog prints no
license URL. Publisher is the printed `source` field. This is not the
SSB PxWeb v0 Statbank (`--source ssb`).

```bash
pda ingest --source ssbv2 --db data/registry.sqlite --limit 10
pda search 13760 --db data/registry.sqlite
pda fetch --dataset ssbv2:13760 --db data/registry.sqlite
```

`pda fetch` GETs the stored JSON-stat2 data URL. Observation values are
copied from the printed json-stat `value` array with dimension labels.
License stays null.

Live ingest 2026-08-28: 10 printed tables (catalog page prints 20; cap 10
copies the first 10 in document order). Live search `13760` returns
`ssbv2:13760`. Live fetch GETs
`https://data.ssb.no/api/pxwebapi/v2/tables/13760/data?lang=no&outputFormat=json-stat2`
HTTP 200, 12 json-stat cells. Sample printed value: `3067`.
`pda methods` is not a two-period series: the printed default data GET
has one time code (`2026M07`). It printed
`no derived yoy_growth values to chart`. methods/ was not edited.
Proof is `data/ssbv2_source_proof.json`.

## SSB Klass leftover SSB-seksjoner

`pda ingest --source ssbsec` is another replaceable adapter. It lists
the leftover collection GET `/api/klass/v1/ssbsections` named in the
official Statistisk sentralbyrå Klass OpenAPI
`https://data.ssb.no/api/klass/v3/api-docs`. The live catalog
`https://data.ssb.no/api/klass/v1/ssbsections` prints that path on
`_links.self.href`. Dataset id is the printed last path segment
`ssbsections`. Printed member `id` fields are null and are not copied.
License stays null. Publisher stays null. This is not the Klass version
fetch and not PxWebApi 2 (`--source ssbv2`).

```bash
pda ingest --source ssbsec --db data/registry.sqlite --limit 10
pda search ssbsections --db data/registry.sqlite
pda fetch --dataset ssbsec:ssbsections --db data/registry.sqlite
```

`pda fetch` GETs the stored ssbsections URL. Observation values are
copied from printed section `name` scalars. Null `id` fields are not
copied. License stays null. Publisher stays null.

Live ingest 2026-08-28: listed 1, inserted 1 (catalog prints one
collection path; 24 section names live on that GET). Live search
`ssbsections` returns `ssbsec:ssbsections`. Live fetch GETs
`https://data.ssb.no/api/klass/v1/ssbsections` HTTP 200, 24 name cells.
Sample printed value: `210 - Seksjon for nasjonalregnskap`.
`pda methods` is not applicable: section names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/ssbsec_source_proof.json`.

## Riksantikvaren leftover GIS source

`pda ingest --source ragis` is another replaceable adapter. It lists printed
leftover name+type services on the official Riksantikvaren MABYGIS ArcGIS
REST catalog
`https://kart.ra.no/arcgis/rest/services/MABYGIS?f=json`,
capped at 10. The folder name `MABYGIS` is printed on the root services
catalog. Empty names and empty types are skipped. Printed `admin` is
skipped because live GET `/MABYGIS/admin/MapServer?f=json` is HTTP 403.
Printed `MABYGIS_rest_ro` is skipped because that FeatureServer is
already `--source riksantikvaren`. Dataset ids are the printed last path
segment of `name`. `access_path` is the printed name plus first printed
type plus the catalog's `f=json` query. License stays null: the catalog
prints no license URL. Publisher stays null. This is not Riksantikvaren
MABYGIS FeatureServer layers (`--source riksantikvaren`, now on main).

```bash
pda ingest --source ragis --db data/registry.sqlite --limit 10
pda search MABYGIS_Askeladden --db data/registry.sqlite
pda fetch --dataset ragis:MABYGIS_Askeladden --db data/registry.sqlite
```

`pda fetch` GETs the stored FeatureServer URL. Observation values are
copied from printed JSON `name` when present, otherwise `mapName`,
`title`, or `id`. License stays null. Publisher stays null.

Live ingest 2026-08-28: 1 leftover service (catalog prints 5 name+type
services; `admin` is HTTP 403; `MABYGIS_rest_ro` is already
`--source riksantikvaren`; cap 10). Live search `MABYGIS_Askeladden`
returns `ragis:MABYGIS_Askeladden`. Live fetch GETs
`https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_Askeladden/FeatureServer?f=json`
HTTP 200, 1 layer-name cell. Sample printed value: `Dispensasjoner`.
`pda methods` is not applicable: a layer name, not a numeric time series.
Proof is `data/ragis_source_proof.json`.

## NIBIO WMS-tjenester source

`pda ingest --source nibiowms` is another replaceable adapter. It lists
printed GetCapabilities hrefs on leftover official NIBIO WMS pages
under `https://nibio.no/tjenester/wms-tjenester`, capped at 10.
Child pages under `/tjenester/wms-tjenester/` are walked. Attachment
links and the gårdskart page (no cgi-bin GetCapabilities) are skipped.
GetCapabilities bodies that are HTML MapServer errors are skipped.
Dataset ids are the printed last cgi-bin path segment so `ok_raster`
stays distinct from `artsdata`. `access_path` is the GetCapabilities
URL as printed. License stays null. Publisher stays null. This is not
NIBIO IPM weather (`--source nibio`).

```bash
pda ingest --source nibiowms --db data/registry.sqlite --limit 10
pda search ok_raster --db data/registry.sqlite
pda fetch --dataset nibiowms:ok_raster --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text. Observation
values are copied from printed WMS `Layer`/`Name` text. A printed
`Title` sibling stays as a dimension. License stays null. Publisher
stays null.

Live ingest 2026-08-28: 10 printed GetCapabilities services (11 live
XML services after skipping HTML; cap 10 copies the first 10 in
document order). Live search `ok_raster` returns `nibiowms:ok_raster`.
Live fetch GETs
`https://wms.nibio.no/cgi-bin/ok_raster?request=getcapabilities&service=wms`
HTTP 200, 4 Layer Name cells. Sample printed value: `ok_raster`.
`pda methods` is not applicable: layer names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nibiowms_source_proof.json`.

## Riksantikvaren leftover WMS source

`pda ingest --source rawms` is another replaceable adapter. It lists the
two printed leftover Riksantikvaren WMS GetCapabilities documents on
`kart.ra.no/wms`, capped at 10. A document that is not WMS XML is
skipped. Dataset ids are the printed last path segment so
`kulturminner2` stays distinct from `kulturmiljoer`. `access_path` is
the GetCapabilities URL as printed. License stays null. Publisher stays
null. This is not Riksantikvaren MABYGIS FeatureServer layers
(`--source riksantikvaren`) and not leftover MABYGIS REST
(`--source ragis`).

```bash
pda ingest --source rawms --db data/registry.sqlite --limit 10
pda search kulturminner2 --db data/registry.sqlite
pda fetch --dataset rawms:kulturminner2 --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text. Observation
values are copied from printed WMS `Layer`/`Name` text. A printed
`Title` sibling stays as a dimension. License stays null. Publisher
stays null.

Live ingest 2026-08-28: 2 printed GetCapabilities documents, both XML
200. Live search `kulturminner2` returns `rawms:kulturminner2`. Live
fetch GETs
`https://kart.ra.no/wms/kulturminner2?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities`
HTTP 200, 6 Layer Name cells. Sample printed value: `Kulturminner`.
`pda methods` is not applicable: layer names, not a numeric time series.
Proof is `data/rawms_source_proof.json`.

## Kystverket leftover WMS source

`pda ingest --source kystwms` is another replaceable adapter. It lists the
two printed leftover Kystverket GetCapabilities documents
`https://services.kystverket.no/wms.ashx?service=WMS&request=GetCapabilities`
and
`https://services.kystverket.no/wfs.ashx?service=WFS&request=GetCapabilities`,
capped at 10. Those URLs are printed on Geonorge as Kystverkets WMS
(`768a3ca6-0655-45d5-8cd5-76bd7e0e59d2`) and Kystverkets WFS
(`de223e4c-e708-4c15-9afb-f8cedd3cd3ba`). A document that is not WMS
or WFS XML is skipped. Dataset ids are the printed last path segment so
`wms.ashx` stays distinct from `wfs.ashx`. `access_path` is the
GetCapabilities URL as printed. License stays null. Publisher stays
null. This is not Kystdatahuset (`--source kystverket`), not Kartverket
Havnedata (`--source havnedata`), and not Kystverket navigasjonsvarsler
(`--source navwarnings`).

```bash
pda ingest --source kystwms --db data/registry.sqlite --limit 10
pda search wms.ashx --db data/registry.sqlite
pda fetch --dataset kystwms:wms.ashx --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text. Observation
values are copied from printed WMS `Layer`/`Name` text or WFS
`FeatureType`/`Name` text. A printed `Title` sibling stays as a
dimension. License stays null. Publisher stays null.

Live ingest 2026-08-28: 2 printed GetCapabilities documents, both XML
200. Live search `wms.ashx` returns `kystwms:wms.ashx`. Live fetch GETs
`https://services.kystverket.no/wms.ashx?service=WMS&request=GetCapabilities`
HTTP 200, 57 Layer Name cells. Sample printed value: `MS`.
`pda methods` is not applicable: layer names, not a numeric time series.
Proof is `data/kystwms_source_proof.json`.

## NVE RegObs KDV source

`pda ingest --source regobs` is another replaceable adapter. It lists
printed `KdvRepositories` keys on the official NVE RegObs KdvElements GET
`https://api.regobs.no/v5/KdvElements`, capped at 10. That path is an
untemplated collection GET in the official swagger
`https://api.regobs.no/v5/swagger/docs/V5`. Empty keys and non-list
repositories are skipped. Dataset ids are those printed keys so
`Dirt_DangerSignKDV` stays distinct from `Dirt_ActivityInfluencedKDV`.
Native URIs append that printed key as a fragment so the registry can
store each repository. `access_path` is the printed KdvElements URL.
License stays null: the
catalog prints no license URL. Publisher stays null. Account paths that
print HTTP 401 stay unused. This is not NVE Magasinstatistikk
(`--source nve`) and not SSB PxWebApi 2 (`--source ssbv2`).

```bash
pda ingest --source regobs --db data/registry.sqlite --limit 10
pda search Dirt_DangerSignKDV --db data/registry.sqlite
pda fetch --dataset regobs:Dirt_DangerSignKDV --db data/registry.sqlite
```

`pda fetch` GETs the stored KdvElements URL. Observation values are
copied from printed `Name` when present, otherwise `Id`, for that one
repository. License stays null. Publisher stays null.

Live ingest 2026-08-28: 10 printed repositories (catalog prints 73; cap
10 copies the first 10 in document order). Live search
`Dirt_DangerSignKDV` returns `regobs:Dirt_DangerSignKDV`. Live fetch GETs
`https://api.regobs.no/v5/KdvElements` HTTP 200, 16 Name cells. Sample
printed value: `Ikke gitt`. `pda methods` is not applicable: code-list
names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/regobs_source_proof.json`.

## MET Sigmets source

`pda ingest --source sigmets` is another replaceable adapter. It lists
printed collection GET paths on the official MET Sigmets swagger
`https://api.met.no/weatherapi/sigmets/2.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. The root product path has no last-segment id so
it is skipped. Dataset ids are the last printed path segment.
`access_path` is the swagger origin + printed `basePath` + path.
License is the printed swagger CC BY 4.0 URL. Publisher stays null.
This is not Metalerts (`--source met`), not MET Sigcharts
(`--source sigcharts`), not MET Volcanicashforecast
(`--source volcanicashforecast`), and not MET Aviationforecast.

```bash
pda ingest --source sigmets --db data/registry.sqlite --limit 10
pda search airmets --db data/registry.sqlite
pda fetch --dataset sigmets:features --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed FeatureCollection `id` on `/features`, or from printed string
arrays on `/values`. License is the printed swagger CC BY 4.0 URL.
Publisher stays null: the spec does not print a publisher.
`/changelog` prints RSS and `/healthz` prints plain text, so they stay
unused for fetch. `/available` prints XML. `/airmets`, `/sigmets`, and
`/windshear` print text/plain.

Live ingest 2026-08-28: 8 printed untemplated GET paths (catalog prints
8 paths with a last-segment id and no required query parameter, cap 10).
Live search `FeatureCollection` returns `sigmets:features`. Live fetch
GETs `https://api.met.no/weatherapi/sigmets/2.0/features`
HTTP 200, 3 printed feature-id cells. Sample printed value: `airmets`.
`pda methods` is not applicable: printed feature ids, not a numeric time
series (`no observations matched entity/measure; available=[]`).
Proof is `data/sigmets_source_proof.json`.

## Utdanningsdirektoratet Grep source

`pda ingest --source grep` is another replaceable adapter. It lists
printed collection GET paths on the official Grep swagger
`https://data.udir.no/swagger/docs/201906`, capped at 10. Templated
`{kode}` / `{type}` / `{filter}` / `{format}` paths are skipped. The
swagger path uses `{version}`; that token is replaced with the printed
last segment of the swagger document URL (`201906`). Dataset ids are the
printed last path segment so `aarstrinn` stays distinct from
`dokumenttype`. `access_path` is the swagger origin plus the concrete
path. License is copied from the printed swagger license URL. Publisher
stays null. This is not Nasjonalt skoleregister (`--source udir`), not
Nasjonalt barnehageregister (`--source nbr`), and not SSB PxWebApi 2
(`--source ssbv2`).

```bash
pda ingest --source grep --db data/registry.sqlite --limit 10
pda search aarstrinn --db data/registry.sqlite
pda fetch --dataset grep:aarstrinn --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed `kode` when present, otherwise `id` or `uri`. Nested
`tittel` arrays are not copied. License is copied from the harvested
swagger license URL. Publisher stays null.

Live ingest 2026-08-28: 10 printed collection paths (swagger prints 43
untemplated collection GETs after dropping `{format}`; cap 10 copies the
first 10 in document order). Live search `aarstrinn` returns
`grep:aarstrinn`. Live fetch GETs
`https://data.udir.no/kl06/v201906/aarstrinn` HTTP 200, 18 kode cells.
Sample printed value: `aarstrinn1`. `pda methods` is not applicable:
year-grade codes, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/grep_source_proof.json`.

## Kartverket leftover WMS/WMTS source

`pda ingest --source kvwms` is another replaceable adapter. It lists
the two official leftover Kartverket GetCapabilities documents
`https://wms.geonorge.no/skwms1/wms.topo?service=WMS&request=GetCapabilities`
and
`https://cache.kartverket.no/v1/wmts/1.0.0/WMTSCapabilities.xml`,
capped at 10. Each document is one dataset. Native ids are the printed
last path segment of the service href so `wms.topo` stays distinct from
`wmts`. `access_path` is that GetCapabilities URL. License stays null:
the documents print copyright text, not a license URL. Publisher stays
null. This is not Geonorge Kartkatalog (`--source geonorge`), not
Kartverket Høydedata (`--source hoydedata`), not Kartverket Høydedata
GIS (`--source hoydegis`), not Kartverket OGC API Coverages
(`--source ogccoverages`), not Kartverket Transformering
(`--source transformering`), and not NIBIO WMS-tjenester
(`--source nibiowms`, now on main after PR 160).

```bash
pda ingest --source kvwms --db data/registry.sqlite --limit 10
pda search norgeskart --db data/registry.sqlite
pda fetch --dataset kvwms:wms.topo --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL. Observation values are
copied from printed WMS Layer `Name` or WMTS Layer `Identifier`. License
stays null. Publisher stays null.

Live ingest 2026-08-28: 2 leftover GetCapabilities documents. Live search
`norgeskart` returns `kvwms:wms.topo`. Live fetch GETs
`https://wms.geonorge.no/skwms1/wms.topo?service=WMS&request=GetCapabilities`
HTTP 200, 227 printed layer-name cells. Sample printed value: `topo`.
`pda methods` is not applicable: layer names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/kvwms_source_proof.json`.

## MET Aviationforecast source

`pda ingest --source aviationforecast` is another replaceable adapter. It lists
printed collection GET paths on the official MET Aviationforecast swagger
`https://api.met.no/weatherapi/aviationforecast/2.0/swagger`, capped at 10.
Templated `{format}` paths and GET operations that print required query
parameters are skipped. Forecast paths `/aw` and `/iga` print required
`icao` or `wmoheader`, so they are not listed. Dataset ids are the last
printed path segment. `access_path` is the swagger origin + printed
`basePath` + path. License is the printed swagger CC BY 4.0 URL.
Publisher stays null. This is not Metalerts (`--source met`), not
Locationforecast (`--source locationforecast`), not Tafmetar
(`--source tafmetar`), not Sigmets, and not Udir Grep.

```bash
pda ingest --source aviationforecast --db data/registry.sqlite --limit 10
pda search locations --db data/registry.sqlite
pda fetch --dataset aviationforecast:locations --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed GeoJSON feature `name` when present, otherwise the printed
Feature `id`. License is the printed swagger CC BY 4.0 URL. Publisher
stays null: the spec does not print a publisher.

Live ingest 2026-08-28: 6 printed untemplated GET paths (catalog prints
6 paths with a last-segment id and no required query parameter, cap 10).
Live search `locations` returns `aviationforecast:locations`. Live fetch GETs
`https://api.met.no/weatherapi/aviationforecast/2.0/locations` HTTP 200, 8
location-name cells. Sample printed value: `BERGEN/FLESLAND`.
`pda methods` is not applicable: GeoJSON ICAO names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/aviationforecast_source_proof.json`.

## NVE Vannkraftdatabase source

`pda ingest --source vannkraft` is another replaceable adapter. It lists
printed untemplated collection GET paths on the official NVE
Vannkraftdatabase documentation
`https://api.nve.no/doc/vannkraftdatabase/`, capped at 10. Templated
paths are skipped. Dataset ids are the printed last path segment so
`GetHydroPowerPlantsInOperation` stays distinct from
`GetHydroPowerPlants`. `access_path` joins each printed path onto the
printed `https://` base `api.nve.no/web/Powerplant`. License stays null:
the documentation prints no license URL. Publisher stays null. This is
not Magasinstatistikk (`--source nve`), not NVE GIS leftovers, and not
RegObs.

```bash
pda ingest --source vannkraft --db data/registry.sqlite --limit 10
pda search vannkraftverk --db data/registry.sqlite
pda fetch --dataset vannkraft:GetHydroPowerPlantsInOperation --db data/registry.sqlite
```

`pda fetch` GETs the stored Powerplant URL. Observation values are
copied from printed `Navn` scalars. Other scalars stay as dimensions.
Nested owner and concession objects are not copied. License stays null.
Publisher stays null.

Live ingest 2026-08-28: 2 printed untemplated GET paths (docs print
only those two). Live search `vannkraftverk` returns
`vannkraft:GetHydroPowerPlantsInOperation`. Live fetch GETs
`https://api.nve.no/web/Powerplant/GetHydroPowerPlantsInOperation`
HTTP 200, 1862 plant-name cells. Sample printed value: `Adamselv`.
`pda methods` is not applicable: plant names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/vannkraft_source_proof.json`.

## NVE Vindkraftdatabase source

`pda ingest --source vindkraft` is another replaceable adapter. It lists
printed untemplated collection GET paths on the official NVE
Vindkraftdatabase documentation
`https://api.nve.no/doc/vindkraftdatabase/`, capped at 10. Templated
paths are skipped. Dataset ids are the printed last path segment so
`GetWindPowerPlantsInOperation` stays distinct from
`GetWindPowerPlants`. `access_path` joins each printed path onto the
printed `https://` base `api.nve.no/web/WindPowerplant`. License stays
null: the documentation prints no license URL. Publisher stays null.
This is not Magasinstatistikk (`--source nve`), not Vannkraftdatabase
(`--source vannkraft`), and not RegObs (`--source regobs`).

```bash
pda ingest --source vindkraft --db data/registry.sqlite --limit 10
pda search "Henter alle" --db data/registry.sqlite
pda fetch --dataset vindkraft:GetWindPowerPlants --db data/registry.sqlite
```

`pda fetch` GETs the stored WindPowerplant URL. Observation values are
copied from printed `Navn` scalars. Other scalars stay as dimensions.
Nested objects are not copied. License stays null. Publisher stays null.

Live ingest 2026-08-28: 2 printed untemplated GET paths (catalog prints
2; cap 10). Live search `Henter alle` returns
`vindkraft:GetWindPowerPlants`. Live fetch GETs
`https://api.nve.no/web/WindPowerplant/GetWindPowerPlants` HTTP 200, 72
Navn cells. Sample printed value: `Bessakerfjellet`. `pda methods` is
not applicable: plant names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/vindkraft_source_proof.json`.

## Statens vegvesen leftover OGC source

`pda ingest --source vegogc` is another replaceable adapter. It lists
printed GetCapabilities hrefs on the official leftover Statens vegvesen
OGC kartlag page
`https://www.vegvesen.no/fag/teknologi/apne-data/et-utvalg-apne-data/ogc-karttjenester/kartlag/`,
capped at 10. It keeps host `ogckart-sn1.atlas.vegvesen.no` with
`request=GetCapabilities` and skips `vegvar.atlas.vegvesen.no` web-map
links. GetCapabilities bodies that are HTML or not WMS/WFS Capabilities
XML are skipped. Dataset ids are the printed path segments after the
host joined with `_` so `vegvar_1_0_ows` stays distinct from
`vegvar_1_0_wfs`. `access_path` is the GetCapabilities URL as printed.
License stays null. Publisher stays null. This is not the Vegvesen CKAN
catalog (`--source vegvesen`) and not Kartverket leftover WMS/WMTS
(`--source kvwms`, now on main after PR 163). It does not scrape
`https://dataut.vegvesen.no/dataset/ogc-karttjenester`. MET Aviationforecast
(`--source aviationforecast`, now on main after PR 166), NVE
Vannkraftdatabase (`--source vannkraft`, now on main after PR 164), and
NVE Vindkraftdatabase (`--source vindkraft`, now on main after PR 169)
stay unused.

```bash
pda ingest --source vegogc --db data/registry.sqlite --limit 10
pda search vegvar_1_0_ows --db data/registry.sqlite
pda fetch --dataset vegogc:vegvar_1_0_ows --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text. Observation
values are copied from printed WMS `Layer`/`Name` text or WFS
`FeatureType`/`Name` text. A printed `Title` sibling stays as a
dimension. License stays null. Publisher stays null.

Live ingest 2026-08-28: 10 printed GetCapabilities services (kartlag
prints 10; all 10 return WMS or WFS Capabilities XML 200). Live search
`vegvar_1_0_ows` returns `vegogc:vegvar_1_0_ows`. Live fetch GETs
`https://ogckart-sn1.atlas.vegvesen.no/vegvar_1_0/ows?service=wms&request=GetCapabilities`
HTTP 200, 2 Layer Name cells. Sample printed value: `tunnel_segments`.
`pda methods` is not applicable: layer names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/vegogc_source_proof.json`.

`pda ingest --source elcert` is another replaceable adapter. It lists
printed untemplated collection GET paths on the official NVE
Elsertifikater documentation `https://api.nve.no/doc/elsertifikater/`,
capped at 10. Templated paths are skipped. Dataset ids are the printed
last path segment so `GetApplications` stays distinct from
`GetSummaryValuesPerQuarter`. `access_path` joins each printed path onto
the printed `https://` base `api.nve.no/web/ElCert`. License stays null.
Publisher stays null. This is not Magasinstatistikk (`--source nve`),
not RegObs (`--source regobs`), not Udir Grep (`--source grep`), not
MET Aviationforecast (`--source aviationforecast`), and not NVE
Vannkraftdatabase (`--source vannkraft`) or Vindkraftdatabase
(`--source vindkraft`).

```bash
pda ingest --source elcert --db data/registry.sqlite --limit 10
pda search elsertifikat --db data/registry.sqlite
pda fetch --dataset elcert:GetApplications --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are copied
from printed JSON `KraftverksNavn` when present, otherwise `Status` or
`TypeAnlegg`. Nested objects are not copied. License stays null.
Publisher stays null.

Live ingest 2026-08-28: 3 printed untemplated GET paths (docs print
only those three, cap 10). Live search `elsertifikat` returns
`elcert:GetApplications`. Live fetch GETs
`https://api.nve.no/web/ElCert/GetApplications` HTTP 200, 914
plant-name cells. Sample printed value: `Myrbekk`. `pda methods` is
not applicable: plant names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/elcert_source_proof.json`.

## Landbruksdirektoratet leftover WMS source

`pda ingest --source ldirwms` is another replaceable adapter. It lists printed
OGC:WMS Type=service rows on the official Geonorge Kartkatalog search
`https://kartkatalog.geonorge.no/api/search?text=Landbruksdirektoratet`,
capped at 10. Other organizations, WFS, downloads, and servicelayers are
skipped. cgi-bin names already ingested by leftover NIBIO WMS are skipped.
GetCapabilities bodies that are not WMS XML are skipped. Dataset ids are
the printed last cgi-bin path segment so `vernskog2` stays distinct from
`reindrift`. `access_path` is the printed `DistributionUrl`. License stays
null: the catalog prints no license URL. Publisher stays null. This is not
Geonorge Kartkatalog REST (`--source geonorge`), not NIBIO IPM weather
(`--source nibio`), and not leftover NIBIO WMS (`--source nibiowms`, now
on main after PR 160).

```bash
pda ingest --source ldirwms --db data/registry.sqlite --limit 10
pda search vernskog --db data/registry.sqlite
pda fetch --dataset ldirwms:vernskog2 --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL. Observation values are
copied from printed WMS `Layer`/`Name` text. A sibling `Title` stays as a
dimension. License stays null. Publisher stays null.

Live ingest 2026-08-28: 4 leftover WMS services (search prints 72 rows;
27 are OGC:WMS; cap 10 copies the 4 leftover Type=service cgi-bin names
after skipping servicelayers, WFS, downloads, and nibiowms cgi-bin
names). Live search `vernskog` returns `ldirwms:vernskog2`. Live fetch
GETs
`https://wms.nibio.no/cgi-bin/vernskog2?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities`
HTTP 200, 9 Layer Name cells. Sample printed value: `VERNSKOG2`.
`pda methods` is not applicable: layer names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/ldirwms_source_proof.json`.

`pda ingest --source frivillig` is another replaceable adapter. It lists
printed collection GET paths on the official Frivillighetsregisteret
OpenAPI
`https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/openapi.json`,
capped at 10. Only `/frivillighetsregisteret/` paths are copied.
Templated `{organisasjonsnummer}` paths, GET operations that print
required parameters, and the printed CSV totalbestand path are skipped.
Dataset ids are the last printed path segment. `access_path` is the
printed `servers[0].url` plus the path. License is the printed NLOD URL.
Publisher stays null. This is not Enhetsregisteret (`--source brreg`)
and not Regnskapsregisteret (`--source regnskap`).

```bash
pda ingest --source frivillig --db data/registry.sqlite --limit 10
pda search ICNPO --db data/registry.sqlite
pda fetch --dataset frivillig:icnpo-kategorier --db data/registry.sqlite
```

`pda fetch` GETs the stored collection URL. Observation values are
copied from printed `navn` when present. Other scalars stay as
dimensions. Nested objects and `_links` are not copied.

Live ingest 2026-08-28: 3 printed untemplated JSON collection GET paths
(catalog prints those three under `/frivillighetsregisteret/`, cap 10).
Live search `ICNPO` returns `frivillig:icnpo-kategorier`. Live fetch GETs
`https://data.brreg.no/frivillighetsregisteret/api/icnpo-kategorier`
HTTP 200, 46 category-name cells. Sample printed value:
`Kultur- og rekreasjon`.
`pda methods` is not applicable: category names, not a numeric
time series (`no observations matched entity/measure; available=[]`).
Proof is `data/frivillig_source_proof.json`.

## Sandnes kommune Medvirkning API source

`pda ingest --source sandnes` is another replaceable adapter. It lists the
one printed GraphQL route on the official Sandnes kommune API docs
`https://medvirkning.sandnes.kommune.no/api/docs`. That page prints
`URL/api` as the POST request route. The origin is copied from the docs
page. Dataset id is `api`. `access_path` is
`https://medvirkning.sandnes.kommune.no/api`. License stays null.
Publisher stays null. This is not Oslo Statistikkbank (`--source oslo`),
not Trondheim Åpne Data (`--source trondheim`), and not Stavanger
Opencom (`--source opencom`). It does not walk process slugs into extra
dataset ids.

```bash
pda ingest --source sandnes --db data/registry.sqlite --limit 1
pda search Sviland --db data/registry.sqlite
pda fetch --dataset sandnes:api --db data/registry.sqlite
```

`pda fetch` POSTs the GraphiQL `default_query` printed on
`https://medvirkning.sandnes.kommune.no/api/graphiql`. Observation
values are copied from printed participatory-process title texts. Null
translation texts are skipped.

Live ingest 2026-08-28: 1 printed API route. Live search `Sviland`
returns `sandnes:api`. Live fetch POSTs
`https://medvirkning.sandnes.kommune.no/api`
HTTP 200, 4 process-title rows. Sample printed titles: Ny plan for
Sviland, Bedre tverrfaglig innsats, Kommunedelplan for kunst og kultur,
Et nytt hus - for alle i Sandnes.
`pda methods` is not applicable: titles, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/sandnes_source_proof.json`.

## NGU leftover WMS source

`pda ingest --source nguwms` is another replaceable adapter. It lists
printed GetCapabilities URLs on leftover official NGU WMS pages
under `https://www.ngu.no/taxonomy/term/36`, capped at 10.
Printed pager hrefs on that same `taxonomy/term/36` path are followed.
URLs without `request=GetCapabilities`, hosts other than `geo.ngu.no`,
paths outside `/mapserver/`, `/api/features`, `/kart/` viewers, and
GetCapabilities bodies that are HTML or not WMS XML are skipped.
Dataset ids are the printed last `/mapserver/` path segment so
`LosmasserWMS3` stays distinct from `BerggrunnWMS3`. `access_path`
is the GetCapabilities URL as printed. License stays null: the
catalog prints no license URL. Publisher stays null. This is not
NGU OGC Features (`--source ngu`).

```bash
pda ingest --source nguwms --db data/registry.sqlite --limit 10
pda search LosmasserWMS3 --db data/registry.sqlite
pda fetch --dataset nguwms:LosmasserWMS3 --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text, with
`Accept: application/xml, text/xml, */*`. Observation values are
copied from printed WMS `Layer`/`Name` text. A printed `Title`
sibling stays as a dimension. License stays null. Publisher stays
null. `pda methods` is not applicable: layer names, not a numeric
time series
(`no observations matched entity/measure; available=[]`).

Live ingest 2026-08-28: 10 leftover GetCapabilities documents
(page 0 prints 10, all XML 200, cap 10). Live search
`LosmasserWMS3` returns `nguwms:LosmasserWMS3`. Live fetch GETs
`https://geo.ngu.no/mapserver/LosmasserWMS3?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities`
HTTP 200, 170 printed layer-name cells. Sample printed value:
`LosmasserWMS3`. Proof is `data/nguwms_source_proof.json`.

## Kartverket Stormflo source

`pda ingest --source stormflo` is another replaceable adapter. It lists
printed collection GET paths on the official Kartverket Stormflo OpenAPI
`https://stormflo-konsekvens.kartverket.no/openapi.yaml`, capped at 10.
The templated `{kommune}` path is skipped. Dataset ids are the last
printed path segment so `national.json` stays distinct from
`alle_kommuner.json`. `access_path` joins each printed path onto the
printed server `https://stormflo-konsekvens.kartverket.no`. License is
the printed OpenAPI Apache 2.0 URL. Publisher stays null. This is not
Kommuneinfo (`--source kommuneinfo`), not leftover Kartverket WMS
(`--source kvwms`), and not Geonorge Kartkatalog (`--source geonorge`).

```bash
pda ingest --source stormflo --db data/registry.sqlite --limit 10
pda search landet --db data/registry.sqlite
pda fetch --dataset stormflo:national.json --db data/registry.sqlite
```

`pda fetch` GETs the stored JSON URL. Observation values are copied
from printed integer and float fields. Printed scenario keys and year
keys stay as dimensions. License is the printed OpenAPI Apache 2.0 URL.
Publisher stays null: the spec does not print a publisher.

Live ingest 2026-08-28: 2 printed untemplated GET paths (catalog prints
3 paths; `{kommune}` is skipped; cap 10). Live search `landet` returns
`stormflo:national.json`. Live fetch GETs
`https://stormflo-konsekvens.kartverket.no/public/api/v1/national.json`
HTTP 200, 168 numeric cells with years 2025, 2100, and 2150. Sample
printed value: `offentlige_bygg` 1810 for `200ymax` / `2025`.
This fetch is a numeric time series with three periods. `methods/` was
not edited.
Proof is `data/stormflo_source_proof.json`.

## Kystverket leftover WFS source

`pda ingest --source kystwfs` is another replaceable adapter. It lists the
printed leftover Kystverket WFS GetCapabilities document on
`https://services.kystverket.no/wfs.ashx?service=WFS&request=GetCapabilities`,
capped at 10. Geonorge prints that URL on Kystverkets WFS
(`de223e4c-e708-4c15-9afb-f8cedd3cd3ba`). GetCapabilities bodies that
are not WFS XML are skipped. The dataset id is the printed last path
segment `wfs.ashx`. `access_path` is the printed GetCapabilities URL.
License stays null: the capabilities document prints no license URL.
Publisher stays null. This is not Kystdatahuset OpenAPI
(`--source kystverket`), not Kartverket Havnedata
(`--source havnedata`), and not leftover Kystverket WMS
(`--source kystwms`).

```bash
pda ingest --source kystwfs --db data/registry.sqlite --limit 10
pda search Kystverket --db data/registry.sqlite
pda fetch --dataset kystwfs:wfs.ashx --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL. Observation values are
copied from printed WFS `FeatureType`/`Name` text. A sibling `Title`
stays as a dimension. License stays null. Publisher stays null.

Live ingest 2026-08-28: 1 leftover WFS document (Geonorge prints one
OGC:WFS DistributionUrl; live GetCapabilities is WFS XML 200). Live
search `Kystverket` returns `kystwfs:wfs.ashx`. Live fetch GETs
`https://services.kystverket.no/wfs.ashx?service=WFS&request=GetCapabilities`
HTTP 200, 44 FeatureType Name cells. Sample printed value: `layer_611`.
`pda methods` is not applicable: feature type names, not a numeric time
series (`no observations matched entity/measure; available=[]`).
Proof is `data/kystwfs_source_proof.json`.

## Kystverket leftover Navigasjonsinstallasjoner source

`pda ingest --source kystnav` is another replaceable adapter. It lists the
two printed leftover Kystverket Navigasjonsinstallasjoner GetCapabilities
documents
`https://maps.kystverket.cloudgis.no/enterprise/services/PROD/nfs_sistop_ekstern_prod/MapServer/WMSServer?request=GetCapabilities&service=WMS`
and
`https://maps.kystverket.cloudgis.no/enterprise/services/PROD/nfs_sistop_ekstern_prod/MapServer/WFSServer?request=GetCapabilities&service=WFS`,
capped at 10. Those URLs are printed on Geonorge as Navigasjonsinstallasjoner
WMS (`80b7eab8-d5da-4136-8ec6-2002867a2b2b`) and Navigasjonsinstallasjoner WFS
(`73e46cf4-d9f5-4d75-b148-bb5edf888c4a`). A document that is not WMS
or WFS XML is skipped. Dataset ids are the printed last path segment so
`WMSServer` stays distinct from `WFSServer`. `access_path` is the
GetCapabilities URL as printed. License stays null. Publisher stays
null. This is not Kystdatahuset (`--source kystverket`), not Kartverket
Havnedata (`--source havnedata`), not Kystverket navigasjonsvarsler
(`--source navwarnings`), not leftover Kystverket WMS
(`--source kystwms`), and not leftover Kystverket WFS
(`--source kystwfs`).

```bash
pda ingest --source kystnav --db data/registry.sqlite --limit 10
pda search WMSServer --db data/registry.sqlite
pda fetch --dataset kystnav:WMSServer --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text. Observation
values are copied from printed WMS `Layer`/`Name` text or WFS
`FeatureType`/`Name` text. A printed `Title` sibling stays as a
dimension. License stays null. Publisher stays null.

Live ingest 2026-08-28: 2 printed GetCapabilities documents, both XML
200. Live search `WMSServer` returns `kystnav:WMSServer`. Live fetch
GETs
`https://maps.kystverket.cloudgis.no/enterprise/services/PROD/nfs_sistop_ekstern_prod/MapServer/WMSServer?request=GetCapabilities&service=WMS`
HTTP 200, 10 Layer Name cells. Sample printed value: `Skilt6756`.
`pda methods` is not applicable: layer names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/kystnav_source_proof.json`.

## Miljødirektoratet leftover WMS/WFS source

`pda ingest --source mdirwms` is another replaceable adapter. It lists printed
leftover OGC:WMS and OGC:WFS Type=service rows on the official Geonorge
Kartkatalog search
`https://kartkatalog.geonorge.no/api/search?text=Milj%C3%B8direktoratet`,
capped at 10. Other organizations, downloads, and servicelayers are skipped.
ArcGIS WMS wrappers already covered by Miljødirektoratet GIS are skipped.
NIBIO leftover WMS hosts, NGU leftover WMS, and NVE GIS hosts are skipped.
GetCapabilities bodies that are not WMS or WFS XML are skipped. Dataset ids
are the printed service path segment so `industri` stays distinct from
`miljoverdi_hav_wms`. `access_path` is the printed `DistributionUrl`. License
stays null: the catalog prints no license URL. Publisher stays null. This is
not Miljødirektoratet ArcGIS REST (`--source miljogis`), not Vannmiljø
(`--source miljodir`), not leftover NIBIO WMS (`--source nibiowms`), and not
leftover Landbruksdirektoratet WMS (`--source ldirwms`).

```bash
pda ingest --source mdirwms --db data/registry.sqlite --limit 10
pda search Industri --db data/registry.sqlite
pda fetch --dataset mdirwms:industri --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL. Observation values are
copied from printed WMS `Layer`/`Name` text or WFS `FeatureType`/`Name`
text. A sibling `Title` stays as a dimension. License stays null. Publisher
stays null.

Live ingest 2026-08-28: 10 leftover WMS services (search prints 176 rows;
59 are OGC:WMS or OGC:WFS Type=service; cap 10 copies the first ten leftover
live documents after skipping miljogis ArcGIS wrappers, other organizations,
downloads, servicelayers, HTML, 404, 504, and ServiceException bodies). Live
search `Industri` returns `mdirwms:industri`. Live fetch GETs
`https://kart3.miljodirektoratet.no/arcgis/services/industri/MapServer/WMSServer?service=WMS&request=GetCapabilities`
HTTP 200, 2 Layer Name cells. Sample printed value:
`industri_landbasert_overvaaking`. `pda methods` is not applicable: layer
names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/mdirwms_source_proof.json`.

## Bane NOR leftover WMS/WFS source

`pda ingest --source banegis` is another replaceable adapter. It lists the
four printed leftover Bane NOR GetCapabilities documents
`https://wfs.geonorge.no/skwms1/wfs.stoysonerjernbanenett?service=WFS&request=GetCapabilities`,
`https://wms.geonorge.no/skwms1/wms.stoysonerjernbanenett?service=WMS&request=GetCapabilities`,
`https://wfs.geonorge.no/skwms1/wfs.banenettverk?request=GetCapabilities&service=WFS`,
and
`https://wms.geonorge.no/skwms1/wms.banenettverk?request=GetCapabilities&service=WMS`,
capped at 10. Those URLs are printed on Geonorge Kartkatalog search
`https://kartkatalog.geonorge.no/api/search?text=Bane%20NOR` as Type=service
OGC:WFS or OGC:WMS. A document that is not WMS or WFS XML is skipped.
Dataset ids are the printed last path segment so `wms.banenettverk` stays
distinct from `wfs.banenettverk`. `access_path` is the GetCapabilities URL
as printed. License stays null. Publisher stays null. This is not
Kartverket leftover topo WMS/WMTS (`--source kvwms`), not leftover
grunnkart WMS (`--source kvgrunn`), not Statens vegvesen leftover OGC
(`--source vegogc`), and not Geonorge Kartkatalog (`--source geonorge`).
Jernbanedirektoratet search printed no Type=service OGC rows.

```bash
pda ingest --source banegis --db data/registry.sqlite --limit 10
pda search stoysonerjernbanenett --db data/registry.sqlite
pda fetch --dataset banegis:wms.stoysonerjernbanenett --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text. Observation
values are copied from printed WMS `Layer`/`Name` text or WFS
`FeatureType`/`Name` text. A printed `Title` sibling stays as a
dimension. License stays null. Publisher stays null.

Live ingest 2026-08-28: 4 printed GetCapabilities documents, all XML
200. Live search `stoysonerjernbanenett` returns
`banegis:wfs.stoysonerjernbanenett`. Live fetch GETs
`https://wms.geonorge.no/skwms1/wms.stoysonerjernbanenett?service=WMS&request=GetCapabilities`
HTTP 200, 3 Layer Name cells. Sample printed value:
`stoysonerjernbanenett`. `pda methods` is not applicable: layer names,
not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/banegis_source_proof.json`.

## Mattilsynet leftover WMS/WFS source

`pda ingest --source mattilsyn` is another replaceable adapter. It lists printed
leftover OGC:WMS and OGC:WFS Type=service rows on the official Geonorge
Kartkatalog search
`https://kartkatalog.geonorge.no/api/search?text=Mattilsynet&limit=50`,
capped at 10. Other organizations, downloads, servicelayers, and W3C:REST
rows are skipped. Leftover NIBIO WMS hosts, leftover Landbruksdirektoratet
WMS hosts, Miljødirektoratet GIS hosts, and leftover Miljødirektoratet WMS
hosts are skipped. GetCapabilities bodies that are not WMS or WFS XML are
skipped. Dataset ids are the printed service path segment so the leftover
`https://kart.mattilsynet.no/wmscache/service?service=WMS&request=GetCapabilities`
keeps native id `service`. `access_path` is the printed `DistributionUrl`.
License stays null: the catalog prints no license URL. Publisher stays
null. This is not Mattilsynet plantevern JSON (`--source mattilsynet`),
not leftover NIBIO WMS (`--source nibiowms`), not leftover
Landbruksdirektoratet WMS (`--source ldirwms`), not Miljødirektoratet
ArcGIS REST (`--source miljogis`), and not leftover Miljødirektoratet
WMS/WFS (`--source mdirwms`).

```bash
pda ingest --source mattilsyn --db data/registry.sqlite --limit 10
pda search Mattilsynets --db data/registry.sqlite
pda fetch --dataset mattilsyn:service --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL. Observation values are
copied from printed WMS `Layer`/`Name` text or WFS `FeatureType`/`Name`
text. A sibling `Title` stays as a dimension. License stays null. Publisher
stays null.

Live ingest 2026-08-28: 1 leftover WMS service (search prints 23 rows;
1 is OGC:WMS Type=service from Mattilsynet; cap 10 copies that leftover
live document after skipping W3C:REST, other organizations, downloads,
servicelayers, and hosts already covered by nibiowms, ldirwms, miljogis,
and mdirwms). Live search `Mattilsynets` returns `mattilsyn:service`.
Live fetch GETs
`https://kart.mattilsynet.no/wmscache/service?service=WMS&request=GetCapabilities`
HTTP 200, 10 Layer Name cells. Sample printed value:
`Mattilsynet_Vannverk_Inntakspunkter`. `pda methods` is not applicable: layer
names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/mattilsyn_source_proof.json`.

## Havforskningsinstituttet leftover WMS/WFS source

`pda ingest --source hiwms` is another replaceable adapter. It lists printed
leftover OGC:WMS and OGC:WFS Type=service rows on the official Geonorge
Kartkatalog search
`https://kartkatalog.geonorge.no/api/search?text=Havforskningsinstituttet&limit=50`,
capped at 10. Other organizations, downloads, servicelayers, and
OGC:API-Features rows are skipped. Havforskningsinstituttet OGC API
Coverages, Maps, Styles, Tiles, and Features paths are skipped.
Fiskeridirektoratet GIS, Kartverket Havnedata, leftover NGU WMS, leftover
Bane NOR skwms1 ids, leftover Avinor skwms1 ids, leftover Kartverket WMS
ids, leftover Miljødirektoratet WFS ids, and the HTML portal
`https://kart.hi.no/data/` are skipped. GetCapabilities bodies that are
not WMS or WFS XML are skipped. Dataset ids are the printed service path
segment so the leftover
`https://kart.hi.no/data/fraraadning/ows?service=WMS&version=1.3.0&request=GetCapabilities`
keeps native id `fraraadning_ows`. `access_path` is the printed
`DistributionUrl`. License stays null: the catalog prints no license URL.
Publisher stays null. This is not Havforskningsinstituttet OGC API Features
(`--source hi`), not OGC Coverages (`--source hicoverages`), not OGC Maps
(`--source himaps`), not OGC Styles (`--source histyles`), not OGC Tiles
(`--source hitiles`), not Fiskeridirektoratet GIS (`--source fiskerigis`),
and not Kartverket Havnedata (`--source havnedata`).

```bash
pda ingest --source hiwms --db data/registry.sqlite --limit 10
pda search Rådgivningskart --db data/registry.sqlite
pda fetch --dataset hiwms:fraraadning_ows --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL. Observation values are
copied from printed WMS `Layer`/`Name` text or WFS `FeatureType`/`Name`
text. A sibling `Title` stays as a dimension. License stays null. Publisher
stays null.

Live ingest 2026-08-28: 10 leftover WMS/WFS services (search prints 325
rows; cap 10 copies leftover live OGC:WMS and OGC:WFS Type=service
documents after skipping covered HI OGC API paths, sibling GIS hosts,
and bodies that are not WMS or WFS XML). Live search `Rådgivningskart`
returns `hiwms:fraraadning_ows`. Live fetch GETs
`https://kart.hi.no/data/fraraadning/ows?service=WMS&version=1.3.0&request=GetCapabilities`
HTTP 200, 4 Layer Name cells. Sample printed value: `Raadgivning_2024`.
`pda methods` is not applicable: layer names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/hiwms_source_proof.json`.

## Statens vegvesen leftover WMS/WFS source

`pda ingest --source vegwms` is another replaceable adapter. It lists printed
leftover OGC:WMS and OGC:WFS Type=service rows on the official Geonorge
Kartkatalog search
`https://kartkatalog.geonorge.no/api/search?text=Statens%20vegvesen&limit=50`,
capped at 10. Other organizations, downloads, servicelayers, and Vegkart
HTML are skipped. Leftover kartlag GetCapabilities already ingested by
`--source vegogc` on `ogckart-sn1.atlas.vegvesen.no` are skipped. The
printed norstoy mirror
`https://www.vegvesen.no/kart/ogc/norstoy_1_0/ows?service=WMS&request=getcapabilities`
is skipped because that workspace is already `--source vegogc`.
GetCapabilities bodies that are not WMS or WFS XML are skipped. Dataset
ids are the printed service path segment so the leftover
`https://wfs.geonorge.no/skwms1/wfs.stoy_veg?request=GetCapabilities&service=WFS`
keeps native id `wfs.stoy_veg`. `access_path` is the printed
`DistributionUrl`. License stays null: the catalog prints no license URL.
Publisher stays null. This is not Statens vegvesen leftover OGC kartlag
(`--source vegogc`) and not Statens vegvesen Dataportalen
(`--source vegvesen`).

```bash
pda ingest --source vegwms --db data/registry.sqlite --limit 10
pda search stoy_veg --db data/registry.sqlite
pda fetch --dataset vegwms:wfs.stoy_veg --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL. Observation values are
copied from printed WMS `Layer`/`Name` text or WFS `FeatureType`/`Name`
text. A sibling `Title` stays as a dimension. License stays null. Publisher
stays null.

Live ingest 2026-09-01: 3 leftover WFS services (search prints 24 rows;
4 are OGC:WMS or OGC:WFS Type=service from Statens vegvesen; the printed
norstoy mirror is already `--source vegogc`; cap 10 copies the 3 leftover
live Geonorge WFS documents). Live search `stoy_veg` returns
`vegwms:wfs.stoy_veg`. Live fetch GETs
`https://wfs.geonorge.no/skwms1/wfs.stoy_veg?request=GetCapabilities&service=WFS`
HTTP 200, 2 FeatureType Name cells. Sample printed value: `app:Støy`.
`pda methods` is not applicable: feature type names, not a numeric time
series. Proof is `data/vegwms_source_proof.json`.

## NGU leftover mineral WMS source

`pda ingest --source nguminer` is another replaceable adapter. It lists the
two official leftover NGU Type=service OGC:WMS GetCapabilities documents
`https://geo.ngu.no/mapserver/IndustrimineralerWMS3?request=GetCapabilities&service=WMS`
and
`https://geo.ngu.no/mapserver/MetallerWMS2?request=GetCapabilities&service=WMS`,
capped at 10. Each document is one dataset. GetCapabilities bodies that
are HTML or not WMS XML are skipped. Leftover mapserver ids already in
`--source nguwms` and OGC API Features already in `--source ngu` are
skipped. Native ids are the printed last `/mapserver/` path segment so
`IndustrimineralerWMS3` stays distinct from `MetallerWMS2`.
`access_path` is that GetCapabilities URL. License stays null: the
documents print no license URL. Publisher stays null. This is not NGU
OGC API Features (`--source ngu`) and not leftover NGU WMS
(`--source nguwms`).

```bash
pda ingest --source nguminer --db data/registry.sqlite --limit 10
pda search IndustrimineralerWMS3 --db data/registry.sqlite
pda fetch --dataset nguminer:IndustrimineralerWMS3 --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text, with
`Accept: application/xml, text/xml, */*`. Observation values are
copied from printed WMS `Layer`/`Name` text. A printed `Title`
sibling stays as a dimension. License stays null. Publisher stays
null. `pda methods` is not applicable: layer names, not a numeric
time series
(`no observations matched entity/measure; available=[]`).

Live ingest 2026-09-01: 2 leftover GetCapabilities documents. Live search
`IndustrimineralerWMS3` returns `nguminer:IndustrimineralerWMS3`. Live
fetch GETs
`https://geo.ngu.no/mapserver/IndustrimineralerWMS3?request=GetCapabilities&service=WMS`
HTTP 200, 78 printed layer-name cells. Sample printed value:
`IndustrimineralerWMS3`. `pda methods` is not applicable: layer names,
not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nguminer_source_proof.json`.

## BarentsWatch leftover WMS/WFS source

`pda ingest --source bwgis` is another replaceable adapter. It lists printed
leftover OGC:WMS and OGC:WFS Type=service rows on the official Geonorge
Kartkatalog search
`https://kartkatalog.geonorge.no/api/search?text=Barentswatch&limit=50`,
capped at 10. Other organizations, downloads, servicelayers, and
W3C:REST rows are skipped. Leftover Kystverket WMS/WFS hosts, leftover
Navigasjonsinstallasjoner hosts, Kartverket Havnedata, Fiskeridirektoratet
GIS, leftover Fiskeridirektoratet WMS, and leftover
Havforskningsinstituttet WMS/WFS hosts are skipped. GetCapabilities
bodies that are not WMS or WFS XML are skipped. Dataset ids are the
printed service path segment so the leftover
`https://geo.barentswatch.no/geoserver/bw/ows?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities`
keeps native id `bw_ows`. `access_path` is the printed `DistributionUrl`.
License stays null: the catalog prints no license URL. Publisher stays
null. This is not leftover Kystverket WMS (`--source kystwms`), not leftover
Kystverket WFS (`--source kystwfs`), not leftover Navigasjonsinstallasjoner
(`--source kystnav`), not Kartverket Havnedata (`--source havnedata`), not
Fiskeridirektoratet GIS (`--source fiskerigis`), not leftover
Fiskeridirektoratet WMS (`--source fdirwms`), and not leftover
Havforskningsinstituttet WMS/WFS (`--source hiwms`).

```bash
pda ingest --source bwgis --db data/registry.sqlite --limit 10
pda search BarentsWatch --db data/registry.sqlite
pda fetch --dataset bwgis:bw_ows --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL. Observation values are
copied from printed WMS `Layer`/`Name` text or WFS `FeatureType`/`Name`
text. A sibling `Title` stays as a dimension. License stays null. Publisher
stays null.

Live ingest 2026-09-01: 1 leftover WMS service (search prints 164
rows; 1 is OGC:WMS Type=service from Barentswatch; cap 10 copies that
leftover live document after skipping W3C:REST, servicelayers, sibling
GIS hosts, and bodies that are not WMS or WFS XML). Live search
`BarentsWatch` returns `bwgis:bw_ows`. Live fetch GETs
`https://geo.barentswatch.no/geoserver/bw/ows?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities`
HTTP 200, 29 Layer Name cells. Sample printed value:
`fisheryactivity_wms_longline`. `pda methods` is not applicable: layer
names, not a numeric time series. Proof is `data/bwgis_source_proof.json`.

## Norges Bank SDMX Codelists source

`pda ingest --source nbcodelist` is another replaceable adapter. It lists
printed codelist ids on the official Norges Bank SDMX catalog
`https://data.norges-bank.no/api/codelist?format=sdmx-json`, capped at 10.
Dataset ids are the printed `id` values. `access_path` joins each printed
`agencyID` and `id` onto the printed `/api/codelist` path and keeps the
catalog `format=sdmx-json` query. License stays null. Publisher stays
null. This is not the Norges Bank dataflow list (`--source norgesbank`).

```bash
pda ingest --source nbcodelist --db data/registry.sqlite --limit 10
pda search Frekvens --db data/registry.sqlite
pda fetch --dataset nbcodelist:CL_FREQ --db data/registry.sqlite
```

`pda fetch` GETs the stored codelist URL. Observation values are copied
from printed code `name` scalars. Other scalars stay as dimensions.
Nested `names` objects are not copied. License stays null. Publisher
stays null.

Live ingest 2026-08-28: 10 printed codelists (catalog prints 37; cap 10).
Live search `Frekvens` returns `nbcodelist:CL_FREQ`. Live fetch GETs
`https://data.norges-bank.no/api/codelist/NB/CL_FREQ?format=sdmx-json`
HTTP 200, 5 name cells. Sample printed value: `Annual`. `pda methods` is
not applicable: code names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nbcodelist_source_proof.json`.

## Norges Bank leftover SDMX data structures

`pda ingest --source nbdsd` is another replaceable adapter. It lists
printed data-structure ids on the official Norges Bank SDMX catalog
`https://data.norges-bank.no/api/datastructure?format=sdmx-json`,
capped at 10. Dataset ids are the printed `id` so `DSD_EXR` stays
distinct from `DSD_ANN_KPRA`. `access_path` joins printed `agencyID`
and `id` onto `/api/datastructure/{agencyID}/{id}` and keeps the same
`format=sdmx-json` query the list uses. License stays null. Publisher
stays null. This is not the dataflow list (`--source norgesbank`) and
not the SDMX codelist list (`--source nbcodelist`).

```bash
pda ingest --source nbdsd --db data/registry.sqlite --limit 10
pda search Valutakurser --db data/registry.sqlite
pda fetch --dataset nbdsd:DSD_EXR --db data/registry.sqlite
```

`pda fetch` GETs the stored structure URL. Observation values are
copied from printed component `id` values on dimensions, time
dimensions, attributes, and the primary measure. Nested objects are
not copied. License stays null. Publisher stays null.

Live ingest 2026-08-28: 10 printed data structures (catalog prints 24,
cap 10). Live search `Valutakurser` returns `nbdsd:DSD_EXR`. Live fetch
GETs
`https://data.norges-bank.no/api/datastructure/NB/DSD_EXR?format=sdmx-json`
HTTP 200, 10 component-id cells. Sample printed value: `FREQ`.
`pda methods` is not applicable: component ids, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nbdsd_source_proof.json`.

## Norges Bank leftover SDMX provision agreements

`pda ingest --source nbprov` is another replaceable adapter. It lists
printed provision-agreement ids on the official Norges Bank SDMX catalog
`https://data.norges-bank.no/api/provisionagreement?format=sdmx-json`,
capped at 10. Dataset ids are the printed `id` so `EXR_NB_NB` stays
distinct from `ANN_KPRA_NB_NB`. `access_path` joins printed `agencyID`
and `id` onto `/api/provisionagreement/{agencyID}/{id}` and keeps the
same `format=sdmx-json` query the catalog uses. License stays null.
Publisher stays null. This is not the dataflow list
(`--source norgesbank`), not the SDMX codelist list
(`--source nbcodelist`), and not the data-structure list
(`--source nbdsd`).

```bash
pda ingest --source nbprov --db data/registry.sqlite --limit 10
pda search Exchange --db data/registry.sqlite
pda fetch --dataset nbprov:EXR_NB_NB --db data/registry.sqlite
```

`pda fetch` GETs the stored provision-agreement URL. Observation values
are copied from printed agreement `name` scalars. Other scalars stay as
dimensions. Nested `names` objects are not copied. License stays null.
Publisher stays null.

Live ingest 2026-08-28: 10 printed provision agreements (catalog prints
24, cap 10). Live search `Exchange` returns `nbprov:EXR_NB_NB`. Live
fetch GETs
`https://data.norges-bank.no/api/provisionagreement/NB/EXR_NB_NB?format=sdmx-json`
HTTP 200, 1 name cell. Sample printed value:
`Norges Bank for Exchange rates`. `pda methods` is not applicable:
agreement names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nbprov_source_proof.json`.

## Kartverket leftover grunnkart WMS source

`pda ingest --source kvgrunn` is another replaceable adapter. It lists
the two official leftover Kartverket WMS GetCapabilities documents
`https://wms.geonorge.no/skwms1/wms.topograatone?service=WMS&request=GetCapabilities`
and
`https://wms.geonorge.no/skwms1/wms.norges_grunnkart?service=WMS&request=GetCapabilities`,
capped at 10. Each document is one dataset. GetCapabilities bodies that
are HTML or not WMS XML are skipped. Native ids are the printed last
path segment so `wms.topograatone` stays distinct from
`wms.norges_grunnkart`. `access_path` is that GetCapabilities URL.
License stays null: the documents print copyright text, not a license
URL. Publisher stays null. This is not Kartverket leftover WMS/WMTS
(`--source kvwms`, `wms.topo` and WMTS only), not Geonorge Kartkatalog
(`--source geonorge`), not Kartverket Høydedata (`--source hoydedata`),
not Kartverket Høydedata GIS (`--source hoydegis`), not Kartverket OGC
API Coverages (`--source ogccoverages`), and not Kartverket
Transformering (`--source transformering`).

```bash
pda ingest --source kvgrunn --db data/registry.sqlite --limit 10
pda search grunnkart --db data/registry.sqlite
pda fetch --dataset kvgrunn:wms.norges_grunnkart --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text, with
`Accept: application/xml, text/xml, */*`. Observation values are
copied from printed WMS `Layer`/`Name` text. A printed `Title`
sibling stays as a dimension. License stays null. Publisher stays
null. `pda methods` is not applicable: layer names, not a numeric
time series
(`no observations matched entity/measure; available=[]`).

Live ingest 2026-08-28: 2 leftover GetCapabilities documents. Live search
`grunnkart` returns `kvgrunn:wms.norges_grunnkart`. Live fetch GETs
`https://wms.geonorge.no/skwms1/wms.norges_grunnkart?service=WMS&request=GetCapabilities`
HTTP 200, 111 printed layer-name cells. Sample printed value:
`Norges_grunnkart`. `pda methods` is not applicable: layer names, not a
numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/kvgrunn_source_proof.json`.

## Kartverket leftover topo WMS source

`pda ingest --source kvtopo` is another replaceable adapter. It lists the
six official leftover Kartverket WMS GetCapabilities documents
`https://wms.geonorge.no/skwms1/wms.kartdata?service=wms&request=getcapabilities`,
`https://wms.geonorge.no/skwms1/wms.fkb?service=wms&request=getcapabilities`,
`https://wms.geonorge.no/skwms1/wms.friluftsruter2?request=GetCapabilities&service=WMS&version=1.3.0`,
`https://wms.geonorge.no/skwms1/wms.fjellskygge?request=GetCapabilities&service=WMS`,
`https://wms.geonorge.no/skwms1/wms.n5raster2?service=wms&request=getcapabilities`,
and
`https://wms.geonorge.no/skwms1/wms.markagrensen?request=GetCapabilities&Service=WMS`,
capped at 10. Each document is one dataset. GetCapabilities bodies that
are HTML or not WMS XML are skipped. `wms.topo` and WMTS already in
`--source kvwms`, leftover grunnkart ids already in `--source kvgrunn`,
and restricted Matrikkelen WMS are skipped. Native ids are the printed
last path segment so `wms.kartdata` stays distinct from `wms.fkb`.
`access_path` is that GetCapabilities URL. License stays null: the
documents print copyright text, not a license URL. Publisher stays
null. This is not Kartverket leftover WMS/WMTS (`--source kvwms`), not
leftover grunnkart WMS (`--source kvgrunn`), not Havnedata
(`--source havnedata`), not Geonorge Kartkatalog (`--source geonorge`),
not Stedsnavn (`--source stedsnavn`), not Høydedata
(`--source hoydedata`), not Transformering (`--source transformering`),
not Kartverket Register (`--source georegister`), and not Kartverket
OGC API Coverages (`--source ogccoverages`).

```bash
pda ingest --source kvtopo --db data/registry.sqlite --limit 10
pda search kartdata --db data/registry.sqlite
pda fetch --dataset kvtopo:wms.kartdata --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text, with
`Accept: application/xml, text/xml, */*`. Observation values are
copied from printed WMS `Layer`/`Name` text. A printed `Title`
sibling stays as a dimension. License stays null. Publisher stays
null. `pda methods` is not applicable: layer names, not a numeric
time series
(`no observations matched entity/measure; available=[]`).

Live ingest 2026-09-01: 6 leftover GetCapabilities documents. Live search
`kartdata` returns `kvtopo:wms.kartdata`. Live fetch GETs
`https://wms.geonorge.no/skwms1/wms.kartdata?service=wms&request=getcapabilities`
HTTP 200, 160 printed layer-name cells. Sample printed value:
`kartdata`. `pda methods` is not applicable: layer names, not a
numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/kvtopo_source_proof.json`.

## Miljødirektoratet leftover ArcGIS WMS source

`pda ingest --source mdirgis` is another replaceable adapter. It lists printed
leftover OGC:WMS and OGC:WFS Type=service rows on the official Geonorge
Kartkatalog search
`https://kartkatalog.geonorge.no/api/search?text=Milj%C3%B8direktoratet`,
capped at 10. Other organizations, downloads, and servicelayers are skipped.
URLs already owned by leftover Miljødirektoratet WMS/WFS
(`--source mdirwms`) or Miljødirektoratet ArcGIS REST
(`--source miljogis`) are skipped, including `industri` and other
kart2/kart3/image001/geoserver GetCapabilities already listed by
`mdirwms`. GetCapabilities bodies that are not WMS or WFS XML are
skipped. Dataset ids are the printed service path segment so
`villrein` stays distinct from `snoscooterloyper`. `access_path` is
the printed `DistributionUrl`. License stays null: the catalog prints
no license URL. Publisher stays null. This is not leftover
Miljødirektoratet WMS/WFS (`--source mdirwms`), not Miljødirektoratet
ArcGIS REST (`--source miljogis`), not Vannmiljø (`--source miljodir`),
not leftover NIBIO WMS (`--source nibiowms`), and not leftover
Landbruksdirektoratet WMS (`--source ldirwms`).

```bash
pda ingest --source mdirgis --db data/registry.sqlite --limit 10
pda search Villreinområder --db data/registry.sqlite
pda fetch --dataset mdirgis:villrein --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL. Observation values are
copied from printed WMS `Layer`/`Name` text or WFS `FeatureType`/`Name`
text. A sibling `Title` stays as a dimension. License stays null. Publisher
stays null.

Live ingest 2026-09-01: 10 leftover WMS services (search prints 176 rows;
leftover live ArcGIS WMS wrappers remain after skipping mdirwms hosts,
miljogis REST, industri, other organizations, downloads, servicelayers,
HTML, 404, and ServiceException bodies; cap 10 copies the first ten). Live
search `Villreinområder` returns `mdirgis:villrein`. Live fetch GETs
`https://kart.miljodirektoratet.no/arcgis/services/villrein/MapServer/WMSServer?request=GetCapabilities&service=WMS`
HTTP 200, 8 Layer Name cells. Sample printed value:
`villrein_helarsbeite`. `pda methods` is not applicable: layer
names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/mdirgis_source_proof.json`.

## Norges Bank SDMX Concept Schemes source

`pda ingest --source nbconcept` is another replaceable adapter. It lists
printed concept-scheme ids on the official Norges Bank SDMX catalog
`https://data.norges-bank.no/api/conceptscheme?format=sdmx-json`,
capped at 10. Dataset ids are the printed `id` values. `access_path`
joins each printed `agencyID` and `id` onto the printed
`/api/conceptscheme` path and keeps the catalog `format=sdmx-json`
query. License stays null. Publisher stays null. This is not the Norges
Bank dataflow list (`--source norgesbank`) and not leftover SDMX
codelists (`--source nbcodelist`) or data structures
(`--source nbdsd`).

```bash
pda ingest --source nbconcept --db data/registry.sqlite --limit 10
pda search konsepter --db data/registry.sqlite
pda fetch --dataset nbconcept:CS_NB --db data/registry.sqlite
```

`pda fetch` GETs the stored concept-scheme URL. Observation values are
copied from printed concept `name` scalars. Other scalars stay as
dimensions. Nested `names`, `links`, and `descriptions` objects are not
copied. License stays null. Publisher stays null.

Live ingest 2026-08-28: 1 printed concept scheme (catalog prints 1; cap
10). Live search `konsepter` returns `nbconcept:CS_NB`. Live fetch GETs
`https://data.norges-bank.no/api/conceptscheme/NB/CS_NB?format=sdmx-json`
HTTP 200, 76 name cells. Sample printed value: `Time Period`.
`pda methods` is not applicable: concept names, not a numeric time
series (`no observations matched entity/measure; available=[]`).
Proof is `data/nbconcept_source_proof.json`.

## SSB Klass classification families source

`pda ingest --source ssbfam` is another replaceable adapter. It lists printed
classification families on the official SSB Klass catalog
`https://data.ssb.no/api/klass/v1/classificationfamilies`, the leftover
collection GET named by `https://data.ssb.no/api/klass/v3/api-docs`, capped
at 10. Dataset ids are the printed family `id`. `access_path` is the printed
`_links.self.href`. License stays null. Publisher stays null. The families
catalog prints neither. This is not Statbank (`--source ssb`), not PxWebApi 2
(`--source ssbv2`), and not the Klass version fetch already on main
(`/api/klass/v1/versions`).

```bash
pda ingest --source ssbfam --db data/registry.sqlite --limit 10
pda search Arbeid --db data/registry.sqlite
pda fetch --dataset ssbfam:1 --db data/registry.sqlite
```

`pda fetch` GETs the stored family URL. Observation values are copied from
printed classification `name` when present, otherwise `id`. License stays
null. Publisher stays null.

Live ingest 2026-08-28: 10 printed families (catalog prints 22, cap 10).
Live search `Arbeid` returns `ssbfam:1`. Live fetch GETs
`https://data.ssb.no/api/klass/v1/classificationfamilies/1` HTTP 200, 1
classification-name cell. Sample printed value: `Standard for
yrkesklassifisering`. `pda methods` is not applicable: classification
names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/ssbfam_source_proof.json`.

## SSB Klass classifications source

`pda ingest --source ssclass` is another replaceable adapter. It lists
printed classification ids on the official Klass collection
`https://data.ssb.no/api/klass/v1/classifications`, capped at 10. The
official Klass OpenAPI names that collection GET and prints no required
query. Dataset ids are the printed `id` values. `access_path` is the
printed `_links.self.href`. License stays null. Publisher stays null.
This is not the SSB PxWeb v0 Statbank (`--source ssb`), not PxWebApi 2
(`--source ssbv2`), not Klass families (`--source ssbfam`), not Klass
sections (`--source ssbsec`), and not Klass version fetch on
`/api/klass/v1/versions`.

```bash
pda ingest --source ssclass --db data/registry.sqlite --limit 10
pda search grunnkretsinndeling --db data/registry.sqlite
pda fetch --dataset ssclass:1 --db data/registry.sqlite
```

`pda fetch` GETs the stored classification URL. Observation values are
copied from printed version `name` scalars. Other scalars stay as
dimensions. Nested `_links` and `published` objects are not copied.
License stays null. Publisher stays null.

Live ingest 2026-08-28: listed 10, inserted 10. The catalog first page
prints 20 of 151 classifications. This walk copies the first ten in
document order. Live search `grunnkretsinndeling` returns `ssclass:1`.
Live fetch GETs `https://data.ssb.no/api/klass/v1/classifications/1`
HTTP 200, 39 name cells. Sample printed value:
`Delområde- og grunnkretsinndeling 2016`. `pda methods` is not
applicable: version names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/ssclass_source_proof.json`.

## SSB Klass versions source

`pda ingest --source ssbver` is another replaceable adapter. It lists
printed version ids on official Klass classifications. The Klass OpenAPI
names GET `/api/klass/v1/versions/{id}` and prints no versions
collection. The walk copies printed `_links.self.href` values from the
classifications catalog, GETs those printed classification paths, and
copies printed `versions[].id` plus `versions[]._links.self.href`. The
walk caps at 10. Dataset ids are the printed version `id` values.
`access_path` is the printed version self href. License stays null.
Publisher stays null. This is not the SSB PxWeb v0 Statbank
(`--source ssb`), not PxWebApi 2 (`--source ssbv2`), not Klass families
(`--source ssbfam`), not Klass sections (`--source ssbsec`), and not
Klass classifications (`--source ssclass`).

```bash
pda ingest --source ssbver --db data/registry.sqlite --limit 10
pda search "grunnkretsinndeling 2016" --db data/registry.sqlite
pda fetch --dataset ssbver:1 --db data/registry.sqlite
```

`pda fetch` GETs the stored version URL. Observation values are copied
from printed correspondence-table `name` scalars. Other scalars stay as
dimensions. Nested `_links` and `published` objects are not copied.
License stays null. Publisher stays null.

Live ingest 2026-08-28: listed 10, inserted 10. The first printed
classification prints 39 versions. This walk copies the first ten in
document order. Live search `grunnkretsinndeling 2016` returns
`ssbver:1`. Live fetch GETs
`https://data.ssb.no/api/klass/v1/versions/1` HTTP 200, 5 name cells.
Sample printed value:
`Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2014`.
`pda methods` is not applicable: correspondence-table names, not a
numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/ssbver_source_proof.json`.

## NIBIO leftover WMS source

`pda ingest --source nibiorest` is another replaceable adapter. It lists
printed GetCapabilities hrefs on leftover official NIBIO WMS pages
under `https://nibio.no/tjenester/wms-tjenester` after the nibiowms cap
of 10, capped at 10. Child pages under `/tjenester/wms-tjenester/` are
walked. cgi-bin names already ingested by leftover NIBIO WMS
(`--source nibiowms`) or leftover Landbruksdirektoratet WMS
(`--source ldirwms`) are skipped. Attachment links and the gårdskart
page (no cgi-bin GetCapabilities) are skipped. GetCapabilities bodies
that are HTML MapServer errors are skipped, including
`riparian_zones_GLE`. Dataset ids are the printed last cgi-bin path
segment so `hrl` stays distinct from `ok_raster`. `access_path` is the
GetCapabilities URL as printed. License stays null. Publisher stays
null. This is not NIBIO IPM weather (`--source nibio`), not leftover
NIBIO WMS (`--source nibiowms`), and not leftover Landbruksdirektoratet
WMS (`--source ldirwms`).

```bash
pda ingest --source nibiorest --db data/registry.sqlite --limit 10
pda search hrl --db data/registry.sqlite
pda fetch --dataset nibiorest:hrl --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text. Observation
values are copied from printed WMS `Layer`/`Name` text. A printed
`Title` sibling stays as a dimension. License stays null. Publisher
stays null.

Live ingest 2026-08-28: 1 leftover GetCapabilities service (catalog
prints 12 hrefs; nibiowms already took the first 10 live XML services;
`riparian_zones_GLE` is HTML; cap 10 copies leftover `hrl`). Live search
`hrl` returns `nibiorest:hrl`. Live fetch GETs
`https://wms.nibio.no/cgi-bin/hrl?VERSION=1.3.0&REQUEST=GetCapabilities&service=wms`
HTTP 200, 7 Layer Name cells. Sample printed value:
`High_Resolution_Layers`. `pda methods` is not applicable: layer names,
not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/nibiorest_source_proof.json`.

## Avinor leftover WMS/WFS source

`pda ingest --source avinorgis` is another replaceable adapter. It lists the
three printed leftover Avinor GetCapabilities documents
`https://wfs.geonorge.no/skwms1/wfs.lufthavnpunkt_avinor?Service=WFS&Request=GetCapabilities`,
`https://wfs.geonorge.no/skwms1/wfs.stoylufthavn?service=WFS&request=GetCapabilities`,
and
`https://wms.geonorge.no/skwms1/wms.stoylufthavn?service=wms&request=getcapabilities`,
capped at 10. Those URLs are printed on Geonorge Kartkatalog search
`https://kartkatalog.geonorge.no/api/search?text=Avinor` as Type=service
OGC:WFS or OGC:WMS. A document that is not WMS or WFS XML is skipped.
Dataset ids are the printed last path segment so `wms.stoylufthavn` stays
distinct from `wfs.stoylufthavn`. `access_path` is the GetCapabilities URL
as printed. License stays null. Publisher stays null. This is not
Kartverket leftover topo WMS/WMTS (`--source kvwms`), not leftover
grunnkart WMS (`--source kvgrunn`), not Statens vegvesen leftover OGC
(`--source vegogc`), not Geonorge Kartkatalog (`--source geonorge`), and
not leftover Bane NOR WMS/WFS (`--source banegis`).

```bash
pda ingest --source avinorgis --db data/registry.sqlite --limit 10
pda search stoylufthavn --db data/registry.sqlite
pda fetch --dataset avinorgis:wms.stoylufthavn --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL as text. Observation
values are copied from printed WMS `Layer`/`Name` text or WFS
`FeatureType`/`Name` text. A printed `Title` sibling stays as a
dimension. License stays null. Publisher stays null.

Live ingest 2026-08-28: 3 printed GetCapabilities documents, all XML
200. Live search `stoylufthavn` returns
`avinorgis:wfs.stoylufthavn`. Live fetch GETs
`https://wms.geonorge.no/skwms1/wms.stoylufthavn?service=wms&request=getcapabilities`
HTTP 200, 2 Layer Name cells. Sample printed value:
`stoylufthavn_wms`. `pda methods` is not applicable: layer names,
not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/avinorgis_source_proof.json`.

## Enhetsregisteret leftover roller lists

`pda ingest --source brroller` is another replaceable adapter. It lists
leftover collection GET paths under `/enhetsregisteret/api/roller/`
named in the official Brønnøysundregistrene OpenAPI
`https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/openapi.json`.
Templated paths, required parameters, and the printed gzip
`totalbestand` dump are skipped. Dataset ids are the printed last path
segment so `representanter` stays distinct from `rolletyper`.
`access_path` is printed `servers[0].url` plus path. License is the
printed OpenAPI NLOD URL. Publisher stays null. This is not
Enhetsregisteret (`--source brreg`) and not Frivillighetsregisteret
(`--source frivillig`).

```bash
pda ingest --source brroller --db data/registry.sqlite --limit 10
pda search rollerepresentanter --db data/registry.sqlite
pda fetch --dataset brroller:representanter --db data/registry.sqlite
```

`pda fetch` GETs the stored representanter URL. Observation values are
copied from printed `beskrivelse` scalars. Printed `kode` stays as a
dimension. License is the printed NLOD URL. Publisher stays null.

Live ingest 2026-08-28: listed 3, inserted 3 (catalog prints three
leftover JSON collection paths; cap 10 copies all three). Live search
`rollerepresentanter` returns `brroller:representanter`. Live fetch GETs
`https://data.brreg.no/enhetsregisteret/api/roller/representanter`
HTTP 200, 4 beskrivelse cells. Sample printed value:
`Representant for A-aksjonærene`.
`pda methods` is not applicable: role descriptions, not a numeric time
series (`no observations matched entity/measure; available=[]`).
Proof is `data/brroller_source_proof.json`.

## Fiskeridirektoratet leftover WMS/WFS source

`pda ingest --source fdirwms` is another replaceable adapter. It lists printed
leftover OGC:WMS and OGC:WFS Type=service rows on the official Geonorge
Kartkatalog search
`https://kartkatalog.geonorge.no/api/search?text=Fiskeridirektoratet`,
capped at 10. Other organizations, downloads, and servicelayers are skipped.
ArcGIS REST already covered by Fiskeridirektoratet GIS is skipped. Kystverket
leftover WMS/WFS hosts and havnedata are skipped. GetCapabilities bodies that
are not WMS or WFS XML are skipped. Dataset ids are the printed service path
segment so `FiskeridirWFS_fiskeri` stays distinct from `fiskeridirWMS`.
`access_path` is the printed `DistributionUrl`. License stays null: the
catalog prints no license URL. Publisher stays null. This is not
Fiskeridirektoratet ArcGIS REST (`--source fiskerigis`), not Fartøyregisteret
(`--source fiskeridir`), not leftover Kystverket WMS (`--source kystwms`),
not leftover Kystverket WFS (`--source kystwfs`), not leftover
Navigasjonsinstallasjoner (`--source kystnav`), and not havnedata
(`--source havnedata`).

```bash
pda ingest --source fdirwms --db data/registry.sqlite --limit 10
pda search FiskeridirWFS_fiskeri --db data/registry.sqlite
pda fetch --dataset fdirwms:FiskeridirWFS_fiskeri --db data/registry.sqlite
```

`pda fetch` GETs the stored GetCapabilities URL. Observation values are
copied from printed WMS `Layer`/`Name` text or WFS `FeatureType`/`Name`
text. A sibling `Title` stays as a dimension. License stays null. Publisher
stays null.

Live ingest 2026-08-28: 10 leftover WMS/WFS services (search prints 48 rows;
14 are OGC:WMS or OGC:WFS Type=service; cap 10 copies the first ten leftover
live documents after skipping fiskerigis ArcGIS wrappers, other organizations,
downloads, servicelayers, HTML, and HTTP 499). Live search
`FiskeridirWFS_fiskeri` returns `fdirwms:FiskeridirWFS_fiskeri`. Live fetch
GETs
`https://gis.fiskeridir.no/server/services/FiskeridirWFS_fiskeri/MapServer/WFSServer?SERVICE=WFS&REQUEST=GetCapabilities`
HTTP 200, 57 FeatureType Name cells. Sample printed value:
`FiskeridirWFS_fiskeri:breivikfjorden_lokalregulering`. `pda methods` is not
applicable: feature type names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/fdirwms_source_proof.json`.

## Enhetsregisteret organisasjonsformer source

`pda ingest --source brorgform` is another replaceable adapter. It lists
printed organisasjonsform codes on the official Enhetsregisteret
collection
`https://data.brreg.no/enhetsregisteret/api/organisasjonsformer`,
capped at 10. Dataset ids are the printed `kode` values. `access_path`
is the printed `_links.self.href`. License stays null. Publisher stays
null. This is not the Enhetsregisteret HAL root (`--source brreg`), not
Frivillighetsregisteret (`--source frivillig`), not
Regnskapsregisteret (`--source regnskap`), and not leftover roller
lists (`--source brroller`).

```bash
pda ingest --source brorgform --db data/registry.sqlite --limit 10
pda search Aksjeselskap --db data/registry.sqlite
pda fetch --dataset brorgform:AS --db data/registry.sqlite
```

`pda fetch` GETs the stored organisasjonsform URL. Observation values
are copied from the printed `beskrivelse` scalar. Other scalars stay as
dimensions. Nested `_links` objects are not copied. License stays null.
Publisher stays null.

The catalog prints 44 organisasjonsformer. This walk copies the first
ten in document order. Live ingest listed 10 and inserted 10. Live
search `Aksjeselskap` returns `brorgform:AS`. Live fetch GETs
`https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/AS`
HTTP 200, 1 row, `beskrivelse` = `Aksjeselskap`. `pda methods` is not
applicable. Organisasjonsform names are not a numeric time series.
Proof is `data/brorgform_source_proof.json`.

## Norges Bank SDMX Agency Schemes source

`pda ingest --source nbagency` is another replaceable adapter. It lists
printed agency-scheme ids on the official Norges Bank SDMX catalog
`https://data.norges-bank.no/api/agencyscheme?format=sdmx-json`,
capped at 10. Dataset ids are the printed `id` values. `access_path`
joins each printed `agencyID` and `id` onto the printed
`/api/agencyscheme` path and keeps the catalog `format=sdmx-json`
query. License stays null. Publisher stays null. This is not the Norges
Bank dataflow list (`--source norgesbank`) and not leftover SDMX
codelists (`--source nbcodelist`), data structures (`--source nbdsd`),
or concept schemes (`--source nbconcept`).

```bash
pda ingest --source nbagency --db data/registry.sqlite --limit 10
pda search Agency --db data/registry.sqlite
pda fetch --dataset nbagency:AGENCIES --db data/registry.sqlite
```

`pda fetch` GETs the stored agency-scheme URL. Observation values are
copied from printed agency `name` scalars. Other scalars stay as
dimensions. Nested `names`, `links`, `descriptions`, and `contacts`
objects are not copied. License stays null. Publisher stays null.

Live ingest 2026-08-28: 1 printed agency scheme (catalog prints 1; cap
10). Live search `Agency` returns `nbagency:AGENCIES`. Live fetch GETs
`https://data.norges-bank.no/api/agencyscheme/SDMX/AGENCIES?format=sdmx-json`
HTTP 200, 2 name cells. Sample printed value: `Norges Bank`.
`pda methods` is not applicable: agency names, not a numeric time
series (`no observations matched entity/measure; available=[]`).
Proof is `data/nbagency_source_proof.json`.

## Norges Bank SDMX Data Provider Schemes source

`pda ingest --source nbdps` is another replaceable adapter. It lists
printed data-provider-scheme ids on the official Norges Bank SDMX
catalog `https://data.norges-bank.no/api/dataproviderscheme?format=sdmx-json`,
capped at 10. Dataset ids are the printed `id` values. `access_path`
joins each printed `agencyID` and `id` onto the printed
`/api/dataproviderscheme` path and keeps the catalog `format=sdmx-json`
query. License stays null. Publisher stays null. This is not the Norges
Bank dataflow list (`--source norgesbank`), not leftover SDMX
agency schemes (`--source nbagency`), not leftover categoryscheme,
and not leftover provision agreements (`--source nbprov`).

```bash
pda ingest --source nbdps --db data/registry.sqlite --limit 10
pda search DATA_PROVIDERS --db data/registry.sqlite
pda fetch --dataset nbdps:DATA_PROVIDERS --db data/registry.sqlite
```

`pda fetch` GETs the stored data-provider-scheme URL. Observation values
are copied from printed data-provider `name` scalars. Other scalars stay
as dimensions. Nested `names`, `links`, and `descriptions` objects are
not copied. License stays null. Publisher stays null.

Live ingest 2026-09-01: 1 printed data-provider scheme (catalog prints 1;
cap 10). Live search `DATA_PROVIDERS` returns `nbdps:DATA_PROVIDERS`.
Live fetch GETs
`https://data.norges-bank.no/api/dataproviderscheme/NB/DATA_PROVIDERS?format=sdmx-json`
HTTP 200, 3 name cells. Sample printed value: `Thomson Reuters`.
`pda methods` is not applicable: data-provider names, not a numeric time
series (`no observations matched entity/measure; available=[]`).
Proof is `data/nbdps_source_proof.json`.

## Digdir Felles datakatalog organization catalogue source

`pda ingest --source fdkorg` is another replaceable adapter. It lists
printed organization ids on the official Digdir Felles datakatalog
organization catalogue
`https://organization-catalogue.fellesdatakatalog.digdir.no/organizations`,
capped at 10. Dataset ids are the printed `organizationId` values.
`access_path` joins each printed `organizationId` onto the printed
`/organizations` path. License stays null. Publisher stays null. This
is not Data.norge (`--source datanorge`), not Enhetsregisteret
(`--source brreg`), and not Kartverket Kommuneinfo
(`--source kommuneinfo`).

```bash
pda ingest --source fdkorg --db data/registry.sqlite --limit 10
pda search BEIARN --db data/registry.sqlite
pda fetch --dataset fdkorg:961147867 --db data/registry.sqlite
```

`pda fetch` GETs the stored organization URL. Observation values are
copied from the printed `name` scalar. Other scalars stay as
dimensions. Nested `prefLabel` objects are not copied. License stays
null. Publisher stays null.

The catalog prints 977 organizations. This walk copies the first ten
in document order. Live ingest listed 10 and inserted 10. Live search
`BEIARN` returns `fdkorg:961147867`. Live fetch GETs
`https://organization-catalogue.fellesdatakatalog.digdir.no/organizations/961147867`
HTTP 200, 1 row, `name` = `BEIARN KOMMUNE`. `pda methods` is not
applicable. Organization names are not a numeric time series.
Proof is `data/fdkorg_source_proof.json`.

## Enhetsregisteret rolletyper source

`pda ingest --source brrolletype` is another replaceable adapter. It lists
printed rolletype codes on the official Enhetsregisteret collection
`https://data.brreg.no/enhetsregisteret/api/roller/rolletyper`,
capped at 10. Dataset ids are the printed `kode` values. `access_path`
joins each printed kode onto that public collection path. Printed
`_links.self.href` values point at `/enhetsregisteret/autorisert-api/`
and that path is HTTP 401, so they are not copied. License stays null.
Publisher stays null. This is not the Enhetsregisteret HAL root
(`--source brreg`), not leftover roller OpenAPI paths
(`--source brroller`), and not organisasjonsformer
(`--source brorgform`).

```bash
pda ingest --source brrolletype --db data/registry.sqlite --limit 10
pda search Administrativ --db data/registry.sqlite
pda fetch --dataset brrolletype:ADOS --db data/registry.sqlite
```

`pda fetch` GETs the stored rolletype URL. Observation values are copied
from the printed `beskrivelse` scalar. Other scalars stay as dimensions.
Nested `_links` objects are not copied. License stays null. Publisher
stays null.

The catalog prints 27 rolletyper. This walk copies the first ten in
document order. Live ingest listed 10 and inserted 10. Live search
`Administrativ` returns `brrolletype:ADOS`. Live fetch GETs
`https://data.brreg.no/enhetsregisteret/api/roller/rolletyper/ADOS`
HTTP 200, 1 row, `beskrivelse` = `Administrativ enhet - offentlig sektor`.
`pda methods` is not applicable. Rolletype names are not a numeric time
series.
Proof is `data/brrolletype_source_proof.json`.

## Enhetsregisteret kommuner source

`pda ingest --source brkommuner` is another replaceable adapter. It lists
printed kommune numbers on the official Enhetsregisteret collection
`https://data.brreg.no/enhetsregisteret/api/kommuner`,
capped at 10. Dataset ids are the printed `nummer` values. `access_path`
is the printed `_links.self.href`. License stays null. Publisher stays
null. This is not the Enhetsregisteret HAL root (`--source brreg`), not
leftover organisasjonsformer (`--source brorgform`), not leftover
roller lists (`--source brroller`), not Frivillighetsregisteret
(`--source frivillig`), and not Kartverket kommuneinfo
(`--source kommuneinfo`).

```bash
pda ingest --source brkommuner --db data/registry.sqlite --limit 10
pda search OSLO --db data/registry.sqlite
pda fetch --dataset brkommuner:0301 --db data/registry.sqlite
```

`pda fetch` GETs the stored kommune URL. Observation values are copied
from the printed `navn` scalar. Other scalars stay as dimensions.
Nested `_links` objects are not copied. License stays null. Publisher
stays null.

The first printed catalog page lists kommuner. This walk copies the
first ten in document order and does not invent page or size query
parameters. Live ingest listed 10 and inserted 10. Live search `OSLO`
returns `brkommuner:0301`. Live fetch GETs
`https://data.brreg.no/enhetsregisteret/api/kommuner/0301`
HTTP 200, 1 row, `navn` = `OSLO`. `pda methods` is not applicable.
Kommune names are not a numeric time series.
Proof is `data/brkommuner_source_proof.json`.

## Enhetsregisteret rollegruppetyper source

`pda ingest --source brrollegruppe` is another replaceable adapter. It
lists printed `kode` values on the official Enhetsregisteret
rollegruppetyper catalog
`https://data.brreg.no/enhetsregisteret/api/roller/rollegruppetyper`,
capped at 10. Dataset ids are the printed `kode` values. `access_path`
joins each printed `kode` onto that public collection path. Printed
`self` hrefs point at `/enhetsregisteret/autorisert-api/` (HTTP 401)
and are not copied. License stays null. Publisher stays null. This is
not the Enhetsregisteret HAL root (`--source brreg`), not leftover
roller OpenAPI collection GETs (`--source brroller`), not leftover
organisasjonsformer (`--source brorgform`), and not leftover
rolletyper (`--source brrolletype`).

```bash
pda ingest --source brrollegruppe --db data/registry.sqlite --limit 10
pda search "Daglig leder" --db data/registry.sqlite
pda fetch --dataset brrollegruppe:DAGL --db data/registry.sqlite
```

`pda fetch` GETs the stored public kode URL. Observation values are
copied from the printed `beskrivelse` scalar. Other scalars stay as
dimensions. Nested `_links` objects are not copied. License stays
null. Publisher stays null.

Live ingest 2026-09-01: 10 printed rollegruppetyper (catalog prints 21;
cap 10). Live search `Daglig leder` returns `brrollegruppe:DAGL`. Live
fetch GETs
`https://data.brreg.no/enhetsregisteret/api/roller/rollegruppetyper/DAGL`
HTTP 200, 1 beskrivelse cell. Sample printed value: `Daglig leder`.
`pda methods` is not applicable: role-group names, not a numeric time
series. Proof is `data/brrollegruppe_source_proof.json`.

## SSB Klass correspondence tables source

`pda ingest --source ssbcorr` is another replaceable adapter. It lists
printed correspondence-table ids on official Klass versions. The Klass
OpenAPI names GET `/api/klass/v1/correspondencetables/{id}` and prints
no correspondence-tables collection. The walk copies printed
`_links.self.href` values from the classifications catalog, GETs those
printed classification paths, GETs printed version self hrefs, and
copies printed `correspondenceTables[].id` plus
`correspondenceTables[]._links.self.href`. The walk caps at 10.
Dataset ids are the printed table `id` values. `access_path` is the
printed table self href. License stays null. Publisher stays null.
This is not the SSB PxWeb v0 Statbank (`--source ssb`), not PxWebApi 2
(`--source ssbv2`), not Klass families (`--source ssbfam`), not Klass
sections (`--source ssbsec`), not Klass classifications
(`--source ssclass`), and not Klass versions (`--source ssbver`).

```bash
pda ingest --source ssbcorr --db data/registry.sqlite --limit 10
pda search "2016 - Delområde- og grunnkretsinndeling 2014" --db data/registry.sqlite
pda fetch --dataset ssbcorr:160 --db data/registry.sqlite
```

`pda fetch` GETs the stored correspondence-table URL. Observation
values are copied from printed `correspondenceMaps[].sourceName`
scalars. Other scalars stay as dimensions. Nested `_links` and
`published` objects are not copied. License stays null. Publisher
stays null.

Live ingest 2026-09-01: listed 10, inserted 10. The first printed
classification versions print correspondence tables. This walk copies
the first ten unique printed table ids in document order. Live search
`2016 - Delområde- og grunnkretsinndeling 2014` returns `ssbcorr:160`.
Live fetch GETs
`https://data.ssb.no/api/klass/v1/correspondencetables/160` HTTP 200,
8 sourceName cells. Sample printed value: `Stabekk 26`. `pda methods`
is not applicable: correspondence-map names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/ssbcorr_source_proof.json`.

## Enhetsregisteret leftover oppdateringer source

`pda ingest --source broppdater` is another replaceable adapter. It lists
leftover collection GET paths under `/enhetsregisteret/api/oppdateringer/`
named in the official Brønnøysundregistrene OpenAPI
`https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/openapi.json`.
Templated paths and GET operations that print required parameters are
skipped. Dataset ids are the printed last path segment so `enheter`
stays distinct from `underenheter` and `roller`. `access_path` is
printed `servers[0].url` plus path. License is the printed OpenAPI NLOD
URL. Publisher stays null. This is not the Enhetsregisteret HAL root
(`--source brreg`), not leftover roller OpenAPI collection GETs
(`--source brroller`), not leftover organisasjonsformer
(`--source brorgform`), not leftover rolletyper
(`--source brrolletype`), not leftover kommuner
(`--source brkommuner`), and not leftover rollegruppetyper
(`--source brrollegruppe`).

```bash
pda ingest --source broppdater --db data/registry.sqlite --limit 10
pda search "oppdateringer på enheter" --db data/registry.sqlite
pda fetch --dataset broppdater:enheter --db data/registry.sqlite
```

`pda fetch` GETs the stored enheter-oppdateringer URL. Observation
values are copied from printed `endringstype` scalars when present.
Other printed scalars stay as dimensions. Nested `_links` objects are
not copied. License is the printed NLOD URL. Publisher stays null.

Live ingest 2026-09-01: listed 3, inserted 3 (catalog prints three
leftover JSON collection paths; cap 10 copies all three). Live search
`oppdateringer på enheter` returns `broppdater:enheter`. Live fetch GETs
`https://data.brreg.no/enhetsregisteret/api/oppdateringer/enheter`
HTTP 200, 20 endringstype cells. Sample printed value: `Ukjent`.
`pda methods` is not applicable: update event labels, not a numeric time
series (`no observations matched entity/measure; available=[]`).
Proof is `data/broppdater_source_proof.json`.
## Kartverket Kommuneinfo fylker source

`pda ingest --source kifylker` is another replaceable adapter. It lists
printed fylkesnummer values on the official Kartverket Kommuneinfo
fylker catalog
`https://api.kartverket.no/kommuneinfo/v1/fylker`,
capped at 10. Dataset ids are the printed `fylkesnummer` values.
`access_path` joins each printed `fylkesnummer` onto the printed
`/kommuneinfo/v1/fylker` path. The official Kommuneinfo OpenAPI names
GET `/fylker/{fylkesnummer}`. License stays null. Publisher stays
null. This is not Kartverket Kommuneinfo OpenAPI collection paths
(`--source kommuneinfo`) and not Enhetsregisteret kommuner
(`--source brkommuner`).

```bash
pda ingest --source kifylker --db data/registry.sqlite --limit 10
pda search Troms --db data/registry.sqlite
pda fetch --dataset kifylker:55 --db data/registry.sqlite
```

`pda fetch` GETs the stored fylke URL. Observation values are copied
from the printed `fylkesnavn` scalar. Other scalars stay as
dimensions. Nested `avgrensningsboks` and `kommuner` objects are not
copied. License stays null. Publisher stays null.

The catalog prints 15 fylker. This walk copies the first ten in
document order. Live ingest listed 10 and inserted 10. Live search
`Troms` returns `kifylker:55`. Live fetch GETs
`https://api.kartverket.no/kommuneinfo/v1/fylker/55`
HTTP 200, 1 row, `fylkesnavn` = `Troms`. `pda methods` is not
applicable. Fylke names are not a numeric time series.
Proof is `data/kifylker_source_proof.json`.

## Enhetsregisteret rollerepresentanter source

`pda ingest --source brrepresent` is another replaceable adapter. It lists
printed representant codes on the official Enhetsregisteret collection
`https://data.brreg.no/enhetsregisteret/api/roller/representanter`,
capped at 10. Dataset ids are the printed `kode` values. `access_path`
joins each printed kode onto that public collection path. Printed
`_links.self.href` values point at `/enhetsregisteret/autorisert-api/`
and that path is HTTP 401, so they are not copied. License stays null.
Publisher stays null. This is not the Enhetsregisteret HAL root
(`--source brreg`), not leftover roller OpenAPI paths
(`--source brroller`), not rolletyper (`--source brrolletype`), not
rollegruppetyper (`--source brrollegruppe`), not organisasjonsformer
(`--source brorgform`), and not kommuner (`--source brkommuner`).

```bash
pda ingest --source brrepresent --db data/registry.sqlite --limit 10
pda search A-aksjonærene --db data/registry.sqlite
pda fetch --dataset brrepresent:A-AK --db data/registry.sqlite
```

`pda fetch` GETs the stored representant URL. Observation values are
copied from the printed `beskrivelse` scalar. Other scalars stay as
dimensions. Nested `_links` objects are not copied. License stays null.
Publisher stays null.

The catalog prints 4 representanter. This walk copies those four in
document order. Live ingest listed 4 and inserted 4. Live search
`A-aksjonærene` returns `brrepresent:A-AK`. Live fetch GETs
`https://data.brreg.no/enhetsregisteret/api/roller/representanter/A-AK`
HTTP 200, 1 row, `beskrivelse` = `Representant for A-aksjonærene`.
`pda methods` is not applicable. Representant names are not a numeric
time series.
Proof is `data/brrepresent_source_proof.json`.

## Enhetsregisteret enheter source

`pda ingest --source brenheter` is another replaceable adapter. It lists
printed `organisasjonsnummer` values from the official Enhetsregisteret
`/enhetsregisteret/api/enheter` collection. The OpenAPI names that
collection GET and GET `/enheter/{enhetorgnr}`. No optional `page`,
`size`, or search filter is added. Dataset ids are the printed
`organisasjonsnummer` values. `access_path` is the printed
`_links.self.href`. License stays null. Publisher stays null. This is
not the Enhetsregisteret HAL root (`--source brreg`), not leftover
organisasjonsformer (`--source brorgform`), not leftover kommuner
(`--source brkommuner`), and not leftover roller lists
(`--source brroller`).

```bash
pda ingest --source brenheter --db data/registry.sqlite --limit 10
pda search ZOTKO --db data/registry.sqlite
pda fetch --dataset brenheter:933365573 --db data/registry.sqlite
```

`pda fetch` GETs the stored enhet URL. Observation values are copied
from the printed `navn` scalar. Other scalars stay as dimensions.
Nested objects and `_links` are not copied. License stays null.
Publisher stays null.

Live ingest 2026-09-01: listed 10, inserted 10. The official first
printed page lists enheter. This walk copies the first ten printed
organisasjonsnummer values in document order. Live search `ZOTKO`
returns `brenheter:933365573`. Live fetch GETs
`https://data.brreg.no/enhetsregisteret/api/enheter/933365573` HTTP 200,
1 navn cell. Sample printed value: `- ZOTKO .NO`. `pda methods` is not
applicable: entity names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/brenheter_source_proof.json`.
## SSB Klass leftover classification variants source

`pda ingest --source ssbvar` is another replaceable adapter. The official
Klass OpenAPI `https://data.ssb.no/api/klass/v3/api-docs` names GET
`/api/klass/v1/variants/{id}` and does not print a variants collection.
Listing copies printed `classificationVariants[].id` and
`_links.self.href` from official version payloads reached through
`https://data.ssb.no/api/klass/v1/classifications`, capped at 10.
Dataset ids are the printed variant `id` values. `access_path` is the
printed variant self href. License stays null. Publisher stays null.
This is not the SSB PxWeb v0 Statbank (`--source ssb`), not PxWebApi 2
(`--source ssbv2`), not Klass classifications (`--source ssclass`), not
Klass versions (`--source ssbver`), and not leftover correspondence
tables (`--source ssbcorr`).

```bash
pda ingest --source ssbvar --db data/registry.sqlite --limit 10
pda search 'begge kjønn' --db data/registry.sqlite
pda fetch --dataset ssbvar:802 --db data/registry.sqlite
```

`pda fetch` GETs the stored variant URL. Observation values are copied
from printed `classificationItems[].name` scalars. Other printed
scalars stay as dimensions. Nested objects are not copied. License
stays null. Publisher stays null.

Live ingest 2026-09-01: listed 10, inserted 10 (official versions print
classification variants; cap 10 copies the first ten unique printed
ids). Live search `begge kjønn` returns `ssbvar:802`. Live fetch GETs
`https://data.ssb.no/api/klass/v1/variants/802` HTTP 200, 3 name cells.
Sample printed value: `Begge kjønn`. `pda methods` is not applicable:
classification-item names, not a numeric time series
(`no observations matched entity/measure; available=[]`).
Proof is `data/ssbvar_source_proof.json`.

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
