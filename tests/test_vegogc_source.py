from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.vegogc import (
    VegogcSource,
    cells_from_vegogc,
    is_vegogc_url,
    printed_getcapabilities,
    printed_service_id,
    vegogc_table_id,
)

LIST_URL = (
    "https://www.vegvesen.no/fag/teknologi/apne-data/"
    "et-utvalg-apne-data/ogc-karttjenester/kartlag/"
)
VEGVAR_OWS_URL = (
    "https://ogckart-sn1.atlas.vegvesen.no/vegvar_1_0/ows"
    "?service=wms&request=GetCapabilities"
)
VEGVAR_WFS_URL = (
    "https://ogckart-sn1.atlas.vegvesen.no/vegvar_1_0/wfs"
    "?service=wfs&request=GetCapabilities"
)
DATEX_OWS_URL = (
    "https://ogckart-sn1.atlas.vegvesen.no/datex_3_1/ows"
    "?service=wms&request=GetCapabilities"
)
VEGVAR_WEB_URL = "https://vegvar.atlas.vegvesen.no/some-map"
DATAUT_URL = "https://dataut.vegvesen.no/dataset/ogc-karttjenester"
NIBIO_WMS_URL = (
    "https://wms.nibio.no/cgi-bin/ok_raster?request=getcapabilities&service=wms"
)
KARTVERKET_URL = "https://wms.geonorge.no/skwms1/wms.topo4"
DATASET_ID = "vegogc:vegvar_1_0_ows"
WFS_DATASET_ID = "vegogc:vegvar_1_0_wfs"

KARTLAG_HTML = """
<html><body>
<a href="https://ogckart-sn1.atlas.vegvesen.no/vegvar_1_0/ows?service=wms&amp;request=GetCapabilities">vegvar wms</a>
<a href="https://vegvar.atlas.vegvesen.no/some-map">web map</a>
<a href="https://ogckart-sn1.atlas.vegvesen.no/vegvar_1_0/wfs?service=wfs&amp;request=GetCapabilities">vegvar wfs</a>
<a href="https://ogckart-sn1.atlas.vegvesen.no/norstoy_1_0/ows?service=wms">norstoy</a>
<a href="https://ogckart-sn1.atlas.vegvesen.no/datex_3_1/ows?service=wms&amp;request=GetCapabilities">datex</a>
</body></html>
"""
VEGVAR_OWS_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>vegvar_1_0</Name>
      <Title>Vegvar</Title>
      <Layer>
        <Name>vegvar_1_0:tunnel_segments</Name>
        <Title>Tunnel segments</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>vegvar_1_0:roads</Name>
        <Title>Roads</Title>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
VEGVAR_WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>vegvar_1_0:tunnel_segments</Name>
      <Title>Tunnel segments</Title>
    </FeatureType>
    <FeatureType>
      <Name>vegvar_1_0:roads</Name>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
"""
DATEX_HTML = """
<html><head><title>Error</title></head>
<body>not capabilities</body></html>
"""


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        pages = {
            LIST_URL: KARTLAG_HTML,
            VEGVAR_OWS_URL: VEGVAR_OWS_XML,
            VEGVAR_WFS_URL: VEGVAR_WFS_XML,
            DATEX_OWS_URL: DATEX_HTML,
        }
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        pages = {
            VEGVAR_OWS_URL: VEGVAR_OWS_XML,
            VEGVAR_WFS_URL: VEGVAR_WFS_XML,
        }
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"vegogc fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"vegogc fetch must GET, not POST {url}")


def test_printed_refs_skip_webmap_missing_getcap_and_html_capabilities() -> None:
    http = CatalogHttp()
    source = VegogcSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "vegvar_1_0_ows",
        "vegvar_1_0_wfs",
    ]
    assert [ref.source_native_uri for ref in refs] == [VEGVAR_OWS_URL, VEGVAR_WFS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "vegvar wms" for ref in refs)
    assert all(ref.source_native_id != "norstoy_1_0_ows" for ref in refs)
    assert all(ref.source_native_id != "datex_3_1_ows" for ref in refs)
    assert all(ref.source_native_id != "wfs" for ref in refs)
    assert all("vegvar.atlas.vegvesen.no" not in url for url in http.gets)
    assert all(DATAUT_URL not in url for url in http.gets)
    assert DATEX_OWS_URL in http.gets
    assert LIST_URL in http.gets


def test_printed_services_keep_document_order() -> None:
    listed = printed_getcapabilities(KARTLAG_HTML, LIST_URL)
    assert [ident for ident, _href, _title in listed] == [
        "vegvar_1_0_ows",
        "vegvar_1_0_wfs",
        "datex_3_1_ows",
    ]
    assert [href for _ident, href, _title in listed] == [
        VEGVAR_OWS_URL,
        VEGVAR_WFS_URL,
        DATEX_OWS_URL,
    ]


def test_printed_service_id_joins_path_segments() -> None:
    assert printed_service_id(VEGVAR_OWS_URL) == "vegvar_1_0_ows"
    assert printed_service_id(VEGVAR_WFS_URL) == "vegvar_1_0_wfs"
    assert printed_service_id("https://ogckart-sn1.atlas.vegvesen.no/wfs") == "wfs"
    assert printed_service_id("/") is None


def test_vegogc_is_a_registered_source() -> None:
    assert "vegogc" in SOURCE_IDS
    assert "vegvesen" in SOURCE_IDS
    source = build_source("vegogc")
    assert isinstance(source, VegogcSource)
    assert source.source_id == "vegogc"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = VegogcSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "vegogc"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == VEGVAR_OWS_URL
    assert row["title"] == "vegvar_1_0_ows"
    wfs = registry.get_dataset(WFS_DATASET_ID)
    assert wfs is not None
    assert wfs["access_path"] == VEGVAR_WFS_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("vegvesen:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["vegogc_service_id"] == "vegvar_1_0_ows"
    assert payload["vegogc_service_href"] == VEGVAR_OWS_URL
    assert payload["vegogc_service_title"] == "vegvar_1_0_ows"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = VegogcSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(ValueError, match="map/tile service"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
        )
    assert registry.list_observations(DATASET_ID) == []
    registry.close()


def test_fetch_copies_featuretype_name_cells(tmp_path: Path) -> None:
    source = VegogcSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(ValueError, match="map/tile service"):
        fetch_observations(
            registry,
            WFS_DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
        )
    assert registry.list_observations(WFS_DATASET_ID) == []
    registry.close()


def test_cells_copy_printed_layer_and_featuretype_name() -> None:
    cells = cells_from_vegogc(VEGVAR_OWS_XML)
    assert [value for _measure, value, _dims in cells] == [
        "vegvar_1_0",
        "vegvar_1_0:tunnel_segments",
        "vegvar_1_0:roads",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "vegvar_1_0:tunnel_segments"
    assert dims["Title"] == "Tunnel segments"
    assert "Abstract" not in dims
    wfs_cells = cells_from_vegogc(VEGVAR_WFS_XML)
    assert [value for _measure, value, _dims in wfs_cells] == [
        "vegvar_1_0:tunnel_segments",
        "vegvar_1_0:roads",
    ]
    assert wfs_cells[0] == (
        "Name",
        "vegvar_1_0:tunnel_segments",
        {"Title": "Tunnel segments"},
    )
    assert wfs_cells[1] == ("Name", "vegvar_1_0:roads", {})
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_vegogc(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_vegogc(DATEX_HTML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_vegogc("<WMS_Capabilities></WMS_Capabilities>")
    with pytest.raises(ValueError, match="FeatureType Name"):
        cells_from_vegogc("<WFS_Capabilities></WFS_Capabilities>")


def test_is_vegogc_url_accepts_only_ogckart_host() -> None:
    assert is_vegogc_url(VEGVAR_OWS_URL)
    assert is_vegogc_url(VEGVAR_WFS_URL)
    assert vegogc_table_id(VEGVAR_OWS_URL) == "vegvar_1_0_ows"
    assert vegogc_table_id(VEGVAR_WFS_URL) == "vegvar_1_0_wfs"
    assert not is_vegogc_url(LIST_URL)
    assert not is_vegogc_url(DATAUT_URL)
    assert not is_vegogc_url(VEGVAR_WEB_URL)
    assert not is_vegogc_url(NIBIO_WMS_URL)
    assert not is_vegogc_url(KARTVERKET_URL)
    assert not is_vegogc_url("https://www.vegvesen.no/fag/teknologi/apne-data/")
    assert not is_vegogc_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = VegogcSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "vegvar_1_0_ows"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["vegvar_1_0_wfs"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
