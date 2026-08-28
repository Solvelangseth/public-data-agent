from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ldirwms import (
    LdirwmsSource,
    SEARCH_URL,
    cells_from_ldirwms,
    is_ldirwms_url,
    ldirwms_table_id,
    printed_service_id,
    printed_wms_services,
)

VERNSKOG_URL = (
    "https://wms.nibio.no/cgi-bin/vernskog2"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
REINDRIFT_URL = (
    "https://reindrift.nibio.no/cgi-bin/reindrift"
    "?request=GetCapabilities&service=WMS"
)
SKOGBRUK_URL = (
    "https://wms.nibio.no/cgi-bin/skogbruksplan"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
MIS_URL = "https://wms.nibio.no/cgi-bin/mis?request=getcapabilities&service=wms"
OK_RASTER_URL = (
    "https://wms.nibio.no/cgi-bin/ok_raster?request=getcapabilities&service=wms"
)
HTML_URL = (
    "https://wms.nibio.no/cgi-bin/htmlldir"
    "?VERSION=1.3.0&REQUEST=GetCapabilities&service=wms"
)
NIBIO_WEATHER_URL = "https://irh.nibio.no/weather/parameter"
GEONORGE_REST_URL = "https://ws.geonorge.no/hoydedata/v1/datakilder"
MISSING_URL = (
    "https://wms.nibio.no/cgi-bin/missingldir"
    "?SERVICE=WMS&REQUEST=GetCapabilities"
)
DATASET_ID = "ldirwms:vernskog2"

CATALOG = {
    "NumFound": 8,
    "Results": [
        {
            "Uuid": "7f854c3d-4c65-4581-ab94-087a76564ee2",
            "Title": "Vernskog",
            "Organization": "Landbruksdirektoratet",
            "DistributionProtocol": "GEONORGE:DOWNLOAD",
            "DistributionUrl": "https://kart8.nibio.no/api/capabilities/",
            "Type": "dataset",
        },
        {
            "Uuid": "6b58021d-9c91-425a-9c67-7e424f007c1b",
            "Title": "Vernskog - WMS",
            "Organization": "Landbruksdirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": VERNSKOG_URL,
            "Type": "service",
        },
        {
            "Uuid": "e324a2da-b7d5-40f7-9f9a-2e045174dc80",
            "Title": "Reindrift - Beitehage - WFS",
            "Organization": "Landbruksdirektoratet",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": "https://wfs02.nibio.no/cgi-bin/rein/beitehage?service=wfs&request=getcapabilities",
            "Type": "service",
        },
        {
            "Uuid": "ff879537-4031-4e80-bff0-87d0e0638a7f",
            "Title": "Reindrift - WMS",
            "Organization": "Landbruksdirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": REINDRIFT_URL,
            "Type": "service",
        },
        {
            "Uuid": "ea9232a5-9f84-4804-9906-75fcf485d572",
            "Title": "Reindrift - Samebyrettsavgjørelse - WMS",
            "Organization": "Landbruksdirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": REINDRIFT_URL,
            "Type": "servicelayer",
        },
        {
            "Uuid": "nibiowms-ok-raster",
            "Title": "ok_raster leftover",
            "Organization": "Landbruksdirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": OK_RASTER_URL,
            "Type": "service",
        },
        {
            "Uuid": "html-ldir",
            "Title": "HTML leftover",
            "Organization": "Landbruksdirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "missing-404",
            "Title": "Missing WMS",
            "Organization": "Landbruksdirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MISSING_URL,
            "Type": "service",
        },
        {
            "Uuid": "barkbille",
            "Title": "Barkbilleovervåking",
            "Organization": "Norsk institutt for bioøkonomi",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": "https://wms.nibio.no/cgi-bin/barkbille?request=getcapabilities&service=wms",
            "Type": "servicelayer",
        },
        {"nested": True},
    ],
}
VERNSKOG_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>VERNSKOG2</Name>
      <Title>Vernskog</Title>
      <Layer>
        <Name>vernskog_alle</Name>
        <Title>Alle vernskog</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>Vernskog_fjell</Name>
        <Title>Fjell</Title>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
REINDRIFT_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0">
  <Capability>
    <Layer>
      <Name>REINDRIFT</Name>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
GLE_HTML = """
<html><head><title>MapServer Message</title></head>
<body>msWMSDispatch(): WMS server error.</body></html>
"""


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url.startswith(f"{SEARCH_URL}?"):
            return CATALOG
        raise AssertionError(f"unexpected GET {url}")

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        pages = {
            VERNSKOG_URL: VERNSKOG_XML,
            REINDRIFT_URL: REINDRIFT_XML,
            HTML_URL: GLE_HTML,
        }
        if url == MISSING_URL:
            raise RuntimeError("HTTP 404")
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == VERNSKOG_URL:
            return VERNSKOG_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ldirwms fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ldirwms fetch must GET, not POST {url}")


def test_printed_refs_skip_wfs_download_servicelayer_nibiowms_and_html() -> None:
    http = CatalogHttp()
    source = LdirwmsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["vernskog2", "reindrift"]
    assert [ref.source_native_uri for ref in refs] == [VERNSKOG_URL, REINDRIFT_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "ok_raster" for ref in refs)
    assert all(ref.source_native_id != "htmlldir" for ref in refs)
    assert all(ref.source_native_id != "barkbille" for ref in refs)
    assert all(ref.source_native_id != "missingldir" for ref in refs)
    assert HTML_URL in http.gets
    assert MISSING_URL in http.gets
    assert any(url.startswith(f"{SEARCH_URL}?") for url in http.gets)


def test_printed_wms_services_keep_document_order_and_unique_cgi() -> None:
    listed = printed_wms_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == [
        "vernskog2",
        "reindrift",
        "htmlldir",
        "missingldir",
    ]
    assert [href for _ident, href, _title in listed] == [
        VERNSKOG_URL,
        REINDRIFT_URL,
        HTML_URL,
        MISSING_URL,
    ]
    assert [title for _ident, _href, title in listed] == [
        "Vernskog - WMS",
        "Reindrift - WMS",
        "HTML leftover",
        "Missing WMS",
    ]


def test_printed_service_id_uses_last_cgi_bin_segment() -> None:
    assert printed_service_id(VERNSKOG_URL) == "vernskog2"
    assert printed_service_id(REINDRIFT_URL) == "reindrift"
    assert printed_service_id("/") is None


def test_ldirwms_is_a_registered_source() -> None:
    assert "ldirwms" in SOURCE_IDS
    assert "geonorge" in SOURCE_IDS
    assert "nibio" in SOURCE_IDS
    assert "nibiowms" in SOURCE_IDS
    assert "ragis" in SOURCE_IDS
    source = build_source("ldirwms")
    assert isinstance(source, LdirwmsSource)
    assert source.source_id == "ldirwms"
    assert build_source("nibiowms").source_id == "nibiowms"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = LdirwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ldirwms"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == VERNSKOG_URL
    assert row["title"] == "Vernskog - WMS"
    rein = registry.get_dataset("ldirwms:reindrift")
    assert rein is not None
    assert rein["access_path"] == REINDRIFT_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("nibio:")
    assert not str(row["id"]).startswith("nibiowms:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["ldirwms_service_id"] == "vernskog2"
    assert payload["ldirwms_service_href"] == VERNSKOG_URL
    assert payload["ldirwms_service_title"] == "Vernskog - WMS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = LdirwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == VERNSKOG_URL
    assert result.table_id == "vernskog2"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"VERNSKOG2", "vernskog_alle", "Vernskog_fjell"}
    assert by_value["vernskog_alle"]["measure"] == "Name"
    dims = json.loads(by_value["vernskog_alle"]["dimensions_json"])
    assert dims["Title"] == "Alle vernskog"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == VERNSKOG_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_name() -> None:
    cells = cells_from_ldirwms(VERNSKOG_XML)
    assert [value for _measure, value, _dims in cells] == [
        "VERNSKOG2",
        "vernskog_alle",
        "Vernskog_fjell",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "vernskog_alle"
    assert dims["Title"] == "Alle vernskog"
    assert "Abstract" not in dims
    assert cells_from_ldirwms(REINDRIFT_XML) == [("Name", "REINDRIFT", {})]
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_ldirwms(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_ldirwms(GLE_HTML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_ldirwms("<WMS_Capabilities></WMS_Capabilities>")


def test_is_ldirwms_url_accepts_leftover_hosts_and_skips_nibiowms() -> None:
    assert is_ldirwms_url(VERNSKOG_URL)
    assert is_ldirwms_url(REINDRIFT_URL)
    assert is_ldirwms_url(SKOGBRUK_URL)
    assert is_ldirwms_url(MIS_URL)
    assert ldirwms_table_id(VERNSKOG_URL) == "vernskog2"
    assert ldirwms_table_id(REINDRIFT_URL) == "reindrift"
    assert not is_ldirwms_url(OK_RASTER_URL)
    assert not is_ldirwms_url(SEARCH_URL)
    assert not is_ldirwms_url(NIBIO_WEATHER_URL)
    assert not is_ldirwms_url(GEONORGE_REST_URL)
    assert not is_ldirwms_url("https://data.norge.no/datasets/x")
    assert not is_ldirwms_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = LdirwmsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "vernskog2"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["reindrift"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
