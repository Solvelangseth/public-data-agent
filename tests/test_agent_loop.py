from __future__ import annotations

from public_data_agent.agent_loop import run_agent

# These exercise loop mechanics with placeholder questions, so the readiness
# gate is off: it would correctly stop "test" before the loop ever ran. The
# gate's own behaviour is covered in tests/test_pipeline.py.


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

    result = run_agent("find Oslo data", Model(), gate=False)
    assert result.final == "done"
    assert result.tool_calls == 1
    assert calls[0][0] == "search"


def test_agent_loop_reports_unknown_tools_without_executing_them() -> None:
    """An unknown name must never reach call_tool, but it is recoverable."""

    class Model:
        def next_action(self, messages, tools):
            return {"tool": "shell"}

    result = run_agent("test", Model(), max_steps=2, gate=False)
    tool_messages = [m for m in result.messages if m.get("role") == "tool"]
    assert tool_messages, "the refusal must be reported back to the model"
    error = tool_messages[0]["content"]["error"]
    assert error["code"] == "unknown_tool"
    assert "shell" in error["message"]
    assert tool_messages[0]["content"]["numbers_retrieved"] is False
    # Never silently succeed: with no usable tool the run must end truthfully.
    assert result.error == "agent step limit reached"
    assert "Ingen tall ble hentet" in (result.final or "")


def test_agent_loop_can_recover_after_an_unknown_tool() -> None:
    class Model:
        def __init__(self) -> None:
            self.seen = 0

        def next_action(self, messages, tools):
            self.seen += 1
            if self.seen == 1:
                return {"tool": "shell"}
            return {"final": "recovered"}

    result = run_agent("test", Model(), max_steps=4, gate=False)
    assert result.final == "recovered"


def test_agent_loop_returns_truthful_fallback_at_step_limit(monkeypatch) -> None:
    monkeypatch.setattr(
        "public_data_agent.agent_loop.call_tool",
        lambda name, arguments: {"error": {"code": "unsupported_access_path"}, "numbers_retrieved": False},
    )

    class Model:
        def next_action(self, messages, tools):
            return {"tool": "fetch", "arguments": {"dataset": "d", "table": "t"}}

    result = run_agent("find data", Model(), max_steps=1, gate=False)
    assert result.final and "Ingen tall ble hentet" in result.final
    assert result.error == "agent step limit reached"
