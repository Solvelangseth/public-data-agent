from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kystwms import (
    WFS_URL,
    WMS_URL,
    KystwmsSource,
    cells_from_kystwms,
    is_kystwms_url,
    kystwms_table_id,
    printed_service_id,
)

HAVNEDATA_URL = "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/collections"
KYSTDATAHUSET_URL = "https://kystdatahuset.no/ws/api/"
NAVWARNINGS_URL = "https://api.kystverket.no/data/navigationwarnings/coastal/"
DATASET_ID = "kystwms:wms.ashx"

WMS_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>kystverk</Name>
      <Title>Kystverkets WMS</Title>
      <Layer>
        <Name>anlegg</Name>
        <Title>Anlegg</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>farled</Name>
        <Title>Farled</Title>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>kyst:anlegg</Name>
      <Title>Anlegg</Title>
    </FeatureType>
    <FeatureType>
      <Name>kyst:farled</Name>
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
            WMS_URL: WMS_XML,
            WFS_URL: WFS_XML,
        }

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url in self.pages:
            return self.pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == WMS_URL:
            return WMS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kystwms fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kystwms fetch must GET, not POST {url}")


def test_printed_refs_keep_live_xml_and_skip_html() -> None:
    http = CatalogHttp()
    source = KystwmsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["wms.ashx", "wfs.ashx"]
    assert [ref.source_native_uri for ref in refs] == [WMS_URL, WFS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "wms" for ref in refs)
    assert all(ref.source_native_id != "wfs" for ref in refs)


def test_printed_refs_skip_html_capabilities() -> None:
    http = CatalogHttp(
        {
            WMS_URL: WMS_XML,
            WFS_URL: HTML_ERROR,
        }
    )
    source = KystwmsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["wms.ashx"]
    assert WFS_URL in http.gets


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id(WMS_URL) == "wms.ashx"
    assert printed_service_id(WFS_URL) == "wfs.ashx"
    assert printed_service_id("/") is None


def test_kystwms_is_a_registered_source() -> None:
    assert "kystwms" in SOURCE_IDS
    assert "kystverket" in SOURCE_IDS
    assert "havnedata" in SOURCE_IDS
    assert "navwarnings" in SOURCE_IDS
    assert "rawms" in SOURCE_IDS
    source = build_source("kystwms")
    assert isinstance(source, KystwmsSource)
    assert source.source_id == "kystwms"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = KystwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kystwms"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == WMS_URL
    assert row["title"] == "wms.ashx"
    other = registry.get_dataset("kystwms:wfs.ashx")
    assert other is not None
    assert other["access_path"] == WFS_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kystverket:")
    assert not str(row["id"]).startswith("havnedata:")
    assert not str(row["id"]).startswith("navwarnings:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["kystwms_service_id"] == "wms.ashx"
    assert payload["kystwms_service_href"] == WMS_URL
    assert payload["kystwms_service_title"] == "wms.ashx"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = KystwmsSource(http=CatalogHttp())
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
    cells = cells_from_kystwms(WMS_XML)
    assert [value for _measure, value, _dims in cells] == [
        "kystverk",
        "anlegg",
        "farled",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "anlegg"
    assert dims["Title"] == "Anlegg"
    assert "Abstract" not in dims
    wfs_cells = cells_from_kystwms(WFS_XML)
    assert [value for _measure, value, _dims in wfs_cells] == [
        "kyst:anlegg",
        "kyst:farled",
    ]
    assert wfs_cells[0][2]["Title"] == "Anlegg"
    assert wfs_cells[1][2] == {}
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_kystwms(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_kystwms(HTML_ERROR)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_kystwms("<WMS_Capabilities></WMS_Capabilities>")
    with pytest.raises(ValueError, match="FeatureType Name"):
        cells_from_kystwms("<WFS_Capabilities></WFS_Capabilities>")


def test_is_kystwms_url_accepts_only_host_path() -> None:
    assert is_kystwms_url(WMS_URL)
    assert is_kystwms_url(WFS_URL)
    assert kystwms_table_id(WMS_URL) == "wms.ashx"
    assert kystwms_table_id(WFS_URL) == "wfs.ashx"
    assert not is_kystwms_url(HAVNEDATA_URL)
    assert not is_kystwms_url(KYSTDATAHUSET_URL)
    assert not is_kystwms_url(NAVWARNINGS_URL)
    assert not is_kystwms_url("https://data.norge.no/datasets/x")
    assert not is_kystwms_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = KystwmsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "wms.ashx"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["wfs.ashx"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
