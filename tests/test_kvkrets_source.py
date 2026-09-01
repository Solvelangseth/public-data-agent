from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kvfkb import FKB_URL, is_kvfkb_url
from public_data_agent.sources.kvgrunn import NORGES_GRUNNKART_URL, is_kvgrunn_url
from public_data_agent.sources.kvkrets import (
    WFS_URL,
    KvkretsSource,
    cells_from_kvkrets,
    is_kvkrets_url,
    kvkrets_table_id,
    printed_service_id,
    printed_service_title,
    printed_services,
)
from public_data_agent.sources.kvtopo import KARTDATA_URL, is_kvtopo_url
from public_data_agent.sources.kvwms import WMS_URL, is_kvwms_url

DATASET_ID = "kvkrets:wfs.grunnkretser"

WFS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0" version="2.0.0">
  <ows:ServiceIdentification xmlns:ows="http://www.opengis.net/ows/1.1">
    <ows:Title>Grunnkretser</ows:Title>
  </ows:ServiceIdentification>
  <FeatureTypeList>
    <FeatureType>
      <Name>app:Delområde</Name>
      <Title>Delområde</Title>
      <Abstract>skip</Abstract>
    </FeatureType>
    <FeatureType>
      <Name>app:Grense</Name>
      <Title>Grense</Title>
    </FeatureType>
    <FeatureType>
      <Name>app:Grunnkrets</Name>
      <Title>Grunnkrets</Title>
    </FeatureType>
  </FeatureTypeList>
</wfs:WFS_Capabilities>
"""

HTML_ERROR = """
<html><head><title>MapServer Message</title></head>
<body>msWFSDispatch(): WFS server error.</body></html>
"""


class CatalogHttp:
    def __init__(self, pages: dict[str, str] | None = None) -> None:
        self.gets: list[str] = []
        self.pages = pages or {WFS_URL: WFS_XML}

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url in self.pages:
            return self.pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == WFS_URL:
            return WFS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kvkrets fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kvkrets fetch must GET, not POST {url}")


def test_printed_refs_keep_live_xml_and_skip_html() -> None:
    http = CatalogHttp()
    source = KvkretsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["wfs.grunnkretser"]
    assert [ref.source_native_uri for ref in refs] == [WFS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "WFS" for ref in refs)
    assert all(ref.source_native_id != "wms.fkb" for ref in refs)
    assert all(ref.source_native_id != "wms.norges_grunnkart" for ref in refs)
    assert FKB_URL not in [ref.source_native_uri for ref in refs]
    assert NORGES_GRUNNKART_URL not in [ref.source_native_uri for ref in refs]
    assert WMS_URL not in [ref.source_native_uri for ref in refs]


def test_printed_refs_skip_html_capabilities() -> None:
    http = CatalogHttp({WFS_URL: HTML_ERROR})
    source = KvkretsSource(http=http)
    with pytest.raises(Exception, match="printed no GetCapabilities XML"):
        source.list_dataset_refs()
    assert WFS_URL in http.gets


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(WFS_XML, WFS_URL)
    assert [ident for ident, _href, _title in listed] == ["wfs.grunnkretser"]
    assert [href for _ident, href, _title in listed] == [WFS_URL]
    assert [title for _ident, _href, title in listed] == ["Grunnkretser"]


def test_printed_service_id_uses_last_skwms1_segment() -> None:
    assert printed_service_id(WFS_URL) == "wfs.grunnkretser"
    assert printed_service_id(FKB_URL) == "wms.fkb"
    assert printed_service_id("/") is None
    assert printed_service_title(WFS_XML, "wfs.grunnkretser") == "Grunnkretser"
    assert printed_service_title(HTML_ERROR, "wfs.grunnkretser") == "wfs.grunnkretser"


def test_kvkrets_is_a_registered_source() -> None:
    assert "kvkrets" in SOURCE_IDS
    assert "kvgrunn" in SOURCE_IDS
    assert "kvfkb" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "geonorge" in SOURCE_IDS
    assert "barmark" in SOURCE_IDS
    assert "ssbgis" in SOURCE_IDS
    assert "stmoter" in SOURCE_IDS
    assert "ssbfritid" in SOURCE_IDS
    assert "kvadm" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("crresult") + 1] == "stmoter"
    assert SOURCE_IDS[SOURCE_IDS.index("stmoter") + 1] == "ssbfritid"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbfritid") + 1] == "kvadm"
    assert SOURCE_IDS[SOURCE_IDS.index("kvadm") + 1] == "kvkrets"
    assert SOURCE_IDS[SOURCE_IDS.index("kvkrets") + 1] == "dsbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("dsbgis") + 1] == "nibiogard"
    assert SOURCE_IDS[SOURCE_IDS.index("nibiogard") + 1] == "stskrift"
    assert SOURCE_IDS[SOURCE_IDS.index("stskrift") + 1] == "sthoring"
    assert SOURCE_IDS[-1] == "sthoring"
    source = build_source("kvkrets")
    assert isinstance(source, KvkretsSource)
    assert source.source_id == "kvkrets"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = KvkretsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kvkrets"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == WFS_URL
    assert row["title"] == "Grunnkretser"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kvgrunn:")
    assert not str(row["id"]).startswith("kvfkb:")
    assert not str(row["id"]).startswith("kvwms:")
    assert not str(row["id"]).startswith("kvtopo:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["kvkrets_service_id"] == "wfs.grunnkretser"
    assert payload["kvkrets_service_href"] == WFS_URL
    assert payload["kvkrets_service_title"] == "Grunnkretser"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_featuretype_name_cells(tmp_path: Path) -> None:
    source = KvkretsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == WFS_URL
    assert result.table_id == "wfs.grunnkretser"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"app:Delområde", "app:Grense", "app:Grunnkrets"}
    assert by_value["app:Grunnkrets"]["measure"] == "Name"
    dims = json.loads(by_value["app:Grunnkrets"]["dimensions_json"])
    assert dims["Title"] == "Grunnkrets"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == WFS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_featuretype_name() -> None:
    cells = cells_from_kvkrets(WFS_XML)
    assert [value for _measure, value, _dims in cells] == [
        "app:Delområde",
        "app:Grense",
        "app:Grunnkrets",
    ]
    measure, value, dims = cells[2]
    assert measure == "Name"
    assert value == "app:Grunnkrets"
    assert dims["Title"] == "Grunnkrets"
    assert "Abstract" not in dims
    with pytest.raises(ValueError, match="WFS XML"):
        cells_from_kvkrets(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_kvkrets(HTML_ERROR)
    with pytest.raises(ValueError, match="FeatureType Name"):
        cells_from_kvkrets("<WFS_Capabilities></WFS_Capabilities>")
    with pytest.raises(ValueError, match="WFS XML"):
        cells_from_kvkrets("<WMS_Capabilities></WMS_Capabilities>")


def test_is_kvkrets_url_accepts_only_leftover_grunnkretser_path() -> None:
    assert is_kvkrets_url(WFS_URL)
    assert kvkrets_table_id(WFS_URL) == "wfs.grunnkretser"
    assert not is_kvkrets_url(FKB_URL)
    assert not is_kvkrets_url(NORGES_GRUNNKART_URL)
    assert not is_kvkrets_url(WMS_URL)
    assert not is_kvkrets_url(KARTDATA_URL)
    assert is_kvfkb_url(FKB_URL)
    assert is_kvgrunn_url(NORGES_GRUNNKART_URL)
    assert is_kvwms_url(WMS_URL)
    assert is_kvtopo_url(KARTDATA_URL)
    assert not is_kvkrets_url("https://data.norge.no/datasets/x")
    assert not is_kvkrets_url(None)


def test_limit_and_offset_slice_printed_documents() -> None:
    source = KvkretsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "wfs.grunnkretser"
    ]
    assert source.list_dataset_refs(limit=1, offset=1) == []
