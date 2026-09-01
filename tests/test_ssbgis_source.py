from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kvgrunn import is_kvgrunn_url
from public_data_agent.sources.kvtopo import is_kvtopo_url
from public_data_agent.sources.kvwms import is_kvwms_url
from public_data_agent.sources.ssbgis import (
    SEARCH_URL,
    SsbgisSource,
    cells_from_ssbgis,
    is_ssbgis_url,
    printed_leftover_services,
    printed_service_id,
    ssbgis_table_id,
)
from public_data_agent.sources.ssbv2 import is_ssbv2_url

SENTRUM_URL = (
    "https://kart.ssb.no/api/mapserver/v1/wms/sentrumssoner"
    "?service=WMS&version=1.3.0&request=GetCapabilities"
)
FRITID_URL = (
    "https://kart.ssb.no/api/mapserver/v1/wms/fritidsbyggomraader"
    "?service=WMS&version=1.3.0&request=GetCapabilities"
)
AREALBRUK_URL = (
    "https://wms.geonorge.no/skwms1/wms.arealbruk"
    "?service=WMS&request=GetCapabilities"
)
WFS_URL = (
    "https://kart.ssb.no/api/mapserver/v1/wfs/sentrumssoner"
    "?service=WFS&version=2.0.0&request=GetCapabilities"
)
SSBV2_URL = "https://data.ssb.no/api/pxwebapi/v2/tables"
KVWMS_URL = "https://wms.geonorge.no/skwms1/wms.topo?service=WMS&request=GetCapabilities"
KVTOPO_URL = (
    "https://wms.geonorge.no/skwms1/wms.kartdata?service=wms&request=getcapabilities"
)
KVGRUNN_URL = (
    "https://wms.geonorge.no/skwms1/wms.topograatone"
    "?service=WMS&request=GetCapabilities"
)
GRUNNKRETS_URL = (
    "https://wms.geonorge.no/skwms1/wms.grunnkretser"
    "?request=GetCapabilities&service=WMS"
)
HTML_URL = (
    "https://kart.ssb.no/api/mapserver/v1/wms/htmlssbgis"
    "?service=WMS&version=1.3.0&request=GetCapabilities"
)
MISSING_URL = (
    "https://kart.ssb.no/api/mapserver/v1/wms/missingssbgis"
    "?service=WMS&version=1.3.0&request=GetCapabilities"
)
DATASET_ID = "ssbgis:sentrumssoner"

CATALOG = {
    "NumFound": 12,
    "Results": [
        {
            "Uuid": "sentrum-wms",
            "Title": "Sentrumssoner WMS",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": SENTRUM_URL,
            "Type": "service",
        },
        {
            "Uuid": "fritid-wms",
            "Title": "Fritidsbyggområder WMS",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": FRITID_URL,
            "Type": "service",
        },
        {
            "Uuid": "arealbruk-wms",
            "Title": "Arealbruk WMS",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": AREALBRUK_URL,
            "Type": "service",
        },
        {
            "Uuid": "sentrum-wfs",
            "Title": "Sentrumssoner WFS",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": WFS_URL,
            "Type": "service",
        },
        {
            "Uuid": "ssbv2-row",
            "Title": "PxWebApi 2",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": SSBV2_URL,
            "Type": "service",
        },
        {
            "Uuid": "kvwms-row",
            "Title": "Topo WMS",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": KVWMS_URL,
            "Type": "service",
        },
        {
            "Uuid": "kvtopo-row",
            "Title": "Kartdata WMS",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": KVTOPO_URL,
            "Type": "service",
        },
        {
            "Uuid": "kvgrunn-row",
            "Title": "Topograatone WMS",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": KVGRUNN_URL,
            "Type": "service",
        },
        {
            "Uuid": "grunnkrets-row",
            "Title": "Statistiske enheter grunnkretser WMS",
            "Organization": "Kartverket",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": GRUNNKRETS_URL,
            "Type": "service",
        },
        {
            "Uuid": "servicelayer",
            "Title": "Sentrumssoner layer",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": SENTRUM_URL,
            "Type": "servicelayer",
        },
        {
            "Uuid": "html-ssbgis",
            "Title": "HTML leftover",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
        },
        {
            "Uuid": "missing-404",
            "Title": "Missing WMS",
            "Organization": "Statistisk sentralbyrå",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": MISSING_URL,
            "Type": "service",
        },
        {"nested": True},
    ],
}
SENTRUM_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Service>
    <Title>Sentrumssoner WMS</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>sentrumssoner</Name>
      <Title>Sentrumssoner</Title>
      <Layer>
        <Name>sentrumssoner_flate</Name>
        <Title>Sentrumssoner flate</Title>
        <Abstract>skip</Abstract>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
FRITID_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0">
  <Service>
    <Title>Fritidsbyggområder WMS</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>fritidsbyggomraader</Name>
      <Title>Fritidsbyggområder</Title>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
AREALBRUK_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0">
  <Service>
    <Title>Arealbruk WMS</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>arealbruk</Name>
      <Title>Arealbruk</Title>
    </Layer>
  </Capability>
</WMS_Capabilities>
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
            SENTRUM_URL: SENTRUM_XML,
            FRITID_URL: FRITID_XML,
            AREALBRUK_URL: AREALBRUK_XML,
            HTML_URL: GLE_HTML,
        }
        if url == MISSING_URL:
            raise RuntimeError("HTTP 404")
        if url in pages:
            return pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == SENTRUM_URL:
            return SENTRUM_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ssbgis fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ssbgis fetch must GET, not POST {url}")


def test_printed_refs_skip_wfs_ssbv2_kv_hosts_servicelayer_html_and_404() -> None:
    http = CatalogHttp()
    source = SsbgisSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "sentrumssoner",
        "fritidsbyggomraader",
        "wms.arealbruk",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        SENTRUM_URL,
        FRITID_URL,
        AREALBRUK_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "sentrumssoner_wfs" for ref in refs)
    assert all(ref.source_native_id != "wms.topo" for ref in refs)
    assert all(ref.source_native_id != "wms.kartdata" for ref in refs)
    assert all(ref.source_native_id != "wms.topograatone" for ref in refs)
    assert all(ref.source_native_id != "wms.grunnkretser" for ref in refs)
    assert all(ref.source_native_id != "htmlssbgis" for ref in refs)
    assert all(ref.source_native_id != "missingssbgis" for ref in refs)
    assert HTML_URL in http.gets
    assert MISSING_URL in http.gets
    assert WFS_URL not in http.gets
    assert SSBV2_URL not in http.gets
    assert KVWMS_URL not in http.gets
    assert KVTOPO_URL not in http.gets
    assert KVGRUNN_URL not in http.gets
    assert GRUNNKRETS_URL not in http.gets
    assert any(url.startswith(f"{SEARCH_URL}?") for url in http.gets)


def test_printed_leftover_services_keep_document_order_and_unique_ids() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == [
        "sentrumssoner",
        "fritidsbyggomraader",
        "wms.arealbruk",
        "htmlssbgis",
        "missingssbgis",
    ]
    assert [href for _ident, href, _title in listed] == [
        SENTRUM_URL,
        FRITID_URL,
        AREALBRUK_URL,
        HTML_URL,
        MISSING_URL,
    ]


def test_printed_service_id_uses_printed_path_segment() -> None:
    assert printed_service_id(SENTRUM_URL) == "sentrumssoner"
    assert printed_service_id(FRITID_URL) == "fritidsbyggomraader"
    assert printed_service_id(AREALBRUK_URL) == "wms.arealbruk"
    assert printed_service_id(WFS_URL) == "sentrumssoner"
    assert printed_service_id(HTML_URL) == "htmlssbgis"
    assert printed_service_id("/") is None


def test_ssbgis_is_a_registered_source() -> None:
    assert "ssbgis" in SOURCE_IDS
    assert "ssbv2" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "kvgrunn" in SOURCE_IDS
    assert "nguminer" in SOURCE_IDS
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
    assert SOURCE_IDS[SOURCE_IDS.index("crinst") + 1] == "ssbgis"
    assert SOURCE_IDS[-1] == "ssbgis"
    source = build_source("ssbgis")
    assert isinstance(source, SsbgisSource)
    assert source.source_id == "ssbgis"
    assert build_source("ssbv2").source_id == "ssbv2"
    assert build_source("kvwms").source_id == "kvwms"
    assert build_source("kvtopo").source_id == "kvtopo"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = SsbgisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ssbgis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == SENTRUM_URL
    assert row["title"] == "Sentrumssoner WMS"
    fritid = registry.get_dataset("ssbgis:fritidsbyggomraader")
    assert fritid is not None
    assert fritid["access_path"] == FRITID_URL
    areal = registry.get_dataset("ssbgis:wms.arealbruk")
    assert areal is not None
    assert areal["access_path"] == AREALBRUK_URL
    assert areal["title"] == "Arealbruk WMS"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssbv2:")
    assert not str(row["id"]).startswith("kvwms:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["ssbgis_service_id"] == "sentrumssoner"
    assert payload["ssbgis_service_href"] == SENTRUM_URL
    assert payload["ssbgis_service_title"] == "Sentrumssoner WMS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = SsbgisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == SENTRUM_URL
    assert result.table_id == "sentrumssoner"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"sentrumssoner", "sentrumssoner_flate"}
    assert by_value["sentrumssoner"]["measure"] == "Name"
    dims = json.loads(by_value["sentrumssoner"]["dimensions_json"])
    assert dims["Title"] == "Sentrumssoner"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == SENTRUM_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_name() -> None:
    cells = cells_from_ssbgis(SENTRUM_XML)
    assert [value for _measure, value, _dims in cells] == [
        "sentrumssoner",
        "sentrumssoner_flate",
    ]
    measure, value, dims = cells[0]
    assert measure == "Name"
    assert value == "sentrumssoner"
    assert dims["Title"] == "Sentrumssoner"
    assert "Abstract" not in dims
    assert cells_from_ssbgis(FRITID_XML) == [
        ("Name", "fritidsbyggomraader", {"Title": "Fritidsbyggområder"})
    ]
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_ssbgis(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_ssbgis(GLE_HTML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_ssbgis("<WMS_Capabilities></WMS_Capabilities>")


def test_is_ssbgis_url_accepts_only_leftover_ssb_wms_paths() -> None:
    assert is_ssbgis_url(SENTRUM_URL)
    assert is_ssbgis_url(FRITID_URL)
    assert is_ssbgis_url(AREALBRUK_URL)
    assert ssbgis_table_id(SENTRUM_URL) == "sentrumssoner"
    assert ssbgis_table_id(FRITID_URL) == "fritidsbyggomraader"
    assert ssbgis_table_id(AREALBRUK_URL) == "wms.arealbruk"
    assert not is_ssbgis_url(WFS_URL)
    assert not is_ssbgis_url(SSBV2_URL)
    assert not is_ssbgis_url(KVWMS_URL)
    assert not is_ssbgis_url(KVTOPO_URL)
    assert not is_ssbgis_url(KVGRUNN_URL)
    assert not is_ssbgis_url(GRUNNKRETS_URL)
    assert not is_ssbv2_url(SENTRUM_URL)
    assert not is_ssbv2_url(AREALBRUK_URL)
    assert not is_kvwms_url(AREALBRUK_URL)
    assert not is_kvtopo_url(AREALBRUK_URL)
    assert not is_kvgrunn_url(AREALBRUK_URL)
    assert is_ssbv2_url(SSBV2_URL)
    assert is_kvwms_url(KVWMS_URL)
    assert is_kvtopo_url(KVTOPO_URL)
    assert not is_ssbgis_url("https://data.norge.no/datasets/x")
    assert not is_ssbgis_url(None)


def test_limit_and_offset_slice_printed_documents() -> None:
    source = SsbgisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "sentrumssoner"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["fritidsbyggomraader"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
