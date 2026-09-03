from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable

from public_data_agent.ask import DEMO_QUESTION, ask, ask_proof_payload
from public_data_agent.analysis import run_analysis
from public_data_agent.artifacts import export_csv, export_json, plot_values
from public_data_agent.fetch import DEFAULT_OSLO_DATASET, DEFAULT_OSLO_TABLE, fetch_observations
from public_data_agent.fetch import can_fetch_access_path
from public_data_agent.join import DEFAULT_KLASS_DATASET, join_bydel_population, join_proof_payload
from public_data_agent.registry import Registry
from public_data_agent.search import search_report
from public_data_agent.ssb_pxweb import DEFAULT_SSB_TABLE

DEFAULT_DB = "data/registry.sqlite"


def tool_search(query: str, db: str = DEFAULT_DB, limit: int = 10) -> dict[str, Any]:
    """Rank datasets in the local registry. Passes through stored metadata only."""

    registry = _open_registry(db)
    try:
        report = search_report(registry, query, limit=limit)
        return {
            "tool": "search",
            "db": db,
            "values_from": "registry",
            "query": query,
            **report.to_dict(),
        }
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
) -> dict[str, Any]:
    """Fetch observation rows, or run the existing Klass/11763 join when join=true."""

    registry = _open_registry(db)
    try:
        if join:
            result = join_bydel_population(
                registry,
                klass_dataset_id=dataset,
                ssb_table=table,
                year=year if year is not None else 2025,
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
            return payload
        dataset_row = registry.get_dataset(dataset) or {}
        result = fetch_observations(
            registry,
            dataset,
            table_id=table,
            from_year=from_year,
            to_year=to_year,
        )
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
                "source_native_uri": row.get("source_native_uri"),
                "temporal": row.get("temporal_json"),
            },
        }
    finally:
        registry.close()


def tool_run_analysis(
    dataset: str,
    db: str = DEFAULT_DB,
    filters: dict[str, str] | None = None,
    measure: str | None = None,
    columns: list[str] | None = None,
    group_by: list[str] | None = None,
    aggregate: str | None = None,
    sort_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    """Filter/select stored observations without fetching or deriving values."""
    registry = _open_registry(db)
    try:
        result = run_analysis(registry, dataset, filters=filters, measure=measure, columns=columns, group_by=group_by, aggregate=aggregate, sort_by=sort_by, descending=descending)
        return {"tool": "run_analysis", "values_from": "stored_observations", **result.to_dict()}
    finally:
        registry.close()


def tool_export_artifact(
    dataset: str,
    path: str,
    db: str = DEFAULT_DB,
    format: str = "csv",
    filters: dict[str, str] | None = None,
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
    filters: dict[str, str] | None = None,
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


TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "search": tool_search,
    "inspect": tool_inspect,
    "run_analysis": tool_run_analysis,
    "export_artifact": tool_export_artifact,
    "create_visualization": tool_create_visualization,
    "ask": tool_ask,
    "fetch": tool_fetch,
}


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    fn = TOOLS.get(name)
    if fn is None:
        raise ValueError(f"unknown tool {name}; known={sorted(TOOLS)}")
    params = inspect.signature(fn).parameters
    cleaned = {key: value for key, value in (arguments or {}).items() if key in params}
    return fn(**cleaned)


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
    server.add_tool(tool_ask, name="ask")
    server.add_tool(tool_fetch, name="fetch")
    return server


def run_stdio() -> None:
    build_server().run(transport="stdio")


def _open_registry(db: str) -> Registry:
    if db != ":memory:" and not Path(db).exists():
        raise ValueError(f"no registry at {db}")
    return Registry(db)
