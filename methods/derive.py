"""Pure transforms over cleaned Observation rows."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence

from methods.types import (
    INDEX,
    INDEX_FORMULA,
    INDEX_INPUTS,
    INDEX_UNITS,
    PERIOD_CHANGE,
    PERIOD_CHANGE_FORMULA,
    PERIOD_CHANGE_INPUTS,
    PERIOD_CHANGE_UNITS,
    RANK,
    RANK_CHANGE,
    RANK_CHANGE_FORMULA,
    RANK_CHANGE_INPUTS,
    RANK_CHANGE_UNITS,
    RANK_FORMULA,
    RANK_INPUTS,
    RANK_TIE_NOTE,
    RANK_UNITS,
    YOY_GROWTH,
    YOY_GROWTH_FORMULA,
    YOY_GROWTH_INPUTS,
    YOY_GROWTH_UNITS,
    DerivedValue,
    Lineage,
    Observation,
    SeriesRow,
)


def derive(
    rows: Sequence[Observation],
    *,
    base_period: str | None = None,
) -> tuple[SeriesRow, ...]:
    """YoY, period change, index, rank, and rank_change over cleaned rows.

    Rank is competition/min within (period, measure): 1 = highest value.
    Rank change is rank_{t-1} - rank_t (positive = moved up). The first
    period has no rank_change. A missing or zero index base is undefined.
    """

    series_groups: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    rank_groups: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    for row in rows:
        series_groups[(row.entity, row.measure)].append(row)
        rank_groups[(row.period, row.measure)].append(row)

    ranks = _ranks_by_id(rank_groups)

    out: list[SeriesRow] = []
    for key in sorted(series_groups):
        series = sorted(series_groups[key], key=lambda row: (row.period, row.id))
        base = _base_row(series, base_period)
        previous: Observation | None = None
        previous_rank: tuple[int, tuple[str, ...]] | None = None
        for current in series:
            current_rank = ranks[current.id]
            yoy_growth, period_change = _period_step(current, previous)
            out.append(
                SeriesRow(
                    observation=current,
                    yoy_growth=yoy_growth,
                    period_change=period_change,
                    index=_index(current, base, requested_base_period=base_period),
                    rank=_rank(current, current_rank),
                    rank_change=_rank_change(current, current_rank, previous, previous_rank),
                )
            )
            previous = current
            previous_rank = current_rank
    out.sort(
        key=lambda row: (
            row.observation.entity,
            row.observation.measure,
            row.observation.period,
            row.observation.id,
        )
    )
    return tuple(out)


def derive_yoy(rows: Sequence[Observation], *, base_period: str | None = None) -> tuple[SeriesRow, ...]:
    """Backward-compatible alias. Prefer derive()."""

    return derive(rows, base_period=base_period)


def _calendar_year(period: str) -> int | None:
    if re.fullmatch(r"\d{4}", period) is None:
        return None
    return int(period)


def _is_adjacent_calendar_year(prev: str, curr: str) -> bool:
    previous_year = _calendar_year(prev)
    current_year = _calendar_year(curr)
    return (
        previous_year is not None
        and current_year is not None
        and current_year - previous_year == 1
    )


def _base_row(series: list[Observation], base_period: str | None) -> Observation | None:
    if not series:
        return None
    if base_period is None:
        return series[0]
    for row in series:
        if row.period == base_period:
            return row
    return None


def _period_step(
    current: Observation,
    previous: Observation | None,
) -> tuple[DerivedValue, DerivedValue]:
    if previous is None:
        source_ids = (current.id,)
        source_periods = (current.period,)
        return (
            DerivedValue(
                value=None,
                lineage=Lineage(
                    name=YOY_GROWTH,
                    formula=YOY_GROWTH_FORMULA,
                    input_columns=YOY_GROWTH_INPUTS,
                    units=YOY_GROWTH_UNITS,
                    source_observation_ids=source_ids,
                    source_periods=source_periods,
                    note="undefined: no prior period",
                ),
            ),
            DerivedValue(
                value=None,
                lineage=Lineage(
                    name=PERIOD_CHANGE,
                    formula=PERIOD_CHANGE_FORMULA,
                    input_columns=PERIOD_CHANGE_INPUTS,
                    units=PERIOD_CHANGE_UNITS,
                    source_observation_ids=source_ids,
                    source_periods=source_periods,
                    note="undefined: no prior period",
                ),
            ),
        )

    source_ids = (previous.id, current.id)
    source_periods = (previous.period, current.period)
    if _is_adjacent_calendar_year(previous.period, current.period):
        if previous.value == 0:
            rate: float | None = None
            note: str | None = "undefined: v_{t-1} is 0"
        else:
            rate = (current.value - previous.value) / previous.value
            note = None
        return (
            DerivedValue(
                value=rate,
                lineage=Lineage(
                    name=YOY_GROWTH,
                    formula=YOY_GROWTH_FORMULA,
                    input_columns=YOY_GROWTH_INPUTS,
                    units=YOY_GROWTH_UNITS,
                    source_observation_ids=source_ids,
                    source_periods=source_periods,
                    note=note,
                ),
            ),
            DerivedValue(
                value=None,
                lineage=Lineage(
                    name=PERIOD_CHANGE,
                    formula=PERIOD_CHANGE_FORMULA,
                    input_columns=PERIOD_CHANGE_INPUTS,
                    units=PERIOD_CHANGE_UNITS,
                    source_observation_ids=source_ids,
                    source_periods=source_periods,
                    note="undefined: step is one calendar year; rate is in yoy_growth",
                ),
            ),
        )

    if previous.value == 0:
        rate = None
        note = "undefined: v_prev is 0; stored step is not a one-year rate"
    else:
        rate = (current.value - previous.value) / previous.value
        note = "change across stored step; not a one-year rate"
    return (
        DerivedValue(
            value=None,
            lineage=Lineage(
                name=YOY_GROWTH,
                formula=YOY_GROWTH_FORMULA,
                input_columns=YOY_GROWTH_INPUTS,
                units=YOY_GROWTH_UNITS,
                source_observation_ids=source_ids,
                source_periods=source_periods,
                note="undefined: periods are not adjacent calendar years",
            ),
        ),
        DerivedValue(
            value=rate,
            lineage=Lineage(
                name=PERIOD_CHANGE,
                formula=PERIOD_CHANGE_FORMULA,
                input_columns=PERIOD_CHANGE_INPUTS,
                units=PERIOD_CHANGE_UNITS,
                source_observation_ids=source_ids,
                source_periods=source_periods,
                note=note,
            ),
        ),
    )


def _index(
    current: Observation,
    base: Observation | None,
    *,
    requested_base_period: str | None,
) -> DerivedValue:
    if base is None:
        period = requested_base_period or current.period
        return DerivedValue(
            value=None,
            lineage=Lineage(
                name=INDEX,
                formula=INDEX_FORMULA,
                input_columns=INDEX_INPUTS,
                units=INDEX_UNITS,
                source_observation_ids=(current.id,),
                source_periods=(current.period,),
                note="undefined: base period not in series",
                base_period=period,
            ),
        )
    if base.value == 0:
        return DerivedValue(
            value=None,
            lineage=Lineage(
                name=INDEX,
                formula=INDEX_FORMULA,
                input_columns=INDEX_INPUTS,
                units=INDEX_UNITS,
                source_observation_ids=(base.id, current.id),
                source_periods=(base.period, current.period),
                note="undefined: v_base is 0",
                base_period=base.period,
                base_observation_id=base.id,
            ),
        )
    if current.id == base.id:
        value = 100.0
        ids = (current.id,)
        periods = (current.period,)
    else:
        value = 100.0 * current.value / base.value
        ids = (base.id, current.id)
        periods = (base.period, current.period)
    return DerivedValue(
        value=value,
        lineage=Lineage(
            name=INDEX,
            formula=INDEX_FORMULA,
            input_columns=INDEX_INPUTS,
            units=INDEX_UNITS,
            source_observation_ids=ids,
            source_periods=periods,
            base_period=base.period,
            base_observation_id=base.id,
        ),
    )


def _ranks_by_id(
    groups: dict[tuple[str, str], list[Observation]],
) -> dict[str, tuple[int, tuple[str, ...]]]:
    """Map observation id -> (competition rank, peer ids) per (period, measure)."""

    out: dict[str, tuple[int, tuple[str, ...]]] = {}
    for group in groups.values():
        peers = tuple(sorted(row.id for row in group))
        ordered = sorted(group, key=lambda row: (-row.value, row.entity, row.id))
        index = 0
        while index < len(ordered):
            end = index + 1
            while end < len(ordered) and ordered[end].value == ordered[index].value:
                end += 1
            rank = index + 1
            for row in ordered[index:end]:
                out[row.id] = (rank, peers)
            index = end
    return out


def _rank(current: Observation, ranked: tuple[int, tuple[str, ...]]) -> DerivedValue:
    rank, peers = ranked
    return DerivedValue(
        value=float(rank),
        lineage=Lineage(
            name=RANK,
            formula=RANK_FORMULA,
            input_columns=RANK_INPUTS,
            units=RANK_UNITS,
            source_observation_ids=(current.id,),
            source_periods=(current.period,),
            note=RANK_TIE_NOTE,
            peer_observation_ids=peers,
        ),
    )


def _rank_change(
    current: Observation,
    current_rank: tuple[int, tuple[str, ...]],
    previous: Observation | None,
    previous_rank: tuple[int, tuple[str, ...]] | None,
) -> DerivedValue:
    if previous is None or previous_rank is None:
        return DerivedValue(
            value=None,
            lineage=Lineage(
                name=RANK_CHANGE,
                formula=RANK_CHANGE_FORMULA,
                input_columns=RANK_CHANGE_INPUTS,
                units=RANK_CHANGE_UNITS,
                source_observation_ids=(current.id,),
                source_periods=(current.period,),
                note="undefined: no prior period; positive would mean moved up",
                peer_observation_ids=current_rank[1],
            ),
        )
    peers = tuple(sorted(set(previous_rank[1]) | set(current_rank[1])))
    return DerivedValue(
        value=float(previous_rank[0] - current_rank[0]),
        lineage=Lineage(
            name=RANK_CHANGE,
            formula=RANK_CHANGE_FORMULA,
            input_columns=RANK_CHANGE_INPUTS,
            units=RANK_CHANGE_UNITS,
            source_observation_ids=(previous.id, current.id),
            source_periods=(previous.period, current.period),
            note="positive = moved up (lower rank number)",
            peer_observation_ids=peers,
        ),
    )
