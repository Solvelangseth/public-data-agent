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
      "command": "pda",
      "args": ["mcp"]
    }
  }
}
```

The client owns stdin/stdout. Do not print logs on stdout.

## Tools

| Tool | Calls | Notes |
| --- | --- | --- |
| `search` | `search_report` | Registry only. Each hit already has publisher, license, access path, original source, and why. |
| `ask` | `ask` | Search plus Klass/11763 join. Lineage is on each ranked row. |
| `fetch` | `fetch_observations` or `join_bydel_population` | Set `join=true` for the existing bydel join. Otherwise this is `pda fetch`. |

## One-shot call (same handlers)

```bash
pda mcp --call search \
  --query "Hvilke Oslo-bydeler er størst og hvilke vokser mest?" \
  --db data/registry.sqlite \
  --limit 5 \
  --out data/mcp_proof.json
```

That writes the request and the registry rows to `data/mcp_proof.json`.
