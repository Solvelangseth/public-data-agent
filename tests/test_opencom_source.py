from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.opencom import (
    OpencomSource,
    cells_from_opencom,
    is_opencom_url,
    opencom_table_id,
    printed_license_url,
    printed_package_show_url,
    printed_publisher,
)

LIST_URL = "https://opencom.no/api/3/action/package_list"
BEHOV_URL = (
    "https://opencom.no/api/3/action/package_show?id=04682-behovsprofil-grunnlagsdata"
)
REGN_URL = "https://opencom.no/api/3/action/package_show?id=regnsensordata"
NLOD_URL = "https://data.norge.no/nlod/no/2.0/"
DATASET_ID = "opencom:04682-behovsprofil-grunnlagsdata"
ORG_ID = "02a6d18e-389c-4b84-8377-7da8127ba92a"
STAVANGER_ORG_ID = "a5828aa1-820f-4937-b704-579a53258a09"

LIST_BODY = {
    "success": True,
    "result": ["04682-behovsprofil-grunnlagsdata", "regnsensordata", ""],
}

BEHOV_PACKAGE = {
    "name": "04682-behovsprofil-grunnlagsdata",
    "title": "04682 Behovsprofil grunnlagsdata 2010-16",
    "notes": "Datasettet viser bl.a. befolkning fordelt på aldersgrupper.",
    "license_url": None,
    "license_id": "NLOD-1.0",
    "organization": {
        "id": ORG_ID,
        "name": "stavangerregionen",
        "title": "Stavangerregionen",
    },
    "resources": [
        {
            "id": "ba9aade1-0470-4af5-a75d-17d10e36a24d",
            "name": "04682_2010.csv",
            "format": "CSV",
            "url": "https://opencom.no/dataset/5f7ec8a6-f727-44c8-aa8c-3cc4171c9d5c/resource/ba9aade1-0470-4af5-a75d-17d10e36a24d/download/ssbdata.csv",
            "nested": {"skip": True},
        },
        {
            "id": "ed8f7ea3-894f-402e-96bb-df93dea1ad56",
            "name": "04682_2011.csv",
            "format": "CSV",
            "url": "https://opencom.no/dataset/5f7ec8a6-f727-44c8-aa8c-3cc4171c9d5c/resource/ed8f7ea3-894f-402e-96bb-df93dea1ad56/download/ssbdata.csv",
        },
    ],
}

REGN_PACKAGE = {
    "name": "regnsensordata",
    "title": "Regnsensordata",
    "notes": "Data er hente fra divserse sensorere som står rundt om i Stavanger.",
    "license_url": NLOD_URL,
    "license_id": "NLOD-2.0",
    "organization": {
        "id": STAVANGER_ORG_ID,
        "title": "Stavanger kommune",
    },
    "resources": [
        {
            "id": "1a6038fd-7bd0-4a8e-a87a-a3de8b19d248",
            "name": "",
            "url": "https://opencom.no/dataset/5867e185-c8b4-4976-b720-219e2bf8d21f/resource/1a6038fd-7bd0-4a8e-a87a-a3de8b19d248/download/dailyrainsensordataoutfileformat1.json",
        }
    ],
}

BEHOV_BODY = {"success": True, "result": BEHOV_PACKAGE}
REGN_BODY = {"success": True, "result": REGN_PACKAGE}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return LIST_BODY
        if url == BEHOV_URL:
            return BEHOV_BODY
        if url == REGN_URL:
            return REGN_BODY
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == BEHOV_URL:
            return JsonResponse(status=200, url=url, body=BEHOV_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"opencom fetch must GET, not POST {url}")


def test_printed_refs_skip_blank_names() -> None:
    source = OpencomSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "04682-behovsprofil-grunnlagsdata",
        "regnsensordata",
    ]
    assert [ref.source_native_uri for ref in refs] == [BEHOV_URL, REGN_URL]
    assert LIST_URL not in [ref.source_native_uri for ref in refs]


def test_package_show_url_joins_printed_origin_and_name() -> None:
    url = printed_package_show_url("04682-behovsprofil-grunnlagsdata", LIST_URL)
    assert url == BEHOV_URL
    assert "package_list" not in url


def test_printed_license_and_publisher_copy_only_printed_fields() -> None:
    assert printed_license_url(REGN_PACKAGE) == NLOD_URL
    assert printed_license_url(BEHOV_PACKAGE) is None
    assert printed_license_url({"license_id": "NLOD-1.0"}) is None
    assert printed_license_url({"license_url": "notspecified"}) is None
    publisher = printed_publisher(BEHOV_PACKAGE)
    assert publisher == {"title": {"no": "Stavangerregionen"}, "id": ORG_ID}
    assert printed_publisher({"organization": None}) is None
    assert printed_publisher({"organization": {"name": "stavangerregionen"}}) is None


def test_opencom_is_a_registered_source() -> None:
    assert "opencom" in SOURCE_IDS
    source = build_source("opencom")
    assert isinstance(source, OpencomSource)
    assert source.source_id == "opencom"


def test_harvest_writes_printed_id_publisher_and_null_license(tmp_path: Path) -> None:
    source = OpencomSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "opencom"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == BEHOV_URL
    assert row["title"] == "04682 Behovsprofil grunnlagsdata 2010-16"
    assert row["publisher_name"] == "Stavangerregionen"
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("vegvesen:")
    assert not str(row["id"]).startswith("trondheim:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["opencom_package_name"] == "04682-behovsprofil-grunnlagsdata"
    assert payload["license"] is None
    assert payload["publisher"]["title"]["no"] == "Stavangerregionen"
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_behovsprofil_resources(tmp_path: Path) -> None:
    source = OpencomSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == BEHOV_URL
    assert result.table_id == "04682-behovsprofil-grunnlagsdata"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["04682_2010.csv", "04682_2011.csv"]
    assert all(row["measure"] == "name" for row in rows)
    first = rows[0]
    dims = json.loads(first["dimensions_json"])
    assert dims["format"] == "CSV"
    assert dims["url"].startswith("https://opencom.no/dataset/")
    assert "nested" not in dims
    assert all(row["publisher_name"] == "Stavangerregionen" for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == BEHOV_URL for row in rows)
    registry.close()


def test_cells_copy_printed_resource_names() -> None:
    cells = cells_from_opencom(BEHOV_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "04682_2010.csv"
    assert dims["format"] == "CSV"
    assert "nested" not in dims
    fallback = cells_from_opencom(REGN_BODY)
    assert fallback == [
        (
            "url",
            "https://opencom.no/dataset/5867e185-c8b4-4976-b720-219e2bf8d21f/resource/1a6038fd-7bd0-4a8e-a87a-a3de8b19d248/download/dailyrainsensordataoutfileformat1.json",
            {"id": "1a6038fd-7bd0-4a8e-a87a-a3de8b19d248", "name": ""},
        )
    ]
    unwrapped = cells_from_opencom(
        {"resources": [{"id": "x", "name": "Nedlastbare filer", "format": "CSV"}]}
    )
    assert unwrapped == [("name", "Nedlastbare filer", {"id": "x", "format": "CSV"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_opencom([{"name": "Behovsprofil"}])
    with pytest.raises(ValueError, match="printed no resources"):
        cells_from_opencom({"success": True, "result": {"name": "empty", "resources": []}})


def test_is_opencom_url_accepts_only_package_show() -> None:
    assert is_opencom_url(BEHOV_URL)
    assert is_opencom_url(REGN_URL)
    assert opencom_table_id(BEHOV_URL) == "04682-behovsprofil-grunnlagsdata"
    assert not is_opencom_url(LIST_URL)
    assert not is_opencom_url("https://opencom.no/dataset/regnsensordata")
    assert not is_opencom_url(
        "https://dataut.vegvesen.no/api/3/action/package_show?id=artsmangfold"
    )
    assert not is_opencom_url("https://data.trondheim.kommune.no/dataset/e736k")
    assert not is_opencom_url("https://data.norge.no/datasets/x")
    assert not is_opencom_url(None)


def test_limit_and_offset_slice_printed_names() -> None:
    source = OpencomSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "04682-behovsprofil-grunnlagsdata"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["regnsensordata"]
