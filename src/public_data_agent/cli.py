from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from public_data_agent.benchmark import DEFAULT_QUESTIONS, load_questions, run_benchmark
from public_data_agent.brreg_sync import sync_snapshot, sync_updates
from public_data_agent.enrich import enrich
from public_data_agent.fetch import DEFAULT_OSLO_DATASET, DEFAULT_OSLO_TABLE, fetch_observations
from public_data_agent.ask import DEMO_QUESTION, ask, ask_proof_payload
from public_data_agent.planner import build_plan
from public_data_agent.export import export_proof_payload, write_ask_charts, write_ask_csv
from public_data_agent.join import (
    DEFAULT_KLASS_DATASET,
    join_bydel_population,
    join_proof_payload,
)
from public_data_agent.ssb_pxweb import DEFAULT_SSB_TABLE
from public_data_agent.harvest import harvest, stderr_progress
from public_data_agent.http_util import SourceHttpError
from public_data_agent.registry import Registry
from public_data_agent.search import build_search_index
from public_data_agent.scan_table_urls import scan_printed_table_urls, scan_proof_payload
from public_data_agent.search import load_prompt_pack, run_search_pack, search_report
from public_data_agent.sources import ADDITIONAL_SOURCE_IDS, SOURCE_IDS, build_source

DEFAULT_DB = Path("data/registry.sqlite")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pda",
        description="Local dataset registry and natural-language search over it.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Harvest a source into the registry")
    ingest.add_argument(
        "--source", default="datanorge", choices=(*SOURCE_IDS, *ADDITIONAL_SOURCE_IDS)
    )
    ingest.add_argument("--db", type=Path, default=DEFAULT_DB)
    ingest.add_argument("--limit", type=int, default=None, help="Max datasets this run. Use this in CI/smoke.")
    ingest.add_argument("--offset", type=int, default=0)
    ingest.add_argument(
        "--refresh-all",
        action="store_true",
        help="Fetch every listed dataset even if SPARQL catalog-record modified is unchanged.",
    )
    ingest.add_argument("--fixtures", type=Path, default=None, help="JSON directory for --source fixture")
    ingest.add_argument("--notes", default=None)
    ingest.add_argument("--batch-size", type=int, default=None, help="Resource Service fetch/upsert batch")
    ingest.add_argument("--quiet", action="store_true", help="Do not print batch progress on stderr")

    check = sub.add_parser(
        "check",
        help="Ask whether a question can be answered at all, without calling a model",
    )
    check.add_argument("question")
    check.add_argument("--db", type=Path, default=DEFAULT_DB)
    check.add_argument("--limit", type=int, default=5)
    check.add_argument(
        "--llm",
        action="store_true",
        help="Use the model to read the question. Off by default; the deterministic reading needs no key.",
    )

    run_cmd = sub.add_parser("run", help="Run the full pipeline: intake, gate, route, answer")
    run_cmd.add_argument("question")
    run_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    run_cmd.add_argument("--model", default="gpt-4.1-mini")
    run_cmd.add_argument("--steps", type=int, default=10)
    run_cmd.add_argument("--limit", type=int, default=5)

    embed_cmd = sub.add_parser("embed", help="Build or refresh the embedding index used for ranking")
    embed_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    embed_cmd.add_argument("--model", default="text-embedding-3-small")
    embed_cmd.add_argument("--limit", type=int, default=None, help="Max rows this run")
    embed_cmd.add_argument("--dimensions", type=int, default=None,
                           help="Shorten the vector (text-embedding-3-* only), to trade "
                                "a little accuracy for a smaller index")
    embed_cmd.add_argument("--quiet", action="store_true")
    embed_cmd.add_argument("--export", type=Path, default=None,
                           help="Write the texts to embed as JSONL and stop (for a GPU elsewhere)")
    embed_cmd.add_argument("--import-vectors", dest="import_vectors", type=Path, default=None,
                           help="Load vectors embedded elsewhere, stored under --model")

    index_cmd = sub.add_parser(
        "index", help="Rebuild the lexical index that narrows what search scores"
    )
    index_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)

    shape_cmd = sub.add_parser(
        "shape",
        help="Read published table metadata into the resource index",
    )
    shape_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    shape_cmd.add_argument("--source", default=None, help="Only datasets from this source_id")
    shape_cmd.add_argument("--dataset", default=None, help="One dataset id")
    shape_cmd.add_argument("--limit", type=int, default=None)

    status = sub.add_parser("status", help="Show registry counts and recent harvest runs")
    status.add_argument("--db", type=Path, default=DEFAULT_DB)

    stats = sub.add_parser("stats", help="Write harvest-run and missing-field counts as JSON")
    stats.add_argument("--db", type=Path, default=DEFAULT_DB)
    stats.add_argument("--out", type=Path, default=None)

    search_cmd = sub.add_parser("search", help="Rank datasets in the local registry")
    search_cmd.add_argument(
        "query",
        nargs="?",
        help="Natural-language query, matched as tokens",
    )
    search_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    search_cmd.add_argument("--limit", type=int, default=10)
    search_cmd.add_argument(
        "--questions",
        type=Path,
        default=None,
        help="Ungolded question list. Emits a compact search_report per query.",
    )
    search_cmd.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON for --questions. Printed either way.",
    )
    search_cmd.add_argument(
        "--decompose",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Split multi-token queries into AND requirements. Default on.",
    )
    search_cmd.add_argument(
        "--user-file",
        type=Path,
        default=None,
        help="Local CSV or SQLite searched next to the public catalog this run.",
    )
    search_cmd.add_argument(
        "--user-db",
        type=Path,
        default=None,
        help="Local SQLite table searched next to the public catalog this run.",
    )

    enrich_cmd = sub.add_parser("enrich", help="Project stored harvest fields into enrichments")
    enrich_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    enrich_cmd.add_argument("--limit", type=int, default=None)
    enrich_cmd.add_argument("--offset", type=int, default=0)
    enrich_cmd.add_argument("--quiet", action="store_true", help="Do not print progress on stderr")

    bench = sub.add_parser("benchmark", help="Score pda search against a sourced gold set")
    bench.add_argument("--db", type=Path, default=DEFAULT_DB)
    bench.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    bench.add_argument("--out", type=Path, default=None)
    bench.add_argument(
        "--baseline",
        choices=["datanorge"],
        default=None,
        help="Optional Data.norge Search API baseline. Unstable, ~10 req/min.",
    )
    bench.add_argument("--quiet", action="store_true", help="Do not print progress on stderr")

    fetch_cmd = sub.add_parser("fetch", help="Retrieve observation rows from a dataset API")
    fetch_cmd.add_argument("--dataset", default=DEFAULT_OSLO_DATASET)
    fetch_cmd.add_argument("--table", default=DEFAULT_OSLO_TABLE)
    fetch_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    fetch_cmd.add_argument("--from-year", type=int, default=None)
    fetch_cmd.add_argument("--to-year", type=int, default=None)

    join_cmd = sub.add_parser("join", help="Join Klass bydel codes to an SSB befolkning table")
    join_cmd.add_argument("--dataset", default=DEFAULT_KLASS_DATASET, help="Klass dataset id")
    join_cmd.add_argument("--table", default=DEFAULT_SSB_TABLE, help="SSB PxWeb table id")
    join_cmd.add_argument("--year", type=int, default=2025)
    join_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    join_cmd.add_argument("--out", type=Path, default=None)

    methods_cmd = sub.add_parser(
        "methods",
        help="Clean stored observations, derive YoY rates, emit table and chart",
    )
    methods_cmd.add_argument("--dataset", default=DEFAULT_OSLO_DATASET)
    methods_cmd.add_argument("--table", default=DEFAULT_OSLO_TABLE)
    methods_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    methods_cmd.add_argument("--out", type=Path, default=Path("methods/proof"))
    methods_cmd.add_argument("--from-year", type=int, default=2020)
    methods_cmd.add_argument("--to-year", type=int, default=2026)
    methods_cmd.add_argument("--entity", default="Oslo (Kristiania og Aker) i alt")
    methods_cmd.add_argument("--measure", default="Folkemengden i alt (antall personer)")

    ask_cmd = sub.add_parser("ask", help="Search, join, and answer one natural-language question")
    ask_cmd.add_argument("question", nargs="?", default=DEMO_QUESTION)
    ask_cmd.add_argument("--dataset", default=DEFAULT_KLASS_DATASET)
    ask_cmd.add_argument("--table", default=DEFAULT_SSB_TABLE)
    ask_cmd.add_argument("--year", type=int, default=2025)
    ask_cmd.add_argument("--prior-year", type=int, default=2024)
    ask_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    ask_cmd.add_argument("--out", type=Path, default=None)
    ask_cmd.add_argument("--limit", type=int, default=10)

    plan_cmd = sub.add_parser(
        "plan",
        help="Plan a natural-language question without fetching or calculating",
    )
    plan_cmd.add_argument("question", nargs="?", default=DEMO_QUESTION)
    plan_cmd.add_argument("--dataset", default=DEFAULT_KLASS_DATASET)
    plan_cmd.add_argument("--table", default=DEFAULT_SSB_TABLE)
    plan_cmd.add_argument("--year", type=int, default=2025)
    plan_cmd.add_argument("--prior-year", type=int, default=2024)
    plan_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    plan_cmd.add_argument("--out", type=Path, default=None)
    plan_cmd.add_argument("--limit", type=int, default=10)

    dashboard_cmd = sub.add_parser("dashboard", help="Run the local planner test dashboard")
    dashboard_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    dashboard_cmd.add_argument("--host", default="127.0.0.1")
    dashboard_cmd.add_argument("--port", type=int, default=8765)

    agent_cmd = sub.add_parser("agent", help="Run the optional OpenAI tool-using agent")
    agent_cmd.add_argument("question")
    agent_cmd.add_argument("--model", default="gpt-4.1-mini")
    agent_cmd.add_argument("--steps", type=int, default=8)
    agent_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    agent_cmd.add_argument(
        "--gate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stop before any model call when no registered source can answer. Default on.",
    )

    scan_cmd = sub.add_parser(
        "scan-table-urls",
        help="Copy harvest-printed PxWeb/JSON-stat table URLs into printed_table_urls",
    )
    scan_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    scan_cmd.add_argument("--out", type=Path, default=None)
    scan_cmd.add_argument(
        "--probe",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="GET each new stored URL and record status plus content-type.",
    )
    scan_cmd.add_argument("--probe-limit", type=int, default=20)

    mirror_cmd = sub.add_parser(
        "mirror-brreg",
        help="Maintain a complete Brønnøysundregistrene entity mirror",
    )
    mirror_cmd.add_argument("kind", choices=["enheter", "underenheter"])
    mirror_cmd.add_argument("phase", choices=["snapshot", "updates"])
    mirror_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    mirror_cmd.add_argument(
        "--storage-dir", type=Path, default=Path("data/raw/brreg"),
        help="Directory for exact compressed publisher snapshots",
    )
    mirror_cmd.add_argument("--batch-size", type=int, default=None)
    mirror_cmd.add_argument(
        "--limit", type=int, default=None,
        help="Snapshot smoke-test rows or maximum update events; never checkpoints a sample",
    )
    mirror_cmd.add_argument("--force", action="store_true", help="Download even if ETag is unchanged")

    mcp_cmd = sub.add_parser("mcp", help="Run the stdio MCP server or call one tool")
    mcp_cmd.add_argument("--call", choices=["search", "ask", "fetch"], default=None)
    mcp_cmd.add_argument("--query", default=None)
    mcp_cmd.add_argument("--question", default=None)
    mcp_cmd.add_argument("--dataset", default=None)
    mcp_cmd.add_argument("--table", default=None)
    mcp_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    mcp_cmd.add_argument("--limit", type=int, default=10)
    mcp_cmd.add_argument("--year", type=int, default=None)
    mcp_cmd.add_argument("--prior-year", type=int, default=None)
    mcp_cmd.add_argument("--from-year", type=int, default=None)
    mcp_cmd.add_argument("--to-year", type=int, default=None)
    mcp_cmd.add_argument("--join", action="store_true")
    mcp_cmd.add_argument("--out", type=Path, default=None)

    args = parser.parse_args(argv)
    if args.command == "ingest":
        return _ingest(args)
    if args.command == "index":
        from public_data_agent.search import build_search_index

        registry = Registry(args.db)
        try:
            result = build_search_index(registry)
        finally:
            registry.close()
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.command == "shape":
        return _shape(args)
    if args.command == "status":
        return _status(args)
    if args.command == "stats":
        return _stats(args)
    if args.command == "embed":
        from public_data_agent.embeddings import export_texts, import_vectors

        if args.export is not None:
            registry = Registry(args.db)
            try:
                result = export_texts(registry, args.export)
            finally:
                registry.close()
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.import_vectors is not None:
            registry = Registry(args.db)
            try:
                result = import_vectors(registry, args.import_vectors, model=args.model)
            finally:
                registry.close()
            print(json.dumps(result, ensure_ascii=False))
            return 0
        return _embed(args)
    if args.command == "check":
        return _check(args)
    if args.command == "run":
        return _run_pipeline(args)
    if args.command == "search":
        return _search(args)
    if args.command == "enrich":
        return _enrich(args)
    if args.command == "benchmark":
        return _benchmark(args)
    if args.command == "fetch":
        return _fetch(args)
    if args.command == "join":
        return _join(args)
    if args.command == "methods":
        return _methods(args)
    if args.command == "ask":
        return _ask(args)
    if args.command == "plan":
        return _plan(args)
    if args.command == "dashboard":
        from public_data_agent.dashboard import serve

        if not Path(args.db).exists() and str(args.db) != ":memory:":
            print(f"no registry at {args.db}", file=sys.stderr)
            return 1
        serve(str(args.db), host=args.host, port=args.port)
        return 0
    if args.command == "agent":
        from public_data_agent.agent_loop import run_agent
        from public_data_agent.openai_agent import OpenAIAgentModel

        try:
            model = OpenAIAgentModel.from_env(model=args.model, dotenv=Path(".env"))
            result = run_agent(
                args.question,
                model,
                max_steps=args.steps,
                db=str(args.db),
                gate=args.gate,
            )
        except (RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({"tool_calls": result.tool_calls, "readiness": result.readiness, "final": result.final, "error": result.error, "messages": result.messages}, ensure_ascii=False, indent=2))
        return 1 if result.error else 0
    if args.command == "scan-table-urls":
        return _scan_table_urls(args)
    if args.command == "mirror-brreg":
        return _mirror_brreg(args)
    if args.command == "mcp":
        return _mcp(args)
    parser.error(f"unknown command {args.command}")
    return 2


def _ingest(args: argparse.Namespace) -> int:
    source = build_source(args.source, fixtures=args.fixtures)
    registry = Registry(args.db)
    try:
        counts = harvest(
            registry,
            source,
            limit=args.limit,
            offset=args.offset,
            refresh_all=args.refresh_all,
            notes=args.notes,
            batch_size=args.batch_size,
            progress=None if args.quiet else stderr_progress,
        )
        # An ingest leaves the lexical index behind, and a stale index makes
        # every search fall back to the full scan. Rebuilding costs a few
        # seconds against an ingest that took minutes.
        if counts.inserted or counts.updated:
            build_search_index(registry, progress=None if args.quiet else stderr_progress)
    finally:
        registry.close()
    print(
        json.dumps(
            {
                "db": str(args.db),
                "source": args.source,
                "listed": counts.listed,
                "inserted": counts.inserted,
                "updated": counts.updated,
                "unchanged": counts.unchanged,
                "failed": counts.failed,
                "errors": counts.errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if counts.failed else 0


def _shape(args: argparse.Namespace) -> int:
    """Read published metadata into resource_fields / resource_keys."""

    from public_data_agent.resource_index import index_dataset, load_classifications

    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        if args.dataset:
            ids = [args.dataset]
        else:
            sql = "SELECT id FROM datasets"
            params: list[Any] = []
            if args.source:
                sql += " WHERE source_id = ?"
                params.append(args.source)
            sql += " ORDER BY id"
            if args.limit is not None:
                sql += " LIMIT ?"
                params.append(args.limit)
            ids = [row[0] for row in registry.conn.execute(sql, params)]
        catalogues = load_classifications()
        indexed = 0
        skipped = 0
        failed: list[dict[str, str]] = []
        for dataset_id in ids:
            try:
                index_dataset(registry, dataset_id, catalogues=catalogues)
                indexed += 1
            except ValueError as exc:
                if str(exc).startswith("no metadata reader"):
                    skipped += 1
                else:
                    failed.append({"id": dataset_id, "error": str(exc)})
            except Exception as exc:
                failed.append({"id": dataset_id, "error": str(exc)})
        registry.conn.commit()
        print(
            json.dumps(
                {
                    "indexed": indexed,
                    "skipped": skipped,
                    "failed": failed,
                },
                ensure_ascii=False,
            )
        )
        return 1 if failed else 0
    finally:
        registry.close()


def _status(args: argparse.Namespace) -> int:
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        runs = registry.list_runs()
        print(
            json.dumps(
                {"db": str(args.db), "datasets": registry.dataset_count(), "harvest_runs": runs},
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        registry.close()
    return 0


def _stats(args: argparse.Namespace) -> int:
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        payload = {
            "db": str(args.db),
            "datasets": registry.dataset_count(),
            "harvest_runs": registry.list_runs(),
            "missing_fields": registry.missing_field_stats(),
        }
    finally:
        registry.close()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def _scan_table_urls(args: argparse.Namespace) -> int:
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        result = scan_printed_table_urls(
            registry,
            probe=args.probe,
            probe_limit=args.probe_limit,
        )
        command = f"pda scan-table-urls --db {args.db}"
        if args.out:
            command += f" --out {args.out}"
        if not args.probe:
            command += " --no-probe"
        payload = scan_proof_payload(result, command=command, db=str(args.db))
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 1 if result.counts.failed else 0
    finally:
        registry.close()


def _mirror_brreg(args: argparse.Namespace) -> int:
    registry = Registry(args.db)
    try:
        if args.phase == "snapshot":
            result = sync_snapshot(
                registry,
                args.kind,
                storage_dir=args.storage_dir,
                limit=args.limit,
                batch_size=args.batch_size or 1000,
                force=args.force,
            )
        else:
            if args.force:
                raise ValueError("--force applies only to the snapshot phase")
            result = sync_updates(
                registry,
                args.kind,
                batch_size=args.batch_size or 100,
                max_events=args.limit,
            )
    except (OSError, SourceHttpError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        registry.close()
    print(
        json.dumps(
            {
                "db": str(args.db),
                "kind": args.kind,
                "phase": args.phase,
                "status": result.status,
                "request_url": result.request_url,
                "listed": result.counts.listed,
                "inserted": result.counts.inserted,
                "updated": result.counts.updated,
                "unchanged": result.counts.unchanged,
                "failed": result.counts.failed,
                "tombstoned": result.tombstoned,
                "cursor": result.cursor,
                "etag": result.etag,
                "sha256": result.sha256,
                "storage_path": result.storage_path,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if result.counts.failed else 0


def _enrich(args: argparse.Namespace) -> int:
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        counts = enrich(
            registry,
            limit=args.limit,
            offset=args.offset,
            progress=None if args.quiet else stderr_progress,
        )
    finally:
        registry.close()
    print(
        json.dumps(
            {
                "db": str(args.db),
                "listed": counts.listed,
                "inserted": counts.inserted,
                "updated": counts.updated,
                "unchanged": counts.unchanged,
                "failed": counts.failed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if counts.failed else 0


def _benchmark(args: argparse.Namespace) -> int:
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    if not Path(args.questions).exists():
        print(f"no questions at {args.questions}", file=sys.stderr)
        return 1
    questions = load_questions(args.questions)
    registry = Registry(args.db)
    try:
        result = run_benchmark(
            registry,
            questions,
            baseline=args.baseline,
            progress=None if args.quiet else stderr_progress,
        )
    finally:
        registry.close()
    result["db"] = str(args.db)
    result["questions_path"] = str(args.questions)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def _fetch(args: argparse.Namespace) -> int:
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        result = fetch_observations(
            registry,
            args.dataset,
            table_id=args.table,
            from_year=args.from_year,
            to_year=args.to_year,
        )
        print(
            json.dumps(
                {
                    "db": str(args.db),
                    "dataset": result.dataset_id,
                    "table": result.table_id,
                    "request_url": result.request_url,
                    "http_status": result.http_status,
                    "listed": result.counts.listed,
                    "inserted": result.counts.inserted,
                    "updated": result.counts.updated,
                    "unchanged": result.counts.unchanged,
                    "failed": result.counts.failed,
                    "sample": result.sample,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if result.counts.failed else 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        registry.close()


def _join(args: argparse.Namespace) -> int:
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        result = join_bydel_population(
            registry,
            klass_dataset_id=args.dataset,
            ssb_table=args.table,
            year=args.year,
        )
        command = (
            f"pda join --dataset {args.dataset} --table {args.table} "
            f"--year {args.year} --db {args.db}"
        )
        if args.out:
            command += f" --out {args.out}"
        payload = join_proof_payload(
            result,
            command=command,
            db=str(args.db),
            klass_dataset=registry.get_dataset(args.dataset),
            datasets=registry.dataset_count(),
            enrichments=registry.enrichment_count(),
        )
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 1 if result.counts.failed else 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        registry.close()


def _methods(args: argparse.Namespace) -> int:
    from methods.cli import main as methods_main

    argv = [
        "--dataset",
        args.dataset,
        "--table",
        args.table,
        "--db",
        str(args.db),
        "--out",
        str(args.out),
        "--entity",
        args.entity,
        "--measure",
        args.measure,
    ]
    if args.from_year is not None:
        argv.extend(["--from-year", str(args.from_year)])
    if args.to_year is not None:
        argv.extend(["--to-year", str(args.to_year)])
    return methods_main(argv)


def _ask(args: argparse.Namespace) -> int:
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        result = ask(
            registry,
            args.question,
            klass_dataset_id=args.dataset,
            ssb_table=args.table,
            latest_year=args.year,
            prior_year=args.prior_year,
            search_limit=args.limit,
        )
        command = f'pda ask "{args.question}" --year {args.year} --prior-year {args.prior_year} --db {args.db}'
        if args.out:
            command += f" --out {args.out}"
        if args.out and args.out.suffix.lower() == ".csv":
            write_ask_csv(result, args.out)
            charts = write_ask_charts(result, args.out.with_name(args.out.stem + "_charts"))
            payload = export_proof_payload(
                result,
                command=command,
                csv_path=args.out,
                chart_paths=charts,
                db=str(args.db),
            )
            proof = args.out.with_name(args.out.stem + "_proof.json")
            proof.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            payload = ask_proof_payload(result, command=command, db=str(args.db))
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        print(text)
        failed = any(item.counts.failed for item in result.joins)
        # A planned non-demo fetch is part of the command's work too. Surface
        # connector failures to callers instead of reporting a false success.
        if result.execution.get("status") == "fetch_failed":
            failed = True
        return 1 if failed else 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        registry.close()


def _plan(args: argparse.Namespace) -> int:
    """Build and print a plan without executing any network operation."""
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        report = search_report(registry, args.question, limit=args.limit)
        plan = build_plan(
            args.question,
            report,
            klass_dataset_id=args.dataset,
            ssb_table=args.table,
            latest_year=args.year,
            prior_year=args.prior_year,
            registry=registry,
        )
        payload = {
            "question": args.question,
            "plan": plan.to_dict(),
            "discovery": report.to_dict(),
            "execution": {
                "status": "not_executed",
                "numbers_retrieved": False,
                "explanation": "Plan-only mode performs no fetch, join, calculation, or visualization.",
            },
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
    finally:
        registry.close()


def _mcp(args: argparse.Namespace) -> int:
    from public_data_agent.mcp_server import call_tool, run_stdio

    if args.call is None:
        run_stdio()
        return 0
    arguments: dict[str, Any] = {"db": str(args.db)}
    if args.call == "search":
        if not args.query:
            print("mcp --call search needs --query", file=sys.stderr)
            return 1
        arguments["query"] = args.query
        arguments["limit"] = args.limit
    elif args.call == "ask":
        arguments["question"] = args.question or DEMO_QUESTION
        arguments["limit"] = args.limit
        if args.dataset:
            arguments["dataset"] = args.dataset
        if args.table:
            arguments["table"] = args.table
        if args.year is not None:
            arguments["year"] = args.year
        if args.prior_year is not None:
            arguments["prior_year"] = args.prior_year
    else:
        if args.dataset:
            arguments["dataset"] = args.dataset
        if args.table:
            arguments["table"] = args.table
        if args.from_year is not None:
            arguments["from_year"] = args.from_year
        if args.to_year is not None:
            arguments["to_year"] = args.to_year
        if args.year is not None:
            arguments["year"] = args.year
        if args.join:
            arguments["join"] = True
    try:
        result = call_tool(args.call, arguments)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parts = [f"pda mcp --call {args.call}"]
    if args.call == "search":
        parts.append(f'--query "{args.query}"')
    elif args.call == "ask":
        parts.append(f'--question "{arguments["question"]}"')
    parts.append(f"--db {args.db}")
    if args.out:
        parts.append(f"--out {args.out}")
    payload = {
        "command": " ".join(parts),
        "tool": args.call,
        "arguments": arguments,
        **result,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def _run_pipeline(args: argparse.Namespace) -> int:
    """Run the graph. Providers are built lazily so the early routes need no key."""

    from public_data_agent.pipeline import ROUTE_CLARIFY, ROUTE_STOP, run_intake, route
    from public_data_agent.pipeline import run_pipeline

    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1

    intake_provider = plan_provider = agent_model = None
    try:
        from public_data_agent.openai_agent import OpenAIAgentModel, OpenAIIntakeProvider
        from public_data_agent.openai_planner import OpenAIPlanProvider

        intake_provider = OpenAIIntakeProvider.from_env(model=args.model, dotenv=Path(".env"))
        plan_provider = OpenAIPlanProvider.from_env(dotenv=Path(".env"))
        agent_model = OpenAIAgentModel.from_env(model=args.model, dotenv=Path(".env"))
    except (RuntimeError, ValueError):
        # No key: intake falls back to the deterministic reading, and the stop
        # and clarify routes still work. The answering routes will say what is
        # missing rather than pretending to run.
        pass

    registry = Registry(args.db)
    try:
        result = run_pipeline(
            registry,
            args.question,
            db=str(args.db),
            intake_provider=intake_provider,
            plan_provider=plan_provider,
            agent_model=agent_model,
            limit=args.limit,
            max_steps=args.steps,
        )
    finally:
        registry.close()
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if result.error:
        return 1
    return 0 if result.route not in {ROUTE_STOP, ROUTE_CLARIFY} else 2


def _embed(args: argparse.Namespace) -> int:
    """Embed dataset text for ranking. Incremental: unchanged rows are skipped."""

    from public_data_agent.embeddings import build_index
    from public_data_agent.openai_agent import OpenAIEmbeddingProvider

    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    try:
        provider = OpenAIEmbeddingProvider.from_env(
            model=args.model, dotenv=Path(".env"), dimensions=getattr(args, "dimensions", None)
        )
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        counts = build_index(
            registry,
            provider,
            model=args.model,
            limit=args.limit,
            progress=None if args.quiet else (lambda line: print(line, file=sys.stderr)),
        )
        counts["stored"] = registry.embedding_count()
    finally:
        registry.close()
    print(json.dumps({"db": str(args.db), "model": args.model, **counts}, ensure_ascii=False, indent=2))
    return 0


def _check(args: argparse.Namespace) -> int:
    """Run the readiness gate. Exit 0 when a question can be answered, 2 when not."""

    from public_data_agent.pipeline import run_intake, stop_message

    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    provider = None
    if args.llm:
        from public_data_agent.openai_agent import OpenAIIntakeProvider

        provider = OpenAIIntakeProvider.from_env(dotenv=Path(".env"))
    registry = Registry(args.db)
    try:
        outcome = run_intake(registry, args.question, provider=provider, limit=args.limit)
    finally:
        registry.close()
    payload = outcome.to_dict()
    if not outcome.readiness.ready:
        payload["stop_message"] = stop_message(outcome.readiness)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    # A distinct exit code so a caller can branch without parsing the payload.
    return 0 if outcome.proceed else 2


def _search(args: argparse.Namespace) -> int:
    if args.questions and args.query:
        print("search --questions does not take a query argument", file=sys.stderr)
        return 1
    if not args.questions and not args.query:
        print("search needs a query or --questions", file=sys.stderr)
        return 1
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    if args.questions and not Path(args.questions).exists():
        print(f"no questions at {args.questions}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        from public_data_agent.sources.user import (
            annotate_search_hits,
            ensure_user_hits,
            ingest_user_file,
        )

        if args.questions:
            pack = load_prompt_pack(args.questions)
            payload = run_search_pack(
                registry,
                pack,
                limit=args.limit,
                decompose_query=args.decompose,
            )
            payload["db"] = str(args.db)
            payload["questions_path"] = str(args.questions)
            payload["registry_rows"] = registry.dataset_count()
            payload["limit"] = args.limit
            payload["decompose"] = args.decompose
            payload["command"] = (
                f"pda search --questions {args.questions} --out {args.out or '-'} "
                f"--db {args.db} --limit {args.limit}"
            )
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(text + "\n", encoding="utf-8")
            print(text)
            return 0

        user_path = args.user_file or args.user_db
        if user_path is not None:
            ingest_user_file(registry, user_path)
        report = search_report(
            registry,
            args.query,
            limit=args.limit,
            decompose_query=args.decompose,
        )
        payload = {
            "db": str(args.db),
            "query": args.query,
            "limit": args.limit,
            "decompose": args.decompose,
            **report.to_dict(),
        }
        if user_path is not None:
            payload["user_file"] = str(user_path)
            payload["results"] = ensure_user_hits(
                payload.get("results") or [],
                registry,
                args.query,
                limit=args.limit,
            )
        annotate_search_hits(payload.get("results") or [], registry)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        registry.close()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
