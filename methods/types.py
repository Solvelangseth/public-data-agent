"""Methods-boundary types. Observation is the input; derived values require lineage."""

from __future__ import annotations

from dataclasses import dataclass


YOY_GROWTH = "yoy_growth"
YOY_GROWTH_FORMULA = "(v_t - v_{t-1}) / v_{t-1}"
YOY_GROWTH_UNITS = "ratio"
YOY_GROWTH_INPUTS = ("value",)

PERIOD_CHANGE = "period_change"
PERIOD_CHANGE_FORMULA = "(v_t - v_prev) / v_prev"
PERIOD_CHANGE_UNITS = "ratio"
PERIOD_CHANGE_INPUTS = ("value",)

INDEX = "index"
INDEX_FORMULA = "100 * v_t / v_base"
INDEX_UNITS = "index (base = 100)"
INDEX_INPUTS = ("value",)

RANK = "rank"
RANK_FORMULA = "1 + count(peers in (period, measure) with value > v_t)"
RANK_UNITS = "rank (1 = highest)"
RANK_INPUTS = ("value",)
RANK_TIE_NOTE = "competition/min: equal values share this rank; the next rank skips"

RANK_CHANGE = "rank_change"
RANK_CHANGE_FORMULA = "rank_{t-1} - rank_t"
RANK_CHANGE_UNITS = "rank positions (positive = moved up)"
RANK_CHANGE_INPUTS = ("rank",)


@dataclass(frozen=True)
class Observation:
    """Canonical methods input. Matches stored fetch rows plus entity/period/source."""

    id: str
    entity: str
    period: str
    measure: str
    value: float
    source: str
    dataset_id: str
    table_id: str
    dimensions: tuple[tuple[str, str], ...]
    retrieved_at: str
    request_url: str
    publisher_name: str | None = None
    license: str | None = None
    access_path: str | None = None
    source_native_uri: str | None = None
    http_status: int | None = None


@dataclass(frozen=True)
class Lineage:
    """How one derived field was computed. Required on every derived value."""

    name: str
    formula: str
    input_columns: tuple[str, ...]
    units: str
    source_observation_ids: tuple[str, ...]
    source_periods: tuple[str, ...]
    note: str | None = None
    base_period: str | None = None
    base_observation_id: str | None = None
    peer_observation_ids: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("lineage.name is required")
        if not self.formula:
            raise ValueError("lineage.formula is required")
        if not self.input_columns:
            raise ValueError("lineage.input_columns is required")
        if not self.units:
            raise ValueError("lineage.units is required")
        if not self.source_observation_ids:
            raise ValueError("lineage.source_observation_ids is required")
        if not self.source_periods:
            raise ValueError("lineage.source_periods is required")
        if self.name == INDEX and not self.base_period:
            raise ValueError("index lineage requires base_period")
        if self.name in {RANK, RANK_CHANGE} and not self.peer_observation_ids:
            raise ValueError("rank lineage requires peer_observation_ids")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "formula": self.formula,
            "input_columns": list(self.input_columns),
            "units": self.units,
            "source_observation_ids": list(self.source_observation_ids),
            "source_periods": list(self.source_periods),
        }
        if self.note is not None:
            payload["note"] = self.note
        if self.base_period is not None:
            payload["base_period"] = self.base_period
        if self.base_observation_id is not None:
            payload["base_observation_id"] = self.base_observation_id
        if self.peer_observation_ids is not None:
            payload["peer_observation_ids"] = list(self.peer_observation_ids)
        return payload


@dataclass(frozen=True)
class DerivedValue:
    """A derived number that cannot be constructed without lineage."""

    value: float | None
    lineage: Lineage

    def __post_init__(self) -> None:
        if not isinstance(self.lineage, Lineage):
            raise TypeError("DerivedValue.lineage must be a Lineage instance")
        if self.lineage is None:
            raise TypeError("derived value without lineage is unrepresentable")

    def to_dict(self) -> dict[str, object]:
        return {"value": self.value, "lineage": self.lineage.to_dict()}


@dataclass(frozen=True)
class SeriesRow:
    """One cleaned observation plus its derived columns."""

    observation: Observation
    yoy_growth: DerivedValue
    period_change: DerivedValue
    index: DerivedValue
    rank: DerivedValue
    rank_change: DerivedValue

    def derived_columns(self) -> tuple[DerivedValue, ...]:
        return (self.yoy_growth, self.period_change, self.index, self.rank, self.rank_change)

    def __post_init__(self) -> None:
        if not isinstance(self.period_change, DerivedValue):
            raise TypeError("SeriesRow.period_change must be a DerivedValue with lineage")
        if not isinstance(self.index, DerivedValue):
            raise TypeError("SeriesRow.index must be a DerivedValue with lineage")
        if not isinstance(self.rank, DerivedValue):
            raise TypeError("SeriesRow.rank must be a DerivedValue with lineage")
        if not isinstance(self.rank_change, DerivedValue):
            raise TypeError("SeriesRow.rank_change must be a DerivedValue with lineage")
