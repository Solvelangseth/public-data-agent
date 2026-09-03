"""Minimal model-driven tool loop, independent of any model provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from public_data_agent.mcp_server import DEFAULT_DB, call_tool
from public_data_agent.pipeline import Readiness, assess_readiness, stop_message
from public_data_agent.registry import Registry


class AgentModel(Protocol):
    def next_action(self, messages: list[dict[str, Any]], tools: list[str]) -> dict[str, Any]: ...


@dataclass
class AgentRun:
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: int = 0
    final: Any = None
    error: str | None = None
    readiness: dict[str, Any] | None = None


def run_agent(
    question: str,
    model: AgentModel,
    *,
    max_steps: int = 8,
    db: str = DEFAULT_DB,
    gate: bool = True,
) -> AgentRun:
    """Let a model choose tools one at a time; tools remain the trust boundary.

    A deterministic gate runs first. If no registered connector could return
    observations for this question, the run stops before any model call: there
    is nothing for a planner to plan over, and letting a model start anyway is
    how an unanswerable question turns into a confident answer.
    """

    if gate:
        readiness = _readiness(question, db)
        if readiness is not None and not readiness.ready:
            return AgentRun(
                messages=[{"role": "user", "content": question}],
                tool_calls=0,
                final=stop_message(readiness),
                error=None,
                readiness=readiness.to_dict(),
            )
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    tools = ["search", "inspect", "fetch", "run_analysis", "create_visualization", "export_artifact", "get_provenance"]
    for _ in range(max_steps):
        action = model.next_action(messages, tools)
        if action.get("final") is not None:
            return AgentRun(messages, len([m for m in messages if m.get("role") == "tool"]), action["final"])
        name = action.get("tool")
        if name not in tools:
            # A mistyped tool name is recoverable.  Aborting the run here left
            # the user with no answer at all, so report it back as a tool
            # result and let the model correct itself within the step budget.
            result: Any = {
                "error": {
                    "code": "unknown_tool",
                    "retryable": True,
                    "message": f"unknown tool: {name}",
                    "available_tools": tools,
                },
                "numbers_retrieved": False,
            }
        else:
            try:
                result = call_tool(name, action.get("arguments", {}))
            except Exception as exc:
                result = {
                    "error": {
                        "code": "tool_error",
                        "retryable": False,
                        "message": str(exc),
                    },
                    "numbers_retrieved": False,
                }
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


def _readiness(question: str, db: str) -> Readiness | None:
    """Run the gate, but never let a gate failure block a real attempt."""

    try:
        registry = Registry(db)
    except Exception:
        return None
    try:
        return assess_readiness(registry, question)
    except Exception:
        return None
    finally:
        registry.close()
