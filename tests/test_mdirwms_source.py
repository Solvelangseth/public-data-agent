from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.mdirwms import (
    MdirwmsSource,
    SEARCH_URL,
    cells_from_mdirwms,
    is_mdirwms_url,
    mdirwms_table_id,
    printed_leftover_services,
    printed_service_id,
)

INDUSTRI_URL = (
    "https://kart3.miljodirektoratet.no/arcgis/services/industri/MapServer/WMSServer"
    "?service=WMS&request=GetCapabilities"
)
HAV_URL = (
    "https://kart.miljodirektoratet.no/geoserver/miljoverdi_hav/wms"
    "?service=wms&version=1.1.1&request=getcapabilities"
)
WFS_URL = (
    "https://kart.miljodirektoratet.no/geoserver/forvaltningsplaner_havomrader/wfs"
    "?Service=WFS&Request=GetCapabilities"
)
MILJOGIS_URL = (
    "https://kart.miljodirektoratet.no/arcgis/services/vern_naturomrader_nin/MapServer/"
    "WMSServer?request=GetCapabilities&service=WMS"
)
NIBIO_URL = (
    "https://wms.nibio.no/cgi-bin/ok_raster?request=getcapabilities&service=wms"
)
NGU_URL = (
    "https://geo.ngu.no/mapserver/LandformerWMS"
    "?REQUEST=GetCapabilities&SERVICE=WMS&VERSION=1.3.0"
)
HTML_URL = (
    "https://kart3.miljodirektoratet.no/arcgis/services/htmlmdir/MapServer/WMSServer"
    "?service=WMS&request=GetCapabilities"
)
MISSING_URL = (
    "https://kart3.miljodirektoratet.no/arcgis/services/missingmdir/MapServer/WMSServer"
    "?service=WMS&request=GetCapabilities"
)
EXCEPTION_URL = (
    "https://kart3.miljodirektoratet.no/arcgis/services/naturtiltak/naturtiltak/"
    "MapServer/WMSServer"
)
MILJOGIS_REST_URL = (
    "https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/"
    "MapServer?f=json"
)
VANNMILO_API = "https://vannmiljoapi.miljodirektoratet.no/api/parameter"
DATASET_ID = "mdirwms:industri"

CATALOG = {
    "NumFound": 10,
    "Results": [
        {
            "Uuid": "download-mdir",
            "Title": "Naturtyper dataset",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "GEONORGE:DOWNLOAD",
            "DistributionUrl": "https://nedlasting.geonorge.no/api/capabilities/",
            "Type": "dataset",
        },
        {
            "Uuid": "industri-wms",
            "Title": "Industri WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": INDUSTRI_URL,
            "Type": "service",
        },
        {
            "Uuid": "miljogis-wrapper",
            "Title": "Natur i verneområder (NiN) WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MILJOGIS_URL,
            "Type": "service",
        },
        {
            "Uuid": "hav-wms",
            "Title": "Miljøverdi, hav WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HAV_URL,
            "Type": "service",
        },
        {
            "Uuid": "hav-wfs",
            "Title": "Forvaltningsplanområder for havområdene WFS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": WFS_URL,
            "Type": "service",
        },
        {
            "Uuid": "servicelayer",
            "Title": "Industri layer",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": INDUSTRI_URL,
            "Type": "servicelayer",
        },
        {
            "Uuid": "nibiowms-row",
            "Title": "ok_raster leftover",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": NIBIO_URL,
            "Type": "service",
        },
        {
            "Uuid": "ngu-row",
            "Title": "Landformer WMS",
            "Organization": "Norges geologiske undersøkelse",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": NGU_URL,
            "Type": "service",
        },
        {
            "Uuid": "html-mdir",
            "Title": "HTML leftover",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "missing-404",
            "Title": "Missing WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MISSING_URL,
            "Type": "service",
        },
        {
            "Uuid": "exception-mdir",
            "Title": "Naturtiltak WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": EXCEPTION_URL,
            "Type": "service",
        },
        {"nested": True},
    ],
}
INDUSTRI_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>industri</Name>
      <Title>Industri</Title>
      <Layer>
        <Name>Utslipp</Name>
        <Title>Utslipp til luft</Title>
        <Abstract>skip</Abstract>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
HAV_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.1.1">
  <Capability>
    <Layer>
      <Name>miljoverdi_hav:verdi</Name>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>forvaltningsplaner_havomrader:omrade</Name>
      <Title>Forvaltningsplanområde</Title>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
"""
GLE_HTML = """
<html><head><title>MapServer Message</title></head>
<body>msWMSDispatch(): WMS server error.</body></html>
"""
EXCEPTION_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<!DOCTYPE ServiceExceptionReport SYSTEM "http://schemas.opengis.net/wms/1.1.1/WMS_exception_1_1_1.dtd">
<ServiceExceptionReport version="1.1.1">
  <ServiceException>Missing GetCapabilities request</ServiceException>
</ServiceExceptionReport>
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
            INDUSTRI_URL: INDUSTRI_XML,
            HAV_URL: HAV_XML,
            WFS_URL: WFS_XML,
            HTML_URL: GLE_HTML,
            EXCEPTION_URL: EXCEPTION_XML,
        }
        if url == MISSING_URL:
            raise RuntimeError("HTTP 404")
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == INDUSTRI_URL:
            return INDUSTRI_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"mdirwms fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"mdirwms fetch must GET, not POST {url}")


def test_printed_refs_skip_miljogis_nibiowms_html_and_exception() -> None:
    http = CatalogHttp()
    source = MdirwmsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "industri",
        "miljoverdi_hav_wms",
        "forvaltningsplaner_havomrader_wfs",
    ]
    assert [ref.source_native_uri for ref in refs] == [INDUSTRI_URL, HAV_URL, WFS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "vern_naturomrader_nin" for ref in refs)
    assert all(ref.source_native_id != "ok_raster" for ref in refs)
    assert all(ref.source_native_id != "htmlmdir" for ref in refs)
    assert all(ref.source_native_id != "missingmdir" for ref in refs)
    assert all(ref.source_native_id != "naturtiltak" for ref in refs)
    assert HTML_URL in http.gets
    assert MISSING_URL in http.gets
    assert EXCEPTION_URL in http.gets
    assert MILJOGIS_URL not in http.gets
    assert NIBIO_URL not in http.gets
    assert NGU_URL not in http.gets
    assert any(url.startswith(f"{SEARCH_URL}?") for url in http.gets)


def test_printed_leftover_services_keep_document_order_and_unique_ids() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == [
        "industri",
        "miljoverdi_hav_wms",
        "forvaltningsplaner_havomrader_wfs",
        "htmlmdir",
        "missingmdir",
        "naturtiltak",
    ]
    assert [href for _ident, href, _title in listed] == [
        INDUSTRI_URL,
        HAV_URL,
        WFS_URL,
        HTML_URL,
        MISSING_URL,
        EXCEPTION_URL,
    ]


def test_printed_service_id_uses_printed_path_segment() -> None:
    assert printed_service_id(INDUSTRI_URL) == "industri"
    assert printed_service_id(HAV_URL) == "miljoverdi_hav_wms"
    assert printed_service_id(WFS_URL) == "forvaltningsplaner_havomrader_wfs"
    assert printed_service_id(EXCEPTION_URL) == "naturtiltak"
    assert printed_service_id("/") is None


def test_mdirwms_is_a_registered_source() -> None:
    assert "mdirwms" in SOURCE_IDS
    assert "miljogis" in SOURCE_IDS
    assert "miljodir" in SOURCE_IDS
    assert "kystwfs" in SOURCE_IDS
    source = build_source("mdirwms")
    assert isinstance(source, MdirwmsSource)
    assert source.source_id == "mdirwms"
    assert build_source("miljogis").source_id == "miljogis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = MdirwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "mdirwms"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == INDUSTRI_URL
    assert row["title"] == "Industri WMS"
    hav = registry.get_dataset("mdirwms:miljoverdi_hav_wms")
    assert hav is not None
    assert hav["access_path"] == HAV_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("miljogis:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["mdirwms_service_id"] == "industri"
    assert payload["mdirwms_service_href"] == INDUSTRI_URL
    assert payload["mdirwms_service_title"] == "Industri WMS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = MdirwmsSource(http=CatalogHttp())
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


def test_cells_copy_printed_layer_and_feature_type_name() -> None:
    cells = cells_from_mdirwms(INDUSTRI_XML)
    assert [value for _measure, value, _dims in cells] == ["industri", "Utslipp"]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "Utslipp"
    assert dims["Title"] == "Utslipp til luft"
    assert "Abstract" not in dims
    assert cells_from_mdirwms(HAV_XML) == [("Name", "miljoverdi_hav:verdi", {})]
    wfs_cells = cells_from_mdirwms(WFS_XML)
    assert wfs_cells == [
        ("Name", "forvaltningsplaner_havomrader:omrade", {"Title": "Forvaltningsplanområde"})
    ]
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_mdirwms(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_mdirwms(GLE_HTML)
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_mdirwms(EXCEPTION_XML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_mdirwms("<WMS_Capabilities></WMS_Capabilities>")


def test_is_mdirwms_url_accepts_leftover_hosts_and_skips_miljogis() -> None:
    assert is_mdirwms_url(INDUSTRI_URL)
    assert is_mdirwms_url(HAV_URL)
    assert is_mdirwms_url(WFS_URL)
    assert mdirwms_table_id(INDUSTRI_URL) == "industri"
    assert mdirwms_table_id(HAV_URL) == "miljoverdi_hav_wms"
    assert not is_mdirwms_url(MILJOGIS_URL)
    assert not is_mdirwms_url(MILJOGIS_REST_URL)
    assert not is_mdirwms_url(NIBIO_URL)
    assert not is_mdirwms_url(NGU_URL)
    assert not is_mdirwms_url(SEARCH_URL)
    assert not is_mdirwms_url(VANNMILO_API)
    assert not is_mdirwms_url("https://data.norge.no/datasets/x")
    assert not is_mdirwms_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = MdirwmsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "industri"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["miljoverdi_hav_wms"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
