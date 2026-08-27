"""Unit tests over a tiny in-memory fixture. These numbers are not Oslo facts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from methods.clean import CleanError, clean
from methods.cli import run as run_methods
from methods.derive import derive, derive_yoy
from methods.emit import emit, index_line_series, yoy_bar_points
from methods.types import (
    DerivedValue,
    Lineage,
    INDEX,
    INDEX_FORMULA,
    RANK,
    RANK_CHANGE,
    RANK_CHANGE_FORMULA,
    RANK_FORMULA,
    YOY_GROWTH,
    YOY_GROWTH_FORMULA,
)
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


def test_index_default_base_is_first_period() -> None:
    derived = derive(clean(FIXTURE_ROWS))
    assert derived[0].index.value == 100.0
    assert derived[0].observation.period == "2000"
    assert derived[1].index.value == pytest.approx(100.0 * 110 / 100)
    assert derived[2].index.value == pytest.approx(100.0 * 80 / 100)
    for row in derived:
        assert row.index.lineage.name == INDEX
        assert row.index.lineage.formula == INDEX_FORMULA
        assert row.index.lineage.base_period == "2000"
        assert row.index.lineage.base_observation_id == "fixture-obs-2000"
        assert row.index.lineage.source_observation_ids
        assert row.index.lineage.source_periods


def test_rank_and_rank_change_two_entities_two_periods() -> None:
    rows = clean(
        [
            {**FIXTURE_ROWS[0], "id": "a-1", "value": 50, "dimensions": {"year": "2000", "entity": "Fixture A"}},
            {**FIXTURE_ROWS[2], "id": "a-2", "value": 150, "dimensions": {"year": "2001", "entity": "Fixture A"}},
            {**FIXTURE_ROWS[0], "id": "b-1", "value": 200, "dimensions": {"year": "2000", "entity": "Fixture B"}},
            {**FIXTURE_ROWS[2], "id": "b-2", "value": 100, "dimensions": {"year": "2001", "entity": "Fixture B"}},
        ]
    )
    derived = derive(rows)
    by_key = {(row.observation.entity, row.observation.period): row for row in derived}
    assert by_key[("Fixture B", "2000")].rank.value == 1
    assert by_key[("Fixture A", "2000")].rank.value == 2
    assert by_key[("Fixture A", "2001")].rank.value == 1
    assert by_key[("Fixture B", "2001")].rank.value == 2
    assert by_key[("Fixture A", "2000")].rank_change.value is None
    assert by_key[("Fixture B", "2000")].rank_change.value is None
    assert by_key[("Fixture A", "2001")].rank_change.value == 1  # 2 -> 1, moved up
    assert by_key[("Fixture B", "2001")].rank_change.value == -1  # 1 -> 2, moved down
    for row in derived:
        assert row.rank.lineage.name == RANK
        assert row.rank.lineage.formula == RANK_FORMULA
        assert row.rank.lineage.peer_observation_ids
        assert row.rank_change.lineage.name == RANK_CHANGE
        assert row.rank_change.lineage.formula == RANK_CHANGE_FORMULA
        assert row.rank_change.lineage.peer_observation_ids
        for derived_col in row.derived_columns():
            assert derived_col.lineage.source_observation_ids
            assert derived_col.lineage.source_periods


def test_rank_ties_share_min_and_skip() -> None:
    rows = clean(
        [
            {**FIXTURE_ROWS[0], "id": "a-1", "value": 100, "dimensions": {"year": "2000", "entity": "Fixture A"}},
            {**FIXTURE_ROWS[0], "id": "b-1", "value": 100, "dimensions": {"year": "2000", "entity": "Fixture B"}},
            {**FIXTURE_ROWS[0], "id": "c-1", "value": 50, "dimensions": {"year": "2000", "entity": "Fixture C"}},
        ]
    )
    derived = derive(rows)
    by_entity = {row.observation.entity: row for row in derived}
    assert by_entity["Fixture A"].rank.value == 1
    assert by_entity["Fixture B"].rank.value == 1
    assert by_entity["Fixture C"].rank.value == 3
    peers = set(by_entity["Fixture A"].rank.lineage.peer_observation_ids or ())
    assert peers == {"a-1", "b-1", "c-1"}


def test_index_two_entities_each_have_own_base(tmp_path: Path) -> None:
    # Fixture Town A/B — not Oslo. Each (entity, measure) series has its own 100.
    rows = clean(
        [
            {**FIXTURE_ROWS[0], "id": "a-1", "value": 50, "dimensions": {"year": "2000", "entity": "Fixture A"}},
            {**FIXTURE_ROWS[2], "id": "a-2", "value": 75, "dimensions": {"year": "2001", "entity": "Fixture A"}},
            {**FIXTURE_ROWS[0], "id": "b-1", "value": 200, "dimensions": {"year": "2000", "entity": "Fixture B"}},
            {**FIXTURE_ROWS[2], "id": "b-2", "value": 100, "dimensions": {"year": "2001", "entity": "Fixture B"}},
        ]
    )
    derived = derive(rows)
    by_key = {(row.observation.entity, row.observation.period): row for row in derived}
    assert by_key[("Fixture A", "2000")].index.value == 100.0
    assert by_key[("Fixture A", "2001")].index.value == pytest.approx(150.0)
    assert by_key[("Fixture B", "2000")].index.value == 100.0
    assert by_key[("Fixture B", "2001")].index.value == pytest.approx(50.0)
    assert by_key[("Fixture A", "2001")].index.lineage.base_observation_id == "a-1"
    assert by_key[("Fixture B", "2001")].index.lineage.base_observation_id == "b-1"
    series = index_line_series(derived)
    assert [item[0] for item in series] == ["Fixture A", "Fixture B"]
    assert series[0][2][0] == ("2000", 100.0)
    assert series[1][2][0] == ("2000", 100.0)
    paths = emit(derived, tmp_path)
    assert paths["index_line"].read_bytes().startswith(b"\x89PNG")


def test_index_configurable_base_period() -> None:
    derived = derive(clean(FIXTURE_ROWS), base_period="2001")
    assert derived[1].observation.period == "2001"
    assert derived[1].index.value == 100.0
    assert derived[0].index.value == pytest.approx(100.0 * 100 / 110)
    assert derived[2].index.value == pytest.approx(100.0 * 80 / 110)
    assert all(row.index.lineage.base_period == "2001" for row in derived)


def test_index_missing_or_zero_base_is_undefined() -> None:
    missing = derive(clean(FIXTURE_ROWS), base_period="1990")
    assert all(row.index.value is None for row in missing)
    assert all(row.index.lineage.note == "undefined: base period not in series" for row in missing)
    zero = derive(
        clean(
            [
                {**FIXTURE_ROWS[0], "value": 0},
                {**FIXTURE_ROWS[2], "value": 10},
            ]
        )
    )
    assert zero[0].index.value is None
    assert zero[1].index.value is None
    assert zero[0].index.lineage.note == "undefined: v_base is 0"


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
    with pytest.raises(ValueError, match="base_period"):
        Lineage(
            name=INDEX,
            formula=INDEX_FORMULA,
            input_columns=("value",),
            units="index (base = 100)",
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
    assert INDEX_FORMULA in md
    assert "index" in csv_text
    lineage = json.loads(paths["lineage"].read_text(encoding="utf-8"))
    names = [column["name"] for column in lineage["derived_columns"]]
    assert names == [YOY_GROWTH, INDEX, RANK, RANK_CHANGE]
    yoy = lineage["derived_columns"][0]
    index = lineage["derived_columns"][1]
    rank = lineage["derived_columns"][2]
    rank_change = lineage["derived_columns"][3]
    assert yoy["formula"] == YOY_GROWTH_FORMULA
    assert index["formula"] == INDEX_FORMULA
    assert rank["formula"] == RANK_FORMULA
    assert rank_change["formula"] == RANK_CHANGE_FORMULA
    assert len(yoy["rows"]) == 3
    assert len(index["rows"]) == 3
    assert len(rank["rows"]) == 3
    assert len(rank_change["rows"]) == 3
    for item in yoy["rows"]:
        assert item["lineage"]["name"] == YOY_GROWTH
        assert item["lineage"]["formula"] == YOY_GROWTH_FORMULA
    for item in index["rows"]:
        assert item["lineage"]["name"] == INDEX
        assert item["lineage"]["formula"] == INDEX_FORMULA
        assert item["lineage"]["base_period"] == "2000"
    png = paths["chart"].read_bytes()
    assert png.startswith(b"\x89PNG")
    bar = paths["yoy_bar"].read_bytes()
    assert bar.startswith(b"\x89PNG")
    points = yoy_bar_points(derived)
    assert [period for period, _rate in points] == ["2001", "2002"]
    assert points[0][1] == pytest.approx(0.1)
    assert points[1][1] == pytest.approx((80 - 110) / 110)
    index_png = paths["index_line"].read_bytes()
    assert index_png.startswith(b"\x89PNG")
    series = index_line_series(derived)
    assert len(series) == 1
    assert series[0][0] == FIXTURE_TOWN
    assert [period for period, _value in series[0][2]] == ["2000", "2001", "2002"]
    assert series[0][2][0][1] == 100.0
    assert series[0][2][1][1] == pytest.approx(110.0)


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
    assert lineage["derived_columns"][1]["formula"] == INDEX_FORMULA
    assert lineage["derived_columns"][2]["formula"] == RANK_FORMULA
    assert lineage["derived_columns"][3]["formula"] == RANK_CHANGE_FORMULA
    assert "index" in table
    assert "rank" in table


def test_select_oslo_defaults_keep_every_entity_when_unmatched() -> None:
    from methods.cli import DEFAULT_ENTITY, DEFAULT_MEASURE, _select

    rows = clean(
        [
            {**FIXTURE_ROWS[0], "id": "a-1", "dimensions": {"year": "2000", "entity": "Fixture A"}},
            {**FIXTURE_ROWS[2], "id": "a-2", "dimensions": {"year": "2001", "entity": "Fixture A"}},
            {**FIXTURE_ROWS[0], "id": "b-1", "dimensions": {"year": "2000", "entity": "Fixture B"}},
        ]
    )
    kept = _select(rows, entity=DEFAULT_ENTITY, measure=DEFAULT_MEASURE)
    assert {row.entity for row in kept} == {"Fixture A", "Fixture B"}
    missing = _select(rows, entity="Not A Real Entity", measure=None)
    assert missing == ()


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
