from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nibioar50 import (
    Nibioar50Source,
    SEARCH_URL,
    cells_from_nibioar50,
    is_nibioar50_url,
    nibioar50_table_id,
    printed_leftover_services,
    printed_service_id,
)
from public_data_agent.sources.nibiorest import is_nibiorest_url
from public_data_agent.sources.nibiowms import is_nibiowms_url

AR50_WMS_URL = (
    "https://wms.nibio.no/cgi-bin/ar50_2?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
AR50_WFS_URL = "https://wfs.nibio.no/cgi-bin/ar50_2?Service=WFS&Request=GetCapabilities"
AR5_WMS_URL = (
    "https://wms.nibio.no/cgi-bin/ar5?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
HRL_URL = "https://wms.nibio.no/cgi-bin/hrl?VERSION=1.3.0&REQUEST=GetCapabilities&service=wms"
HTML_URL = (
    "https://wms.nibio.no/cgi-bin/ar50_2?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities&html=1"
)
DATASET_ID = "nibioar50:ar50_2"

CATALOG = {
    "NumFound": 8,
    "Results": [
        {
            "Uuid": "ar50-dataset",
            "Title": "Arealressurskart - AR50",
            "Organization": "Norsk institutt for bioøkonomi",
            "DistributionProtocol": "GEONORGE:DOWNLOAD",
            "DistributionUrl": "https://kart8.nibio.no/api/capabilities/",
            "Type": "dataset",
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
            "Uuid": "a7949917-033c-4e78-8c0f-e30323ce353a",
            "Title": "Arealressurskart - AR50 - WFS",
            "Organization": "Norsk institutt for bioøkonomi",
            "DistributionProtocol": "OGC:WFS",
            "DistributionUrl": AR50_WFS_URL,
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
            "Title": "AR50 layer",
            "Organization": "Norsk institutt for bioøkonomi",
            "DistributionProtocol": "OGC:WMS",
            "DistributionUrl": AR50_WMS_URL,
            "Type": "servicelayer",
            "AccessConstraint": "no restrictions",
            "AccessIsRestricted": False,
        },
        {
            "Uuid": "html-ar50",
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
            "Title": "Hovedøkosystemer i Norge - versjon 1",
            "Organization": "Miljødirektoratet",
            "DistributionProtocol": "W3C:REST",
            "DistributionUrl": (
                "https://kart2.miljodirektoratet.no/arcgis/rest/services/"
                "hovedokosystem/hovedokosystem/MapServer"
            ),
            "Type": "dataset",
        },
        {"nested": True},
    ],
}
AR50_WMS_XML = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Service>
    <Title>WMS for AR50 fra NIBIO</Title>
  </Service>
  <Capability>
    <Layer>
      <Name>AR50_2</Name>
      <Title>WMS for AR50 fra NIBIO</Title>
      <Layer>
        <Name>Bonitet</Name>
        <Title>Bonitet</Title>
        <Abstract>skip</Abstract>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""
AR50_WFS_XML = """<?xml version="1.0"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <FeatureTypeList>
    <FeatureType>
      <Name>ms:AR50</Name>
      <Title>AR50</Title>
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
        if url == AR50_WMS_URL:
            return AR50_WMS_XML
        if url == AR50_WFS_URL:
            raise RuntimeError("certificate verify failed")
        if url == HTML_URL:
            return GLE_HTML
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == AR50_WMS_URL:
            return AR50_WMS_XML
        raise AssertionError(f"unexpected GET {url}")

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nibioar50 fetch must GET text, not JSON {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nibioar50 fetch must GET, not POST {url}")


def test_printed_refs_skip_restricted_ar5_html_wfs_ssl_and_downloads() -> None:
    http = CatalogHttp()
    source = Nibioar50Source(http=http)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["ar50_2"]
    assert [ref.source_native_uri for ref in refs] == [AR50_WMS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "ar5" for ref in refs)
    assert all(ref.source_native_uri != AR5_WMS_URL for ref in refs)
    assert all(ref.source_native_uri != AR50_WFS_URL for ref in refs)
    assert AR50_WMS_URL in http.gets
    assert AR50_WFS_URL in http.gets
    assert HTML_URL in http.gets
    assert AR5_WMS_URL not in http.gets
    assert any("text=AR50" in url for url in http.gets)


def test_printed_leftover_services_keep_document_order_and_unique_hrefs() -> None:
    listed = printed_leftover_services(CATALOG["Results"])
    assert [ident for ident, _href, _title in listed] == ["ar50_2", "ar50_2_wfs", "ar50_2"]
    assert [href for _ident, href, _title in listed] == [
        AR50_WMS_URL,
        AR50_WFS_URL,
        HTML_URL,
    ]
    assert AR5_WMS_URL not in [href for _ident, href, _title in listed]


def test_printed_service_id_uses_printed_cgi_bin_name() -> None:
    assert printed_service_id(AR50_WMS_URL) == "ar50_2"
    assert printed_service_id(AR50_WFS_URL) == "ar50_2_wfs"
    assert printed_service_id("/") is None


def test_nibioar50_is_a_registered_source() -> None:
    assert "nibioar50" in SOURCE_IDS
    assert "nibiowms" in SOURCE_IDS
    assert "nibiorest" in SOURCE_IDS
    assert "nordatlas" in SOURCE_IDS
    assert "bwgis" in SOURCE_IDS
    assert "mdirgis" in SOURCE_IDS
    assert "nguminer" in SOURCE_IDS
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
    assert SOURCE_IDS[-1] == "stmoter"
    source = build_source("nibioar50")
    assert isinstance(source, Nibioar50Source)
    assert source.source_id == "nibioar50"
    assert build_source("nibiowms").source_id == "nibiowms"
    assert build_source("nibiorest").source_id == "nibiorest"
    assert build_source("nordatlas").source_id == "nordatlas"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = Nibioar50Source(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nibioar50"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == AR50_WMS_URL
    assert row["title"] == "Arealressurskart - AR50 - WMS"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("nibiowms:")
    assert not str(row["id"]).startswith("nibiorest:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nibioar50_service_id"] == "ar50_2"
    assert payload["nibioar50_service_href"] == AR50_WMS_URL
    assert payload["nibioar50_service_title"] == "Arealressurskart - AR50 - WMS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_copies_layer_name_cells(tmp_path: Path) -> None:
    source = Nibioar50Source(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == AR50_WMS_URL
    assert result.table_id == "ar50_2"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"AR50_2", "Bonitet"}
    assert by_value["Bonitet"]["measure"] == "Name"
    dims = json.loads(by_value["Bonitet"]["dimensions_json"])
    assert dims["Title"] == "Bonitet"
    assert "Abstract" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == AR50_WMS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_layer_and_feature_type_name() -> None:
    cells = cells_from_nibioar50(AR50_WMS_XML)
    assert [value for _measure, value, _dims in cells] == ["AR50_2", "Bonitet"]
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "Bonitet"
    assert dims["Title"] == "Bonitet"
    assert "Abstract" not in dims
    wfs_cells = cells_from_nibioar50(AR50_WFS_XML)
    assert wfs_cells == [("Name", "ms:AR50", {"Title": "AR50"})]
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_nibioar50(None)
    with pytest.raises(ValueError, match="HTML"):
        cells_from_nibioar50(GLE_HTML)
    with pytest.raises(ValueError, match="WMS/WFS XML"):
        cells_from_nibioar50(EXCEPTION_XML)
    with pytest.raises(ValueError, match="Layer Name"):
        cells_from_nibioar50("<WMS_Capabilities></WMS_Capabilities>")


def test_is_nibioar50_url_accepts_leftover_ar50_and_skips_owned() -> None:
    assert is_nibioar50_url(AR50_WMS_URL)
    assert is_nibioar50_url(AR50_WFS_URL)
    assert nibioar50_table_id(AR50_WMS_URL) == "ar50_2"
    assert nibioar50_table_id(AR50_WFS_URL) == "ar50_2_wfs"
    assert not is_nibioar50_url(AR5_WMS_URL)
    assert not is_nibioar50_url(HRL_URL)
    assert not is_nibioar50_url(SEARCH_URL)
    assert not is_nibioar50_url("https://data.norge.no/datasets/x")
    assert not is_nibioar50_url(None)
    assert is_nibiowms_url(AR50_WMS_URL)
    assert is_nibiorest_url(AR50_WMS_URL)
    assert not is_nibiowms_url(AR50_WFS_URL)
    assert not is_nibiorest_url(AR50_WFS_URL)


def test_limit_and_offset_slice_printed_services() -> None:
    source = Nibioar50Source(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["ar50_2"]
    assert source.list_dataset_refs(limit=1, offset=1) == []
