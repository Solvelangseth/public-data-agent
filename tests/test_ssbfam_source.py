from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ssbfam import (
    SsbfamSource,
    cells_from_ssbfam,
    is_ssbfam_url,
    printed_families,
    printed_family_id,
    printed_self_href,
    ssbfam_table_id,
)
from public_data_agent.ssb_klass import is_klass_url

LIST_URL = "https://data.ssb.no/api/klass/v1/classificationfamilies"
FAMILY_1_URL = "https://data.ssb.no/api/klass/v1/classificationfamilies/1"
FAMILY_3_URL = "https://data.ssb.no/api/klass/v1/classificationfamilies/3"
KLASS_VERSION_URL = "https://data.ssb.no/api/klass/v1/versions/683.json"
CLASSIFICATIONS_URL = "https://data.ssb.no/api/klass/v1/classifications"
SSB_V0_URL = "https://data.ssb.no/api/v0/no/table/06683"
SSBV2_URL = "https://data.ssb.no/api/pxwebapi/v2/tables/13760/data?lang=no&outputFormat=json-stat2"
DATASET_ID = "ssbfam:1"

CATALOG = {
    "_embedded": {
        "classificationFamilies": [
            {
                "name": "Arbeid og lønn",
                "id": 1,
                "numberOfClassifications": 1,
                "_links": {"self": {"href": FAMILY_1_URL}},
            },
            {
                "name": "Bank og finansmarked",
                "id": 2,
                "numberOfClassifications": 0,
                "_links": {"self": {"href": "https://data.ssb.no/api/klass/v1/classificationfamilies/2"}},
            },
            {
                "name": "Befolkning",
                "id": 3,
                "numberOfClassifications": 6,
                "_links": {"self": {"href": FAMILY_3_URL}},
            },
            {
                "name": "skip missing id",
                "id": None,
                "_links": {"self": {"href": FAMILY_1_URL}},
            },
            {
                "name": "skip missing href",
                "id": 99,
                "_links": {},
            },
            {"nested": True},
        ]
    }
}
FAMILY_1 = {
    "name": "Arbeid og lønn",
    "id": 1,
    "classifications": [
        {
            "name": "Standard for yrkesklassifisering",
            "id": 7,
            "classificationType": "Klassifikasjon",
            "classificationFamilyId": 1,
            "_links": {"self": {"href": "https://data.ssb.no/api/klass/v1/classifications/7"}},
        }
    ],
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return CATALOG
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == FAMILY_1_URL:
            return JsonResponse(status=200, url=url, body=FAMILY_1)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ssbfam fetch must GET, not POST {url}")


def test_printed_refs_copy_id_and_self_href() -> None:
    source = SsbfamSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["1", "2", "3"]
    assert [ref.source_native_uri for ref in refs] == [
        FAMILY_1_URL,
        "https://data.ssb.no/api/klass/v1/classificationfamilies/2",
        FAMILY_3_URL,
    ]
    assert all("classifications/" not in (ref.source_native_uri or "") for ref in refs)
    assert LIST_URL not in [ref.source_native_uri for ref in refs]


def test_printed_families_keep_document_order() -> None:
    listed = printed_families(CATALOG)
    assert [item["id"] for item in listed] == ["1", "2", "3"]
    assert printed_family_id(CATALOG["_embedded"]["classificationFamilies"][0]) == "1"
    assert printed_self_href(CATALOG["_embedded"]["classificationFamilies"][0]) == FAMILY_1_URL


def test_ssbfam_is_a_registered_source() -> None:
    assert "ssbfam" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    assert "ssbv2" in SOURCE_IDS
    assert "stormflo" in SOURCE_IDS
    assert "kystwfs" in SOURCE_IDS
    assert "nbcodelist" in SOURCE_IDS
    assert "nbdsd" in SOURCE_IDS
    assert "kvgrunn" in SOURCE_IDS
    assert "nbconcept" in SOURCE_IDS
    assert "kystnav" in SOURCE_IDS
    assert "mdirwms" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("mdirwms") + 1] == "ssbfam"
    source = build_source("ssbfam")
    assert isinstance(source, SsbfamSource)
    assert source.source_id == "ssbfam"


def test_harvest_writes_printed_id_and_keeps_license_null(tmp_path: Path) -> None:
    source = SsbfamSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ssbfam"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FAMILY_1_URL
    assert row["title"] == "Arbeid og lønn"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssb:")
    assert not str(row["id"]).startswith("ssbv2:")
    nxt = registry.get_dataset("ssbfam:3")
    assert nxt is not None
    assert nxt["access_path"] == FAMILY_3_URL
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["ssbfam_family"]["id"] == "1"
    assert payload["ssbfam_family"]["href"] == FAMILY_1_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_classification_name(tmp_path: Path) -> None:
    source = SsbfamSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == FAMILY_1_URL
    assert result.table_id == "1"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    assert len(rows) == 1
    assert rows[0]["measure"] == "name"
    assert json.loads(rows[0]["value_json"]) == "Standard for yrkesklassifisering"
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["id"] == "7"
    assert dims["classificationType"] == "Klassifikasjon"
    assert "classificationFamilyId" in dims
    assert "_links" not in dims
    assert rows[0]["publisher_name"] is None
    assert rows[0]["license"] is None
    assert rows[0]["access_path"] == FAMILY_1_URL
    registry.close()


def test_cells_copy_printed_classification_or_family_name() -> None:
    cells = cells_from_ssbfam(FAMILY_1)
    assert cells[0][0] == "name"
    assert cells[0][1] == "Standard for yrkesklassifisering"
    assert cells[0][2]["id"] == "7"
    assert "_links" not in cells[0][2]
    catalog_cells = cells_from_ssbfam(CATALOG)
    assert [cell[1] for cell in catalog_cells] == [
        "Arbeid og lønn",
        "Bank og finansmarked",
        "Befolkning",
        "skip missing id",
        "skip missing href",
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ssbfam(None)
    with pytest.raises(ValueError, match="family members"):
        cells_from_ssbfam({})


def test_is_ssbfam_url_accepts_only_classificationfamilies_path() -> None:
    assert is_ssbfam_url(FAMILY_1_URL)
    assert is_ssbfam_url(LIST_URL)
    assert ssbfam_table_id(FAMILY_1_URL) == "1"
    assert ssbfam_table_id(FAMILY_3_URL) == "3"
    assert ssbfam_table_id(LIST_URL) == "ssbfam"
    assert not is_ssbfam_url(KLASS_VERSION_URL)
    assert not is_ssbfam_url(CLASSIFICATIONS_URL)
    assert not is_ssbfam_url(SSB_V0_URL)
    assert not is_ssbfam_url(SSBV2_URL)
    assert not is_ssbfam_url("https://data.norge.no/datasets/x")
    assert not is_ssbfam_url(None)
    assert is_klass_url(FAMILY_1_URL)
    assert is_klass_url(KLASS_VERSION_URL)


def test_limit_and_offset_slice_printed_families() -> None:
    source = SsbfamSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["1"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["2"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
