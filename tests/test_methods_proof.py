"""Live proof: load stored Oslo observations. Artifact checks read the committed run."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from methods.clean import clean
from methods.derive import derive
from methods.emit import index_line_series, yoy_bar_points
from methods.types import INDEX, INDEX_FORMULA, YOY_GROWTH, YOY_GROWTH_FORMULA

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
    return derive(selected)


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
        assert row.index.lineage.name == INDEX
        assert row.index.lineage.formula == INDEX_FORMULA
        assert row.index.lineage.base_period == series_snapshot[0]["period"]
        assert row.index.lineage.base_observation_id == series_snapshot[0]["id"]
        assert row.index.lineage.source_observation_ids

    by_period = {item["period"]: item["value"] for item in series_snapshot}
    for year, expected in M7_SANITY.items():
        if year in by_period:
            assert by_period[year] == expected

    assert derived[0].yoy_growth.value is None
    stored_base = series_snapshot[0]["value"]
    assert derived[0].index.value == 100.0
    if derived[0].observation.period == "2020":
        assert derived[0].index.value == 100.0
    for index in range(1, len(derived)):
        previous = series_snapshot[index - 1]["value"]
        current = series_snapshot[index]["value"]
        assert derived[index].yoy_growth.value == pytest.approx((current - previous) / previous)
        assert derived[index].index.value == pytest.approx(100.0 * current / stored_base)
    bars = yoy_bar_points(derived)
    assert [period for period, _rate in bars] == [item["period"] for item in series_snapshot[1:]]
    for (_period, rate), item, previous in zip(bars, series_snapshot[1:], series_snapshot):
        assert rate == pytest.approx((item["value"] - previous["value"]) / previous["value"])
    plotted = index_line_series(derived)
    assert len(plotted) == 1
    assert [period for period, _value in plotted[0][2]] == [item["period"] for item in series_snapshot]
    assert plotted[0][2][0][1] == 100.0
    for (_period, value), item in zip(plotted[0][2], series_snapshot):
        assert value == pytest.approx(100.0 * item["value"] / stored_base)


def test_committed_oslo_proof_artifacts() -> None:
    csv_path = PROOF_DIR / "table.csv"
    md_path = PROOF_DIR / "table.md"
    lineage_path = PROOF_DIR / "lineage.json"
    chart_path = PROOF_DIR / "chart.png"
    bar_path = PROOF_DIR / "yoy_bar.png"
    index_path = PROOF_DIR / "index_line.png"
    assert csv_path.is_file()
    assert md_path.is_file()
    assert lineage_path.is_file()
    assert chart_path.is_file()
    assert bar_path.is_file()
    assert index_path.is_file()
    assert chart_path.read_bytes().startswith(b"\x89PNG")
    assert bar_path.read_bytes().startswith(b"\x89PNG")
    assert index_path.read_bytes().startswith(b"\x89PNG")

    with csv_path.open(encoding="utf-8", newline="") as handle:
        table = list(csv.DictReader(handle))
    assert table
    assert table[0]["period"]
    assert table[-1]["period"]
    assert table[0]["yoy_growth"] == ""
    assert float(table[0]["index"]) == 100.0
    values = [float(row["value"]) for row in table]
    stored_base = values[0]
    for year, expected in M7_SANITY.items():
        match = next((row for row in table if row["period"] == year), None)
        if match is not None:
            assert float(match["value"]) == expected
    table_yoy = []
    for index in range(1, len(table)):
        previous = values[index - 1]
        current = values[index]
        rate = float(table[index]["yoy_growth"])
        assert rate == pytest.approx((current - previous) / previous)
        assert float(table[index]["index"]) == pytest.approx(100.0 * current / stored_base)
        table_yoy.append((table[index]["period"], rate))
    assert table[0]["period"] not in {period for period, _rate in table_yoy}
    table_index = [(row["period"], float(row["index"])) for row in table if row["index"]]
    assert table_index[0][1] == 100.0
    assert [period for period, _value in table_index] == [row["period"] for row in table]

    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    names = [column["name"] for column in lineage["derived_columns"]]
    assert YOY_GROWTH in names
    assert INDEX in names
    yoy = next(column for column in lineage["derived_columns"] if column["name"] == YOY_GROWTH)
    index = next(column for column in lineage["derived_columns"] if column["name"] == INDEX)
    assert yoy["formula"] == YOY_GROWTH_FORMULA
    assert index["formula"] == INDEX_FORMULA
    assert len(yoy["rows"]) == len(table)
    assert len(index["rows"]) == len(table)
    for item in yoy["rows"]:
        assert item["lineage"]["name"] == YOY_GROWTH
        assert item["lineage"]["formula"] == YOY_GROWTH_FORMULA
        assert item["lineage"]["source_observation_ids"]
        assert item["lineage"]["source_periods"]
    for item in index["rows"]:
        assert item["lineage"]["name"] == INDEX
        assert item["lineage"]["formula"] == INDEX_FORMULA
        assert item["lineage"]["base_period"]
        assert item["lineage"]["source_observation_ids"]
        assert item["lineage"]["source_periods"]
        if item["value"] is not None:
            assert item["lineage"]["base_observation_id"]
    md = md_path.read_text(encoding="utf-8")
    assert YOY_GROWTH_FORMULA in md
    assert INDEX_FORMULA in md


SSB_11763 = "ssb:11763"
SSB_PROOF_DIR = Path(__file__).resolve().parents[1] / "methods" / "proof" / "ssb11763"
SSB_STORE = SSB_PROOF_DIR / "store.json"


def _ssb11763_stored_rows() -> list[dict]:
    """Read stored ssb:11763 rows. Prefer the live sqlite; else the committed dump."""

    if REGISTRY.exists():
        from public_data_agent.registry import Registry

        registry = Registry(REGISTRY)
        try:
            stored = registry.list_observations(SSB_11763)
        finally:
            registry.close()
        if stored:
            return stored
    if not SSB_STORE.is_file():
        pytest.skip("no stored ssb:11763 rows")
    dump = json.loads(SSB_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    return dump["rows"]


def _numeric_value(row: dict):
    if "value" in row and row.get("value") is not None:
        return row["value"]
    payload = row.get("value_json")
    if payload is None or payload == "":
        return None
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    return payload


def test_live_ssb11763_store_matches_formula_and_lineage() -> None:
    stored = _ssb11763_stored_rows()
    assert len(stored) == 36
    numeric = [row for row in stored if _numeric_value(row) is not None]
    assert len(numeric) == 30
    cleaned = clean(stored)
    assert len(cleaned) == 30
    entities = {row.entity for row in cleaned}
    periods = {row.period for row in cleaned}
    assert len(entities) == 15
    assert periods == {"2024", "2025"}
    derived = derive(cleaned)

    by_key = {(row.observation.entity, row.observation.period): row for row in derived}
    assert len(derived) == 30
    for entity in entities:
        base = by_key[(entity, "2024")]
        latest = by_key[(entity, "2025")]
        assert base.yoy_growth.value is None
        assert base.yoy_growth.lineage.note == "undefined: no prior period"
        assert base.index.value == 100.0
        assert base.index.lineage.base_period == "2024"
        assert base.index.lineage.base_observation_id == base.observation.id
        expected = (latest.observation.value - base.observation.value) / base.observation.value
        assert latest.yoy_growth.value == pytest.approx(expected)
        assert latest.index.value == pytest.approx(100.0 * latest.observation.value / base.observation.value)
        assert latest.index.lineage.base_period == "2024"
        assert latest.index.lineage.base_observation_id == base.observation.id
        for row in (base, latest):
            assert row.yoy_growth.lineage.name == YOY_GROWTH
            assert row.yoy_growth.lineage.formula == YOY_GROWTH_FORMULA
            assert row.yoy_growth.lineage.input_columns == ("value",)
            assert row.yoy_growth.lineage.source_observation_ids
            assert row.yoy_growth.lineage.source_periods
            assert row.index.lineage.name == INDEX
            assert row.index.lineage.formula == INDEX_FORMULA
            assert row.index.lineage.source_observation_ids
            assert row.index.lineage.source_periods
            assert row.index.lineage.base_period
            assert row.observation.source == SSB_11763

    bars = yoy_bar_points(derived)
    assert len(bars) == 15
    assert {period for period, _rate in bars} == {"2025"}
    plotted = index_line_series(derived)
    assert len(plotted) == 15
    for _entity, _measure, points in plotted:
        assert [period for period, _value in points] == ["2024", "2025"]
        assert points[0][1] == 100.0


def test_ssb11763_cli_reads_store_and_does_not_fetch(tmp_path: Path) -> None:
    from public_data_agent.models import HarvestCounts
    from public_data_agent.registry import Registry

    from methods.cli import run as run_methods
    import methods.cli as methods_cli

    dump = json.loads(SSB_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    db = tmp_path / "registry.sqlite"
    registry = Registry(db)
    registry.ensure_observation_dataset(
        dataset_id=SSB_11763,
        title="11763: Folkemengde 31.12.",
        publisher_name="Statistisk sentralbyrå",
        access_path="https://data.ssb.no/api/v0/no/table/11763",
        license=None,
    )
    run_id = registry.start_fetch_run(
        dataset_id=SSB_11763,
        table_id="11763",
        request_url="https://data.ssb.no/api/v0/no/table/11763",
        request_method="SEED",
    )
    for row in dump["rows"]:
        registry.upsert_observation(row, run_id)
    registry.finish_fetch_run(
        run_id,
        HarvestCounts(listed=len(dump["rows"]), inserted=len(dump["rows"])),
        status="completed",
        http_status=200,
    )
    stored = registry.list_observations(SSB_11763)
    registry.close()
    assert len(stored) == 36

    fetch_calls: list[object] = []

    def _forbid_fetch(*_args, **_kwargs):
        fetch_calls.append((_args, _kwargs))
        raise AssertionError("pda fetch must not run for ssb:11763")

    original = methods_cli._call_existing_fetch
    methods_cli._call_existing_fetch = _forbid_fetch  # type: ignore[method-assign]
    try:
        derived = run_methods(
            dataset_id=SSB_11763,
            db=db,
            out=tmp_path / "out",
            table_id="11763",
            from_year=2020,
            to_year=2026,
            entity="Oslo (Kristiania og Aker) i alt",
            measure="Folkemengden i alt (antall personer)",
        )
    finally:
        methods_cli._call_existing_fetch = original  # type: ignore[method-assign]

    assert fetch_calls == []
    assert len(derived) == 30
    assert {row.observation.period for row in derived} == {"2024", "2025"}
    assert all(row.observation.source == SSB_11763 for row in derived)
    by_id = {row["id"]: _numeric_value(row) for row in stored}
    for row in derived:
        assert row.observation.value == float(by_id[row.observation.id])
        assert row.yoy_growth.lineage.formula == YOY_GROWTH_FORMULA
        assert row.index.lineage.formula == INDEX_FORMULA


def test_ssb11763_empty_store_does_not_post() -> None:
    from methods.cli import run as run_methods
    import methods.cli as methods_cli

    fetch_calls: list[object] = []

    def _forbid_fetch(*_args, **_kwargs):
        fetch_calls.append((_args, _kwargs))
        raise AssertionError("pda fetch must not run for ssb:11763")

    original = methods_cli._call_existing_fetch
    methods_cli._call_existing_fetch = _forbid_fetch  # type: ignore[method-assign]
    try:
        with pytest.raises(ValueError, match="refusing to call pda fetch"):
            run_methods(
                dataset_id=SSB_11763,
                db=Path("data/missing-registry.sqlite"),
                out=Path("/tmp/methods-11763-empty"),
                table_id="11763",
                from_year=2020,
                to_year=2026,
                entity=None,
                measure=None,
            )
    finally:
        methods_cli._call_existing_fetch = original  # type: ignore[method-assign]
    assert fetch_calls == []


def test_committed_ssb11763_proof_artifacts() -> None:
    csv_path = SSB_PROOF_DIR / "table.csv"
    md_path = SSB_PROOF_DIR / "table.md"
    lineage_path = SSB_PROOF_DIR / "lineage.json"
    chart_path = SSB_PROOF_DIR / "chart.png"
    bar_path = SSB_PROOF_DIR / "yoy_bar.png"
    index_path = SSB_PROOF_DIR / "index_line.png"
    assert csv_path.is_file()
    assert md_path.is_file()
    assert lineage_path.is_file()
    assert chart_path.is_file()
    assert bar_path.is_file()
    assert index_path.is_file()
    assert chart_path.read_bytes().startswith(b"\x89PNG")
    assert bar_path.read_bytes().startswith(b"\x89PNG")
    assert index_path.read_bytes().startswith(b"\x89PNG")
    assert (PROOF_DIR / "table.csv").is_file()
    oslo = (PROOF_DIR / "table.csv").read_text(encoding="utf-8")
    assert "Oslo (Kristiania og Aker) i alt" in oslo
    assert "ssb:11763" not in oslo

    with csv_path.open(encoding="utf-8", newline="") as handle:
        table = list(csv.DictReader(handle))
    assert len(table) == 30
    entities = {row["entity"] for row in table}
    periods = {row["period"] for row in table}
    assert len(entities) == 15
    assert periods == {"2024", "2025"}
    by_key = {(row["entity"], row["period"]): row for row in table}
    for entity in entities:
        base = by_key[(entity, "2024")]
        latest = by_key[(entity, "2025")]
        assert base["yoy_growth"] == ""
        assert float(base["index"]) == 100.0
        previous = float(base["value"])
        current = float(latest["value"])
        assert float(latest["yoy_growth"]) == pytest.approx((current - previous) / previous)
        assert float(latest["index"]) == pytest.approx(100.0 * current / previous)
        assert latest["source"] == SSB_11763
        assert base["source"] == SSB_11763

    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    names = [column["name"] for column in lineage["derived_columns"]]
    assert names == [YOY_GROWTH, INDEX]
    yoy = lineage["derived_columns"][0]
    index = lineage["derived_columns"][1]
    assert yoy["formula"] == YOY_GROWTH_FORMULA
    assert index["formula"] == INDEX_FORMULA
    assert len(yoy["rows"]) == 30
    assert len(index["rows"]) == 30
    for item in yoy["rows"]:
        assert item["lineage"]["name"] == YOY_GROWTH
        assert item["lineage"]["formula"] == YOY_GROWTH_FORMULA
        assert item["lineage"]["input_columns"] == ["value"]
        assert item["lineage"]["source_observation_ids"]
        assert item["lineage"]["source_periods"]
        if item["period"] == "2024":
            assert item["value"] is None
            assert item["lineage"]["note"] == "undefined: no prior period"
        else:
            assert item["value"] is not None
    for item in index["rows"]:
        assert item["lineage"]["name"] == INDEX
        assert item["lineage"]["formula"] == INDEX_FORMULA
        assert item["lineage"]["base_period"] == "2024"
        assert item["lineage"]["source_observation_ids"]
        assert item["lineage"]["source_periods"]
        if item["value"] is not None:
            assert item["lineage"]["base_observation_id"]
    md = md_path.read_text(encoding="utf-8")
    assert YOY_GROWTH_FORMULA in md
    assert INDEX_FORMULA in md
    dump = json.loads(SSB_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    assert dump["counts"]["total"] == 36
    assert dump["counts"]["numeric"] == 30
