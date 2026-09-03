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
from public_data_agent.registry import Registry
from public_data_agent.search import search_report

# Rank deeper than the caller wants so each lane can fill its own top-N.
LANE_DEPTH = 6

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


def assess_readiness(registry: Registry, question: str, *, limit: int = 5) -> Readiness:
    """Decide whether any registered connector could answer this question.

    Ready means at least one hit classifies as ``observations``. A code list is
    not enough on its own: a classification supplies join keys, never measures.
    A catalogue record that merely describes data is not enough either.
    """

    report = search_report(registry, question, limit=max(limit * LANE_DEPTH, limit))
    uncovered = list(report.coverage.missing)
    observations: list[SourceRef] = []
    lookups: list[SourceRef] = []
    catalogue: list[SourceRef] = []
    for hit in report.hits:
        kind = classify_access_path(hit.access_path)["kind"]
        ref = SourceRef(
            dataset_id=hit.dataset_id,
            title=hit.title,
            capability=kind,
            access_path=hit.access_path,
            publisher=(hit.publisher or {}).get("name") if hit.publisher else None,
            relevance=hit.relevance,
        )
        if kind == "observations":
            observations.append(ref)
        elif kind == "lookup":
            lookups.append(ref)
        else:
            catalogue.append(ref)

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
