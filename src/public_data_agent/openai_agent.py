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
    {"type": "function", "name": "fetch", "description": "Fetch observations from a supported stored access path.", "parameters": {"type": "object", "properties": {"dataset": {"type": "string"}, "table": {"type": "string"}, "from_year": {"type": "integer"}, "to_year": {"type": "integer"}}, "required": ["dataset", "table"], "additionalProperties": False}},
    {"type": "function", "name": "run_analysis", "description": "Filter or aggregate stored observations.", "parameters": {"type": "object", "properties": {"dataset": {"type": "string"}, "filters": {"type": "object", "additionalProperties": {"type": "string"}}, "measure": {"type": "string"}, "group_by": {"type": "array", "items": {"type": "string"}}, "aggregate": {"type": "string", "enum": ["count", "sum", "mean"]}}, "required": ["dataset"], "additionalProperties": False}},
    {"type": "function", "name": "export_artifact", "description": "Export stored results as a local CSV or JSON artifact.", "parameters": {"type": "object", "properties": {"dataset": {"type": "string"}, "path": {"type": "string"}, "format": {"type": "string", "enum": ["csv", "json"]}}, "required": ["dataset", "path"], "additionalProperties": False}},
    {"type": "function", "name": "create_visualization", "description": "Create a local PNG chart from numeric stored results.", "parameters": {"type": "object", "properties": {"dataset": {"type": "string"}, "path": {"type": "string"}, "label": {"type": "string"}}, "required": ["dataset", "path"], "additionalProperties": False}},
]


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
        body = {"model": self.model, "input": _to_input(messages), "tools": [tool for tool in TOOL_SCHEMAS if tool["name"] in tools]}
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
