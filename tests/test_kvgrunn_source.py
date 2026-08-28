from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kvgrunn import (
    NORGES_GRUNNKART_URL,
    TOPOGRAATONE_URL,
    KvgrunnSource,
    cells_from_kvgrunn,
    is_kvgrunn_url,
    kvgrunn_table_id,
    printed_service_id,
    printed_services,
)
from public_data_agent.sources.kvwms import WMTS_URL, WMS_URL, is_kvwms_url

DATASET_ID = "kvgrunn:wms.norges_grunnkart"

TOPOGRAATONE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>Topografisk norgeskart gråtone</Title>
    <OnlineResource href="https://wms.geonorge.no/skwms1/wms.topograatone?"/>
  </Service>
  <Capability>
    <Layer>
      <Title>root</Title>
      <Layer>
        <Name>topograatone</Name>
        <Title>Graatone</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>kd_arealdekkeflate</Name>
        <Title>Arealdekke</Title>
      </Layer>
      <Layer>
        <Name></Name>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

NORGES_GRUNNKART_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>Norges grunnkart</Title>
    <OnlineResource href="https://wms.geonorge.no/skwms1/wms.norges_grunnkart?"/>
  </Service>
  <Capability>
    <Layer>
      <Name>Norges_grunnkart</Name>
      <Title>Norges grunnkart</Title>
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
        self.pages = pages or {
            TOPOGRAATONE_URL: TOPOGRAATONE_XML,
            NORGES_GRUNNKART_URL: NORGES_GRUNNKART_XML,
        }

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url in self.pages:
            return self.pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == NORGES_GRUNNKART_URL:
            return NORGES_GRUNNKART_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kvgrunn fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kvgrunn fetch must GET, not POST {url}")


def test_printed_refs_keep_live_xml_and_skip_html() -> None:
    http = CatalogHttp()
    source = KvgrunnSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "wms.topograatone",
        "wms.norges_grunnkart",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        TOPOGRAATONE_URL,
        NORGES_GRUNNKART_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "WMS" for ref in refs)
    assert all(ref.source_native_id != "wms.topo" for ref in refs)
    assert all(ref.source_native_id != "wmts" for ref in refs)
    assert WMS_URL not in [ref.source_native_uri for ref in refs]
    assert WMTS_URL not in [ref.source_native_uri for ref in refs]


def test_printed_refs_skip_html_capabilities() -> None:
    http = CatalogHttp(
        {
            TOPOGRAATONE_URL: HTML_ERROR,
            NORGES_GRUNNKART_URL: NORGES_GRUNNKART_XML,
        }
    )
    source = KvgrunnSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["wms.norges_grunnkart"]
    assert TOPOGRAATONE_URL in http.gets


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(TOPOGRAATONE_XML, TOPOGRAATONE_URL)
    assert [ident for ident, _href, _title in listed] == ["wms.topograatone"]
    assert [href for _ident, href, _title in listed] == [TOPOGRAATONE_URL]
    assert [title for _ident, _href, title in listed] == ["Topografisk norgeskart gråtone"]
    listed = printed_services(NORGES_GRUNNKART_XML, NORGES_GRUNNKART_URL)
    assert [ident for ident, _href, _title in listed] == ["wms.norges_grunnkart"]
    assert [title for _ident, _href, title in listed] == ["Norges grunnkart"]


def test_printed_service_id_uses_last_skwms1_segment() -> None:
    assert printed_service_id(TOPOGRAATONE_URL) == "wms.topograatone"
    assert printed_service_id(NORGES_GRUNNKART_URL) == "wms.norges_grunnkart"
    assert printed_service_id(WMS_URL) == "wms.topo"
    assert printed_service_id("/") is None


def test_kvgrunn_is_a_registered_source() -> None:
    assert "kvgrunn" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    assert "nguwms" in SOURCE_IDS
    assert "stormflo" in SOURCE_IDS
    assert "kystwfs" in SOURCE_IDS
    assert "nbcodelist" in SOURCE_IDS
    assert "nbdsd" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("nbdsd") + 1] == "kvgrunn"
    source = build_source("kvgrunn")
    assert isinstance(source, KvgrunnSource)
    assert source.source_id == "kvgrunn"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = KvgrunnSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kvgrunn"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == NORGES_GRUNNKART_URL
    assert row["title"] == "Norges grunnkart"
    graatone = registry.get_dataset("kvgrunn:wms.topograatone")
    assert graatone is not None
    assert graatone["access_path"] == TOPOGRAATONE_URL
    assert graatone["title"] == "Topografisk norgeskart gråtone"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kvwms:")
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("hoydegis:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["kvgrunn_service_id"] == "wms.norges_grunnkart"
    assert payload["kvgrunn_service_href"] == NORGES_GRUNNKART_URL
    assert payload["kvgrunn_service_title"] == "Norges grunnkart"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = KvgrunnSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == NORGES_GRUNNKART_URL
    assert result.table_id == "wms.norges_grunnkart"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Norges_grunnkart"}
    assert by_value["Norges_grunnkart"]["measure"] == "Name"
    dims = json.loads(by_value["Norges_grunnkart"]["dimensions_json"])
    assert dims["Title"] == "Norges grunnkart"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == NORGES_GRUNNKART_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_name() -> None:
    cells = cells_from_kvgrunn(TOPOGRAATONE_XML)
    assert [value for _measure, value, _dims in cells] == [
        "topograatone",
        "kd_arealdekkeflate",
    ]
    measure, value, dims = cells[0]
    assert measure == "Name"
    assert value == "topograatone"
    assert dims["Title"] == "Graatone"
    assert "Abstract" not in dims
    assert cells_from_kvgrunn(NORGES_GRUNNKART_XML) == [
        ("Name", "Norges_grunnkart", {"Title": "Norges grunnkart"})
    ]
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_kvgrunn(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_kvgrunn(HTML_ERROR)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_kvgrunn("<WMS_Capabilities></WMS_Capabilities>")


def test_is_kvgrunn_url_accepts_only_leftover_grunnkart_paths() -> None:
    assert is_kvgrunn_url(TOPOGRAATONE_URL)
    assert is_kvgrunn_url(NORGES_GRUNNKART_URL)
    assert kvgrunn_table_id(TOPOGRAATONE_URL) == "wms.topograatone"
    assert kvgrunn_table_id(NORGES_GRUNNKART_URL) == "wms.norges_grunnkart"
    assert not is_kvgrunn_url(WMS_URL)
    assert not is_kvgrunn_url(WMTS_URL)
    assert not is_kvwms_url(TOPOGRAATONE_URL)
    assert not is_kvwms_url(NORGES_GRUNNKART_URL)
    assert is_kvwms_url(WMS_URL)
    assert is_kvwms_url(WMTS_URL)
    assert not is_kvgrunn_url("https://data.norge.no/datasets/x")
    assert not is_kvgrunn_url(None)


def test_limit_and_offset_slice_printed_documents() -> None:
    source = KvgrunnSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "wms.topograatone"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["wms.norges_grunnkart"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
