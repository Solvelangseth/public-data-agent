# MCP

A stdio MCP server over the tools this repo already has. Search ranks the
local registry. Ask runs the Milestone 10 join. Fetch runs `pda fetch`, or
the existing Klass/11763 join when `join` is true.

The server uses the official Python SDK (`mcp` 2.x, `MCPServer`). Tool
handlers live in `src/public_data_agent/mcp_server.py` and call
`search_report`, `ask`, `fetch_observations`, and `join_bydel_population`.
They pass through stored or fetched cells. They do not invent values.

## Run the server

```bash
pda mcp
```

Cursor / Claude Desktop, after `pip install -e .`:

```json
{
  "mcpServers": {
    "public-data-agent": {
      "command": "/absolute/path/to/.venv/bin/pda",
      "args": ["mcp"],
      "env": { "OPENAI_API_KEY": "sk-..." }
    }
  }
}
```

Use the absolute path to the interpreter's `pda`. A bare `pda` resolves against
whatever PATH the client happens to have, which is usually not the virtualenv.

The client owns stdin/stdout. Do not print logs on stdout.

### The API key is not optional in practice

Without an embedding provider the server still runs and still answers, ranking on
token overlap alone. Measured against the fetchable gold set, that is the difference
between finding the right table for **86% of questions and 40%** — and for naturally
phrased ones, 87% against 33%. A question like "byggekostnader" returns nothing
fetchable at all, while five building-cost tables sit in the registry.

`search` reports which ranking it used in `ranking`, and says what the weaker one costs
in `ranking_note`. Check that field if results look thin.

## Tools

| Tool | Calls | Notes |
| --- | --- | --- |
| `search` | `search_report` | Registry only. Each hit already has publisher, license, access path, original source, and why. |
| `ask` | `ask` | Search plus Klass/11763 join. Lineage is on each ranked row. |
| `fetch` | `fetch_observations` or `join_bydel_population` | Set `join=true` for the existing bydel join. Otherwise this is `pda fetch`. |
| `inspect` | registry + resource index | The shape a fetch is planned from: fields, their roles, sample values, period covered. Answers for a resource nothing has fetched, which `observation_schema` cannot. |
| `get_provenance` | registry | Publisher, licence, access path, stored count. Licence is `null` when unknown, never guessed. |
| `run_analysis` | `analysis` | Aggregates over stored observations only. |
| `create_visualization` | `artifacts` | Writes a chart from stored cells. Needs `path`. |
| `export_artifact` | `export` | Writes CSV from stored cells. Needs `path`. |

## What a caller should do first

`search`, then `inspect` on the chosen dataset, then `fetch` with a selection built from
the fields `inspect` returned. Dimension names are source-defined and cannot be guessed
from a title; a filter invented without inspecting matches no rows and comes back as an
empty result rather than an error.

`fetch` refuses a selection larger than the source allows before sending it, and names
which dimension to narrow. It also refuses a value the table does not publish rather
than dropping it, since a dropped value silently widens the query.

## One-shot call (same handlers)

```bash
pda mcp --call search \
  --query "Hvilke Oslo-bydeler er størst og hvilke vokser mest?" \
  --db data/registry.sqlite \
  --limit 5 \
  --out data/mcp_proof.json
```

That writes the request and the registry rows to `data/mcp_proof.json`.
