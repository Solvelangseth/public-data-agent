from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nibioar5f import (
    Nibioar5fSource,
    SEARCH_URL,
    cells_from_nibioar5f,
    is_nibioar5f_url,
    nibioar5f_table_id,
    printed_leftover_services,
    printed_service_id,
    printed_wms_service_title,
)
from public_data_agent.sources.nibioar50 import is_nibioar50_url
from public_data_agent.sources.nibiorest import is_nibiorest_url
from public_data_agent.sources.nibiowms import is_nibiowms_url

AR5F_WMS_URL = (
    "https://wms.nibio.no/cgi-bin/ar5forvaltning2?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
AR50_WMS_URL = (
    "https://wms.nibio.no/cgi-bin/ar50_2?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
AR5_WMS_URL = (
    "https://wms.nibio.no/cgi-bin/ar5?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
HRL_URL = "https://wms.nibio.no/cgi-bin/hrl?VERSION=1.3.0&REQUEST=GetCapabilities&service=wms"
HTML_URL = (
    "https://wms.nibio.no/cgi-bin/ar5forvaltning2?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities&html=1"
)
DATASET_ID = "nibioar5f:ar5forvaltning2"

CATALOG = {
    "NumFound": 6,
    "Results": [
        {
            "Uuid": "7e6307a0-1a7d-4470-a722-a4368faf31e6",
            "Title": "Arealressurskart - FKB-AR5 - Forvaltning - 2 - WMS",
            "Organization": "Norsk institutt for bioøkonomi",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": AR5F_WMS_URL,
            "Type": "service",
            "AccessConstraint": "no restrictions",
            "AccessIsRestricted": False,
        },
        {
            "Uuid": "8f191dcd-bcec-4044-8259-a2a1b43cfb85",
            "Title": "Arealressurskart - AR50 - WMS",
            "Organization": "Norsk institutt for bioøkonomi",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": AR50_WMS_URL,
            "Type": "service",
            "AccessConstraint": "no restrictions",
            "AccessIsRestricted": False,
        },
        {
            "Uuid": "b1966b1e-8920-4405-bf0e-b8e7394ec8d5",
            "Title": "FKB-AR5 - WMS",
            "Organization": "Norsk institutt for bioøkonomi",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": AR5_WMS_URL,
            "Type": "service",
            "AccessConstraint": "norway digital restricted",
            "AccessIsRestricted": True,
        },
        {
            "Uuid": "servicelayer",
            "Title": "AR5 forvaltning layer",
            "Organization": "Norsk institutt for bioøkonomi",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": AR5F_WMS_URL,
            "Type": "servicelayer",
            "AccessConstraint": "no restrictions",
            "AccessIsRestricted": False,
        },
        {
            "Uuid": "html-ar5f",
            "Title": "HTML leftover",
            "Organization": "Norsk institutt for bioøkonomi",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": HTML_URL,
            "Type": "service",
            "AccessConstraint": "no restrictions",
            "AccessIsRestricted": False,
        },
        {
            "Uuid": "other-org",
            "Title": "Forvaltningsplanområder for havområdene WMS",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": (
                "https://kart.miljodirektoratet.no/geoserver/"
                "forvaltningsplaner_havomrader/wms?service=wms&version=1.3.0"
                "&request=getCapabilities"
            ),
            "Type": "service",
        },
        {"nested": True},
    ],
}
AR5F_WMS_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Service>
    <Title>WMS for AR5forvaltning fra NIBIO</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>AR5FORVALTNING</Name>
      <Title>WMS for AR5forvaltning fra NIBIO</Title>
      <Layer>
        <Name>Manuskart</Name>
        <Title>Manuskart</Title>
        <Abstract>skip</Abstract>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
AR5F_WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>ms:AR5FORVALTNING</Name>
      <Title>AR5FORVALTNING</Title>
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
        if url == AR5F_WMS_URL:
            return AR5F_WMS_XML
        if url == HTML_URL:
            return GLE_HTML
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == AR5F_WMS_URL:
            return AR5F_WMS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nibioar5f fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nibioar5f fetch must GET, not POST {url}")


def test_printed_refs_skip_restricted_ar5_ar50_html_and_downloads() -> None:
    http = CatalogHttp()
    source = Nibioar5fSource(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["ar5forvaltning2"]
    assert [ref.source_native_uri for ref in refs] == [AR5F_WMS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "ar5" for ref in refs)
    assert all(ref.source_native_id != "ar50_2" for ref in refs)
    assert all(ref.source_native_uri != AR5_WMS_URL for ref in refs)
    assert all(ref.source_native_uri != AR50_WMS_URL for ref in refs)
    assert AR5F_WMS_URL in http.gets
    assert HTML_URL in http.gets
    assert AR5_WMS_URL not in http.gets
    assert AR50_WMS_URL not in http.gets
    assert any("text=AR5+forvaltning" in url or "text=AR5+forvaltning".replace("+", "%20") in url for url in http.gets)


def test_printed_leftover_services_keep_document_order_and_unique_hrefs() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == ["ar5forvaltning2", "ar5forvaltning2"]
    assert [href for _ident, href, _title in listed] == [
        AR5F_WMS_URL,
        HTML_URL,
    ]
    assert AR5_WMS_URL not in [href for _ident, href, _title in listed]
    assert AR50_WMS_URL not in [href for _ident, href, _title in listed]


def test_printed_service_id_uses_printed_cgi_bin_name() -> None:
    assert printed_service_id(AR5F_WMS_URL) == "ar5forvaltning2"
    assert printed_service_id("/") is None


def test_printed_wms_service_title_copies_service_title() -> None:
    assert printed_wms_service_title(AR5F_WMS_XML) == "WMS for AR5forvaltning fra NIBIO"
    assert printed_wms_service_title(GLE_HTML) is None
    assert printed_wms_service_title(EXCEPTION_XML) is None


def test_nibioar5f_is_a_registered_source() -> None:
    assert "nibioar5f" in SOURCE_IDS
    assert "nibioar50" in SOURCE_IDS
    assert "nibiowms" in SOURCE_IDS
    assert "nibiorest" in SOURCE_IDS
    assert "nordatlas" in SOURCE_IDS
    assert "fbgis" in SOURCE_IDS
    assert "bwgis" in SOURCE_IDS
    assert "mdirgis" in SOURCE_IDS
    assert "nguminer" in SOURCE_IDS
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
    assert SOURCE_IDS[SOURCE_IDS.index("stskrift") + 1] == "nibiomark"
    assert SOURCE_IDS[-1] == "nibiomark"
    source = build_source("nibioar5f")
    assert isinstance(source, Nibioar5fSource)
    assert source.source_id == "nibioar5f"
    assert build_source("nibioar50").source_id == "nibioar50"
    assert build_source("nibiowms").source_id == "nibiowms"
    assert build_source("nibiorest").source_id == "nibiorest"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = Nibioar5fSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nibioar5f"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == AR5F_WMS_URL
    assert row["title"] == "WMS for AR5forvaltning fra NIBIO"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("nibiowms:")
    assert not str(row["id"]).startswith("nibiorest:")
    assert not str(row["id"]).startswith("nibioar50:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nibioar5f_service_id"] == "ar5forvaltning2"
    assert payload["nibioar5f_service_href"] == AR5F_WMS_URL
    assert payload["nibioar5f_service_title"] == "WMS for AR5forvaltning fra NIBIO"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = Nibioar5fSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == AR5F_WMS_URL
    assert result.table_id == "ar5forvaltning2"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"AR5FORVALTNING", "Manuskart"}
    assert by_value["Manuskart"]["measure"] == "Name"
    dims = json.loads(by_value["Manuskart"]["dimensions_json"])
    assert dims["Title"] == "Manuskart"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == AR5F_WMS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_and_feature_type_name() -> None:
    cells = cells_from_nibioar5f(AR5F_WMS_XML)
    assert [value for _measure, value, _dims in cells] == ["AR5FORVALTNING", "Manuskart"]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "Manuskart"
    assert dims["Title"] == "Manuskart"
    assert "Abstract" not in dims
    wfs_cells = cells_from_nibioar5f(AR5F_WFS_XML)
    assert wfs_cells == [("Name", "ms:AR5FORVALTNING", {"Title": "AR5FORVALTNING"})]
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_nibioar5f(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_nibioar5f(GLE_HTML)
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_nibioar5f(EXCEPTION_XML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_nibioar5f("<WMS_Capabilities></WMS_Capabilities>")


def test_is_nibioar5f_url_accepts_leftover_ar5f_and_skips_owned() -> None:
    assert is_nibioar5f_url(AR5F_WMS_URL)
    assert nibioar5f_table_id(AR5F_WMS_URL) == "ar5forvaltning2"
    assert not is_nibioar5f_url(AR50_WMS_URL)
    assert not is_nibioar5f_url(AR5_WMS_URL)
    assert not is_nibioar5f_url(HRL_URL)
    assert not is_nibioar5f_url(SEARCH_URL)
    assert not is_nibioar5f_url("https://data.norge.no/datasets/x")
    assert not is_nibioar5f_url(None)
    assert is_nibioar50_url(AR50_WMS_URL)
    assert not is_nibioar50_url(AR5F_WMS_URL)
    assert is_nibiowms_url(AR5F_WMS_URL)
    assert is_nibiorest_url(AR5F_WMS_URL)


def test_limit_and_offset_slice_printed_services() -> None:
    source = Nibioar5fSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["ar5forvaltning2"]
    assert source.list_dataset_refs(limit=1, offset=1) == []
