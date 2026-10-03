"""Discovering a capability nothing had declared.

3,232 datasets on 2026-10-03 had an access_path a connector recognises and no
capability row, so the lane that returns data left them out although a fetch
would have worked. Some fetch branches store cells without recording a
capability -- kikommuner:3419 held an observation and no capability because of
it -- so discovery writes the record its own fetch demonstrated.

The evidence is the cells that came back: nothing is written when none did.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from public_data_agent.models import HarvestCounts
from public_data_agent.registry import Registry
from public_data_agent.verify import discoverable, record_evidence, verify_capabilities


@dataclass
class _Result:
    counts: HarvestCounts


def _dataset(registry: Registry, dataset_id: str, access_path: str) -> None:
    registry.ensure_observation_dataset(
        dataset_id=dataset_id, title=dataset_id, publisher_name="p",
        access_path=access_path, license=None,
    )
    registry.conn.commit()


FETCHABLE = "https://api.kartverket.no/kommuneinfo/v1/kommuner/3419"


def test_a_dataset_a_connector_can_fetch_is_discoverable(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:known", FETCHABLE)
        assert [d for d, _s in discoverable(registry)] == ["fixture:known"]
    finally:
        registry.close()


def test_a_dataset_no_connector_recognises_is_not(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:unknown", "https://example.invalid/whatever")
        assert discoverable(registry) == []
    finally:
        registry.close()


def test_a_dataset_that_already_declares_a_capability_is_not_rediscovered(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:declared", FETCHABLE)
        registry.set_capability("fixture:declared", {
            "capability": "observations", "record_kind": "observation",
            "endpoint": FETCHABLE,
        })
        registry.conn.commit()
        assert discoverable(registry) == []
    finally:
        registry.close()


def test_the_sample_count_recorded_is_the_cells_that_came_back(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:got", FETCHABLE)
        counts = HarvestCounts()
        counts.listed = 7
        assert record_evidence(registry, "fixture:got", _Result(counts)) is True
        capability = registry.get_capability("fixture:got")
        assert capability["capability"] == "observations"
        assert capability["verified_sample_count"] == 7
        assert capability["verified_at"]
    finally:
        registry.close()


def test_a_fetch_that_returned_nothing_declares_nothing(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:empty", FETCHABLE)
        # HTTP 200 and no cells is not evidence that a resource answers.
        assert record_evidence(registry, "fixture:empty", _Result(HarvestCounts())) is False
        assert registry.get_capability("fixture:empty") is None
    finally:
        registry.close()


def test_an_existing_capability_is_never_overwritten(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:has", FETCHABLE)
        registry.set_capability("fixture:has", {
            "capability": "lookup", "record_kind": "entity", "endpoint": FETCHABLE,
            "verified_at": "2026-01-01T00:00:00Z", "verified_sample_count": 1,
        })
        registry.conn.commit()
        counts = HarvestCounts()
        counts.listed = 99
        assert record_evidence(registry, "fixture:has", _Result(counts)) is False
        assert registry.get_capability("fixture:has")["capability"] == "lookup"
    finally:
        registry.close()


def test_discovery_counts_what_it_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:a", FETCHABLE)

        def _one_cell(*_args: object, **_kwargs: object) -> _Result:
            counts = HarvestCounts()
            counts.listed = 1
            return _Result(counts)

        monkeypatch.setattr("public_data_agent.verify.fetch_observations", _one_cell)
        got = verify_capabilities(registry, discover=True)
        assert (got.probed, got.verified, got.declared) == (1, 1, 1)
        assert registry.get_capability("fixture:a")["verified_sample_count"] == 1
    finally:
        registry.close()


def test_without_discovery_an_undeclared_dataset_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:b", FETCHABLE)
        monkeypatch.setattr(
            "public_data_agent.verify.fetch_observations",
            lambda *a, **k: pytest.fail("nothing should be fetched"),
        )
        got = verify_capabilities(registry)
        assert (got.probed, got.declared) == (0, 0)
        assert registry.get_capability("fixture:b") is None
    finally:
        registry.close()


def test_a_capability_that_was_never_verified_gets_its_evidence(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:claimed", FETCHABLE)
        registry.set_capability("fixture:claimed", {
            "capability": "observations", "record_kind": "observation",
            "endpoint": FETCHABLE, "subject_scheme": "kommune",
            "subject_template": "https://example.invalid/{subject}",
        })
        registry.conn.commit()
        counts = HarvestCounts()
        counts.listed = 4
        assert record_evidence(registry, "fixture:claimed", _Result(counts)) is True
        capability = registry.get_capability("fixture:claimed")
        assert capability["verified_sample_count"] == 4
        # set_capability replaces every column, so the rest of the row has to
        # survive the merge or the endpoint and addressing are erased.
        assert capability["endpoint"] == FETCHABLE
        assert capability["subject_scheme"] == "kommune"
        assert capability["subject_template"] == "https://example.invalid/{subject}"
        assert capability["record_kind"] == "observation"
    finally:
        registry.close()


def test_a_lookup_capability_keeps_its_kind_when_verified(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:lookup", FETCHABLE)
        registry.set_capability("fixture:lookup", {
            "capability": "lookup", "record_kind": "entity", "endpoint": FETCHABLE,
        })
        registry.conn.commit()
        counts = HarvestCounts()
        counts.listed = 1
        assert record_evidence(registry, "fixture:lookup", _Result(counts)) is True
        capability = registry.get_capability("fixture:lookup")
        assert (capability["capability"], capability["record_kind"]) == ("lookup", "entity")
    finally:
        registry.close()
