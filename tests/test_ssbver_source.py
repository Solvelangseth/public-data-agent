from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ssbver import (
    LIST_URL,
    SsbverSource,
    cells_from_ssbver,
    is_ssbver_url,
    printed_item_url,
    ssbver_table_id,
)

ITEM_URL = "https://data.ssb.no/api/klass/v1/classifications/1"
NEXT_URL = "https://data.ssb.no/api/klass/v1/classifications/2"
VERSION_URL = "https://data.ssb.no/api/klass/v1/versions/1"
NEXT_VERSION_URL = "https://data.ssb.no/api/klass/v1/versions/2"
FAMILIES_URL = "https://data.ssb.no/api/klass/v1/classificationfamilies"
CODES_URL = "https://data.ssb.no/api/klass/v1/classifications/1/codes"
CORR_URL = "https://data.ssb.no/api/klass/v1/correspondencetables/160"
SSBV2_URL = "https://data.ssb.no/api/pxwebapi/v2/tables"
SSB_V0_URL = "https://data.ssb.no/api/v0/no/table"
DATASET_ID = "ssbver:1"

CATALOG = {
    "_embedded": {
        "classifications": [
            {
                "id": 1,
                "name": "Standard for delområde- og grunnkretsinndeling",
                "classificationType": "Klassifikasjon",
                "_links": {"self": {"href": ITEM_URL}},
            },
            {
                "id": 2,
                "name": "Standard for kjønn",
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
            "name": "Delområde- og grunnkretsinndeling 2014",
            "id": 2,
            "validFrom": "2014-01-01",
            "_links": {"self": {"href": NEXT_VERSION_URL}},
        },
        {
            "name": "missing href is skipped",
            "id": 99,
        },
    ],
}
VERSION_BODY = {
    "name": "Delområde- og grunnkretsinndeling 2016",
    "id": 1,
    "validFrom": "2016-01-01",
    "validTo": "2017-01-01",
    "correspondenceTables": [
        {
            "name": "Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2014",
            "id": 160,
            "sourceId": 1,
            "targetId": 2,
            "changeTable": True,
            "published": ["nb", "nn", "en"],
            "_links": {"self": {"href": CORR_URL}},
        },
        {
            "name": "Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2013",
            "id": 161,
            "sourceId": 1,
            "targetId": 3,
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
        if url == ITEM_URL:
            return CLASS_BODY
        if url == NEXT_URL:
            return {"id": 2, "name": "Standard for kjønn", "versions": []}
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == VERSION_URL:
            return JsonResponse(status=200, url=url, body=VERSION_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ssbver fetch must GET, not POST {url}")


def test_printed_refs_copy_version_ids() -> None:
    source = SsbverSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["1", "2"]
    assert [ref.source_native_uri for ref in refs] == [VERSION_URL, NEXT_VERSION_URL]
    assert all("/classifications/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/classificationfamilies" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_self_href() -> None:
    assert (
        printed_item_url({"id": 1, "_links": {"self": {"href": VERSION_URL}}}, LIST_URL)
        == VERSION_URL
    )
    with pytest.raises(Exception, match="self href"):
        printed_item_url({"id": 7}, LIST_URL)


def test_ssbver_is_a_registered_source() -> None:
    assert "ssbver" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    assert "ssbv2" in SOURCE_IDS
    assert "ssbfam" in SOURCE_IDS
    assert "ssbsec" in SOURCE_IDS
    assert "ssclass" in SOURCE_IDS
    assert "nbprov" in SOURCE_IDS
    assert "nibiorest" in SOURCE_IDS
    assert "avinorgis" in SOURCE_IDS
    assert "brroller" in SOURCE_IDS
    assert "fdirwms" in SOURCE_IDS
    assert "brorgform" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("brorgform") + 1] == "ssbver"
    source = build_source("ssbver")
    assert isinstance(source, SsbverSource)
    assert source.source_id == "ssbver"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = SsbverSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ssbver"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == VERSION_URL
    assert row["title"] == "Delområde- og grunnkretsinndeling 2016"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssclass:")
    assert not str(row["id"]).startswith("ssb:")
    nxt = registry.get_dataset("ssbver:2")
    assert nxt is not None
    assert nxt["title"] == "Delområde- og grunnkretsinndeling 2014"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "1"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["ssbver_version"]["id"] == 1
    assert "_links" not in payload["ssbver_version"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_correspondence_names(tmp_path: Path) -> None:
    source = SsbverSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == VERSION_URL
    assert result.table_id == "1"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {
        "Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2014",
        "Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2013",
    }
    assert all(row["measure"] == "name" for row in rows)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(
        by_value[
            "Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2014"
        ]["dimensions_json"]
    )
    assert dims["id"] == "160"
    assert dims["sourceId"] == "1"
    assert dims["targetId"] == "2"
    assert "published" not in dims
    assert "_links" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == VERSION_URL for row in rows)
    registry.close()


def test_cells_copy_printed_correspondence_tables() -> None:
    cells = cells_from_ssbver(VERSION_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == (
        "Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2014"
    )
    assert dims["id"] == "160"
    assert "published" not in dims
    fallback = cells_from_ssbver({"id": 9, "name": "Delområde- og grunnkretsinndeling 2016"})
    assert fallback == [("name", "Delområde- og grunnkretsinndeling 2016", {"id": "9"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ssbver(["Delområde- og grunnkretsinndeling 2016"])
    with pytest.raises(ValueError, match="version members"):
        cells_from_ssbver({"correspondenceTables": []})


def test_is_ssbver_url_accepts_only_version_paths() -> None:
    assert is_ssbver_url(VERSION_URL)
    assert is_ssbver_url(NEXT_VERSION_URL)
    assert ssbver_table_id(VERSION_URL) == "1"
    assert not is_ssbver_url(LIST_URL)
    assert not is_ssbver_url(ITEM_URL)
    assert not is_ssbver_url(FAMILIES_URL)
    assert not is_ssbver_url(CODES_URL)
    assert not is_ssbver_url(CORR_URL)
    assert not is_ssbver_url(SSBV2_URL)
    assert not is_ssbver_url(SSB_V0_URL)
    assert not is_ssbver_url("https://data.norge.no/datasets/x")
    assert not is_ssbver_url(None)


def test_limit_and_offset_slice_printed_versions() -> None:
    source = SsbverSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["1"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["2"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
