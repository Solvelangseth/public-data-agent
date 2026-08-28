from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.rawms import (
    KULTURMILJOER_URL,
    KULTURMINNER2_URL,
    RawmsSource,
    cells_from_rawms,
    is_rawms_url,
    printed_service_id,
    rawms_table_id,
)

MABYGIS_URL = (
    "https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_Askeladden/FeatureServer?f=json"
)
REST_RO_URL = (
    "https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_rest_ro/FeatureServer/0?f=json"
)
NIBIOWMS_URL = (
    "https://wms.nibio.no/cgi-bin/ok_raster?request=getcapabilities&service=wms"
)
DATASET_ID = "rawms:kulturminner2"

KULTURMINNER2_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>Kulturminner</Name>
      <Title>Kulturminner - Lokaliteter, Enkeltminner og Sikringssoner</Title>
      <Layer>
        <Name>Enkeltminner</Name>
        <Title>Enkeltminner</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>Lokaliteter</Name>
        <Title>Lokaliteter</Title>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
KULTURMILJOER_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0">
  <Capability>
    <Layer>
      <Name>Kulturmiljoer</Name>
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
            KULTURMINNER2_URL: KULTURMINNER2_XML,
            KULTURMILJOER_URL: KULTURMILJOER_XML,
        }

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url in self.pages:
            return self.pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == KULTURMINNER2_URL:
            return KULTURMINNER2_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"rawms fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"rawms fetch must GET, not POST {url}")


def test_printed_refs_keep_live_xml_and_skip_html() -> None:
    http = CatalogHttp()
    source = RawmsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["kulturminner2", "kulturmiljoer"]
    assert [ref.source_native_uri for ref in refs] == [KULTURMINNER2_URL, KULTURMILJOER_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "WMS" for ref in refs)
    assert all(ref.source_native_id != "MABYGIS_Askeladden" for ref in refs)
    assert MABYGIS_URL not in [ref.source_native_uri for ref in refs]


def test_printed_refs_skip_html_capabilities() -> None:
    http = CatalogHttp(
        {
            KULTURMINNER2_URL: KULTURMINNER2_XML,
            KULTURMILJOER_URL: HTML_ERROR,
        }
    )
    source = RawmsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["kulturminner2"]
    assert KULTURMILJOER_URL in http.gets


def test_printed_service_id_uses_last_wms_segment() -> None:
    assert printed_service_id(KULTURMINNER2_URL) == "kulturminner2"
    assert printed_service_id(KULTURMILJOER_URL) == "kulturmiljoer"
    assert printed_service_id("/") is None


def test_rawms_is_a_registered_source() -> None:
    assert "rawms" in SOURCE_IDS
    assert "ragis" in SOURCE_IDS
    assert "riksantikvaren" in SOURCE_IDS
    assert "nibiowms" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    source = build_source("rawms")
    assert isinstance(source, RawmsSource)
    assert source.source_id == "rawms"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = RawmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "rawms"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == KULTURMINNER2_URL
    assert row["title"] == "kulturminner2"
    other = registry.get_dataset("rawms:kulturmiljoer")
    assert other is not None
    assert other["access_path"] == KULTURMILJOER_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ragis:")
    assert not str(row["id"]).startswith("riksantikvaren:")
    assert not str(row["id"]).startswith("nibiowms:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["rawms_service_id"] == "kulturminner2"
    assert payload["rawms_service_href"] == KULTURMINNER2_URL
    assert payload["rawms_service_title"] == "kulturminner2"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = RawmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == KULTURMINNER2_URL
    assert result.table_id == "kulturminner2"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Kulturminner", "Enkeltminner", "Lokaliteter"}
    assert by_value["Enkeltminner"]["measure"] == "Name"
    dims = json.loads(by_value["Enkeltminner"]["dimensions_json"])
    assert dims["Title"] == "Enkeltminner"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == KULTURMINNER2_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_name() -> None:
    cells = cells_from_rawms(KULTURMINNER2_XML)
    assert [value for _measure, value, _dims in cells] == [
        "Kulturminner",
        "Enkeltminner",
        "Lokaliteter",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "Enkeltminner"
    assert dims["Title"] == "Enkeltminner"
    assert "Abstract" not in dims
    assert cells_from_rawms(KULTURMILJOER_XML) == [("Name", "Kulturmiljoer", {})]
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_rawms(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_rawms(HTML_ERROR)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_rawms("<WMS_Capabilities></WMS_Capabilities>")


def test_is_rawms_url_accepts_only_wms_host_path() -> None:
    assert is_rawms_url(KULTURMINNER2_URL)
    assert is_rawms_url(KULTURMILJOER_URL)
    assert rawms_table_id(KULTURMINNER2_URL) == "kulturminner2"
    assert rawms_table_id(KULTURMILJOER_URL) == "kulturmiljoer"
    assert not is_rawms_url(MABYGIS_URL)
    assert not is_rawms_url(REST_RO_URL)
    assert not is_rawms_url(NIBIOWMS_URL)
    assert not is_rawms_url("https://data.norge.no/datasets/x")
    assert not is_rawms_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = RawmsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "kulturminner2"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["kulturmiljoer"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
