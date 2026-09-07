"""Deterministic gates that run before any model is asked to plan.

The first node of the pipeline decides whether a question can be answered at
all. It is a plain function, not an agent: a model asked to judge its own
readiness is systematically overconfident, and the signals needed to decide are
already computed by search and the connector classifier.

Nothing here calls a model, and nothing here produces a number. It answers one
question — is there a registered source that could return observations for this
— and carries forward the dataset handles a later node would need.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from public_data_agent.fetch import classify_access_path
from public_data_agent.intake import (
    EXPLORATORY,
    IntakeProvider,
    Request,
    read_question_with_fallback,
)
from public_data_agent.registry import Registry
from public_data_agent.retrieval import find
from public_data_agent.search import search_report

# Rank deeper than the caller wants so each lane can fill its own top-N.
LANE_DEPTH = 6

# Routes out of the first stage. Chosen by rule, never by a model: a model
# judging its own readiness or its own task shape is systematically
# overconfident, and every signal these need is already computed.
ROUTE_STOP = "stop"
ROUTE_CLARIFY = "clarify"
ROUTE_SPECIFIC = "specific"
ROUTE_EXPLORATORY = "exploratory"

NOTHING_FOUND = "nothing_found"
CATALOGUE_ONLY = "catalogue_only"
LOOKUP_ONLY = "lookup_only"
READY = "ready"


@dataclass(frozen=True)
class SourceRef:
    """A handle to a dataset, not a summary of it.

    Later nodes receive these rather than prose. A sentence like "population
    grew about 3%" passed between nodes becomes an unverifiable claim; an id
    plus a capability stays checkable all the way to the answer.
    """

    dataset_id: str
    title: str | None
    capability: str
    access_path: str | None
    publisher: str | None
    relevance: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "title": self.title,
            "capability": self.capability,
            "access_path": self.access_path,
            "publisher": self.publisher,
            "relevance": self.relevance,
        }


@dataclass(frozen=True)
class Readiness:
    """Whether the pipeline should continue, and the evidence either way."""

    question: str
    ready: bool
    outcome: str
    reason: str
    observation_sources: list[SourceRef] = field(default_factory=list)
    lookup_sources: list[SourceRef] = field(default_factory=list)
    catalogue_records: list[SourceRef] = field(default_factory=list)
    # Query terms no retrieved record stores. Reported, never used to refuse:
    # search indexes titles and keywords, not dimension *values*, so "Trondheim"
    # is uncovered even when a table can answer for it via select=. Treating a
    # missing term as proof of absence would stop questions we can answer.
    uncovered_terms: list[str] = field(default_factory=list)

    @property
    def numbers_retrieved(self) -> bool:
        """No gate ever retrieves a number. Stated so callers cannot assume."""

        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": "readiness_gate",
            "question": self.question,
            "ready": self.ready,
            "outcome": self.outcome,
            "reason": self.reason,
            "observation_sources": [item.to_dict() for item in self.observation_sources],
            "lookup_sources": [item.to_dict() for item in self.lookup_sources],
            "catalogue_records": [item.to_dict() for item in self.catalogue_records],
            "uncovered_terms": list(self.uncovered_terms),
            "numbers_retrieved": False,
        }


def assess_readiness(
    registry: Registry,
    question: str,
    *,
    limit: int = 5,
    request: Request | None = None,
    provider: Any | None = None,
) -> Readiness:
    """Decide whether any registered connector could answer this question.

    Ready means at least one hit classifies as ``observations``. A code list is
    not enough on its own: a classification supplies join keys, never measures.
    A catalogue record that merely describes data is not enough either.

    When an intake ``request`` is supplied, its extracted terms are searched
    rather than the raw sentence, so question words do not become requirements.

    With an embedding ``provider`` this ranks through `retrieval.find`, which
    measures recall@5 0.860 against the fetchable gold set where lexical search
    alone measures 0.442, and 0.814 against 0.233 on naturally phrased
    questions. Without one it stays lexical, which is a real loss rather than a
    missing optimisation.
    """

    query = request.search_query() if request is not None and request.search_terms else question
    depth = max(limit * LANE_DEPTH, limit)
    found = find(registry, query, provider=provider, limit=depth, depth=depth)
    uncovered = list(found.uncovered)

    def _ref(dataset_id: str) -> SourceRef:
        row = registry.get_dataset(dataset_id) or {}
        return SourceRef(
            dataset_id=dataset_id,
            title=row.get("title"),
            capability=classify_access_path(row.get("access_path"))["kind"],
            access_path=row.get("access_path"),
            publisher=row.get("publisher_name"),
            # Zero where a result was found by embedding rather than by tokens:
            # the ordering already carries the ranking, and inventing a lexical
            # score for a non-lexical match would misreport how it was found.
            relevance=found.relevance.get(dataset_id, 0),
        )

    observations = [_ref(d) for d in found.observations]
    lookups: list[SourceRef] = []
    catalogue: list[SourceRef] = []
    for dataset_id in found.catalogue:
        ref = _ref(dataset_id)
        (lookups if ref.capability == "lookup" else catalogue).append(ref)

    observations, lookups, catalogue = observations[:limit], lookups[:limit], catalogue[:limit]

    if observations:
        reason = (
            f"{len(observations)} registered source(s) can return observations for this "
            "question; continue to planning."
        )
        if uncovered:
            reason += (
                f" No retrieved record stores {uncovered}; those may still be dimension "
                "values inside a matched table, so confirm them against the stored "
                "schema before answering, and say so if they cannot be confirmed."
            )
        return Readiness(
            question=question,
            ready=True,
            outcome=READY,
            reason=reason,
            observation_sources=observations,
            lookup_sources=lookups,
            catalogue_records=catalogue,
            uncovered_terms=uncovered,
        )
    if lookups and not catalogue:
        outcome, reason = LOOKUP_ONLY, (
            "The only fetchable matches are classification code lists. Those supply join "
            "keys and names, never measures, so no number can be produced from them alone."
        )
    elif catalogue or lookups:
        extra = (
            f" {len(lookups)} of them are code lists, which carry join keys but no measures."
            if lookups else ""
        )
        outcome, reason = CATALOGUE_ONLY, (
            f"{len(catalogue) + len(lookups)} catalogue record(s) match, but none can return "
            f"observations.{extra} They describe data this project cannot currently fetch."
        )
    else:
        outcome, reason = NOTHING_FOUND, (
            "No catalogue record matched this question, so there is nothing to retrieve "
            "and nothing to describe."
        )
    return Readiness(
        question=question,
        ready=False,
        outcome=outcome,
        reason=reason,
        lookup_sources=lookups,
        catalogue_records=catalogue,
        uncovered_terms=uncovered,
    )


def stop_message(readiness: Readiness) -> str:
    """Norwegian user-facing text for a question that cannot be answered.

    The stop path runs no model by design, so this text is templated. It states
    plainly that no numbers were retrieved and names what was found instead;
    it never speculates about what the answer might have been.
    """

    if readiness.ready:
        raise ValueError("stop_message is only for a question the gate stopped")

    lines = ["Jeg hentet ingen tall for dette spørsmålet."]
    if readiness.outcome == NOTHING_FOUND:
        lines.append(
            "Ingen katalogpost i registeret traff søket, så det finnes verken data å hente "
            "eller kilder å vise til."
        )
    elif readiness.outcome == LOOKUP_ONLY:
        lines.append(
            "De eneste hentbare treffene er kodelister (klassifikasjoner). De gir "
            "koder og navn til kobling, men ingen målte verdier."
        )
    else:
        lines.append(
            "Katalogen har relevante poster, men ingen av dem har en registrert connector "
            "som kan hente observasjoner. De beskriver data vi ikke kan hente."
        )

    if readiness.uncovered_terms:
        lines.append(
            f"Ingen av treffene lagrer: {', '.join(readiness.uncovered_terms)}."
        )
    shown = (readiness.lookup_sources + readiness.catalogue_records)[:5]
    if shown:
        lines.append("")
        lines.append("Nærmeste treff i katalogen:")
        for ref in shown:
            title = ref.title or ref.dataset_id
            lines.append(f"  - {title} ({ref.dataset_id}, kan ikke hentes: {ref.capability})")
    lines.append("")
    lines.append(
        "Ingen tall ble hentet eller beregnet. Prøv et annet spørsmål, eller be om at en "
        "connector registreres for en av kildene over."
    )
    return "\n".join(lines)


@dataclass(frozen=True)
class Intake:
    """Intake and the gate composed: the first two nodes of the pipeline."""

    request: Request
    readiness: Readiness
    intake_warning: str | None = None

    @property
    def proceed(self) -> bool:
        """Continue only when the question is understood and answerable."""

        return self.readiness.ready and not self.request.needs_clarification

    def to_dict(self) -> dict[str, Any]:
        return {
            "proceed": self.proceed,
            "intake": self.request.to_dict(),
            "readiness": self.readiness.to_dict(),
            "intake_warning": self.intake_warning,
            "numbers_retrieved": False,
        }


def run_intake(
    registry: Registry,
    question: str,
    *,
    provider: IntakeProvider | None = None,
    limit: int = 5,
    embedding_provider: Any | None = None,
) -> Intake:
    """Read the question, then decide whether anything can answer it.

    Clarification is asked before the gate's verdict is acted on: a question we
    have misread is not evidence that the data is missing.
    """

    request, warning = read_question_with_fallback(question, provider)
    readiness = assess_readiness(
        registry, question, limit=limit, request=request, provider=embedding_provider
    )
    return Intake(request=request, readiness=readiness, intake_warning=warning)


def route(intake: "Intake") -> str:
    """Pick the next node. Order matters.

    Clarification comes before the gate's verdict: a question we have misread
    is not evidence that the data is missing. The gate comes before the split,
    because there is nothing to plan or explore over when nothing can answer.
    """

    if intake.request.needs_clarification:
        return ROUTE_CLARIFY
    if not intake.readiness.ready:
        return ROUTE_STOP
    return ROUTE_EXPLORATORY if intake.request.shape == EXPLORATORY else ROUTE_SPECIFIC


def plan_candidates(readiness: Readiness, *, limit: int = 10) -> list[dict[str, Any]]:
    """The bounded, factual context a planner may choose from.

    Only sources that can actually return observations are offered. A planner
    given a landing page will eventually try to fetch it.
    """

    return [
        {
            "dataset_id": ref.dataset_id,
            "title": ref.title,
            "publisher": ref.publisher,
            "access_path": ref.access_path,
            "table_id": _table_id_from(ref.access_path),
            "capability": ref.capability,
        }
        for ref in readiness.observation_sources[:limit]
    ]


def _table_id_from(access_path: str | None) -> str | None:
    """The trailing path segment of a PxWeb table URL, or nothing.

    Never guessed from a title: an id we cannot read off the stored path is an
    id we do not have.
    """

    if not access_path:
        return None
    tail = access_path.rstrip("/").rsplit("/", 1)[-1]
    return tail if tail.isdigit() else None


@dataclass(frozen=True)
class PipelineRun:
    """One trip through the graph, with the trace that produced it."""

    question: str
    route: str
    intake: Intake
    plan: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    agent: dict[str, Any] | None = None
    final: str | None = None
    error: str | None = None

    @property
    def numbers_retrieved(self) -> bool:
        """True only when a tool returned a numeric cell on this run."""

        for payload in (self.execution, self.agent):
            if payload and payload.get("numbers_retrieved"):
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "route": self.route,
            "intake": self.intake.to_dict(),
            "plan": self.plan,
            "execution": self.execution,
            "agent": self.agent,
            "final": self.final,
            "error": self.error,
            "numbers_retrieved": self.numbers_retrieved,
        }


def run_specific(
    registry: Registry,
    intake: Intake,
    *,
    plan_provider: Any,
    http: Any | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    """Plan over the found sources, then execute the plan deterministically.

    The planner may only choose from sources the gate proved can return
    observations, and its output is validated before anything runs. Returns
    (plan, execution, error); a rejected plan executes nothing.
    """

    from public_data_agent.executor import execute_plan
    from public_data_agent.llm_planner import plan_with_provider

    candidates = plan_candidates(intake.readiness)
    if not candidates:
        return None, None, "no observation source survived the gate to plan over"
    validation = plan_with_provider(
        plan_provider, question=intake.request.question, candidates=candidates
    )
    if validation.plan is None:
        return None, None, validation.error or "plan failed validation"
    plan = validation.plan.to_dict()
    result = execute_plan(registry, validation.plan, http=http)
    return plan, result.to_dict(), None


def run_pipeline(
    registry: Registry,
    question: str,
    *,
    db: str,
    intake_provider: IntakeProvider | None = None,
    plan_provider: Any | None = None,
    agent_model: Any | None = None,
    embedding_provider: Any | None = None,
    limit: int = 5,
    max_steps: int = 10,
) -> PipelineRun:
    """Run the graph: intake, gate, route, then the path the route names.

    Every branch returns something truthful. A route that cannot run for want
    of a provider says so rather than falling through to a different path,
    because silently answering a different way is how a run stops being
    reproducible.
    """

    intake = run_intake(registry, question, provider=intake_provider, limit=limit,
                        embedding_provider=embedding_provider)
    chosen = route(intake)

    if chosen == ROUTE_CLARIFY:
        return PipelineRun(
            question=question,
            route=chosen,
            intake=intake,
            final=intake.request.clarifying_question,
        )
    if chosen == ROUTE_STOP:
        return PipelineRun(
            question=question,
            route=chosen,
            intake=intake,
            final=stop_message(intake.readiness),
        )
    if chosen == ROUTE_SPECIFIC:
        if plan_provider is None:
            return PipelineRun(
                question=question,
                route=chosen,
                intake=intake,
                error="specific route needs a plan provider",
            )
        plan, execution, error = run_specific(registry, intake, plan_provider=plan_provider)
        return PipelineRun(
            question=question, route=chosen, intake=intake,
            plan=plan, execution=execution, error=error,
        )

    if agent_model is None:
        return PipelineRun(
            question=question,
            route=chosen,
            intake=intake,
            error="exploratory route needs an agent model",
        )
    # Exploratory questions cannot be planned up front: which datasets matter
    # is part of what is being asked. So the bounded tool loop drives, with the
    # same tools and the same trust boundary, and the gate has already proved
    # something can answer. The gate is not re-run inside the loop.
    from public_data_agent.agent_loop import run_agent

    run = run_agent(
        intake.request.question, agent_model, max_steps=max_steps, db=db, gate=False
    )
    return PipelineRun(
        question=question,
        route=chosen,
        intake=intake,
        agent={
            "tool_calls": run.tool_calls,
            "error": run.error,
            "numbers_retrieved": any(
                isinstance(m.get("content"), dict) and m["content"].get("numbers_retrieved")
                for m in run.messages
                if m.get("role") == "tool"
            ),
        },
        final=run.final,
        error=run.error,
    )
