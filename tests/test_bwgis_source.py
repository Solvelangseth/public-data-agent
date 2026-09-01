from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.bwgis import (
    BwgisSource,
    SEARCH_URL,
    cells_from_bwgis,
    bwgis_table_id,
    is_bwgis_url,
    printed_leftover_services,
    printed_service_id,
)
from public_data_agent.sources.fdirwms import is_fdirwms_url
from public_data_agent.sources.fiskerigis import is_fiskerigis_url
from public_data_agent.sources.havnedata import is_havnedata_url
from public_data_agent.sources.hiwms import is_hiwms_url
from public_data_agent.sources.kystnav import is_kystnav_url
from public_data_agent.sources.kystwfs import is_kystwfs_url
from public_data_agent.sources.kystwms import is_kystwms_url

WMS_URL = (
    "https://geo.barentswatch.no/geoserver/bw/ows"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
WFS_URL = (
    "https://geo.barentswatch.no/geoserver/bw/wfs"
    "?SERVICE=WFS&REQUEST=GetCapabilities"
)
REST_URL = "https://www.barentswatch.no/bwapi/"
KYSTWMS_URL = "https://services.kystverket.no/wms.ashx?service=WMS&request=GetCapabilities"
KYSTWFS_URL = "https://services.kystverket.no/wfs.ashx?service=WFS&request=GetCapabilities"
KYSTNAV_URL = (
    "https://maps.kystverket.cloudgis.no/enterprise/services/PROD/"
    "nfs_sistop_ekstern_prod/MapServer/WMSServer"
    "?request=GetCapabilities&service=WMS"
)
HAVNEDATA_URL = "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/api?f=json"
FISKERIGIS_URL = "https://gis.fiskeridir.no/arcgis/rest/services?f=json"
FDIRWMS_URL = (
    "https://gis.fiskeridir.no/server/services/fiskeridirWMS/MapServer/WMSServer"
    "?service=wms&request=getcapabilities"
)
HIWMS_URL = (
    "https://kart.hi.no/data/fraraadning/ows"
    "?service=WMS&version=1.3.0&request=GetCapabilities"
)
HTML_URL = (
    "https://geo.barentswatch.no/geoserver/htmlbwgis/ows"
    "?SERVICE=WMS&REQUEST=GetCapabilities"
)
MISSING_URL = (
    "https://geo.barentswatch.no/geoserver/missingbwgis/ows"
    "?SERVICE=WMS&REQUEST=GetCapabilities"
)
DATASET_ID = "bwgis:bw_ows"

CATALOG = {
    "NumFound": 10,
    "Results": [
        {
            "Uuid": "bwgis-wms",
            "Title": "BarentsWatch WMS",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "bwgis-wfs",
            "Title": "BarentsWatch WFS",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": WFS_URL,
            "Type": "service",
        },
        {
            "Uuid": "servicelayer",
            "Title": "ILA overvåkningssoner",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "servicelayer",
        },
        {
            "Uuid": "rest-row",
            "Title": "BarentsWatch Fiskehelse API",
            "Organization": "Barentswatch",
            "DistributionProtocol": "W3C:REST",
            "DistributionUrl": REST_URL,
            "Type": "service",
        },
        {
            "Uuid": "kystwms-row",
            "Title": "Kystverket WMS",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": KYSTWMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "kystwfs-row",
            "Title": "Kystverket WFS",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": KYSTWFS_URL,
            "Type": "service",
        },
        {
            "Uuid": "kystnav-row",
            "Title": "Navigasjonsinstallasjoner",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": KYSTNAV_URL,
            "Type": "service",
        },
        {
            "Uuid": "havnedata-row",
            "Title": "Havnedata",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HAVNEDATA_URL,
            "Type": "service",
        },
        {
            "Uuid": "fiskerigis-row",
            "Title": "Fiskeridirektoratet GIS",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": FISKERIGIS_URL,
            "Type": "service",
        },
        {
            "Uuid": "fdirwms-row",
            "Title": "Fiskeridirektoratets WMS",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": FDIRWMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "hiwms-row",
            "Title": "HI leftover WMS",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HIWMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "html-bwgis",
            "Title": "HTML leftover",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "missing-404",
            "Title": "Missing WMS",
            "Organization": "Barentswatch",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MISSING_URL,
            "Type": "service",
        },
        {
            "Uuid": "other-org",
            "Title": "Fiskeridirektoratets WMS",
            "Organization": "Fiskeridirektoratet",
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
    <Title>BarentsWatch WMS</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>fisheryactivity_wms</Name>
      <Title>Fiskeriaktivitet</Title>
      <Layer>
        <Name>icechart_latest</Name>
        <Title>Iskonsentrasjon</Title>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>bw:fishingfacility</Name>
      <Title>Faststående bruk</Title>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
"""
GLE_HTML = """
<html><head><title>GeoServer</title></head>
<body>Not a capabilities document.</body></html>
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
        raise AssertionError(f"bwgis fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"bwgis fetch must GET, not POST {url}")


def test_printed_refs_skip_covered_hosts_servicelayer_rest_html_and_404() -> None:
    http = CatalogHttp()
    source = BwgisSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["bw_ows", "bw_wfs"]
    assert [ref.source_native_uri for ref in refs] == [WMS_URL, WFS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "htmlbwgis_ows" for ref in refs)
    assert all(ref.source_native_id != "missingbwgis_ows" for ref in refs)
    assert HTML_URL in http.gets
    assert MISSING_URL in http.gets
    assert REST_URL not in http.gets
    assert KYSTWMS_URL not in http.gets
    assert KYSTWFS_URL not in http.gets
    assert KYSTNAV_URL not in http.gets
    assert HAVNEDATA_URL not in http.gets
    assert FISKERIGIS_URL not in http.gets
    assert FDIRWMS_URL not in http.gets
    assert HIWMS_URL not in http.gets
    assert any(url.startswith(f"{SEARCH_URL}?") for url in http.gets)


def test_list_stops_after_max_items_live() -> None:
    http = CatalogHttp()
    source = BwgisSource(http=http, max_items=1)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["bw_ows"]
    assert WFS_URL not in http.gets
    assert HTML_URL not in http.gets
    assert MISSING_URL not in http.gets


def test_printed_leftover_services_keep_document_order_and_unique_ids() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == [
        "bw_ows",
        "bw_wfs",
        "htmlbwgis_ows",
        "missingbwgis_ows",
    ]
    assert [href for _ident, href, _title in listed] == [
        WMS_URL,
        WFS_URL,
        HTML_URL,
        MISSING_URL,
    ]


def test_printed_service_id_uses_printed_path_segment() -> None:
    assert printed_service_id(WMS_URL) == "bw_ows"
    assert printed_service_id(WFS_URL) == "bw_wfs"
    assert printed_service_id(HTML_URL) == "htmlbwgis_ows"
    assert printed_service_id(MISSING_URL) == "missingbwgis_ows"
    assert printed_service_id("/") is None


def test_bwgis_is_a_registered_source() -> None:
    assert "bwgis" in SOURCE_IDS
    assert "hiwms" in SOURCE_IDS
    assert "fdirwms" in SOURCE_IDS
    assert "fiskerigis" in SOURCE_IDS
    assert "kystwms" in SOURCE_IDS
    assert "kystwfs" in SOURCE_IDS
    assert "kystnav" in SOURCE_IDS
    assert "havnedata" in SOURCE_IDS
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("hiwms")
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("nbagency")
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("kvtopo")
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("nbdps")
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("vegwms")
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("fdkorg")
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("brrolletype")
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("brkommuner")
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("nguminer")
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("brrollegruppe")
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("mdirgis")
    assert SOURCE_IDS.index("bwgis") > SOURCE_IDS.index("ssbcorr")
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
    assert SOURCE_IDS[-1] == "brenheter"
    source = build_source("bwgis")
    assert isinstance(source, BwgisSource)
    assert source.source_id == "bwgis"
    assert build_source("hiwms").source_id == "hiwms"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = BwgisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "bwgis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == WMS_URL
    assert row["title"] == "BarentsWatch WMS"
    assert row["publisher_name"] is None
    assert row["license"] is None
    wfs = registry.get_dataset("bwgis:bw_wfs")
    assert wfs is not None
    assert wfs["access_path"] == WFS_URL
    assert not str(row["id"]).startswith("hiwms:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()[0]
    )
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["bwgis_service_id"] == "bw_ows"
    assert payload["bwgis_service_href"] == WMS_URL
    assert payload["bwgis_service_title"] == "BarentsWatch WMS"
    registry.close()


def test_fetch_copies_printed_layer_names(tmp_path: Path) -> None:
    source = BwgisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    dataset = registry.get_dataset(DATASET_ID)
    assert dataset is not None
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.http_status == 200
    assert result.request_url == WMS_URL
    assert result.table_id == "bw_ows"
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"fisheryactivity_wms", "icechart_latest"}
    assert by_value["icechart_latest"]["measure"] == "Name"
    dims = json.loads(by_value["icechart_latest"]["dimensions_json"])
    assert dims["Title"] == "Iskonsentrasjon"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == WMS_URL for row in rows)
    registry.close()


def test_cells_from_bwgis_copy_printed_names_only() -> None:
    cells = cells_from_bwgis(WMS_XML)
    assert cells == [
        ("Name", "fisheryactivity_wms", {"Title": "Fiskeriaktivitet"}),
        ("Name", "icechart_latest", {"Title": "Iskonsentrasjon"}),
    ]
    wfs_cells = cells_from_bwgis(WFS_XML)
    assert wfs_cells == [
        ("Name", "bw:fishingfacility", {"Title": "Faststående bruk"}),
    ]
    with pytest.raises(ValueError, match="empty"):
        cells_from_bwgis(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_bwgis(GLE_HTML)
    with pytest.raises(ValueError, match="not WMS/WFS XML"):
        cells_from_bwgis("<ServiceExceptionReport></ServiceExceptionReport>")
    with pytest.raises(ValueError, match="printed no Layer Name"):
        cells_from_bwgis("<WMS_Capabilities></WMS_Capabilities>")


def test_is_bwgis_url_accepts_leftover_host_only() -> None:
    assert is_bwgis_url(WMS_URL)
    assert is_bwgis_url(WFS_URL)
    assert bwgis_table_id(WMS_URL) == "bw_ows"
    assert bwgis_table_id(WFS_URL) == "bw_wfs"
    assert not is_bwgis_url(REST_URL)
    assert not is_bwgis_url(KYSTWMS_URL)
    assert not is_bwgis_url(KYSTWFS_URL)
    assert not is_bwgis_url(KYSTNAV_URL)
    assert not is_bwgis_url(HAVNEDATA_URL)
    assert not is_bwgis_url(FISKERIGIS_URL)
    assert not is_bwgis_url(FDIRWMS_URL)
    assert not is_bwgis_url(HIWMS_URL)
    assert not is_bwgis_url(SEARCH_URL)
    assert not is_bwgis_url(None)
    assert is_kystwms_url(KYSTWMS_URL)
    assert is_kystwfs_url(KYSTWFS_URL)
    assert is_kystnav_url(KYSTNAV_URL)
    assert is_havnedata_url(HAVNEDATA_URL)
    assert is_fiskerigis_url(FISKERIGIS_URL)
    assert is_fdirwms_url(FDIRWMS_URL)
    assert is_hiwms_url(HIWMS_URL)
    assert not is_kystwms_url(WMS_URL)
    assert not is_kystwfs_url(WMS_URL)
    assert not is_kystnav_url(WMS_URL)
    assert not is_havnedata_url(WMS_URL)
    assert not is_fiskerigis_url(WMS_URL)
    assert not is_fdirwms_url(WMS_URL)
    assert not is_hiwms_url(WMS_URL)
