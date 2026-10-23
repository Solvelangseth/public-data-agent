from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from methods.derive import derive_yoy
from methods.types import Observation, SeriesRow
from public_data_agent.fetch import JsonHttp, fetch_observations
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
from public_data_agent.retrieval import find
from public_data_agent.search import search_report
from public_data_agent.ssb_pxweb import DEFAULT_SSB_TABLE
from public_data_agent.constraints import constraints_in
from public_data_agent.planner import QuestionPlan, build_plan

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
    plan: QuestionPlan | None = None
    execution: dict[str, Any] = field(default_factory=dict)
    answer: dict[str, Any] = field(default_factory=dict)


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
    provider: Any | None = None,
) -> AskResult:
    """Search, join two years, then rank size and YoY from the joined cells."""

    report = search_report(registry, question, limit=search_limit)
    # Discovery used token matching alone, which finds the right table for 44%
    # of gold questions against 86% for the measured stack. Asking
    # "byggekostnader" planned no fetch at all while five building-cost tables
    # sat in the registry, so the question was answered "no numbers retrieved".
    found = find(registry, question, provider=provider, limit=search_limit)
    plan = build_plan(
        question,
        report,
        candidates=found.observations,
        klass_dataset_id=klass_dataset_id,
        ssb_table=ssb_table,
        latest_year=latest_year,
        prior_year=prior_year,
        registry=registry,
    )
    if plan.intent != "bydel_population_size_and_growth" or plan.refusal_reason:
        execution = _execute_catalog_plan(registry, plan, http=http)
        return AskResult(
            question=question,
            latest_year=str(latest_year),
            prior_year=str(prior_year),
            join_key="",
            search=report.to_dict(),
            plan=plan,
            execution=execution,
            answer={
                "numbers_retrieved": bool(execution.get("numbers_retrieved")),
                "explanation": execution.get("explanation"),
                "observations": execution.get("observations", []),
            },
        )
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
        plan=plan,
        execution={
            "status": "completed",
            "numbers_retrieved": True,
            "observation_source": "joined_rows",
            "explanation": "Values are copied from the two fetched observation periods and the stored bydel_code join.",
        },
        answer={
            "numbers_retrieved": True,
            "explanation": "Values are copied from observations, joined_rows, and methods.derive_yoy.",
        },
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
        "why_datasets": (
            {
                "klass": WHY_KLASS,
                "ssb_11763": WHY_11763,
                "not_m7_m8": WHY_NOT_M7_M8,
                "not_07459": WHY_NOT_07459,
                "methods": WHY_METHODS,
            }
            if result.plan and result.plan.intent == "bydel_population_size_and_growth"
            else {}
        ),
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
        "plan": result.plan.to_dict() if result.plan else None,
        "execution": result.execution,
        "answer": result.answer,
        "numbers_retrieved": bool(result.answer.get("numbers_retrieved")),
    }


# What one question may store. The unbounded path stored 264,033 cells for
# a question about two kommuner in one year; the same request narrowed
# returns 27. This is the ceiling for when narrowing fails, not a target --
# over it `fetch_observations` stores nothing and says what the response
# held, because a partial table reported as success is worse than no answer.
ASK_MAX_CELLS = 20_000


def _execute_catalog_plan(
    registry: Registry,
    plan: QuestionPlan,
    *,
    http: JsonHttp | None,
    max_cells: int | None = ASK_MAX_CELLS,
) -> dict[str, Any]:
    """Execute the planned fetch, narrowed to what the question pinned down.

    It used to send the request with no filter at all and then return
    `list_observations(dataset_id)` -- every row ever stored for that dataset.
    Asked for household waste per inhabitant in Bærum against Asker in 2024,
    that fetched **264,033 cells** covering every kommune, every year and every
    waste fraction, returned all of them, and reported `numbers_retrieved:
    true`. Nothing was wrong with the search, the plan or the connector; the
    words "Bærum" and "2024" were simply never read.

    `fetch_observations` has taken `kommune`, `from_year`, `to_year` and
    `max_cells` since long before this. The same request with the kommune and
    the year filled in returns **27 cells**, and they include
    `Årsinnbyggere (antall)` -- the denominator the question needs.

    One request per place the question names, because a comparison asks about
    two and a single filter can only hold one. The rows handed back are the
    ones these fetches touched, by `observation_ids`, not everything the
    dataset has accumulated.
    """

    fetch_step = next((step for step in plan.steps if step.kind == "fetch"), None)
    if fetch_step is None or fetch_step.dataset_id is None:
        return {
            "status": "not_fetched",
            "numbers_retrieved": False,
            "observations": [],
            "explanation": plan.refusal_reason or "The planner found no executable fetch step; no numbers were retrieved.",
        }
    found = constraints_in(plan.question, registry)
    years = found.years
    narrowing: dict[str, Any] = {
        "years": list(years),
        "places": [place.to_dict() for place in found.places],
        "unresolved": list(found.unresolved),
    }
    # A place the register maps to several codes is not narrowed to one of
    # them. Picking would answer confidently about a kommune nobody asked for.
    codes: list[str | None] = [place.code for place in found.resolved_places] or [None]
    try:
        fetched, observation_ids, dropped, flags = _fetch_each(
            registry,
            fetch_step,
            codes=codes,
            years=years,
            http=http,
            max_cells=max_cells,
        )
        if dropped:
            narrowing["filter_not_supported"] = dropped
    except Exception as exc:
        return {
            "status": "fetch_failed",
            "numbers_retrieved": False,
            "dataset_id": fetch_step.dataset_id,
            "request_url": registry.get_dataset(fetch_step.dataset_id).get("access_path")
            if registry.get_dataset(fetch_step.dataset_id)
            else None,
            "observations": [],
            "reason": str(exc),
            "explanation": f"The ranked hit was not fetched successfully ({exc}); no numbers were retrieved.",
        }
    # Only what these requests touched. `list_observations(dataset_id)` is
    # every row the dataset has ever accumulated, which is how one question
    # came back with 264,033.
    rows = registry.list_observations(ids=observation_ids)
    dataset = registry.get_dataset(fetch_step.dataset_id) or {}
    observations = []
    numeric = False
    for row in rows:
        value = _json_value(row.get("value_json"))
        numeric = numeric or isinstance(value, (int, float)) and not isinstance(value, bool)
        observations.append(
            {
                "observation_id": row["id"],
                "dataset_id": row["dataset_id"],
                "table_id": row["table_id"],
                "measure": row["measure"],
                "value": value,
                "dimensions": _json_value(row["dimensions_json"]),
                "publisher_name": row.get("publisher_name") or dataset.get("publisher_name"),
                "license": row.get("license") or dataset.get("license"),
                "access_path": row.get("access_path") or dataset.get("access_path"),
                "request_url": row.get("request_url"),
                "http_status": row.get("http_status"),
            }
        )
    # Did the narrowing actually happen? 164 of the 221 connector dispatches
    # never receive the `select` that `fetch_observations` computes, so a
    # filter can be requested, accepted and silently dropped. Measured on
    # bwfish: `kommune=5060` returns the same 580 localities as no filter at
    # all, across all 125 kommuner. Without this check the answer would read
    # "narrowed to place Austevoll" while carrying the whole country.
    #
    # Conservative on purpose: it only reports a failure it can SEE, by
    # finding a stored row that contradicts what was asked for. A source
    # whose dimensions do not name the place at all stays "unverified"
    # rather than being accused.
    # Two independent readings, and either one saying no is enough. The
    # connector-level flag sees the sample the request itself returned; the
    # row-level check sees every stored row this request touched. Neither
    # subsumes the other: a sample is current but usually partial, while a
    # stored row can prove only dimensions whose values are comparable.
    in_rows = _narrowing_held(observations, found.resolved_places, years)
    from_connector = None if not flags else (
        False if False in flags else (True if all(f is True for f in flags) else None)
    )
    held: bool | None
    if in_rows is False or from_connector is False:
        held = False
    elif in_rows is True or from_connector is True:
        held = True
    else:
        held = None
    # A request that the connector refused was not fully narrowed, even if
    # the remaining constraints happen to match every returned row. In the
    # all-refused case `_fetch_each` deliberately makes one fallback request
    # without the place; a matching year must not turn that into proof that
    # the omitted place filter held.
    if dropped:
        held = False
    narrowing["narrowed_in_the_rows"] = held
    if not numeric:
        explanation = "The connector returned no numeric observation values; no numbers were emitted."
    else:
        pinned = []
        if narrowing["places"]:
            pinned.append("place " + ", ".join(
                p["name"] for p in narrowing["places"] if p.get("code")))
        if years:
            pinned.append("year " + ", ".join(str(year) for year in years))
        explanation = (
            "Values are copied from stored observations; no join or derived "
            "number was emitted."
        )
        held = narrowing["narrowed_in_the_rows"]
        if dropped:
            dropped_names = [
                place.name
                for place in found.resolved_places
                if place.code in dropped
            ]
            requested_codes = [code for code in codes if code is not None]
            if len(dropped) == len(requested_codes):
                explanation = (
                    "The connector could not apply the requested place filter for "
                    f"{', '.join(dropped_names or dropped)}; the fallback request omitted "
                    "that filter, so these values may cover more than was asked for. "
                    + explanation
                )
            else:
                explanation = (
                    "The connector could not apply the requested place filter for "
                    f"{', '.join(dropped_names or dropped)}; these values do not fully "
                    "cover every requested place. " + explanation
                )
        elif pinned and held is False:
            explanation = (
                f"The request asked for {'; '.join(pinned)} and the rows came back "
                "unfiltered -- this connector does not apply the filter, so the "
                "values below cover more than was asked for. " + explanation
            )
        elif pinned:
            was = "narrowed" if held else "sent narrowed"
            explanation = (
                f"The request was {was} to {'; '.join(pinned)}. " + explanation
            )
        if narrowing["unresolved"]:
            # Said out loud rather than silently dropped: the register holds
            # more than one code for that name, so the rows below are not
            # filtered to it.
            explanation += (
                " Not narrowed to "
                + ", ".join(narrowing["unresolved"])
                + ": the register holds more than one code for that name."
            )
    return {
        "status": "completed",
        "numbers_retrieved": numeric,
        "dataset_id": fetch_step.dataset_id,
        "request_url": fetched.request_url,
        "http_status": fetched.http_status,
        "listed": fetched.counts.listed,
        "narrowing": narrowing,
        "observations": observations,
        "explanation": explanation,
    }


def _fetch_each(
    registry: Registry,
    fetch_step: Any,
    *,
    codes: list[str | None],
    years: tuple[int, ...],
    http: JsonHttp | None,
    max_cells: int | None,
) -> tuple[Any, list[str], list[str], list[bool | None]]:
    """One request per named place, and the ids they touched.

    A connector that cannot filter on kommune raises rather than ignoring the
    argument, which is the right behaviour and would otherwise turn a
    comparison question into an error. So a refused filter falls back to one
    unfiltered request -- still under the cell budget -- and the caller is
    told which filter was dropped, because an answer narrowed to nothing and
    an answer narrowed to Bærum must not read the same.
    """

    from_year = min(years) if years else None
    to_year = max(years) if years else None
    observation_ids: list[str] = []
    dropped: list[str] = []
    flags: list[bool | None] = []
    last = None
    for code in codes:
        try:
            last = fetch_observations(
                registry,
                fetch_step.dataset_id,
                table_id=fetch_step.table_id or "",
                kommune=code,
                from_year=from_year,
                to_year=to_year,
                http=http,
                max_cells=max_cells,
            )
        except Exception:
            if code is None:
                raise
            dropped.append(code)
            continue
        flags.append(getattr(last, "filter_applied", None))
        observation_ids.extend(last.observation_ids or [])
    if last is None:
        # Every place-filtered request was refused; ask once without it.
        last = fetch_observations(
            registry,
            fetch_step.dataset_id,
            table_id=fetch_step.table_id or "",
            kommune=None,  # explicit: the place filter was refused, not forgotten
            from_year=from_year,
            to_year=to_year,
            http=http,
            max_cells=max_cells,
        )
        flags.append(getattr(last, "filter_applied", None))
        observation_ids.extend(last.observation_ids or [])
    return last, observation_ids, dropped, flags


def _json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    import json

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


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


def _narrowing_held(
    observations: list[dict[str, Any]],
    places: tuple[Any, ...],
    years: tuple[int, ...],
) -> bool | None:
    """Whether the returned rows actually match what was asked for.

    `True` when every row that names the dimension agrees with the request,
    `False` when a row plainly contradicts it, and `None` when the rows say
    nothing either way -- which is the common case and is not a failure.

    The asymmetry is deliberate. A silently dropped filter is only detectable
    as a row that should not be there, so the check looks for that and makes
    no claim otherwise. Treating "cannot tell" as "did not work" would make
    every source without a named kommune dimension look broken.
    """

    if not observations or (not places and not years):
        return None
    wanted_places = [
        {
            str(value).casefold()
            for value in (place.code, place.name, place.label)
            if value
        }
        for place in places
        if place.code
    ]
    wanted_years = {str(year) for year in years}
    saw_places: set[int] = set()
    saw_year = False
    for row in observations:
        dimensions = row.get("dimensions")
        if not isinstance(dimensions, dict):
            continue
        for dimension, value in dimensions.items():
            text = str(value)
            if wanted_places and _looks_like_a_place_dimension(str(dimension)):
                matches = [
                    index
                    for index, options in enumerate(wanted_places)
                    if text.casefold() in options
                ]
                if not matches:
                    return False
                saw_places.update(matches)
            if wanted_years and _looks_like_a_time_dimension(str(dimension)):
                year = _year_in_dimension(text)
                if year is None:
                    continue
                saw_year = True
                if year not in wanted_years:
                    return False
    proved_every_kind = (
        len(saw_places) == len(wanted_places)
        and (not wanted_years or saw_year)
    )
    return True if proved_every_kind else None


def _looks_like_a_place_dimension(name: str) -> bool:
    """Whether a dimension's own name explicitly identifies a kommune.

    Constraints currently resolve only kommune names through the Brønnøysund
    register. A generic ``Region`` may mean a country, county or aggregation,
    so it cannot prove that kommune narrowing held.
    """

    folded = name.casefold()
    return "kommune" in folded or "municipality" in folded


def _looks_like_a_time_dimension(name: str) -> bool:
    folded = "".join(character for character in name.casefold() if character.isalnum())
    return folded in {"tid", "år", "aar", "year", "time", "period", "timeperiod"}


def _year_in_dimension(value: str) -> str | None:
    match = re.search(r"(?<!\d)((?:18|19|20)\d{2}|2100)(?!\d)", value)
    return match.group(1) if match else None
