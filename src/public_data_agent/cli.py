from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from public_data_agent.benchmark import DEFAULT_QUESTIONS, load_questions, run_benchmark
from public_data_agent.enrich import enrich
from public_data_agent.fetch import DEFAULT_OSLO_DATASET, DEFAULT_OSLO_TABLE, fetch_observations
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


def _search(args: argparse.Namespace) -> int:
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        report = search_report(
            registry,
            args.query,
            limit=args.limit,
            decompose_query=args.decompose,
        )
    finally:
        registry.close()
    print(
        json.dumps(
            {
                "db": str(args.db),
                "query": args.query,
                "limit": args.limit,
                "decompose": args.decompose,
                **report.to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0
