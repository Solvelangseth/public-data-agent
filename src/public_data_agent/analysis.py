"""Small deterministic operations over stored observation cells."""

from __future__ import annotations

import json
from typing import Any

from public_data_agent.contracts import Provenance, ToolResult
from public_data_agent.registry import Registry


def run_analysis(
    registry: Registry,
    dataset_id: str,
    *,
    filters: dict[str, Any] | None = None,
    measure: str | None = None,
    series: str | None = None,
    columns: list[str] | None = None,
    group_by: list[str] | None = None,
    aggregate: str | None = None,
    sort_by: str | None = None,
    descending: bool = False,
) -> ToolResult:
    """Filter/select stored cells; never fetches or invents missing values."""
    dataset = registry.get_dataset(dataset_id)
    if dataset is None:
        return ToolResult(status="failed", error=f"dataset not found in registry: {dataset_id}")
    filters = filters or {}
    rows: list[dict[str, Any]] = []
    for row in registry.list_observations(dataset_id, series=series):
        dimensions = _decode(row.get("dimensions_json")) or {}
        # Agents commonly use ``measure=value`` to request numeric cells.  The
        # stored measure label is source-defined and must not be guessed.
        if measure is not None and measure != "value" and row.get("measure") != measure:
            continue
        if any(
            (str(dimensions.get(key)) not in {str(item) for item in value} if isinstance(value, (list, tuple, set)) else str(dimensions.get(key)) != str(value))
            for key, value in filters.items()
        ):
            continue
        item = {
            "observation_id": row["id"],
            "dataset_id": dataset_id,
            "series": row.get("series"),
            "table_id": row["table_id"],
            "measure": row["measure"],
            "value": _decode(row.get("value_json")),
            "dimensions": dimensions,
        }
        rows.append(item)
    if group_by:
        rows = _aggregate(rows, group_by, aggregate or "count")
    if columns:
        rows = [{key: item[key] for key in columns if key in item} for item in rows]
    if sort_by:
        # Missing values must never win a ranking.  The previous key put them
        # first under descending=True, so "largest" led with empty cells.
        present = [item for item in rows if item.get(sort_by) is not None]
        missing = [item for item in rows if item.get(sort_by) is None]
        present.sort(key=lambda item: item.get(sort_by), reverse=descending)
        rows = present + missing
    provenance = [
        Provenance(
            dataset_id=dataset_id,
            title=dataset.get("title"),
            publisher=dataset.get("publisher_name"),
            license=dataset.get("license"),
            access_path=dataset.get("access_path"),
        )
    ]
    result = ToolResult(status="completed", values=rows, provenance=provenance)
    result.warnings = _analysis_warnings(
        registry,
        dataset_id,
        rows,
        filters=filters,
        measure=measure,
        series=series,
        group_by=group_by,
        aggregate=aggregate,
    )
    return result


MAX_LISTED_VALUES = 40
# Stored labels that denote an "all categories" cell.  Summing such a row
# together with its own parts double counts, so callers are warned rather
# than handed a plausible wrong total.
TOTAL_LABELS = frozenset({"i alt", "alle", "total", "totalt", "begge kjønn", "alle bydeler i oslo"})


# How many records one call will return before it says so. A Klass
# classification holds 7,127 items, and handing all of them back is not an
# answer, it is a file.
RECORD_PAGE = 200

# How much geometry one call may hand back. A single Havforskningsinstituttet
# advisory polygon carries 24 MB of coordinates, so `include_geometry` without
# a bound is a download that happens to be shaped like an answer. Whole shapes
# are included until the budget is spent and the rest are left out and
# counted: a geometry is complete or absent, never truncated, because half a
# polygon is a different place.
GEOMETRY_BUDGET = 200_000


def run_record_analysis(
    registry: Registry,
    dataset_id: str,
    *,
    kind: str | None = None,
    filters: dict[str, Any] | None = None,
    columns: list[str] | None = None,
    sort_by: str | None = None,
    descending: bool = False,
    limit: int = RECORD_PAGE,
    include_geometry: bool = False,
) -> ToolResult:
    """Filter/select stored records; never fetches or invents missing values.

    The counterpart of `run_analysis` for the store that holds things rather
    than measurements. It exists because 17,900 rows moved into `records` this
    week and nothing could read one: the tools said, correctly, that they only
    read observations, and then there was nowhere else to go.

    Records are not blended with observations. A dataset holds one shape or the
    other, and a caller that gets rows back is told which store they came from.

    A feature's geometry is named but not spent by default. One Havforsknings-
    instituttet contour carries four thousand characters of coordinates, and a
    page of them is a download rather than an answer; `geometry_type` is the
    publisher's own word for what is stored and `include_geometry` hands over
    the shape itself. Nothing is derived from it -- no centroid, no bounding
    box -- because a point computed from a polygon is a value no one published.
    """

    dataset = registry.get_dataset(dataset_id)
    if dataset is None:
        return ToolResult(status="failed", error=f"dataset not found in registry: {dataset_id}")
    filters = filters or {}
    rows: list[dict[str, Any]] = []
    total = 0
    spent = 0
    oversized = 0
    for row in registry.list_records(dataset_id, kind=kind):
        attributes = _decode(row.get("attributes_json")) or {}
        geometry = _decode(row.get("geometry_json"))
        item = {
            "record_id": row["id"],
            "dataset_id": dataset_id,
            "kind": row["kind"],
            "series": row.get("series"),
            "subject_scheme": row.get("subject_scheme"),
            "subject_code": row.get("subject_code"),
            "subject_label": row.get("subject_label"),
            "period": row.get("period"),
            "measure": row.get("measure"),
            "value": _decode(row.get("value_json")),
            "attributes": attributes,
            "geometry_type": (geometry or {}).get("type") if isinstance(geometry, dict) else None,
        }
        if include_geometry and geometry is not None:
            size = len(json.dumps(geometry, ensure_ascii=False))
            if spent + size <= GEOMETRY_BUDGET:
                item["geometry"] = geometry
                spent += size
            else:
                oversized += 1
        if any(
            not _matches(item.get(key, attributes.get(key)), value)
            for key, value in filters.items()
        ):
            continue
        total += 1
        if len(rows) < limit:
            rows.append(item)
    if sort_by:
        present = [item for item in rows if item.get(sort_by) is not None]
        missing = [item for item in rows if item.get(sort_by) is None]
        present.sort(key=lambda item: str(item.get(sort_by)), reverse=descending)
        rows = present + missing
    if columns:
        rows = [{key: item[key] for key in columns if key in item} for item in rows]
    result = ToolResult(
        status="completed",
        values=rows,
        provenance=[
            Provenance(
                dataset_id=dataset_id,
                title=dataset.get("title"),
                publisher=dataset.get("publisher_name"),
                license=dataset.get("license"),
                access_path=dataset.get("access_path"),
            )
        ],
    )
    if include_geometry and oversized:
        result_warning = (
            f"{oversized} of these rows carry a geometry left out to stay under the "
            f"{GEOMETRY_BUDGET:,}-character budget; narrow with filters to see them. "
            f"The shapes included are whole, never cut short."
        )
    elif not include_geometry:
        withheld = sum(1 for row in rows if row.get("geometry_type"))
        result_warning = (
            f"{withheld} of these rows carry a geometry that is not included; "
            f"ask with include_geometry=true for the shapes themselves."
        ) if withheld else None
    else:
        result_warning = None
    if total > len(rows):
        # Said plainly, because a truncated list that looks complete is how a
        # caller comes to report "Norway has 200 municipalities".
        result.warnings = [
            f"{total} records matched and {len(rows)} are returned; narrow with "
            f"filters or raise the limit before counting these."
        ]
    if result_warning:
        result.warnings = list(result.warnings or []) + [result_warning]
    return result


def _matches(stored: Any, wanted: Any) -> bool:
    if isinstance(wanted, (list, tuple, set)):
        return str(stored) in {str(item) for item in wanted}
    return str(stored) == str(wanted)


def stored_records(registry: Registry, dataset_id: str) -> dict[str, int]:
    """How many records of each kind a dataset holds.

    The observation store is not the whole store. A company, a building and a
    parliamentary decision live in `records`, and a tool that counts only
    observations reports a dataset holding a company as empty -- which reads as
    "there is nothing here" rather than "I cannot read what is here".
    """

    rows = registry.conn.execute(
        "SELECT kind, COUNT(*) AS n FROM records WHERE dataset_id = ? GROUP BY kind",
        (dataset_id,),
    ).fetchall()
    return {row["kind"]: int(row["n"]) for row in rows}


def describe_observations(
    registry: Registry, dataset_id: str, *, series: str | None = None
) -> dict[str, Any]:
    """Summarise the stored observation store so a caller can pick real filters.

    Nothing here is inferred: every key, value, and count is read back from
    rows the connectors actually wrote.  Without this a model has to guess
    dimension names, and a guessed name silently matches no rows.
    """

    rows = list(registry.list_observations(dataset_id, series=series))
    series_counts: dict[str, int] = {}
    dimensions: dict[str, dict[str, int]] = {}
    measures: dict[str, int] = {}
    shapes: dict[tuple[str, ...], int] = {}
    for row in rows:
        dims = _decode(row.get("dimensions_json")) or {}
        if not isinstance(dims, dict):
            dims = {}
        shapes[tuple(sorted(dims))] = shapes.get(tuple(sorted(dims)), 0) + 1
        for key, value in dims.items():
            dimensions.setdefault(key, {})
            label = str(value)
            dimensions[key][label] = dimensions[key].get(label, 0) + 1
        label = str(row.get("series") or "(untagged)")
        series_counts[label] = series_counts.get(label, 0) + 1
        measure = row.get("measure")
        if measure is not None:
            measures[str(measure)] = measures.get(str(measure), 0) + 1

    described: dict[str, Any] = {}
    for key, counts in sorted(dimensions.items()):
        values = sorted(counts)
        totals = [value for value in values if value.casefold() in TOTAL_LABELS]
        described[key] = {
            "distinct": len(values),
            "values": values[:MAX_LISTED_VALUES],
            "truncated": len(values) > MAX_LISTED_VALUES,
            "row_count": sum(counts.values()),
            "total_like_values": totals,
        }

    warnings: list[str] = []
    if len(shapes) > 1:
        readable = sorted(", ".join(shape) or "(no dimensions)" for shape in shapes)
        warnings.append(
            f"this dataset stores {len(shapes)} incompatible dimension shapes "
            f"({'; '.join(readable)}); a filter valid for one shape matches no rows in another. "
            f"Pass series=<one of {sorted(series_counts)}> to scope to a single shape."
        )
    for key, info in described.items():
        if info["total_like_values"]:
            warnings.append(
                f"dimension {key} mixes total rows {info['total_like_values']} with their parts; "
                "filter to one level before summing or ranking"
            )
    return {
        "dataset_id": dataset_id,
        "series": series,
        "observation_count": len(rows),
        "series_counts": dict(sorted(series_counts.items())),
        "dimensions": described,
        "measures": sorted(measures),
        "dimension_shapes": [
            {"dimensions": list(shape), "row_count": count} for shape, count in sorted(shapes.items())
        ],
        "warnings": warnings,
    }


def _analysis_warnings(
    registry: Registry,
    dataset_id: str,
    rows: list[dict[str, Any]],
    *,
    filters: dict[str, Any],
    measure: str | None,
    series: str | None,
    group_by: list[str] | None,
    aggregate: str | None,
) -> list[str]:
    """Explain an empty or double-counting result instead of returning it bare."""

    schema = describe_observations(registry, dataset_id, series=series)
    warnings: list[str] = []
    if not rows:
        if schema["observation_count"] == 0 and series is not None:
            available = describe_observations(registry, dataset_id)
            if available["observation_count"]:
                return [
                    f"no rows matched: series={series!r} holds no observations. "
                    f"Stored series for this dataset are {sorted(available['series_counts'])}."
                ]
        if schema["observation_count"] == 0:
            # A dataset can hold rows and no observations. Telling the caller
            # to fetch one of those sends it to the network for data already
            # in the registry -- 17,900 rows moved into `records` and this
            # advice stayed written for the world where they had not.
            held = stored_records(registry, dataset_id)
            if held:
                kinds = ", ".join(
                    f"{n} {name} record" + ("s" if n != 1 else "")
                    for name, n in sorted(held.items())
                )
                return [
                    f"this dataset stores no observations, but {kinds} are already "
                    "stored. Do not fetch: read them from the record store, which is "
                    "what run_analysis returns when no observation matches."
                ]
            # "Nothing stored" is not "no such data exists".  Saying so stopped
            # the agent after one step and reported absence it had not checked.
            return [
                "this dataset has no stored observations yet, so nothing could match. "
                "This is NOT evidence that the data does not exist: call fetch for this "
                "dataset first, then re-run the analysis."
            ]
        if measure is not None and measure != "value" and measure not in schema["measures"]:
            warnings.append(
                f"no rows matched: measure={measure!r} is not a stored measure; "
                f"stored measures are {schema['measures']}. Use measure='value' for numeric cells."
            )
        unknown = sorted(key for key in filters if key not in schema["dimensions"])
        if unknown:
            warnings.append(
                f"no rows matched: filter key(s) {unknown} are not stored dimensions; "
                f"stored dimensions are {sorted(schema['dimensions'])}"
            )
        # Filters drawn from two different shapes can each be individually valid
        # and still match nothing together, because no single row carries both.
        shapes = [set(shape["dimensions"]) for shape in schema["dimension_shapes"]]
        keys = set(filters) - set(unknown)
        if keys and shapes and not any(keys <= shape for shape in shapes):
            warnings.append(
                f"no rows matched: filter keys {sorted(keys)} come from different dimension shapes "
                f"and no single observation has all of them. Each row uses exactly one of: "
                f"{[sorted(shape) for shape in shapes]}. Pick one shape and filter only within it."
            )
        elif not warnings:
            for key, value in filters.items():
                stored = schema["dimensions"].get(key, {})
                listed = stored.get("values") or []
                if stored.get("truncated"):
                    continue
                wanted = [str(item) for item in value] if isinstance(value, (list, tuple, set)) else [str(value)]
                missing = [item for item in wanted if item not in listed]
                if missing:
                    warnings.append(
                        f"no rows matched: {key} value(s) {missing} are not stored; stored values are {listed}"
                    )
        if not warnings:
            warnings.append("no stored observation matched these filters; nothing was fetched or inferred")
        return warnings

    if aggregate in {"sum", "mean"} and group_by:
        collapsed = [
            key
            for key in schema["dimensions"]
            if key not in group_by and key not in filters and schema["dimensions"][key]["distinct"] > 1
        ]
        if collapsed:
            warnings.append(
                f"aggregate={aggregate} collapses unconstrained dimension(s) {sorted(collapsed)}; "
                "each group sums across every stored value of them, which double counts "
                "overlapping categories. Filter them first."
            )
    for key in list(filters) + list(group_by or []):
        totals = (schema["dimensions"].get(key) or {}).get("total_like_values") or []
        if totals and str(filters.get(key)) not in {str(item) for item in totals}:
            warnings.append(f"dimension {key} contains total row(s) {totals} alongside their parts")
    return warnings


def _decode(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _aggregate(rows: list[dict[str, Any]], group_by: list[str], aggregate: str) -> list[dict[str, Any]]:
    if aggregate not in {"count", "sum", "mean"}:
        raise ValueError("aggregate must be count, sum, or mean")
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        dimensions = row.get("dimensions") or {}
        key = tuple(row.get(field, dimensions.get(field)) for field in group_by)
        groups.setdefault(key, []).append(row)
    out: list[dict[str, Any]] = []
    for key, members in groups.items():
        item = {field: value for field, value in zip(group_by, key)}
        if aggregate == "count":
            value: Any = len(members)
        else:
            numeric = [member.get("value") for member in members if isinstance(member.get("value"), (int, float)) and not isinstance(member.get("value"), bool)]
            value = (sum(numeric) / len(numeric)) if aggregate == "mean" and numeric else (sum(numeric) if numeric else None)
        item.update({"value": value, "aggregate": aggregate, "count": len(members)})
        out.append(item)
    return out
