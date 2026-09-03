from __future__ import annotations

from public_data_agent.agent_loop import run_agent


def test_agent_loop_calls_tools_until_final(monkeypatch) -> None:
    calls = []

    def fake_call(name, arguments):
        calls.append((name, arguments))
        return {"tool": name, "ok": True}

    monkeypatch.setattr("public_data_agent.agent_loop.call_tool", fake_call)

    class Model:
        def next_action(self, messages, tools):
            if not calls:
                return {"tool": "search", "arguments": {"query": "Oslo"}}
            return {"final": "done"}

    result = run_agent("find Oslo data", Model())
    assert result.final == "done"
    assert result.tool_calls == 1
    assert calls[0][0] == "search"


def test_agent_loop_rejects_unknown_tools() -> None:
    class Model:
        def next_action(self, messages, tools):
            return {"tool": "shell"}

    result = run_agent("test", Model())
    assert result.final is None
    assert "unknown tool" in (result.error or "")
