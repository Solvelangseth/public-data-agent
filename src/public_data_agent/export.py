from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from methods.emit import emit
from methods.types import SeriesRow
from public_data_agent.ask import AskResult

CSV_COLUMNS = (
    "bydel_code",
    "name",
    "year",
    "personer",
    "yoy",
    "klass_publisher",
    "klass_license",
    "ssb_publisher",
    "ssb_license",
    "join_key",
    "lineage",
)


def write_ask_csv(result: AskResult, path: Path) -> Path:
    """Write one Excel-stable row per latest-year bydel. Numbers come from ask."""

    path.parent.mkdir(parents=True, exist_ok=True)
    growth = {row["bydel_code"]: row.get("yoy_growth") for row in result.growing}
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for row in result.largest:
            sources = row.get("sources") or []
            klass = sources[0] if len(sources) > 0 else {}
            ssb = sources[1] if len(sources) > 1 else {}
            yoy = growth.get(row["bydel_code"])
            writer.writerow(
                {
                    "bydel_code": row["bydel_code"],
                    "name": row.get("name") or "",
                    "year": row["year"],
                    "personer": "" if row.get("population") is None else row["population"],
                    "yoy": "" if yoy is None else yoy,
                    "klass_publisher": klass.get("publisher_name") or "",
                    "klass_license": klass.get("license") or "",
                    "ssb_publisher": ssb.get("publisher_name") or "",
                    "ssb_license": ssb.get("license") or "",
                    "join_key": row.get("join_key") or result.join_key,
                    "lineage": row.get("why_matched") or "",
                }
            )
    return path


def write_ask_charts(result: AskResult, out_dir: Path) -> dict[str, Path]:
    """Call methods.emit.emit. Do not draw a new chart."""

    rows = _chart_rows(result)
    if not rows:
        return {}
    return emit(rows, out_dir)


def _chart_rows(result: AskResult) -> tuple[SeriesRow, ...]:
    derived = result.derived
    if not derived:
        return ()
    if result.growing:
        code = result.growing[0]["bydel_code"]
        subset = tuple(row for row in derived if row.observation.entity == code)
        if subset:
            return subset
    return derived


def export_proof_payload(
    result: AskResult,
    *,
    command: str,
    csv_path: Path,
    chart_paths: dict[str, Path],
    db: str,
) -> dict[str, Any]:
    return {
        "command": command,
        "question": result.question,
        "csv": str(csv_path),
        "csv_columns": list(CSV_COLUMNS),
        "csv_rows": len(result.largest),
        "joined_rows": result.joined_rows,
        "plan": result.plan.to_dict() if result.plan else None,
        "execution": result.execution,
        "numbers_retrieved": bool(result.answer.get("numbers_retrieved")),
        "chart_helper": "methods.emit.emit",
        "charts": {key: str(path) for key, path in chart_paths.items()},
        "joins": [
            {
                "year": year,
                "left_http_status": item.left_http_status,
                "right_http_status": item.right_http_status,
                "left_request_url": item.left_request_url,
                "right_request_url": item.right_request_url,
            }
            for year, item in zip((result.prior_year, result.latest_year), result.joins)
        ],
        "db": db,
    }
