from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from methods.clean import clean
from methods.derive import derive
from methods.emit import index_line_series, yoy_bar_points
from methods.types import (
    INDEX,
    INDEX_FORMULA,
    PERIOD_CHANGE,
    PERIOD_CHANGE_FORMULA,
    PERIOD_CHANGE_UNITS,
    RANK,
    RANK_CHANGE,
    RANK_CHANGE_FORMULA,
    RANK_FORMULA,
    YOY_GROWTH,
    YOY_GROWTH_FORMULA,
)

OSLO_DATASET = "datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57"
OSLO_ENTITY = "Oslo (Kristiania og Aker) i alt"
OSLO_MEASURE = "Folkemengden i alt (antall personer)"
PROOF_DIR = Path(__file__).resolve().parents[1] / "methods" / "proof"
REGISTRY = Path("data/registry.sqlite")

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
JOIN_SERIES = "join:bydel_population"
SSB_PROOF_DIR = Path(__file__).resolve().parents[1] / "methods" / "proof" / "ssb11763"
SSB_STORE = SSB_PROOF_DIR / "store.json"


def _ssb11763_stored_rows() -> list[dict]:
    if REGISTRY.exists():
        from public_data_agent.registry import Registry

        registry = Registry(REGISTRY)
        try:
            # One dataset_id holds several projections: a raw full-table fetch
            # (every age, every region) and this joined per-bydel "I alt" series.
            # The formula/lineage proof is about the joined series, so it must be
            # scoped to it -- an unscoped read blends two incompatible shapes.
            stored = registry.list_observations(SSB_11763, series=JOIN_SERIES)
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
        assert base.rank_change.value is None
        assert latest.rank_change.value == pytest.approx(base.rank.value - latest.rank.value)
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
            assert row.rank.lineage.name == RANK
            assert row.rank.lineage.formula == RANK_FORMULA
            assert row.rank.lineage.peer_observation_ids
            assert len(row.rank.lineage.peer_observation_ids) == 15
            assert row.rank_change.lineage.name == RANK_CHANGE
            assert row.rank_change.lineage.formula == RANK_CHANGE_FORMULA
            assert row.rank_change.lineage.peer_observation_ids
            assert row.observation.source == SSB_11763
            for derived_col in row.derived_columns():
                assert derived_col.lineage.name
                assert derived_col.lineage.formula
                assert derived_col.lineage.source_observation_ids
                assert derived_col.lineage.source_periods

    rank1_2024 = max((row for row in derived if row.observation.period == "2024"), key=lambda row: row.observation.value)
    assert rank1_2024.rank.value == 1
    assert rank1_2024.observation.value == max(
        row.observation.value for row in derived if row.observation.period == "2024"
    )

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
    methods_cli._call_existing_fetch = _forbid_fetch
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
        methods_cli._call_existing_fetch = original
    assert fetch_calls == []
    assert len(derived) == 30
    assert {row.observation.period for row in derived} == {"2024", "2025"}
    assert all(row.observation.source == SSB_11763 for row in derived)
    by_id = {row["id"]: _numeric_value(row) for row in stored}
    for row in derived:
        assert row.observation.value == float(by_id[row.observation.id])
        assert row.yoy_growth.lineage.formula == YOY_GROWTH_FORMULA
        assert row.index.lineage.formula == INDEX_FORMULA
        assert row.rank.lineage.formula == RANK_FORMULA
        assert row.rank_change.lineage.formula == RANK_CHANGE_FORMULA


def test_ssb11763_empty_store_does_not_post() -> None:
    from methods.cli import run as run_methods
    import methods.cli as methods_cli

    fetch_calls: list[object] = []

    def _forbid_fetch(*_args, **_kwargs):
        fetch_calls.append((_args, _kwargs))
        raise AssertionError("pda fetch must not run for ssb:11763")

    original = methods_cli._call_existing_fetch
    methods_cli._call_existing_fetch = _forbid_fetch
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
        methods_cli._call_existing_fetch = original
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
        assert base["rank_change"] == ""
        assert float(latest["rank_change"]) == pytest.approx(float(base["rank"]) - float(latest["rank"]))

    rank1 = max((row for row in table if row["period"] == "2024"), key=lambda row: float(row["value"]))
    assert float(rank1["rank"]) == 1

    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
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
    assert len(yoy["rows"]) == 30
    assert len(index["rows"]) == 30
    assert len(rank["rows"]) == 30
    assert len(rank_change["rows"]) == 30
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
    for item in rank["rows"]:
        assert item["lineage"]["name"] == RANK
        assert item["lineage"]["formula"] == RANK_FORMULA
        assert item["lineage"]["peer_observation_ids"]
        assert len(item["lineage"]["peer_observation_ids"]) == 15
        assert item["value"] is not None
    for item in rank_change["rows"]:
        assert item["lineage"]["name"] == RANK_CHANGE
        assert item["lineage"]["formula"] == RANK_CHANGE_FORMULA
        assert item["lineage"]["peer_observation_ids"]
        if item["period"] == "2024":
            assert item["value"] is None
        else:
            assert item["value"] is not None
    md = md_path.read_text(encoding="utf-8")
    assert YOY_GROWTH_FORMULA in md
    assert INDEX_FORMULA in md
    assert RANK_FORMULA in md
    assert RANK_CHANGE_FORMULA in md
    dump = json.loads(SSB_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    assert dump["counts"]["total"] == 36
    assert dump["counts"]["numeric"] == 30


SSB_06683 = "ssb:06683"
SSB_06683_PROOF_DIR = Path(__file__).resolve().parents[1] / "methods" / "proof" / "ssb06683"
SSB_06683_STORE = SSB_06683_PROOF_DIR / "store.json"
SSB_06683_VALUES = {
    ("Stebarn", "2023"): 202.0,
    ("Stebarn", "2024"): 236.0,
    ("Utenlandsadopsjoner", "2023"): 34.0,
    ("Utenlandsadopsjoner", "2024"): 24.0,
}


def _ssb06683_stored_rows() -> list[dict]:
    if REGISTRY.exists():
        from public_data_agent.registry import Registry

        registry = Registry(REGISTRY)
        try:
            stored = registry.list_observations(SSB_06683)
        finally:
            registry.close()
        if stored:
            return stored
    if not SSB_06683_STORE.is_file():
        pytest.skip("no stored ssb:06683 rows")
    dump = json.loads(SSB_06683_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    return dump["rows"]


def test_live_ssb06683_store_matches_formula_and_lineage() -> None:
    stored = _ssb06683_stored_rows()
    assert len(stored) == 4
    numeric = [row for row in stored if _numeric_value(row) is not None]
    assert len(numeric) == 4
    cleaned = clean(stored)
    assert len(cleaned) == 4
    entities = {row.entity for row in cleaned}
    periods = {row.period for row in cleaned}
    assert entities == {"Stebarn", "Utenlandsadopsjoner"}
    assert periods == {"2023", "2024"}
    for row in cleaned:
        assert row.value == SSB_06683_VALUES[(row.entity, row.period)]
        assert row.source == SSB_06683
    derived = derive(cleaned)

    by_key = {(row.observation.entity, row.observation.period): row for row in derived}
    assert len(derived) == 4
    for entity in entities:
        base = by_key[(entity, "2023")]
        latest = by_key[(entity, "2024")]
        assert base.yoy_growth.value is None
        assert base.yoy_growth.lineage.note == "undefined: no prior period"
        assert base.index.value == 100.0
        assert base.index.lineage.base_period == "2023"
        assert base.index.lineage.base_observation_id == base.observation.id
        expected = (latest.observation.value - base.observation.value) / base.observation.value
        assert latest.yoy_growth.value == pytest.approx(expected)
        assert latest.index.value == pytest.approx(
            100.0 * latest.observation.value / base.observation.value
        )
        assert latest.index.lineage.base_period == "2023"
        assert latest.index.lineage.base_observation_id == base.observation.id
        assert base.rank_change.value is None
        assert latest.rank_change.value == pytest.approx(base.rank.value - latest.rank.value)
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
            assert row.rank.lineage.name == RANK
            assert row.rank.lineage.formula == RANK_FORMULA
            assert row.rank.lineage.peer_observation_ids
            assert len(row.rank.lineage.peer_observation_ids) == 2
            assert row.rank_change.lineage.name == RANK_CHANGE
            assert row.rank_change.lineage.formula == RANK_CHANGE_FORMULA
            assert row.rank_change.lineage.peer_observation_ids
            assert row.observation.source == SSB_06683
            for derived_col in row.derived_columns():
                assert derived_col.lineage.name
                assert derived_col.lineage.formula
                assert derived_col.lineage.source_observation_ids
                assert derived_col.lineage.source_periods

    stebarn_2024 = by_key[("Stebarn", "2024")]
    utenlands_2024 = by_key[("Utenlandsadopsjoner", "2024")]
    assert stebarn_2024.yoy_growth.value == pytest.approx((236 - 202) / 202)
    assert utenlands_2024.yoy_growth.value == pytest.approx((24 - 34) / 34)
    assert stebarn_2024.index.value == pytest.approx(100.0 * 236 / 202)
    assert utenlands_2024.index.value == pytest.approx(100.0 * 24 / 34)
    assert by_key[("Stebarn", "2023")].rank.value == 1
    assert by_key[("Utenlandsadopsjoner", "2023")].rank.value == 2

    bars = yoy_bar_points(derived)
    assert len(bars) == 2
    assert {period for period, _rate in bars} == {"2024"}
    plotted = index_line_series(derived)
    assert len(plotted) == 2
    for _entity, _measure, points in plotted:
        assert [period for period, _value in points] == ["2023", "2024"]
        assert points[0][1] == 100.0


def test_ssb06683_cli_reads_store_and_does_not_fetch(tmp_path: Path) -> None:
    from public_data_agent.models import HarvestCounts
    from public_data_agent.registry import Registry

    from methods.cli import run as run_methods
    import methods.cli as methods_cli

    dump = json.loads(SSB_06683_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    db = tmp_path / "registry.sqlite"
    registry = Registry(db)
    registry.ensure_observation_dataset(
        dataset_id=SSB_06683,
        title="06683: Adopsjoner, etter adopsjonstype, statistikkvariabel og år",
        publisher_name="Statistisk sentralbyrå",
        access_path="https://data.ssb.no/api/v0/no/table/06683",
        license=None,
    )
    run_id = registry.start_fetch_run(
        dataset_id=SSB_06683,
        table_id="06683",
        request_url="https://data.ssb.no/api/v0/no/table/06683",
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
    stored = registry.list_observations(SSB_06683)
    registry.close()
    assert len(stored) == 4

    fetch_calls: list[object] = []

    def _forbid_fetch(*_args, **_kwargs):
        fetch_calls.append((_args, _kwargs))
        raise AssertionError("pda fetch must not run for ssb:06683")

    original = methods_cli._call_existing_fetch
    methods_cli._call_existing_fetch = _forbid_fetch
    try:
        derived = run_methods(
            dataset_id=SSB_06683,
            db=db,
            out=tmp_path / "out",
            table_id="06683",
            from_year=2023,
            to_year=2024,
            entity="Oslo (Kristiania og Aker) i alt",
            measure="Folkemengden i alt (antall personer)",
        )
    finally:
        methods_cli._call_existing_fetch = original
    assert fetch_calls == []
    assert len(derived) == 4
    assert {row.observation.period for row in derived} == {"2023", "2024"}
    assert {row.observation.entity for row in derived} == {"Stebarn", "Utenlandsadopsjoner"}
    assert all(row.observation.source == SSB_06683 for row in derived)
    by_id = {row["id"]: _numeric_value(row) for row in stored}
    for row in derived:
        assert row.observation.value == float(by_id[row.observation.id])
        assert row.yoy_growth.lineage.formula == YOY_GROWTH_FORMULA
        assert row.index.lineage.formula == INDEX_FORMULA
        assert row.rank.lineage.formula == RANK_FORMULA
        assert row.rank_change.lineage.formula == RANK_CHANGE_FORMULA


def test_ssb06683_empty_store_does_not_post() -> None:
    from methods.cli import run as run_methods
    import methods.cli as methods_cli

    fetch_calls: list[object] = []

    def _forbid_fetch(*_args, **_kwargs):
        fetch_calls.append((_args, _kwargs))
        raise AssertionError("pda fetch must not run for ssb:06683")

    original = methods_cli._call_existing_fetch
    methods_cli._call_existing_fetch = _forbid_fetch
    try:
        with pytest.raises(ValueError, match="refusing to call pda fetch"):
            run_methods(
                dataset_id=SSB_06683,
                db=Path("data/missing-registry-06683.sqlite"),
                out=Path("/tmp/methods-06683-empty"),
                table_id="06683",
                from_year=2023,
                to_year=2024,
                entity=None,
                measure=None,
            )
    finally:
        methods_cli._call_existing_fetch = original
    assert fetch_calls == []


def test_committed_ssb06683_proof_artifacts() -> None:
    csv_path = SSB_06683_PROOF_DIR / "table.csv"
    md_path = SSB_06683_PROOF_DIR / "table.md"
    lineage_path = SSB_06683_PROOF_DIR / "lineage.json"
    chart_path = SSB_06683_PROOF_DIR / "chart.png"
    bar_path = SSB_06683_PROOF_DIR / "yoy_bar.png"
    index_path = SSB_06683_PROOF_DIR / "index_line.png"
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
    assert "ssb:06683" not in oslo
    ssb11763 = (SSB_PROOF_DIR / "table.csv").read_text(encoding="utf-8")
    assert "ssb:11763" in ssb11763
    assert "ssb:06683" not in ssb11763

    with csv_path.open(encoding="utf-8", newline="") as handle:
        table = list(csv.DictReader(handle))
    assert len(table) == 4
    entities = {row["entity"] for row in table}
    periods = {row["period"] for row in table}
    assert entities == {"Stebarn", "Utenlandsadopsjoner"}
    assert periods == {"2023", "2024"}
    by_key = {(row["entity"], row["period"]): row for row in table}
    for entity in entities:
        base = by_key[(entity, "2023")]
        latest = by_key[(entity, "2024")]
        assert base["yoy_growth"] == ""
        assert float(base["index"]) == 100.0
        previous = float(base["value"])
        current = float(latest["value"])
        assert previous == SSB_06683_VALUES[(entity, "2023")]
        assert current == SSB_06683_VALUES[(entity, "2024")]
        assert float(latest["yoy_growth"]) == pytest.approx((current - previous) / previous)
        assert float(latest["index"]) == pytest.approx(100.0 * current / previous)
        assert latest["source"] == SSB_06683
        assert base["source"] == SSB_06683
        assert base["rank_change"] == ""
        assert float(latest["rank_change"]) == pytest.approx(float(base["rank"]) - float(latest["rank"]))

    assert float(by_key[("Stebarn", "2024")]["yoy_growth"]) == pytest.approx((236 - 202) / 202)
    assert float(by_key[("Utenlandsadopsjoner", "2024")]["yoy_growth"]) == pytest.approx((24 - 34) / 34)
    assert float(by_key[("Stebarn", "2023")]["rank"]) == 1

    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
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
    assert len(yoy["rows"]) == 4
    assert len(index["rows"]) == 4
    assert len(rank["rows"]) == 4
    assert len(rank_change["rows"]) == 4
    for item in yoy["rows"]:
        assert item["lineage"]["name"] == YOY_GROWTH
        assert item["lineage"]["formula"] == YOY_GROWTH_FORMULA
        assert item["lineage"]["input_columns"] == ["value"]
        assert item["lineage"]["source_observation_ids"]
        assert item["lineage"]["source_periods"]
        if item["period"] == "2023":
            assert item["value"] is None
            assert item["lineage"]["note"] == "undefined: no prior period"
        else:
            assert item["value"] is not None
    for item in index["rows"]:
        assert item["lineage"]["name"] == INDEX
        assert item["lineage"]["formula"] == INDEX_FORMULA
        assert item["lineage"]["base_period"] == "2023"
        assert item["lineage"]["source_observation_ids"]
        assert item["lineage"]["source_periods"]
        if item["value"] is not None:
            assert item["lineage"]["base_observation_id"]
        if item["period"] == "2023":
            assert item["value"] == 100.0
    for item in rank["rows"]:
        assert item["lineage"]["name"] == RANK
        assert item["lineage"]["formula"] == RANK_FORMULA
        assert item["lineage"]["peer_observation_ids"]
        assert len(item["lineage"]["peer_observation_ids"]) == 2
        assert item["value"] is not None
    for item in rank_change["rows"]:
        assert item["lineage"]["name"] == RANK_CHANGE
        assert item["lineage"]["formula"] == RANK_CHANGE_FORMULA
        assert item["lineage"]["peer_observation_ids"]
        if item["period"] == "2023":
            assert item["value"] is None
        else:
            assert item["value"] is not None
    md = md_path.read_text(encoding="utf-8")
    assert YOY_GROWTH_FORMULA in md
    assert INDEX_FORMULA in md
    assert RANK_FORMULA in md
    assert RANK_CHANGE_FORMULA in md
    dump = json.loads(SSB_06683_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    assert dump["counts"]["total"] == 4
    assert dump["counts"]["numeric"] == 4
    committed = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "ssb_source_proof.json").read_text(
            encoding="utf-8"
        )
    )
    printed = {
        (item["dimensions"]["Adopsjonstype"], item["dimensions"]["Tid"]): item["value"]
        for item in committed["fetch"]["sample"]
    }
    assert printed == {
        ("Stebarn", "2023"): 202,
        ("Stebarn", "2024"): 236,
        ("Utenlandsadopsjoner", "2023"): 34,
        ("Utenlandsadopsjoner", "2024"): 24,
    }


SSB_06831 = "ssb:06831"
SSB_06831_PROOF_DIR = Path(__file__).resolve().parents[1] / "methods" / "proof" / "ssb06831"
SSB_06831_STORE = SSB_06831_PROOF_DIR / "store.json"
SSB_06831_ENTITY_16 = "16-19 år / Kvinner / Samboere"
SSB_06831_ENTITY_20 = "20-24 år / Kvinner / Samboere"
SSB_06831_VALUES = {
    (SSB_06831_ENTITY_16, "2021"): 3.0,
    (SSB_06831_ENTITY_16, "2022"): 2.0,
    (SSB_06831_ENTITY_20, "2021"): 23.0,
    (SSB_06831_ENTITY_20, "2022"): 23.0,
}


def _ssb06831_stored_rows() -> list[dict]:
    if REGISTRY.exists():
        from public_data_agent.registry import Registry

        registry = Registry(REGISTRY)
        try:
            stored = registry.list_observations(SSB_06831)
        finally:
            registry.close()
        if stored:
            return stored
    if not SSB_06831_STORE.is_file():
        pytest.skip("no stored ssb:06831 rows")
    dump = json.loads(SSB_06831_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    return dump["rows"]


def test_live_ssb06831_store_matches_formula_and_lineage() -> None:
    stored = _ssb06831_stored_rows()
    assert len(stored) == 4
    numeric = [row for row in stored if _numeric_value(row) is not None]
    assert len(numeric) == 4
    cleaned = clean(stored)
    assert len(cleaned) == 4
    entities = {row.entity for row in cleaned}
    periods = {row.period for row in cleaned}
    assert entities == {SSB_06831_ENTITY_16, SSB_06831_ENTITY_20}
    assert periods == {"2021", "2022"}
    for row in cleaned:
        assert row.value == SSB_06831_VALUES[(row.entity, row.period)]
        assert row.source == SSB_06831
    derived = derive(cleaned)

    by_key = {(row.observation.entity, row.observation.period): row for row in derived}
    assert len(derived) == 4
    for entity in entities:
        base = by_key[(entity, "2021")]
        latest = by_key[(entity, "2022")]
        assert base.yoy_growth.value is None
        assert base.yoy_growth.lineage.note == "undefined: no prior period"
        assert base.index.value == 100.0
        assert base.index.lineage.base_period == "2021"
        assert base.index.lineage.base_observation_id == base.observation.id
        expected = (latest.observation.value - base.observation.value) / base.observation.value
        assert latest.yoy_growth.value == pytest.approx(expected)
        assert latest.index.value == pytest.approx(
            100.0 * latest.observation.value / base.observation.value
        )
        assert latest.index.lineage.base_period == "2021"
        assert latest.index.lineage.base_observation_id == base.observation.id
        assert base.rank_change.value is None
        assert latest.rank_change.value == pytest.approx(base.rank.value - latest.rank.value)
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
            assert row.rank.lineage.name == RANK
            assert row.rank.lineage.formula == RANK_FORMULA
            assert row.rank.lineage.peer_observation_ids
            assert len(row.rank.lineage.peer_observation_ids) == 2
            assert row.rank_change.lineage.name == RANK_CHANGE
            assert row.rank_change.lineage.formula == RANK_CHANGE_FORMULA
            assert row.rank_change.lineage.peer_observation_ids
            assert row.observation.source == SSB_06831
            for derived_col in row.derived_columns():
                assert derived_col.lineage.name
                assert derived_col.lineage.formula
                assert derived_col.lineage.source_observation_ids
                assert derived_col.lineage.source_periods

    young_2022 = by_key[(SSB_06831_ENTITY_16, "2022")]
    older_2022 = by_key[(SSB_06831_ENTITY_20, "2022")]
    assert young_2022.yoy_growth.value == pytest.approx((2 - 3) / 3)
    assert older_2022.yoy_growth.value == pytest.approx((23 - 23) / 23)
    assert young_2022.index.value == pytest.approx(100.0 * 2 / 3)
    assert older_2022.index.value == pytest.approx(100.0)
    assert by_key[(SSB_06831_ENTITY_20, "2021")].rank.value == 1
    assert by_key[(SSB_06831_ENTITY_16, "2021")].rank.value == 2

    bars = yoy_bar_points(derived)
    assert len(bars) == 2
    assert {period for period, _rate in bars} == {"2022"}
    plotted = index_line_series(derived)
    assert len(plotted) == 2
    for _entity, _measure, points in plotted:
        assert [period for period, _value in points] == ["2021", "2022"]
        assert points[0][1] == 100.0


def test_ssb06831_cli_reads_store_and_does_not_fetch(tmp_path: Path) -> None:
    from public_data_agent.models import HarvestCounts
    from public_data_agent.registry import Registry

    from methods.cli import run as run_methods
    import methods.cli as methods_cli

    dump = json.loads(SSB_06831_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    db = tmp_path / "registry.sqlite"
    registry = Registry(db)
    registry.ensure_observation_dataset(
        dataset_id=SSB_06831,
        title="06831: Andel personer (prosent), etter samlivsform, kjønn, alder, statistikkvariabel og år",
        publisher_name="Statistisk sentralbyrå",
        access_path="https://data.ssb.no/api/v0/no/table/06831",
        license=None,
    )
    run_id = registry.start_fetch_run(
        dataset_id=SSB_06831,
        table_id="06831",
        request_url="https://data.ssb.no/api/v0/no/table/06831",
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
    stored = registry.list_observations(SSB_06831)
    registry.close()
    assert len(stored) == 4

    fetch_calls: list[object] = []

    def _forbid_fetch(*_args, **_kwargs):
        fetch_calls.append((_args, _kwargs))
        raise AssertionError("pda fetch must not run for ssb:06831")

    original = methods_cli._call_existing_fetch
    methods_cli._call_existing_fetch = _forbid_fetch
    try:
        derived = run_methods(
            dataset_id=SSB_06831,
            db=db,
            out=tmp_path / "out",
            table_id="06831",
            from_year=2021,
            to_year=2022,
            entity="Oslo (Kristiania og Aker) i alt",
            measure="Folkemengden i alt (antall personer)",
        )
    finally:
        methods_cli._call_existing_fetch = original
    assert fetch_calls == []
    assert len(derived) == 4
    assert {row.observation.period for row in derived} == {"2021", "2022"}
    assert {row.observation.entity for row in derived} == {
        SSB_06831_ENTITY_16,
        SSB_06831_ENTITY_20,
    }
    assert all(row.observation.source == SSB_06831 for row in derived)
    by_id = {row["id"]: _numeric_value(row) for row in stored}
    for row in derived:
        assert row.observation.value == float(by_id[row.observation.id])
        assert row.yoy_growth.lineage.formula == YOY_GROWTH_FORMULA
        assert row.index.lineage.formula == INDEX_FORMULA
        assert row.rank.lineage.formula == RANK_FORMULA
        assert row.rank_change.lineage.formula == RANK_CHANGE_FORMULA


def test_ssb06831_empty_store_does_not_post() -> None:
    from methods.cli import run as run_methods
    import methods.cli as methods_cli

    fetch_calls: list[object] = []

    def _forbid_fetch(*_args, **_kwargs):
        fetch_calls.append((_args, _kwargs))
        raise AssertionError("pda fetch must not run for ssb:06831")

    original = methods_cli._call_existing_fetch
    methods_cli._call_existing_fetch = _forbid_fetch
    try:
        with pytest.raises(ValueError, match="refusing to call pda fetch"):
            run_methods(
                dataset_id=SSB_06831,
                db=Path("data/missing-registry-06831.sqlite"),
                out=Path("/tmp/methods-06831-empty"),
                table_id="06831",
                from_year=2021,
                to_year=2022,
                entity=None,
                measure=None,
            )
    finally:
        methods_cli._call_existing_fetch = original
    assert fetch_calls == []


def test_committed_ssb06831_proof_artifacts() -> None:
    csv_path = SSB_06831_PROOF_DIR / "table.csv"
    md_path = SSB_06831_PROOF_DIR / "table.md"
    lineage_path = SSB_06831_PROOF_DIR / "lineage.json"
    chart_path = SSB_06831_PROOF_DIR / "chart.png"
    bar_path = SSB_06831_PROOF_DIR / "yoy_bar.png"
    index_path = SSB_06831_PROOF_DIR / "index_line.png"
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
    assert "ssb:06831" not in oslo
    ssb11763 = (SSB_PROOF_DIR / "table.csv").read_text(encoding="utf-8")
    assert "ssb:11763" in ssb11763
    assert "ssb:06831" not in ssb11763
    ssb06683 = (SSB_06683_PROOF_DIR / "table.csv").read_text(encoding="utf-8")
    assert "ssb:06683" in ssb06683
    assert "ssb:06831" not in ssb06683

    with csv_path.open(encoding="utf-8", newline="") as handle:
        table = list(csv.DictReader(handle))
    assert len(table) == 4
    entities = {row["entity"] for row in table}
    periods = {row["period"] for row in table}
    assert entities == {SSB_06831_ENTITY_16, SSB_06831_ENTITY_20}
    assert periods == {"2021", "2022"}
    by_key = {(row["entity"], row["period"]): row for row in table}
    for entity in entities:
        base = by_key[(entity, "2021")]
        latest = by_key[(entity, "2022")]
        assert base["yoy_growth"] == ""
        assert float(base["index"]) == 100.0
        previous = float(base["value"])
        current = float(latest["value"])
        assert previous == SSB_06831_VALUES[(entity, "2021")]
        assert current == SSB_06831_VALUES[(entity, "2022")]
        assert float(latest["yoy_growth"]) == pytest.approx((current - previous) / previous)
        assert float(latest["index"]) == pytest.approx(100.0 * current / previous)
        assert latest["source"] == SSB_06831
        assert base["source"] == SSB_06831
        assert base["rank_change"] == ""
        assert float(latest["rank_change"]) == pytest.approx(float(base["rank"]) - float(latest["rank"]))

    assert float(by_key[(SSB_06831_ENTITY_16, "2022")]["yoy_growth"]) == pytest.approx((2 - 3) / 3)
    assert float(by_key[(SSB_06831_ENTITY_20, "2022")]["yoy_growth"]) == pytest.approx(0.0)
    assert float(by_key[(SSB_06831_ENTITY_20, "2021")]["rank"]) == 1

    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
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
    assert len(yoy["rows"]) == 4
    assert len(index["rows"]) == 4
    assert len(rank["rows"]) == 4
    assert len(rank_change["rows"]) == 4
    for item in yoy["rows"]:
        assert item["lineage"]["name"] == YOY_GROWTH
        assert item["lineage"]["formula"] == YOY_GROWTH_FORMULA
        assert item["lineage"]["input_columns"] == ["value"]
        assert item["lineage"]["source_observation_ids"]
        assert item["lineage"]["source_periods"]
        if item["period"] == "2021":
            assert item["value"] is None
            assert item["lineage"]["note"] == "undefined: no prior period"
        else:
            assert item["value"] is not None
    for item in index["rows"]:
        assert item["lineage"]["name"] == INDEX
        assert item["lineage"]["formula"] == INDEX_FORMULA
        assert item["lineage"]["base_period"] == "2021"
        assert item["lineage"]["source_observation_ids"]
        assert item["lineage"]["source_periods"]
        if item["value"] is not None:
            assert item["lineage"]["base_observation_id"]
        if item["period"] == "2021":
            assert item["value"] == 100.0
    for item in rank["rows"]:
        assert item["lineage"]["name"] == RANK
        assert item["lineage"]["formula"] == RANK_FORMULA
        assert item["lineage"]["peer_observation_ids"]
        assert len(item["lineage"]["peer_observation_ids"]) == 2
        assert item["value"] is not None
    for item in rank_change["rows"]:
        assert item["lineage"]["name"] == RANK_CHANGE
        assert item["lineage"]["formula"] == RANK_CHANGE_FORMULA
        assert item["lineage"]["peer_observation_ids"]
        if item["period"] == "2021":
            assert item["value"] is None
        else:
            assert item["value"] is not None
    md = md_path.read_text(encoding="utf-8")
    assert YOY_GROWTH_FORMULA in md
    assert INDEX_FORMULA in md
    assert RANK_FORMULA in md
    assert RANK_CHANGE_FORMULA in md
    dump = json.loads(SSB_06831_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    assert dump["counts"]["total"] == 4
    assert dump["counts"]["numeric"] == 4
    committed = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "ssb_expand_proof.json").read_text(
            encoding="utf-8"
        )
    )
    printed = {
        (
            item["dimensions"]["Alder"],
            item["dimensions"]["Kjonn"],
            item["dimensions"]["Samboere"],
            item["dimensions"]["Tid"],
        ): item["value"]
        for item in committed["fetch"]["sample"]
    }
    assert printed == {
        ("16-19 år", "Kvinner", "Samboere", "2021"): 3,
        ("16-19 år", "Kvinner", "Samboere", "2022"): 2,
        ("20-24 år", "Kvinner", "Samboere", "2021"): 23,
        ("20-24 år", "Kvinner", "Samboere", "2022"): 23,
    }
    assert committed["fetch"]["listed"] == 132


STORMFLO_NATIONAL = "stormflo:national.json"
STORMFLO_PROOF_DIR = Path(__file__).resolve().parents[1] / "methods" / "proof" / "stormflo_national"
STORMFLO_STORE = STORMFLO_PROOF_DIR / "store.json"
STORMFLO_URL = "https://stormflo-konsekvens.kartverket.no/public/api/v1/national.json"
STORMFLO_PROOF_JSON = Path(__file__).resolve().parents[1] / "data" / "stormflo_source_proof.json"
TWO_PERIOD_CODES = frozenset({"200ymax", "1000ymax", "20ymax"})
THREE_PERIOD_CODES = frozenset({"mhw", "highendwl"})


def _printed_stormflo_cells() -> dict[tuple[str, str, str], float]:
    payload = json.loads(STORMFLO_PROOF_JSON.read_text(encoding="utf-8"))
    cells = payload["printed_samples"]["cells"]
    out: dict[tuple[str, str, str], float] = {}
    for code, years in cells.items():
        for year, record in years.items():
            for measure, value in record.items():
                out[(str(code), str(year), str(measure))] = float(value)
    return out


def _stormflo_stored_rows() -> list[dict]:
    # The committed store, not the live registry. The proof's printed cells were
    # produced on 2026-08-28 alongside this store, so the two are one fetch.
    # The live registry was re-fetched on 2026-09-14, after Kartverket revised
    # 67 of the 168 cells (median 0.03%, at most 3.3%), and comparing a live
    # store with an older proof fails on the publisher's revision rather than on
    # the formula or lineage this test exists to check. A live comparison needs
    # a proof from the same fetch; stormflo_national_proof.json carries only a
    # sample, not all 168 printed cells.
    if not STORMFLO_STORE.is_file():
        pytest.skip("no stored stormflo:national.json rows")
    dump = json.loads(STORMFLO_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    return dump["rows"]


def test_live_stormflo_store_matches_formula_and_lineage() -> None:
    printed = _printed_stormflo_cells()
    assert len(printed) == 168
    stored = _stormflo_stored_rows()
    assert len(stored) == 168
    assert len([row for row in stored if _numeric_value(row) is not None]) == 168

    cleaned = clean(stored)
    assert len(cleaned) == 168
    assert {row.entity for row in cleaned} == TWO_PERIOD_CODES | THREE_PERIOD_CODES
    assert {row.period for row in cleaned} == {"2025", "2100", "2150"}
    cleaned_keys = {
        (row.entity, row.period, row.measure): row.value for row in cleaned
    }
    assert cleaned_keys == printed
    assert all(row.source == STORMFLO_NATIONAL for row in cleaned)

    by_code = {code: {row.period for row in cleaned if row.entity == code} for code in TWO_PERIOD_CODES | THREE_PERIOD_CODES}
    for code in TWO_PERIOD_CODES:
        assert by_code[code] == {"2025", "2100"}
    for code in THREE_PERIOD_CODES:
        assert by_code[code] == {"2025", "2100", "2150"}

    derived = derive(cleaned)
    assert len(derived) == 168
    by_key = {
        (row.observation.entity, row.observation.measure, row.observation.period): row
        for row in derived
    }
    for (code, year, measure), value in printed.items():
        row = by_key[(code, measure, year)]
        assert row.observation.value == value
        assert row.yoy_growth.value is None
        assert row.yoy_growth.lineage.name == YOY_GROWTH
        assert row.period_change.lineage.name == PERIOD_CHANGE
        assert row.period_change.lineage.formula == PERIOD_CHANGE_FORMULA
        assert row.index.lineage.formula == INDEX_FORMULA
        for derived_col in row.derived_columns():
            assert derived_col.lineage.source_observation_ids
            assert derived_col.lineage.source_periods

    two = by_key[("200ymax", "offentlige_bygg", "2025")]
    two_next = by_key[("200ymax", "offentlige_bygg", "2100")]
    assert two.observation.value == 1810
    assert two_next.observation.value == 4176
    assert two.index.value == 100.0
    assert two.period_change.value is None
    assert two_next.index.value == pytest.approx(100.0 * 4176 / 1810)
    assert two_next.period_change.value == pytest.approx((4176 - 1810) / 1810)
    assert two_next.period_change.lineage.source_periods == ("2025", "2100")
    assert two_next.yoy_growth.lineage.note == "undefined: periods are not adjacent calendar years"
    assert ("200ymax", "offentlige_bygg", "2150") not in by_key

    mhw_2025 = by_key[("mhw", "offentlige_bygg", "2025")]
    mhw_2100 = by_key[("mhw", "offentlige_bygg", "2100")]
    mhw_2150 = by_key[("mhw", "offentlige_bygg", "2150")]
    assert mhw_2025.observation.value == 583
    assert mhw_2100.observation.value == 956
    assert mhw_2150.observation.value == 1844
    assert mhw_2025.index.value == 100.0
    assert mhw_2100.index.value == pytest.approx(100.0 * 956 / 583)
    assert mhw_2150.index.value == pytest.approx(100.0 * 1844 / 583)
    assert mhw_2100.period_change.value == pytest.approx((956 - 583) / 583)
    assert mhw_2150.period_change.value == pytest.approx((1844 - 956) / 956)
    assert mhw_2100.period_change.lineage.source_periods == ("2025", "2100")
    assert mhw_2150.period_change.lineage.source_periods == ("2100", "2150")

    committed = json.loads(STORMFLO_PROOF_JSON.read_text(encoding="utf-8"))
    assert committed["fetch"]["listed"] == 168
    assert committed["printed_samples"]["copied_not_invented"] is True


def test_stormflo_cli_reads_store_and_does_not_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from public_data_agent.models import HarvestCounts
    from public_data_agent.registry import Registry

    from methods.cli import run as run_methods
    import methods.cli as methods_cli

    dump = json.loads(STORMFLO_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    printed = _printed_stormflo_cells()
    db = tmp_path / "registry.sqlite"
    registry = Registry(db)
    registry.ensure_observation_dataset(
        dataset_id=STORMFLO_NATIONAL,
        title="Stormflo national",
        publisher_name=None,
        access_path=STORMFLO_URL,
        license="https://www.apache.org/licenses/LICENSE-2.0.html",
    )
    run_id = registry.start_fetch_run(
        dataset_id=STORMFLO_NATIONAL,
        table_id="national.json",
        request_url=STORMFLO_URL,
        request_method="SEED",
    )
    for stored_row in dump["rows"]:
        registry.upsert_observation(stored_row, run_id)
    registry.finish_fetch_run(
        run_id,
        HarvestCounts(listed=len(dump["rows"]), inserted=len(dump["rows"])),
        status="completed",
        http_status=200,
    )
    stored = registry.list_observations(STORMFLO_NATIONAL)
    registry.close()
    assert len(stored) == 168

    fetch_calls: list[object] = []

    def _forbid_fetch(*args, **kwargs):
        fetch_calls.append((args, kwargs))
        raise AssertionError("pda fetch must not run for stormflo:national.json")

    monkeypatch.setattr(methods_cli, "_call_existing_fetch", _forbid_fetch)
    out = tmp_path / "out"
    derived = run_methods(
        dataset_id=STORMFLO_NATIONAL,
        db=db,
        out=out,
        table_id="national.json",
        from_year=None,
        to_year=None,
        entity=None,
        measure=None,
    )

    assert fetch_calls == []
    assert len(derived) == 168
    got = {
        (row.observation.entity, row.observation.period, row.observation.measure): row.observation.value
        for row in derived
    }
    assert got == printed
    assert all(row.yoy_growth.value is None for row in derived)
    assert (out / "chart.png").is_file()
    assert (out / "index_line.png").is_file()
    assert not (out / "yoy_bar.png").exists()


def test_stormflo_empty_store_does_not_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from methods.cli import run as run_methods
    import methods.cli as methods_cli

    fetch_calls: list[object] = []

    def _forbid_fetch(*args, **kwargs):
        fetch_calls.append((args, kwargs))
        raise AssertionError("pda fetch must not run for stormflo:national.json")

    monkeypatch.setattr(methods_cli, "_call_existing_fetch", _forbid_fetch)
    with pytest.raises(ValueError, match="refusing to call pda fetch"):
        run_methods(
            dataset_id=STORMFLO_NATIONAL,
            db=tmp_path / "missing-registry.sqlite",
            out=tmp_path / "empty",
            table_id="national.json",
            from_year=None,
            to_year=None,
            entity=None,
            measure=None,
        )
    assert fetch_calls == []


def test_committed_stormflo_proof_artifacts() -> None:
    csv_path = STORMFLO_PROOF_DIR / "table.csv"
    md_path = STORMFLO_PROOF_DIR / "table.md"
    lineage_path = STORMFLO_PROOF_DIR / "lineage.json"
    chart_path = STORMFLO_PROOF_DIR / "chart.png"
    index_path = STORMFLO_PROOF_DIR / "index_line.png"
    assert csv_path.is_file()
    assert md_path.is_file()
    assert lineage_path.is_file()
    assert chart_path.read_bytes().startswith(b"\x89PNG")
    assert index_path.read_bytes().startswith(b"\x89PNG")
    assert not (STORMFLO_PROOF_DIR / "yoy_bar.png").exists()

    printed = _printed_stormflo_cells()
    with csv_path.open(encoding="utf-8", newline="") as handle:
        table = list(csv.DictReader(handle))
    assert len(table) == 168
    table_keys = {
        (row["entity"], row["period"], row["measure"]): float(row["value"]) for row in table
    }
    assert table_keys == printed
    assert all(row["yoy_growth"] == "" for row in table)
    two_period_2150 = [
        row for row in table if row["entity"] in TWO_PERIOD_CODES and row["period"] == "2150"
    ]
    assert two_period_2150 == []

    bygg_2025 = next(
        row
        for row in table
        if row["entity"] == "200ymax" and row["measure"] == "offentlige_bygg" and row["period"] == "2025"
    )
    bygg_2100 = next(
        row
        for row in table
        if row["entity"] == "200ymax" and row["measure"] == "offentlige_bygg" and row["period"] == "2100"
    )
    assert float(bygg_2025["index"]) == 100.0
    assert bygg_2025["period_change"] == ""
    assert float(bygg_2100["period_change"]) == pytest.approx((4176 - 1810) / 1810)
    assert float(bygg_2100["index"]) == pytest.approx(100.0 * 4176 / 1810)

    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    names = [column["name"] for column in lineage["derived_columns"]]
    assert names == [YOY_GROWTH, PERIOD_CHANGE, INDEX, RANK, RANK_CHANGE]
    by_name = {column["name"]: column for column in lineage["derived_columns"]}
    assert by_name[YOY_GROWTH]["formula"] == YOY_GROWTH_FORMULA
    assert by_name[PERIOD_CHANGE]["formula"] == PERIOD_CHANGE_FORMULA
    assert by_name[INDEX]["formula"] == INDEX_FORMULA

    markdown = md_path.read_text(encoding="utf-8")
    assert PERIOD_CHANGE_FORMULA in markdown
    assert "`period_change` describes the stored step. It is not a one-year rate." in markdown
    dump = json.loads(STORMFLO_STORE.read_text(encoding="utf-8"))
    assert dump["posted"] is False
    assert dump["counts"]["total"] == 168
    assert dump["counts"]["numeric"] == 168
    assert dump["counts"]["entities"] == 5
    assert dump["counts"]["periods"] == ["2025", "2100", "2150"]
    assert dump["seeded_from"]["main_merge"] == "ca8f749"
    assert dump["seeded_from"]["pr"] == 191
    assert "no GET or POST" in dump["seeded_from"]["note"]
    assert "NATIONAL_BODY" in dump["seeded_from"]["note"]
    store_keys = {
        (row["dimensions"]["code"], row["dimensions"]["year"], row["measure"]): float(row["value"])
        for row in dump["rows"]
    }
    assert store_keys == printed
