"""Parse and validate observations at the methods input boundary."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping

from methods.types import Observation

_YEAR = re.compile(r"^\d{4}$")
PERIOD_ALIASES = frozenset(
    {
        "år",
        "ar",
        "aar",
        "årstall",
        "year",
        "tid",
        "time",
        "period",
    }
)
ENTITY_ALIASES = frozenset(
    {
        "geografisk område",
        "geografisk omrade",
        "region",
        "entity",
        "geography",
        "area",
        "kommune",
        "fylke",
        "geo",
    }
)


class CleanError(ValueError):
    """A row failed the Observation schema and cannot enter methods."""


def clean(rows: Iterable[Mapping[str, Any]]) -> tuple[Observation, ...]:
    """Validate once. Drop null/non-numeric values. Sort by (entity, measure, period).

    After this function, transforms trust the typed rows.
    """

    kept: list[Observation] = []
    for index, raw in enumerate(rows):
        parsed = _parse_row(raw, index=index)
        if parsed is None:
            continue
        kept.append(parsed)
    kept.sort(key=lambda row: (row.entity, row.measure, row.period, row.id))
    return tuple(kept)


def _parse_row(raw: Mapping[str, Any], *, index: int) -> Observation | None:
    row_id = _require_text(raw, "id", index)
    dataset_id = _require_text(raw, "dataset_id", index)
    table_id = _text(raw.get("table_id")) or ""
    measure = _require_text(raw, "measure", index)
    dimensions = _dimensions(raw, index)
    value = _numeric_value(raw)
    if value is None:
        return None
    period = _text(raw.get("period")) or _period_from_dimensions(dimensions)
    if not period:
        raise CleanError(f"row {index} ({row_id}): no period in dimensions or period field")
    entity = (
        _text(raw.get("entity"))
        or _entity_from_dimensions(dimensions)
        or dataset_id
    )
    source = _text(raw.get("source")) or dataset_id
    retrieved_at = _text(raw.get("retrieved_at")) or ""
    request_url = _text(raw.get("request_url")) or ""
    return Observation(
        id=row_id,
        entity=entity,
        period=period,
        measure=measure,
        value=value,
        source=source,
        dataset_id=dataset_id,
        table_id=table_id,
        dimensions=tuple(sorted(dimensions.items())),
        retrieved_at=retrieved_at,
        request_url=request_url,
        publisher_name=_text(raw.get("publisher_name")),
        license=_text(raw.get("license")),
        access_path=_text(raw.get("access_path")),
        source_native_uri=_text(raw.get("source_native_uri")),
        http_status=_optional_int(raw.get("http_status")),
    )


def _require_text(raw: Mapping[str, Any], key: str, index: int) -> str:
    value = _text(raw.get(key))
    if not value:
        raise CleanError(f"row {index}: missing {key}")
    return value


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dimensions(raw: Mapping[str, Any], index: int) -> dict[str, str]:
    payload = raw.get("dimensions")
    if payload is None:
        payload = raw.get("dimensions_json")
    if payload is None:
        return {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CleanError(f"row {index}: dimensions_json is not JSON") from exc
    if not isinstance(payload, dict):
        raise CleanError(f"row {index}: dimensions must be an object")
    out: dict[str, str] = {}
    for key, value in payload.items():
        if value is None:
            continue
        out[str(key)] = str(value)
    return out


def _numeric_value(raw: Mapping[str, Any]) -> float | None:
    if "value" in raw and raw.get("value") is not None:
        return _coerce_number(raw.get("value"))
    if "value_json" in raw:
        payload = raw.get("value_json")
        if payload is None or payload == "":
            return None
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                return _coerce_number(payload)
        return _coerce_number(payload)
    return None


def _coerce_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number != number:  # NaN
            return None
        return number
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"null", "none", "nan", "."}:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = text
        if parsed is not text:
            return _coerce_number(parsed)
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _period_from_dimensions(dimensions: dict[str, str]) -> str | None:
    alias_hit: str | None = None
    year_hit: str | None = None
    for key, value in dimensions.items():
        folded = key.casefold()
        if folded in PERIOD_ALIASES:
            alias_hit = value
            break
        if year_hit is None and _YEAR.match(value):
            year_hit = value
    return alias_hit or year_hit


def _entity_from_dimensions(dimensions: dict[str, str]) -> str | None:
    leftover: list[tuple[str, str]] = []
    for key, value in dimensions.items():
        folded = key.casefold()
        if folded in PERIOD_ALIASES or _YEAR.match(value):
            continue
        if folded in ENTITY_ALIASES:
            return value
        leftover.append((key, value))
    if leftover:
        leftover.sort(key=lambda item: item[0].casefold())
        values = [value for _key, value in leftover]
        return values[0] if len(values) == 1 else " / ".join(values)
    return None
