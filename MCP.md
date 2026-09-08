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

## Embedding elsewhere (Colab, or any GPU)

Ranking quality depends on the embedding index, and building one over 13,281 datasets
is hours on a laptop CPU and minutes on a rented GPU. Only the bulk build has to move:
a query is one short text and embeds fast anywhere, so the model still runs locally at
query time.

**1. Export what to embed**

```bash
pda embed --db data/registry.sqlite --export texts.jsonl
```

One JSON object per line: `dataset_id`, `text`, `text_hash`. About 6 MB.

**2. Embed it on a GPU**

```python
# Colab, GPU runtime
!pip -q install sentence-transformers
import json, torch
from sentence_transformers import SentenceTransformer

MODEL = "NbAiLab/nb-sbert-base"          # or intfloat/multilingual-e5-large
rows  = [json.loads(l) for l in open("texts.jsonl")]
model = SentenceTransformer(MODEL, device="cuda" if torch.cuda.is_available() else "cpu")

vectors = model.encode([r["text"] for r in rows], batch_size=64,
                       normalize_embeddings=True, show_progress_bar=True)

with open("vectors.jsonl", "w") as out:
    for row, vector in zip(rows, vectors):
        out.write(json.dumps({"dataset_id": row["dataset_id"],
                              "text_hash": row["text_hash"],
                              "vector": [float(x) for x in vector]}) + "\n")
```

**3. Load the vectors back**

```bash
pda embed --db data/registry.sqlite --model NbAiLab/nb-sbert-base \
          --import-vectors vectors.jsonl
```

Vectors are stored under their own model name and **do not replace** an existing index,
so two models can be compared on the same corpus. A vector is refused when the dataset's
text no longer hashes to what was exported: the row changed after export, and ranking a
resource by a description it no longer has is worse than not ranking it.

**4. Query with the same model**

`semantic_ranking(..., model=...)` selects the index. The model has to be loadable
locally to embed the query — one short text, fast on a laptop — so this splits the work
rather than removing the dependency.

Whether a Norwegian model beats `text-embedding-3-small` is an open question, not an
assumption. The current stack scores recall@5 0.857 against `data/heldout_gold.json`,
and the failures left are Norwegian vocabulary distance — `domfelte` against `straffede
personer`, `yrkesdeltakelse` against `arbeidsstyrken`. Measure before switching.
