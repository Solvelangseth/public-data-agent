from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ssclass import (
    LIST_URL,
    SsclassSource,
    cells_from_ssclass,
    is_ssclass_url,
    printed_item_url,
    ssclass_table_id,
)

ITEM_URL = "https://data.ssb.no/api/klass/v1/classifications/1"
NEXT_URL = "https://data.ssb.no/api/klass/v1/classifications/2"
FAMILIES_URL = "https://data.ssb.no/api/klass/v1/classificationfamilies"
FAMILY_URL = "https://data.ssb.no/api/klass/v1/classificationfamilies/1"
VERSION_URL = "https://data.ssb.no/api/klass/v1/versions/1"
CODES_URL = "https://data.ssb.no/api/klass/v1/classifications/1/codes"
SEARCH_URL = "https://data.ssb.no/api/klass/v1/classifications/search"
SSBV2_URL = "https://data.ssb.no/api/pxwebapi/v2/tables"
SSB_V0_URL = "https://data.ssb.no/api/v0/no/table"
DATASET_ID = "ssclass:1"

CATALOG = {
    "_embedded": {
        "classifications": [
            {
                "id": 1,
                "name": "Standard for delområde- og grunnkretsinndeling",
                "classificationType": "Klassifikasjon",
                "classificationFamilyId": 15,
                "lastModified": "2026-08-05T11:10:37.000+0000",
                "_links": {"self": {"href": ITEM_URL}},
            },
            {
                "id": 2,
                "name": "Standard for kjønn",
                "classificationType": "Klassifikasjon",
                "classificationFamilyId": 3,
                "_links": {"self": {"href": NEXT_URL}},
            },
            {
                "name": "missing id is skipped",
                "_links": {"self": {"href": "https://data.ssb.no/api/klass/v1/classifications/x"}},
            },
        ]
    },
    "page": {"size": 20, "totalElements": 151, "totalPages": 8, "number": 0},
}
CLASS_BODY = {
    "name": "Standard for delområde- og grunnkretsinndeling",
    "id": 1,
    "classificationType": "Klassifikasjon",
    "classificationFamilyId": 15,
    "versions": [
        {
            "name": "Delområde- og grunnkretsinndeling 2016",
            "id": 1,
            "validFrom": "2016-01-01",
            "validTo": "2017-01-01",
            "published": ["nb", "nn", "en"],
            "_links": {"self": {"href": VERSION_URL}},
        },
        {
            "name": "Delområde- og grunnkretsinndeling 2017",
            "id": 2,
            "validFrom": "2017-01-01",
        },
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
        if url == ITEM_URL:
            return JsonResponse(status=200, url=url, body=CLASS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ssclass fetch must GET, not POST {url}")


def test_printed_refs_copy_classification_ids() -> None:
    source = SsclassSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["1", "2"]
    assert [ref.source_native_uri for ref in refs] == [ITEM_URL, NEXT_URL]
    assert all("/classificationfamilies" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/versions/" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_self_href() -> None:
    assert (
        printed_item_url({"id": 1, "_links": {"self": {"href": ITEM_URL}}}, LIST_URL)
        == ITEM_URL
    )
    assert printed_item_url({"id": 7}, LIST_URL) == (
        "https://data.ssb.no/api/klass/v1/classifications/7"
    )


def test_ssclass_is_a_registered_source() -> None:
    assert "ssclass" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    assert "ssbv2" in SOURCE_IDS
    assert "ssbfam" in SOURCE_IDS
    assert "ssbsec" in SOURCE_IDS
    assert "nbconcept" in SOURCE_IDS
    source = build_source("ssclass")
    assert isinstance(source, SsclassSource)
    assert source.source_id == "ssclass"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = SsclassSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ssclass"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ITEM_URL
    assert row["title"] == "Standard for delområde- og grunnkretsinndeling"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssb:")
    assert not str(row["id"]).startswith("ssbv2:")
    nxt = registry.get_dataset("ssclass:2")
    assert nxt is not None
    assert nxt["title"] == "Standard for kjønn"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "1"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["ssclass_classification"]["id"] == 1
    assert "_links" not in payload["ssclass_classification"]
    assert "versions" not in payload["ssclass_classification"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_version_names(tmp_path: Path) -> None:
    source = SsclassSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ITEM_URL
    assert result.table_id == "1"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {
        "Delområde- og grunnkretsinndeling 2016",
        "Delområde- og grunnkretsinndeling 2017",
    }
    assert all(row["measure"] == "name" for row in rows)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_value["Delområde- og grunnkretsinndeling 2016"]["dimensions_json"])
    assert dims["id"] == "1"
    assert dims["validFrom"] == "2016-01-01"
    assert dims["validTo"] == "2017-01-01"
    assert "published" not in dims
    assert "_links" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ITEM_URL for row in rows)
    registry.close()


def test_cells_copy_printed_versions() -> None:
    cells = cells_from_ssclass(CLASS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Delområde- og grunnkretsinndeling 2016"
    assert dims["id"] == "1"
    assert "published" not in dims
    fallback = cells_from_ssclass({"id": 9, "name": "Standard for kjønn"})
    assert fallback == [("name", "Standard for kjønn", {"id": "9"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ssclass(["Standard for kjønn"])
    with pytest.raises(ValueError, match="classification members"):
        cells_from_ssclass({"versions": []})


def test_is_ssclass_url_accepts_only_classifications_paths() -> None:
    assert is_ssclass_url(ITEM_URL)
    assert is_ssclass_url(LIST_URL)
    assert ssclass_table_id(ITEM_URL) == "1"
    assert not is_ssclass_url(FAMILIES_URL)
    assert not is_ssclass_url(FAMILY_URL)
    assert not is_ssclass_url(VERSION_URL)
    assert not is_ssclass_url(CODES_URL)
    assert not is_ssclass_url(SEARCH_URL)
    assert not is_ssclass_url(SSBV2_URL)
    assert not is_ssclass_url(SSB_V0_URL)
    assert not is_ssclass_url("https://data.norge.no/datasets/x")
    assert not is_ssclass_url(None)


def test_limit_and_offset_slice_printed_classifications() -> None:
    source = SsclassSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["1"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["2"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
