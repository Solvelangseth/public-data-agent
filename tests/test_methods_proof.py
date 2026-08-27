"""Live proof: load stored Oslo observations. Artifact checks read the committed run."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from methods.clean import clean
from methods.derive import derive_yoy
from methods.types import YOY_GROWTH, YOY_GROWTH_FORMULA

OSLO_DATASET = "datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57"
OSLO_ENTITY = "Oslo (Kristiania og Aker) i alt"
OSLO_MEASURE = "Folkemengden i alt (antall personer)"
PROOF_DIR = Path(__file__).resolve().parents[1] / "methods" / "proof"
REGISTRY = Path("data/registry.sqlite")

# Sanity-check totals from the M7 live fetch. Applied only after a store/artifact read.
M7_SANITY = {"2020": 693494, "2026": 728714}


def _oslo_series_from_store(rows: list[dict]) -> tuple:
    cleaned = clean(rows)
    selected = tuple(
        row for row in cleaned if row.entity == OSLO_ENTITY and row.measure == OSLO_MEASURE
    )
    return derive_yoy(selected)


def test_live_oslo_store_matches_formula_and_lineage() -> None:
    if not REGISTRY.exists():
        pytest.skip("no local registry.sqlite; unit fixture tests cover the transforms")
    from public_data_agent.registry import Registry

    registry = Registry(REGISTRY)
    try:
        stored = registry.list_observations(OSLO_DATASET)
    finally:
        registry.close()
    if not stored:
        pytest.skip("registry has no Oslo observations")

    snapshot = [
        {
            "id": row["id"],
            "period": json.loads(row["dimensions_json"]).get("år"),
            "entity": json.loads(row["dimensions_json"]).get("geografisk område"),
            "measure": row["measure"],
            "value": json.loads(row["value_json"]),
        }
        for row in stored
    ]
    series_snapshot = [
        item
        for item in snapshot
        if item["entity"] == OSLO_ENTITY and item["measure"] == OSLO_MEASURE
    ]
    series_snapshot.sort(key=lambda item: item["period"] or "")
    derived = _oslo_series_from_store(stored)

    assert len(derived) == len(series_snapshot)
    assert derived[0].observation.period == series_snapshot[0]["period"]
    assert derived[-1].observation.period == series_snapshot[-1]["period"]
    for row, item in zip(derived, series_snapshot):
        assert row.observation.value == float(item["value"])
        assert row.observation.id == item["id"]
        assert row.yoy_growth.lineage.name == YOY_GROWTH
        assert row.yoy_growth.lineage.formula == YOY_GROWTH_FORMULA
        assert row.yoy_growth.lineage.source_observation_ids

    by_period = {item["period"]: item["value"] for item in series_snapshot}
    for year, expected in M7_SANITY.items():
        if year in by_period:
            assert by_period[year] == expected

    assert derived[0].yoy_growth.value is None
    for index in range(1, len(derived)):
        previous = series_snapshot[index - 1]["value"]
        current = series_snapshot[index]["value"]
        assert derived[index].yoy_growth.value == pytest.approx((current - previous) / previous)


def test_committed_oslo_proof_artifacts() -> None:
    csv_path = PROOF_DIR / "table.csv"
    md_path = PROOF_DIR / "table.md"
    lineage_path = PROOF_DIR / "lineage.json"
    chart_path = PROOF_DIR / "chart.png"
    assert csv_path.is_file()
    assert md_path.is_file()
    assert lineage_path.is_file()
    assert chart_path.is_file()
    assert chart_path.read_bytes().startswith(b"\x89PNG")

    with csv_path.open(encoding="utf-8", newline="") as handle:
        table = list(csv.DictReader(handle))
    assert table
    assert table[0]["period"]
    assert table[-1]["period"]
    assert table[0]["yoy_growth"] == ""
    values = [float(row["value"]) for row in table]
    for year, expected in M7_SANITY.items():
        match = next((row for row in table if row["period"] == year), None)
        if match is not None:
            assert float(match["value"]) == expected
    for index in range(1, len(table)):
        previous = values[index - 1]
        current = values[index]
        assert float(table[index]["yoy_growth"]) == pytest.approx((current - previous) / previous)

    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    column = lineage["derived_columns"][0]
    assert column["name"] == YOY_GROWTH
    assert column["formula"] == YOY_GROWTH_FORMULA
    assert len(column["rows"]) == len(table)
    for item in column["rows"]:
        assert item["lineage"]["name"] == YOY_GROWTH
        assert item["lineage"]["formula"] == YOY_GROWTH_FORMULA
        assert item["lineage"]["source_observation_ids"]
        assert item["lineage"]["source_periods"]
    md = md_path.read_text(encoding="utf-8")
    assert YOY_GROWTH_FORMULA in md
