from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.vegwms import (
    VegwmsSource,
    SEARCH_URL,
    cells_from_vegwms,
    is_vegwms_url,
    printed_leftover_services,
    printed_service_id,
    vegwms_table_id,
)

STOY_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.stoy_veg"
    "?request=GetCapabilities&service=WFS"
)
ULYKKER_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.trafikkulykker"
    "?service=wfs&request=getcapabilities"
)
MENGDE_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.trafikkmengde"
    "?service=wfs&request=getcapabilities"
)
NORSTOY_MIRROR_URL = (
    "https://www.vegvesen.no/kart/ogc/norstoy_1_0/ows"
    "?service=WMS&request=getcapabilities"
)
VEGOGC_URL = (
    "https://ogckart-sn1.atlas.vegvesen.no/nvdb_2_0/ows"
    "?service=wms&request=GetCapabilities"
)
VEGKART_URL = "https://vegkart.atlas.vegvesen.no/"
BANEGIS_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.stoysonerjernbanenett"
    "?service=wfs&request=getcapabilities"
)
AVINOR_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.stoylufthavn"
    "?service=WFS&request=GetCapabilities"
)
FDIR_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.fiskeplasserredskap"
    "?service=wfs&request=getcapabilities"
)
HI_URL = (
    "https://kart.hi.no/data/fraraadning/ows"
    "?service=WMS&version=1.3.0&request=GetCapabilities"
)
HTML_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.htmlvegwms"
    "?service=WFS&request=GetCapabilities"
)
MISSING_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.missingvegwms"
    "?service=WFS&request=GetCapabilities"
)
DATASET_ID = "vegwms:wfs.stoy_veg"

CATALOG = {
    "NumFound": 10,
    "Results": [
        {
            "Uuid": "download-veg",
            "Title": "Trafikkulykker dataset",
            "Organization": "Statens vegvesen",
            "DistributionProtocol": "GEONORGE:DOWNLOAD",
            "DistributionUrl": "https://nedlasting.geonorge.no/api/capabilities/",
            "Type": "dataset",
        },
        {
            "Uuid": "stoy-wfs",
            "Title": "Støykartlegging veg etter T-1442 WFS",
            "Organization": "Statens vegvesen",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": STOY_URL,
            "Type": "service",
        },
        {
            "Uuid": "norstoy-mirror",
            "Title": "Støy Veg WMS",
            "Organization": "Statens vegvesen",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": NORSTOY_MIRROR_URL,
            "Type": "service",
        },
        {
            "Uuid": "ulykker-wfs",
            "Title": "Trafikkulykker WFS",
            "Organization": "Statens vegvesen",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": ULYKKER_URL,
            "Type": "service",
        },
        {
            "Uuid": "vegogc-row",
            "Title": "NVDB leftover",
            "Organization": "Statens vegvesen",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": VEGOGC_URL,
            "Type": "service",
        },
        {
            "Uuid": "mengde-wfs",
            "Title": "Trafikkmengde WFS",
            "Organization": "Statens vegvesen",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": MENGDE_URL,
            "Type": "service",
        },
        {
            "Uuid": "servicelayer",
            "Title": "Støy layer",
            "Organization": "Statens vegvesen",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": STOY_URL,
            "Type": "servicelayer",
        },
        {
            "Uuid": "kyst-row",
            "Title": "Kystverket leftover",
            "Organization": "Kystverket",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": STOY_URL,
            "Type": "service",
        },
        {
            "Uuid": "html-vegwms",
            "Title": "HTML leftover",
            "Organization": "Statens vegvesen",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "missing-404",
            "Title": "Missing WFS",
            "Organization": "Statens vegvesen",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": MISSING_URL,
            "Type": "service",
        },
        {
            "Uuid": "vegkart",
            "Title": "Vegkart",
            "Organization": "Statens vegvesen",
            "DistributionProtocol": "WWW:LINK-1.0-http--link",
            "DistributionUrl": VEGKART_URL,
            "Type": "software",
        },
        {"nested": True},
    ],
}
STOY_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>app:Stoysone</Name>
      <Title>Støysone</Title>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
"""
ULYKKER_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>app:Trafikkulykke</Name>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
"""
MENGDE_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>app:Trafikkmengde</Name>
      <Title>ÅDT</Title>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
"""
WMS_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability>
    <Layer>
      <Name>stoy_veg</Name>
      <Title>Støy veg</Title>
      <Layer>
        <Name>Stoysone</Name>
        <Title>Støysone rød</Title>
        <Abstract>skip</Abstract>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
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
            STOY_URL: STOY_XML,
            ULYKKER_URL: ULYKKER_XML,
            MENGDE_URL: MENGDE_XML,
            HTML_URL: GLE_HTML,
        }
        if url == MISSING_URL:
            raise RuntimeError("HTTP 404")
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == STOY_URL:
            return STOY_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"vegwms fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"vegwms fetch must GET, not POST {url}")


def test_printed_refs_skip_vegogc_mirror_html_and_404() -> None:
    http = CatalogHttp()
    source = VegwmsSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "wfs.stoy_veg",
        "wfs.trafikkulykker",
        "wfs.trafikkmengde",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        STOY_URL,
        ULYKKER_URL,
        MENGDE_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "norstoy_1_0_ows" for ref in refs)
    assert all(ref.source_native_id != "nvdb_2_0_ows" for ref in refs)
    assert all(ref.source_native_id != "htmlvegwms" for ref in refs)
    assert all(ref.source_native_id != "missingvegwms" for ref in refs)
    assert HTML_URL not in http.gets
    assert MISSING_URL not in http.gets
    assert NORSTOY_MIRROR_URL not in http.gets
    assert VEGOGC_URL not in http.gets
    assert VEGKART_URL not in http.gets
    assert any(url.startswith(f"{SEARCH_URL}?") for url in http.gets)


def test_printed_leftover_services_keep_document_order_and_unique_ids() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == [
        "wfs.stoy_veg",
        "wfs.trafikkulykker",
        "wfs.trafikkmengde",
    ]
    assert [href for _ident, href, _title in listed] == [
        STOY_URL,
        ULYKKER_URL,
        MENGDE_URL,
    ]


def test_printed_service_id_uses_printed_path_segment() -> None:
    assert printed_service_id(STOY_URL) == "wfs.stoy_veg"
    assert printed_service_id(ULYKKER_URL) == "wfs.trafikkulykker"
    assert printed_service_id(MENGDE_URL) == "wfs.trafikkmengde"
    assert printed_service_id(NORSTOY_MIRROR_URL) == "norstoy_1_0_ows"
    assert printed_service_id(VEGOGC_URL) == "nvdb_2_0_ows"
    assert printed_service_id("/") is None


def test_vegwms_is_a_registered_source() -> None:
    assert "vegwms" in SOURCE_IDS
    assert "vegogc" in SOURCE_IDS
    assert "vegvesen" in SOURCE_IDS
    assert "hiwms" in SOURCE_IDS
    assert "nbagency" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
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
    assert SOURCE_IDS[-1] == "kikommuner"
    source = build_source("vegwms")
    assert isinstance(source, VegwmsSource)
    assert source.source_id == "vegwms"
    assert build_source("vegogc").source_id == "vegogc"
    assert build_source("vegvesen").source_id == "vegvesen"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = VegwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "vegwms"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == STOY_URL
    assert row["title"] == "Støykartlegging veg etter T-1442 WFS"
    ulykker = registry.get_dataset("vegwms:wfs.trafikkulykker")
    assert ulykker is not None
    assert ulykker["access_path"] == ULYKKER_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("vegogc:")
    assert not str(row["id"]).startswith("vegvesen:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["vegwms_service_id"] == "wfs.stoy_veg"
    assert payload["vegwms_service_href"] == STOY_URL
    assert payload["vegwms_service_title"] == "Støykartlegging veg etter T-1442 WFS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_feature_type_name_cells(tmp_path: Path) -> None:
    source = VegwmsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == STOY_URL
    assert result.table_id == "wfs.stoy_veg"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"app:Stoysone"}
    assert by_value["app:Stoysone"]["measure"] == "Name"
    dims = json.loads(by_value["app:Stoysone"]["dimensions_json"])
    assert dims["Title"] == "Støysone"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == STOY_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_and_feature_type_name() -> None:
    cells = cells_from_vegwms(WMS_XML)
    assert [value for _measure, value, _dims in cells] == ["stoy_veg", "Stoysone"]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "Stoysone"
    assert dims["Title"] == "Støysone rød"
    assert "Abstract" not in dims
    assert cells_from_vegwms(ULYKKER_XML) == [
        ("Name", "app:Trafikkulykke", {})
    ]
    wfs_cells = cells_from_vegwms(STOY_XML)
    assert wfs_cells == [
        ("Name", "app:Stoysone", {"Title": "Støysone"})
    ]
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_vegwms(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_vegwms(GLE_HTML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_vegwms("<WMS_Capabilities></WMS_Capabilities>")
    with pytest.raises(ValueError, match="FeatureType Name"):
        cells_from_vegwms("<WFS_Capabilities></WFS_Capabilities>")


def test_is_vegwms_url_accepts_leftover_ids_and_skips_taken() -> None:
    assert is_vegwms_url(STOY_URL)
    assert is_vegwms_url(ULYKKER_URL)
    assert is_vegwms_url(MENGDE_URL)
    assert vegwms_table_id(STOY_URL) == "wfs.stoy_veg"
    assert vegwms_table_id(ULYKKER_URL) == "wfs.trafikkulykker"
    assert vegwms_table_id(MENGDE_URL) == "wfs.trafikkmengde"
    assert not is_vegwms_url(NORSTOY_MIRROR_URL)
    assert not is_vegwms_url(VEGOGC_URL)
    assert not is_vegwms_url(VEGKART_URL)
    assert not is_vegwms_url(BANEGIS_URL)
    assert not is_vegwms_url(AVINOR_URL)
    assert not is_vegwms_url(FDIR_URL)
    assert not is_vegwms_url(HI_URL)
    assert not is_vegwms_url(SEARCH_URL)
    assert not is_vegwms_url("https://data.norge.no/datasets/x")
    assert not is_vegwms_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = VegwmsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "wfs.stoy_veg"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["wfs.trafikkulykker"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
