from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable

from public_data_agent.ask import DEMO_QUESTION, ask, ask_proof_payload
from public_data_agent.analysis import describe_observations, run_analysis
from public_data_agent.artifacts import export_csv, export_json, plot_values
from public_data_agent.fetch import DEFAULT_OSLO_DATASET, DEFAULT_OSLO_TABLE, fetch_observations
from public_data_agent.fetch import (
    SelectionTooLarge,
    can_fetch_access_path,
    classify_access_path,
)
from public_data_agent.join import (
    DEFAULT_KLASS_DATASET,
    JOIN_KEY,
    JOIN_SERIES,
    join_classification_to_table,
    join_proof_payload,
)
from public_data_agent.registry import Registry
from public_data_agent.search import search_report, tokenize
from public_data_agent.ssb_pxweb import DEFAULT_SSB_TABLE

DEFAULT_DB = "data/registry.sqlite"
# How much deeper than `limit` to rank so each lane can fill its own top-N.
LANE_DEPTH = 6

# Hand-registered observation connectors and the question vocabulary each one
# actually serves.  These tokens are declared, never inferred from a title, and
# they exist so an unrelated question gets no candidate rather than a wrong one.
REGISTERED_CONNECTORS: tuple[dict[str, Any], ...] = (
    {
        "dataset_id": "ssb:11763",
        "table_id": DEFAULT_SSB_TABLE,
        "match_tokens": frozenset({
            "befolkning", "folkemengde", "folketall", "innbygger", "innbyggere",
            "bydel", "bydeler", "bydelene", "oslo", "alder", "vekst", "befolkningsvekst",
        }),
        "covers": "population by Oslo bydel and age, per year, from SSB PxWeb table 11763",
    },
    {
        "dataset_id": DEFAULT_KLASS_DATASET,
        "table_id": "1168",
        "match_tokens": frozenset({
            "bydel", "bydeler", "bydelene", "oslo", "bydelsinndeling",
            "klassifikasjon", "kode", "koder",
        }),
        "covers": "Oslo bydel code-to-name mapping from SSB Klass version 1168",
    },
)


def tool_search(query: str, db: str = DEFAULT_DB, limit: int = 10) -> dict[str, Any]:
    """Rank datasets in the local registry. Passes through stored metadata only."""

    registry = _open_registry(db)
    try:
        # Rank deeper than the caller asked for: each lane needs its own top-N,
        # and a lane cannot be filled from a list already truncated to the other's
        # winners. Ranked order within each lane is unchanged.
        report = search_report(registry, query, limit=max(limit * LANE_DEPTH, limit))
        payload = {
            "tool": "search",
            "db": db,
            "values_from": "registry",
            "query": query,
            **report.to_dict(),
        }
        ranked = payload["results"]
        payload["results"] = ranked[:limit]
        payload["returned"] = len(payload["results"])
        # Search results are catalog records, while these are the small set of
        # observation connectors already registered by the project.  Keeping
        # them explicit prevents the model from guessing a table from a
        # landing-page dataset (the failure mode seen in the dashboard).
        for hit in ranked:
            path = (hit.get("access") or {}).get("access_path")
            capability = classify_access_path(path)
            hit["connector"] = {
                "fetch_supported": can_fetch_access_path(path),
                "capability": capability["kind"],
                "reason": capability["reason"],
            }
        # A candidate is only a candidate for a question it actually covers.
        # Offering the Oslo population connectors for "fiskeoppdrett" invites
        # the model to answer from the wrong source, so each registered
        # connector declares the tokens it serves and is matched against them.
        query_tokens = set(tokenize(query))
        candidates = []
        for candidate in REGISTERED_CONNECTORS:
            if not query_tokens & candidate["match_tokens"]:
                continue
            row = registry.get_dataset(candidate["dataset_id"])
            if row and can_fetch_access_path(row.get("access_path")):
                candidates.append({
                    "dataset_id": candidate["dataset_id"],
                    "table_id": candidate["table_id"],
                    "title": row.get("title"),
                    "publisher_name": row.get("publisher_name"),
                    "license": row.get("license"),
                    "access_path": row.get("access_path"),
                    "fetch_supported": True,
                    "matched_query_tokens": sorted(query_tokens & candidate["match_tokens"]),
                    "covers": candidate["covers"],
                    "reason": "registered connector candidate; inspect before fetching",
                })
        # Two different questions share one ranked list: "what can answer me with
        # numbers" and "what record describes this". Letting them compete for the
        # same slots means every ranking change robs one to pay the other. Ranked
        # order is unchanged; the lanes just stop crowding each other out.
        payload["observation_sources"] = [
            hit for hit in ranked if hit["connector"]["capability"] == "observations"
        ][:limit]
        payload["catalogue_records"] = [
            hit for hit in ranked if hit["connector"]["capability"] != "observations"
        ][:limit]
        payload["lanes_note"] = (
            "observation_sources can return numbers; catalogue_records describe data that "
            "no registered connector can retrieve. Both are ranked by the same score. "
            "Answer numeric questions from observation_sources."
        )
        payload["connector_candidates"] = candidates
        if not candidates:
            payload["connector_candidates_note"] = (
                "No registered observation connector declares coverage of this question. "
                "Catalogue hits above may describe relevant data but are not fetchable; "
                "report that numbers were not retrieved rather than guessing an API path."
            )
        return payload
    finally:
        registry.close()


def tool_ask(
    question: str = DEMO_QUESTION,
    db: str = DEFAULT_DB,
    dataset: str = DEFAULT_KLASS_DATASET,
    table: str = DEFAULT_SSB_TABLE,
    year: int = 2025,
    prior_year: int = 2024,
    limit: int = 10,
) -> dict[str, Any]:
    """Search, join Klass to SSB 11763, and rank size and YoY from stored/fetched cells."""

    registry = _open_registry(db)
    try:
        result = ask(
            registry,
            question,
            klass_dataset_id=dataset,
            ssb_table=table,
            latest_year=year,
            prior_year=prior_year,
            search_limit=limit,
        )
        payload = ask_proof_payload(
            result,
            command=f'pda ask "{question}" --year {year} --prior-year {prior_year} --db {db}',
            db=db,
        )
        payload["tool"] = "ask"
        payload["values_from"] = "registry+ssb_api"
        return payload
    finally:
        registry.close()


def tool_fetch(
    dataset: str = DEFAULT_OSLO_DATASET,
    table: str = DEFAULT_OSLO_TABLE,
    db: str = DEFAULT_DB,
    from_year: int | None = None,
    to_year: int | None = None,
    year: int | None = None,
    join: bool = False,
    join_key: str | None = None,
    series: str | None = None,
    select: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch observation rows, or join a Klass classification to a table when join=true.

    With join=true, `dataset` is the Klass classification and `table` the SSB
    table. The join key is discovered by matching the classification's codes
    against the table's stored dimension values; no overlap means no join.
    """

    registry = _open_registry(db)
    try:
        if join:
            result = join_classification_to_table(
                registry,
                klass_dataset_id=dataset,
                ssb_table=table,
                year=year if year is not None else 2025,
                join_key=join_key or JOIN_KEY,
                series=series or JOIN_SERIES,
            )
            payload = join_proof_payload(
                result,
                command=f"pda join --dataset {dataset} --table {table} --year {year or 2025} --db {db}",
                db=db,
                klass_dataset=registry.get_dataset(dataset),
                datasets=registry.dataset_count(),
                enrichments=registry.enrichment_count(),
            )
            payload["tool"] = "fetch"
            payload["values_from"] = "registry+ssb_api"
            payload["mode"] = "join"
            # `sample` is the first few joined rows in join-key order, not a
            # ranking.  Reading it as "the top 5" produced a confident but
            # wrongly ordered answer, so the truncation is now stated.
            payload["row_count"] = len(payload.get("rows") or [])
            payload["sample_is_truncated"] = len(payload.get("sample") or []) < payload["row_count"]
            payload["sample_note"] = (
                f"`sample` shows {len(payload.get('sample') or [])} of {payload['row_count']} joined rows "
                "in bydel_code order. It is NOT sorted by value and is NOT a ranking. "
                "Use the full `rows` list, or run_analysis with sort_by, before stating any ranking."
            )
            return payload
        dataset_row = registry.get_dataset(dataset) or {}
        access_path = dataset_row.get("access_path")
        if not can_fetch_access_path(access_path):
            return {
                "tool": "fetch",
                "mode": "observations",
                "values_from": "registry",
                "dataset": dataset,
                "table": table,
                "error": {
                    "code": "unsupported_access_path",
                    "retryable": False,
                    "message": "No registered connector can fetch this dataset access_path; numbers were not retrieved.",
                    "access_path": access_path,
                    "suggested_action": "Use connector_candidates from search or inspect a different registered dataset.",
                },
                "numbers_retrieved": False,
            }
        try:
            result = fetch_observations(
                registry,
                dataset,
                table_id=table,
                from_year=from_year,
                to_year=to_year,
                select=select,
            )
        except SelectionTooLarge as exc:
            # Asking for every value of every dimension is refused by the source
            # as an opaque 403. Report the sizes so the caller can narrow to the
            # slice it actually needs instead of retrying the same request.
            return {
                "tool": "fetch",
                "mode": "observations",
                "values_from": "registry",
                "dataset": dataset,
                "table": table,
                "error": {
                    "code": "selection_too_large",
                    "retryable": True,
                    "message": str(exc),
                    "cells_requested": exc.cells,
                    "cell_limit": exc.limit,
                    "dimensions": exc.dimensions,
                    "suggested_action": (
                        "Re-run fetch with select={dimension: [values]} narrowing the "
                        "dimensions listed above, or use from_year/to_year to shorten time."
                    ),
                },
                "numbers_retrieved": False,
            }
        return {
            "tool": "fetch",
            "mode": "observations",
            "values_from": "registry+api",
            "db": db,
            "dataset": result.dataset_id,
            "table": result.table_id,
            "publisher_name": dataset_row.get("publisher_name"),
            "license": dataset_row.get("license"),
            "access_path": dataset_row.get("access_path"),
            "original_source": dataset_row.get("source_native_uri"),
            "why_picked": "caller passed this dataset_id; cells come from the stored access_path",
            "request_url": result.request_url,
            "http_status": result.http_status,
            "listed": result.counts.listed,
            "inserted": result.counts.inserted,
            "updated": result.counts.updated,
            "unchanged": result.counts.unchanged,
            "failed": result.counts.failed,
            "sample": result.sample,
        }
    finally:
        registry.close()


def tool_inspect(dataset: str, db: str = DEFAULT_DB) -> dict[str, Any]:
    """Return stored metadata and connector capability for one dataset."""
    registry = _open_registry(db)
    try:
        row = registry.get_dataset(dataset)
        if row is None:
            raise ValueError(f"dataset not found in registry: {dataset}")
        return {
            "tool": "inspect",
            "dataset": dataset,
            "values_from": "registry",
            "metadata": {
                "title": row.get("title"),
                "description": row.get("description"),
                "publisher_name": row.get("publisher_name"),
                "license": row.get("license"),
                "access_path": row.get("access_path"),
                "fetch_supported": can_fetch_access_path(row.get("access_path")),
                "capability": classify_access_path(row.get("access_path")),
                "source_native_uri": row.get("source_native_uri"),
                "temporal": row.get("temporal_json"),
            },
            # The stored dimension names are source-defined and cannot be
            # guessed from the title.  Returning them is what lets a caller
            # build a filter that matches rows instead of silently matching none.
            "observation_schema": describe_observations(registry, dataset),
        }
    finally:
        registry.close()


def tool_run_analysis(
    dataset: str,
    db: str = DEFAULT_DB,
    filters: dict[str, Any] | None = None,
    measure: str | None = None,
    series: str | None = None,
    columns: list[str] | None = None,
    group_by: list[str] | None = None,
    aggregate: str | None = None,
    sort_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    """Filter/select stored observations without fetching or deriving values."""
    registry = _open_registry(db)
    try:
        result = run_analysis(registry, dataset, filters=filters, measure=measure, series=series, columns=columns, group_by=group_by, aggregate=aggregate, sort_by=sort_by, descending=descending)
        return {"tool": "run_analysis", "values_from": "stored_observations", **result.to_dict()}
    finally:
        registry.close()


def tool_export_artifact(
    dataset: str,
    path: str,
    db: str = DEFAULT_DB,
    format: str = "csv",
    filters: dict[str, Any] | None = None,
    measure: str | None = None,
    group_by: list[str] | None = None,
    aggregate: str | None = None,
) -> dict[str, Any]:
    """Export stored-observation analysis results to a local CSV or JSON file."""
    registry = _open_registry(db)
    try:
        result = run_analysis(registry, dataset, filters=filters, measure=measure, group_by=group_by, aggregate=aggregate)
        artifact = export_json(result, Path(path)) if format == "json" else export_csv(result, Path(path)) if format == "csv" else None
        if artifact is None:
            raise ValueError("format must be csv or json")
        return {"tool": "export_artifact", "values_from": "stored_observations", "result": result.to_dict(), "artifact": artifact.to_dict()}
    finally:
        registry.close()


def tool_create_visualization(
    dataset: str,
    path: str,
    db: str = DEFAULT_DB,
    label: str = "label",
    filters: dict[str, Any] | None = None,
    measure: str | None = None,
    group_by: list[str] | None = None,
    aggregate: str | None = None,
) -> dict[str, Any]:
    """Create a local PNG chart from numeric stored-observation results."""
    registry = _open_registry(db)
    try:
        result = run_analysis(registry, dataset, filters=filters, measure=measure, group_by=group_by, aggregate=aggregate)
        artifact = plot_values(result, Path(path), label=label)
        return {"tool": "create_visualization", "values_from": "stored_observations", "artifact": artifact.to_dict(), "result": result.to_dict()}
    finally:
        registry.close()


def tool_get_provenance(dataset: str, db: str = DEFAULT_DB) -> dict[str, Any]:
    """Return stored dataset metadata and observation lineage without fetching."""
    registry = _open_registry(db)
    try:
        row = registry.get_dataset(dataset)
        if row is None:
            raise ValueError(f"dataset not found in registry: {dataset}")
        observations = registry.list_observations(dataset)
        return {
            "tool": "get_provenance",
            "values_from": "registry",
            "dataset": dataset,
            "metadata": {
                "title": row.get("title"),
                "publisher_name": row.get("publisher_name"),
                "license": row.get("license"),
                "access_path": row.get("access_path"),
            },
            "observation_count": len(observations),
            "request_urls": sorted({item.get("request_url") for item in observations if item.get("request_url")}),
        }
    finally:
        registry.close()


TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "search": tool_search,
    "inspect": tool_inspect,
    "run_analysis": tool_run_analysis,
    "export_artifact": tool_export_artifact,
    "create_visualization": tool_create_visualization,
    "get_provenance": tool_get_provenance,
    "ask": tool_ask,
    "fetch": tool_fetch,
}


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    fn = TOOLS.get(name)
    if fn is None:
        raise ValueError(f"unknown tool {name}; known={sorted(TOOLS)}")
    params = inspect.signature(fn).parameters
    supplied = dict(arguments or {})
    # Dropping unknown arguments silently turns "population in 2025" into
    # "population in every stored year" and still reports success.  An
    # unrecognised argument is a failed request, not an empty one.
    unknown = sorted(key for key in supplied if key not in params)
    if unknown:
        raise ValueError(
            f"unknown argument(s) for tool {name}: {', '.join(unknown)}; "
            f"accepted={sorted(params)}. Dimension filters belong inside `filters`."
        )
    return fn(**supplied)


def build_server():
    from mcp.server.mcpserver import MCPServer

    server = MCPServer(
        name="public-data-agent",
        instructions=(
            "Search, inspect, ask, and fetch Norwegian open data from the local registry. "
            "Pass through stored or fetched cells. Do not invent observation values."
        ),
    )
    server.add_tool(tool_search, name="search")
    server.add_tool(tool_inspect, name="inspect")
    server.add_tool(tool_run_analysis, name="run_analysis")
    server.add_tool(tool_export_artifact, name="export_artifact")
    server.add_tool(tool_create_visualization, name="create_visualization")
    server.add_tool(tool_get_provenance, name="get_provenance")
    server.add_tool(tool_ask, name="ask")
    server.add_tool(tool_fetch, name="fetch")
    return server


def run_stdio() -> None:
    build_server().run(transport="stdio")


def _open_registry(db: str) -> Registry:
    if db != ":memory:" and not Path(db).exists():
        raise ValueError(f"no registry at {db}")
    return Registry(db)
