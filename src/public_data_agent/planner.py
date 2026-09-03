"""Small, explicit planning layer for the first natural-language slice.

The parser is intentionally deterministic so tests can prove that factual
values never come from a model. An LLM can be added behind this boundary later
to produce the same plan shape; execution remains registry/connector based.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from public_data_agent.fetch import can_fetch_access_path
from public_data_agent.search import SearchReport


@dataclass(frozen=True)
class PlanStep:
    kind: str
    reason: str
    dataset_id: str | None = None
    table_id: str | None = None
    periods: tuple[int, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "reason": self.reason}
        if self.dataset_id is not None:
            out["dataset_id"] = self.dataset_id
        if self.table_id is not None:
            out["table_id"] = self.table_id
        if self.periods:
            out["periods"] = list(self.periods)
        if self.parameters:
            out["parameters"] = self.parameters
        return out


@dataclass
class QuestionPlan:
    question: str
    intent: str
    parser: str
    search_query: str
    requirements: list[str]
    steps: list[PlanStep] = field(default_factory=list)
    refusal_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "intent": self.intent,
            "parser": self.parser,
            "search_query": self.search_query,
            "requirements": self.requirements,
            "steps": [step.to_dict() for step in self.steps],
            "refusal_reason": self.refusal_reason,
        }


def build_plan(
    question: str,
    report: SearchReport,
    *,
    klass_dataset_id: str,
    ssb_table: str,
    latest_year: int,
    prior_year: int,
    registry: Any,
) -> QuestionPlan:
    """Turn one Norwegian question and search report into executable steps."""

    requirements = list(report.coverage.requirements)
    if _is_bydel_growth(question):
        klass = registry.get_dataset(klass_dataset_id)
        ssb = registry.get_dataset(f"ssb:{ssb_table}")
        ssb_is_usable = ssb is None or _row_is_fetchable(ssb)
        if klass and ssb_is_usable and _row_is_fetchable(klass):
            return QuestionPlan(
                question=question,
                intent="bydel_population_size_and_growth",
                parser="deterministic_norwegian_heuristics",
                search_query=question,
                requirements=requirements,
                steps=[
                    PlanStep("search", "discover candidate catalog records"),
                    PlanStep(
                        "fetch",
                        "fetch the stored Klass classification URL",
                        dataset_id=klass_dataset_id,
                        table_id="1168",
                        periods=(prior_year, latest_year),
                    ),
                    PlanStep(
                        "fetch",
                        "fetch the configured SSB PxWeb table through its existing connector",
                        dataset_id=f"ssb:{ssb_table}",
                        table_id=ssb_table,
                        periods=(prior_year, latest_year),
                    ),
                    PlanStep(
                        "join",
                        "join only on the stored bydel_code key",
                        dataset_id=f"ssb:{ssb_table}",
                        table_id=ssb_table,
                        periods=(prior_year, latest_year),
                    ),
                    PlanStep(
                        "derive",
                        "derive YoY only from the two joined observation periods",
                        periods=(prior_year, latest_year),
                    ),
                ],
            )
        return QuestionPlan(
            question=question,
            intent="bydel_population_size_and_growth",
            parser="deterministic_norwegian_heuristics",
            search_query=question,
            requirements=requirements,
            steps=[PlanStep("search", "discover candidate catalog records")],
            refusal_reason=(
                "The Oslo-bydel plan needs both the stored Klass and SSB table "
                "records with supported connectors; no numbers were retrieved."
            ),
        )

    fetchable = _first_fetchable_hit(report, registry)
    steps = [PlanStep("search", "discover and rank catalog records")]
    refusal_reason = None
    if fetchable is not None:
        dataset_id, table_id = fetchable
        steps.append(
            PlanStep(
                "fetch",
                "fetch only a stored access path handled by an existing connector",
                dataset_id=dataset_id,
                table_id=table_id,
            )
        )
    else:
        refusal_reason = (
            "No ranked catalog hit has both a stored access path and an existing "
            "connector capable of a real HTTP fetch; no numbers were retrieved."
        )
    return QuestionPlan(
        question=question,
        intent="catalog_search_and_optional_fetch",
        parser="deterministic_norwegian_heuristics",
        search_query=question,
        requirements=requirements,
        steps=steps,
        refusal_reason=refusal_reason,
    )


def _is_bydel_growth(question: str) -> bool:
    text = question.casefold()
    population_language = ("befolkning", "folkemengde", "innbygger", "folketall")
    ranking_language = ("størst", "stor", "vok", "vekst", "sammenlign", "ranger")
    return (
        "oslo" in text
        and ("bydel" in text or "bydeler" in text)
        and any(token in text for token in ranking_language)
        and (any(token in text for token in population_language) or "størst" in text or "vok" in text)
    )


def _row_is_fetchable(row: dict[str, Any]) -> bool:
    return bool(row.get("access_path") and can_fetch_access_path(row["access_path"]))


def _first_fetchable_hit(report: SearchReport, registry: Any) -> tuple[str, str] | None:
    for hit in report.hits:
        row = registry.get_dataset(hit.dataset_id)
        if not row or not _row_is_fetchable(row):
            continue
        access = str(row["access_path"])
        table_id = access.rstrip("/").rsplit("/", 1)[-1] or hit.dataset_id
        return hit.dataset_id, table_id
    return None
