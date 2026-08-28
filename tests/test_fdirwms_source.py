from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.fdirwms import (
    FdirwmsSource,
    SEARCH_URL,
    cells_from_fdirwms,
    is_fdirwms_url,
    fdirwms_table_id,
    printed_leftover_services,
    printed_service_id,
)

WFS_FISKERI_URL = (
    "https://gis.fiskeridir.no/server/services/FiskeridirWFS_fiskeri/MapServer/"
    "WFSServer?SERVICE=WFS&REQUEST=GetCapabilities"
)
WMS_URL = (
    "https://gis.fiskeridir.no/server/services/fiskeridirWMS/MapServer/WMSServer"
    "?service=wms&request=getcapabilities"
)
GEONORGE_WFS_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.fiskeplasserredskap"
    "?service=wfs&request=getcapabilities"
)
ACTIVITY_URL = (
    "https://gis.fiskeridir.no/server/services/fiskeridirWMS_fiskeriaktivtet/"
    "MapServer/WMSServer"
)
FISKERIGIS_WMS_URL = (
    "https://gis.fiskeridir.no/arcgis/services/AIS_density_Norge_2016/MapServer/"
    "WMSServer?request=GetCapabilities&service=WMS"
)
FISKERIGIS_REST_URL = (
    "https://gis.fiskeridir.no/arcgis/rest/services/AIS_density_Norge_2016/"
    "MapServer?f=json"
)
KYSTWMS_URL = "https://services.kystverket.no/wms.ashx?service=WMS&request=GetCapabilities"
KYSTNAV_URL = (
    "https://maps.kystverket.cloudgis.no/enterprise/services/PROD/"
    "nfs_sistop_ekstern_prod/MapServer/WMSServer"
    "?request=GetCapabilities&service=WMS"
)
HAVNEDATA_URL = "https://ogcapitest.kartverket.no/havnedata/v1/collections"
BANEGIS_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.stoysonerjernbanenett"
    "?service=wfs&request=getcapabilities"
)
HTML_URL = (
    "https://gis.fiskeridir.no/server/services/htmlfdir/MapServer/WMSServer"
    "?service=WMS&request=GetCapabilities"
)
MISSING_URL = (
    "https://gis.fiskeridir.no/server/services/missingfdir/MapServer/WMSServer"
    "?service=WMS&request=GetCapabilities"
)
FDIR_API = "https://api.fiskeridir.no/vessel/api"
DATASET_ID = "fdirwms:FiskeridirWFS_fiskeri"

CATALOG = {
    "NumFound": 10,
    "Results": [
        {
            "Uuid": "download-fdir",
            "Title": "Akvakultur dataset",
            "Organization": "Fiskeridirektoratet",
            "DistributionProtocol": "GEONORGE:DOWNLOAD",
            "DistributionUrl": "https://nedlasting.geonorge.no/api/capabilities/",
            "Type": "dataset",
        },
        {
            "Uuid": "wfs-fiskeri",
            "Title": "Fiskeridirektoratets WFS- fiskeri",
            "Organization": "Fiskeridirektoratet",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": WFS_FISKERI_URL,
            "Type": "service",
        },
        {
            "Uuid": "fiskerigis-wrapper",
            "Title": "AIS density WMS",
            "Organization": "Fiskeridirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": FISKERIGIS_WMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "fdir-wms",
            "Title": "Fiskeridirektoratets WMS",
            "Organization": "Fiskeridirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "geonorge-wfs",
            "Title": "Fiskeplasser - redskap WFS",
            "Organization": "Fiskeridirektoratet",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": GEONORGE_WFS_URL,
            "Type": "service",
        },
        {
            "Uuid": "servicelayer",
            "Title": "Fiskeri layer",
            "Organization": "Fiskeridirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "servicelayer",
        },
        {
            "Uuid": "kyst-row",
            "Title": "Kystverket leftover",
            "Organization": "Kystverket",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": KYSTWMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "hi-row",
            "Title": "HI leftover",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "html-fdir",
            "Title": "HTML leftover",
            "Organization": "Fiskeridirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "missing-404",
            "Title": "Missing WMS",
            "Organization": "Fiskeridirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MISSING_URL,
            "Type": "service",
        },
        {
            "Uuid": "activity-499",
            "Title": "Fiskeriaktivitet utenlandske fiskefartøy årlig",
            "Organization": "Fiskeridirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": ACTIVITY_URL,
            "Type": "service",
        },
        {"nested": True},
    ],
}
WFS_FISKERI_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>fiskeri:område</Name>
      <Title>Fiskeområde</Title>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
"""
WMS_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>fiskeridirWMS</Name>
      <Title>Fiskeridirektoratets WMS</Title>
      <Layer>
        <Name>Akvakultur</Name>
        <Title>Akvakulturlokaliteter</Title>
        <Abstract>skip</Abstract>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
GEONORGE_WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>fiskeplasserredskap:redskap</Name>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
"""
GLE_HTML = """
<html><head><title>ArcGIS Server Error</title></head>
<body>Missing GetCapabilities request</body></html>
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
            WFS_FISKERI_URL: WFS_FISKERI_XML,
            WMS_URL: WMS_XML,
            GEONORGE_WFS_URL: GEONORGE_WFS_XML,
            HTML_URL: GLE_HTML,
            ACTIVITY_URL: GLE_HTML,
        }
        if url == MISSING_URL:
            raise RuntimeError("HTTP 404")
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == WFS_FISKERI_URL:
            return WFS_FISKERI_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"fdirwms fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"fdirwms fetch must GET, not POST {url}")


def test_printed_refs_skip_fiskerigis_kyst_html_and_404() -> None:
    http = CatalogHttp()
    source = FdirwmsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "FiskeridirWFS_fiskeri",
        "fiskeridirWMS",
        "wfs.fiskeplasserredskap",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        WFS_FISKERI_URL,
        WMS_URL,
        GEONORGE_WFS_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "AIS_density_Norge_2016" for ref in refs)
    assert all(ref.source_native_id != "htmlfdir" for ref in refs)
    assert all(ref.source_native_id != "missingfdir" for ref in refs)
    assert all(ref.source_native_id != "fiskeridirWMS_fiskeriaktivtet" for ref in refs)
    assert HTML_URL in http.gets
    assert MISSING_URL in http.gets
    assert ACTIVITY_URL in http.gets
    assert FISKERIGIS_WMS_URL not in http.gets
    assert KYSTWMS_URL not in http.gets
    assert any(url.startswith(f"{SEARCH_URL}?") for url in http.gets)


def test_printed_leftover_services_keep_document_order_and_unique_ids() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == [
        "FiskeridirWFS_fiskeri",
        "fiskeridirWMS",
        "wfs.fiskeplasserredskap",
        "htmlfdir",
        "missingfdir",
        "fiskeridirWMS_fiskeriaktivtet",
    ]
    assert [href for _ident, href, _title in listed] == [
        WFS_FISKERI_URL,
        WMS_URL,
        GEONORGE_WFS_URL,
        HTML_URL,
        MISSING_URL,
        ACTIVITY_URL,
    ]


def test_printed_service_id_uses_printed_path_segment() -> None:
    assert printed_service_id(WFS_FISKERI_URL) == "FiskeridirWFS_fiskeri"
    assert printed_service_id(WMS_URL) == "fiskeridirWMS"
    assert printed_service_id(GEONORGE_WFS_URL) == "wfs.fiskeplasserredskap"
    assert printed_service_id(ACTIVITY_URL) == "fiskeridirWMS_fiskeriaktivtet"
    assert printed_service_id("/") is None


def test_fdirwms_is_a_registered_source() -> None:
    assert "fdirwms" in SOURCE_IDS
    assert "fiskerigis" in SOURCE_IDS
    assert "fiskeridir" in SOURCE_IDS
    assert "nibiorest" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("brroller") + 1] == "fdirwms"
    assert SOURCE_IDS[-1] == "fdirwms"
    source = build_source("fdirwms")
    assert isinstance(source, FdirwmsSource)
    assert source.source_id == "fdirwms"
    assert build_source("fiskerigis").source_id == "fiskerigis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = FdirwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "fdirwms"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == WFS_FISKERI_URL
    assert row["title"] == "Fiskeridirektoratets WFS- fiskeri"
    wms = registry.get_dataset("fdirwms:fiskeridirWMS")
    assert wms is not None
    assert wms["access_path"] == WMS_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("fiskerigis:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["fdirwms_service_id"] == "FiskeridirWFS_fiskeri"
    assert payload["fdirwms_service_href"] == WFS_FISKERI_URL
    assert payload["fdirwms_service_title"] == "Fiskeridirektoratets WFS- fiskeri"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_feature_type_name_cells(tmp_path: Path) -> None:
    source = FdirwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == WFS_FISKERI_URL
    assert result.table_id == "FiskeridirWFS_fiskeri"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"fiskeri:område"}
    assert by_value["fiskeri:område"]["measure"] == "Name"
    dims = json.loads(by_value["fiskeri:område"]["dimensions_json"])
    assert dims["Title"] == "Fiskeområde"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == WFS_FISKERI_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_and_feature_type_name() -> None:
    cells = cells_from_fdirwms(WMS_XML)
    assert [value for _measure, value, _dims in cells] == ["fiskeridirWMS", "Akvakultur"]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "Akvakultur"
    assert dims["Title"] == "Akvakulturlokaliteter"
    assert "Abstract" not in dims
    assert cells_from_fdirwms(GEONORGE_WFS_XML) == [
        ("Name", "fiskeplasserredskap:redskap", {})
    ]
    wfs_cells = cells_from_fdirwms(WFS_FISKERI_XML)
    assert wfs_cells == [
        ("Name", "fiskeri:område", {"Title": "Fiskeområde"})
    ]
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_fdirwms(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_fdirwms(GLE_HTML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_fdirwms("<WMS_Capabilities></WMS_Capabilities>")


def test_is_fdirwms_url_accepts_leftover_hosts_and_skips_taken() -> None:
    assert is_fdirwms_url(WFS_FISKERI_URL)
    assert is_fdirwms_url(WMS_URL)
    assert is_fdirwms_url(GEONORGE_WFS_URL)
    assert fdirwms_table_id(WFS_FISKERI_URL) == "FiskeridirWFS_fiskeri"
    assert fdirwms_table_id(WMS_URL) == "fiskeridirWMS"
    assert fdirwms_table_id(GEONORGE_WFS_URL) == "wfs.fiskeplasserredskap"
    assert not is_fdirwms_url(FISKERIGIS_WMS_URL)
    assert not is_fdirwms_url(FISKERIGIS_REST_URL)
    assert not is_fdirwms_url(KYSTWMS_URL)
    assert not is_fdirwms_url(KYSTNAV_URL)
    assert not is_fdirwms_url(HAVNEDATA_URL)
    assert not is_fdirwms_url(BANEGIS_URL)
    assert not is_fdirwms_url(SEARCH_URL)
    assert not is_fdirwms_url(FDIR_API)
    assert not is_fdirwms_url("https://data.norge.no/datasets/x")
    assert not is_fdirwms_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = FdirwmsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "FiskeridirWFS_fiskeri"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["fiskeridirWMS"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
