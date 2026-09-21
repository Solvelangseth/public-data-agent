from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kystwfs import (
    WFS_URL,
    KystwfsSource,
    cells_from_kystwfs,
    is_kystwfs_url,
    kystwfs_table_id,
    printed_service_id,
    printed_service_title,
)

KYSTDATAHUSET_URL = "https://kystdatahuset.no/ws/api/ais/latest"
HAVNEDATA_URL = "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/collections"
NAVWARNINGS_URL = "https://api.kystverket.no/openapi.json"
KYSTWMS_URL = (
    "https://services.kystverket.no/wms.ashx?service=WMS&request=GetCapabilities"
)
DATASET_ID = "kystwfs:wfs.ashx"

WFS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs" version="1.1.0">
  <ows:ServiceIdentification xmlns:ows="http://www.opengis.net/ows">
    <ows:Title>Kystverket WFS - kart</ows:Title>
  </ows:ServiceIdentification>
  <FeatureTypeList>
    <FeatureType>
      <Name>layer_611</Name>
      <Title>Kystkontur</Title>
      <Abstract>skip</Abstract>
    </FeatureType>
    <FeatureType>
      <Name>layer_26</Name>
      <Title>Nødhavner</Title>
    </FeatureType>
    <FeatureType>
      <Name>layer_1077</Name>
    </FeatureType>
  </FeatureTypeList>
</wfs:WFS_Capabilities>
"""
HTML_ERROR = """
<html><head><title>MapServer Message</title></head>
<body>msWFSDispatch(): WFS server error.</body></html>
"""


class CatalogHttp:
    def __init__(self, pages: dict[str, str] | None = None, missing: set[str] | None = None) -> None:
        self.gets: list[str] = []
        self.pages = pages or {WFS_URL: WFS_XML}
        self.missing = missing or set()

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url in self.missing:
            raise RuntimeError("HTTP 404")
        if url in self.pages:
            return self.pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == WFS_URL:
            return WFS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kystwfs fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kystwfs fetch must GET, not POST {url}")


def test_printed_refs_keep_live_xml_and_skip_html() -> None:
    http = CatalogHttp()
    source = KystwfsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["wfs.ashx"]
    assert [ref.source_native_uri for ref in refs] == [WFS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "avfallspunkt" for ref in refs)
    assert HAVNEDATA_URL not in [ref.source_native_uri for ref in refs]
    assert KYSTDATAHUSET_URL not in [ref.source_native_uri for ref in refs]
    assert KYSTWMS_URL not in [ref.source_native_uri for ref in refs]


def test_printed_refs_skip_html_and_404() -> None:
    http = CatalogHttp(pages={WFS_URL: HTML_ERROR})
    source = KystwfsSource(http=http)
    with pytest.raises(Exception, match="GetCapabilities XML"):
        source.list_dataset_refs()
    assert WFS_URL in http.gets

    missing = CatalogHttp(pages={}, missing={WFS_URL})
    source_missing = KystwfsSource(http=missing)
    with pytest.raises(Exception, match="GetCapabilities XML"):
        source_missing.list_dataset_refs()


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id(WFS_URL) == "wfs.ashx"
    assert printed_service_id("/") is None
    assert printed_service_title(WFS_XML, "wfs.ashx") == "Kystverket WFS - kart"
    assert printed_service_title(HTML_ERROR, "wfs.ashx") == "wfs.ashx"


def test_kystwfs_is_a_registered_source() -> None:
    assert "kystwfs" in SOURCE_IDS
    assert "kystverket" in SOURCE_IDS
    assert "havnedata" in SOURCE_IDS
    assert "ldirwms" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    source = build_source("kystwfs")
    assert isinstance(source, KystwfsSource)
    assert source.source_id == "kystwfs"
    assert build_source("kystverket").source_id == "kystverket"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = KystwfsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kystwfs"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == WFS_URL
    assert row["title"] == "Kystverket WFS - kart"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kystverket:")
    assert not str(row["id"]).startswith("havnedata:")
    assert not str(row["id"]).startswith("ldirwms:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["kystwfs_service_id"] == "wfs.ashx"
    assert payload["kystwfs_service_href"] == WFS_URL
    assert payload["kystwfs_service_title"] == "Kystverket WFS - kart"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_featuretype_name_cells(tmp_path: Path) -> None:
    source = KystwfsSource(http=CatalogHttp())
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


def test_cells_copy_printed_featuretype_name() -> None:
    cells = cells_from_kystwfs(WFS_XML)
    assert [value for _measure, value, _dims in cells] == [
        "layer_611",
        "layer_26",
        "layer_1077",
    ]
    measure, value, dims = cells[0]
    assert measure == "Name"
    assert value == "layer_611"
    assert dims["Title"] == "Kystkontur"
    assert "Abstract" not in dims
    assert cells[2] == ("Name", "layer_1077", {})
    with pytest.raises(ValueError, match="WFS XML"):
        cells_from_kystwfs(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_kystwfs(HTML_ERROR)
    with pytest.raises(ValueError, match="FeatureType Name"):
        cells_from_kystwfs("<WFS_Capabilities></WFS_Capabilities>")
    with pytest.raises(ValueError, match="WFS XML"):
        cells_from_kystwfs("<WMS_Capabilities></WMS_Capabilities>")


def test_is_kystwfs_url_accepts_only_wfs_host_path() -> None:
    assert is_kystwfs_url(WFS_URL)
    assert kystwfs_table_id(WFS_URL) == "wfs.ashx"
    assert not is_kystwfs_url(KYSTDATAHUSET_URL)
    assert not is_kystwfs_url(HAVNEDATA_URL)
    assert not is_kystwfs_url(NAVWARNINGS_URL)
    assert not is_kystwfs_url(KYSTWMS_URL)
    assert not is_kystwfs_url("https://data.norge.no/datasets/x")
    assert not is_kystwfs_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = KystwfsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "wfs.ashx"
    ]
    assert source.list_dataset_refs(limit=1, offset=1) == []
