"""Probing a declared capability, bounded, and classifying what came back.

A capability read from metadata is a claim. Of 5,157 declared on 2026-10-03,
578 were verified; a sample of 122 fetched 118, so the claims were good, but
those probes wrote 1.73 million cells. A probe therefore asks for one period
under a cell budget, and "answered with more than we will store" is reported
apart from "did not work".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.registry import Registry
from public_data_agent.verify import latest_period_year, unverified, verify_capabilities


def _dataset_with_period(registry: Registry, dataset_id: str, years: list[str],
                         *, verified: bool = False) -> None:
    registry.ensure_observation_dataset(
        dataset_id=dataset_id, title=dataset_id, publisher_name="p",
        access_path=f"https://example.invalid/{dataset_id.replace(':', '-')}", license=None,
    )
    registry.conn.execute(
        "INSERT INTO resource_fields (dataset_id, field_code, field_label, field_role,"
        " value_count, position) VALUES (?, 'Tid', 'år', 'period', ?, 0)",
        (dataset_id, len(years)),
    )
    for year in years:
        registry.conn.execute(
            "INSERT INTO resource_field_values (dataset_id, field_code, value_code,"
            " value_label) VALUES (?, 'Tid', ?, ?)",
            (dataset_id, year, year),
        )
    registry.set_capability(dataset_id, {
        "capability": "observations",
        "record_kind": "observation",
        "endpoint": f"https://example.invalid/{dataset_id.replace(':', '-')}",
        **({"verified_at": "2026-01-01T00:00:00Z", "verified_sample_count": 1} if verified else {}),
    })
    registry.conn.commit()


def test_the_latest_published_period_is_read_not_assumed(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset_with_period(registry, "fixture:old", ["2008", "2009", "2010"])
        # A table that ended in 2010 answers a request for this year with
        # nothing, which looks exactly like a broken capability.
        assert latest_period_year(registry, "fixture:old") == 2010
    finally:
        registry.close()


def test_a_dataset_already_verified_is_not_probed_again(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset_with_period(registry, "fixture:done", ["2024"], verified=True)
        _dataset_with_period(registry, "fixture:todo", ["2024"])
        assert [d for d, _s in unverified(registry)] == ["fixture:todo"]
    finally:
        registry.close()


def test_a_resource_with_no_recorded_period_is_probed_anyway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        registry.ensure_observation_dataset(
            dataset_id="fixture:bare", title="t", publisher_name="p",
            access_path="https://example.invalid/bare", license=None,
        )
        registry.set_capability("fixture:bare", {
            "capability": "observations", "record_kind": "observation",
            "endpoint": "https://example.invalid/bare",
        })
        registry.conn.commit()
        seen: dict[str, object] = {}

        def _record(_registry: object, dataset_id: str, **kwargs: object) -> object:
            seen.update(dataset=dataset_id, **kwargs)
            return object()

        monkeypatch.setattr("public_data_agent.verify.fetch_observations", _record)
        counts = verify_capabilities(registry)
        # NVDB road objects are not a time series; skipping them left a sample
        # of 100 entirely unprobed. The cell budget is what protects the disk.
        assert (counts.probed, counts.verified, counts.no_period) == (1, 1, 1)
        assert seen["from_year"] is None and seen["to_year"] is None
    finally:
        registry.close()


def test_the_sources_own_size_limit_is_not_a_broken_capability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset_with_period(registry, "fixture:huge", ["2024"])

        def _selection_too_large(*_args: object, **_kwargs: object) -> object:
            raise ValueError(
                "SelectionTooLarge: selection is 174,636,000 cells, over the "
                "800,000 limit for table 11087"
            )

        monkeypatch.setattr("public_data_agent.verify.fetch_observations", _selection_too_large)
        counts = verify_capabilities(registry)
        assert (counts.too_large, counts.failed) == (1, 0)
        assert counts.errors == []
    finally:
        registry.close()


def test_over_the_budget_is_reported_apart_from_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset_with_period(registry, "fixture:big", ["2024"])

        def _too_large(*_args: object, **_kwargs: object) -> object:
            raise ValueError("fixture:big table t returned 9000 cells, over the "
                             "200-cell budget for this request; nothing was stored.")

        monkeypatch.setattr("public_data_agent.verify.fetch_observations", _too_large)
        counts = verify_capabilities(registry)
        assert (counts.too_large, counts.failed, counts.verified) == (1, 0, 0)
        assert counts.errors == []
    finally:
        registry.close()


def test_a_real_failure_is_recorded_with_its_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset_with_period(registry, "fixture:broken", ["2024"])

        def _boom(*_args: object, **_kwargs: object) -> object:
            raise ValueError("HTTP 500 for https://example.invalid/x")

        monkeypatch.setattr("public_data_agent.verify.fetch_observations", _boom)
        counts = verify_capabilities(registry)
        assert (counts.failed, counts.verified) == (1, 0)
        assert counts.errors[0]["dataset"] == "fixture:broken"
        assert "HTTP 500" in counts.errors[0]["error"]
    finally:
        registry.close()


def test_the_probe_asks_for_the_tables_own_year_under_a_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset_with_period(registry, "fixture:ok", ["2019", "2020"])
        seen: dict[str, object] = {}

        def _record(_registry: object, dataset_id: str, **kwargs: object) -> object:
            seen.update(dataset=dataset_id, **kwargs)
            return object()

        monkeypatch.setattr("public_data_agent.verify.fetch_observations", _record)
        counts = verify_capabilities(registry, max_cells=50)
        assert counts.verified == 1
        assert seen["from_year"] == 2020 and seen["to_year"] == 2020
        assert seen["max_cells"] == 50
    finally:
        registry.close()


def test_a_sample_is_reproducible_for_a_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        for index in range(8):
            _dataset_with_period(registry, f"fixture:d{index}", ["2024"])
        probed: list[list[str]] = []

        def _note(_registry: object, dataset_id: str, **_kwargs: object) -> object:
            probed[-1].append(dataset_id)
            return object()

        monkeypatch.setattr("public_data_agent.verify.fetch_observations", _note)
        for _ in range(2):
            probed.append([])
            verify_capabilities(registry, sample=3, seed=7)
        assert probed[0] == probed[1]
        assert len(probed[0]) == 3
    finally:
        registry.close()


def _attribute_field(registry: Registry, dataset_id: str, code: str,
                     values: list[str], position: int) -> None:
    registry.conn.execute(
        "INSERT INTO resource_fields (dataset_id, field_code, field_label, field_role,"
        " value_count, position) VALUES (?, ?, ?, 'attribute', ?, ?)",
        (dataset_id, code, code.lower(), len(values), position),
    )
    for value in values:
        registry.conn.execute(
            "INSERT INTO resource_field_values (dataset_id, field_code, value_code,"
            " value_label) VALUES (?, ?, ?, ?)",
            (dataset_id, code, value, f"{code} {value}"),
        )
    registry.conn.commit()


def test_one_value_of_every_dimension_is_pinned(tmp_path: Path) -> None:
    from public_data_agent.verify import narrowing_select

    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset_with_period(registry, "fixture:wide", ["2024"])
        _attribute_field(registry, "fixture:wide", "Kjonn", ["0", "1", "2"], 1)
        _attribute_field(registry, "fixture:wide", "Yrke", ["0-9", "1", "2"], 2)
        # One measure of one year is still the cross-product of everything
        # else; 11418 is thousands of cells whole and seven pinned this way.
        assert narrowing_select(registry, "fixture:wide") == {
            "Kjonn": ["0"], "Yrke": ["0-9"],
        }
    finally:
        registry.close()


def test_the_period_and_measure_are_not_pinned(tmp_path: Path) -> None:
    from public_data_agent.verify import narrowing_select

    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset_with_period(registry, "fixture:plain", ["2023", "2024"])
        # The period is bounded by from_year/to_year and the measure by
        # `measure=`; pinning them here would fight those.
        assert narrowing_select(registry, "fixture:plain") == {}
    finally:
        registry.close()


def test_a_combination_with_no_cell_is_retried_without_the_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset_with_period(registry, "fixture:sparse", ["2024"])
        _attribute_field(registry, "fixture:sparse", "Kjonn", ["0", "1"], 1)
        calls: list[object] = []

        def _empty_when_narrowed(_registry: object, _dataset_id: str, **kwargs: object) -> object:
            calls.append(kwargs.get("select"))
            if kwargs.get("select"):
                raise ValueError("no data for the requested selection")
            return object()

        monkeypatch.setattr("public_data_agent.verify.fetch_observations", _empty_when_narrowed)
        counts = verify_capabilities(registry)
        # A combination the resource holds no cell for is not a resource that
        # cannot be fetched.
        assert (counts.verified, counts.failed, counts.retried_wide) == (1, 0, 1)
        assert calls == [{"Kjonn": ["0"]}, None]
    finally:
        registry.close()
