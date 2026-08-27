"""Pure transforms over cleaned Observation rows."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from methods.types import (
    YOY_GROWTH,
    YOY_GROWTH_FORMULA,
    YOY_GROWTH_INPUTS,
    YOY_GROWTH_UNITS,
    DerivedValue,
    Lineage,
    Observation,
    SeriesRow,
)


def derive_yoy(rows: Sequence[Observation]) -> tuple[SeriesRow, ...]:
    """Year-over-year growth: (v_t - v_{t-1}) / v_{t-1}.

    Groups by (entity, measure). The first period in each group has no rate.
    A zero prior value is undefined, never a guessed number.
    """

    groups: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    for row in rows:
        groups[(row.entity, row.measure)].append(row)

    out: list[SeriesRow] = []
    for key in sorted(groups):
        series = sorted(groups[key], key=lambda row: (row.period, row.id))
        previous: Observation | None = None
        for current in series:
            out.append(SeriesRow(observation=current, yoy_growth=_yoy(current, previous)))
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
