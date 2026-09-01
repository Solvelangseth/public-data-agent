from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.mdirgis import (
    MdirgisSource,
    SEARCH_URL,
    cells_from_mdirgis,
    is_mdirgis_url,
    mdirgis_table_id,
    printed_leftover_services,
    printed_service_id,
)
from public_data_agent.sources.mdirwms import is_mdirwms_url
from public_data_agent.sources.miljogis import is_miljogis_url

VILLREIN_URL = (
    "https://kart.miljodirektoratet.no/arcgis/services/villrein/MapServer/WMSServer"
    "?request=GetCapabilities&service=WMS"
)
SNO_URL = (
    "https://kart.miljodirektoratet.no/arcgis/services/snoscooterloyper/MapServer/"
    "WMSServer?service=wms&version=1.3.0&request=getCapabilities"
)
PETRO_URL = (
    "https://kart.miljodirektoratet.no/arcgis/services/petroleumsvirksomhet/mapserver/"
    "WMSServer?request=GetCapabilities&service=WMS"
)
INDUSTRI_URL = (
    "https://kart3.miljodirektoratet.no/arcgis/services/industri/MapServer/WMSServer"
    "?service=WMS&request=GetCapabilities"
)
VANNMILO_URL = (
    "https://kart3.miljodirektoratet.no/arcgis/services/vannmiljo/MapServer/WMSServer"
    "?service=WMS&request=GetCapabilities"
)
HAV_URL = (
    "https://kart.miljodirektoratet.no/geoserver/miljoverdi_hav/wms"
    "?service=wms&version=1.1.1&request=getcapabilities"
)
MILJOGIS_REST_URL = (
    "https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/"
    "MapServer?f=json"
)
HTML_URL = (
    "https://kart.miljodirektoratet.no/arcgis/services/htmlmdirgis/MapServer/WMSServer"
    "?service=WMS&request=GetCapabilities"
)
EXCEPTION_URL = (
    "https://kart.miljodirektoratet.no/arcgis/services/kartleggingsenheter_nin/"
    "MapServer/WmsServer"
)
NIBIO_URL = (
    "https://wms.nibio.no/cgi-bin/ok_raster?request=getcapabilities&service=wms"
)
DATASET_ID = "mdirgis:villrein"

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
            "Uuid": "vannmiljo-wms",
            "Title": "Vannmiljø WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": VANNMILO_URL,
            "Type": "service",
        },
        {
            "Uuid": "miljogis-rest",
            "Title": "Anadrome laksefisk REST",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "W3C:REST",
            "DistributionUrl": MILJOGIS_REST_URL,
            "Type": "service",
        },
        {
            "Uuid": "villrein-wms",
            "Title": "Villreinområder WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": VILLREIN_URL,
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
            "Uuid": "sno-wms",
            "Title": "Snøscooterløyper WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": SNO_URL,
            "Type": "service",
        },
        {
            "Uuid": "servicelayer",
            "Title": "Villrein layer",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": VILLREIN_URL,
            "Type": "servicelayer",
        },
        {
            "Uuid": "petro-404",
            "Title": "Petroleumsvirksomhet WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": PETRO_URL,
            "Type": "service",
        },
        {
            "Uuid": "html-mdirgis",
            "Title": "HTML leftover",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "exception-mdirgis",
            "Title": "Kartleggingsenheter NiN WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": EXCEPTION_URL,
            "Type": "service",
        },
        {
            "Uuid": "nibiowms-row",
            "Title": "ok_raster leftover",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": NIBIO_URL,
            "Type": "service",
        },
        {"nested": True},
    ],
}
VILLREIN_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>villrein</Name>
      <Title>Villrein</Title>
      <Layer>
        <Name>Villreinomrade</Name>
        <Title>Villreinområde</Title>
        <Abstract>skip</Abstract>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
SNO_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0">
  <Capability>
    <Layer>
      <Name>snoscooterloyper</Name>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>villrein:omrade</Name>
      <Title>Villreinområde</Title>
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
            VILLREIN_URL: VILLREIN_XML,
            SNO_URL: SNO_XML,
            HTML_URL: GLE_HTML,
            EXCEPTION_URL: EXCEPTION_XML,
        }
        if url == PETRO_URL:
            raise RuntimeError("HTTP 404")
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == VILLREIN_URL:
            return VILLREIN_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"mdirgis fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"mdirgis fetch must GET, not POST {url}")


def test_printed_refs_skip_mdirwms_miljogis_html_and_exception() -> None:
    http = CatalogHttp()
    source = MdirgisSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["villrein", "snoscooterloyper"]
    assert [ref.source_native_uri for ref in refs] == [VILLREIN_URL, SNO_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "industri" for ref in refs)
    assert all(ref.source_native_id != "vannmiljo" for ref in refs)
    assert all(ref.source_native_id != "miljoverdi_hav_wms" for ref in refs)
    assert all(ref.source_native_id != "anadrome_laksefisk" for ref in refs)
    assert all(ref.source_native_id != "htmlmdirgis" for ref in refs)
    assert all(ref.source_native_id != "petroleumsvirksomhet" for ref in refs)
    assert all(ref.source_native_id != "kartleggingsenheter_nin" for ref in refs)
    assert HTML_URL in http.gets
    assert PETRO_URL in http.gets
    assert EXCEPTION_URL in http.gets
    assert INDUSTRI_URL not in http.gets
    assert VANNMILO_URL not in http.gets
    assert HAV_URL not in http.gets
    assert MILJOGIS_REST_URL not in http.gets
    assert NIBIO_URL not in http.gets
    assert any(url.startswith(f"{SEARCH_URL}?") for url in http.gets)


def test_printed_leftover_services_keep_document_order_and_unique_ids() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == [
        "villrein",
        "snoscooterloyper",
        "petroleumsvirksomhet",
        "htmlmdirgis",
        "kartleggingsenheter_nin",
    ]
    assert [href for _ident, href, _title in listed] == [
        VILLREIN_URL,
        SNO_URL,
        PETRO_URL,
        HTML_URL,
        EXCEPTION_URL,
    ]


def test_printed_service_id_uses_printed_path_segment() -> None:
    assert printed_service_id(VILLREIN_URL) == "villrein"
    assert printed_service_id(SNO_URL) == "snoscooterloyper"
    assert printed_service_id(PETRO_URL) == "petroleumsvirksomhet"
    assert printed_service_id(EXCEPTION_URL) == "kartleggingsenheter_nin"
    assert printed_service_id("/") is None


def test_mdirgis_is_a_registered_source() -> None:
    assert "mdirgis" in SOURCE_IDS
    assert "mdirwms" in SOURCE_IDS
    assert "miljogis" in SOURCE_IDS
    assert "miljodir" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "nbdps" in SOURCE_IDS
    assert "vegwms" in SOURCE_IDS
    assert "fdkorg" in SOURCE_IDS
    assert "brrolletype" in SOURCE_IDS
    assert "brkommuner" in SOURCE_IDS
    assert "nguminer" in SOURCE_IDS
    assert "brrollegruppe" in SOURCE_IDS
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
    assert SOURCE_IDS[-1] == "brorgformen"
    source = build_source("mdirgis")
    assert isinstance(source, MdirgisSource)
    assert source.source_id == "mdirgis"
    assert build_source("mdirwms").source_id == "mdirwms"
    assert build_source("miljogis").source_id == "miljogis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = MdirgisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "mdirgis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == VILLREIN_URL
    assert row["title"] == "Villreinområder WMS"
    sno = registry.get_dataset("mdirgis:snoscooterloyper")
    assert sno is not None
    assert sno["access_path"] == SNO_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("mdirwms:")
    assert not str(row["id"]).startswith("miljogis:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["mdirgis_service_id"] == "villrein"
    assert payload["mdirgis_service_href"] == VILLREIN_URL
    assert payload["mdirgis_service_title"] == "Villreinområder WMS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = MdirgisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == VILLREIN_URL
    assert result.table_id == "villrein"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"villrein", "Villreinomrade"}
    assert by_value["Villreinomrade"]["measure"] == "Name"
    dims = json.loads(by_value["Villreinomrade"]["dimensions_json"])
    assert dims["Title"] == "Villreinområde"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == VILLREIN_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_and_feature_type_name() -> None:
    cells = cells_from_mdirgis(VILLREIN_XML)
    assert [value for _measure, value, _dims in cells] == ["villrein", "Villreinomrade"]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "Villreinomrade"
    assert dims["Title"] == "Villreinområde"
    assert "Abstract" not in dims
    assert cells_from_mdirgis(SNO_XML) == [("Name", "snoscooterloyper", {})]
    wfs_cells = cells_from_mdirgis(WFS_XML)
    assert wfs_cells == [
        ("Name", "villrein:omrade", {"Title": "Villreinområde"})
    ]
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_mdirgis(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_mdirgis(GLE_HTML)
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_mdirgis(EXCEPTION_XML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_mdirgis("<WMS_Capabilities></WMS_Capabilities>")


def test_is_mdirgis_url_accepts_leftover_wrappers_and_skips_owned() -> None:
    assert is_mdirgis_url(VILLREIN_URL)
    assert is_mdirgis_url(SNO_URL)
    assert is_mdirgis_url(PETRO_URL)
    assert mdirgis_table_id(VILLREIN_URL) == "villrein"
    assert mdirgis_table_id(SNO_URL) == "snoscooterloyper"
    assert not is_mdirgis_url(INDUSTRI_URL)
    assert not is_mdirgis_url(VANNMILO_URL)
    assert not is_mdirgis_url(HAV_URL)
    assert not is_mdirgis_url(MILJOGIS_REST_URL)
    assert not is_mdirgis_url(NIBIO_URL)
    assert not is_mdirgis_url(SEARCH_URL)
    assert not is_mdirgis_url("https://data.norge.no/datasets/x")
    assert not is_mdirgis_url(None)
    assert is_mdirwms_url(INDUSTRI_URL)
    assert is_mdirwms_url(HAV_URL)
    assert not is_mdirwms_url(VILLREIN_URL)
    assert is_miljogis_url(MILJOGIS_REST_URL)
    assert not is_miljogis_url(VILLREIN_URL)


def test_limit_and_offset_slice_printed_services() -> None:
    source = MdirgisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "villrein"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["snoscooterloyper"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
