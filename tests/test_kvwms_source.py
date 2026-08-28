from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kvwms import (
    KvwmsSource,
    WMTS_URL,
    WMS_URL,
    cells_from_kvwms,
    is_kvwms_url,
    kvwms_table_id,
    printed_services,
)

HOYDEGIS_URL = "https://hoydedata.no/arcgis/rest/services?f=json"
GEONORGE_URL = "https://kartkatalog.geonorge.no/api/search"
NPIINTERN_URL = "https://geodata.npolar.no/arcgis/rest/services/Basisdata_Intern?f=json"
NVEGIS_URL = "https://gis3.nve.no/map/rest/services?f=json"
DATASET_ID = "kvwms:wms.topo"

WMS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>Topografisk norgeskart</Title>
    <OnlineResource href="https://wms.geonorge.no/skwms1/wms.topo?"/>
  </Service>
  <Capability>
    <Layer>
      <Title>root</Title>
      <Layer>
        <Name>topo</Name>
        <Title>Topo</Title>
      </Layer>
      <Layer>
        <Name>kd_hoydelag</Name>
        <Title>Hoydelag</Title>
      </Layer>
      <Layer>
        <Name></Name>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

WMTS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Capabilities>
  <ServiceIdentification>
    <Title>Kartverket WMTS v1</Title>
  </ServiceIdentification>
  <OperationsMetadata>
    <Operation name="GetCapabilities">
      <DCP>
        <HTTP>
          <Get href="https://cache.kartverket.no/v1/wmts?"/>
        </HTTP>
      </DCP>
    </Operation>
  </OperationsMetadata>
  <Contents>
    <Layer>
      <Identifier>topo</Identifier>
      <Title>Topo</Title>
    </Layer>
    <Layer>
      <Identifier>topograatone</Identifier>
      <Title>Graatone</Title>
    </Layer>
    <Layer>
      <Identifier></Identifier>
    </Layer>
  </Contents>
</Capabilities>
"""


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_text(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == WMS_URL:
            return WMS_XML
        if url == WMTS_URL:
            return WMTS_XML
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == WMS_URL:
            return WMS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None):
        raise AssertionError(f"kvwms fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None):
        raise AssertionError(f"kvwms fetch must GET, not POST {url}")


def test_printed_refs_keep_document_order() -> None:
    source = KvwmsSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["wms.topo", "wmts"]
    assert [ref.source_native_uri for ref in refs] == [WMS_URL, WMTS_URL]
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "WMS" for ref in refs)


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(WMS_XML, WMS_URL)
    assert [ident for ident, _href, _title in listed] == ["wms.topo"]
    assert [href for _ident, href, _title in listed] == [WMS_URL]
    listed = printed_services(WMTS_XML, WMTS_URL)
    assert [ident for ident, _href, _title in listed] == ["wmts"]
    assert [href for _ident, href, _title in listed] == [WMTS_URL]


def test_kvwms_is_a_registered_source() -> None:
    assert "kvwms" in SOURCE_IDS
    assert "npiintern" in SOURCE_IDS
    assert "hoydegis" in SOURCE_IDS
    source = build_source("kvwms")
    assert isinstance(source, KvwmsSource)
    assert source.source_id == "kvwms"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = KvwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kvwms"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == WMS_URL
    assert row["title"] == "Topografisk norgeskart"
    wmts = registry.get_dataset("kvwms:wmts")
    assert wmts is not None
    assert wmts["access_path"] == WMTS_URL
    assert wmts["title"] == "Kartverket WMTS v1"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("hoydegis:")
    assert not str(row["id"]).startswith("hoydedata:")
    assert not str(row["id"]).startswith("npiintern:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["kvwms_service_id"] == "wms.topo"
    assert payload["kvwms_service_href"] == WMS_URL
    assert payload["kvwms_service_title"] == "Topografisk norgeskart"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_layer_names(tmp_path: Path) -> None:
    source = KvwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == WMS_URL
    assert result.table_id == "wms.topo"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"topo", "kd_hoydelag"}
    assert by_value["topo"]["measure"] == "Name"
    dims = json.loads(by_value["topo"]["dimensions_json"])
    assert dims["Title"] == "Topo"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == WMS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_identifier() -> None:
    wms_cells = cells_from_kvwms(WMS_XML)
    assert [(measure, value) for measure, value, _dims in wms_cells] == [
        ("Name", "topo"),
        ("Name", "kd_hoydelag"),
    ]
    assert wms_cells[0][2]["Title"] == "Topo"
    wmts_cells = cells_from_kvwms(WMTS_XML)
    assert [(measure, value) for measure, value, _dims in wmts_cells] == [
        ("Identifier", "topo"),
        ("Identifier", "topograatone"),
    ]
    assert wmts_cells[1][2]["Title"] == "Graatone"
    with pytest.raises(ValueError, match="not XML"):
        cells_from_kvwms(None)
    with pytest.raises(ValueError, match="named layers"):
        cells_from_kvwms("<WMS_Capabilities><Layer><Name></Name></Layer></WMS_Capabilities>")


def test_is_kvwms_url_accepts_only_leftover_paths() -> None:
    assert is_kvwms_url(WMS_URL)
    assert is_kvwms_url(WMTS_URL)
    assert kvwms_table_id(WMS_URL) == "wms.topo"
    assert kvwms_table_id(WMTS_URL) == "wmts"
    assert not is_kvwms_url(HOYDEGIS_URL)
    assert not is_kvwms_url(GEONORGE_URL)
    assert not is_kvwms_url(NPIINTERN_URL)
    assert not is_kvwms_url(NVEGIS_URL)
    assert not is_kvwms_url("https://data.norge.no/datasets/x")
    assert not is_kvwms_url(None)


def test_limit_and_offset_slice_printed_documents() -> None:
    source = KvwmsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "wms.topo"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["wmts"]
