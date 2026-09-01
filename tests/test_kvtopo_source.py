from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kvgrunn import (
    NORGES_GRUNNKART_URL,
    TOPOGRAATONE_URL,
    is_kvgrunn_url,
)
from public_data_agent.sources.kvtopo import (
    FJELLSKYGGE_URL,
    FRILUFTSRUTER_URL,
    FKB_URL,
    KARTDATA_URL,
    MARKAGRENSEN_URL,
    N5RASTER_URL,
    KvtopoSource,
    cells_from_kvtopo,
    is_kvtopo_url,
    kvtopo_table_id,
    printed_service_id,
    printed_services,
)
from public_data_agent.sources.kvwms import WMTS_URL, WMS_URL, is_kvwms_url

DATASET_ID = "kvtopo:wms.kartdata"
MATRIKKELKART_URL = (
    "https://wms.geonorge.no/skwms1/wms.matrikkelkart?service=wms&request=getcapabilities"
)
HAVNEDATA_URL = "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/api?f=json"

KARTDATA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>kartdata</Title>
    <OnlineResource href="https://wms.geonorge.no/skwms1/wms.kartdata?"/>
  </Service>
  <Capability>
    <Layer>
      <Title>root</Title>
      <Layer>
        <Name>kartdata</Name>
        <Title>Kartdata</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>arealdekkeflate</Name>
        <Title>Arealdekke</Title>
      </Layer>
      <Layer>
        <Name></Name>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

FKB_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>fkb WMS</Title>
    <OnlineResource href="https://wms.geonorge.no/skwms1/wms.fkb?"/>
  </Service>
  <Capability>
    <Layer>
      <Name>fkb</Name>
      <Title>FKB</Title>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

FRILUFT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>Tur- og friluftsruter WMS</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>fotrute</Name>
      <Title>Fotrute</Title>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

FJELL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>Fjellskygge</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>fjellskygge</Name>
      <Title>Fjellskygge</Title>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

N5_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>N5Raster2 WMS</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>n5raster2</Name>
      <Title>N5Raster2</Title>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

MARKA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities>
  <Service>
    <Name>WMS</Name>
    <Title>Markagrensen</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>markagrensen</Name>
      <Title>Markagrensen</Title>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

HTML_ERROR = """
<html><head><title>MapServer Message</title></head>
<body>msWMSDispatch(): WMS server error.</body></html>
"""

DEFAULT_PAGES = {
    KARTDATA_URL: KARTDATA_XML,
    FKB_URL: FKB_XML,
    FRILUFTSRUTER_URL: FRILUFT_XML,
    FJELLSKYGGE_URL: FJELL_XML,
    N5RASTER_URL: N5_XML,
    MARKAGRENSEN_URL: MARKA_XML,
}


class CatalogHttp:
    def __init__(self, pages: dict[str, str] | None = None) -> None:
        self.gets: list[str] = []
        self.pages = pages or DEFAULT_PAGES

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url in self.pages:
            return self.pages[url]
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == KARTDATA_URL:
            return KARTDATA_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kvtopo fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kvtopo fetch must GET, not POST {url}")


def test_printed_refs_keep_live_xml_and_skip_html() -> None:
    http = CatalogHttp()
    source = KvtopoSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "wms.kartdata",
        "wms.fkb",
        "wms.friluftsruter2",
        "wms.fjellskygge",
        "wms.n5raster2",
        "wms.markagrensen",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        KARTDATA_URL,
        FKB_URL,
        FRILUFTSRUTER_URL,
        FJELLSKYGGE_URL,
        N5RASTER_URL,
        MARKAGRENSEN_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "WMS" for ref in refs)
    assert all(ref.source_native_id != "wms.topo" for ref in refs)
    assert all(ref.source_native_id != "wms.topograatone" for ref in refs)
    assert all(ref.source_native_id != "wms.norges_grunnkart" for ref in refs)
    assert all(ref.source_native_id != "wms.matrikkelkart" for ref in refs)
    assert all(ref.source_native_id != "wmts" for ref in refs)
    assert WMS_URL not in [ref.source_native_uri for ref in refs]
    assert WMTS_URL not in [ref.source_native_uri for ref in refs]
    assert TOPOGRAATONE_URL not in [ref.source_native_uri for ref in refs]
    assert NORGES_GRUNNKART_URL not in [ref.source_native_uri for ref in refs]
    assert MATRIKKELKART_URL not in [ref.source_native_uri for ref in refs]
    assert HAVNEDATA_URL not in [ref.source_native_uri for ref in refs]


def test_printed_refs_skip_html_capabilities() -> None:
    pages = dict(DEFAULT_PAGES)
    pages[KARTDATA_URL] = HTML_ERROR
    http = CatalogHttp(pages)
    source = KvtopoSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "wms.fkb",
        "wms.friluftsruter2",
        "wms.fjellskygge",
        "wms.n5raster2",
        "wms.markagrensen",
    ]
    assert KARTDATA_URL in http.gets


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(KARTDATA_XML, KARTDATA_URL)
    assert [ident for ident, _href, _title in listed] == ["wms.kartdata"]
    assert [href for _ident, href, _title in listed] == [KARTDATA_URL]
    assert [title for _ident, _href, title in listed] == ["kartdata"]
    listed = printed_services(FKB_XML, FKB_URL)
    assert [ident for ident, _href, _title in listed] == ["wms.fkb"]
    assert [title for _ident, _href, title in listed] == ["fkb WMS"]


def test_printed_service_id_uses_last_skwms1_segment() -> None:
    assert printed_service_id(KARTDATA_URL) == "wms.kartdata"
    assert printed_service_id(FKB_URL) == "wms.fkb"
    assert printed_service_id(FRILUFTSRUTER_URL) == "wms.friluftsruter2"
    assert printed_service_id(FJELLSKYGGE_URL) == "wms.fjellskygge"
    assert printed_service_id(N5RASTER_URL) == "wms.n5raster2"
    assert printed_service_id(MARKAGRENSEN_URL) == "wms.markagrensen"
    assert printed_service_id(WMS_URL) == "wms.topo"
    assert printed_service_id(MATRIKKELKART_URL) == "wms.matrikkelkart"
    assert printed_service_id("/") is None


def test_kvtopo_is_a_registered_source() -> None:
    assert "kvtopo" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    assert "kvgrunn" in SOURCE_IDS
    assert "hiwms" in SOURCE_IDS
    assert "havnedata" in SOURCE_IDS
    assert "geonorge" in SOURCE_IDS
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
    assert SOURCE_IDS[-1] == "nibiogard"
    source = build_source("kvtopo")
    assert isinstance(source, KvtopoSource)
    assert source.source_id == "kvtopo"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = KvtopoSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 6
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kvtopo"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == KARTDATA_URL
    assert row["title"] == "kartdata"
    fkb = registry.get_dataset("kvtopo:wms.fkb")
    assert fkb is not None
    assert fkb["access_path"] == FKB_URL
    assert fkb["title"] == "fkb WMS"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kvwms:")
    assert not str(row["id"]).startswith("kvgrunn:")
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("havnedata:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["kvtopo_service_id"] == "wms.kartdata"
    assert payload["kvtopo_service_href"] == KARTDATA_URL
    assert payload["kvtopo_service_title"] == "kartdata"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = KvtopoSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == KARTDATA_URL
    assert result.table_id == "wms.kartdata"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"kartdata", "arealdekkeflate"}
    assert by_value["kartdata"]["measure"] == "Name"
    dims = json.loads(by_value["kartdata"]["dimensions_json"])
    assert dims["Title"] == "Kartdata"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == KARTDATA_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_name() -> None:
    cells = cells_from_kvtopo(KARTDATA_XML)
    assert [value for _measure, value, _dims in cells] == [
        "kartdata",
        "arealdekkeflate",
    ]
    measure, value, dims = cells[0]
    assert measure == "Name"
    assert value == "kartdata"
    assert dims["Title"] == "Kartdata"
    assert "Abstract" not in dims
    assert cells_from_kvtopo(FKB_XML) == [
        ("Name", "fkb", {"Title": "FKB"})
    ]
    with pytest.raises(ValueError, match="WMS XML"):
        cells_from_kvtopo(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_kvtopo(HTML_ERROR)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_kvtopo("<WMS_Capabilities></WMS_Capabilities>")


def test_is_kvtopo_url_accepts_only_leftover_topo_paths() -> None:
    assert is_kvtopo_url(KARTDATA_URL)
    assert is_kvtopo_url(FKB_URL)
    assert is_kvtopo_url(FRILUFTSRUTER_URL)
    assert is_kvtopo_url(FJELLSKYGGE_URL)
    assert is_kvtopo_url(N5RASTER_URL)
    assert is_kvtopo_url(MARKAGRENSEN_URL)
    assert kvtopo_table_id(KARTDATA_URL) == "wms.kartdata"
    assert kvtopo_table_id(FRILUFTSRUTER_URL) == "wms.friluftsruter2"
    assert not is_kvtopo_url(WMS_URL)
    assert not is_kvtopo_url(WMTS_URL)
    assert not is_kvtopo_url(TOPOGRAATONE_URL)
    assert not is_kvtopo_url(NORGES_GRUNNKART_URL)
    assert not is_kvtopo_url(MATRIKKELKART_URL)
    assert not is_kvtopo_url(HAVNEDATA_URL)
    assert not is_kvwms_url(KARTDATA_URL)
    assert not is_kvwms_url(FKB_URL)
    assert not is_kvgrunn_url(KARTDATA_URL)
    assert not is_kvgrunn_url(FKB_URL)
    assert is_kvwms_url(WMS_URL)
    assert is_kvgrunn_url(NORGES_GRUNNKART_URL)
    assert not is_kvtopo_url("https://data.norge.no/datasets/x")
    assert not is_kvtopo_url(None)


def test_limit_and_offset_slice_printed_documents() -> None:
    source = KvtopoSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "wms.kartdata"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["wms.fkb"]
    assert source.list_dataset_refs(limit=1, offset=6) == []
