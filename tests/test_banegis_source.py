from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.banegis import (
    BANENETTVERK_WFS_URL,
    BANENETTVERK_WMS_URL,
    STOYSONER_WFS_URL,
    STOYSONER_WMS_URL,
    BanegisSource,
    cells_from_banegis,
    is_banegis_url,
    banegis_table_id,
    printed_service_id,
)

KVWMS_URL = "https://wms.geonorge.no/skwms1/wms.topo?service=WMS&request=GetCapabilities"
KVGRUNN_URL = (
    "https://wms.geonorge.no/skwms1/wms.norges_grunnkart?service=WMS&request=GetCapabilities"
)
VEGOGC_URL = "https://ogckart-sn1.atlas.vegvesen.no/vegvar/1.0/ows?service=WMS&request=GetCapabilities"
GEONORGE_URL = "https://kartkatalog.geonorge.no/api/search?text=Bane%20NOR&limit=50"
MDIR_WFS_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.protectedsites?service=WFS&request=GetCapabilities"
)
DATASET_ID = "banegis:wms.stoysonerjernbanenett"

WMS_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>stoysoner</Name>
      <Title>Stoysoner</Title>
      <Layer>
        <Name>stoy_natt</Name>
        <Title>Stoy natt</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>stoy_dag</Name>
        <Title>Stoy dag</Title>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>jernbane:stoysone</Name>
      <Title>Stoysone</Title>
    </FeatureType>
    <FeatureType>
      <Name>jernbane:bane</Name>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
"""
HTML_ERROR = """
<html><head><title>MapServer Message</title></head>
<body>msWMSDispatch(): WMS server error.</body></html>
"""


class CatalogHttp:
    def __init__(self, pages: dict[str, str] | None = None) -> None:
        self.gets: list[str] = []
        self.pages = pages or {
            STOYSONER_WFS_URL: WFS_XML,
            STOYSONER_WMS_URL: WMS_XML,
            BANENETTVERK_WFS_URL: WFS_XML,
            BANENETTVERK_WMS_URL: WMS_XML,
        }

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url in self.pages:
            return self.pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == STOYSONER_WMS_URL:
            return WMS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"banegis fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"banegis fetch must GET, not POST {url}")


def test_printed_refs_keep_live_xml_and_skip_html() -> None:
    http = CatalogHttp()
    source = BanegisSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "wfs.stoysonerjernbanenett",
        "wms.stoysonerjernbanenett",
        "wfs.banenettverk",
        "wms.banenettverk",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        STOYSONER_WFS_URL,
        STOYSONER_WMS_URL,
        BANENETTVERK_WFS_URL,
        BANENETTVERK_WMS_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "wms" for ref in refs)
    assert all(ref.source_native_id != "wfs" for ref in refs)


def test_printed_refs_skip_html_and_failed_capabilities() -> None:
    http = CatalogHttp(
        {
            STOYSONER_WFS_URL: WFS_XML,
            STOYSONER_WMS_URL: WMS_XML,
            BANENETTVERK_WFS_URL: HTML_ERROR,
            BANENETTVERK_WMS_URL: WMS_XML,
        }
    )
    source = BanegisSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "wfs.stoysonerjernbanenett",
        "wms.stoysonerjernbanenett",
        "wms.banenettverk",
    ]
    assert BANENETTVERK_WFS_URL in http.gets


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id(STOYSONER_WMS_URL) == "wms.stoysonerjernbanenett"
    assert printed_service_id(STOYSONER_WFS_URL) == "wfs.stoysonerjernbanenett"
    assert printed_service_id(BANENETTVERK_WMS_URL) == "wms.banenettverk"
    assert printed_service_id(BANENETTVERK_WFS_URL) == "wfs.banenettverk"
    assert printed_service_id("/") is None


def test_banegis_is_a_registered_source() -> None:
    assert "banegis" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    assert "kvgrunn" in SOURCE_IDS
    assert "vegogc" in SOURCE_IDS
    assert "geonorge" in SOURCE_IDS
    source = build_source("banegis")
    assert isinstance(source, BanegisSource)
    assert source.source_id == "banegis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = BanegisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "banegis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == STOYSONER_WMS_URL
    assert row["title"] == "wms.stoysonerjernbanenett"
    other = registry.get_dataset("banegis:wfs.banenettverk")
    assert other is not None
    assert other["access_path"] == BANENETTVERK_WFS_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kvwms:")
    assert not str(row["id"]).startswith("kvgrunn:")
    assert not str(row["id"]).startswith("vegogc:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["banegis_service_id"] == "wms.stoysonerjernbanenett"
    assert payload["banegis_service_href"] == STOYSONER_WMS_URL
    assert payload["banegis_service_title"] == "wms.stoysonerjernbanenett"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = BanegisSource(http=CatalogHttp())
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


def test_cells_copy_printed_layer_and_featuretype_name() -> None:
    cells = cells_from_banegis(WMS_XML)
    assert [value for _measure, value, _dims in cells] == [
        "stoysoner",
        "stoy_natt",
        "stoy_dag",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "stoy_natt"
    assert dims["Title"] == "Stoy natt"
    assert "Abstract" not in dims
    wfs_cells = cells_from_banegis(WFS_XML)
    assert [value for _measure, value, _dims in wfs_cells] == [
        "jernbane:stoysone",
        "jernbane:bane",
    ]
    assert wfs_cells[0][2]["Title"] == "Stoysone"
    assert wfs_cells[1][2] == {}
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_banegis(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_banegis(HTML_ERROR)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_banegis("<WMS_Capabilities></WMS_Capabilities>")
    with pytest.raises(ValueError, match="FeatureType Name"):
        cells_from_banegis("<WFS_Capabilities></WFS_Capabilities>")


def test_is_banegis_url_accepts_only_printed_leftover_ids() -> None:
    assert is_banegis_url(STOYSONER_WMS_URL)
    assert is_banegis_url(STOYSONER_WFS_URL)
    assert is_banegis_url(BANENETTVERK_WMS_URL)
    assert is_banegis_url(BANENETTVERK_WFS_URL)
    assert banegis_table_id(STOYSONER_WMS_URL) == "wms.stoysonerjernbanenett"
    assert banegis_table_id(BANENETTVERK_WFS_URL) == "wfs.banenettverk"
    assert not is_banegis_url(KVWMS_URL)
    assert not is_banegis_url(KVGRUNN_URL)
    assert not is_banegis_url(VEGOGC_URL)
    assert not is_banegis_url(GEONORGE_URL)
    assert not is_banegis_url(MDIR_WFS_URL)
    assert not is_banegis_url("https://data.norge.no/datasets/x")
    assert not is_banegis_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = BanegisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "wfs.stoysonerjernbanenett"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["wms.stoysonerjernbanenett"]
    assert source.list_dataset_refs(limit=1, offset=4) == []
