from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ngu import is_ngu_url
from public_data_agent.sources.nguminer import (
    INDUSTRIMINERALER_URL,
    METALLER_URL,
    NguminerSource,
    cells_from_nguminer,
    is_nguminer_url,
    nguminer_table_id,
    printed_service_id,
    printed_services,
)
from public_data_agent.sources.nguwms import is_nguwms_url

DATASET_ID = "nguminer:IndustrimineralerWMS3"
LOSMASSER_URL = (
    "https://geo.ngu.no/mapserver/LosmasserWMS3"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
KRITISKE_URL = (
    "https://geo.ngu.no/mapserver/KritiskeMineralerWMS"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
BERGGRUNN_URL = (
    "https://geo.ngu.no/mapserver/BerggrunnWMS3"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
API_FEATURES_URL = "https://geo.ngu.no/api/features/ankringsforhold"
KART_URL = "https://geo.ngu.no/kart/"
NADAG_URL = (
    "https://geo.ngu.no/geoserver/nadag/ows"
    "?request=GetCapabilities&service=WMS&version=1.3.0"
)

INDUSTRI_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>IndustrimineralerWMS3</Title>
    <OnlineResource href="https://geo.ngu.no/mapserver/IndustrimineralerWMS3?"/>
  </Service>
  <Capability>
    <Layer>
      <Title>root</Title>
      <Layer>
        <Name>IndustrimineralerWMS3</Name>
        <Title>IndustrimineralerWMS3</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>Punkt_Industrimineraler</Name>
        <Title>Industrimineraler Alle</Title>
      </Layer>
      <Layer>
        <Name></Name>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

METALLER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>MetallerWMS2</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>MetallerWMS2</Name>
      <Title>MetallerWMS2</Title>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

HTML_ERROR = """
<html><head><title>MapServer Message</title></head>
<body>msWMSDispatch(): WMS server error.</body></html>
"""

DEFAULT_PAGES = {
    INDUSTRIMINERALER_URL: INDUSTRI_XML,
    METALLER_URL: METALLER_XML,
}


class CatalogHttp:
    def __init__(self, pages: dict[str, str] | None = None) -> None:
        self.gets: list[str] = []
        self.pages = pages or DEFAULT_PAGES

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url in self.pages:
            return self.pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == INDUSTRIMINERALER_URL:
            return INDUSTRI_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nguminer fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nguminer fetch must GET, not POST {url}")


def test_printed_refs_keep_live_xml_and_skip_html() -> None:
    http = CatalogHttp()
    source = NguminerSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "IndustrimineralerWMS3",
        "MetallerWMS2",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        INDUSTRIMINERALER_URL,
        METALLER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "WMS" for ref in refs)
    assert all(ref.source_native_id != "LosmasserWMS3" for ref in refs)
    assert all(ref.source_native_id != "KritiskeMineralerWMS" for ref in refs)
    assert all(ref.source_native_id != "BerggrunnWMS3" for ref in refs)
    assert all(ref.source_native_id != "ankringsforhold" for ref in refs)
    assert LOSMASSER_URL not in [ref.source_native_uri for ref in refs]
    assert KRITISKE_URL not in [ref.source_native_uri for ref in refs]
    assert BERGGRUNN_URL not in [ref.source_native_uri for ref in refs]
    assert API_FEATURES_URL not in [ref.source_native_uri for ref in refs]
    assert KART_URL not in [ref.source_native_uri for ref in refs]
    assert NADAG_URL not in [ref.source_native_uri for ref in refs]


def test_printed_refs_skip_html_capabilities() -> None:
    pages = dict(DEFAULT_PAGES)
    pages[INDUSTRIMINERALER_URL] = HTML_ERROR
    http = CatalogHttp(pages)
    source = NguminerSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["MetallerWMS2"]
    assert INDUSTRIMINERALER_URL in http.gets


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(INDUSTRI_XML, INDUSTRIMINERALER_URL)
    assert [ident for ident, _href, _title in listed] == ["IndustrimineralerWMS3"]
    assert [href for _ident, href, _title in listed] == [INDUSTRIMINERALER_URL]
    assert [title for _ident, _href, title in listed] == ["IndustrimineralerWMS3"]
    listed = printed_services(METALLER_XML, METALLER_URL)
    assert [ident for ident, _href, _title in listed] == ["MetallerWMS2"]
    assert [title for _ident, _href, title in listed] == ["MetallerWMS2"]


def test_printed_service_id_uses_last_mapserver_segment() -> None:
    assert printed_service_id(INDUSTRIMINERALER_URL) == "IndustrimineralerWMS3"
    assert printed_service_id(METALLER_URL) == "MetallerWMS2"
    assert printed_service_id(LOSMASSER_URL) == "LosmasserWMS3"
    assert printed_service_id(BERGGRUNN_URL) == "BerggrunnWMS3"
    assert printed_service_id("/") is None


def test_nguminer_is_a_registered_source() -> None:
    assert "nguminer" in SOURCE_IDS
    assert "ngu" in SOURCE_IDS
    assert "nguwms" in SOURCE_IDS
    assert "vegwms" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "hiwms" in SOURCE_IDS
    assert "nbagency" in SOURCE_IDS
    assert "nbdps" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("hiwms") + 1] == "nbagency"
    assert SOURCE_IDS[SOURCE_IDS.index("nbagency") + 1] == "kvtopo"
    assert SOURCE_IDS[SOURCE_IDS.index("kvtopo") + 1] == "nbdps"
    assert SOURCE_IDS[SOURCE_IDS.index("nbdps") + 1] == "vegwms"
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
    assert SOURCE_IDS[SOURCE_IDS.index("crunit") + 1] == "barmark"
    assert SOURCE_IDS[SOURCE_IDS.index("barmark") + 1] == "crproj"
    assert SOURCE_IDS[SOURCE_IDS.index("crproj") + 1] == "ssbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbgis") + 1] == "stpartier"
    assert SOURCE_IDS[SOURCE_IDS.index("stpartier") + 1] == "crbio"
    assert SOURCE_IDS[SOURCE_IDS.index("crbio") + 1] == "nibioar5f"
    assert SOURCE_IDS[SOURCE_IDS.index("nibioar5f") + 1] == "kvfkb"
    assert SOURCE_IDS[SOURCE_IDS.index("kvfkb") + 1] == "crperson"
    assert SOURCE_IDS[SOURCE_IDS.index("crperson") + 1] == "stsporre"
    assert SOURCE_IDS[-1] == "stsporre"
    source = build_source("nguminer")
    assert isinstance(source, NguminerSource)
    assert source.source_id == "nguminer"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NguminerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nguminer"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == INDUSTRIMINERALER_URL
    assert row["title"] == "IndustrimineralerWMS3"
    metaller = registry.get_dataset("nguminer:MetallerWMS2")
    assert metaller is not None
    assert metaller["access_path"] == METALLER_URL
    assert metaller["title"] == "MetallerWMS2"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ngu:")
    assert not str(row["id"]).startswith("nguwms:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nguminer_service_id"] == "IndustrimineralerWMS3"
    assert payload["nguminer_service_href"] == INDUSTRIMINERALER_URL
    assert payload["nguminer_service_title"] == "IndustrimineralerWMS3"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = NguminerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == INDUSTRIMINERALER_URL
    assert result.table_id == "IndustrimineralerWMS3"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"IndustrimineralerWMS3", "Punkt_Industrimineraler"}
    assert by_value["IndustrimineralerWMS3"]["measure"] == "Name"
    dims = json.loads(by_value["IndustrimineralerWMS3"]["dimensions_json"])
    assert dims["Title"] == "IndustrimineralerWMS3"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == INDUSTRIMINERALER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_name() -> None:
    cells = cells_from_nguminer(INDUSTRI_XML)
    assert [value for _measure, value, _dims in cells] == [
        "IndustrimineralerWMS3",
        "Punkt_Industrimineraler",
    ]
    measure, value, dims = cells[0]
    assert measure == "Name"
    assert value == "IndustrimineralerWMS3"
    assert dims["Title"] == "IndustrimineralerWMS3"
    assert "Abstract" not in dims
    assert cells_from_nguminer(METALLER_XML) == [
        ("Name", "MetallerWMS2", {"Title": "MetallerWMS2"})
    ]
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_nguminer(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_nguminer(HTML_ERROR)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_nguminer("<WMS_Capabilities></WMS_Capabilities>")


def test_is_nguminer_url_accepts_only_leftover_mineral_paths() -> None:
    assert is_nguminer_url(INDUSTRIMINERALER_URL)
    assert is_nguminer_url(METALLER_URL)
    assert nguminer_table_id(INDUSTRIMINERALER_URL) == "IndustrimineralerWMS3"
    assert nguminer_table_id(METALLER_URL) == "MetallerWMS2"
    assert not is_nguminer_url(LOSMASSER_URL)
    assert not is_nguminer_url(KRITISKE_URL)
    assert not is_nguminer_url(BERGGRUNN_URL)
    assert not is_nguminer_url(API_FEATURES_URL)
    assert not is_nguminer_url(KART_URL)
    assert not is_nguminer_url(NADAG_URL)
    assert not is_nguwms_url(INDUSTRIMINERALER_URL)
    assert not is_nguwms_url(METALLER_URL)
    assert not is_ngu_url(INDUSTRIMINERALER_URL)
    assert not is_ngu_url(METALLER_URL)
    assert is_nguwms_url(LOSMASSER_URL)
    assert is_ngu_url(API_FEATURES_URL)
    assert not is_nguminer_url("https://data.norge.no/datasets/x")
    assert not is_nguminer_url(None)


def test_limit_and_offset_slice_printed_documents() -> None:
    source = NguminerSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "IndustrimineralerWMS3"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["MetallerWMS2"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
