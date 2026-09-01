from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.avinorgis import is_avinorgis_url
from public_data_agent.sources.banegis import is_banegis_url
from public_data_agent.sources.bwgis import is_bwgis_url
from public_data_agent.sources.fbgis import (
    FbgisSource,
    SEARCH_URL,
    cells_from_fbgis,
    fbgis_table_id,
    is_fbgis_url,
    printed_leftover_services,
    printed_service_id,
)
from public_data_agent.sources.havnedata import is_havnedata_url
from public_data_agent.sources.kvgrunn import is_kvgrunn_url
from public_data_agent.sources.kvtopo import is_kvtopo_url
from public_data_agent.sources.kvwms import is_kvwms_url

WMS_URL = (
    "https://wms.geonorge.no/skwms1/wms.skytefelt?service=wms&request=getcapabilities"
)
WFS_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.ovingsfeltsjo"
    "?request=GetCapabilities&service=WFS"
)
KVWMS_URL = "https://wms.geonorge.no/skwms1/wms.topo?service=WMS&request=GetCapabilities"
KVGRUNN_URL = (
    "https://wms.geonorge.no/skwms1/wms.topograatone"
    "?service=WMS&request=GetCapabilities"
)
KVTOPO_URL = (
    "https://wms.geonorge.no/skwms1/wms.friluftsruter2"
    "?request=GetCapabilities&service=WMS&version=1.3.0"
)
KVTOPO_KARTDATA_URL = (
    "https://wms.geonorge.no/skwms1/wms.kartdata?service=wms&request=getcapabilities"
)
MATRIKKELKART_URL = (
    "https://wms.geonorge.no/skwms1/wms.matrikkelkart"
    "?service=wms&request=getcapabilities"
)
HAVNEDATA_URL = "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/api?f=json"
AVINORGIS_URL = (
    "https://wms.geonorge.no/skwms1/wms.stoylufthavn"
    "?service=wms&request=getcapabilities"
)
BANEGIS_URL = (
    "https://wms.geonorge.no/skwms1/wms.banenettverk"
    "?request=GetCapabilities&service=WMS"
)
SSBGIS_URL = (
    "https://kart.ssb.no/api/mapserver/v1/wms/sentrumssoner"
    "?service=WMS&version=1.3.0&request=GetCapabilities"
)
BWGIS_URL = (
    "https://geo.barentswatch.no/geoserver/bw/ows"
    "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
HTML_URL = (
    "https://wms.geonorge.no/skwms1/wms.htmlfbgis"
    "?service=WMS&request=GetCapabilities"
)
MISSING_URL = (
    "https://wms.geonorge.no/skwms1/wms.missingfbgis"
    "?service=WMS&request=GetCapabilities"
)
DATASET_ID = "fbgis:wms.skytefelt"

CATALOG = {
    "NumFound": 10,
    "Results": [
        {
            "Uuid": "fbgis-wms",
            "Title": "Forsvarets skyte- og øvingsfelt land WMS",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "fbgis-wfs",
            "Title": "Forsvarets skyte- og øvingsfelt i sjø WFS",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": WFS_URL,
            "Type": "service",
        },
        {
            "Uuid": "servicelayer",
            "Title": "Skytefelt layer",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": WMS_URL,
            "Type": "servicelayer",
        },
        {
            "Uuid": "download-row",
            "Title": "Militære forbudsområder innen sjøforsvaret",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "GEONORGE:DOWNLOAD",
            "DistributionUrl": "https://nedlasting.geonorge.no/api/capabilities/",
            "Type": "dataset",
        },
        {
            "Uuid": "kvwms-row",
            "Title": "Kartverket topo",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": KVWMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "kvgrunn-row",
            "Title": "Kartverket grunnkart",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": KVGRUNN_URL,
            "Type": "service",
        },
        {
            "Uuid": "kvtopo-row",
            "Title": "Friluftsruter",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": KVTOPO_URL,
            "Type": "service",
        },
        {
            "Uuid": "kvtopo-kartdata-row",
            "Title": "Kartdata",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": KVTOPO_KARTDATA_URL,
            "Type": "service",
        },
        {
            "Uuid": "matrikkel-row",
            "Title": "Matrikkelkart",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MATRIKKELKART_URL,
            "Type": "service",
        },
        {
            "Uuid": "havnedata-row",
            "Title": "Havnedata",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HAVNEDATA_URL,
            "Type": "service",
        },
        {
            "Uuid": "avinorgis-row",
            "Title": "Avinor leftover WMS",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": AVINORGIS_URL,
            "Type": "service",
        },
        {
            "Uuid": "banegis-row",
            "Title": "Bane NOR leftover WMS",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": BANEGIS_URL,
            "Type": "service",
        },
        {
            "Uuid": "ssbgis-row",
            "Title": "SSB leftover WMS",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": SSBGIS_URL,
            "Type": "service",
        },
        {
            "Uuid": "bwgis-row",
            "Title": "BarentsWatch leftover WMS",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": BWGIS_URL,
            "Type": "service",
        },
        {
            "Uuid": "html-fbgis",
            "Title": "HTML leftover",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "missing-404",
            "Title": "Missing WMS",
            "Organization": "Forsvarsbygg",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MISSING_URL,
            "Type": "service",
        },
        {
            "Uuid": "other-org",
            "Title": "Kartverket leftover WMS",
            "Organization": "Kartverket",
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
    <Title>Forsvarets skyte- og øvingsfelt land WMS</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>skytefelt</Name>
      <Title>Skytefelt</Title>
      <Layer>
        <Name>ovingsfelt</Name>
        <Title>Øvingsfelt</Title>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>app:ovingsfeltsjo</Name>
      <Title>Øvingsfelt i sjø</Title>
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
        raise AssertionError(f"fbgis fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"fbgis fetch must GET, not POST {url}")


def test_printed_refs_skip_owned_ids_servicelayer_download_html_and_404() -> None:
    http = CatalogHttp()
    source = FbgisSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["wms.skytefelt", "wfs.ovingsfeltsjo"]
    assert [ref.source_native_uri for ref in refs] == [WMS_URL, WFS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "wms.htmlfbgis" for ref in refs)
    assert all(ref.source_native_id != "wms.missingfbgis" for ref in refs)
    assert HTML_URL in http.gets
    assert MISSING_URL in http.gets
    assert KVWMS_URL not in http.gets
    assert KVGRUNN_URL not in http.gets
    assert KVTOPO_URL not in http.gets
    assert KVTOPO_KARTDATA_URL not in http.gets
    assert MATRIKKELKART_URL not in http.gets
    assert HAVNEDATA_URL not in http.gets
    assert AVINORGIS_URL not in http.gets
    assert BANEGIS_URL not in http.gets
    assert SSBGIS_URL not in http.gets
    assert BWGIS_URL not in http.gets
    assert any(url.startswith(f"{SEARCH_URL}?") for url in http.gets)


def test_list_stops_after_max_items_live() -> None:
    http = CatalogHttp()
    source = FbgisSource(http=http, max_items=1)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["wms.skytefelt"]
    assert WFS_URL not in http.gets
    assert HTML_URL not in http.gets
    assert MISSING_URL not in http.gets


def test_printed_leftover_services_keep_document_order_and_unique_ids() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == [
        "wms.skytefelt",
        "wfs.ovingsfeltsjo",
        "wms.htmlfbgis",
        "wms.missingfbgis",
    ]
    assert [href for _ident, href, _title in listed] == [
        WMS_URL,
        WFS_URL,
        HTML_URL,
        MISSING_URL,
    ]


def test_printed_service_id_uses_printed_path_segment() -> None:
    assert printed_service_id(WMS_URL) == "wms.skytefelt"
    assert printed_service_id(WFS_URL) == "wfs.ovingsfeltsjo"
    assert printed_service_id(KVTOPO_URL) == "wms.friluftsruter2"
    assert printed_service_id(HTML_URL) == "wms.htmlfbgis"
    assert printed_service_id(MISSING_URL) == "wms.missingfbgis"
    assert printed_service_id("/") is None


def test_fbgis_is_a_registered_source() -> None:
    assert "fbgis" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    assert "kvgrunn" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "havnedata" in SOURCE_IDS
    assert "avinorgis" in SOURCE_IDS
    assert "banegis" in SOURCE_IDS
    assert "bwgis" in SOURCE_IDS
    assert SOURCE_IDS.index("fbgis") > SOURCE_IDS.index("bwgis")
    assert SOURCE_IDS.index("fbgis") > SOURCE_IDS.index("kvtopo")
    assert SOURCE_IDS.index("fbgis") > SOURCE_IDS.index("mdirgis")
    assert SOURCE_IDS.index("fbgis") > SOURCE_IDS.index("ssbcorr")
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
    source = build_source("fbgis")
    assert isinstance(source, FbgisSource)
    assert source.source_id == "fbgis"
    assert build_source("bwgis").source_id == "bwgis"
    assert build_source("kvtopo").source_id == "kvtopo"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = FbgisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "fbgis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == WMS_URL
    assert row["title"] == "Forsvarets skyte- og øvingsfelt land WMS"
    assert row["publisher_name"] is None
    assert row["license"] is None
    wfs = registry.get_dataset("fbgis:wfs.ovingsfeltsjo")
    assert wfs is not None
    assert wfs["access_path"] == WFS_URL
    assert not str(row["id"]).startswith("kvtopo:")
    assert not str(row["id"]).startswith("kvfriluft:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()[0]
    )
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["fbgis_service_id"] == "wms.skytefelt"
    assert payload["fbgis_service_href"] == WMS_URL
    assert payload["fbgis_service_title"] == "Forsvarets skyte- og øvingsfelt land WMS"
    registry.close()


def test_fetch_copies_printed_layer_names(tmp_path: Path) -> None:
    source = FbgisSource(http=CatalogHttp())
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
    assert result.table_id == "wms.skytefelt"
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"skytefelt", "ovingsfelt"}
    assert by_value["ovingsfelt"]["measure"] == "Name"
    dims = json.loads(by_value["ovingsfelt"]["dimensions_json"])
    assert dims["Title"] == "Øvingsfelt"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == WMS_URL for row in rows)
    registry.close()


def test_cells_from_fbgis_copy_printed_names_only() -> None:
    cells = cells_from_fbgis(WMS_XML)
    assert cells == [
        ("Name", "skytefelt", {"Title": "Skytefelt"}),
        ("Name", "ovingsfelt", {"Title": "Øvingsfelt"}),
    ]
    wfs_cells = cells_from_fbgis(WFS_XML)
    assert wfs_cells == [
        ("Name", "app:ovingsfeltsjo", {"Title": "Øvingsfelt i sjø"}),
    ]
    with pytest.raises(ValueError, match="empty"):
        cells_from_fbgis(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_fbgis(GLE_HTML)
    with pytest.raises(ValueError, match="not WMS/WFS XML"):
        cells_from_fbgis("<ServiceExceptionReport></ServiceExceptionReport>")
    with pytest.raises(ValueError, match="printed no Layer Name"):
        cells_from_fbgis("<WMS_Capabilities></WMS_Capabilities>")


def test_is_fbgis_url_accepts_leftover_ids_only() -> None:
    assert is_fbgis_url(WMS_URL)
    assert is_fbgis_url(WFS_URL)
    assert fbgis_table_id(WMS_URL) == "wms.skytefelt"
    assert fbgis_table_id(WFS_URL) == "wfs.ovingsfeltsjo"
    assert not is_fbgis_url(KVWMS_URL)
    assert not is_fbgis_url(KVGRUNN_URL)
    assert not is_fbgis_url(KVTOPO_URL)
    assert not is_fbgis_url(KVTOPO_KARTDATA_URL)
    assert not is_fbgis_url(MATRIKKELKART_URL)
    assert not is_fbgis_url(HAVNEDATA_URL)
    assert not is_fbgis_url(AVINORGIS_URL)
    assert not is_fbgis_url(BANEGIS_URL)
    assert not is_fbgis_url(SSBGIS_URL)
    assert not is_fbgis_url(BWGIS_URL)
    assert not is_fbgis_url(SEARCH_URL)
    assert not is_fbgis_url(None)
    assert is_kvwms_url(KVWMS_URL)
    assert is_kvgrunn_url(KVGRUNN_URL)
    assert is_kvtopo_url(KVTOPO_URL)
    assert is_kvtopo_url(KVTOPO_KARTDATA_URL)
    assert is_havnedata_url(HAVNEDATA_URL)
    assert is_avinorgis_url(AVINORGIS_URL)
    assert is_banegis_url(BANEGIS_URL)
    assert is_bwgis_url(BWGIS_URL)
    assert not is_kvwms_url(WMS_URL)
    assert not is_kvgrunn_url(WMS_URL)
    assert not is_kvtopo_url(WMS_URL)
    assert not is_havnedata_url(WMS_URL)
    assert not is_avinorgis_url(WMS_URL)
    assert not is_banegis_url(WMS_URL)
    assert not is_bwgis_url(WMS_URL)
