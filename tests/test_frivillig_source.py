from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.frivillig import (
    FrivilligSource,
    cells_from_frivillig,
    frivillig_table_id,
    is_frivillig_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/openapi.json"
KATEGORIER_URL = "https://data.brreg.no/frivillighetsregisteret/api/icnpo-kategorier"
INFORMASJON_URL = "https://data.brreg.no/frivillighetsregisteret/api/informasjonstyper"
ORGANISASJONER_URL = (
    "https://data.brreg.no/frivillighetsregisteret/api/frivillige-organisasjoner"
)
LICENSE_URL = "https://data.norge.no/nlod/no/2.0"
DATASET_ID = "frivillig:icnpo-kategorier"
BRREG_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer"
REGNSKAP_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/v3/api-docs"
ELCERT_URL = "https://api.nve.no/web/ElCert/GetApplications"

OPENAPI = {
    "openapi": "3.0.1",
    "info": {
        "title": "Enhetsregisterets dokumentasjon for åpne data",
        "description": "Åpne data inkludert Frivillighetsregisteret",
        "license": {"name": "Norsk lisens for offentlige data (NLOD)", "url": LICENSE_URL},
    },
    "servers": [{"url": "https://data.brreg.no", "description": "Server"}],
    "paths": {
        "/enhetsregisteret/api/organisasjonsformer": {
            "get": {"summary": "Enhetsregisteret leftover, skip"},
        },
        "/frivillighetsregisteret/api/frivillige-organisasjoner": {
            "get": {"summary": "Søk i frivillige organisasjoner"},
        },
        "/frivillighetsregisteret/api/frivillige-organisasjoner/{organisasjonsnummer}": {
            "get": {
                "summary": "templated",
                "parameters": [
                    {
                        "name": "organisasjonsnummer",
                        "in": "path",
                        "required": True,
                    }
                ],
            }
        },
        "/frivillighetsregisteret/api/frivillige-organisasjoner/totalbestand/csv": {
            "get": {"summary": "CSV totalbestand"},
        },
        "/frivillighetsregisteret/api/icnpo-kategorier": {
            "get": {"summary": "Hent ICNPO kategorier"},
        },
        "/frivillighetsregisteret/api/informasjonstyper": {
            "get": {"summary": "Hent informasjonstyper i Frivillighetsregisteret"},
        },
    },
}
KATEGORIER_BODY = {
    "_embedded": {
        "icnpoKategorier": [
            {
                "icnpoNummer": "1",
                "navn": "Kultur- og rekreasjon",
                "spraakkode": "NOB",
                "_links": {"self": {"href": "skip"}},
            },
            {
                "icnpoNummer": "1200",
                "navn": "Idrett",
                "spraakkode": "NOB",
                "underkategorier": [{"navn": "skip nested"}],
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
        if url == KATEGORIER_URL:
            return JsonResponse(status=200, url=url, body=KATEGORIER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"frivillig fetch must GET, not POST {url}")


def test_printed_refs_keep_frivillig_collection_paths() -> None:
    source = FrivilligSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "frivillige-organisasjoner",
        "icnpo-kategorier",
        "informasjonstyper",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        ORGANISASJONER_URL,
        KATEGORIER_URL,
        INFORMASJON_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "csv" for ref in refs)
    assert all(ref.source_native_id != "organisasjonsformer" for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_server_and_path() -> None:
    url = printed_endpoint_url(OPENAPI, "/frivillighetsregisteret/api/icnpo-kategorier", OPENAPI_URL)
    assert url == KATEGORIER_URL
    assert "/enhetsregisteret/" not in url


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/frivillighetsregisteret/api/icnpo-kategorier") == "icnpo-kategorier"
    assert printed_operation_id("/frivillighetsregisteret/api/informasjonstyper") == "informasjonstyper"


def test_printed_license_url_copies_openapi_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Frivillighetsregisteret"}) is None


def test_frivillig_is_a_registered_source() -> None:
    assert "frivillig" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "regnskap" in SOURCE_IDS
    assert "vannkraft" in SOURCE_IDS
    assert "vindkraft" in SOURCE_IDS
    assert "aviationforecast" in SOURCE_IDS
    source = build_source("frivillig")
    assert isinstance(source, FrivilligSource)
    assert source.source_id == "frivillig"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = FrivilligSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "frivillig"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == KATEGORIER_URL
    assert row["title"] == "Hent ICNPO kategorier"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("brreg:")
    assert not str(row["id"]).startswith("regnskap:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["frivillig_openapi_path"] == "/frivillighetsregisteret/api/icnpo-kategorier"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_category_names(tmp_path: Path) -> None:
    source = FrivilligSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == KATEGORIER_URL
    assert result.table_id == "icnpo-kategorier"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Kultur- og rekreasjon", "Idrett"}
    assert by_value["Kultur- og rekreasjon"]["measure"] == "navn"
    dims = json.loads(by_value["Kultur- og rekreasjon"]["dimensions_json"])
    assert dims["icnpoNummer"] == "1"
    assert dims["spraakkode"] == "NOB"
    assert "_links" not in dims
    assert "underkategorier" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == KATEGORIER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_navn() -> None:
    cells = cells_from_frivillig(KATEGORIER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "navn"
    assert value == "Kultur- og rekreasjon"
    assert dims["icnpoNummer"] == "1"
    assert "_links" not in dims
    fallback = cells_from_frivillig(
        {"_embedded": {"frivilligeOrganisasjoner": [{"organisasjonsnummer": "810098252"}]}}
    )
    assert fallback == [("organisasjonsnummer", "810098252", {})]
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_frivillig({"_embedded": {"icnpoKategorier": []}})


def test_is_frivillig_url_accepts_only_frivillighetsregisteret_path() -> None:
    assert is_frivillig_url(KATEGORIER_URL)
    assert is_frivillig_url(ORGANISASJONER_URL)
    assert frivillig_table_id(KATEGORIER_URL) == "icnpo-kategorier"
    assert not is_frivillig_url(BRREG_URL)
    assert not is_frivillig_url(REGNSKAP_URL)
    assert not is_frivillig_url(ELCERT_URL)
    assert not is_frivillig_url(OPENAPI_URL)
    assert not is_frivillig_url("https://data.norge.no/datasets/x")
    assert not is_frivillig_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = FrivilligSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "frivillige-organisasjoner"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["icnpo-kategorier"]
