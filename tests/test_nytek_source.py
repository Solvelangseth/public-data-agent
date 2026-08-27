from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nytek import (
    NytekSource,
    cells_from_nytek,
    is_nytek_url,
    nytek_table_id,
    printed_endpoint_url,
    printed_license_url,
)

OPENAPI_URL = "https://api.fiskeridir.no/nytek-public/v3/api-docs"
CERTIFICATES_URL = "https://api.fiskeridir.no/nytek-public/api/v3/certificates"
LICENSE_URL = "https://www.fiskeridir.no/Tall-og-analyse/Lisens-for-bruk-av-Fiskeridirektoratets-data"
DATASET_ID = "nytek:certificates"

OPENAPI = {
    "info": {
        "title": "nytek-public",
        "description": "API for deling av NYTEK23 data",
        "license": {"name": "Lisens for bruk av Fiskeridirektoratets data", "url": LICENSE_URL},
        "version": "1.0.0",
    },
    "servers": [{"url": "https://api.fiskeridir.no/nytek-public"}],
    "paths": {
        "/api/v3/certificates": {"get": {"summary": "Søk etter anleggssertifikat med parametre"}},
        "/api/v3/certificates/{site-nr}": {"get": {"summary": "Hent siste utstedte anleggssertifikat"}},
        "/api/v3/files/{uuid}": {"get": {"summary": "Last ned fil"}},
    },
}
CERTIFICATES_BODY = {
    "content": [
        {
            "status": {"status": "ISSUED", "validFrom": "2026-08-27T13:26:07.036090Z"},
            "installationCertificate": {
                "uuid": "676b7e59-0d9f-4b51-9545-05f2437329c8",
                "siteNr": 30517,
                "siteName": "TRÆLVIKA",
                "issueDate": "2024-04-29",
                "licenseHolder": {"orgNr": "966840528", "name": "SALMAR FARMING AS"},
            },
        },
        {
            "status": {"status": "ISSUED"},
            "installationCertificate": {
                "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "siteNr": 36077,
                "siteName": None,
                "issueDate": "2024-05-01",
            },
        },
    ],
    "totalElements": 2,
    "page": 0,
    "size": 20,
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
        if url == CERTIFICATES_URL:
            return JsonResponse(status=200, url=url, body=CERTIFICATES_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nytek fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = NytekSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["certificates"]
    assert [ref.source_native_uri for ref in refs] == [CERTIFICATES_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_printed_absolute_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/v3/certificates", OPENAPI_URL)
    assert url == CERTIFICATES_URL
    assert "/api-docs" not in url
    relative = printed_endpoint_url(
        {"servers": [{"url": "/"}]},
        "/api/v3/certificates",
        OPENAPI_URL,
    )
    assert relative == "https://api.fiskeridir.no/api/v3/certificates"


def test_nytek_is_a_registered_source() -> None:
    assert "nytek" in SOURCE_IDS
    source = build_source("nytek")
    assert isinstance(source, NytekSource)
    assert source.source_id == "nytek"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = NytekSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nytek"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == CERTIFICATES_URL
    assert row["title"] == "Søk etter anleggssertifikat med parametre"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("fiskeridir:")
    assert not str(row["id"]).startswith("buyer:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nytek_openapi_path"] == "/api/v3/certificates"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_certificates(tmp_path: Path) -> None:
    source = NytekSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == CERTIFICATES_URL
    assert result.table_id == "certificates"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"TRÆLVIKA", 36077}
    assert by_value["TRÆLVIKA"]["measure"] == "siteName"
    assert by_value[36077]["measure"] == "siteNr"
    dims = json.loads(by_value["TRÆLVIKA"]["dimensions_json"])
    assert dims["siteNr"] == "30517"
    assert dims["status"] == "ISSUED"
    assert "licenseHolder" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == CERTIFICATES_URL for row in rows)
    registry.close()


def test_cells_copy_printed_site_name_or_site_nr() -> None:
    cells = cells_from_nytek(CERTIFICATES_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "siteName"
    assert value == "TRÆLVIKA"
    assert dims["siteNr"] == "30517"
    assert dims["status"] == "ISSUED"
    assert "licenseHolder" not in dims
    fallback = cells_from_nytek(
        {"content": [{"installationCertificate": {"siteNr": 9, "siteName": None}}]}
    )
    assert fallback == [("siteNr", 9, {"siteName": ""})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nytek([{"siteName": "TRÆLVIKA"}])
    with pytest.raises(ValueError, match="content array"):
        cells_from_nytek({"siteName": "TRÆLVIKA"})


def test_is_nytek_url_accepts_only_nytek_public_path() -> None:
    assert is_nytek_url(CERTIFICATES_URL)
    assert is_nytek_url(OPENAPI_URL)
    assert nytek_table_id(CERTIFICATES_URL) == "certificates"
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({}) is None
    assert not is_nytek_url("https://api.fiskeridir.no/vessel-api/api/v1/vessels")
    assert not is_nytek_url("https://api.fiskeridir.no/buyer-api/v1/locations")
    assert not is_nytek_url("https://data.norge.no/datasets/x")
    assert not is_nytek_url("https://www.fiskeridir.no/nytek-public/api/v3/certificates")
    assert not is_nytek_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = NytekSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["certificates"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert nxt == []
