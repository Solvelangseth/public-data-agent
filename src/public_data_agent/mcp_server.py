from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable

from public_data_agent.ask import DEMO_QUESTION, ask, ask_proof_payload
from public_data_agent.analysis import (
    describe_observations,
    run_analysis,
    run_record_analysis,
    stored_records,
)
from public_data_agent.artifacts import export_csv, export_json, plot_values
from public_data_agent.fetch import fetch_observations
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
from public_data_agent.fetch import is_retrievable
from public_data_agent.registry import Registry
from public_data_agent.resource_index import resource_shape
from public_data_agent.retrieval import find
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


def _embedding_provider() -> Any | None:
    """An embedding provider if one can be built, else None.

    Ranking without one measures recall@5 0.442 against the fetchable gold set
    where the full stack measures 0.860, so its absence is reported to the
    caller rather than passed off as a normal result.
    """

    from pathlib import Path as _Path

    try:
        from public_data_agent.openai_agent import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider.from_env(dotenv=_Path(".env"))
    except Exception:
        return None


def _query_rewriter() -> Any | None:
    """A query rewriter if one can be built, else None.

    Optional for the same reason the embedding provider is: the server has to
    work without an API key. Its absence costs the questions whose words the
    catalogue does not use -- held-out recall@5 0.811 without it against
    0.865-0.892 with it, and naturally phrased questions 0.812 against
    0.938-1.000.
    """

    from pathlib import Path as _Path

    try:
        from public_data_agent.openai_agent import OpenAIQueryRewriter

        return OpenAIQueryRewriter.from_env(dotenv=_Path(".env"))
    except Exception:
        return None


def _reranker() -> Any | None:
    """A reranker if one can be built, else None.

    Optional like the other two model-backed steps. Its absence costs the
    questions the stack retrieves but ranks too low: held-out recall@5
    0.865 without it against 0.892 with it, and MRR 0.733 against 0.759.
    """

    from pathlib import Path as _Path

    try:
        from public_data_agent.openai_agent import OpenAIReranker

        return OpenAIReranker.from_env(dotenv=_Path(".env"))
    except Exception:
        return None


def _entry_for(registry: Registry, dataset_id: str) -> dict[str, Any]:
    """A result entry built from stored metadata for a dataset the lexical
    search never returned.

    Semantic ranking finds resources whose title shares no word with the
    question -- 35 of 86 gold questions are that shape -- and those have no
    lexical hit to carry their metadata. Omitting them would drop exactly the
    results the ranking was added to find.
    """

    row = registry.get_dataset(dataset_id) or {}
    return {
        "id": dataset_id,
        "title": row.get("title"),
        "publisher": {"name": row.get("publisher_name")},
        "license": row.get("license"),
        "licenses": [],
        "access": {"access_path": row.get("access_path")},
        "original_link": row.get("source_native_uri"),
        "geography": None,
        "time": None,
        "keywords": [],
        "variables": [],
        "missing_fields": {},
        # Zero, not an invented score: this record was not matched by tokens, so
        # it has no token score, and the ordering already carries the ranking.
        "relevance": 0,
        "why": "ranked by meaning; this record shares no query token with the question",
    }


def tool_search(query: str, db: str = DEFAULT_DB, limit: int = 10) -> dict[str, Any]:
    """Rank datasets in the local registry. Passes through stored metadata only."""

    registry = _open_registry(db)
    try:
        # Rank deeper than the caller asked for: each lane needs its own top-N,
        # and a lane cannot be filled from a list already truncated to the other's
        # winners. Ranked order within each lane is unchanged.
        depth = max(limit * LANE_DEPTH, limit)
        report = search_report(registry, query, limit=depth)
        payload = {
            "tool": "search",
            "db": db,
            "values_from": "registry",
            "query": query,
            **report.to_dict(),
        }
        ranked = payload["results"]

        provider = _embedding_provider()
        payload["ranking"] = "lexical only" if provider is None else "meaning and tokens"
        if provider is None:
            payload["ranking_note"] = (
                "No embedding provider is configured, so this is token matching alone. "
                "Measured against the fetchable gold set that finds the right table for "
                "44% of questions against 86% with meaning-based ranking, and 23% "
                "against 81% for naturally phrased ones."
            )
        else:
            found = find(
                registry,
                query,
                provider=provider,
                limit=depth,
                depth=depth,
                rewriter=_query_rewriter(),
                reranker=_reranker(),
            )
            order = [*found.observations, *found.catalogue]
            position = {dataset_id: i for i, dataset_id in enumerate(order)}
            by_id = {hit["id"]: hit for hit in ranked}
            ranked = [
                by_id.get(dataset_id) or _entry_for(registry, dataset_id)
                for dataset_id in order
            ] + [hit for hit in ranked if hit["id"] not in position]
            payload["results"] = ranked
            payload["ranking_steps"] = found.steps
        payload["results"] = ranked[:limit]
        payload["returned"] = len(payload["results"])
        # Search results are catalog records, while these are the small set of
        # observation connectors already registered by the project.  Keeping
        # them explicit prevents the model from guessing a table from a
        # landing-page dataset (the failure mode seen in the dashboard).
        for hit in ranked:
            path = (hit.get("access") or {}).get("access_path")
            capability = classify_access_path(path)
            kind = capability["kind"]
            reason = capability["reason"]
            supported = can_fetch_access_path(path)
            # A verified probe outranks a guess from the URL, the same rule
            # `retrieval._capability` applies. Without this the lanes here
            # disagreed with the ranking that filled them: 769 datasets whose
            # fetch was demonstrated -- every Norges Bank series among them --
            # read as `unverified` because a register's stored access path is
            # its collection endpoint, and landed in the lane that says nothing
            # can be fetched.
            recorded = registry.get_capability(hit["id"]) or {}
            if recorded.get("capability") and recorded.get("verified_at"):
                kind = recorded["capability"]
                supported = True
                reason = (
                    f"verified {recorded['verified_at']}: a fetch returned "
                    f"{recorded.get('record_kind') or kind}"
                )
            hit["connector"] = {
                "fetch_supported": supported,
                "capability": kind,
                "reason": reason,
            }
            # "Cannot be retrieved" stopped being true for most of the
            # catalogue lane. 571 datasets read `lookup` -- Oslo's 42 bydeler,
            # 365 municipalities, 7,127 occupation titles -- and every one of
            # them holds entity records that `run_analysis` reads. Saying
            # nothing here told the caller its data was out of reach while it
            # sat in the record store.
            if not is_retrievable(kind):
                held = stored_records(registry, hit["id"])
                if held:
                    hit["connector"]["stored_records"] = held
                    kinds = ", ".join(
                        f"{n} {name} record" + ("s" if n != 1 else "")
                        for name, n in sorted(held.items())
                    )
                    hit["connector"]["readable"] = (
                        f"no fetch, but {kinds} already stored; read them with "
                        f"run_analysis, which returns them from the record store"
                    )
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
            hit for hit in ranked if is_retrievable(hit["connector"]["capability"])
        ][:limit]
        payload["catalogue_records"] = [
            hit for hit in ranked if not is_retrievable(hit["connector"]["capability"])
        ][:limit]
        payload["lanes_note"] = (
            "observation_sources can return numbers; catalogue_records cannot be fetched "
            "by any registered connector. Both are ranked by the same score. Answer "
            "numeric questions from observation_sources. A catalogue record carrying "
            "`stored_records` is not out of reach: its rows are already stored and "
            "run_analysis returns them, which is how a code list or a register answers."
        )
        payload["connector_candidates"] = candidates
        if not candidates:
            readable = [
                hit["id"]
                for hit in payload["catalogue_records"]
                if hit.get("connector", {}).get("stored_records")
            ]
            payload["connector_candidates_note"] = (
                "No registered observation connector declares coverage of this question. "
                "Catalogue hits above are not fetchable; report that numbers were not "
                "retrieved rather than guessing an API path."
                + (
                    " Some of them do hold rows already: "
                    f"{', '.join(readable[:5])} carry stored_records that run_analysis "
                    "returns, which answers a question about things rather than numbers."
                    if readable
                    else ""
                )
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
            provider=_embedding_provider(),
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


def _too_large_suggestion(access_path: str | None) -> str:
    """How to narrow a refused fetch, for the source that refused it.

    The same advice does not fit every source. An SSB table is wide in time as
    well as in dimensions, so a shorter year range helps. A Norges Bank dataflow
    is wide in series -- MONEY_MARKET holds 35,354 -- and its fetcher ignores
    from_year/to_year entirely, so suggesting them sends a caller round the same
    refusal again.
    """

    from public_data_agent.sources.norgesbank import is_norgesbank_url

    if is_norgesbank_url(access_path):
        return (
            "Re-run fetch with select={dimension: [codes]} using the dimension codes "
            "listed above; this dataflow is wide in series, not time, so from_year and "
            "to_year do not narrow it. inspect shows each dimension's codes and its "
            "position in the series key."
        )
    return (
        "Re-run fetch with select={dimension: [values]} narrowing the "
        "dimensions listed above, or use from_year/to_year to shorten time."
    )


def tool_fetch(
    dataset: str,
    table: str | None = None,
    db: str = DEFAULT_DB,
    from_year: int | None = None,
    to_year: int | None = None,
    year: int | None = None,
    kommune: str | None = None,
    fylke: str | None = None,
    bydel: str | None = None,
    measure: str | None = None,
    join: bool = False,
    join_key: str | None = None,
    series: str | None = None,
    select: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch rows from a registered connector, or join Klass to a table when join=true.

    `table` is a PxWeb table id. Registers (companies, road objects, protected
    areas, dairy-delivery years) address a subject with `select` and do not
    need it. With join=true, `dataset` is the Klass classification and `table`
    the SSB table. The join key is discovered by matching stored codes.
    """

    registry = _open_registry(db)
    try:
        if join:
            if not table:
                return {
                    "tool": "fetch",
                    "mode": "join",
                    "values_from": "registry",
                    "dataset": dataset,
                    "error": {
                        "code": "table_required",
                        "retryable": True,
                        "message": "join=true needs table set to an SSB PxWeb table id.",
                    },
                    "numbers_retrieved": False,
                }
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
        table_id = table or dataset_row.get("source_native_id") or ""
        if not can_fetch_access_path(access_path):
            return {
                "tool": "fetch",
                "mode": "observations",
                "values_from": "registry",
                "dataset": dataset,
                "table": table_id,
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
                table_id=table_id,
                from_year=from_year,
                to_year=to_year,
                select=select,
                kommune=kommune,
                fylke=fylke,
                bydel=bydel,
                measure=measure,
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
                "table": table_id,
                "error": {
                    "code": "selection_too_large",
                    "retryable": True,
                    "message": str(exc),
                    "cells_requested": exc.cells,
                    "cell_limit": exc.limit,
                    "dimensions": exc.dimensions,
                    "suggested_action": _too_large_suggestion(access_path),
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
            # What is stored of every kind, so a dataset holding a company does
            # not read as empty because it holds no statistical cells.
            "stored_records": stored_records(registry, dataset),
            # `observation_schema` describes what has already been fetched, so
            # it is empty for a resource nothing has pulled yet -- which is
            # every resource a caller is about to plan its first fetch against.
            # The index describes the resource itself, fetched or not.
            "resource_shape": resource_shape(registry, dataset),
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
    include_geometry: bool = False,
) -> dict[str, Any]:
    """Filter/select stored observations without fetching or deriving values."""
    registry = _open_registry(db)
    try:
        result = run_analysis(registry, dataset, filters=filters, measure=measure, series=series, columns=columns, group_by=group_by, aggregate=aggregate, sort_by=sort_by, descending=descending)
        payload = {"tool": "run_analysis", "values_from": "stored_observations", **result.to_dict()}
        # A dataset holding companies or buildings returned "completed" with no
        # rows, which a caller reads as "this dataset is empty". It said so for
        # 17,900 rows that are simply in the other store. It reads them now, and
        # names which store they came from, because a measurement and a thing
        # are not interchangeable even when both arrive as `values`.
        if not (payload.get("values") or payload.get("rows")):
            records = stored_records(registry, dataset)
            if records:
                kinds = ", ".join(f"{n} {kind}" for kind, n in sorted(records.items()))
                record_result = run_record_analysis(
                    registry,
                    dataset,
                    filters=filters,
                    columns=columns,
                    sort_by=sort_by,
                    descending=descending,
                    include_geometry=include_geometry,
                )
                payload = {
                    "tool": "run_analysis",
                    "values_from": "stored_records",
                    **record_result.to_dict(),
                }
                payload["stored_records"] = records
                payload["explanation"] = (
                    f"No observations matched. This dataset stores {kinds}, and these "
                    "rows are read from the record store: each is a thing with a "
                    "subject code and a label, not a measurement."
                )
                if measure or group_by or aggregate:
                    # Reporting rows while silently dropping the aggregation
                    # the caller asked for would answer a different question.
                    asked = ", ".join(
                        name
                        for name, given in (
                            ("measure", measure), ("group_by", group_by), ("aggregate", aggregate)
                        )
                        if given
                    )
                    payload.setdefault("warnings", [])
                    payload["warnings"] = list(payload["warnings"]) + [
                        f"{asked} was not applied: the record store holds no measured "
                        f"value to select or aggregate over."
                    ]
        return payload
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
        # The observation store is not the whole store. Reporting only its count
        # said "0" for a dataset holding a company record, which reads as "there
        # is nothing here" rather than "what is here is not an observation".
        records = stored_records(registry, dataset)
        urls = {item.get("request_url") for item in observations if item.get("request_url")}
        urls |= {
            r["request_url"]
            for r in registry.conn.execute(
                "SELECT DISTINCT request_url FROM records WHERE dataset_id = ?", (dataset,)
            )
            if r["request_url"]
        }
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
            "record_counts": records,
            "stored_total": len(observations) + sum(records.values()),
            "request_urls": sorted(urls),
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
