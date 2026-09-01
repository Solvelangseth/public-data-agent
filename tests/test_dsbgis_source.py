from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.dsbgis import (
    DsbgisSource,
    SEARCH_URL,
    cells_from_dsbgis,
    dsbgis_table_id,
    is_dsbgis_url,
    printed_leftover_services,
    printed_service_id,
)
from public_data_agent.sources.kvfkb import is_kvfkb_url
from public_data_agent.sources.ssbgis import is_ssbgis_url

DSB_WMS_URL = (
    "https://ogc.dsb.no/wms.ashx?SERVICE=WMS&REQUEST=GetCapabilities&version=1.3.0"
)
DSB_WFS_URL = "https://ogc.dsb.no/wfs.ashx?SERVICE=WFS&REQUEST=GetCapabilities"
KART_DSB_URL = "https://kart.dsb.no"
HTML_URL = (
    "https://ogc.dsb.no/wms.ashx?SERVICE=WMS&REQUEST=GetCapabilities&version=1.3.0&html=1"
)
FKB_URL = "https://wms.geonorge.no/skwms1/wms.fkb?service=wms&request=getcapabilities"
SSB_WMS_URL = (
    "https://kart.ssb.no/api/mapserver/v1/wms/sentrumssoner"
    "?service=WMS&version=1.3.0&request=GetCapabilities"
)
DATASET_ID = "dsbgis:ogc.dsb.no"

CATALOG = {
    "NumFound": 6,
    "Results": [
        {
            "Uuid": "a192a05c-0b9c-44ab-972e-428aa1ff9ada",
            "Title": "DSB kartinnsyn",
            "Organization": "Direktoratet for samfunnssikkerhet og beredskap",
            "DistributionProtocol": "WWW:LINK-1.0-http--link",
            "DistributionUrl": KART_DSB_URL,
            "Type": "software",
        },
        {
            "Uuid": "21be7540-adba-42d9-9f3c-583365491eea",
            "Title": "DSBs WMS-tjenester",
            "Organization": "Direktoratet for samfunnssikkerhet og beredskap",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": DSB_WMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "e4ca461a-a23c-48a0-8659-b72af0b231fc",
            "Title": "DSBs WFS-tjenester",
            "Organization": "Direktoratet for samfunnssikkerhet og beredskap",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": DSB_WFS_URL,
            "Type": "service",
        },
        {
            "Uuid": "html-dsb",
            "Title": "HTML leftover",
            "Organization": "Direktoratet for samfunnssikkerhet og beredskap",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "download-brann",
            "Title": "Brannstasjoner",
            "Organization": "Direktoratet for samfunnssikkerhet og beredskap",
            "DistributionProtocol": "GEONORGE:DOWNLOAD",
            "DistributionUrl": "https://nedlasting.geonorge.no/api/capabilities/",
            "Type": "dataset",
        },
        {
            "Uuid": "other-org",
            "Title": "Fritidsbyggområder WMS",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": SSB_WMS_URL,
            "Type": "service",
        },
        {"nested": True},
    ],
}
DSB_WMS_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Service>
    <Title>Mapserver WMS - kart</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>MS</Name>
      <Title>Mapserver WMS - kart</Title>
      <Layer>
        <Name>layer_183</Name>
        <Title>Brannstasjoner</Title>
        <Abstract>skip</Abstract>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
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
        if url == DSB_WMS_URL:
            return DSB_WMS_XML
        if url == HTML_URL:
            return GLE_HTML
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == DSB_WMS_URL:
            return DSB_WMS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"dsbgis fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"dsbgis fetch must GET, not POST {url}")


def test_printed_refs_skip_kart_dsb_wfs_html_and_downloads() -> None:
    http = CatalogHttp()
    source = DsbgisSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["ogc.dsb.no"]
    assert [ref.source_native_uri for ref in refs] == [DSB_WMS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "wms.ashx" for ref in refs)
    assert all(ref.source_native_uri != KART_DSB_URL for ref in refs)
    assert all(ref.source_native_uri != DSB_WFS_URL for ref in refs)
    assert DSB_WMS_URL in http.gets
    assert HTML_URL in http.gets
    assert KART_DSB_URL not in http.gets
    assert DSB_WFS_URL not in http.gets
    assert any("text=DSB" in url for url in http.gets)


def test_printed_leftover_services_keep_document_order_and_unique_hrefs() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == ["ogc.dsb.no", "ogc.dsb.no"]
    assert [href for _ident, href, _title in listed] == [DSB_WMS_URL, HTML_URL]
    assert KART_DSB_URL not in [href for _ident, href, _title in listed]
    assert DSB_WFS_URL not in [href for _ident, href, _title in listed]


def test_printed_service_id_uses_host_for_generic_ashx() -> None:
    assert printed_service_id(DSB_WMS_URL) == "ogc.dsb.no"
    assert printed_service_id("/") is None


def test_dsbgis_is_a_registered_source() -> None:
    assert "dsbgis" in SOURCE_IDS
    assert "ssbgis" in SOURCE_IDS
    assert "kvfkb" in SOURCE_IDS
    assert "nibioar5f" in SOURCE_IDS
    assert "barmark" in SOURCE_IDS
    assert "nordatlas" in SOURCE_IDS
    assert "fbgis" in SOURCE_IDS
    assert "bwgis" in SOURCE_IDS
    assert "mdirgis" in SOURCE_IDS
    assert "nguminer" in SOURCE_IDS
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
    source = build_source("dsbgis")
    assert isinstance(source, DsbgisSource)
    assert source.source_id == "dsbgis"
    assert build_source("ssbgis").source_id == "ssbgis"
    assert build_source("kvfkb").source_id == "kvfkb"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = DsbgisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "dsbgis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == DSB_WMS_URL
    assert row["title"] == "DSBs WMS-tjenester"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssbgis:")
    assert not str(row["id"]).startswith("kvfkb:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["dsbgis_service_id"] == "ogc.dsb.no"
    assert payload["dsbgis_service_href"] == DSB_WMS_URL
    assert payload["dsbgis_service_title"] == "DSBs WMS-tjenester"
    assert payload["description"] == {"no": DSB_WMS_URL}
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = DsbgisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == DSB_WMS_URL
    assert result.table_id == "ogc.dsb.no"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"MS", "layer_183"}
    assert by_value["layer_183"]["measure"] == "Name"
    dims = json.loads(by_value["layer_183"]["dimensions_json"])
    assert dims["Title"] == "Brannstasjoner"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == DSB_WMS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_name() -> None:
    cells = cells_from_dsbgis(DSB_WMS_XML)
    assert [value for _measure, value, _dims in cells] == ["MS", "layer_183"]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "layer_183"
    assert dims["Title"] == "Brannstasjoner"
    assert "Abstract" not in dims
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_dsbgis(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_dsbgis(GLE_HTML)
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_dsbgis(EXCEPTION_XML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_dsbgis("<WMS_Capabilities></WMS_Capabilities>")


def test_is_dsbgis_url_accepts_leftover_dsb_wms_and_skips_owned() -> None:
    assert is_dsbgis_url(DSB_WMS_URL)
    assert dsbgis_table_id(DSB_WMS_URL) == "ogc.dsb.no"
    assert not is_dsbgis_url(DSB_WFS_URL)
    assert not is_dsbgis_url(KART_DSB_URL)
    assert not is_dsbgis_url(FKB_URL)
    assert not is_dsbgis_url(SSB_WMS_URL)
    assert not is_dsbgis_url(SEARCH_URL)
    assert not is_dsbgis_url("https://data.norge.no/datasets/x")
    assert not is_dsbgis_url(None)
    assert not is_ssbgis_url(DSB_WMS_URL)
    assert not is_kvfkb_url(DSB_WMS_URL)


def test_limit_and_offset_slice_printed_services() -> None:
    source = DsbgisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "ogc.dsb.no"
    ]
    assert source.list_dataset_refs(limit=1, offset=1) == []
