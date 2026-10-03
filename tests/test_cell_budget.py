"""One request may be told how many cells it is allowed to store.

Connectors carry their own caps for shapes whose size is known in advance.
This is the caller's bound for any fetch: verifying a capability is cheap to
ask for and expensive to store. Probing 122 datasets on 2026-10-03 with only a
year bound wrote 1.73 million cells and took the registry from 406 MB to
1.9 GB, one table contributing 792,990 of them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.fetch import _store_cells, cell_budget
from public_data_agent.models import HarvestCounts
from public_data_agent.registry import Registry

CELLS = [("Personer", 1.0, {"ar": "2024"}), ("Personer", 2.0, {"ar": "2025"})]


def _dataset(registry: Registry) -> dict[str, object]:
    registry.ensure_observation_dataset(
        dataset_id="fixture:t", title="T", publisher_name="p",
        access_path="https://example.invalid/t", license=None,
    )
    return dict(registry.get_dataset("fixture:t"))


def _store(registry: Registry, dataset: dict[str, object]) -> HarvestCounts:
    counts = HarvestCounts()
    run_id = registry.start_fetch_run(
        dataset_id="fixture:t", table_id="t",
        request_url="https://example.invalid/t", request_method="GET",
    )
    _store_cells(
        registry, dataset, run_id, table_id="t", cells=CELLS,
        retrieved_at="2026-10-03T00:00:00Z",
        request_url="https://example.invalid/t", http_status=200, counts=counts,
    )
    return counts


def test_a_response_within_the_budget_is_stored(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        dataset = _dataset(registry)
        with cell_budget(2):
            counts = _store(registry, dataset)
        assert counts.inserted == 2
        assert len(registry.list_observations("fixture:t")) == 2
    finally:
        registry.close()


def test_a_response_over_the_budget_stores_nothing(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        dataset = _dataset(registry)
        # Not the first cell, not a truncated table: a partial answer reported
        # as success is worse than no answer.
        with pytest.raises(ValueError, match="returned 2 cells, over the 1-cell budget"):
            with cell_budget(1):
                _store(registry, dataset)
        assert registry.list_observations("fixture:t") == []
    finally:
        registry.close()


def test_the_error_says_how_to_narrow_the_request(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        dataset = _dataset(registry)
        with pytest.raises(ValueError, match="one year, one region, one measure"):
            with cell_budget(1):
                _store(registry, dataset)
    finally:
        registry.close()


def test_without_a_budget_nothing_is_refused(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        dataset = _dataset(registry)
        counts = _store(registry, dataset)
        assert counts.inserted == 2
    finally:
        registry.close()


def test_the_budget_does_not_leak_out_of_its_block(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        dataset = _dataset(registry)
        with pytest.raises(ValueError):
            with cell_budget(1):
                _store(registry, dataset)
        # The next fetch is unbounded again, so one refusal does not silently
        # cap everything that follows.
        assert _store(registry, dataset).inserted == 2
    finally:
        registry.close()
