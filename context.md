# Public Data Agent — working context

Read this before changing search, connectors, the registry, the agent, or the MCP
surface. It describes what the product is for and how the pieces serve that. It is
not a changelog; specific past defects live in git history and `GAPS.md`.

## 1. What we are building

An AI-native data layer over Norwegian public data. Someone asks a question in plain
Norwegian — through the CLI, the dashboard, or an agent over MCP — and gets back real
numbers, with the lineage that proves where they came from.

The bar is **generality**. Any reasonable question about Norwegian public statistics
should work, not a curated list of them. A question about unemployment, rents,
emissions, or fishing quotas should travel the same path as a question about
population. If a question only works because someone special-cased it, that is a bug,
not a feature.

The end state is a system that can:

1. understand a Norwegian question,
2. find the datasets that can actually answer it,
3. retrieve exactly the observations needed,
4. join across sources on real shared keys,
5. derive the figures asked for — growth, shares, indices, rankings,
6. return values, files and charts with a truthful explanation.

The model plans and explains. It never supplies facts. Tools are the trust boundary.

## 2. Non-negotiable rules

These bind code, prompts, tests, and every interface:

- Never invent observation values, table ids, periods, licences, dimensions, or join
  keys.
- Every number must trace to fetched observations, stored observations, joined rows,
  or a deterministic method output.
- Missing evidence is `null` plus a reason, or a plain statement that numbers were not
  retrieved. A plausible guess is never acceptable.
- Fetch only through a registered connector. A catalogue landing page is not an API.
- Never turn a failed fetch into an answer. Report the failure, then continue with a
  real alternative or stop truthfully.
- Licences stay `null` when unknown.
- Joins require a key both sides actually store. Discover it by matching stored values;
  never assume one from a code's shape or a column's name.
- Methods calculate only from observations that exist with the periods required.
  Division by a missing or zero base yields null plus a reason.
- Aggregation must not silently double count. Overlapping categories and "total" rows
  mixed with their parts are a warning, not a number.
- Adding a data source must not silently re-weight the ranker.
- No `offentligdata.no` work.
- Keep lineage columns and provenance in every export.

## 3. Architecture

### Registry

`registry.py` over SQLite (`data/registry.sqlite`, gitignored and rebuildable).
`schema.sql` defines datasets, harvest runs, raw payloads, enrichments, fetch runs,
observations, joins and joined rows.

Observations carry a **`series`** tag naming the connector projection that wrote them.
One dataset can hold several projections of the same upstream table — a raw full fetch
and a joined subset — whose dimension names differ. Without the tag they blend into one
pool and a filter valid for one silently matches none. Scope analysis by `series`.

### Catalogue sources

- `sources/datanorge.py` — Data.norge / Felles datakatalog (~9,100 records). Broad
  descriptive coverage; most rows are not fetchable.
- `sources/ssbtable.py` — SSB PxWeb table catalogue (~3,800 numeric tables). These are
  the rows that can actually return observations, and they carry dimension names and
  period coverage that the Data.norge records lack.

Harvest with `pda ingest --source <id>`.

### Discovery

`search.py` ranks by token overlap: title 10, keyword 5, theme 5, description 2, with
AND-decomposition, Norwegian stopwords and inflection folding.

Results come back in **two lanes**, ranked by the same score but not competing for the
same slots: `observation_sources` (a registered connector can return numbers) and
`catalogue_records` (describes data we cannot retrieve). They answer different
questions — "what can answer me" and "what exists" — and a single mixed list makes
every ranking change rob one to pay the other. Lanes are filled from a deeper ranking,
because a lane cannot be filled from a list already truncated to the other's winners.

Two measurements, and both matter:

- `pda benchmark` — ranking against 65 gold Data.norge questions, scored on the
  **catalogue lane**, since every gold answer is a catalogue record. R@5 ≈ 0.892,
  R@10 ≈ 0.938. **Must not regress.**
- `run_answerable` over `data/answerable_questions.json` — how often a question reaches
  a dataset we can actually pull numbers from. ≈ 0.87 across 30 topic-spread questions.

The first measures ranking; only the second measures whether the product works. A
change that improves one and breaks the other has not been validated. Check both — a
single green metric has already hidden a broken product once.

### Connectors and fetch

`fetch.py` is the dispatch boundary.

- `classify_access_path()` reports what a stored URL can actually yield:
  `observations`, `lookup` (code lists — join keys, not facts), `unverified` (a
  connector matches but the payload shape is unconfirmed), or `none`. Prefer it over
  the older boolean `can_fetch_access_path()`, which says yes to bare hostnames,
  documentation pages and map endpoints.
- `fetch_observations()` performs real HTTP and records lineage. Pass
  `select={dimension: [codes]}` to fetch a slice; an unknown dimension or value is an
  error, never a silent widening. A query above the source's cell limit is refused
  before the request with the per-dimension sizes, so a caller can narrow instead of
  retrying. Fetch the slice the question needs, not the whole table.
- Tools reject unsupported access paths before any network call.

Never derive an endpoint from a catalogue title or landing page by guesswork.

### Joins

`join.py`. `join_classification_to_table()` joins any SSB Klass classification to any
SSB PxWeb table. The key is **discovered**: the classification's stored codes are
matched against the table's stored dimension values, exact string equality only. No
overlap means the two do not share a key, and the join refuses rather than inventing
glue. `join_bydel_population()` is a thin Oslo-shaped wrapper over it.

Klass code lists (bydel, kommune, fylke, land, yrke) are the shared key vocabulary for
most of SSB. Widening join coverage usually means adding a classification, not new join
code.

### Analysis, methods, artifacts

- `analysis.py` filters, sorts and aggregates stored observations. `describe_observations()`
  reports the stored dimensions, their values, measures and series so a caller can build
  a filter that matches rows instead of guessing a name that matches none. Results carry
  `warnings` explaining an empty result or an aggregate that would double count.
  **Warnings are binding** — do not report a number the tool warned about.
- `methods/` holds deterministic derivations (YoY, period change, index, rank) with
  lineage. `executor.execute_plan` runs them: a `join` step joins a Klass
  classification to a table on a discovered key, and a `derive` step computes
  growth and rank over whatever earlier steps produced. Ranking and growth are
  therefore method output, never arithmetic done while writing an answer.
- `artifacts.py` / `export.py` write CSV, JSON and PNG, preserving provenance.

### Pipeline

The run is a small graph, and most of its nodes are plain functions. A model is
asked only where language is the problem; every routing decision is computed.

`intake.py` reads the question — terms, geography, period, whether it is a
lookup or an open investigation, and whether anything is unclear enough to ask
about. It runs before any search, so it has no datasets and no numbers, and
`validate_intake` rejects output containing either. `read_question()` is a
deterministic fallback that needs no model, so the pipeline and the tests work
without a key.

`pipeline.assess_readiness` then decides whether any registered source could
answer, before a planner is asked to plan. Three stop outcomes:
`nothing_found`, `catalogue_only` (records describe data nothing can fetch),
`lookup_only` (code lists carry join keys, never measures). Models judge their
own readiness poorly, so this gate is deterministic and uses signals search and
the capability classifier already compute.

Two rules hold the graph together:

- **State carries handles, not prose.** Nodes pass dataset ids, series tags and
  tool results. A summary sentence handed between nodes becomes a fact nobody
  can check.
- **Uncovered query terms are reported, never used to refuse.** Search indexes
  titles and keywords, not dimension *values*, so "Trondheim" is uncovered even
  when a table answers for it via `select=`.

`route()` then picks the next node by rule:

- **clarify** — intake asked something; stop and ask. Checked first, because a
  question we have misread is not evidence that data is missing.
- **stop** — the gate found nothing that can answer.
- **specific** — a lookup, a ranking, a comparison. `run_specific` plans over
  the gate's observation sources only, validates the plan, then executes it
  deterministically.
- **exploratory** — answering means deciding which variables to relate. Driven
  by the bounded tool loop, since which datasets matter is part of the question
  and cannot be planned up front. Same tools, same trust boundary.

A route that cannot run for want of a provider says so; it never falls through
to another path, because silently answering a different way makes a run
irreproducible.

`pda check "<question>"` runs intake and the gate. `pda run "<question>"` runs
the whole graph. Both exit 2 when a question is not answered.

### Agent and interfaces

- `agent_loop.py` — provider-neutral, bounded tool loop, fronted by the
  readiness gate (`gate=False` to bypass it for loop-level tests). Tool errors come back to the
  model as retryable results; at the step limit it returns an explicit no-numbers
  answer rather than a blank one.
- `openai_agent.py` — OpenAI Responses adapter and the `SYSTEM_INSTRUCTIONS` evidence
  boundary. Keep those instructions general: they teach how to read tool results
  honestly, not how to answer one particular question.
- Tools: search, inspect, fetch, run_analysis, create_visualization, export_artifact,
  get_provenance.
- CLI `pda`, local dashboard `pda dashboard`, MCP via `mcp_server.py` (see `MCP.md`).

The expected shape is: **search → inspect → fetch → run_analysis/method →
visualize/export → explain**. If a source is not fetchable, say so and list what was
found. Never retry a guessed path.

## 4. Working rules for changes

- Prefer generalising an existing path over adding a special case. A demo-specific
  branch is a signal that the general path is missing.
- Tool results are the model's only view of the data. When the model behaves badly,
  first ask whether the tool told it the truth clearly enough — an unlabelled excerpt
  or an unexplained empty result is a tool bug, not a prompt bug.
- Never widen a tool's contract silently. Unknown arguments are an error, not a no-op.
- Run both measurements before claiming a search change is safe.

## 5. Local setup

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
```

`.env` holds `OPENAI_API_KEY` locally and is never committed. Load with
`set -a; source .env; set +a`.

```bash
pda status  --db data/registry.sqlite
pda search  "arbeidsledighet" --db data/registry.sqlite
pda ingest  --source ssbtable --db data/registry.sqlite
pda ask     "..." --db data/registry.sqlite --out out.csv
pda agent   "..." --steps 8
pda dashboard --db data/registry.sqlite
PYTHONPATH=src:. pytest -q
```

The deterministic paths and the whole test suite work without an LLM key.

## 6. Test contract

Tests must cover registry/harvest normalisation, search ranking and recall, connector
capability and honest refusal, observation lineage, discovered-key joins, deterministic
methods, rejection of model plans containing facts, agent step bounds and truthful
fallback, MCP tools, artifacts, and dashboard endpoints.

A numeric-answer test must fail if a value did not originate in observations, joined
rows, or a method output. Do not weaken those tests to make a demo pass. If a proof
test fails, first ask whether it is reporting a real defect.

## 7. Where the ceiling currently is

- **Methods are not reachable from the agent.** `methods/derive.py` computes YoY, index
  and rank deterministically, but no tool exposes it, so growth questions are answered
  by arithmetic done in the model's head.
- **Norwegian compounds miss.** Queries like `byggekostnader` or `kraftproduksjon` do
  not match stored `bygge`/`kostnader` tokens. A vocabulary-driven split (only split
  when both halves exist in the index) generalises better than a hand-written list.
- **Retrieval is lexical only.** `embeddings.py` has a provider-neutral scaffold.
  Embeddings must stay a ranking aid: they can never authorise a fetch or supply a value.
- **Most Data.norge records carry no variable list or spatial metadata.** Do not infer
  either.
- The dashboard is a development harness, not hosting or auth.
