"""Fetching road features from NVDB.

The thing worth holding still: "fetch this type" must never mean "fetch all of
it". Type 5 holds 245,616 guardrails, so a collection request is a bounded page
and an unbounded one is refused rather than quietly truncated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.fetch import (
    CAPABILITY_FEATURES,
    SelectionTooLarge,
    classify_access_path,
    fetch_observations,
)
from public_data_agent.registry import Registry
from public_data_agent.sources.nvdb import OBJECT_API, feature_from_vegobjekt

BRIDGE = {
    "id": 272296863,
    "metadata": {"type": {"id": 60, "navn": "Bru"}},
    "egenskaper": [
        {"navn": "Byggverkstype", "verdi": "Hvelvbru (562)"},
        {"navn": "Eier", "verdi": "Fylkeskommune"},
        {"navn": None, "verdi": "dropped"},
    ],
    "lokasjon": {
        "geometri": {"wkt": "LINESTRING Z (284734.193 6579669.92 35.053)"},
        "kommuner": [3105],
        "fylker": [31],
        "lengde": 22.95,
    },
}


class FakeResponse:
    def __init__(self, status, body):
        self.status, self.body = status, body


class FakeHttp:
    def __init__(self, body, status=200):
        self.body, self.status, self.urls = body, status, []

    def get_json_response(self, url, headers=None):
        self.urls.append(url)
        return FakeResponse(self.status, self.body)

    def get_json(self, url, headers=None):
        return self.get_json_response(url, headers).body


def _registry(tmp_path: Path, access_path: str) -> Registry:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id="nvdb:60", title="Bru", publisher_name="Statens vegvesen",
        access_path=access_path, license=None,
    )
    registry.conn.commit()
    return registry


def test_a_road_object_url_is_classified_as_features() -> None:
    assert classify_access_path(f"{OBJECT_API}/60/272296863")["kind"] == CAPABILITY_FEATURES
    assert classify_access_path(f"{OBJECT_API}/60")["kind"] == CAPABILITY_FEATURES


def test_one_object_becomes_one_feature_record(tmp_path: Path) -> None:
    registry = _registry(tmp_path, f"{OBJECT_API}/60/272296863")
    try:
        result = fetch_observations(
            registry, "nvdb:60", table_id="60", http=FakeHttp(BRIDGE)
        )
        assert result.counts.listed == 1
        sample = result.sample[0]
        assert sample["subject_scheme"] == "NVDB vegobjekt-id"
        assert sample["subject_code"] == "272296863"
        # The kommune and fylke codes are what join a road object to statistics,
        # so they are lifted out of lokasjon rather than left buried.
        assert sample["attributes"]["kommuner"] == ["3105"]
        assert sample["attributes"]["fylker"] == ["31"]
        assert sample["attributes"]["Byggverkstype"] == "Hvelvbru (562)"
        assert sample["attributes"]["geometri_wkt"].startswith("LINESTRING Z")
        stored = registry.list_records(dataset_id="nvdb:60")
        assert [r["kind"] for r in stored] == ["feature"]
    finally:
        registry.close()


def test_a_collection_fetch_is_a_bounded_page(tmp_path: Path) -> None:
    registry = _registry(tmp_path, f"{OBJECT_API}/60")
    http = FakeHttp({"objekter": [BRIDGE]})
    try:
        fetch_observations(registry, "nvdb:60", table_id="60", http=http)
        # The default page size is asked for explicitly; nothing is unbounded.
        assert "antall=10" in http.urls[0]
    finally:
        registry.close()


def test_an_unbounded_page_is_refused_not_truncated(tmp_path: Path) -> None:
    registry = _registry(tmp_path, f"{OBJECT_API}/60")
    try:
        with pytest.raises(SelectionTooLarge):
            fetch_observations(
                registry, "nvdb:60", table_id="60",
                http=FakeHttp({"objekter": []}), select={"antall": ["5000"]},
            )
    finally:
        registry.close()


def test_a_place_filter_takes_a_klass_code_not_a_name(tmp_path: Path) -> None:
    registry = _registry(tmp_path, f"{OBJECT_API}/60")
    http = FakeHttp({"objekter": [BRIDGE]})
    try:
        fetch_observations(
            registry, "nvdb:60", table_id="60", http=http, select={"kommune": ["0301"]}
        )
        assert "kommune=0301" in http.urls[0]
        # A name would be sent to NVDB and silently match nothing.
        with pytest.raises(ValueError, match="not a numeric Klass code"):
            fetch_observations(
                registry, "nvdb:60", table_id="60", http=http, select={"kommune": ["Oslo"]}
            )
    finally:
        registry.close()


def test_an_unknown_filter_is_refused(tmp_path: Path) -> None:
    registry = _registry(tmp_path, f"{OBJECT_API}/60")
    try:
        with pytest.raises(ValueError, match="does not filter on"):
            fetch_observations(
                registry, "nvdb:60", table_id="60",
                http=FakeHttp({"objekter": []}), select={"farge": ["rød"]},
            )
    finally:
        registry.close()


def test_an_empty_response_stores_nothing_and_says_so(tmp_path: Path) -> None:
    # Returning success with zero records would read as "there are no bridges".
    registry = _registry(tmp_path, f"{OBJECT_API}/60")
    try:
        with pytest.raises(ValueError, match="no objects"):
            fetch_observations(
                registry, "nvdb:60", table_id="60", http=FakeHttp({"objekter": []})
            )
        assert registry.list_records(dataset_id="nvdb:60") == []
    finally:
        registry.close()


def test_a_payload_without_an_id_is_not_turned_into_a_record() -> None:
    with pytest.raises(ValueError, match="no id"):
        feature_from_vegobjekt({"metadata": {}})
