from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brorgformen import (
    BrorgformenSource,
    brorgformen_table_id,
    cells_from_brorgformen,
    is_brorgformen_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/openapi.json"
ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/enheter"
UNDERENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/underenheter"
LICENSE_URL = "https://data.norge.no/nlod/no/2.0"
DATASET_ID = "brorgformen:enheter"
BRREG_URL = "https://data.brreg.no/enhetsregisteret/api"
ORGFORM_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer"
ORGFORM_ITEM_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/ADOS"
OPPDATER_URL = "https://data.brreg.no/enhetsregisteret/api/oppdateringer/enheter"
ENHET_ITEM_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/916627939"
UNDER_ITEM_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter/933489272"

OPENAPI = {
    "openapi": "3.0.1",
    "info": {
        "title": "Enhetsregisterets dokumentasjon for åpne data",
        "description": "Åpne data inkludert organisasjonsformer",
        "license": {"name": "Norsk lisens for offentlige data (NLOD)", "url": LICENSE_URL},
    },
    "servers": [{"url": "https://data.brreg.no", "description": "Server"}],
    "paths": {
        "/enhetsregisteret/api/organisasjonsformer": {
            "get": {"summary": "Hent organisasjonsformer"},
        },
        "/enhetsregisteret/api/organisasjonsformer/enheter": {
            "get": {"summary": "Hent organisasjonsformer for enheter"},
        },
        "/enhetsregisteret/api/organisasjonsformer/underenheter": {
            "get": {"summary": "Hent organisasjonsformer for underenheter"},
        },
        "/enhetsregisteret/api/organisasjonsformer/{organisasjonskode}": {
            "get": {
                "summary": "templated",
                "parameters": [
                    {
                        "name": "organisasjonskode",
                        "in": "path",
                        "required": True,
                    }
                ],
            }
        },
        "/enhetsregisteret/api/oppdateringer/enheter": {
            "get": {"summary": "oppdateringer leftover, skip"},
        },
        "/enhetsregisteret/api/enheter": {
            "get": {"summary": "enheter leftover, skip"},
        },
    },
}
ENHETER_BODY = {
    "_embedded": {
        "organisasjonsformer": [
            {
                "kode": "ADOS",
                "beskrivelse": "Administrativ enhet - offentlig sektor",
                "_links": {
                    "self": {
                        "href": "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/ADOS"
                    }
                },
            },
            {
                "kode": "ANNA",
                "beskrivelse": "Annen juridisk person",
                "nested": [{"kode": "skip nested"}],
            },
        ]
    }
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == OPENAPI_URL:
            return OPENAPI
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == ENHETER_URL:
            return JsonResponse(status=200, url=url, body=ENHETER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"brorgformen fetch must GET, not POST {url}")


def test_printed_refs_keep_leftover_organisasjonsformer_paths() -> None:
    source = BrorgformenSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["enheter", "underenheter"]
    assert [ref.source_native_uri for ref in refs] == [ENHETER_URL, UNDERENHETER_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "organisasjonsformer" for ref in refs)
    assert all(ref.source_native_id != "ADOS" for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_server_and_path() -> None:
    url = printed_endpoint_url(
        OPENAPI, "/enhetsregisteret/api/organisasjonsformer/enheter", OPENAPI_URL
    )
    assert url == ENHETER_URL
    assert "/oppdateringer/" not in url
    assert "/enheter/" not in url


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/enhetsregisteret/api/organisasjonsformer/enheter") == "enheter"
    assert (
        printed_operation_id("/enhetsregisteret/api/organisasjonsformer/underenheter")
        == "underenheter"
    )


def test_printed_license_url_copies_openapi_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Enhetsregisteret"}) is None


def test_brorgformen_is_a_registered_source() -> None:
    assert "brorgformen" in SOURCE_IDS
    assert "brorgform" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "brenheter" in SOURCE_IDS
    assert "brunder" in SOURCE_IDS
    assert "broppdater" in SOURCE_IDS
    assert "kikommuner" in SOURCE_IDS
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
    assert SOURCE_IDS[-1] == "brorgformen"
    source = build_source("brorgformen")
    assert isinstance(source, BrorgformenSource)
    assert source.source_id == "brorgformen"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = BrorgformenSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "brorgformen"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ENHETER_URL
    assert row["title"] == "Hent organisasjonsformer for enheter"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("brorgform:")
    assert not str(row["id"]).startswith("brenheter:")
    assert not str(row["id"]).startswith("brunder:")
    assert not str(row["id"]).startswith("broppdater:")
    nxt = registry.get_dataset("brorgformen:underenheter")
    assert nxt is not None
    assert nxt["title"] == "Hent organisasjonsformer for underenheter"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["brorgformen_openapi_path"] == "/enhetsregisteret/api/organisasjonsformer/enheter"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_beskrivelse(tmp_path: Path) -> None:
    source = BrorgformenSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ENHETER_URL
    assert result.table_id == "enheter"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_kode = {json.loads(row["dimensions_json"])["kode"]: row for row in rows}
    assert set(by_kode) == {"ADOS", "ANNA"}
    assert json.loads(by_kode["ADOS"]["value_json"]) == "Administrativ enhet - offentlig sektor"
    assert by_kode["ADOS"]["measure"] == "beskrivelse"
    dims = json.loads(by_kode["ADOS"]["dimensions_json"])
    assert dims["kode"] == "ADOS"
    assert "_links" not in dims
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == ENHETER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_beskrivelse() -> None:
    cells = cells_from_brorgformen(ENHETER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "beskrivelse"
    assert value == "Administrativ enhet - offentlig sektor"
    assert dims["kode"] == "ADOS"
    assert "_links" not in dims
    fallback = cells_from_brorgformen(
        {"_embedded": {"organisasjonsformer": [{"kode": "AS"}]}}
    )
    assert fallback == [("kode", "AS", {})]
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_brorgformen({"_embedded": {"organisasjonsformer": []}})


def test_is_brorgformen_url_accepts_only_leftover_collection_paths() -> None:
    assert is_brorgformen_url(ENHETER_URL)
    assert is_brorgformen_url(UNDERENHETER_URL)
    assert brorgformen_table_id(ENHETER_URL) == "enheter"
    assert not is_brorgformen_url(ORGFORM_URL)
    assert not is_brorgformen_url(ORGFORM_ITEM_URL)
    assert not is_brorgformen_url(OPPDATER_URL)
    assert not is_brorgformen_url(ENHET_ITEM_URL)
    assert not is_brorgformen_url(UNDER_ITEM_URL)
    assert not is_brorgformen_url(BRREG_URL)
    assert not is_brorgformen_url(OPENAPI_URL)
    assert not is_brorgformen_url("https://data.norge.no/datasets/x")
    assert not is_brorgformen_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = BrorgformenSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["enheter"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["underenheter"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
