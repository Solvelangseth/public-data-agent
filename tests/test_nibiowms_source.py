from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nibiowms import (
    NibiowmsSource,
    cells_from_nibiowms,
    is_nibiowms_url,
    nibiowms_table_id,
    printed_child_urls,
    printed_getcapabilities,
    printed_service_id,
)

LIST_URL = "https://nibio.no/tjenester/wms-tjenester"
CHILD_OK_URL = "https://nibio.no/tjenester/wms-tjenester/wms-tjeneste-markslag-ok"
CHILD_SKOG_URL = "https://nibio.no/tjenester/wms-tjenester/wms-tjeneste-skogportal"
CHILD_GARDS_URL = (
    "https://nibio.no/tjenester/wms-tjenester/webservice-og-wms-for-gardskart"
)
OK_RASTER_URL = (
    "https://wms.nibio.no/cgi-bin/ok_raster?request=getcapabilities&service=wms"
)
ARTSDATA_URL = (
    "https://wms.nibio.no/cgi-bin/artsdata?request=getcapabilities&service=wms"
)
GLE_URL = (
    "https://wms.nibio.no/cgi-bin/riparian_zones_GLE"
    "?VERSION=1.3.0&REQUEST=GetCapabilities&service=wms"
)
NIBIO_WEATHER_URL = "https://irh.nibio.no/weather/parameter"
KART_NIBIO_URL = "https://kart.nibio.no/cgi-bin/ok_raster"
DATASET_ID = "nibiowms:ok_raster"

PARENT_HTML = """
<html><body>
<a href="/tjenester/wms-tjenester/wms-tjeneste-markslag-ok">Markslag</a>
<a href="/tjenester/wms-tjenester/_/attachment/file.pdf">attachment</a>
<a href="/tjenester/wms-tjenester">WMS-tjenester</a>
<a href="/tjenester/wms-tjenester/wms-tjeneste-skogportal">Skogportal</a>
<a href="/tjenester/wms-tjenester/webservice-og-wms-for-gardskart">Gardskart</a>
</body></html>
"""
CHILD_OK_HTML = """
<html><body>
<a href="https://wms.nibio.no/cgi-bin/ok_raster?request=getcapabilities&amp;service=wms">her</a>
</body></html>
"""
CHILD_SKOG_HTML = """
<html><body>
<a href="https://wms.nibio.no/cgi-bin/artsdata?request=getcapabilities&amp;service=wms">her</a>
<a href="https://wms.nibio.no/cgi-bin/skog?service=wms">skog</a>
<a href="https://wms.nibio.no/cgi-bin/riparian_zones_GLE?VERSION=1.3.0&amp;REQUEST=GetCapabilities&amp;service=wms">her</a>
</body></html>
"""
CHILD_GARDS_HTML = """
<html><body>
<p>Gardskart has no cgi-bin GetCapabilities.</p>
</body></html>
"""
OK_RASTER_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>ok_raster</Name>
      <Title>OK raster</Title>
      <Layer>
        <Name>ok_raster_data_35</Name>
        <Title>OK 35</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>ok_raster_data_33</Name>
        <Title>OK 33</Title>
      </Layer>
      <Layer>
        <Name>ok_raster_data_32</Name>
        <Title>OK 32</Title>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
ARTSDATA_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0">
  <Capability>
    <Layer>
      <Name>artsdata</Name>
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

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        pages = {
            LIST_URL: PARENT_HTML,
            CHILD_OK_URL: CHILD_OK_HTML,
            CHILD_SKOG_URL: CHILD_SKOG_HTML,
            CHILD_GARDS_URL: CHILD_GARDS_HTML,
            OK_RASTER_URL: OK_RASTER_XML,
            ARTSDATA_URL: ARTSDATA_XML,
            GLE_URL: GLE_HTML,
        }
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == OK_RASTER_URL:
            return OK_RASTER_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nibiowms fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nibiowms fetch must GET, not POST {url}")


def test_printed_refs_skip_attachment_gardskart_and_html_capabilities() -> None:
    http = CatalogHttp()
    source = NibiowmsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["ok_raster", "artsdata"]
    assert [ref.source_native_uri for ref in refs] == [OK_RASTER_URL, ARTSDATA_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "her" for ref in refs)
    assert all(ref.source_native_id != "skog" for ref in refs)
    assert all(ref.source_native_id != "ar5" for ref in refs)
    assert all(ref.source_native_id != "riparian_zones_GLE" for ref in refs)
    assert all("/_/attachment" not in url for url in http.gets)
    assert GLE_URL in http.gets
    assert CHILD_GARDS_URL in http.gets


def test_printed_services_keep_document_order() -> None:
    children = printed_child_urls(PARENT_HTML, LIST_URL)
    assert children == [CHILD_OK_URL, CHILD_SKOG_URL, CHILD_GARDS_URL]
    listed = printed_getcapabilities(CHILD_SKOG_HTML, CHILD_SKOG_URL)
    assert [ident for ident, _href, _title in listed] == [
        "artsdata",
        "riparian_zones_GLE",
    ]
    assert [href for _ident, href, _title in listed] == [ARTSDATA_URL, GLE_URL]


def test_printed_service_id_uses_last_cgi_bin_segment() -> None:
    assert printed_service_id(OK_RASTER_URL) == "ok_raster"
    assert printed_service_id("https://wms.nibio.no/cgi-bin/artsdata") == "artsdata"
    assert printed_service_id("/") is None


def test_nibiowms_is_a_registered_source() -> None:
    assert "nibiowms" in SOURCE_IDS
    assert "nibio" in SOURCE_IDS
    source = build_source("nibiowms")
    assert isinstance(source, NibiowmsSource)
    assert source.source_id == "nibiowms"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NibiowmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nibiowms"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == OK_RASTER_URL
    assert row["title"] == "ok_raster"
    arts = registry.get_dataset("nibiowms:artsdata")
    assert arts is not None
    assert arts["access_path"] == ARTSDATA_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("nibio:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nibiowms_service_id"] == "ok_raster"
    assert payload["nibiowms_service_href"] == OK_RASTER_URL
    assert payload["nibiowms_service_title"] == "ok_raster"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = NibiowmsSource(http=CatalogHttp())
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


def test_cells_copy_printed_layer_name() -> None:
    cells = cells_from_nibiowms(OK_RASTER_XML)
    assert [value for _measure, value, _dims in cells] == [
        "ok_raster",
        "ok_raster_data_35",
        "ok_raster_data_33",
        "ok_raster_data_32",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "ok_raster_data_35"
    assert dims["Title"] == "OK 35"
    assert "Abstract" not in dims
    assert cells_from_nibiowms(ARTSDATA_XML) == [("Name", "artsdata", {})]
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_nibiowms(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_nibiowms(GLE_HTML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_nibiowms("<WMS_Capabilities></WMS_Capabilities>")


def test_is_nibiowms_url_accepts_only_wms_host_path() -> None:
    assert is_nibiowms_url(OK_RASTER_URL)
    assert is_nibiowms_url(ARTSDATA_URL)
    assert nibiowms_table_id(OK_RASTER_URL) == "ok_raster"
    assert nibiowms_table_id(ARTSDATA_URL) == "artsdata"
    assert not is_nibiowms_url(LIST_URL)
    assert not is_nibiowms_url(NIBIO_WEATHER_URL)
    assert not is_nibiowms_url(KART_NIBIO_URL)
    assert not is_nibiowms_url("https://data.norge.no/datasets/x")
    assert not is_nibiowms_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = NibiowmsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "ok_raster"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["artsdata"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
