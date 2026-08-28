from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nguwms import (
    NguwmsSource,
    cells_from_nguwms,
    is_nguwms_url,
    nguwms_table_id,
    printed_getcapabilities,
    printed_pager_urls,
    printed_service_id,
)

LIST_URL = "https://www.ngu.no/taxonomy/term/36"
PAGE1_URL = "https://www.ngu.no/taxonomy/term/36/?page=1"
LOSMASSER_URL = (
    "https://geo.ngu.no/mapserver/LosmasserWMS3"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
GNIST_URL = (
    "https://geo.ngu.no/mapserver/GnistWMS"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
KRITISKE_URL = (
    "https://geo.ngu.no/mapserver/KritiskeMineralerWMS"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
GEOTREAT_URL = "https://geo.ngu.no/mapserver/GeotreatWMS2"
BERGGRUNN_URL = (
    "https://geo.ngu.no/mapserver/BerggrunnWMS3"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
API_FEATURES_URL = "https://geo.ngu.no/api/features/ankringsforhold"
KART_URL = "https://geo.ngu.no/kart/"
NIBIO_WMS_URL = (
    "https://wms.nibio.no/cgi-bin/ok_raster?request=getcapabilities&service=wms"
)
KVWMS_URL = "https://wms.geonorge.no/skwms1/wms.topo?service=WMS&request=GetCapabilities"
DATASET_ID = "nguwms:LosmasserWMS3"

PAGE0_HTML = """
<html><body>
<div class="field__item">https://geo.ngu.no/mapserver/LosmasserWMS3?SERVICE=WMS&amp;VERSION=1.3.0&amp;REQUEST=GetCapabilities</div>
<div class="field__item">https://geo.ngu.no/mapserver/GnistWMS?SERVICE=WMS&amp;VERSION=1.3.0&amp;REQUEST=GetCapabilities</div>
<div class="field__item">https://geo.ngu.no/mapserver/KritiskeMineralerWMS?SERVICE=WMS&amp;VERSION=1.3.0&amp;REQUEST=GetCapabilities</div>
<div class="field__item">https://geo.ngu.no/mapserver/GeotreatWMS2</div>
<div class="field__item">https://geo.ngu.no/api/features/ankringsforhold</div>
<div class="field__item">https://geo.ngu.no/kart/</div>
<a href="/en/taxonomy/term/36?page=1">English</a>
<a href="?page=1">page 1</a>
</body></html>
"""
PAGE1_HTML = """
<html><body>
<div class="field__item">https://geo.ngu.no/mapserver/BerggrunnWMS3?SERVICE=WMS&amp;VERSION=1.3.0&amp;REQUEST=GetCapabilities</div>
</body></html>
"""
LOSMASSER_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>LosmasserWMS3</Name>
      <Title>Losmasser</Title>
      <Layer>
        <Name>losmasser</Name>
        <Title>Losmasser layer</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>losmasser_thickness</Name>
        <Title>Thickness</Title>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
BERGGRUNN_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0">
  <Capability>
    <Layer>
      <Name>BerggrunnWMS3</Name>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
GNIST_HTML = """
<html><head><title>MapServer Message</title></head>
<body>msWMSDispatch(): WMS server error.</body></html>
"""


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        parsed = urlsplit(url)
        path = parsed.path.rstrip("/")
        if url == LIST_URL or (path == "/taxonomy/term/36" and not parsed.query):
            return PAGE0_HTML
        if path == "/taxonomy/term/36" and parsed.query == "page=1":
            return PAGE1_HTML
        if url == KRITISKE_URL:
            raise RuntimeError("404")
        pages = {
            LOSMASSER_URL: LOSMASSER_XML,
            GNIST_URL: GNIST_HTML,
            BERGGRUNN_URL: BERGGRUNN_XML,
        }
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == LOSMASSER_URL:
            return LOSMASSER_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nguwms fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nguwms fetch must GET, not POST {url}")


def test_printed_refs_skip_html_404_no_query_api_features_and_kart() -> None:
    http = CatalogHttp()
    source = NguwmsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["LosmasserWMS3", "BerggrunnWMS3"]
    assert [ref.source_native_uri for ref in refs] == [LOSMASSER_URL, BERGGRUNN_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "GeotreatWMS2" for ref in refs)
    assert all(ref.source_native_id != "GnistWMS" for ref in refs)
    assert all(ref.source_native_id != "KritiskeMineralerWMS" for ref in refs)
    assert all(ref.source_native_id != "ankringsforhold" for ref in refs)
    assert all("/api/features" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/kart/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/en/taxonomy/term/36" not in url for url in http.gets)
    assert GNIST_URL in http.gets
    assert KRITISKE_URL in http.gets
    assert any(urlsplit(url).query == "page=1" for url in http.gets)
    assert GEOTREAT_URL not in http.gets


def test_printed_services_keep_document_order() -> None:
    pagers = printed_pager_urls(PAGE0_HTML, LIST_URL)
    assert pagers == [PAGE1_URL]
    listed = printed_getcapabilities(PAGE0_HTML)
    assert [ident for ident, _href, _title in listed] == [
        "LosmasserWMS3",
        "GnistWMS",
        "KritiskeMineralerWMS",
    ]
    assert [href for _ident, href, _title in listed] == [
        LOSMASSER_URL,
        GNIST_URL,
        KRITISKE_URL,
    ]
    later = printed_getcapabilities(PAGE1_HTML)
    assert [ident for ident, _href, _title in later] == ["BerggrunnWMS3"]
    assert [href for _ident, href, _title in later] == [BERGGRUNN_URL]


def test_printed_service_id_uses_last_mapserver_segment() -> None:
    assert printed_service_id(LOSMASSER_URL) == "LosmasserWMS3"
    assert printed_service_id("https://geo.ngu.no/mapserver/BerggrunnWMS3") == "BerggrunnWMS3"
    assert printed_service_id("/") is None


def test_nguwms_is_a_registered_source() -> None:
    assert "nguwms" in SOURCE_IDS
    assert "ngu" in SOURCE_IDS
    assert "ldirwms" in SOURCE_IDS
    assert "frivillig" in SOURCE_IDS
    assert "sandnes" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("sandnes") + 1] == "nguwms"
    source = build_source("nguwms")
    assert isinstance(source, NguwmsSource)
    assert source.source_id == "nguwms"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NguwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nguwms"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOSMASSER_URL
    assert row["title"] == "LosmasserWMS3"
    berg = registry.get_dataset("nguwms:BerggrunnWMS3")
    assert berg is not None
    assert berg["access_path"] == BERGGRUNN_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ngu:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nguwms_service_id"] == "LosmasserWMS3"
    assert payload["nguwms_service_href"] == LOSMASSER_URL
    assert payload["nguwms_service_title"] == "LosmasserWMS3"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = NguwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == LOSMASSER_URL
    assert result.table_id == "LosmasserWMS3"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {
        "LosmasserWMS3",
        "losmasser",
        "losmasser_thickness",
    }
    assert by_value["losmasser"]["measure"] == "Name"
    dims = json.loads(by_value["losmasser"]["dimensions_json"])
    assert dims["Title"] == "Losmasser layer"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == LOSMASSER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_name() -> None:
    cells = cells_from_nguwms(LOSMASSER_XML)
    assert [value for _measure, value, _dims in cells] == [
        "LosmasserWMS3",
        "losmasser",
        "losmasser_thickness",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "losmasser"
    assert dims["Title"] == "Losmasser layer"
    assert "Abstract" not in dims
    assert cells_from_nguwms(BERGGRUNN_XML) == [("Name", "BerggrunnWMS3", {})]
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_nguwms(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_nguwms(GNIST_HTML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_nguwms("<WMS_Capabilities></WMS_Capabilities>")


def test_is_nguwms_url_accepts_only_mapserver_host_path() -> None:
    assert is_nguwms_url(LOSMASSER_URL)
    assert is_nguwms_url(BERGGRUNN_URL)
    assert nguwms_table_id(LOSMASSER_URL) == "LosmasserWMS3"
    assert nguwms_table_id(BERGGRUNN_URL) == "BerggrunnWMS3"
    assert not is_nguwms_url(LIST_URL)
    assert not is_nguwms_url(API_FEATURES_URL)
    assert not is_nguwms_url(KART_URL)
    assert not is_nguwms_url(NIBIO_WMS_URL)
    assert not is_nguwms_url(KVWMS_URL)
    assert not is_nguwms_url("https://data.norge.no/datasets/x")
    assert not is_nguwms_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = NguwmsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "LosmasserWMS3"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["BerggrunnWMS3"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
