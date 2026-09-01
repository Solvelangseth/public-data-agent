from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kvadm import (
    ADM_WFS_URL,
    ADM_WMS_URL,
    KvadmSource,
    cells_from_kvadm,
    is_kvadm_url,
    kvadm_table_id,
    printed_service_id,
    printed_services,
)
from public_data_agent.sources.kvgrunn import NORGES_GRUNNKART_URL, is_kvgrunn_url
from public_data_agent.sources.kvtopo import KARTDATA_URL, is_kvtopo_url
from public_data_agent.sources.kvwms import WMS_URL, is_kvwms_url

DATASET_ID = "kvadm:wms.adm_enheter2"
HISTORISK_URL = (
    "https://wms.geonorge.no/skwms1/wms.adm_enheter_historisk"
    "?service=WMS&request=GetCapabilities"
)
KOMMUNEINFO_URL = "https://ws.geonorge.no/kommuneinfo/v1/"

ADM_WMS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities version="1.3.0">
  <Service>
    <Name>WMS</Name>
    <Title>Administrative enheter WMS</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>adm_enheter_V2_WMS</Name>
      <Title>Administrative enheter</Title>
      <Layer>
        <Name>kommuner</Name>
        <Title>Kommuner</Title>
        <Abstract>skip</Abstract>
      </Layer>
      <Layer>
        <Name>kommuner_gjel</Name>
        <Title>Kommuner gjeldende</Title>
      </Layer>
      <Layer>
        <Name></Name>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

ADM_WFS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<WFS_Capabilities version="2.0.0">
  <ServiceIdentification>
    <Title>Administrative enheter WFS</Title>
  </ServiceIdentification>
  <FeatureTypeList>
    <FeatureType>
      <Name>app:Fylke</Name>
      <Title>Fylke</Title>
    </FeatureType>
    <FeatureType>
      <Name>app:Kommune</Name>
      <Title>Kommune</Title>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
"""

HTML_ERROR = """
<html><head><title>MapServer Message</title></head>
<body>msWMSDispatch(): WMS server error.</body></html>
"""

DEFAULT_PAGES = {
    ADM_WMS_URL: ADM_WMS_XML,
    ADM_WFS_URL: ADM_WFS_XML,
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
        if url == ADM_WMS_URL:
            return ADM_WMS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kvadm fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kvadm fetch must GET, not POST {url}")


def test_printed_refs_keep_live_xml_and_skip_owned() -> None:
    http = CatalogHttp()
    source = KvadmSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "wms.adm_enheter2",
        "wfs.administrative_enheter",
    ]
    assert [ref.source_native_uri for ref in refs] == [ADM_WMS_URL, ADM_WFS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "wms.topo" for ref in refs)
    assert all(ref.source_native_id != "wms.kartdata" for ref in refs)
    assert all(ref.source_native_id != "wms.adm_enheter_historisk" for ref in refs)
    assert WMS_URL not in [ref.source_native_uri for ref in refs]
    assert KARTDATA_URL not in [ref.source_native_uri for ref in refs]
    assert HISTORISK_URL not in [ref.source_native_uri for ref in refs]
    assert KOMMUNEINFO_URL not in [ref.source_native_uri for ref in refs]


def test_printed_refs_skip_html_capabilities() -> None:
    pages = dict(DEFAULT_PAGES)
    pages[ADM_WMS_URL] = HTML_ERROR
    http = CatalogHttp(pages)
    source = KvadmSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["wfs.administrative_enheter"]
    assert ADM_WMS_URL in http.gets


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(ADM_WMS_XML, ADM_WMS_URL)
    assert [ident for ident, _href, _title in listed] == ["wms.adm_enheter2"]
    assert [href for _ident, href, _title in listed] == [ADM_WMS_URL]
    assert [title for _ident, _href, title in listed] == ["Administrative enheter WMS"]
    listed = printed_services(ADM_WFS_XML, ADM_WFS_URL)
    assert [ident for ident, _href, _title in listed] == ["wfs.administrative_enheter"]
    assert [title for _ident, _href, title in listed] == ["Administrative enheter WFS"]


def test_printed_service_id_uses_last_skwms1_segment() -> None:
    assert printed_service_id(ADM_WMS_URL) == "wms.adm_enheter2"
    assert printed_service_id(ADM_WFS_URL) == "wfs.administrative_enheter"
    assert printed_service_id(WMS_URL) == "wms.topo"
    assert printed_service_id(HISTORISK_URL) == "wms.adm_enheter_historisk"
    assert printed_service_id("/") is None


def test_kvadm_is_a_registered_source() -> None:
    assert "kvadm" in SOURCE_IDS
    assert "ssbgis" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "kvgrunn" in SOURCE_IDS
    assert "kommuneinfo" in SOURCE_IDS
    assert "barmark" in SOURCE_IDS
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
    assert SOURCE_IDS[SOURCE_IDS.index("stskrift") + 1] == "sthoring"
    assert SOURCE_IDS[-1] == "sthoring"
    source = build_source("kvadm")
    assert isinstance(source, KvadmSource)
    assert source.source_id == "kvadm"
    assert build_source("ssbgis").source_id == "ssbgis"
    assert build_source("kvwms").source_id == "kvwms"
    assert build_source("kvtopo").source_id == "kvtopo"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = KvadmSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kvadm"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ADM_WMS_URL
    assert row["title"] == "Administrative enheter WMS"
    wfs = registry.get_dataset("kvadm:wfs.administrative_enheter")
    assert wfs is not None
    assert wfs["access_path"] == ADM_WFS_URL
    assert wfs["title"] == "Administrative enheter WFS"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kvwms:")
    assert not str(row["id"]).startswith("kvtopo:")
    assert not str(row["id"]).startswith("kvgrunn:")
    assert not str(row["id"]).startswith("kommuneinfo:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["kvadm_service_id"] == "wms.adm_enheter2"
    assert payload["kvadm_service_href"] == ADM_WMS_URL
    assert payload["kvadm_service_title"] == "Administrative enheter WMS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = KvadmSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ADM_WMS_URL
    assert result.table_id == "wms.adm_enheter2"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"adm_enheter_V2_WMS", "kommuner", "kommuner_gjel"}
    assert by_value["kommuner"]["measure"] == "Name"
    dims = json.loads(by_value["kommuner"]["dimensions_json"])
    assert dims["Title"] == "Kommuner"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ADM_WMS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_and_feature_type_name() -> None:
    cells = cells_from_kvadm(ADM_WMS_XML)
    assert [value for _measure, value, _dims in cells] == [
        "adm_enheter_V2_WMS",
        "kommuner",
        "kommuner_gjel",
    ]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "kommuner"
    assert dims["Title"] == "Kommuner"
    assert "Abstract" not in dims
    assert cells_from_kvadm(ADM_WFS_XML) == [
        ("Name", "app:Fylke", {"Title": "Fylke"}),
        ("Name", "app:Kommune", {"Title": "Kommune"}),
    ]
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_kvadm(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_kvadm(HTML_ERROR)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_kvadm("<WMS_Capabilities></WMS_Capabilities>")
    with pytest.raises(ValueError, match="FeatureType Name"):
        cells_from_kvadm("<WFS_Capabilities></WFS_Capabilities>")


def test_is_kvadm_url_accepts_only_leftover_admin_paths() -> None:
    assert is_kvadm_url(ADM_WMS_URL)
    assert is_kvadm_url(ADM_WFS_URL)
    assert kvadm_table_id(ADM_WMS_URL) == "wms.adm_enheter2"
    assert kvadm_table_id(ADM_WFS_URL) == "wfs.administrative_enheter"
    assert not is_kvadm_url(WMS_URL)
    assert not is_kvadm_url(KARTDATA_URL)
    assert not is_kvadm_url(NORGES_GRUNNKART_URL)
    assert not is_kvadm_url(HISTORISK_URL)
    assert not is_kvadm_url(KOMMUNEINFO_URL)
    assert not is_kvwms_url(ADM_WMS_URL)
    assert not is_kvtopo_url(ADM_WMS_URL)
    assert not is_kvgrunn_url(ADM_WMS_URL)
    assert is_kvwms_url(WMS_URL)
    assert is_kvtopo_url(KARTDATA_URL)
    assert not is_kvadm_url("https://data.norge.no/datasets/x")
    assert not is_kvadm_url(None)


def test_limit_and_offset_slice_printed_documents() -> None:
    source = KvadmSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "wms.adm_enheter2"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["wfs.administrative_enheter"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
