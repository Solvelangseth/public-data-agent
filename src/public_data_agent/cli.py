from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from public_data_agent.benchmark import DEFAULT_QUESTIONS, load_questions, run_benchmark
from public_data_agent.enrich import enrich
from public_data_agent.fetch import DEFAULT_OSLO_DATASET, DEFAULT_OSLO_TABLE, fetch_observations
from public_data_agent.ask import DEMO_QUESTION, ask, ask_proof_payload
from public_data_agent.export import export_proof_payload, write_ask_charts, write_ask_csv
from public_data_agent.join import (
    DEFAULT_KLASS_DATASET,
    join_bydel_population,
    join_proof_payload,
)
from public_data_agent.ssb_pxweb import DEFAULT_SSB_TABLE
from public_data_agent.harvest import harvest, stderr_progress
from public_data_agent.registry import Registry
from public_data_agent.search import search_report
from public_data_agent.sources import SOURCE_IDS, build_source

DEFAULT_DB = Path("data/registry.sqlite")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pda",
        description="Local dataset registry and natural-language search over it.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Harvest a source into the registry")
    ingest.add_argument("--source", default="datanorge", choices=SOURCE_IDS)
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

    status = sub.add_parser("status", help="Show registry counts and recent harvest runs")
    status.add_argument("--db", type=Path, default=DEFAULT_DB)

    stats = sub.add_parser("stats", help="Write harvest-run and missing-field counts as JSON")
    stats.add_argument("--db", type=Path, default=DEFAULT_DB)
    stats.add_argument("--out", type=Path, default=None)

    search_cmd = sub.add_parser("search", help="Rank datasets in the local registry")
    search_cmd.add_argument("query", help="Natural-language query, matched as tokens")
    search_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
    search_cmd.add_argument("--limit", type=int, default=10)
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
        help="Local CSV searched next to the public catalog this run.",
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
    if args.command == "status":
        return _status(args)
    if args.command == "stats":
        return _stats(args)
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
        return 1 if failed else 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
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


def _search(args: argparse.Namespace) -> int:
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        from public_data_agent.sources.user import (
            annotate_search_hits,
            ensure_user_hits,
            ingest_user_file,
        )

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
