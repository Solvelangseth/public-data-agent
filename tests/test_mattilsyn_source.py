from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.mattilsyn import (
    MattilsynSource,
    SEARCH_URL,
    cells_from_mattilsyn,
    is_mattilsyn_url,
    mattilsyn_table_id,
    printed_leftover_services,
    printed_service_id,
)
from public_data_agent.sources.mattilsynet import (
    MattilsynetPlantevernSource,
    is_mattilsynet_url,
)

WMS_URL = (
    "https://kart.mattilsynet.no/wmscache/service"
    "?service=WMS&request=GetCapabilities"
)
WFS_URL = (
    "https://kart.mattilsynet.no/wmscache/wfs"
    "?service=WFS&request=GetCapabilities"
)
NIBIO_URL = (
    "https://wms.nibio.no/cgi-bin/ok_raster?request=getcapabilities&service=wms"
)
MILJOGIS_URL = (
    "https://kart.miljodirektoratet.no/arcgis/services/vern_naturomrader_nin/MapServer/"
    "WMSServer?request=GetCapabilities&service=WMS"
)
MDIRWMS_URL = (
    "https://kart3.miljodirektoratet.no/arcgis/services/industri/MapServer/WMSServer"
    "?service=WMS&request=GetCapabilities"
)
HTML_URL = (
    "https://kart.mattilsynet.no/wmscache/htmlmattilsyn"
    "?service=WMS&request=GetCapabilities"
)
MISSING_URL = (
    "https://kart.mattilsynet.no/wmscache/missingmattilsyn"
    "?service=WMS&request=GetCapabilities"
)
PLANTEVERN_URL = "https://api.plantevernmidler.mattilsynet.io/hobby_preparater"
DATASET_ID = "mattilsyn:service"

CATALOG = {
    "NumFound": 10,
    "Results": [
        {
            "Uuid": "mattilsyn-wms",
            "Title": "Mattilsynets WMS",
            "Organization": "Mattilsynet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "mattilsyn-wfs",
            "Title": "Mattilsynet leftover WFS",
            "Organization": "Mattilsynet",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": WFS_URL,
            "Type": "service",
        },
        {
            "Uuid": "servicelayer",
            "Title": "Mattilsynet layer",
            "Organization": "Mattilsynet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "servicelayer",
        },
        {
            "Uuid": "barentswatch-rest",
            "Title": "BarentsWatch Fiskehelse API",
            "Organization": "Mattilsynet",
            "DistributionProtocol": "W3C:REST",
            "Type": "service",
        },
        {
            "Uuid": "nibiowms-row",
            "Title": "ok_raster leftover",
            "Organization": "Mattilsynet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": NIBIO_URL,
            "Type": "service",
        },
        {
            "Uuid": "miljogis-wrapper",
            "Title": "Natur i verneområder (NiN) WMS",
            "Organization": "Mattilsynet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MILJOGIS_URL,
            "Type": "service",
        },
        {
            "Uuid": "mdirwms-row",
            "Title": "Industri WMS",
            "Organization": "Mattilsynet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MDIRWMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "html-mattilsyn",
            "Title": "HTML leftover",
            "Organization": "Mattilsynet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "missing-404",
            "Title": "Missing WMS",
            "Organization": "Mattilsynet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MISSING_URL,
            "Type": "service",
        },
        {
            "Uuid": "other-org",
            "Title": "Mattilsynets WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "service",
        },
        {"nested": True},
    ],
}
WMS_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Service>
    <Title>Mattilsynet cache for eksternt publiserte kartlag</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>Mattilsynet_Vannverk_Inntakspunkter</Name>
      <Title>Mattilsynet_Vannverk_Inntakspunkter</Title>
      <Layer>
        <Name>Mattilsynet_Dyrehold_Produksjonsdyr</Name>
        <Title>Mattilsynet_Dyrehold_Produksjonsdyr</Title>
        <Abstract>skip</Abstract>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>Mattilsynet_Vannverk_Inntakspunkter</Name>
      <Title>Mattilsynet_Vannverk_Inntakspunkter</Title>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
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
            WMS_URL: WMS_XML,
            WFS_URL: WFS_XML,
            HTML_URL: GLE_HTML,
        }
        if url == MISSING_URL:
            raise RuntimeError("HTTP 404")
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == WMS_URL:
            return WMS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"mattilsyn fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"mattilsyn fetch must GET, not POST {url}")


def test_printed_refs_skip_covered_hosts_servicelayer_rest_html_and_404() -> None:
    http = CatalogHttp()
    source = MattilsynSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["service", "wmscache_wfs"]
    assert [ref.source_native_uri for ref in refs] == [WMS_URL, WFS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "ok_raster" for ref in refs)
    assert all(ref.source_native_id != "vern_naturomrader_nin" for ref in refs)
    assert all(ref.source_native_id != "industri" for ref in refs)
    assert all(ref.source_native_id != "htmlmattilsyn" for ref in refs)
    assert all(ref.source_native_id != "missingmattilsyn" for ref in refs)
    assert HTML_URL in http.gets
    assert MISSING_URL in http.gets
    assert NIBIO_URL not in http.gets
    assert MILJOGIS_URL not in http.gets
    assert MDIRWMS_URL not in http.gets
    assert any(url.startswith(f"{SEARCH_URL}?") for url in http.gets)


def test_printed_leftover_services_keep_document_order_and_unique_ids() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == [
        "service",
        "wmscache_wfs",
        "htmlmattilsyn",
        "missingmattilsyn",
    ]
    assert [href for _ident, href, _title in listed] == [
        WMS_URL,
        WFS_URL,
        HTML_URL,
        MISSING_URL,
    ]


def test_printed_service_id_uses_printed_path_segment() -> None:
    assert printed_service_id(WMS_URL) == "service"
    assert printed_service_id(WFS_URL) == "wmscache_wfs"
    assert printed_service_id(HTML_URL) == "htmlmattilsyn"
    assert printed_service_id(MISSING_URL) == "missingmattilsyn"
    assert printed_service_id("/") is None


def test_mattilsyn_is_a_registered_source() -> None:
    assert "mattilsyn" in SOURCE_IDS
    assert "mattilsynet" in SOURCE_IDS
    assert "mdirwms" in SOURCE_IDS
    assert "nibiorest" in SOURCE_IDS
    assert "kystnav" in SOURCE_IDS
    assert "kvgrunn" in SOURCE_IDS
    assert "nibiowms" in SOURCE_IDS
    assert "ldirwms" in SOURCE_IDS
    assert "banegis" in SOURCE_IDS
    assert SOURCE_IDS.index("mattilsyn") > SOURCE_IDS.index("ssclass")
    assert SOURCE_IDS.index("mattilsyn") > SOURCE_IDS.index("banegis")
    assert SOURCE_IDS[SOURCE_IDS.index("mattilsyn") + 1] == "nibiorest"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbver") + 1] == "hiwms"
    assert SOURCE_IDS[SOURCE_IDS.index("vegwms") + 1] == "fdkorg"
    assert SOURCE_IDS[SOURCE_IDS.index("fdkorg") + 1] == "brrolletype"
    assert SOURCE_IDS[SOURCE_IDS.index("brrolletype") + 1] == "brkommuner"
    assert "nibiorest" in SOURCE_IDS
    assert "fdirwms" in SOURCE_IDS
    assert "avinorgis" in SOURCE_IDS
    assert "brorgform" in SOURCE_IDS
    assert "ssbver" in SOURCE_IDS
    assert "mattilsyn" != "mattilsynet"
    source = build_source("mattilsyn")
    assert isinstance(source, MattilsynSource)
    assert source.source_id == "mattilsyn"
    plantevern = build_source("mattilsynet")
    assert isinstance(plantevern, MattilsynetPlantevernSource)
    assert plantevern.source_id == "mattilsynet"
    assert build_source("mdirwms").source_id == "mdirwms"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = MattilsynSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "mattilsyn"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == WMS_URL
    assert row["title"] == "Mattilsynets WMS"
    wfs = registry.get_dataset("mattilsyn:wmscache_wfs")
    assert wfs is not None
    assert wfs["access_path"] == WFS_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("mattilsynet:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["mattilsyn_service_id"] == "service"
    assert payload["mattilsyn_service_href"] == WMS_URL
    assert payload["mattilsyn_service_title"] == "Mattilsynets WMS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = MattilsynSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == WMS_URL
    assert result.table_id == "service"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {
        "Mattilsynet_Vannverk_Inntakspunkter",
        "Mattilsynet_Dyrehold_Produksjonsdyr",
    }
    assert by_value["Mattilsynet_Dyrehold_Produksjonsdyr"]["measure"] == "Name"
    dims = json.loads(by_value["Mattilsynet_Dyrehold_Produksjonsdyr"]["dimensions_json"])
    assert dims["Title"] == "Mattilsynet_Dyrehold_Produksjonsdyr"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == WMS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_and_feature_type_name() -> None:
    cells = cells_from_mattilsyn(WMS_XML)
    assert [value for _measure, value, _dims in cells] == [
        "Mattilsynet_Vannverk_Inntakspunkter",
        "Mattilsynet_Dyrehold_Produksjonsdyr",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "Mattilsynet_Dyrehold_Produksjonsdyr"
    assert dims["Title"] == "Mattilsynet_Dyrehold_Produksjonsdyr"
    assert "Abstract" not in dims
    wfs_cells = cells_from_mattilsyn(WFS_XML)
    assert wfs_cells == [
        (
            "Name",
            "Mattilsynet_Vannverk_Inntakspunkter",
            {"Title": "Mattilsynet_Vannverk_Inntakspunkter"},
        )
    ]
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_mattilsyn(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_mattilsyn(GLE_HTML)
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_mattilsyn("<ServiceExceptionReport></ServiceExceptionReport>")
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_mattilsyn("<WMS_Capabilities></WMS_Capabilities>")


def test_is_mattilsyn_url_accepts_leftover_host_only() -> None:
    assert is_mattilsyn_url(WMS_URL)
    assert is_mattilsyn_url(WFS_URL)
    assert mattilsyn_table_id(WMS_URL) == "service"
    assert mattilsyn_table_id(WFS_URL) == "wmscache_wfs"
    assert not is_mattilsyn_url(PLANTEVERN_URL)
    assert not is_mattilsyn_url(NIBIO_URL)
    assert not is_mattilsyn_url(MILJOGIS_URL)
    assert not is_mattilsyn_url(MDIRWMS_URL)
    assert not is_mattilsyn_url(SEARCH_URL)
    assert not is_mattilsyn_url("https://data.norge.no/datasets/x")
    assert not is_mattilsyn_url(None)
    assert is_mattilsynet_url(PLANTEVERN_URL)
    assert not is_mattilsynet_url(WMS_URL)


def test_limit_and_offset_slice_printed_services() -> None:
    source = MattilsynSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "service"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["wmscache_wfs"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
