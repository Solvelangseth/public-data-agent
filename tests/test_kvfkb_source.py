from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kvfkb import (
    FKB_URL,
    KvfkbSource,
    cells_from_kvfkb,
    is_kvfkb_url,
    kvfkb_table_id,
    printed_service_id,
    printed_services,
)
from public_data_agent.sources.kvgrunn import NORGES_GRUNNKART_URL, is_kvgrunn_url
from public_data_agent.sources.kvtopo import KARTDATA_URL, is_kvtopo_url
from public_data_agent.sources.kvwms import WMS_URL, is_kvwms_url

DATASET_ID = "kvfkb:wms.fkb"

FKB_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>fkb WMS</Title>
    <OnlineResource href="https://wms.geonorge.no/skwms1/wms.fkb?"/>
  </Service>
  <Capability>
    <Layer>
      <Name>fkb</Name>
      <Title>fkb WMS</Title>
      <Layer>
        <Name>fkb_arealdekke</Name>
        <Title>FKB Arealdekke</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>ar5</Name>
        <Title>FKB AR5 - Arealressurs</Title>
      </Layer>
      <Layer>
        <Name></Name>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

HTML_ERROR = """
<html><head><title>MapServer Message</title></head>
<body>msWMSDispatch(): WMS server error.</body></html>
"""


class CatalogHttp:
    def __init__(self, pages: dict[str, str] | None = None) -> None:
        self.gets: list[str] = []
        self.pages = pages or {FKB_URL: FKB_XML}

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url in self.pages:
            return self.pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == FKB_URL:
            return FKB_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kvfkb fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kvfkb fetch must GET, not POST {url}")


def test_printed_refs_keep_live_xml_and_skip_html() -> None:
    http = CatalogHttp()
    source = KvfkbSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["wms.fkb"]
    assert [ref.source_native_uri for ref in refs] == [FKB_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "WMS" for ref in refs)
    assert all(ref.source_native_id != "wms.topo" for ref in refs)
    assert all(ref.source_native_id != "wms.kartdata" for ref in refs)
    assert WMS_URL not in [ref.source_native_uri for ref in refs]
    assert KARTDATA_URL not in [ref.source_native_uri for ref in refs]
    assert NORGES_GRUNNKART_URL not in [ref.source_native_uri for ref in refs]


def test_printed_refs_skip_html_capabilities() -> None:
    http = CatalogHttp({FKB_URL: HTML_ERROR})
    source = KvfkbSource(http=http)
    with pytest.raises(Exception, match="printed no GetCapabilities XML"):
        source.list_dataset_refs()
    assert FKB_URL in http.gets


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(FKB_XML, FKB_URL)
    assert [ident for ident, _href, _title in listed] == ["wms.fkb"]
    assert [href for _ident, href, _title in listed] == [FKB_URL]
    assert [title for _ident, _href, title in listed] == ["fkb WMS"]


def test_printed_service_id_uses_last_skwms1_segment() -> None:
    assert printed_service_id(FKB_URL) == "wms.fkb"
    assert printed_service_id(WMS_URL) == "wms.topo"
    assert printed_service_id("/") is None


def test_kvfkb_is_a_registered_source() -> None:
    assert "kvfkb" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "kvgrunn" in SOURCE_IDS
    assert "geonorge" in SOURCE_IDS
    assert "barmark" in SOURCE_IDS
    assert "nordatlas" in SOURCE_IDS
    assert "nibioar50" in SOURCE_IDS
    assert "fbgis" in SOURCE_IDS
    assert "ssbgis" in SOURCE_IDS
    assert "stpartier" in SOURCE_IDS
    assert "crbio" in SOURCE_IDS
    assert "nibioar5f" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("crunit") + 1] == "barmark"
    assert SOURCE_IDS[SOURCE_IDS.index("barmark") + 1] == "crproj"
    assert SOURCE_IDS[SOURCE_IDS.index("crproj") + 1] == "ssbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbgis") + 1] == "stpartier"
    assert SOURCE_IDS[SOURCE_IDS.index("stpartier") + 1] == "crbio"
    assert SOURCE_IDS[SOURCE_IDS.index("crbio") + 1] == "nibioar5f"
    assert SOURCE_IDS[SOURCE_IDS.index("nibioar5f") + 1] == "kvfkb"
    assert SOURCE_IDS[SOURCE_IDS.index("kvfkb") + 1] == "crperson"
    assert SOURCE_IDS[SOURCE_IDS.index("crperson") + 1] == "stsporre"
    assert SOURCE_IDS[SOURCE_IDS.index("stsporre") + 1] == "crresult"
    assert SOURCE_IDS[SOURCE_IDS.index("crresult") + 1] == "stmoter"
    assert SOURCE_IDS[SOURCE_IDS.index("stmoter") + 1] == "ssbfritid"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbfritid") + 1] == "kvadm"
    assert SOURCE_IDS[SOURCE_IDS.index("kvadm") + 1] == "kvkrets"
    assert SOURCE_IDS[SOURCE_IDS.index("kvkrets") + 1] == "sthoringer"
    assert SOURCE_IDS[-1] == "sthoringer"
    source = build_source("kvfkb")
    assert isinstance(source, KvfkbSource)
    assert source.source_id == "kvfkb"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = KvfkbSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kvfkb"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FKB_URL
    assert row["title"] == "fkb WMS"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kvwms:")
    assert not str(row["id"]).startswith("kvtopo:")
    assert not str(row["id"]).startswith("kvgrunn:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["kvfkb_service_id"] == "wms.fkb"
    assert payload["kvfkb_service_href"] == FKB_URL
    assert payload["kvfkb_service_title"] == "fkb WMS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = KvfkbSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == FKB_URL
    assert result.table_id == "wms.fkb"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"fkb", "fkb_arealdekke", "ar5"}
    assert by_value["fkb_arealdekke"]["measure"] == "Name"
    dims = json.loads(by_value["fkb_arealdekke"]["dimensions_json"])
    assert dims["Title"] == "FKB Arealdekke"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == FKB_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_name() -> None:
    cells = cells_from_kvfkb(FKB_XML)
    assert [value for _measure, value, _dims in cells] == [
        "fkb",
        "fkb_arealdekke",
        "ar5",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "fkb_arealdekke"
    assert dims["Title"] == "FKB Arealdekke"
    assert "Abstract" not in dims
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_kvfkb(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_kvfkb(HTML_ERROR)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_kvfkb("<WMS_Capabilities></WMS_Capabilities>")


def test_is_kvfkb_url_accepts_only_leftover_fkb_path() -> None:
    assert is_kvfkb_url(FKB_URL)
    assert kvfkb_table_id(FKB_URL) == "wms.fkb"
    assert not is_kvfkb_url(WMS_URL)
    assert not is_kvfkb_url(KARTDATA_URL)
    assert not is_kvfkb_url(NORGES_GRUNNKART_URL)
    assert is_kvtopo_url(FKB_URL)
    assert is_kvwms_url(WMS_URL)
    assert is_kvgrunn_url(NORGES_GRUNNKART_URL)
    assert not is_kvfkb_url("https://data.norge.no/datasets/x")
    assert not is_kvfkb_url(None)


def test_limit_and_offset_slice_printed_documents() -> None:
    source = KvfkbSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "wms.fkb"
    ]
    assert source.list_dataset_refs(limit=1, offset=1) == []
