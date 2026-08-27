"""Pure transforms over cleaned Observation rows."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from methods.types import (
    INDEX,
    INDEX_FORMULA,
    INDEX_INPUTS,
    INDEX_UNITS,
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
    """YoY growth plus an index (base period = 100) per (entity, measure).

    The default base is the first period in that series. A missing or zero
    base is undefined, never a guessed number.
    """

    groups: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    for row in rows:
        groups[(row.entity, row.measure)].append(row)

    out: list[SeriesRow] = []
    for key in sorted(groups):
        series = sorted(groups[key], key=lambda row: (row.period, row.id))
        base = _base_row(series, base_period)
        previous: Observation | None = None
        for current in series:
            out.append(
                SeriesRow(
                    observation=current,
                    yoy_growth=_yoy(current, previous),
                    index=_index(current, base, requested_base_period=base_period),
                )
            )
            previous = current
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


def _base_row(series: list[Observation], base_period: str | None) -> Observation | None:
    if not series:
        return None
    if base_period is None:
        return series[0]
    for row in series:
        if row.period == base_period:
            return row
    return None


def _yoy(current: Observation, previous: Observation | None) -> DerivedValue:
    if previous is None:
        return DerivedValue(
            value=None,
            lineage=Lineage(
                name=YOY_GROWTH,
                formula=YOY_GROWTH_FORMULA,
                input_columns=YOY_GROWTH_INPUTS,
                units=YOY_GROWTH_UNITS,
                source_observation_ids=(current.id,),
                source_periods=(current.period,),
                note="undefined: no prior period",
            ),
        )
    if previous.value == 0:
        rate: float | None = None
        note: str | None = "undefined: v_{t-1} is 0"
    else:
        rate = (current.value - previous.value) / previous.value
        note = None
    return DerivedValue(
        value=rate,
        lineage=Lineage(
            name=YOY_GROWTH,
            formula=YOY_GROWTH_FORMULA,
            input_columns=YOY_GROWTH_INPUTS,
            units=YOY_GROWTH_UNITS,
            source_observation_ids=(previous.id, current.id),
            source_periods=(previous.period, current.period),
            note=note,
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
