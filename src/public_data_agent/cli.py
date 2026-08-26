from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from public_data_agent.harvest import harvest, stderr_progress
from public_data_agent.registry import Registry
from public_data_agent.search import search
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

    args = parser.parse_args(argv)
    if args.command == "ingest":
        return _ingest(args)
    if args.command == "status":
        return _status(args)
    if args.command == "stats":
        return _stats(args)
    if args.command == "search":
        return _search(args)
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


def _search(args: argparse.Namespace) -> int:
    if not Path(args.db).exists() and str(args.db) != ":memory:":
        print(f"no registry at {args.db}", file=sys.stderr)
        return 1
    registry = Registry(args.db)
    try:
        hits = search(registry, args.query, limit=args.limit)
    finally:
        registry.close()
    print(
        json.dumps(
            {
                "db": str(args.db),
                "query": args.query,
                "limit": args.limit,
                "returned": len(hits),
                "results": [hit.to_dict() for hit in hits],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0
