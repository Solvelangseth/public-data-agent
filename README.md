# public-data-agent

An AI-native data layer for Norwegian open data.

Today, answering a question with public data means finding the right portal, the right
dataset, the right API, downloading it, combining sources, and doing the analysis by hand.
The goal here is that you describe what you want to find out — in plain language — and the
system finds the right data for you.

> *Which Norwegian municipalities have had strong population growth, high housing
> construction, and relatively few construction companies over the last five years?*

## Principles

- **Data first, AI second.** LLMs handle intent, semantics and planning. Retrieval, joins,
  filtering, aggregation and math stay deterministic. The model never guesses factual values.
- **Sources are replaceable.** Data.norge, SSB, BRREG and others are ingestion sources into
  *our* registry. Search runs on the registry, not on someone else's search API.
- **Provenance from day one.** Every result can say what it is, who publishes it, why it was
  selected, when it was last updated, how to access it, and under which license.

## Architecture (long term)

1. **Dataset discovery** — find what data exists
2. **Data access** — retrieve the actual rows
3. **Semantic / entity layer** — what the data represents and how datasets relate
4. **Analysis engine** — joins, filtering, feature engineering
5. **Agent layer** — understand the goal, plan the analysis
6. **Interfaces** — web, API, MCP, CSV/Excel, external AI agents

## MVP — Layer 1 only

Natural language in, ranked relevant datasets out. The MVP does not answer the analytical
question. It answers: **"which data do I need in order to answer this?"**

Scope:

- Ingest catalogue metadata into our own dataset registry (identity, description, access,
  time coverage, geography, structure)
- Enrich metadata separately from the original (topics, aliases, geographic level, what
  questions the dataset can answer) — enrichment never overwrites source metadata
- Search over enriched documents, not just titles
- Decompose multi-part questions into separate information requirements
- Check coverage, and say *"I am missing data for X"* rather than settling for a weak proxy
- Show original metadata and system interpretation as clearly distinct
- Collect feedback from day one as future evaluation data

Explicitly **not** in the MVP: row-level retrieval, SQL execution, joins, feature
engineering, charts, export, private user data, MCP, billing, enterprise auth.

## Measuring it

A benchmark of 50–100 manually verified questions — simple, synonym, indirect,
multi-requirement, and hard phrasings — scored on Recall@5, Recall@10, MRR, and
**requirement coverage** for multi-part questions. Data.norge's own AI search is the baseline.

## Milestones

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

## Definition of success

A user submits a complex question requiring several kinds of information, and the system
understands the requirements, finds concrete relevant datasets, ranks the best ones highly,
explains why, detects what it did *not* cover, searches again where coverage is weak, shows
original sources — and does this clearly better than a plain dataset search box.

The first version does not need to be *"AI that analyzes all Norwegian public data."* It only
needs to prove: **describe what you are trying to find out, and we will find the right data.**

Direction of travel: finding data → accessing data → combining data → analyzing data →
agentic data infrastructure.
