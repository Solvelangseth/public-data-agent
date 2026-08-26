from __future__ import annotations

import json
from typing import Any, Callable

from public_data_agent.mapping import localized_text, preferred_text, unique_strings
from public_data_agent.models import HarvestCounts
from public_data_agent.registry import Registry
from public_data_agent.search import keywords_from_payload

ENRICH_SOURCE = "system"
ENRICH_METHOD = "deterministic_from_stored_metadata"
GEOGRAPHY_MISSING = "absent from stored spatial_json"
TIME_MISSING = "absent from stored issued, modified, and temporal columns"
FIELDS_MISSING = "no variable or column list is stored in the registry or harvested payload"

ProgressFn = Callable[[str], None]


def enrich(
    registry: Registry,
    *,
    limit: int | None = None,
    offset: int = 0,
    progress: ProgressFn | None = None,
) -> HarvestCounts:
    """Project stored harvest fields into enrichments. Does not write harvest tables."""

    log = progress or (lambda _message: None)
    counts = HarvestCounts()
    rows = sorted(registry.iter_search_rows(), key=lambda row: row["id"])
    if offset:
        rows = rows[offset:]
    if limit is not None:
        rows = rows[:limit]
    counts.listed = len(rows)
    log(f"listed {counts.listed} datasets to enrich")

    for row in rows:
        try:
            action = registry.upsert_enrichment(project_row(row))
        except Exception as exc:
            counts.failed += 1
            counts.errors.append({"id": row.get("id") or "", "error": str(exc)})
            continue
        if action == "inserted":
            counts.inserted += 1
        elif action == "updated":
            counts.updated += 1
        else:
            counts.unchanged += 1

    log(
        f"enrich completed: listed={counts.listed} inserted={counts.inserted} "
        f"updated={counts.updated} unchanged={counts.unchanged} failed={counts.failed}"
    )
    return counts


def project_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = _json_obj(row.get("payload_json"))
    topics = _topics(payload)
    aliases = _aliases(row, payload)
    geography = _geography(row)
    time_coverage = _time_coverage(row)
    fields = _fields(payload)
    missing: dict[str, str] = {}
    if geography is None:
        missing["geography"] = GEOGRAPHY_MISSING
    if time_coverage is None:
        missing["time_coverage"] = TIME_MISSING
    if fields is None:
        missing["fields"] = FIELDS_MISSING
    return {
        "dataset_id": row["id"],
        "source": ENRICH_SOURCE,
        "method": ENRICH_METHOD,
        "payload_hash": row["payload_hash"],
        "topics": topics,
        "aliases": aliases,
        "geography": geography,
        "time_coverage": time_coverage,
        "fields": fields,
        "can_answer": _can_answer(row, topics, geography, time_coverage),
        "missing": missing,
    }


def _topics(payload: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in _as_items(payload.get("theme")):
        if not isinstance(item, dict):
            continue
        values.extend(localized_text(item.get("title")).values())
        code = item.get("code")
        if isinstance(code, str) and code.strip():
            values.append(code)
    for item in _as_items(payload.get("losTheme")):
        if not isinstance(item, dict):
            continue
        labels = (
            localized_text(item.get("name"))
            or localized_text(item.get("prefLabel"))
            or localized_text(item.get("title"))
        )
        values.extend(labels.values())
    values.extend(keywords_from_payload(payload))
    return unique_strings([value for value in values if value and value.strip()])


def _aliases(row: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    title = row.get("title")
    values: list[str] = []
    for text in _json_obj(row.get("title_i18n_json")).values():
        if isinstance(text, str) and text.strip() and text != title:
            values.append(text)
    for keyword in keywords_from_payload(payload):
        if keyword != title:
            values.append(keyword)
    return unique_strings(values)


def _geography(row: dict[str, Any]) -> list[dict[str, Any]] | None:
    spatial = _json_list(row.get("spatial_json"))
    return spatial or None


def _time_coverage(row: dict[str, Any]) -> dict[str, Any] | None:
    issued = row.get("issued") or None
    modified = row.get("modified") or None
    temporal = _json_list(row.get("temporal_json"))
    if not issued and not modified and not temporal:
        return None
    return {"issued": issued, "modified": modified, "temporal": temporal}


def _fields(payload: dict[str, Any]) -> list[str] | None:
    for key in ("variables", "variableList", "variable_list"):
        value = payload.get(key)
        if not isinstance(value, list) or not value:
            continue
        names = [item for item in value if isinstance(item, str) and item.strip()]
        if names:
            return names
    return None


def _can_answer(
    row: dict[str, Any],
    topics: list[str],
    geography: list[dict[str, Any]] | None,
    time_coverage: dict[str, Any] | None,
) -> list[str]:
    questions: list[str] = []
    title = row.get("title")
    if title:
        questions.append(f"What is described by the dataset titled {title}?")
    publisher_name = row.get("publisher_name")
    if publisher_name:
        questions.append(f"Which datasets does {publisher_name} publish?")
    for topic in topics:
        questions.append(f"Which datasets are tagged {topic}?")
    for item in geography or []:
        label = _geo_label(item)
        if label:
            questions.append(f"Which datasets cover {label}?")
    start = row.get("temporal_start")
    if not start and time_coverage:
        temporal = time_coverage.get("temporal") or []
        if temporal and isinstance(temporal[0], dict):
            start = temporal[0].get("start")
    if start:
        questions.append(f"Which datasets cover the period starting {start}?")
    return questions


def _geo_label(item: dict[str, Any]) -> str | None:
    pref = item.get("pref_label")
    if isinstance(pref, dict):
        label = preferred_text(localized_text(pref))
        if label:
            return label
    code = item.get("code")
    if isinstance(code, str) and code.strip():
        return code
    uri = item.get("uri")
    if isinstance(uri, str) and uri.strip():
        return uri
    return None


def _as_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _json_obj(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    return []
