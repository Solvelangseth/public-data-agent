from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brroller import (
    BrrollerSource,
    cells_from_brroller,
    brroller_table_id,
    is_brroller_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/openapi.json"
REPRESENTANTER_URL = "https://data.brreg.no/enhetsregisteret/api/roller/representanter"
GRUPPETYPER_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rollegruppetyper"
ROLLETYPER_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rolletyper"
LICENSE_URL = "https://data.norge.no/nlod/no/2.0"
DATASET_ID = "brroller:representanter"
BRREG_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer"
FRIVILLIG_URL = "https://data.brreg.no/frivillighetsregisteret/api/icnpo-kategorier"
REGNSKAP_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/v3/api-docs"

OPENAPI = {
    "openapi": "3.0.1",
    "info": {
        "title": "Enhetsregisterets dokumentasjon for åpne data",
        "description": "Åpne data inkludert roller",
        "license": {"name": "Norsk lisens for offentlige data (NLOD)", "url": LICENSE_URL},
    },
    "servers": [{"url": "https://data.brreg.no", "description": "Server"}],
    "paths": {
        "/enhetsregisteret/api/organisasjonsformer": {
            "get": {"summary": "Enhetsregisteret leftover, skip"},
        },
        "/enhetsregisteret/api/roller/totalbestand": {
            "get": {"summary": "Last ned totalbestand av roller som zippet json"},
        },
        "/enhetsregisteret/autorisert-api/roller/totalbestand": {
            "get": {"summary": "authorized dump, skip"},
        },
        "/enhetsregisteret/api/roller/representanter": {
            "get": {"summary": "Hent alle rollerepresentanter"},
        },
        "/enhetsregisteret/api/roller/rollegruppetyper": {
            "get": {"summary": "Hent alle rollegruppetyper"},
        },
        "/enhetsregisteret/api/roller/rolletyper": {
            "get": {"summary": "Hent alle rolletyper"},
        },
        "/enhetsregisteret/api/roller/enheter/{enhetorgnr}/juridiskeroller": {
            "get": {
                "summary": "templated",
                "parameters": [
                    {
                        "name": "enhetorgnr",
                        "in": "path",
                        "required": True,
                    }
                ],
            }
        },
        "/frivillighetsregisteret/api/icnpo-kategorier": {
            "get": {"summary": "Frivillighetsregisteret leftover, skip"},
        },
    },
}
REPRESENTANTER_BODY = {
    "_embedded": {
        "representanter": [
            {
                "kode": "A-AK",
                "beskrivelse": "Representant for A-aksjonærene",
                "_links": {"self": {"href": "skip"}},
            },
            {
                "kode": "AREP",
                "beskrivelse": "Representant for de ansatte",
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
        if url == REPRESENTANTER_URL:
            return JsonResponse(status=200, url=url, body=REPRESENTANTER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"brroller fetch must GET, not POST {url}")


def test_printed_refs_keep_leftover_roller_paths() -> None:
    source = BrrollerSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "representanter",
        "rollegruppetyper",
        "rolletyper",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        REPRESENTANTER_URL,
        GRUPPETYPER_URL,
        ROLLETYPER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "totalbestand" for ref in refs)
    assert all(ref.source_native_id != "organisasjonsformer" for ref in refs)
    assert all(ref.source_native_id != "icnpo-kategorier" for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_server_and_path() -> None:
    url = printed_endpoint_url(
        OPENAPI, "/enhetsregisteret/api/roller/representanter", OPENAPI_URL
    )
    assert url == REPRESENTANTER_URL
    assert "/frivillighetsregisteret/" not in url


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/enhetsregisteret/api/roller/representanter") == "representanter"
    assert printed_operation_id("/enhetsregisteret/api/roller/rolletyper") == "rolletyper"


def test_printed_license_url_copies_openapi_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Enhetsregisteret"}) is None


def test_brroller_is_a_registered_source() -> None:
    assert "brroller" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "frivillig" in SOURCE_IDS
    assert "regnskap" in SOURCE_IDS
    assert "ssbsec" in SOURCE_IDS
    assert "ssclass" in SOURCE_IDS
    assert "ssbfam" in SOURCE_IDS
    assert "banegis" in SOURCE_IDS
    assert "mattilsyn" in SOURCE_IDS
    assert "nibiorest" in SOURCE_IDS
    assert "nbprov" in SOURCE_IDS
    assert "avinorgis" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("avinorgis") + 1] == "brroller"
    source = build_source("brroller")
    assert isinstance(source, BrrollerSource)
    assert source.source_id == "brroller"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = BrrollerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "brroller"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == REPRESENTANTER_URL
    assert row["title"] == "Hent alle rollerepresentanter"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("brreg:")
    assert not str(row["id"]).startswith("frivillig:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["brroller_openapi_path"] == "/enhetsregisteret/api/roller/representanter"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_representant_names(tmp_path: Path) -> None:
    source = BrrollerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == REPRESENTANTER_URL
    assert result.table_id == "representanter"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {
        "Representant for A-aksjonærene",
        "Representant for de ansatte",
    }
    assert by_value["Representant for A-aksjonærene"]["measure"] == "beskrivelse"
    dims = json.loads(by_value["Representant for A-aksjonærene"]["dimensions_json"])
    assert dims["kode"] == "A-AK"
    assert "_links" not in dims
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == REPRESENTANTER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_beskrivelse() -> None:
    cells = cells_from_brroller(REPRESENTANTER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "beskrivelse"
    assert value == "Representant for A-aksjonærene"
    assert dims["kode"] == "A-AK"
    assert "_links" not in dims
    fallback = cells_from_brroller(
        {"_embedded": {"rolletyper": [{"kode": "DAGL"}]}}
    )
    assert fallback == [("kode", "DAGL", {})]
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_brroller({"_embedded": {"representanter": []}})


def test_is_brroller_url_accepts_only_roller_path() -> None:
    assert is_brroller_url(REPRESENTANTER_URL)
    assert is_brroller_url(ROLLETYPER_URL)
    assert brroller_table_id(REPRESENTANTER_URL) == "representanter"
    assert not is_brroller_url(BRREG_URL)
    assert not is_brroller_url(FRIVILLIG_URL)
    assert not is_brroller_url(REGNSKAP_URL)
    assert not is_brroller_url(OPENAPI_URL)
    assert not is_brroller_url("https://data.brreg.no/enhetsregisteret/autorisert-api/roller/totalbestand")
    assert not is_brroller_url("https://data.norge.no/datasets/x")
    assert not is_brroller_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = BrrollerSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "representanter"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["rollegruppetyper"]
