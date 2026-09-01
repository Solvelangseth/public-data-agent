from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nibiorest import (
    NibiorestSource,
    cells_from_nibiorest,
    is_nibiorest_url,
    nibiorest_table_id,
)
from public_data_agent.sources.nibiowms import (
    printed_child_urls,
    printed_getcapabilities,
    printed_service_id,
)

LIST_URL = "https://nibio.no/tjenester/wms-tjenester"
CHILD_OK_URL = "https://nibio.no/tjenester/wms-tjenester/wms-tjeneste-markslag-ok"
CHILD_SKOG_URL = "https://nibio.no/tjenester/wms-tjenester/wms-tjenester-copernicus"
CHILD_GARDS_URL = (
    "https://nibio.no/tjenester/wms-tjenester/webservice-og-wms-for-gardskart"
)
OK_RASTER_URL = (
    "https://wms.nibio.no/cgi-bin/ok_raster?request=getcapabilities&service=wms"
)
HRL_URL = (
    "https://wms.nibio.no/cgi-bin/hrl?VERSION=1.3.0&REQUEST=GetCapabilities&service=wms"
)
GLE_URL = (
    "https://wms.nibio.no/cgi-bin/riparian_zones_GLE"
    "?VERSION=1.3.0&REQUEST=GetCapabilities&service=wms"
)
VERNSKOG_URL = (
    "https://wms.nibio.no/cgi-bin/vernskog2"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
NIBIO_WEATHER_URL = "https://irh.nibio.no/weather/parameter"
KART_NIBIO_URL = "https://kart.nibio.no/cgi-bin/hrl"
DATASET_ID = "nibiorest:hrl"

PARENT_HTML = """
<html><body>
<a href="/tjenester/wms-tjenester/wms-tjeneste-markslag-ok">Markslag</a>
<a href="/tjenester/wms-tjenester/_/attachment/file.pdf">attachment</a>
<a href="/tjenester/wms-tjenester">WMS-tjenester</a>
<a href="/tjenester/wms-tjenester/wms-tjenester-copernicus">Copernicus</a>
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
<a href="https://wms.nibio.no/cgi-bin/hrl?VERSION=1.3.0&amp;REQUEST=GetCapabilities&amp;service=wms">her</a>
<a href="https://wms.nibio.no/cgi-bin/skog?service=wms">skog</a>
<a href="https://wms.nibio.no/cgi-bin/riparian_zones_GLE?VERSION=1.3.0&amp;REQUEST=GetCapabilities&amp;service=wms">her</a>
<a href="https://wms.nibio.no/cgi-bin/vernskog2?SERVICE=WMS&amp;VERSION=1.3.0&amp;REQUEST=GetCapabilities">her</a>
</body></html>
"""
CHILD_GARDS_HTML = """
<html><body>
<p>Gardskart has no cgi-bin GetCapabilities.</p>
</body></html>
"""
HRL_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>High_Resolution_Layers</Name>
      <Title>High Resolution Layers 2018</Title>
      <Layer>
        <Name>HRL_Imperviousness</Name>
        <Title>Imperviousness</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>HRL_Grassland</Name>
        <Title>Grassland</Title>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
GLE_HTML = """
<html><head><title>MapServer Message</title></head>
<body>msWMSDispatch(): WMS server error.</body></html>
"""
VERNSKOG_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0">
  <Capability>
    <Layer>
      <Name>VERNSKOG2</Name>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
OK_RASTER_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0">
  <Capability>
    <Layer>
      <Name>ok_raster</Name>
    </Layer>
  </Capability>
</WMS_Capabilities>
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
            HRL_URL: HRL_XML,
            GLE_URL: GLE_HTML,
            VERNSKOG_URL: VERNSKOG_XML,
        }
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == HRL_URL:
            return HRL_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nibiorest fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nibiorest fetch must GET, not POST {url}")


def test_printed_refs_skip_taken_nibiowms_ldirwms_and_html() -> None:
    http = CatalogHttp()
    source = NibiorestSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["hrl"]
    assert [ref.source_native_uri for ref in refs] == [HRL_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "ok_raster" for ref in refs)
    assert all(ref.source_native_id != "vernskog2" for ref in refs)
    assert all(ref.source_native_id != "her" for ref in refs)
    assert all(ref.source_native_id != "skog" for ref in refs)
    assert all(ref.source_native_id != "ar5" for ref in refs)
    assert all(ref.source_native_id != "riparian_zones_GLE" for ref in refs)
    assert all("/_/attachment" not in url for url in http.gets)
    assert GLE_URL in http.gets
    assert CHILD_GARDS_URL in http.gets
    assert OK_RASTER_URL not in http.gets
    assert VERNSKOG_URL not in http.gets


def test_printed_services_keep_document_order() -> None:
    children = printed_child_urls(PARENT_HTML, LIST_URL)
    assert children == [CHILD_OK_URL, CHILD_SKOG_URL, CHILD_GARDS_URL]
    listed = printed_getcapabilities(CHILD_SKOG_HTML, CHILD_SKOG_URL)
    assert [ident for ident, _href, _title in listed] == [
        "hrl",
        "riparian_zones_GLE",
        "vernskog2",
    ]
    assert [href for _ident, href, _title in listed] == [HRL_URL, GLE_URL, VERNSKOG_URL]


def test_printed_service_id_uses_last_cgi_bin_segment() -> None:
    assert printed_service_id(HRL_URL) == "hrl"
    assert printed_service_id("https://wms.nibio.no/cgi-bin/hrl") == "hrl"
    assert printed_service_id("/") is None


def test_nibiorest_is_a_registered_source() -> None:
    assert "nibiorest" in SOURCE_IDS
    assert "nibiowms" in SOURCE_IDS
    assert "ldirwms" in SOURCE_IDS
    assert "nibio" in SOURCE_IDS
    assert "kystnav" in SOURCE_IDS
    assert "mdirwms" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("mattilsyn") + 1] == "nibiorest"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbver") + 1] == "hiwms"
    assert SOURCE_IDS[SOURCE_IDS.index("vegwms") + 1] == "fdkorg"
    assert SOURCE_IDS[SOURCE_IDS.index("fdkorg") + 1] == "brrolletype"
    assert SOURCE_IDS[SOURCE_IDS.index("brrolletype") + 1] == "brkommuner"
    assert SOURCE_IDS[SOURCE_IDS.index("brkommuner") + 1] == "nguminer"
    assert SOURCE_IDS[SOURCE_IDS.index("nguminer") + 1] == "brrollegruppe"
    assert SOURCE_IDS[SOURCE_IDS.index("brrollegruppe") + 1] == "mdirgis"
    assert SOURCE_IDS[SOURCE_IDS.index("mdirgis") + 1] == "ssbcorr"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbcorr") + 1] == "bwgis"
    assert SOURCE_IDS[SOURCE_IDS.index("bwgis") + 1] == "broppdater"
    assert SOURCE_IDS[SOURCE_IDS.index("broppdater") + 1] == "kifylker"
    assert SOURCE_IDS[SOURCE_IDS.index("kifylker") + 1] == "brrepresent"
    assert SOURCE_IDS[SOURCE_IDS.index("brrepresent") + 1] == "brenheter"
    assert SOURCE_IDS[SOURCE_IDS.index("brenheter") + 1] == "ssbvar"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbvar") + 1] == "nordatlas"
    assert SOURCE_IDS[SOURCE_IDS.index("nordatlas") + 1] == "brunder"
    assert SOURCE_IDS[SOURCE_IDS.index("brunder") + 1] == "kikommuner"
    assert SOURCE_IDS[SOURCE_IDS.index("kikommuner") + 1] == "fbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("fbgis") + 1] == "stperioder"
    assert SOURCE_IDS[SOURCE_IDS.index("stperioder") + 1] == "nibioar50"
    assert SOURCE_IDS[SOURCE_IDS.index("nibioar50") + 1] == "brorgformen"
    assert SOURCE_IDS[SOURCE_IDS.index("brorgformen") + 1] == "crinst"
    assert SOURCE_IDS[SOURCE_IDS.index("crinst") + 1] == "stsaker"
    assert SOURCE_IDS[SOURCE_IDS.index("stsaker") + 1] == "ssbsubj"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbsubj") + 1] == "stkomiteer"
    assert SOURCE_IDS[SOURCE_IDS.index("stkomiteer") + 1] == "crunit"
    assert SOURCE_IDS[-1] == "crunit"
    assert "nibiorest" in SOURCE_IDS
    assert "fdirwms" in SOURCE_IDS
    assert "avinorgis" in SOURCE_IDS
    assert "brorgform" in SOURCE_IDS
    assert "ssbver" in SOURCE_IDS
    source = build_source("nibiorest")
    assert isinstance(source, NibiorestSource)
    assert source.source_id == "nibiorest"
    assert build_source("nibiowms").source_id == "nibiowms"
    assert build_source("ldirwms").source_id == "ldirwms"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NibiorestSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nibiorest"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == HRL_URL
    assert row["title"] == "hrl"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("nibiowms:")
    assert not str(row["id"]).startswith("ldirwms:")
    assert not str(row["id"]).startswith("nibio:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nibiorest_service_id"] == "hrl"
    assert payload["nibiorest_service_href"] == HRL_URL
    assert payload["nibiorest_service_title"] == "hrl"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = NibiorestSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == HRL_URL
    assert result.table_id == "hrl"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {
        "High_Resolution_Layers",
        "HRL_Imperviousness",
        "HRL_Grassland",
    }
    assert by_value["HRL_Imperviousness"]["measure"] == "Name"
    dims = json.loads(by_value["HRL_Imperviousness"]["dimensions_json"])
    assert dims["Title"] == "Imperviousness"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == HRL_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_name() -> None:
    cells = cells_from_nibiorest(HRL_XML)
    assert [value for _measure, value, _dims in cells] == [
        "High_Resolution_Layers",
        "HRL_Imperviousness",
        "HRL_Grassland",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "HRL_Imperviousness"
    assert dims["Title"] == "Imperviousness"
    assert "Abstract" not in dims
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_nibiorest(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_nibiorest(GLE_HTML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_nibiorest("<WMS_Capabilities></WMS_Capabilities>")


def test_is_nibiorest_url_accepts_only_leftover_cgi_bin() -> None:
    assert is_nibiorest_url(HRL_URL)
    assert nibiorest_table_id(HRL_URL) == "hrl"
    assert not is_nibiorest_url(OK_RASTER_URL)
    assert not is_nibiorest_url(VERNSKOG_URL)
    assert not is_nibiorest_url(LIST_URL)
    assert not is_nibiorest_url(NIBIO_WEATHER_URL)
    assert not is_nibiorest_url(KART_NIBIO_URL)
    assert not is_nibiorest_url("https://data.norge.no/datasets/x")
    assert not is_nibiorest_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = NibiorestSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "hrl"
    ]
    assert source.list_dataset_refs(limit=1, offset=1) == []
