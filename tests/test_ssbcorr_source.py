from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ssbcorr import (
    LIST_URL,
    SsbcorrSource,
    cells_from_ssbcorr,
    is_ssbcorr_url,
    printed_item_url,
    ssbcorr_table_id,
)

ITEM_URL = "https://data.ssb.no/api/klass/v1/classifications/1"
NEXT_URL = "https://data.ssb.no/api/klass/v1/classifications/2"
VERSION_URL = "https://data.ssb.no/api/klass/v1/versions/1"
NEXT_VERSION_URL = "https://data.ssb.no/api/klass/v1/versions/2"
CORR_URL = "https://data.ssb.no/api/klass/v1/correspondencetables/160"
NEXT_CORR_URL = "https://data.ssb.no/api/klass/v1/correspondencetables/161"
FAMILIES_URL = "https://data.ssb.no/api/klass/v1/classificationfamilies"
CODES_URL = "https://data.ssb.no/api/klass/v1/classifications/1/codes"
SSBV2_URL = "https://data.ssb.no/api/pxwebapi/v2/tables"
SSB_V0_URL = "https://data.ssb.no/api/v0/no/table"
DATASET_ID = "ssbcorr:160"

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
            "_links": {"self": {"href": NEXT_CORR_URL}},
        },
        {
            "name": "missing href is skipped",
            "id": 999,
        },
    ],
}
NEXT_VERSION_BODY = {
    "name": "Delområde- og grunnkretsinndeling 2014",
    "id": 2,
    "correspondenceTables": [],
}
TABLE_BODY = {
    "name": "Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2014",
    "id": 160,
    "sourceId": 1,
    "targetId": 2,
    "changeTable": True,
    "correspondenceMaps": [
        {
            "sourceCode": "02190926",
            "sourceName": "Stabekk 26",
            "targetCode": "02190914",
            "targetName": "Stabekk 14",
        },
        {
            "sourceCode": "02190927",
            "sourceName": "Stabekk 27",
            "targetCode": "02190915",
            "targetName": "Stabekk 15",
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
        if url == VERSION_URL:
            return VERSION_BODY
        if url == NEXT_VERSION_URL:
            return NEXT_VERSION_BODY
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == CORR_URL:
            return JsonResponse(status=200, url=url, body=TABLE_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ssbcorr fetch must GET, not POST {url}")


def test_printed_refs_copy_correspondence_table_ids() -> None:
    source = SsbcorrSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["160", "161"]
    assert [ref.source_native_uri for ref in refs] == [CORR_URL, NEXT_CORR_URL]
    assert all("/versions/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/classifications/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/classificationfamilies" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_self_href() -> None:
    assert (
        printed_item_url({"id": 160, "_links": {"self": {"href": CORR_URL}}}, LIST_URL)
        == CORR_URL
    )
    with pytest.raises(Exception, match="self href"):
        printed_item_url({"id": 160}, LIST_URL)


def test_ssbcorr_is_a_registered_source() -> None:
    assert "ssbcorr" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    assert "ssbv2" in SOURCE_IDS
    assert "ssbfam" in SOURCE_IDS
    assert "ssbsec" in SOURCE_IDS
    assert "ssclass" in SOURCE_IDS
    assert "ssbver" in SOURCE_IDS
    assert "brkommuner" in SOURCE_IDS
    assert "brrolletype" in SOURCE_IDS
    assert "fdkorg" in SOURCE_IDS
    assert "nguminer" in SOURCE_IDS
    assert "brrollegruppe" in SOURCE_IDS
    assert "mdirgis" in SOURCE_IDS
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
    assert SOURCE_IDS[SOURCE_IDS.index("dsbgis") + 1] == "ssbens"
    assert SOURCE_IDS[-1] == "ssbens"
    source = build_source("ssbcorr")
    assert isinstance(source, SsbcorrSource)
    assert source.source_id == "ssbcorr"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = SsbcorrSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ssbcorr"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == CORR_URL
    assert row["title"] == (
        "Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2014"
    )
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssbver:")
    assert not str(row["id"]).startswith("ssclass:")
    assert not str(row["id"]).startswith("ssb:")
    nxt = registry.get_dataset("ssbcorr:161")
    assert nxt is not None
    assert nxt["title"] == (
        "Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2013"
    )
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "160"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["ssbcorr_correspondencetable"]["id"] == 160
    assert "_links" not in payload["ssbcorr_correspondencetable"]
    assert "correspondenceMaps" not in payload["ssbcorr_correspondencetable"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_map_names(tmp_path: Path) -> None:
    source = SsbcorrSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == CORR_URL
    assert result.table_id == "160"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Stabekk 26", "Stabekk 27"]
    assert all(row["measure"] == "sourceName" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["sourceCode"] == "02190926"
    assert dims["targetCode"] == "02190914"
    assert dims["targetName"] == "Stabekk 14"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == CORR_URL for row in rows)
    registry.close()


def test_cells_copy_printed_correspondence_maps() -> None:
    cells = cells_from_ssbcorr(TABLE_BODY)
    assert cells == [
        (
            "sourceName",
            "Stabekk 26",
            {
                "sourceCode": "02190926",
                "targetCode": "02190914",
                "targetName": "Stabekk 14",
            },
        ),
        (
            "sourceName",
            "Stabekk 27",
            {
                "sourceCode": "02190927",
                "targetCode": "02190915",
                "targetName": "Stabekk 15",
            },
        ),
    ]
    fallback = cells_from_ssbcorr(
        {
            "id": 160,
            "name": "Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2014",
        }
    )
    assert fallback == [
        (
            "name",
            "Delområde- og grunnkretsinndeling 2016 - Delområde- og grunnkretsinndeling 2014",
            {"id": "160"},
        )
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ssbcorr(["Stabekk 26"])
    with pytest.raises(ValueError, match="correspondence-table members"):
        cells_from_ssbcorr({"correspondenceMaps": []})


def test_is_ssbcorr_url_accepts_only_correspondence_table_paths() -> None:
    assert is_ssbcorr_url(CORR_URL)
    assert is_ssbcorr_url(NEXT_CORR_URL)
    assert ssbcorr_table_id(CORR_URL) == "160"
    assert not is_ssbcorr_url(LIST_URL)
    assert not is_ssbcorr_url(ITEM_URL)
    assert not is_ssbcorr_url(VERSION_URL)
    assert not is_ssbcorr_url(FAMILIES_URL)
    assert not is_ssbcorr_url(CODES_URL)
    assert not is_ssbcorr_url(SSBV2_URL)
    assert not is_ssbcorr_url(SSB_V0_URL)
    assert not is_ssbcorr_url("https://data.ssb.no/api/klass/v1/correspondencetables")
    assert not is_ssbcorr_url("https://data.norge.no/datasets/x")
    assert not is_ssbcorr_url(None)


def test_limit_and_offset_slice_printed_tables() -> None:
    source = SsbcorrSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["160"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["161"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
