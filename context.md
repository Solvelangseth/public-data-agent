# Public Data Agent — handover context

This document is the working context for Sølve and any future contributor or coding
agent. Read it before changing the planner, connectors, registry, dashboard, or MCP
surface. It describes the intended product and the current implementation as of
September 2026.

## 1. Product vision

Public Data Agent is an AI-native data layer for Norwegian public data. A person (or a
coding agent connected through MCP/API) should be able to ask a natural-language question
in Norwegian and receive a reproducible plan, fetched data, deterministic transformations,
charts/files, and an explanation with provenance.

The long-term product is a better, agent-friendly version of the public-data catalogue:

1. Understand the user's question using an LLM and/or embeddings.
2. Find the best matching datasets in our local catalogue.
3. Select only sources that have a registered, usable connector.
4. Fetch the exact observations needed.
5. Filter, reshape, join, aggregate, calculate, and visualize deterministically.
6. Return values, files, charts, and a human-readable explanation with lineage.
7. Expose the same capabilities as a local CLI, browser dashboard, MCP server, and later
   a stable API.

The model is a planner and interface, not a source of facts. The data/tool layer is the
trust boundary.

## 2. Non-negotiable rules

These rules apply to code, prompts, tests, dashboard behavior, and MCP/API responses:

- Never invent observation values, table IDs, periods/years, licenses, dimensions, or
  join keys.
- Every numeric answer must be traceable to fetched observations, stored observations,
  `joined_rows`, or a deterministic method output.
- Missing evidence is `null` plus a reason, or an explicit statement that numbers were not
  retrieved. A plausible guess is never acceptable.
- Fetch only through a connector already implemented and registered in the project.
  A catalogue landing page is not automatically a fetchable API.
- Do not silently turn a failed fetch into an answer. Report the failure and continue with
  safe alternatives, or stop truthfully.
- Licenses remain `null` when unknown. In particular, SSB table 11763 intentionally has a
  null license in the local registry.
- Joins require a stored/documented key. The Oslo demo joins only on exact `bydel_code`.
- Methods may calculate only from observations that actually exist and have the required
  periods. Division by missing/zero bases yields null plus a reason.
- No `offentligdata.no` work: do not fetch, scrape, compare, or build competitor features.
- Do not ingest new `source_id`s unless Sølve explicitly names one substantial numeric
  table. Small WMS, lookup, JSON, GIS, and publisher catalogue additions are out of scope.
- Do not build a hosted BI/Power BI clone. The first UI is a local test dashboard.
- Keep CSV lineage columns and provenance in all exports.

## 3. Current repository and branch

Repository: `Solvelangseth/public-data-agent`.

Work from the latest `main` snapshot and use the current feature branch
`codex/ai-planner`. Do not use a remote named `Origin`; push with the repository URL or
the configured non-Origin remote. Do not clone another repository or mint a new one.

The open PR is the AI planner/agent work. Recent relevant commits include:

- `cd98ba1` provider-neutral agent loop
- `b9274a7` OpenAI Responses agent adapter and tool-call history
- `6d1253f` dashboard Run agent action
- `94d7b43` connector-aware search and honest fetch failures
- `ee744ce` expose the registered Oslo join to the model
- `7103e06` fixed evidence-boundary system instructions

`.env` and `.env.*` are ignored. Never print or commit `OPENAI_API_KEY`.

## 4. Architecture

### Catalogue and registry

- `src/public_data_agent/harvest.py` runs catalogue ingestion.
- `src/public_data_agent/sources/datanorge.py` harvests Data.norge/Felles datakatalog.
- Membership comes from SPARQL (`https://sparql.fellesdatakatalog.digdir.no`).
- Full metadata comes from Resource Service
  (`https://resource.api.fellesdatakatalog.digdir.no`).
- The Data.norge Search API is not the harvest system of record.
- `src/public_data_agent/registry.py` stores normalized metadata in SQLite.
- `src/public_data_agent/schema.sql` defines `datasets`, `harvest_runs`, raw harvested
  payloads, enrichments, fetch runs, observations, joins, and joined rows.
- Default DB: `data/registry.sqlite` (large, local, gitignored).

The live registry currently contains roughly 9,100 Data.norge datasets plus observation
identity rows. It is disposable/rebuildable; do not commit it.

### Discovery

- `search.py` performs deterministic token-overlap ranking over stored fields.
- Ranking weights: title 10, keyword 5, theme 5, description 2.
- It supports token decomposition, synonyms/compound splits, and coverage reporting.
- Search quality must not regress: the 65-question harness previously measured R@5 about
  0.892 and R@10 about 0.939.
- `mcp_server.tool_search` adds connector capability metadata and explicit registered
  connector candidates. This is intentionally separate from catalogue ranking so a model
  can distinguish “relevant description” from “fetchable observations”.

Embeddings and LLM ranking may improve discovery later. They must remain candidates/ranking
helpers; they cannot authorize an unregistered fetch or provide factual values.

### Connectors and fetch

- `fetch.py` is the connector dispatch boundary. `can_fetch_access_path()` is the cheap,
  no-network capability check.
- Existing important connectors include:
  - `ssb_pxweb.py`: SSB PxWeb, especially table `11763`.
  - `ssb_klass.py`: SSB Klass, Oslo bydelsinndeling version `1168`.
  - `fetch.py` dispatch for the other already-present source adapters.
- `fetch_observations()` performs real HTTP fetches and records lineage in observations.
- `mcp_server.tool_fetch` rejects unsupported access paths before network I/O and returns
  `error.code = unsupported_access_path` with `numbers_retrieved = false`.
- Do not derive a table endpoint from a catalogue title or landing-page URL by guesswork.

### Oslo reference workflow

The default demo question is:

`Hvilke Oslo-bydeler er størst og hvilke vokser mest?`

The supported path is:

1. SSB Klass dataset `datanorge:0c89041e-ae88-32ef-a765-8e1ccbd64fdd`, version `1168`,
   supplies code-to-name mappings.
2. SSB table `ssb:11763` supplies population observations for 2024 and 2025 (or the two
   periods actually requested and present).
3. `join.py` performs an inner join on exact `bydel_code`.
4. `methods/derive.py` computes YoY only from the two joined cells.
5. `ask.py` ranks largest population and highest growth.
6. `export.py`/artifact tools produce CSV and charts with lineage.

Do not hardcode which bydel is largest. Recompute it from cells. The observed August proof
had Grünerløkka largest in 2025, but that is not a constant.

### Planning and agent execution

- `planner.py` contains the deterministic validated plan model and demo fallback.
- `llm_planner.py` defines provider-neutral plan validation. Model output is limited to
  operation steps and candidate IDs; factual values are forbidden.
- `openai_planner.py` optionally calls the OpenAI Responses API for structured plans.
- `openai_agent.py` calls the OpenAI Responses API with function tools and a fixed
  `SYSTEM_INSTRUCTIONS` evidence boundary.
- `agent_loop.py` is provider-neutral and bounded. It records user, assistant function-call,
  and tool messages. At a step limit it returns an explicit no-numbers fallback rather than
  a blank answer.
- Available tool capabilities are search, inspect, fetch, run_analysis,
  create_visualization, export_artifact, and get_provenance (plus legacy ask/fetch MCP
  operations). Tools are the enforcement layer.

The LLM may parse Norwegian intent and choose tools. It may not claim facts that no tool
returned. Structured output helps shape but does not prove semantics; validators and tool
checks remain mandatory.

### Analysis, methods, and artifacts

- `analysis.py` filters and aggregates stored observation rows (`count`, `sum`, `mean`),
  with optional grouping and sorting.
- `join.py` contains the documented Oslo join.
- `methods/` contains deterministic derivations such as YoY and index. Preserve lineage.
- `artifacts.py` writes CSV/JSON/PNG locally. Paths must be returned to the caller.
- `export.py` preserves provenance/lineage columns for `pda ask --out file.csv`.

### Interfaces

- CLI entry point: `public_data_agent.cli:main` (console command is normally `pda` after
  editable installation).
- Dashboard: `pda dashboard` or `python -m public_data_agent.cli dashboard`; local only,
  usually `http://127.0.0.1:8765`.
- MCP implementation: `mcp_server.py`; inspect `MCP.md` for stdio details.
- Future API/MCP work should reuse the same tool contracts and provenance, not create a
  second data-processing implementation.

## 5. Agent system prompt and behavior

`openai_agent.SYSTEM_INSTRUCTIONS` is an invariant. It tells the model to use only
registered datasets/connectors, never invent factual fields, require fetch/observation
evidence for every number, use the Oslo exact join, and explain sources/transformations.
Keep this instruction provider-independent in meaning if another model adapter is added.

The model should normally do:

`search → inspect connector candidates → fetch (possibly join=true) → run_analysis/method →
create_visualization/export_artifact → get_provenance → final explanation`.

If a source is not fetchable, the final response must say that no numbers were retrieved and
list ranked catalogue hits or the reason for refusal. It must not retry guessed paths.

## 6. Local setup and commands

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Create `.env` locally (never commit it):

```text
OPENAI_API_KEY=your-key-here
```

Load it for shell commands when needed:

```bash
set -a; source .env; set +a
```

Useful commands:

```bash
pda status --db data/registry.sqlite
pda stats --db data/registry.sqlite
pda search "befolkning Oslo bydel" --db data/registry.sqlite
pda ask "Hvilke Oslo-bydeler er størst og hvilke vokser mest?" --db data/registry.sqlite
pda ask "Hvilke Oslo-bydeler er størst og hvilke vokser mest?" --out oslo.csv
pda dashboard --db data/registry.sqlite
pda agent "Finn dokumentert befolkning i Oslo-bydeler ..." --steps 8
pytest
```

If the `pda` console script is unavailable, use `PYTHONPATH=src:. python` and call
`public_data_agent.cli.main(...)` or install the package editable.

## 7. Test contract

Run the full suite before handing off:

```bash
PYTHONPATH=src:. pytest -q
```

Tests must cover:

- registry/harvest normalization and null/missing-field reasons;
- search ranking and benchmark recall;
- connector capability checks and unsupported fetch refusal;
- observation lineage and HTTP provenance;
- exact joins and deterministic methods;
- rejection of model plans containing factual values or unapproved IDs;
- agent function-call history, step bounds, and truthful fallback;
- MCP tools, CSV/JSON/PNG artifacts, and dashboard endpoints.

Numeric-answer tests must fail if a value does not originate in observations, joined rows,
or a method output. Do not weaken those tests to make an LLM demo pass.

The full suite has recently passed 1770 tests (one expected skip and one deselection); a
matplotlib `tight_layout` warning in `methods/emit.py` is known and non-fatal.

## 8. Current known gaps

- Token-overlap search can rank images, landing pages, and unrelated catalogue records too
  highly for broad Norwegian queries. Connector candidates now mitigate this for the agent;
  improve ranking carefully and re-run the 65-question benchmark.
- Most Data.norge records have no variable/column list and spatial metadata is frequently
  absent. Do not infer either field.
- Oslo municipality's statbank is catalogued but currently not a registered working
  observation connector in this project; it must be reported as unavailable rather than
  guessed into a PxWeb path.
- The general agent still needs stronger operation planning for arbitrary datasets,
  especially choosing dimensions/periods from fetched metadata and chaining artifacts.
- OpenAI API calls require the user's local key. The deterministic demo and all tests work
  without an LLM key.
- The dashboard is a development harness, not production hosting or authentication.
- No new small official endpoint ingestion is needed for the first planner slice.

## 9. Recommended next development sequence

1. Re-run the challenging dashboard prompt and verify the model chooses the registered
   Klass + SSB join, not a landing page.
2. Add an end-to-end mocked agent test asserting search → inspect → join/fetch → analysis →
   export/visualization and provenance, with no numeric hallucination path.
3. Improve tool result contracts so the model can see available periods/dimensions after a
   fetch and select the two latest periods from returned metadata rather than guessing.
4. Add a bounded retry/recovery policy for connector errors (retry only when `retryable` is
   true; never retry unsupported paths).
5. Make dashboard artifact paths clickable/downloadable and show a compact provenance panel.
6. Add provider-neutral embedding retrieval/reranking behind an optional dependency and
   benchmark it against the existing search; retain deterministic fallback.
7. Expand methods only when a new stored numeric series with at least two periods is found.
8. Stabilize MCP schemas and document connection examples for Claude Code and other agents.
9. Add an HTTP API only after the MCP/tool contracts and provenance behavior are stable.

## 10. Definition of done for the first planner slice

- A Norwegian question produces a validated plan and tool trace.
- The demo question still returns recomputed 2024/2025 Oslo bydel size and YoY ranks.
- The planner selects tools rather than always hardcoding the demo path.
- Unsupported sources produce ranked hits plus an explicit “numbers not retrieved” message.
- No number can appear unless it came from observations/joined rows/methods.
- CSV export retains lineage/provenance columns; visualization is reproducible locally.
- Full tests pass and README/context instructions explain local operation.

When uncertain, preserve evidence and provenance first, ask for clarification only when a
missing choice changes the source or operation materially, and prefer a truthful refusal to
an impressive but unsupported answer.
