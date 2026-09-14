from __future__ import annotations

import json
from pathlib import Path

import pytest

from urllib.parse import parse_qs, urlsplit

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.aqua import (
    AquaSource,
    aqua_table_id,
    cells_from_aqua,
    cells_from_aqua_overview,
    is_aqua_overview_url,
    is_aqua_url,
    printed_endpoint_url,
    printed_license_url,
)

OPENAPI_URL = "https://api.fiskeridir.no/pub-aqua/api/api-docs"
AREAS_URL = "https://api.fiskeridir.no/pub-aqua/api/v1/areas"
SITES_URL = "https://api.fiskeridir.no/pub-aqua/api/v1/sites"
OVERVIEW_URL = "https://api.fiskeridir.no/pub-aqua/api/v1/licenses-overview"
OVERVIEW_ID = "aqua:licenses-overview"
LICENSE_URL = "https://www.fiskeridir.no/Tall-og-analyse/Lisens-for-bruk-av-Fiskeridirektoratets-data"
DATASET_ID = "aqua:areas"

OPENAPI = {
    "info": {
        "title": "Offentlig Akvakulturregister",
        "description": "API for det nye offentlige Akvakulturregisteret",
        "license": {"name": "FDIR data usage license", "url": LICENSE_URL},
        "version": "1.0.0",
    },
    "servers": [{"url": "https://api.fiskeridir.no/pub-aqua"}],
    "paths": {
        "/api/v1/sites": {"get": {"summary": "Hent en liste av lokaliteter"}},
        "/api/v1/sites/{site-nr}": {"get": {"summary": "Hent en lokalitet"}},
        "/api/v1/areas": {"get": {"summary": "Henter en liste av områder"}},
    },
}
OVERVIEW_BODY = [
    {
        "licenseNr": "A-A-0001",
        "legalEntityName": "NORGES MILJØ- OG BIOVITENSKAPELIGE UNIVERSITET (NMBU)",
        "capacity": {"accumulated": 1.0, "current": 1.0, "unit": "TN", "type": "MTK"},
        "nested": {"skip": True},
    }
]

AREAS_BODY = [
    {
        "id": 1000,
        "type": "COUNTRY",
        "defaultCode": "ABW",
        "defaultName": "ARUBA",
        "shortName": "ABW",
        "name": "ARUBA",
        "versionId": 1000,
        "nested": {"skip": "dict"},
    },
    {
        "id": 1001,
        "type": "COUNTRY",
        "defaultCode": "AFG",
        "defaultName": "AFGHANISTAN",
        "name": None,
    },
]


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
        parts = urlsplit(url)
        if parts.path.rstrip("/") == urlsplit(OVERVIEW_URL).path.rstrip("/"):
            nr = parse_qs(parts.query).get("license-nr", [None])[0]
            body = OVERVIEW_BODY if nr == "A-A-0001" else []
            return JsonResponse(status=200, url=url, body=body)
        if url == AREAS_URL:
            return JsonResponse(status=200, url=url, body=AREAS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"aqua fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = AquaSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["sites", "areas"]
    assert [ref.source_native_uri for ref in refs] == [SITES_URL, AREAS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_printed_absolute_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/v1/areas", OPENAPI_URL)
    assert url == AREAS_URL
    assert "/api-docs" not in url
    relative = printed_endpoint_url(
        {"servers": [{"url": "/"}]},
        "/api/v1/areas",
        OPENAPI_URL,
    )
    assert relative == "https://api.fiskeridir.no/api/v1/areas"


def test_aqua_is_a_registered_source() -> None:
    assert "aqua" in SOURCE_IDS
    source = build_source("aqua")
    assert isinstance(source, AquaSource)
    assert source.source_id == "aqua"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = AquaSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "aqua"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == AREAS_URL
    assert row["title"] == "Henter en liste av områder"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("fiskeridir:")
    assert not str(row["id"]).startswith("buyer:")
    assert not str(row["id"]).startswith("nytek:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["aqua_openapi_path"] == "/api/v1/areas"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    assert registry.enrichment_count() == 0
    registry.close()


def test_fetch_refuses_area_name_catalog(tmp_path: Path) -> None:
    source = AquaSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(ValueError, match="licenses-overview"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
        )
    registry.close()


def test_overview_url_is_observations() -> None:
    assert is_aqua_overview_url(OVERVIEW_URL)
    assert not is_aqua_overview_url(AREAS_URL)
    assert classify_access_path(OVERVIEW_URL)["kind"] == "observations"
    assert classify_access_path(AREAS_URL)["kind"] == "none"


def test_fetch_gets_printed_license_capacity(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id=OVERVIEW_ID,
        title="Hent alle tillatelser",
        publisher_name=None,
        access_path=OVERVIEW_URL,
        license=LICENSE_URL,
    )
    registry.conn.commit()
    result = fetch_observations(
        registry,
        OVERVIEW_ID,
        table_id="ignored",
        http=FetchHttp(),
        select={"license-nr": ["A-A-0001"]},
    )
    assert "license-nr=A-A-0001" in result.request_url
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(OVERVIEW_ID)
    by_measure = {row["measure"]: json.loads(row["value_json"]) for row in rows}
    assert by_measure["current"] == 1.0
    assert by_measure["accumulated"] == 1.0
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["licenseNr"] == "A-A-0001"
    assert dims["unit"] == "TN"
    assert "nested" not in dims
    assert all(row["license"] == LICENSE_URL for row in rows)
    cap = registry.get_capability(OVERVIEW_ID)
    assert cap["capability"] == "observations"
    registry.close()


def test_fetch_refuses_unfiltered_license_overview(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id=OVERVIEW_ID,
        title="overview",
        publisher_name=None,
        access_path=OVERVIEW_URL,
        license=None,
    )
    registry.conn.commit()
    with pytest.raises(ValueError, match="printed license-nr"):
        fetch_observations(
            registry,
            OVERVIEW_ID,
            table_id="licenses-overview",
            http=FetchHttp(),
        )
    registry.close()


def test_cells_copy_printed_capacity() -> None:
    cells = cells_from_aqua_overview(OVERVIEW_BODY)
    assert cells[0][0] == "current"
    assert cells[0][1] == 1.0
    assert cells[0][2]["licenseNr"] == "A-A-0001"
    assert cells[0][2]["unit"] == "TN"
    assert "nested" not in cells[0][2]
    assert cells[1] == ("accumulated", 1.0, cells[0][2])


def test_cells_copy_printed_name_or_default_name() -> None:
    cells = cells_from_aqua(AREAS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "ARUBA"
    assert dims["id"] == "1000"
    assert "nested" not in dims
    fallback = cells_from_aqua([{"id": 9, "name": None, "defaultName": "AFGHANISTAN"}])
    assert fallback == [("defaultName", "AFGHANISTAN", {"id": "9", "name": ""})]
    fish = cells_from_aqua([{"code": "010901", "nbNoName": "Abbor", "latinName": "Perca fluviatilis"}])
    assert fish == [("nbNoName", "Abbor", {"code": "010901", "latinName": "Perca fluviatilis"})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_aqua({"name": "ARUBA"})
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_aqua([])


def test_is_aqua_url_accepts_only_pub_aqua_path() -> None:
    assert is_aqua_url(AREAS_URL)
    assert is_aqua_url(OPENAPI_URL)
    assert aqua_table_id(AREAS_URL) == "areas"
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({}) is None
    assert not is_aqua_url("https://api.fiskeridir.no/vessel-api/api/v1/vessels")
    assert not is_aqua_url("https://api.fiskeridir.no/buyer-api/v1/locations")
    assert not is_aqua_url("https://api.fiskeridir.no/nytek-public/api/v3/certificates")
    assert not is_aqua_url("https://data.norge.no/datasets/x")
    assert not is_aqua_url("https://www.fiskeridir.no/pub-aqua/api/v1/areas")
    assert not is_aqua_url("https://www.barnehagefakta.no/api/Fylker")
    assert not is_aqua_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = AquaSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["sites"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["areas"]
