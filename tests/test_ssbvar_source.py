from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ssbvar import (
    LIST_URL,
    SsbvarSource,
    cells_from_ssbvar,
    is_ssbvar_url,
    printed_item_url,
    ssbvar_table_id,
)

ITEM_URL = "https://data.ssb.no/api/klass/v1/classifications/2"
NEXT_URL = "https://data.ssb.no/api/klass/v1/classifications/7"
VERSION_URL = "https://data.ssb.no/api/klass/v1/versions/14"
NEXT_VERSION_URL = "https://data.ssb.no/api/klass/v1/versions/33"
VARIANT_URL = "https://data.ssb.no/api/klass/v1/variants/802"
NEXT_VARIANT_URL = "https://data.ssb.no/api/klass/v1/variants/1630"
FAMILIES_URL = "https://data.ssb.no/api/klass/v1/classificationfamilies"
CODES_URL = "https://data.ssb.no/api/klass/v1/classifications/2/codes"
CORR_URL = "https://data.ssb.no/api/klass/v1/correspondencetables/160"
SSBV2_URL = "https://data.ssb.no/api/pxwebapi/v2/tables"
SSB_V0_URL = "https://data.ssb.no/api/v0/no/table"
DATASET_ID = "ssbvar:802"

CATALOG = {
    "_embedded": {
        "classifications": [
            {
                "id": 2,
                "name": "Standard for kjønn",
                "classificationType": "Klassifikasjon",
                "_links": {"self": {"href": ITEM_URL}},
            },
            {
                "id": 7,
                "name": "Standard for yrkesklassifisering",
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
    "name": "Standard for kjønn",
    "id": 2,
    "versions": [
        {
            "name": "Kjønn 1960",
            "id": 14,
            "validFrom": "1960-01-01",
            "_links": {"self": {"href": VERSION_URL}},
        },
        {
            "name": "missing href is skipped",
            "id": 99,
        },
    ],
}
VERSION_BODY = {
    "name": "Kjønn 1960",
    "id": 14,
    "classificationVariants": [
        {
            "name": 'Kjønn, inkl. "begge kjønn" 1960  - variant av Kjønn 1960',
            "id": 802,
            "owningSection": "360",
            "published": ["nb", "en"],
            "_links": {"self": {"href": VARIANT_URL}},
        },
        {
            "name": "missing href is skipped",
            "id": 999,
        },
    ],
}
NEXT_CLASS_BODY = {
    "name": "Standard for yrkesklassifisering",
    "id": 7,
    "versions": [
        {
            "name": "Yrkesklassifisering 2011",
            "id": 33,
            "_links": {"self": {"href": NEXT_VERSION_URL}},
        }
    ],
}
NEXT_VERSION_BODY = {
    "name": "Yrkesklassifisering 2011",
    "id": 33,
    "classificationVariants": [
        {
            "name": "Yrkesklassifisering 2011 - variant",
            "id": 1630,
            "_links": {"self": {"href": NEXT_VARIANT_URL}},
        }
    ],
}
VARIANT_BODY = {
    "name": 'Kjønn, inkl. "begge kjønn" 1960  - variant av Kjønn 1960',
    "id": 802,
    "classificationItems": [
        {
            "code": "0",
            "parentCode": "",
            "level": "1",
            "name": "Begge kjønn",
            "shortName": None,
            "notes": None,
        },
        {
            "code": "1",
            "parentCode": "",
            "level": "1",
            "name": "Menn",
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
            return NEXT_CLASS_BODY
        if url == VERSION_URL:
            return VERSION_BODY
        if url == NEXT_VERSION_URL:
            return NEXT_VERSION_BODY
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == VARIANT_URL:
            return JsonResponse(status=200, url=url, body=VARIANT_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ssbvar fetch must GET, not POST {url}")


def test_printed_refs_copy_variant_ids() -> None:
    source = SsbvarSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["802", "1630"]
    assert [ref.source_native_uri for ref in refs] == [VARIANT_URL, NEXT_VARIANT_URL]
    assert all("/versions/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/classifications/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/correspondencetables/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/classificationfamilies" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_self_href() -> None:
    assert (
        printed_item_url({"id": 802, "_links": {"self": {"href": VARIANT_URL}}}, LIST_URL)
        == VARIANT_URL
    )
    with pytest.raises(Exception, match="self href"):
        printed_item_url({"id": 802}, LIST_URL)


def test_ssbvar_is_a_registered_source() -> None:
    assert "ssbvar" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    assert "ssbv2" in SOURCE_IDS
    assert "ssbfam" in SOURCE_IDS
    assert "ssbsec" in SOURCE_IDS
    assert "ssclass" in SOURCE_IDS
    assert "ssbver" in SOURCE_IDS
    assert "ssbcorr" in SOURCE_IDS
    assert "broppdater" in SOURCE_IDS
    assert "kifylker" in SOURCE_IDS
    assert "brrepresent" in SOURCE_IDS
    assert "brenheter" in SOURCE_IDS
    assert "bwgis" in SOURCE_IDS
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
    assert SOURCE_IDS[SOURCE_IDS.index("nibiogard") + 1] == "stskrift"
    assert SOURCE_IDS[SOURCE_IDS.index("stskrift") + 1] == "sthoring"
    assert SOURCE_IDS[-1] == "sthoring"
    source = build_source("ssbvar")
    assert isinstance(source, SsbvarSource)
    assert source.source_id == "ssbvar"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = SsbvarSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ssbvar"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == VARIANT_URL
    assert row["title"] == 'Kjønn, inkl. "begge kjønn" 1960  - variant av Kjønn 1960'
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssbver:")
    assert not str(row["id"]).startswith("ssbcorr:")
    assert not str(row["id"]).startswith("ssclass:")
    assert not str(row["id"]).startswith("ssb:")
    nxt = registry.get_dataset("ssbvar:1630")
    assert nxt is not None
    assert nxt["title"] == "Yrkesklassifisering 2011 - variant"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "802"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["ssbvar_variant"]["id"] == 802
    assert "_links" not in payload["ssbvar_variant"]
    assert "classificationItems" not in payload["ssbvar_variant"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_item_names(tmp_path: Path) -> None:
    source = SsbvarSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == VARIANT_URL
    assert result.table_id == "802"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {"Begge kjønn", "Menn"}
    assert all(row["measure"] == "name" for row in rows)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_value["Begge kjønn"]["dimensions_json"])
    assert dims["code"] == "0"
    assert dims["level"] == "1"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == VARIANT_URL for row in rows)
    registry.close()


def test_cells_copy_printed_classification_items() -> None:
    cells = cells_from_ssbvar(VARIANT_BODY)
    assert cells == [
        (
            "name",
            "Begge kjønn",
            {
                "code": "0",
                "parentCode": "",
                "level": "1",
                "shortName": "",
                "notes": "",
            },
        ),
        (
            "name",
            "Menn",
            {
                "code": "1",
                "parentCode": "",
                "level": "1",
            },
        ),
    ]
    fallback = cells_from_ssbvar(
        {
            "id": 802,
            "name": 'Kjønn, inkl. "begge kjønn" 1960  - variant av Kjønn 1960',
        }
    )
    assert fallback == [
        (
            "name",
            'Kjønn, inkl. "begge kjønn" 1960  - variant av Kjønn 1960',
            {"id": "802"},
        )
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ssbvar(["Begge kjønn"])
    with pytest.raises(ValueError, match="classification-variant members"):
        cells_from_ssbvar({"classificationItems": []})


def test_is_ssbvar_url_accepts_only_variant_paths() -> None:
    assert is_ssbvar_url(VARIANT_URL)
    assert is_ssbvar_url(NEXT_VARIANT_URL)
    assert ssbvar_table_id(VARIANT_URL) == "802"
    assert not is_ssbvar_url(LIST_URL)
    assert not is_ssbvar_url(ITEM_URL)
    assert not is_ssbvar_url(VERSION_URL)
    assert not is_ssbvar_url(FAMILIES_URL)
    assert not is_ssbvar_url(CODES_URL)
    assert not is_ssbvar_url(CORR_URL)
    assert not is_ssbvar_url(SSBV2_URL)
    assert not is_ssbvar_url(SSB_V0_URL)
    assert not is_ssbvar_url("https://data.ssb.no/api/klass/v1/variants")
    assert not is_ssbvar_url("https://data.norge.no/datasets/x")
    assert not is_ssbvar_url(None)


def test_limit_and_offset_slice_printed_variants() -> None:
    source = SsbvarSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["802"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["1630"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
