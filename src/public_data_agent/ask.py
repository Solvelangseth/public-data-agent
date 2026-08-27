from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from methods.derive import derive_yoy
from methods.types import Observation, SeriesRow
from public_data_agent.fetch import JsonHttp
from public_data_agent.join import (
    DEFAULT_KLASS_DATASET,
    JOIN_KEY,
    WHY_11763,
    WHY_NOT_07459,
    WHY_NOT_M7_M8,
    JoinResult,
    join_bydel_population,
)
from public_data_agent.registry import Registry, utc_now
from public_data_agent.search import search_report
from public_data_agent.ssb_pxweb import DEFAULT_SSB_TABLE

DEMO_QUESTION = "Hvilke Oslo-bydeler er størst og hvilke vokser mest?"
WHY_KLASS = (
    "Bydelsinndeling is already in the registry with a working Klass GET. "
    "Milestone 9 joined it to SSB 11763 on exact bydel_code."
)
WHY_METHODS = (
    "PR 13 is on main. YoY is methods.derive.derive_yoy. "
    "This slice calls that function and does not reimplement the rate."
)


@dataclass
class AskResult:
    question: str
    latest_year: str
    prior_year: str
    join_key: str
    search: dict[str, Any]
    joins: list[JoinResult] = field(default_factory=list)
    largest: list[dict[str, Any]] = field(default_factory=list)
    growing: list[dict[str, Any]] = field(default_factory=list)
    derived: tuple[SeriesRow, ...] = ()
    joined_rows: int = 0


def ask(
    registry: Registry,
    question: str,
    *,
    klass_dataset_id: str = DEFAULT_KLASS_DATASET,
    ssb_table: str = DEFAULT_SSB_TABLE,
    latest_year: int = 2025,
    prior_year: int = 2024,
    search_limit: int = 10,
    http: JsonHttp | None = None,
) -> AskResult:
    """Search, join two years, then rank size and YoY from the joined cells."""

    report = search_report(registry, question, limit=search_limit)
    prior = join_bydel_population(
        registry,
        klass_dataset_id=klass_dataset_id,
        ssb_table=ssb_table,
        year=prior_year,
        http=http,
    )
    latest = join_bydel_population(
        registry,
        klass_dataset_id=klass_dataset_id,
        ssb_table=ssb_table,
        year=latest_year,
        http=http,
    )
    rows = [*prior.rows, *latest.rows]
    observations = _observations_from_joined(rows, latest)
    derived = derive_yoy(observations)
    latest_label = str(latest_year)
    prior_label = str(prior_year)
    lineage = _source_lineage(registry, klass_dataset_id, latest)
    largest = _rank_size(rows, latest_label, lineage)
    growing = _attach_names(_rank_growth(derived, latest_label, lineage), largest)
    return AskResult(
        question=question,
        latest_year=latest_label,
        prior_year=prior_label,
        join_key=JOIN_KEY,
        search=report.to_dict(),
        joins=[prior, latest],
        largest=largest,
        growing=growing,
        derived=derived,
        joined_rows=len(rows),
    )


def ask_proof_payload(
    result: AskResult,
    *,
    command: str,
    db: str,
) -> dict[str, Any]:
    return {
        "produced_at": utc_now(),
        "command": command,
        "question": result.question,
        "join_key": result.join_key,
        "latest_year": result.latest_year,
        "prior_year": result.prior_year,
        "discovery": {
            "method": "pda search / search_report",
            "returned": result.search.get("returned"),
            "hits": [
                {
                    "dataset_id": hit.get("id") or hit.get("dataset_id"),
                    "title": hit.get("title"),
                    "relevance": hit.get("relevance"),
                    "why": hit.get("why"),
                }
                for hit in (result.search.get("results") or [])[:5]
            ],
        },
        "why_datasets": {
            "klass": WHY_KLASS,
            "ssb_11763": WHY_11763,
            "not_m7_m8": WHY_NOT_M7_M8,
            "not_07459": WHY_NOT_07459,
            "methods": WHY_METHODS,
        },
        "joins": [
            {
                "year": year,
                "left_request_url": item.left_request_url,
                "right_request_url": item.right_request_url,
                "left_http_status": item.left_http_status,
                "right_http_status": item.right_http_status,
                "listed": item.counts.listed,
            }
            for year, item in zip((result.prior_year, result.latest_year), result.joins)
        ],
        "joined_rows": result.joined_rows,
        "largest": result.largest,
        "growing": result.growing,
        "db": db,
    }


def _observations_from_joined(rows: list[dict[str, Any]], latest: JoinResult) -> tuple[Observation, ...]:
    out: list[Observation] = []
    for row in rows:
        value = row.get("population")
        if value is None:
            continue
        code = str(row["bydel_code"])
        year = str(row["year"])
        out.append(
            Observation(
                id=f"{code}:{year}",
                entity=code,
                period=year,
                measure=str(row.get("population_measure") or "Personer (antall)"),
                value=float(value),
                source=latest.right_dataset_id,
                dataset_id=latest.right_dataset_id,
                table_id="11763",
                dimensions=(("bydel_code", code), ("år", year)),
                retrieved_at=utc_now(),
                request_url=latest.right_request_url,
                publisher_name=latest.right_publisher,
                license=None,
                access_path=latest.right_request_url,
                http_status=latest.right_http_status,
            )
        )
    return tuple(out)


def _rank_size(
    rows: list[dict[str, Any]],
    latest_year: str,
    lineage: dict[str, Any],
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("year")) != latest_year or row.get("population") is None:
            continue
        ranked.append(
            {
                "rank": 0,
                "bydel_code": row["bydel_code"],
                "name": row.get("klass_name") or row.get("ssb_region_label"),
                "year": latest_year,
                "population": row["population"],
                **lineage,
            }
        )
    ranked.sort(key=lambda item: (-float(item["population"]), item["bydel_code"]))
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return ranked


def _rank_growth(
    derived: tuple[Any, ...],
    latest_year: str,
    lineage: dict[str, Any],
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for row in derived:
        if row.observation.period != latest_year or row.yoy_growth.value is None:
            continue
        ranked.append(
            {
                "rank": 0,
                "bydel_code": row.observation.entity,
                "year": latest_year,
                "population": row.observation.value,
                "yoy_growth": row.yoy_growth.value,
                "yoy_formula": row.yoy_growth.lineage.formula,
                "yoy_source_periods": list(row.yoy_growth.lineage.source_periods),
                **lineage,
            }
        )
    ranked.sort(key=lambda item: (-float(item["yoy_growth"]), item["bydel_code"]))
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return ranked


def _source_lineage(
    registry: Registry,
    klass_dataset_id: str,
    latest: JoinResult,
) -> dict[str, Any]:
    klass = registry.get_dataset(klass_dataset_id) or {}
    return {
        "join_key": JOIN_KEY,
        "why_matched": f"exact {JOIN_KEY} in SSB 11763 Region and Klass classificationItems.code",
        "sources": [
            {
                "dataset_id": klass_dataset_id,
                "title": klass.get("title"),
                "publisher_name": klass.get("publisher_name"),
                "license": klass.get("license"),
                "access_path": klass.get("access_path"),
                "request_url": latest.left_request_url,
                "http_status": latest.left_http_status,
                "why_picked": WHY_KLASS,
            },
            {
                "dataset_id": latest.right_dataset_id,
                "title": latest.right_title,
                "publisher_name": latest.right_publisher,
                "license": None,
                "access_path": latest.right_request_url,
                "request_url": latest.right_request_url,
                "http_status": latest.right_http_status,
                "why_picked": WHY_11763,
            },
        ],
    }


def _attach_names(growing: list[dict[str, Any]], largest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = {item["bydel_code"]: item.get("name") for item in largest}
    for item in growing:
        item["name"] = names.get(item["bydel_code"])
    return growing
