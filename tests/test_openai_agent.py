from __future__ import annotations

import json

from public_data_agent.openai_agent import OpenAIAgentModel, _to_input


def test_tool_result_messages_use_responses_function_call_output() -> None:
    result = _to_input([{"role": "user", "content": "x"}, {"role": "tool", "name": "search", "call_id": "c1", "content": {"ok": True}}])
    assert result[1]["type"] == "function_call_output"
    assert result[1]["call_id"] == "c1"


def test_openai_agent_parses_function_call(monkeypatch) -> None:
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps({"output": [{"type": "function_call", "name": "search", "call_id": "c1", "arguments": '{"query":"Oslo"}'}]}).encode()

    monkeypatch.setattr("public_data_agent.openai_agent.urlopen", lambda request, timeout: Response())
    action = OpenAIAgentModel("secret").next_action([{"role": "user", "content": "find Oslo"}], ["search"])
    assert action == {"tool": "search", "arguments": {"query": "Oslo"}, "call_id": "c1"}
