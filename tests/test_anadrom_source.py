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
from public_data_agent.sources.anadrom import (
    LAYER_URL,
    MAX_LIMIT,
    AnadromSource,
    feature_from_arcgis,
    is_anadrom_url,
    query_url,
)

LAYER = {
    "name": "anadrome_strekninger_lin",
    "type": "Feature Layer",
    "geometryType": "esriGeometryPolyline",
    "fields": [
        {"name": "vassdragsNR", "type": "esriFieldTypeString", "alias": "vassdragsNR"},
        {"name": "elvenavn", "type": "esriFieldTypeString", "alias": "elvenavn"},
        {"name": "nasjonaltLaksevassdrag", "type": "esriFieldTypeString", "alias": "nasjonaltLaksevassdrag"},
        {"name": "lakseregURL", "type": "esriFieldTypeString", "alias": "lakseregURL"},
        {"name": "SHAPE", "type": "esriFieldTypeGeometry", "alias": "SHAPE"},
    ],
}
FEATURE = {
    "attributes": {
        "vassdragsNR": "234.Z",
        "elvenavn": "Tanaelva",
        "nasjonaltLaksevassdrag": "Ja",
        "lakseregURL": "https://lakseregisteret.statsforvalteren.no/visElv.aspx?id=234.Z",
        "OBJECTID": 2,
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


def test_url_is_the_stretch_layer_not_the_catalog_or_other_layers() -> None:
    assert is_anadrom_url(LAYER_URL)
    assert is_anadrom_url(LAYER_URL + "/")
    assert not is_anadrom_url(
        "https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/MapServer?f=json"
    )
    assert not is_anadrom_url(
        "https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/MapServer/0"
    )
    assert not is_anadrom_url(
        "https://kart.miljodirektoratet.no/arcgis/rest/services/vern/MapServer/0"
    )
    assert classify_access_path(LAYER_URL)["kind"] == "features"
    assert (
        classify_access_path(
            "https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/MapServer?f=json"
        )["kind"]
        == "none"
    )
    assert isinstance(build_source("anadrom"), AnadromSource)


def test_feature_uses_printed_vassdragsnummer() -> None:
    feature = feature_from_arcgis(FEATURE)
    assert feature["subject_code"] == "234.Z"
    assert feature["subject_label"] == "Tanaelva"
    assert feature["subject_scheme"] == "nve:vassdragsnummer"
    assert feature["attributes"]["nasjonaltLaksevassdrag"] == "Ja"


def test_query_url_omits_geometry_and_escapes_id() -> None:
    url = query_url(LAYER_URL, vassdrags_nr="234.Z", limit=1)
    assert "returnGeometry=false" in url
    assert "vassdragsNR=" in url
    assert "234.Z" in url
    named = query_url(LAYER_URL, elvenavn="Tanaelva", limit=1)
    assert "elvenavn=" in named
    assert "Tanaelva" in named


def test_source_promotes_only_the_stretch_layer(tmp_path: Path) -> None:
    source = AnadromSource(http=ScriptedHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["anadrome_strekninger_lin"]
    mapped = map_harvested_record(source.fetch_dataset(refs[0]))
    assert mapped.title == "Anadrome laksefisk - Strekninger"
    assert mapped.publisher_name == "Miljødirektoratet"
    assert mapped.access_path == LAYER_URL
    assert mapped.license is None


def test_fetch_one_stretch_stores_a_feature_not_an_observation(tmp_path: Path) -> None:
    http = ScriptedHttp()
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, AnadromSource(http=http))
    indexed = index_dataset(registry, "anadrom:anadrome_strekninger_lin", http=http, catalogues={})
    assert indexed["fields"] >= 1
    result = fetch_observations(
        registry,
        "anadrom:anadrome_strekninger_lin",
        table_id="anadrome_strekninger_lin",
        select={"vassdragsNR": ["234.Z"]},
        http=http,
    )
    assert result.counts.listed == 1
    assert result.sample[0]["kind"] == "feature"
    assert result.sample[0]["subject_code"] == "234.Z"
    assert registry.list_observations("anadrom:anadrome_strekninger_lin") == []
    cap = registry.get_capability("anadrom:anadrome_strekninger_lin")
    assert cap["capability"] == "features"
    assert cap["verified_sample_count"] == 1
    assert cap["subject_scheme"] == "nve:vassdragsnummer"
    registry.close()


def test_page_above_the_cap_is_refused(tmp_path: Path) -> None:
    http = ScriptedHttp()
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, AnadromSource(http=http))
    with pytest.raises(SelectionTooLarge):
        fetch_observations(
            registry,
            "anadrom:anadrome_strekninger_lin",
            table_id="anadrome_strekninger_lin",
            select={"antall": [str(MAX_LIMIT + 1)]},
            http=http,
        )
    assert not any("query" in url for url in http.gets)
    registry.close()
