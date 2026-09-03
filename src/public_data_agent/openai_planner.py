"""Optional OpenAI-backed plan provider.

This adapter interprets questions only. The returned JSON must still pass
``llm_planner.validate_model_plan`` before execution.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


SYSTEM_PROMPT = """You produce a JSON execution plan for a public-data agent.
Use only the supplied catalog candidates. Never include factual values,
observations, invented IDs, licenses, years, or join keys. Return exactly one
JSON object with this shape:
{"intent":"...","search_query":"...","requirements":["..."],
"steps":[{"kind":"search|fetch|filter|reshape|join|derive|visualize|export",
"reason":"...","dataset_id":"candidate id or omit",
"table_id":"candidate table id or omit","periods":[2024,2025]}],
"refusal_reason":null}
Requirements must be an array of strings. Use only the listed step kinds.
Do not answer the question; describe operations for a deterministic executor.
"""


class OpenAIPlanProvider:
    def __init__(self, api_key: str, *, model: str = "gpt-4.1-mini", timeout: float = 60.0) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key is empty")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @classmethod
    def from_env(cls, *, model: str = "gpt-4.1-mini", dotenv: Path | None = None) -> "OpenAIPlanProvider":
        key = os.environ.get("OPENAI_API_KEY")
        if not key and dotenv:
            key = _read_dotenv_key(dotenv)
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return cls(key, model=model)

    def make_plan(self, question: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        body = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps({"question": question, "candidates": candidates}, ensure_ascii=False)}],
                },
            ],
            "text": {"format": {"type": "json_object"}},
        }
        request = Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload.get("output_text") or _extract_output_text(payload)
        if not text:
            raise RuntimeError("OpenAI response did not contain plan JSON")
        result = json.loads(text)
        if not isinstance(result, dict):
            raise RuntimeError("OpenAI plan response was not a JSON object")
        return result


def _extract_output_text(payload: dict[str, Any]) -> str | None:
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(str(content["text"]))
    return "".join(chunks) or None


def _read_dotenv_key(path: Path) -> str | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("OPENAI_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value or None
    return None
