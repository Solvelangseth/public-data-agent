from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.avinorgis import (
    LUFTHAVNPUNKT_WFS_URL,
    STOYLUFTHAVN_WFS_URL,
    STOYLUFTHAVN_WMS_URL,
    AvinorgisSource,
    avinorgis_table_id,
    cells_from_avinorgis,
    is_avinorgis_url,
    printed_service_id,
)

KVWMS_URL = "https://wms.geonorge.no/skwms1/wms.topo?service=WMS&request=GetCapabilities"
KVGRUNN_URL = (
    "https://wms.geonorge.no/skwms1/wms.norges_grunnkart?service=WMS&request=GetCapabilities"
)
VEGOGC_URL = "https://ogckart-sn1.atlas.vegvesen.no/vegvar/1.0/ows?service=WMS&request=GetCapabilities"
GEONORGE_URL = "https://kartkatalog.geonorge.no/api/search?text=Avinor&limit=50"
BANEGIS_WMS_URL = (
    "https://wms.geonorge.no/skwms1/wms.stoysonerjernbanenett"
    "?service=WMS&request=GetCapabilities"
)
DATASET_ID = "avinorgis:wms.stoylufthavn"

WMS_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>stoylufthavn</Name>
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
      <Name>avinor:lufthavn</Name>
      <Title>Lufthavn</Title>
    </FeatureType>
    <FeatureType>
      <Name>avinor:stoy</Name>
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
            LUFTHAVNPUNKT_WFS_URL: WFS_XML,
            STOYLUFTHAVN_WFS_URL: WFS_XML,
            STOYLUFTHAVN_WMS_URL: WMS_XML,
        }

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url in self.pages:
            return self.pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == STOYLUFTHAVN_WMS_URL:
            return WMS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"avinorgis fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"avinorgis fetch must GET, not POST {url}")


def test_printed_refs_keep_live_xml_and_skip_html() -> None:
    http = CatalogHttp()
    source = AvinorgisSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "wfs.lufthavnpunkt_avinor",
        "wfs.stoylufthavn",
        "wms.stoylufthavn",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        LUFTHAVNPUNKT_WFS_URL,
        STOYLUFTHAVN_WFS_URL,
        STOYLUFTHAVN_WMS_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "wms" for ref in refs)
    assert all(ref.source_native_id != "wfs" for ref in refs)


def test_printed_refs_skip_html_and_failed_capabilities() -> None:
    http = CatalogHttp(
        {
            LUFTHAVNPUNKT_WFS_URL: WFS_XML,
            STOYLUFTHAVN_WFS_URL: HTML_ERROR,
            STOYLUFTHAVN_WMS_URL: WMS_XML,
        }
    )
    source = AvinorgisSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "wfs.lufthavnpunkt_avinor",
        "wms.stoylufthavn",
    ]
    assert STOYLUFTHAVN_WFS_URL in http.gets


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id(LUFTHAVNPUNKT_WFS_URL) == "wfs.lufthavnpunkt_avinor"
    assert printed_service_id(STOYLUFTHAVN_WFS_URL) == "wfs.stoylufthavn"
    assert printed_service_id(STOYLUFTHAVN_WMS_URL) == "wms.stoylufthavn"
    assert printed_service_id("/") is None


def test_avinorgis_is_a_registered_source() -> None:
    assert "avinorgis" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    assert "kvgrunn" in SOURCE_IDS
    assert "vegogc" in SOURCE_IDS
    assert "geonorge" in SOURCE_IDS
    assert "banegis" in SOURCE_IDS
    assert "mattilsyn" in SOURCE_IDS
    assert "nibiorest" in SOURCE_IDS
    assert "nbprov" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("nbprov") + 1] == "avinorgis"
    source = build_source("avinorgis")
    assert isinstance(source, AvinorgisSource)
    assert source.source_id == "avinorgis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = AvinorgisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "avinorgis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == STOYLUFTHAVN_WMS_URL
    assert row["title"] == "wms.stoylufthavn"
    other = registry.get_dataset("avinorgis:wfs.lufthavnpunkt_avinor")
    assert other is not None
    assert other["access_path"] == LUFTHAVNPUNKT_WFS_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kvwms:")
    assert not str(row["id"]).startswith("kvgrunn:")
    assert not str(row["id"]).startswith("vegogc:")
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("banegis:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["avinorgis_service_id"] == "wms.stoylufthavn"
    assert payload["avinorgis_service_href"] == STOYLUFTHAVN_WMS_URL
    assert payload["avinorgis_service_title"] == "wms.stoylufthavn"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = AvinorgisSource(http=CatalogHttp())
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
    cells = cells_from_avinorgis(WMS_XML)
    assert [value for _measure, value, _dims in cells] == [
        "stoylufthavn",
        "stoy_natt",
        "stoy_dag",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "stoy_natt"
    assert dims["Title"] == "Stoy natt"
    assert "Abstract" not in dims
    wfs_cells = cells_from_avinorgis(WFS_XML)
    assert [value for _measure, value, _dims in wfs_cells] == [
        "avinor:lufthavn",
        "avinor:stoy",
    ]
    assert wfs_cells[0][2]["Title"] == "Lufthavn"
    assert wfs_cells[1][2] == {}
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_avinorgis(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_avinorgis(HTML_ERROR)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_avinorgis("<WMS_Capabilities></WMS_Capabilities>")
    with pytest.raises(ValueError, match="FeatureType Name"):
        cells_from_avinorgis("<WFS_Capabilities></WFS_Capabilities>")


def test_is_avinorgis_url_accepts_only_printed_leftover_ids() -> None:
    assert is_avinorgis_url(LUFTHAVNPUNKT_WFS_URL)
    assert is_avinorgis_url(STOYLUFTHAVN_WFS_URL)
    assert is_avinorgis_url(STOYLUFTHAVN_WMS_URL)
    assert avinorgis_table_id(STOYLUFTHAVN_WMS_URL) == "wms.stoylufthavn"
    assert avinorgis_table_id(LUFTHAVNPUNKT_WFS_URL) == "wfs.lufthavnpunkt_avinor"
    assert not is_avinorgis_url(KVWMS_URL)
    assert not is_avinorgis_url(KVGRUNN_URL)
    assert not is_avinorgis_url(VEGOGC_URL)
    assert not is_avinorgis_url(GEONORGE_URL)
    assert not is_avinorgis_url(BANEGIS_WMS_URL)
    assert not is_avinorgis_url("https://data.norge.no/datasets/x")
    assert not is_avinorgis_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = AvinorgisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "wfs.lufthavnpunkt_avinor"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["wfs.stoylufthavn"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
