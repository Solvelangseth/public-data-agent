"""Unit tests over a tiny in-memory fixture. These numbers are not Oslo facts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from methods.clean import CleanError, clean
from methods.cli import run as run_methods
from methods.derive import derive_yoy
from methods.emit import emit
from methods.types import DerivedValue, Lineage, YOY_GROWTH, YOY_GROWTH_FORMULA
from public_data_agent.cli import main
from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource

# In-memory fixture series. Deliberately not Norwegian population counts.
FIXTURE_TOWN = "Fixture Town"
FIXTURE_MEASURE = "fixture_count"
FIXTURE_ROWS = [
    {
        "id": "fixture-obs-2000",
        "dataset_id": "fixture:methods-town",
        "table_id": "fixture/table.px",
        "measure": FIXTURE_MEASURE,
        "value": 100,
        "dimensions": {"year": "2000", "entity": FIXTURE_TOWN},
        "retrieved_at": "2000-01-01T00:00:00Z",
        "request_url": "https://example.test/fixture",
        "http_status": 200,
        "publisher_name": "FIXTURE PUBLISHER",
        "license": None,
        "access_path": None,
        "source_native_uri": None,
    },
    {
        "id": "fixture-obs-2002",
        "dataset_id": "fixture:methods-town",
        "table_id": "fixture/table.px",
        "measure": FIXTURE_MEASURE,
        "value": 80,
        "dimensions": {"year": "2002", "entity": FIXTURE_TOWN},
        "retrieved_at": "2000-01-01T00:00:00Z",
        "request_url": "https://example.test/fixture",
        "http_status": 200,
        "publisher_name": "FIXTURE PUBLISHER",
        "license": None,
        "access_path": None,
        "source_native_uri": None,
    },
    {
        "id": "fixture-obs-2001",
        "dataset_id": "fixture:methods-town",
        "table_id": "fixture/table.px",
        "measure": FIXTURE_MEASURE,
        "value": 110,
        "dimensions": {"year": "2001", "entity": FIXTURE_TOWN},
        "retrieved_at": "2000-01-01T00:00:00Z",
        "request_url": "https://example.test/fixture",
        "http_status": 200,
        "publisher_name": "FIXTURE PUBLISHER",
        "license": None,
        "access_path": None,
        "source_native_uri": None,
    },
]


def test_clean_drops_non_numeric_and_sorts() -> None:
    messy = [
        FIXTURE_ROWS[2],
        {**FIXTURE_ROWS[0], "id": "fixture-null", "value": None},
        {**FIXTURE_ROWS[0], "id": "fixture-text", "value": "not-a-number"},
        FIXTURE_ROWS[0],
        {**FIXTURE_ROWS[1], "value_json": "80", "value": None},
    ]
    rows = clean(messy)
    assert [row.period for row in rows] == ["2000", "2001", "2002"]
    assert [row.value for row in rows] == [100.0, 110.0, 80.0]
    assert rows[0].entity == FIXTURE_TOWN
    assert rows[0].source == "fixture:methods-town"


def test_clean_rejects_missing_schema_fields() -> None:
    with pytest.raises(CleanError, match="missing id"):
        clean([{k: v for k, v in FIXTURE_ROWS[0].items() if k != "id"}])
    with pytest.raises(CleanError, match="no period"):
        clean([{**FIXTURE_ROWS[0], "dimensions": {"entity": FIXTURE_TOWN}}])


def test_clean_parses_registry_json_columns() -> None:
    rows = clean(
        [
            {
                "id": "fixture-json",
                "dataset_id": "fixture:methods-town",
                "table_id": "fixture/table.px",
                "measure": FIXTURE_MEASURE,
                "value_json": "250",
                "dimensions_json": json.dumps({"år": "1999", "geografisk område": FIXTURE_TOWN}),
                "retrieved_at": "1999-01-01T00:00:00Z",
                "request_url": "https://example.test/fixture",
                "http_status": 200,
            }
        ]
    )
    assert len(rows) == 1
    assert rows[0].period == "1999"
    assert rows[0].entity == FIXTURE_TOWN
    assert rows[0].value == 250.0


def test_yoy_formula_and_first_period_absent() -> None:
    derived = derive_yoy(clean(FIXTURE_ROWS))
    assert len(derived) == 3
    assert derived[0].yoy_growth.value is None
    assert derived[0].yoy_growth.lineage.note == "undefined: no prior period"
    assert derived[1].yoy_growth.value == pytest.approx((110 - 100) / 100)
    assert derived[2].yoy_growth.value == pytest.approx((80 - 110) / 110)
    for row in derived:
        assert row.yoy_growth.lineage.name == YOY_GROWTH
        assert row.yoy_growth.lineage.formula == YOY_GROWTH_FORMULA
        assert row.yoy_growth.lineage.input_columns == ("value",)
        assert row.yoy_growth.lineage.source_observation_ids
        assert row.yoy_growth.lineage.source_periods


def test_zero_prior_value_is_undefined() -> None:
    rows = clean(
        [
            {**FIXTURE_ROWS[0], "value": 0},
            {**FIXTURE_ROWS[2], "value": 10},
        ]
    )
    derived = derive_yoy(rows)
    assert derived[1].yoy_growth.value is None
    assert derived[1].yoy_growth.lineage.note == "undefined: v_{t-1} is 0"


def test_derived_without_lineage_is_unrepresentable() -> None:
    with pytest.raises(TypeError):
        DerivedValue(value=0.1)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        DerivedValue(value=0.1, lineage=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="formula"):
        Lineage(
            name="yoy_growth",
            formula="",
            input_columns=("value",),
            units="ratio",
            source_observation_ids=("x",),
            source_periods=("2000",),
        )


def test_emit_writes_table_chart_and_lineage(tmp_path: Path) -> None:
    derived = derive_yoy(clean(FIXTURE_ROWS))
    paths = emit(derived, tmp_path)
    csv_text = paths["csv"].read_text(encoding="utf-8")
    assert "fixture-obs-2000" in csv_text
    assert "0.1" in csv_text
    md = paths["markdown"].read_text(encoding="utf-8")
    assert YOY_GROWTH_FORMULA in md
    lineage = json.loads(paths["lineage"].read_text(encoding="utf-8"))
    column = lineage["derived_columns"][0]
    assert column["name"] == YOY_GROWTH
    assert column["formula"] == YOY_GROWTH_FORMULA
    assert len(column["rows"]) == 3
    for item in column["rows"]:
        assert item["lineage"]["name"] == YOY_GROWTH
        assert item["lineage"]["formula"] == YOY_GROWTH_FORMULA
    png = paths["chart"].read_bytes()
    assert png.startswith(b"\x89PNG")


def test_methods_modules_do_not_import_connectors() -> None:
    root = Path(__file__).resolve().parents[1] / "methods"
    forbidden = (
        "public_data_agent.fetch",
        "public_data_agent.sources",
        "pxweb",
        "datanorge",
        "statbank",
    )
    for path in root.glob("*.py"):
        if path.name in {"cli.py", "__main__.py"}:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text, f"{path.name} mentions {token}"


def _fixture_registry(tmp_path: Path) -> Path:
    payloads = [
        json.loads((Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    db = tmp_path / "registry.sqlite"
    registry = Registry(db)
    harvest(registry, FixtureSource(payloads))
    dataset_id = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
    run_id = registry.start_fetch_run(
        dataset_id=dataset_id,
        table_id="fixture/table.px",
        request_url="https://example.test/fixture",
        request_method="TEST",
    )
    for row in FIXTURE_ROWS:
        registry.upsert_observation(
            {
                **row,
                "dataset_id": dataset_id,
                "dimensions": {"år": row["dimensions"]["year"], "geografisk område": FIXTURE_TOWN},
            },
            run_id,
        )
    registry.close()
    return db


def test_cli_methods_on_fixture_store(tmp_path: Path) -> None:
    db = _fixture_registry(tmp_path)
    out = tmp_path / "proof"
    assert (
        main(
            [
                "methods",
                "--dataset",
                "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f",
                "--db",
                str(db),
                "--out",
                str(out),
                "--entity",
                FIXTURE_TOWN,
                "--measure",
                FIXTURE_MEASURE,
            ]
        )
        == 0
    )
    table = (out / "table.csv").read_text(encoding="utf-8")
    assert "100" in table
    assert "110" in table
    assert (out / "chart.png").is_file()
    lineage = json.loads((out / "lineage.json").read_text(encoding="utf-8"))
    assert lineage["derived_columns"][0]["formula"] == YOY_GROWTH_FORMULA


def test_run_methods_uses_stored_fixture_values(tmp_path: Path) -> None:
    db = _fixture_registry(tmp_path)
    derived = run_methods(
        dataset_id="fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f",
        db=db,
        out=tmp_path / "out",
        table_id="fixture/table.px",
        from_year=None,
        to_year=None,
        entity=FIXTURE_TOWN,
        measure=FIXTURE_MEASURE,
    )
    stored = Registry(db).list_observations("fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f")
    by_id = {row["id"]: json.loads(row["value_json"]) for row in stored}
    assert [row.observation.value for row in derived] == [
        float(by_id[row.observation.id]) for row in derived
    ]
    assert derived[0].yoy_growth.value is None
    assert derived[1].yoy_growth.value == pytest.approx(
        (by_id["fixture-obs-2001"] - by_id["fixture-obs-2000"]) / by_id["fixture-obs-2000"]
    )
