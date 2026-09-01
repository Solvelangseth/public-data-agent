from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.hiwms import (
    HiwmsSource,
    SEARCH_URL,
    cells_from_hiwms,
    hiwms_table_id,
    is_hiwms_url,
    printed_leftover_services,
    printed_service_id,
)
from public_data_agent.sources.hicoverages import is_hicoverages_url
from public_data_agent.sources.himaps import is_himaps_url
from public_data_agent.sources.fiskerigis import is_fiskerigis_url
from public_data_agent.sources.havnedata import is_havnedata_url
from public_data_agent.sources.banegis import is_banegis_url

WMS_URL = (
    "https://kart.hi.no/data/fraraadning/ows"
    "?service=WMS&version=1.3.0&request=GetCapabilities"
)
WFS_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.taptefiskeredskaper"
    "?service=WFS&Version=2.0.0&request=Getcapabilities"
)
PUNKT_WMS_URL = (
    "https://kart.hi.no/mareano/mareano_stasjoner/bunnprover_punktstasjoner/wms"
    "?service=WMS&request=GetCapabilities"
)
HICOVERAGES_URL = "https://kart.hi.no/data/ogc/coverages/v1/collections?f=application%2Fjson"
HIMAPS_URL = "https://kart.hi.no/data/ogc/maps/v1/collections?f=application%2Fjson"
HISTYLES_URL = "https://kart.hi.no/data/ogc/styles/v1/styles?f=application%2Fjson"
HITILES_URL = "https://kart.hi.no/data/ogc/tiles/v1/tileMatrixSets?f=application%2Fjson"
HI_FEATURES_URL = "https://kart.hi.no/data/ogc/features/v1/collections"
FISKERIGIS_URL = "https://gis.fiskeridir.no/arcgis/rest/services?f=json"
HAVNEDATA_URL = "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/api?f=json"
BANEGIS_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.stoysonerjernbanenett"
    "?service=WFS&request=GetCapabilities"
)
AVINOR_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.lufthavnpunkt_avinor"
    "?Service=WFS&Request=GetCapabilities"
)
PORTAL_URL = "https://kart.hi.no/data/"
HTML_URL = (
    "https://kart.hi.no/data/htmlhiwms/ows"
    "?service=WMS&request=GetCapabilities"
)
MISSING_URL = (
    "https://kart.hi.no/data/missinghiwms/ows"
    "?service=WMS&request=GetCapabilities"
)
DATASET_ID = "hiwms:fraraadning_ows"

CATALOG = {
    "NumFound": 10,
    "Results": [
        {
            "Uuid": "hiwms-wms",
            "Title": "Rådgivningskart for seismiske og elektromagnetiske undersøkelser WMS",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "hiwms-wfs",
            "Title": "Menneskelig påvirkning -Tapte fiskeredskaper WFS",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": WFS_URL,
            "Type": "service",
        },
        {
            "Uuid": "servicelayer",
            "Title": "Overflatestrøm Atlanterhavet WMS",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "servicelayer",
        },
        {
            "Uuid": "ogc-api-features",
            "Title": "Artsutbredelse OGC API Features",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:API-Features",
            "DistributionUrl": HI_FEATURES_URL,
            "Type": "service",
        },
        {
            "Uuid": "hicoverages-row",
            "Title": "HI coverages",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HICOVERAGES_URL,
            "Type": "service",
        },
        {
            "Uuid": "himaps-row",
            "Title": "HI maps",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HIMAPS_URL,
            "Type": "service",
        },
        {
            "Uuid": "fiskerigis-row",
            "Title": "Fiskeridirektoratet GIS",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": FISKERIGIS_URL,
            "Type": "service",
        },
        {
            "Uuid": "havnedata-row",
            "Title": "Havnedata",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HAVNEDATA_URL,
            "Type": "service",
        },
        {
            "Uuid": "banegis-row",
            "Title": "Bane NOR leftover",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": BANEGIS_URL,
            "Type": "service",
        },
        {
            "Uuid": "avinor-row",
            "Title": "Avinor leftover",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": AVINOR_URL,
            "Type": "service",
        },
        {
            "Uuid": "portal-row",
            "Title": "Kart fra Havforskningsinstituttet",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": PORTAL_URL,
            "Type": "service",
        },
        {
            "Uuid": "html-hiwms",
            "Title": "HTML leftover",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "missing-404",
            "Title": "Missing WMS",
            "Organization": "Havforskningsinstituttet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MISSING_URL,
            "Type": "service",
        },
        {
            "Uuid": "other-org",
            "Title": "Marine naturtyper WMS",
            "Organization": "Norges geologiske undersøkelse",
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
    <Title>Rådgivningskart for seismiske og elektromagnetiske undersøkelser WMS</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>Raadgivning_2024</Name>
      <Title>Raadgivning_2024</Title>
      <Layer>
        <Name>Raadgivning_2025</Name>
        <Title>Raadgivning_2025</Title>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>taptefiskeredskaper</Name>
      <Title>Tapte fiskeredskaper</Title>
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
        raise AssertionError(f"hiwms fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"hiwms fetch must GET, not POST {url}")


def test_printed_refs_skip_covered_hosts_servicelayer_api_html_and_404() -> None:
    http = CatalogHttp()
    source = HiwmsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "fraraadning_ows",
        "wfs.taptefiskeredskaper",
    ]
    assert [ref.source_native_uri for ref in refs] == [WMS_URL, WFS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "collections" for ref in refs)
    assert all(ref.source_native_id != "wfs.stoysonerjernbanenett" for ref in refs)
    assert all(ref.source_native_id != "wfs.lufthavnpunkt_avinor" for ref in refs)
    assert all(ref.source_native_id != "htmlhiwms_ows" for ref in refs)
    assert all(ref.source_native_id != "missinghiwms_ows" for ref in refs)
    assert HTML_URL in http.gets
    assert MISSING_URL in http.gets
    assert HICOVERAGES_URL not in http.gets
    assert HIMAPS_URL not in http.gets
    assert FISKERIGIS_URL not in http.gets
    assert HAVNEDATA_URL not in http.gets
    assert BANEGIS_URL not in http.gets
    assert AVINOR_URL not in http.gets
    assert PORTAL_URL not in http.gets
    assert any(url.startswith(f"{SEARCH_URL}?") for url in http.gets)


def test_list_stops_after_max_items_live() -> None:
    http = CatalogHttp()
    source = HiwmsSource(http=http, max_items=1)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["fraraadning_ows"]
    assert WFS_URL not in http.gets
    assert HTML_URL not in http.gets
    assert MISSING_URL not in http.gets


def test_printed_leftover_services_keep_document_order_and_unique_ids() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == [
        "fraraadning_ows",
        "wfs.taptefiskeredskaper",
        "htmlhiwms_ows",
        "missinghiwms_ows",
    ]
    assert [href for _ident, href, _title in listed] == [
        WMS_URL,
        WFS_URL,
        HTML_URL,
        MISSING_URL,
    ]


def test_printed_service_id_uses_printed_path_segment() -> None:
    assert printed_service_id(WMS_URL) == "fraraadning_ows"
    assert printed_service_id(WFS_URL) == "wfs.taptefiskeredskaper"
    assert printed_service_id(PUNKT_WMS_URL) == "bunnprover_punktstasjoner_wms"
    assert printed_service_id(HTML_URL) == "htmlhiwms_ows"
    assert printed_service_id(MISSING_URL) == "missinghiwms_ows"
    assert printed_service_id("/") is None


def test_hiwms_is_a_registered_source() -> None:
    assert "hiwms" in SOURCE_IDS
    assert "hicoverages" in SOURCE_IDS
    assert "himaps" in SOURCE_IDS
    assert "histyles" in SOURCE_IDS
    assert "hitiles" in SOURCE_IDS
    assert "nibiorest" in SOURCE_IDS
    assert "mattilsyn" in SOURCE_IDS
    assert "banegis" in SOURCE_IDS
    assert SOURCE_IDS.index("hiwms") > SOURCE_IDS.index("nibiorest")
    assert SOURCE_IDS.index("hiwms") > SOURCE_IDS.index("brorgform")
    assert SOURCE_IDS.index("hiwms") > SOURCE_IDS.index("fdirwms")
    assert SOURCE_IDS.index("hiwms") > SOURCE_IDS.index("avinorgis")
    assert "ssbver" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("ssbver") + 1] == "hiwms"
    assert "nbagency" in SOURCE_IDS
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
    assert SOURCE_IDS[SOURCE_IDS.index("stsporre") + 1] == "crresult"
    assert SOURCE_IDS[SOURCE_IDS.index("crresult") + 1] == "stmoter"
    assert SOURCE_IDS[SOURCE_IDS.index("stmoter") + 1] == "ssbfritid"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbfritid") + 1] == "kvadm"
    assert SOURCE_IDS[SOURCE_IDS.index("kvadm") + 1] == "kvkrets"
    assert SOURCE_IDS[SOURCE_IDS.index("kvkrets") + 1] == "dsbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("dsbgis") + 1] == "nibiogard"
    assert SOURCE_IDS[SOURCE_IDS.index("nibiogard") + 1] == "stskrift"
    assert SOURCE_IDS[-1] == "stskrift"
    source = build_source("hiwms")
    assert isinstance(source, HiwmsSource)
    assert source.source_id == "hiwms"
    assert build_source("nibiorest").source_id == "nibiorest"
    assert build_source("hicoverages").source_id == "hicoverages"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = HiwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "hiwms"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == WMS_URL
    assert row["title"] == (
        "Rådgivningskart for seismiske og elektromagnetiske undersøkelser WMS"
    )
    assert row["publisher_name"] is None
    assert row["license"] is None
    wfs = registry.get_dataset("hiwms:wfs.taptefiskeredskaper")
    assert wfs is not None
    assert wfs["access_path"] == WFS_URL
    assert not str(row["id"]).startswith("hicoverages:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()[0]
    )
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["hiwms_service_id"] == "fraraadning_ows"
    assert payload["hiwms_service_href"] == WMS_URL
    assert payload["hiwms_service_title"] == (
        "Rådgivningskart for seismiske og elektromagnetiske undersøkelser WMS"
    )
    registry.close()


def test_fetch_copies_printed_layer_names(tmp_path: Path) -> None:
    source = HiwmsSource(http=CatalogHttp())
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
    assert result.table_id == "fraraadning_ows"
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Raadgivning_2024", "Raadgivning_2025"}
    assert by_value["Raadgivning_2025"]["measure"] == "Name"
    dims = json.loads(by_value["Raadgivning_2025"]["dimensions_json"])
    assert dims["Title"] == "Raadgivning_2025"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == WMS_URL for row in rows)
    registry.close()


def test_cells_from_hiwms_copy_printed_names_only() -> None:
    cells = cells_from_hiwms(WMS_XML)
    assert cells == [
        ("Name", "Raadgivning_2024", {"Title": "Raadgivning_2024"}),
        ("Name", "Raadgivning_2025", {"Title": "Raadgivning_2025"}),
    ]
    wfs_cells = cells_from_hiwms(WFS_XML)
    assert wfs_cells == [
        ("Name", "taptefiskeredskaper", {"Title": "Tapte fiskeredskaper"}),
    ]
    with pytest.raises(ValueError, match="empty"):
        cells_from_hiwms(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_hiwms(GLE_HTML)
    with pytest.raises(ValueError, match="not WMS/WFS XML"):
        cells_from_hiwms("<ServiceExceptionReport></ServiceExceptionReport>")
    with pytest.raises(ValueError, match="printed no Layer Name"):
        cells_from_hiwms("<WMS_Capabilities></WMS_Capabilities>")


def test_is_hiwms_url_accepts_leftover_hosts_only() -> None:
    assert is_hiwms_url(WMS_URL)
    assert is_hiwms_url(WFS_URL)
    assert is_hiwms_url(PUNKT_WMS_URL)
    assert hiwms_table_id(WMS_URL) == "fraraadning_ows"
    assert hiwms_table_id(WFS_URL) == "wfs.taptefiskeredskaper"
    assert not is_hiwms_url(HICOVERAGES_URL)
    assert not is_hiwms_url(HIMAPS_URL)
    assert not is_hiwms_url(HISTYLES_URL)
    assert not is_hiwms_url(HITILES_URL)
    assert not is_hiwms_url(HI_FEATURES_URL)
    assert not is_hiwms_url(FISKERIGIS_URL)
    assert not is_hiwms_url(HAVNEDATA_URL)
    assert not is_hiwms_url(BANEGIS_URL)
    assert not is_hiwms_url(AVINOR_URL)
    assert not is_hiwms_url(
        "https://wfs.geonorge.no/skwms1/wfs.stoy_veg"
        "?request=GetCapabilities&service=WFS"
    )
    assert not is_hiwms_url(PORTAL_URL)
    assert not is_hiwms_url(SEARCH_URL)
    assert not is_hiwms_url(None)
    assert is_hicoverages_url(HICOVERAGES_URL)
    assert is_himaps_url(HIMAPS_URL)
    assert is_fiskerigis_url(FISKERIGIS_URL)
    assert is_havnedata_url(HAVNEDATA_URL)
    assert is_banegis_url(BANEGIS_URL)
    assert not is_hicoverages_url(WMS_URL)
    assert not is_himaps_url(WMS_URL)
    assert not is_fiskerigis_url(WMS_URL)
    assert not is_havnedata_url(WMS_URL)
    assert not is_banegis_url(WFS_URL)
