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
from public_data_agent.sources.friluft import (
    LAYER_URL,
    MAX_LIMIT,
    FriluftSource,
    feature_from_arcgis,
    is_friluft_url,
    query_url,
)

LAYER = {
    "name": "friluftsliv_statlig_sikra",
    "type": "Feature Layer",
    "geometryType": "esriGeometryPolygon",
    "fields": [
        {"name": "friluftId", "type": "esriFieldTypeString", "alias": "friluftId"},
        {"name": "omraadeNavn", "type": "esriFieldTypeString", "alias": "Områdenavn"},
        {"name": "omraadeVerdi", "type": "esriFieldTypeString", "alias": "Område verdi"},
        {"name": "faktaark", "type": "esriFieldTypeString", "alias": "Faktaark"},
        {"name": "SHAPE", "type": "esriFieldTypeGeometry", "alias": "SHAPE"},
        {"name": "SHAPE.STArea()", "type": "esriFieldTypeDouble", "alias": "SHAPE.STArea()"},
    ],
}
FEATURE = {
    "attributes": {
        "friluftId": "FS00000161",
        "omraadeNavn": "Kystad",
        "omraadeVerdi": "IkkeVerdisattFriluftslivsomraade",
        "faktaark": "https://faktaark.naturbase.no/?id=FS00000161",
        "brukergrupper": "Lokalt",
        "OBJECTID": 1,
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


def test_url_is_the_area_layer_not_the_catalog_or_other_services() -> None:
    assert is_friluft_url(LAYER_URL)
    assert is_friluft_url(LAYER_URL + "/")
    assert not is_friluft_url(
        "https://kart.miljodirektoratet.no/arcgis/rest/services/friluftsliv_statlig_sikra/MapServer?f=json"
    )
    assert not is_friluft_url(
        "https://kart.miljodirektoratet.no/arcgis/rest/services/friluftsliv_kartlagt/MapServer/0"
    )
    assert not is_friluft_url(
        "https://kart.miljodirektoratet.no/arcgis/rest/services/vern/MapServer/0"
    )
    assert classify_access_path(LAYER_URL)["kind"] == "features"
    assert (
        classify_access_path(
            "https://kart.miljodirektoratet.no/arcgis/rest/services/friluftsliv_statlig_sikra/MapServer?f=json"
        )["kind"]
        == "none"
    )
    assert isinstance(build_source("friluft"), FriluftSource)


def test_feature_uses_printed_friluft_id() -> None:
    feature = feature_from_arcgis(FEATURE)
    assert feature["subject_code"] == "FS00000161"
    assert feature["subject_label"] == "Kystad"
    assert feature["subject_scheme"] == "naturbase:friluftId"
    assert feature["attributes"]["faktaark"] == "https://faktaark.naturbase.no/?id=FS00000161"


def test_query_url_omits_geometry_and_escapes_id() -> None:
    url = query_url(LAYER_URL, friluft_id="FS00000161", limit=1)
    assert "returnGeometry=false" in url
    assert "friluftId=" in url
    assert "FS00000161" in url


def test_source_promotes_only_the_area_layer(tmp_path: Path) -> None:
    source = FriluftSource(http=ScriptedHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["friluftsliv_statlig_sikra"]
    mapped = map_harvested_record(source.fetch_dataset(refs[0]))
    assert mapped.title == "Friluftslivsområder - statlig sikra"
    assert mapped.publisher_name == "Miljødirektoratet"
    assert mapped.access_path == LAYER_URL
    assert mapped.license is None


def test_fetch_one_area_stores_a_feature_not_an_observation(tmp_path: Path) -> None:
    http = ScriptedHttp()
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FriluftSource(http=http))
    indexed = index_dataset(registry, "friluft:friluftsliv_statlig_sikra", http=http, catalogues={})
    assert indexed["fields"] >= 1
    result = fetch_observations(
        registry,
        "friluft:friluftsliv_statlig_sikra",
        table_id="friluftsliv_statlig_sikra",
        select={"friluftId": ["FS00000161"]},
        http=http,
    )
    assert result.counts.listed == 1
    assert result.sample[0]["kind"] == "feature"
    assert result.sample[0]["subject_code"] == "FS00000161"
    assert registry.list_observations("friluft:friluftsliv_statlig_sikra") == []
    cap = registry.get_capability("friluft:friluftsliv_statlig_sikra")
    assert cap["capability"] == "features"
    assert cap["verified_sample_count"] == 1
    assert cap["subject_scheme"] == "naturbase:friluftId"
    registry.close()


def test_page_above_the_cap_is_refused(tmp_path: Path) -> None:
    http = ScriptedHttp()
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FriluftSource(http=http))
    with pytest.raises(SelectionTooLarge):
        fetch_observations(
            registry,
            "friluft:friluftsliv_statlig_sikra",
            table_id="friluftsliv_statlig_sikra",
            select={"antall": [str(MAX_LIMIT + 1)]},
            http=http,
        )
    assert not any("query" in url for url in http.gets)
    registry.close()
