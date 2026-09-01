from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.mdirgis import is_mdirgis_url
from public_data_agent.sources.mdirwms import is_mdirwms_url
from public_data_agent.sources.miljogis import is_miljogis_url
from public_data_agent.sources.nordatlas import (
    NordatlasSource,
    SEARCH_URL,
    cells_from_nordatlas,
    is_nordatlas_url,
    nordatlas_table_id,
    printed_leftover_services,
    printed_service_id,
)

NORDATLAS_WMS_URL = (
    "http://wms.nordatlas.no/wms.ashx?request=GetCapabilities&service=WMS"
)
NORDATLAS_WFS_DESCRIBE_URL = (
    "http://wms.nordatlas.no/wfs.ashx?service=wfs&request=describefeatureType&version=1.1.0"
)
FYLKESATLAS_URL = (
    "https://kart.fylkesatlas.no/wms.ashx?service=WMS&request=GetCapabilities"
)
BARMARKS_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.barmarksloyper?service=WFS&request=GetCapabilities"
)
HTML_URL = (
    "https://kart.fylkesatlas.no/wms.ashx?service=WMS&request=GetCapabilities&html=1"
)
MISSING_URL = (
    "http://wms.nordatlas.no/wms.ashx?request=GetCapabilities&service=WMS&missing=1"
)
MDIRWMS_URL = (
    "https://kart3.miljodirektoratet.no/arcgis/services/industri/MapServer/WMSServer"
    "?service=WMS&request=GetCapabilities"
)
MILJOGIS_REST_URL = (
    "https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/"
    "MapServer?f=json"
)
MDIRGIS_URL = (
    "https://kart.miljodirektoratet.no/arcgis/services/villrein/MapServer/WMSServer"
    "?request=GetCapabilities&service=WMS"
)
NIBIO_URL = (
    "https://wms.nibio.no/cgi-bin/vernskog2?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
DATASET_ID = "nordatlas:kart.fylkesatlas.no"

CATALOG = {
    "NumFound": 12,
    "Results": [
        {
            "Uuid": "nordatlas-software",
            "Title": "NordAtlas",
            "Organization": "Statsforvalteren",
            "DistributionProtocol": "WWW:LINK-1.0-http--link",
            "DistributionUrl": "http://www.nordatlas.no",
            "Type": "software",
        },
        {
            "Uuid": "nordatlas-wms",
            "Title": "Nordatlas - WMS",
            "Organization": "Statsforvalteren",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": NORDATLAS_WMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "nordatlas-wfs-describe",
            "Title": "Mapserver WFS - www.nordatlas.no",
            "Organization": "Statsforvalteren",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": NORDATLAS_WFS_DESCRIBE_URL,
            "Type": "service",
        },
        {
            "Uuid": "fylkesatlas-wms",
            "Title": "Fylkesatlas Vestland - wms https",
            "Organization": "Statsforvalteren",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": FYLKESATLAS_URL,
            "Type": "service",
        },
        {
            "Uuid": "barmarks-wfs",
            "Title": "Barmarksløyper i Finnmark WFS",
            "Organization": "Statsforvalteren",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": BARMARKS_URL,
            "Type": "service",
        },
        {
            "Uuid": "servicelayer",
            "Title": "Fylkesatlas layer",
            "Organization": "Statsforvalteren",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": FYLKESATLAS_URL,
            "Type": "servicelayer",
        },
        {
            "Uuid": "html-nordatlas",
            "Title": "HTML leftover",
            "Organization": "Statsforvalteren",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "timeout-nordatlas",
            "Title": "Nordatlas missing",
            "Organization": "Statsforvalteren",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MISSING_URL,
            "Type": "service",
        },
        {
            "Uuid": "mdirwms-row",
            "Title": "Industri WMS",
            "Organization": "Statsforvalteren",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MDIRWMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "miljogis-rest",
            "Title": "Anadrome laksefisk REST",
            "Organization": "Statsforvalteren",
            "DistributionProtocol": "W3C:REST",
            "DistributionUrl": MILJOGIS_REST_URL,
            "Type": "service",
        },
        {
            "Uuid": "mdirgis-row",
            "Title": "Villreinområder WMS",
            "Organization": "Statsforvalteren",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MDIRGIS_URL,
            "Type": "service",
        },
        {
            "Uuid": "nibiowms-row",
            "Title": "Vernskog - WMS",
            "Organization": "Landbruksdirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": NIBIO_URL,
            "Type": "service",
        },
        {"nested": True},
    ],
}
FYLKESATLAS_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Service>
    <Title>Fylkesatlas A3 WMS</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>MS</Name>
      <Title>Fylkesatlas A3 WMS</Title>
      <Layer>
        <Name>layer_2391</Name>
        <Title>Fylkesveg</Title>
        <Abstract>skip</Abstract>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
BARMARKS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>app:Barmarksløype</Name>
      <Title>Barmarksløype</Title>
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
            FYLKESATLAS_URL: FYLKESATLAS_XML,
            BARMARKS_URL: BARMARKS_XML,
            HTML_URL: GLE_HTML,
        }
        if url in {NORDATLAS_WMS_URL, MISSING_URL}:
            raise RuntimeError("timeout")
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == FYLKESATLAS_URL:
            return FYLKESATLAS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nordatlas fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nordatlas fetch must GET, not POST {url}")


def test_printed_refs_skip_dead_describe_owned_html_and_other_orgs() -> None:
    http = CatalogHttp()
    source = NordatlasSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "kart.fylkesatlas.no",
        "wfs.barmarksloyper",
    ]
    assert [ref.source_native_uri for ref in refs] == [FYLKESATLAS_URL, BARMARKS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "wms.ashx" for ref in refs)
    assert all(ref.source_native_uri != NORDATLAS_WMS_URL for ref in refs)
    assert all(ref.source_native_uri != NORDATLAS_WFS_DESCRIBE_URL for ref in refs)
    assert HTML_URL in http.gets
    assert NORDATLAS_WMS_URL in http.gets
    assert MISSING_URL in http.gets
    assert NORDATLAS_WFS_DESCRIBE_URL not in http.gets
    assert MDIRWMS_URL not in http.gets
    assert MILJOGIS_REST_URL not in http.gets
    assert MDIRGIS_URL not in http.gets
    assert NIBIO_URL not in http.gets
    assert any("text=Nordatlas" in url for url in http.gets)
    assert any("text=Statsforvalteren" in url for url in http.gets)


def test_printed_leftover_services_keep_document_order_and_unique_hrefs() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == [
        "wms.nordatlas.no",
        "kart.fylkesatlas.no",
        "wfs.barmarksloyper",
        "kart.fylkesatlas.no",
        "wms.nordatlas.no",
    ]
    assert [href for _ident, href, _title in listed] == [
        NORDATLAS_WMS_URL,
        FYLKESATLAS_URL,
        BARMARKS_URL,
        HTML_URL,
        MISSING_URL,
    ]
    assert NORDATLAS_WFS_DESCRIBE_URL not in [href for _ident, href, _title in listed]
    assert MDIRWMS_URL not in [href for _ident, href, _title in listed]
    assert MDIRGIS_URL not in [href for _ident, href, _title in listed]
    assert NIBIO_URL not in [href for _ident, href, _title in listed]


def test_printed_service_id_uses_printed_host_or_path_segment() -> None:
    assert printed_service_id(NORDATLAS_WMS_URL) == "wms.nordatlas.no"
    assert printed_service_id(FYLKESATLAS_URL) == "kart.fylkesatlas.no"
    assert printed_service_id(BARMARKS_URL) == "wfs.barmarksloyper"
    assert printed_service_id("/") is None


def test_nordatlas_is_a_registered_source() -> None:
    assert "nordatlas" in SOURCE_IDS
    assert "mdirgis" in SOURCE_IDS
    assert "mdirwms" in SOURCE_IDS
    assert "miljogis" in SOURCE_IDS
    assert "mattilsyn" in SOURCE_IDS
    assert "nguminer" in SOURCE_IDS
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
    assert SOURCE_IDS[-1] == "stpartier"
    source = build_source("nordatlas")
    assert isinstance(source, NordatlasSource)
    assert source.source_id == "nordatlas"
    assert build_source("mdirgis").source_id == "mdirgis"
    assert build_source("mdirwms").source_id == "mdirwms"
    assert build_source("miljogis").source_id == "miljogis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NordatlasSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nordatlas"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FYLKESATLAS_URL
    assert row["title"] == "Fylkesatlas Vestland - wms https"
    barmarks = registry.get_dataset("nordatlas:wfs.barmarksloyper")
    assert barmarks is not None
    assert barmarks["access_path"] == BARMARKS_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("mdirgis:")
    assert not str(row["id"]).startswith("mdirwms:")
    assert not str(row["id"]).startswith("miljogis:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nordatlas_service_id"] == "kart.fylkesatlas.no"
    assert payload["nordatlas_service_href"] == FYLKESATLAS_URL
    assert payload["nordatlas_service_title"] == "Fylkesatlas Vestland - wms https"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = NordatlasSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == FYLKESATLAS_URL
    assert result.table_id == "kart.fylkesatlas.no"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"MS", "layer_2391"}
    assert by_value["layer_2391"]["measure"] == "Name"
    dims = json.loads(by_value["layer_2391"]["dimensions_json"])
    assert dims["Title"] == "Fylkesveg"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == FYLKESATLAS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_and_feature_type_name() -> None:
    cells = cells_from_nordatlas(FYLKESATLAS_XML)
    assert [value for _measure, value, _dims in cells] == ["MS", "layer_2391"]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "layer_2391"
    assert dims["Title"] == "Fylkesveg"
    assert "Abstract" not in dims
    wfs_cells = cells_from_nordatlas(BARMARKS_XML)
    assert wfs_cells == [
        ("Name", "app:Barmarksløype", {"Title": "Barmarksløype"})
    ]
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_nordatlas(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_nordatlas(GLE_HTML)
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_nordatlas(EXCEPTION_XML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_nordatlas("<WMS_Capabilities></WMS_Capabilities>")


def test_is_nordatlas_url_accepts_leftover_and_skips_owned() -> None:
    assert is_nordatlas_url(NORDATLAS_WMS_URL)
    assert is_nordatlas_url(FYLKESATLAS_URL)
    assert is_nordatlas_url(BARMARKS_URL)
    assert nordatlas_table_id(FYLKESATLAS_URL) == "kart.fylkesatlas.no"
    assert nordatlas_table_id(BARMARKS_URL) == "wfs.barmarksloyper"
    assert nordatlas_table_id(NORDATLAS_WMS_URL) == "wms.nordatlas.no"
    assert not is_nordatlas_url(MDIRWMS_URL)
    assert not is_nordatlas_url(MILJOGIS_REST_URL)
    assert not is_nordatlas_url(MDIRGIS_URL)
    assert not is_nordatlas_url(NIBIO_URL)
    assert not is_nordatlas_url(SEARCH_URL)
    assert not is_nordatlas_url("https://data.norge.no/datasets/x")
    assert not is_nordatlas_url(None)
    assert is_mdirwms_url(MDIRWMS_URL)
    assert is_mdirgis_url(MDIRGIS_URL)
    assert is_miljogis_url(MILJOGIS_REST_URL)
    assert not is_mdirwms_url(FYLKESATLAS_URL)
    assert not is_mdirgis_url(FYLKESATLAS_URL)
    assert not is_miljogis_url(FYLKESATLAS_URL)


def test_limit_and_offset_slice_printed_services() -> None:
    source = NordatlasSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "kart.fylkesatlas.no"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["wfs.barmarksloyper"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
