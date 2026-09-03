"""Minimal model-driven tool loop, independent of any model provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from public_data_agent.mcp_server import call_tool


class AgentModel(Protocol):
    def next_action(self, messages: list[dict[str, Any]], tools: list[str]) -> dict[str, Any]: ...


@dataclass
class AgentRun:
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: int = 0
    final: Any = None
    error: str | None = None


def run_agent(question: str, model: AgentModel, *, max_steps: int = 8) -> AgentRun:
    """Let a model choose tools one at a time; tools remain the trust boundary."""
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    tools = ["search", "inspect", "fetch", "run_analysis", "create_visualization", "export_artifact", "get_provenance"]
    for _ in range(max_steps):
        action = model.next_action(messages, tools)
        if action.get("final") is not None:
            return AgentRun(messages, len([m for m in messages if m.get("role") == "tool"]), action["final"])
        name = action.get("tool")
        if name not in tools:
            return AgentRun(messages, len([m for m in messages if m.get("role") == "tool"]), error=f"unknown tool: {name}")
        try:
            result = call_tool(name, action.get("arguments", {}))
        except Exception as exc:
            result = {"error": str(exc)}
        messages.append({"role": "assistant", "function_call": action})
        messages.append({"role": "tool", "name": name, "call_id": action.get("call_id", ""), "content": result})
    # A bounded loop must still produce a truthful user-facing result.  In
    # particular, never leave the UI with a blank answer after a connector
    # failure: no numeric claim was produced by the trust boundary.
    return AgentRun(
        messages,
        len([m for m in messages if m.get("role") == "tool"]),
        final=(
            "Jeg fant ikke en registrert connector som kunne hente dokumenterte "
            "observasjoner innenfor stegbegrensningen. Ingen tall ble hentet "
            "eller beregnet; prøv en kilde i connector_candidates eller inspiser "
            "en annen katalogpost."
        ),
        error="agent step limit reached",
    )
