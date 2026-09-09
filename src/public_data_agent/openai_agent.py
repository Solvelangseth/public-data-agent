"""OpenAI Responses API adapter for the provider-neutral agent loop."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


TOOL_SCHEMAS = [
    {"type": "function", "name": "search", "description": "Search the local public-data catalog.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"], "additionalProperties": False}},
    {"type": "function", "name": "inspect", "description": "Inspect stored metadata and connector capability.", "parameters": {"type": "object", "properties": {"dataset": {"type": "string"}}, "required": ["dataset"], "additionalProperties": False}},
    {"type": "function", "name": "get_provenance", "description": "Return stored publisher, license, access URL, and observation lineage.", "parameters": {"type": "object", "properties": {"dataset": {"type": "string"}}, "required": ["dataset"], "additionalProperties": False}},
    {"type": "function", "name": "fetch", "description": "Fetch observations from a supported stored access path. With join=true, dataset=a Klass classification id and table=an SSB table id joins them on codes both sides literally store; pass join_key/series to name the result. For Oslo bydel population use the Klass bydel dataset with table=11763. Large tables must be narrowed: pass select={dimension: [codes]} using codes from the error's dimension list, plus from_year/to_year for time.", "parameters": {"type": "object", "properties": {"dataset": {"type": "string"}, "table": {"type": "string"}, "from_year": {"type": "integer"}, "to_year": {"type": "integer"}, "year": {"type": "integer"}, "join": {"type": "boolean"}, "join_key": {"type": "string"}, "series": {"type": "string"}, "select": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}}}, "required": ["dataset", "table"], "additionalProperties": False}},
    {"type": "function", "name": "run_analysis", "description": "Filter, sort, or aggregate stored observations. Filters may use a scalar or an array of exact stored dimension values; measure=value selects numeric cells. Call inspect first and use only dimension names and values listed in its observation_schema. When observation_schema lists more than one series, pass series= to scope to one: dimension names differ between series and mixing them matches nothing. Use sort_by/descending to rank: never order rows yourself. Always read the returned `warnings`.", "parameters": {"type": "object", "properties": {"dataset": {"type": "string"}, "filters": {"type": "object", "additionalProperties": {"type": ["string", "array"]}}, "measure": {"type": "string"}, "group_by": {"type": "array", "items": {"type": "string"}}, "aggregate": {"type": "string", "enum": ["count", "sum", "mean"]}, "sort_by": {"type": "string"}, "descending": {"type": "boolean"}, "series": {"type": "string"}}, "required": ["dataset"], "additionalProperties": False}},
    {"type": "function", "name": "export_artifact", "description": "Export stored results as a local CSV or JSON artifact.", "parameters": {"type": "object", "properties": {"dataset": {"type": "string"}, "path": {"type": "string"}, "format": {"type": "string", "enum": ["csv", "json"]}}, "required": ["dataset", "path"], "additionalProperties": False}},
    {"type": "function", "name": "create_visualization", "description": "Create a local PNG chart from numeric stored results.", "parameters": {"type": "object", "properties": {"dataset": {"type": "string"}, "path": {"type": "string"}, "label": {"type": "string"}}, "required": ["dataset", "path"], "additionalProperties": False}},
]

SYSTEM_INSTRUCTIONS = """You are a Norwegian public-data agent operating under a strict evidence boundary.
Use only datasets returned by search/inspect and only registered connectors.
Never invent or infer numeric values, table ids, periods, licenses, dimensions, or join keys.
Every number in the final answer must come directly from fetch results, stored observations,
joined rows, or a deterministic analysis tool result. Missing evidence means null or a clear
explanation that numbers were not retrieved. Do not fetch landing pages or guess API paths.
For Oslo bydel population, use dataset id `datanorge:0c89041e-ae88-32ef-a765-8e1ccbd64fdd`
with `table=11763` and `join=true` for the registered Klass + SSB exact bydel_code join.
Never rewrite ids (for example, `ssb:11763` includes a colon). Explain sources and
transformations, and mention artifact paths when files are made.

Reading tool results correctly is part of the evidence boundary:
- Call inspect before run_analysis and use only the dimension names and values listed in
  its `observation_schema`. A guessed dimension name matches no rows.
- A field named `sample` is a truncated, unsorted excerpt. Never present it as a ranking
  or as a complete list. Rank only with run_analysis sort_by, or over a full `rows` list.
- Never state a ranking, a total, or a growth figure you computed in your head. Ask the
  tool to sort or aggregate, and report what it returned.
- A tool result's `warnings` list is binding. If it says an aggregate double counts or
  that totals are mixed with their parts, do not report that number; re-run with the
  filter the warning names.
- An empty result is evidence of absence, not licence to substitute another period.
  If the requested period is missing, say so and name the periods that do exist.
- `selection_too_large` is retryable and tells you exactly what to narrow. Re-run fetch
  with `select` limited to the codes the question needs, using codes from the error's
  `dimensions` list. Never retry the same unnarrowed request.
- Fetch only the slice the question needs. Pulling a whole table to read one number
  wastes the source's quota and usually fails outright.
"""


class OpenAIAgentModel:
    def __init__(self, api_key: str, *, model: str = "gpt-4.1-mini", timeout: float = 90.0) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key is empty")
        self.api_key, self.model, self.timeout = api_key, model, timeout

    @classmethod
    def from_env(cls, *, model: str = "gpt-4.1-mini", dotenv: Path | None = None) -> "OpenAIAgentModel":
        key = os.environ.get("OPENAI_API_KEY")
        if not key and dotenv and dotenv.is_file():
            for line in dotenv.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return cls(key, model=model)

    def next_action(self, messages: list[dict[str, Any]], tools: list[str]) -> dict[str, Any]:
        body = {"model": self.model, "instructions": SYSTEM_INSTRUCTIONS, "input": _to_input(messages), "tools": [tool for tool in TOOL_SCHEMAS if tool["name"] in tools]}
        request = Request("https://api.openai.com/v1/responses", data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode())
        for item in payload.get("output", []):
            if item.get("type") == "function_call":
                return {"tool": item["name"], "arguments": json.loads(item.get("arguments", "{}")), "call_id": item.get("call_id")}
        text = payload.get("output_text") or _extract_text(payload)
        return {"final": text}


def _to_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for message in messages:
        if message.get("function_call"):
            call = message["function_call"]
            out.append({"type": "function_call", "call_id": call.get("call_id"), "name": call.get("tool"), "arguments": json.dumps(call.get("arguments", {}), ensure_ascii=False)})
            continue
        if message.get("role") == "tool":
            out.append({"type": "function_call_output", "call_id": message.get("call_id", ""), "output": json.dumps(message.get("content", {}), ensure_ascii=False)})
        else:
            out.append(message)
    return out


def _extract_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(str(content["text"]))
    return "".join(chunks)


class OpenAIIntakeProvider:
    """Reads a Norwegian question into a structured request. Never answers it.

    Shares the credential handling of the agent adapter. The output is validated
    by `intake.validate_intake` before anything downstream sees it, so a model
    that ignores the instructions and returns an answer is rejected rather than
    trusted.
    """

    def __init__(self, api_key: str, *, model: str = "gpt-4.1-mini", timeout: float = 45.0) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key is empty")
        self.api_key, self.model, self.timeout = api_key, model, timeout

    @classmethod
    def from_env(cls, *, model: str = "gpt-4.1-mini", dotenv: Path | None = None) -> "OpenAIIntakeProvider":
        agent = OpenAIAgentModel.from_env(model=model, dotenv=dotenv)
        return cls(agent.api_key, model=model)

    def read_question(self, question: str) -> dict[str, Any]:
        from public_data_agent.intake import INTAKE_INSTRUCTIONS

        body = {
            "model": self.model,
            "instructions": INTAKE_INSTRUCTIONS,
            # json_object format requires the word "json" in the input itself,
            # not only in the instructions.
            "input": [{"role": "user", "content": f"Return JSON for this question:\n{question}"}],
            "text": {"format": {"type": "json_object"}},
        }
        request = Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode())
        text = payload.get("output_text") or _extract_text(payload)
        if not text:
            raise ValueError("intake provider returned no text")
        return json.loads(text)


class OpenAIEmbeddingProvider:
    """Embeds text for ranking only.

    A vector reorders candidates and surfaces ones lexical overlap missed. It
    never authorises a fetch and never supplies a value: those still come from
    a registered connector through the tool boundary.
    """

    DEFAULT_MODEL = "text-embedding-3-small"

    def __init__(self, api_key: str, *, model: str = DEFAULT_MODEL, timeout: float = 120.0) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key is empty")
        self.api_key, self.model, self.timeout = api_key, model, timeout

    @classmethod
    def from_env(cls, *, model: str = DEFAULT_MODEL, dotenv: Path | None = None) -> "OpenAIEmbeddingProvider":
        agent = OpenAIAgentModel.from_env(dotenv=dotenv)
        return cls(agent.api_key, model=model)

    def embed(self, texts: Any) -> list[list[float]]:
        items = [str(text) for text in texts]
        if not items:
            return []
        body = {"model": self.model, "input": items}
        request = Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode())
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != len(items):
            raise ValueError("embedding response did not cover every input")
        # The API may return items out of order; index is authoritative.
        ordered = sorted(data, key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in ordered]


class OpenAIQueryRewriter:
    """Asks the model what the catalogue would call the subject of a question.

    Shares the credential handling of the other adapters. Returns search terms
    and nothing else: `rewrite.clean_terms` discards anything that is not a
    short Norwegian phrase, so a model that answers the question instead of
    translating it contributes nothing rather than something false.
    """

    def __init__(self, api_key: str, *, model: str = "gpt-4.1-mini", timeout: float = 45.0) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key is empty")
        self.api_key, self.model, self.timeout = api_key, model, timeout

    @classmethod
    def from_env(
        cls, *, model: str = "gpt-4.1-mini", dotenv: Path | None = None
    ) -> "OpenAIQueryRewriter":
        agent = OpenAIAgentModel.from_env(model=model, dotenv=dotenv)
        return cls(agent.api_key, model=model)

    def terms(self, query: str) -> list[str]:
        from public_data_agent.rewrite import REWRITE_INSTRUCTIONS, clean_terms

        body = {
            "model": self.model,
            "instructions": REWRITE_INSTRUCTIONS,
            # json_object format requires the word "json" in the input itself.
            "input": [{"role": "user", "content": f"Return json search terms for:\n{query}"}],
            "text": {"format": {"type": "json_object"}},
            # Left to itself the model returns different terms for the same
            # question -- 26 of 123 rewrites changed between two runs, which
            # moved held-out recall@5 from 0.865 to 0.892. A search backend
            # should answer the same question the same way, and a measurement
            # of it should be repeatable.
            "temperature": 0,
        }
        request = Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode())
        return clean_terms(payload.get("output_text") or _extract_text(payload))
