from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.fetch import SelectionTooLarge, classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.mapping import map_harvested_record
from public_data_agent.registry import Registry
from public_data_agent.resource_index import index_dataset
from public_data_agent.sources import build_source
from public_data_agent.sources.naturvern import (
    LAYER_URL,
    MAX_LIMIT,
    NaturvernSource,
    feature_from_arcgis,
    is_naturvern_url,
    query_url,
)

LAYER = {
    "name": "naturvern_omrade",
    "type": "Feature Layer",
    "geometryType": "esriGeometryPolygon",
    "fields": [
        {"name": "naturvernId", "type": "esriFieldTypeString", "alias": "lokalId"},
        {"name": "navn", "type": "esriFieldTypeString", "alias": "navn"},
        {"name": "offisieltNavn", "type": "esriFieldTypeString", "alias": "offisieltNavn"},
        {"name": "verneform", "type": "esriFieldTypeString", "alias": "verneform"},
        {"name": "kommune", "type": "esriFieldTypeString", "alias": "kommune"},
        {"name": "SHAPE", "type": "esriFieldTypeGeometry", "alias": "SHAPE"},
    ],
}
FEATURE = {
    "attributes": {
        "naturvernId": "VV00003155",
        "navn": "Blåfjell",
        "offisieltNavn": "Blåfjell naturreservat",
        "verneform": "Naturreservat",
        "kommune": "Asker (3203)",
        "OBJECTID": 26765,
    }
}


class ScriptedHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url.startswith(LAYER_URL) and "query" not in url:
            return LAYER
        raise AssertionError(url)

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        self.gets.append(url)
        if "query" in url:
            return JsonResponse(status=200, url=url, body={"features": [FEATURE]})
        if url.startswith(LAYER_URL):
            return JsonResponse(status=200, url=url, body=LAYER)
        raise AssertionError(url)


def test_url_is_the_area_layer_not_the_wms_or_the_catalog() -> None:
    assert is_naturvern_url(LAYER_URL)
    assert is_naturvern_url(LAYER_URL + "/")
    assert not is_naturvern_url(
        "https://kart.miljodirektoratet.no/arcgis/rest/services/vern/MapServer?f=json"
    )
    assert not is_naturvern_url(
        "https://kart.miljodirektoratet.no/arcgis/services/vern/mapserver/WMSServer"
        "?service=wms&request=getcapabilities"
    )
    assert classify_access_path(LAYER_URL)["kind"] == "features"
    assert isinstance(build_source("naturvern"), NaturvernSource)


def test_feature_uses_printed_naturvern_id() -> None:
    feature = feature_from_arcgis(FEATURE)
    assert feature["subject_code"] == "VV00003155"
    assert feature["subject_label"] == "Blåfjell naturreservat"
    assert feature["attributes"]["kommune"] == "Asker (3203)"


def test_query_url_omits_geometry_and_escapes_id() -> None:
    url = query_url(LAYER_URL, naturvern_id="VV00003155", limit=1)
    assert "returnGeometry=false" in url
    assert "naturvernId=" in url
    assert "VV00003155" in url


def test_source_promotes_only_the_area_layer(tmp_path: Path) -> None:
    source = NaturvernSource(http=ScriptedHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["naturvern_omrade"]
    mapped = map_harvested_record(source.fetch_dataset(refs[0]))
    assert mapped.title == "Naturvernområder"
    assert mapped.publisher_name == "Miljødirektoratet"
    assert mapped.access_path == LAYER_URL
    assert mapped.license is None


def test_fetch_one_area_stores_a_feature_not_an_observation(tmp_path: Path) -> None:
    http = ScriptedHttp()
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, NaturvernSource(http=http))
    indexed = index_dataset(registry, "naturvern:naturvern_omrade", http=http, catalogues={})
    assert indexed["fields"] >= 1
    result = fetch_observations(
        registry,
        "naturvern:naturvern_omrade",
        table_id="naturvern_omrade",
        select={"naturvernId": ["VV00003155"]},
        http=http,
    )
    assert result.counts.listed == 1
    assert result.sample[0]["kind"] == "feature"
    assert result.sample[0]["subject_code"] == "VV00003155"
    cap = registry.get_capability("naturvern:naturvern_omrade")
    assert cap["capability"] == "features"
    assert cap["verified_sample_count"] == 1
    registry.close()


def test_page_above_the_cap_is_refused(tmp_path: Path) -> None:
    http = ScriptedHttp()
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, NaturvernSource(http=http))
    with pytest.raises(SelectionTooLarge):
        fetch_observations(
            registry,
            "naturvern:naturvern_omrade",
            table_id="naturvern_omrade",
            select={"antall": [str(MAX_LIMIT + 1)]},
            http=http,
        )
    assert not any("query" in url for url in http.gets)
    registry.close()
