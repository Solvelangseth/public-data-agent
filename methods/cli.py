"""Thin proof/demo entrypoint: select stored observations, then transform."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from methods.clean import clean
from methods.derive import derive
from methods.emit import emit
from methods.types import (
    INDEX_FORMULA,
    RANK_CHANGE_FORMULA,
    RANK_FORMULA,
    YOY_GROWTH_FORMULA,
    SeriesRow,
)

# Selection only. Transforms never branch on these ids.
DEFAULT_DATASET = "datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57"
DEFAULT_TABLE = "Befolkning/Folkemengde/OK-BEF008.px"
DEFAULT_ENTITY = "Oslo (Kristiania og Aker) i alt"
DEFAULT_MEASURE = "Folkemengden i alt (antall personer)"
DEFAULT_DB = Path("data/registry.sqlite")
DEFAULT_OUT = Path("methods/proof")
SSB_11763 = "ssb:11763"
SSB_06683 = "ssb:06683"
SSB_06831 = "ssb:06831"
STORE_ONLY_DATASETS = frozenset({SSB_11763, SSB_06683, SSB_06831})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pda methods",
        description="Clean stored observations, derive YoY rates and an index, emit table and chart.",
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--table", default=DEFAULT_TABLE, help="Used only if observations are missing")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--from-year", type=int, default=2020)
    parser.add_argument("--to-year", type=int, default=2026)
    parser.add_argument(
        "--entity",
        default=DEFAULT_ENTITY,
        help="Select which stored series to load. Empty string keeps every entity.",
    )
    parser.add_argument(
        "--measure",
        default=DEFAULT_MEASURE,
        help="Select which stored measure to load. Empty string keeps every measure.",
    )
    parser.add_argument(
        "--base-period",
        default=None,
        help="Index base period. Default: first period in each (entity, measure) series.",
    )
    args = parser.parse_args(argv)
    try:
        rows = run(
            dataset_id=args.dataset,
            db=args.db,
            out=args.out,
            table_id=args.table,
            from_year=args.from_year,
            to_year=args.to_year,
            entity=args.entity or None,
            measure=args.measure or None,
            base_period=args.base_period,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(_summary(rows, args), ensure_ascii=False, indent=2))
    return 0


def run(
    *,
    dataset_id: str,
    db: Path,
    out: Path,
    table_id: str,
    from_year: int | None,
    to_year: int | None,
    entity: str | None,
    measure: str | None,
    base_period: str | None = None,
) -> tuple[SeriesRow, ...]:
    raw = load_observations(dataset_id, db)
    if not raw:
        if dataset_id in STORE_ONLY_DATASETS:
            raise ValueError(
                f"no stored observations for {dataset_id}; "
                "refusing to call pda fetch (no POST to SSB/PxWeb)"
            )
        _call_existing_fetch(dataset_id, db, table_id, from_year, to_year)
        raw = load_observations(dataset_id, db)
    if not raw:
        raise ValueError(f"no stored observations for {dataset_id} after pda fetch")
    cleaned = clean(raw)
    selected = _select(cleaned, entity=entity, measure=measure)
    if not selected:
        available = sorted({(row.entity, row.measure) for row in cleaned})
        raise ValueError(f"no observations matched entity/measure; available={available}")
    derived = derive(selected, base_period=base_period)
    emit(derived, out)
    return derived


def load_observations(dataset_id: str, db: Path) -> list[dict[str, Any]]:
    """Read stored Observation rows. Does not import any fetch/connector module."""

    if not Path(db).exists() and str(db) != ":memory:":
        return []
    from public_data_agent.registry import Registry

    registry = Registry(db)
    try:
        return registry.list_observations(dataset_id)
    finally:
        registry.close()


def _call_existing_fetch(
    dataset_id: str,
    db: Path,
    table_id: str,
    from_year: int | None,
    to_year: int | None,
) -> None:
    command = [
        sys.executable,
        "-m",
        "public_data_agent",
        "fetch",
        "--dataset",
        dataset_id,
        "--table",
        table_id,
        "--db",
        str(db),
    ]
    if from_year is not None:
        command.extend(["--from-year", str(from_year)])
    if to_year is not None:
        command.extend(["--to-year", str(to_year)])
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise ValueError(
            "stored observations were missing and `pda fetch` failed. "
            "Ingest the dataset into the registry, then rerun."
        )


def _select(rows, *, entity: str | None, measure: str | None):
    """Filter to entity/measure. Oslo CLI defaults fall back to every series.

    `pda methods` always forwards the Oslo city-total defaults. Those names
    are not in ssb:11763, ssb:06683, or ssb:06831, so an unmatched default
    keeps every stored series instead of calling fetch or emitting an empty table.
    """

    selected = rows
    if entity:
        matched = tuple(row for row in selected if row.entity == entity)
        if matched or entity != DEFAULT_ENTITY:
            selected = matched
    if measure:
        matched = tuple(row for row in selected if row.measure == measure)
        if matched or measure != DEFAULT_MEASURE:
            selected = matched
    return selected


def _summary(rows: tuple[SeriesRow, ...], args: argparse.Namespace) -> dict[str, Any]:
    return {
        "db": str(args.db),
        "dataset": args.dataset,
        "out": str(args.out),
        "rows": len(rows),
        "formula": {
            "yoy_growth": YOY_GROWTH_FORMULA,
            "index": INDEX_FORMULA,
            "rank": RANK_FORMULA,
            "rank_change": RANK_CHANGE_FORMULA,
        },
        "series": [
            {
                "entity": row.observation.entity,
                "period": row.observation.period,
                "measure": row.observation.measure,
                "value": row.observation.value,
                "yoy_growth": row.yoy_growth.value,
                "index": row.index.value,
                "rank": row.rank.value,
                "rank_change": row.rank_change.value,
                "observation_id": row.observation.id,
            }
            for row in rows
        ],
    }
