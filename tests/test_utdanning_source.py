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
from public_data_agent.sources.utdanning import (
    UtdanningSource,
    cells_from_utdanning,
    cells_from_utdanning_tidsserie,
    is_utdanning_tidsserie_url,
    is_utdanning_url,
    printed_endpoint_url,
    printed_license_url,
    utdanning_table_id,
)

OPENAPI_URL = "https://api.utdanning.no/openapi.json"
STEDSVELGER_URL = "https://api.utdanning.no/arbeidsmarkedskart/stedsvelger"
CAMPUS_URL = "https://api.utdanning.no/arbeidsmarkedskart/campus_yrke"
TIDSSERIE_URL = "https://api.utdanning.no/arbeidsmarkedskart/tidsserie"
DATASET_ID = "utdanning:stedsvelger"
TIDSSERIE_ID = "utdanning:tidsserie"

OPENAPI = {
    "info": {
        "title": "Utdanning.no API (production)",
        "description": "Åpent api for interne tjenester på utdanning.no.",
        "version": "v3018.0.0",
    },
    "paths": {
        "/arbeidsmarkedskart/campus_yrke": {
            "get": {"summary": "Viser hvilke steder du kan bli utdannet innen et yrke"}
        },
        "/arbeidsmarkedskart/campus_yrke/{uno_id}": {
            "get": {"summary": "Get one campus yrke"}
        },
        "/arbeidsmarkedskart/stedsvelger": {
            "get": {"summary": "Retrieves the collection of Stedsvelger_Fylke resources."}
        },
        "/fagskolevelgeren/sluttkompetanse": {
            "get": {"summary": "Returner en liste over alle sluttkompetanser"}
        },
    },
}
STEDSVELGER_BODY = [
    {
        "fylkenr": "22",
        "fylkenavn": "Jan Mayen",
        "fylketype": "EXTRA",
        "har_videregaende_skoler": False,
        "har_bedrifter": True,
        "region": None,
        "kommuner": [{"kommunenr": "2211", "kommunenavn": "Jan Mayen"}],
    },
    {
        "fylkenr": "03",
        "fylkenavn": "Oslo",
        "fylketype": "FYLKE",
        "har_videregaende_skoler": True,
        "har_bedrifter": True,
        "region": "Østlandet",
    },
]
TIDSSERIE_BODY = {
    "hydra:member": [
        {
            "id": "tidsserie_0301_2016-10-14",
            "dato": "2016-10-14",
            "antall_ansatte": 640739,
            "antall_aarsverk": 523385,
            "kommunenr": "0301",
            "kommunenavn": "Oslo",
            "fylkenr": "03",
            "fylkenavn": "Oslo",
            "region": "kommune",
        },
        {
            "id": "tidsserie_0301_2017-10-14",
            "dato": "2017-10-14",
            "antall_ansatte": 650000,
            "antall_aarsverk": 530000,
            "kommunenr": "0301",
            "kommunenavn": "Oslo",
            "fylkenr": "03",
            "fylkenavn": "Oslo",
            "region": "kommune",
        },
    ],
    "hydra:totalItems": 2,
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
        parts = urlsplit(url)
        if parts.path.rstrip("/") == urlsplit(TIDSSERIE_URL).path.rstrip("/"):
            kommune = parse_qs(parts.query).get("kommune", [None])[0]
            body = dict(TIDSSERIE_BODY)
            if kommune and kommune != "0301":
                body = {"hydra:member": [], "hydra:totalItems": 0}
            return JsonResponse(status=200, url=url, body=body)
        if url == STEDSVELGER_URL:
            return JsonResponse(status=200, url=url, body=STEDSVELGER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"utdanning fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = UtdanningSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "campus_yrke",
        "stedsvelger",
        "sluttkompetanse",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        CAMPUS_URL,
        STEDSVELGER_URL,
        "https://api.utdanning.no/fagskolevelgeren/sluttkompetanse",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_origin_when_servers_absent() -> None:
    url = printed_endpoint_url(OPENAPI, "/arbeidsmarkedskart/stedsvelger", OPENAPI_URL)
    assert url == STEDSVELGER_URL
    assert "/openapi.json" not in url
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://api.utdanning.no/"}]},
        "/arbeidsmarkedskart/stedsvelger",
        OPENAPI_URL,
    )
    assert with_server == STEDSVELGER_URL


def test_utdanning_is_a_registered_source() -> None:
    assert "utdanning" in SOURCE_IDS
    source = build_source("utdanning")
    assert isinstance(source, UtdanningSource)
    assert source.source_id == "utdanning"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = UtdanningSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "utdanning"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == STEDSVELGER_URL
    assert row["title"] == "Retrieves the collection of Stedsvelger_Fylke resources."
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["utdanning_openapi_path"] == "/arbeidsmarkedskart/stedsvelger"
    assert payload["license"] is None
    assert payload["publisher"] is None
    registry.close()


def test_fetch_refuses_stedsvelger_name_catalog(tmp_path: Path) -> None:
    source = UtdanningSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(ValueError, match="tidsserie"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
        )
    registry.close()


def test_tidsserie_url_is_observations() -> None:
    assert is_utdanning_tidsserie_url(TIDSSERIE_URL)
    assert not is_utdanning_tidsserie_url(STEDSVELGER_URL)
    assert classify_access_path(TIDSSERIE_URL)["kind"] == "observations"
    assert classify_access_path(STEDSVELGER_URL)["kind"] == "none"


def test_fetch_gets_printed_tidsserie_counts(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id=TIDSSERIE_ID,
        title="Retrieves the collection of Tidsserie resources.",
        publisher_name=None,
        access_path=TIDSSERIE_URL,
        license=None,
    )
    registry.conn.commit()
    result = fetch_observations(
        registry,
        TIDSSERIE_ID,
        table_id="ignored",
        http=FetchHttp(),
        select={"kommune": ["0301"]},
    )
    assert "kommune=0301" in result.request_url
    assert "itemsPerPage=100" in result.request_url
    assert result.table_id == "tidsserie"
    assert result.http_status == 200
    assert result.counts.listed == 4
    rows = registry.list_observations(TIDSSERIE_ID)
    ansatte = [
        json.loads(row["value_json"])
        for row in rows
        if row["measure"] == "antall_ansatte"
    ]
    assert sorted(ansatte) == [640739, 650000]
    dims = json.loads(
        next(row["dimensions_json"] for row in rows if row["measure"] == "antall_ansatte")
    )
    assert dims["kommunenr"] == "0301"
    assert dims["dato"] in {"2016-10-14", "2017-10-14"}
    assert all(row["license"] is None for row in rows)
    cap = registry.get_capability(TIDSSERIE_ID)
    assert cap["capability"] == "observations"
    registry.close()


def test_fetch_refuses_unfiltered_tidsserie(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id=TIDSSERIE_ID,
        title="Tidsserie",
        publisher_name=None,
        access_path=TIDSSERIE_URL,
        license=None,
    )
    registry.conn.commit()
    with pytest.raises(ValueError, match="printed kommune"):
        fetch_observations(
            registry,
            TIDSSERIE_ID,
            table_id="tidsserie",
            http=FetchHttp(),
        )
    registry.close()


def test_cells_copy_printed_tidsserie_counts() -> None:
    cells = cells_from_utdanning_tidsserie(TIDSSERIE_BODY)
    assert cells[0][0] == "antall_ansatte"
    assert cells[0][1] == 640739
    assert cells[0][2]["kommunenr"] == "0301"
    assert cells[1][0] == "antall_aarsverk"
    assert cells[1][1] == 523385
    with pytest.raises(ValueError, match="hydra collection"):
        cells_from_utdanning_tidsserie([])


def test_cells_copy_printed_fylkenavn_and_hydra() -> None:
    cells = cells_from_utdanning(STEDSVELGER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "fylkenavn"
    assert value == "Jan Mayen"
    assert dims["fylkenr"] == "22"
    assert "kommuner" not in dims
    hydra = cells_from_utdanning(
        {"hydra:member": [{"tittel": "Bygg- og anleggsteknikk", "utdanningsprogram_kode": "BA"}]}
    )
    assert hydra == [("tittel", "Bygg- og anleggsteknikk", {"utdanningsprogram_kode": "BA"})]
    strings = cells_from_utdanning(["Aktivitørfaget", "Anleggsgartnerfaget"])
    assert strings == [("value", "Aktivitørfaget", {}), ("value", "Anleggsgartnerfaget", {})]
    fallback = cells_from_utdanning([{"id": "9", "fylkenr": "03"}])
    assert fallback == [("id", "9", {"fylkenr": "03"})]
    with pytest.raises(ValueError, match="hydra collection"):
        cells_from_utdanning({"fylkenavn": "Oslo"})


def test_is_utdanning_url_accepts_only_api_host() -> None:
    assert is_utdanning_url(STEDSVELGER_URL)
    assert is_utdanning_url(OPENAPI_URL)
    assert utdanning_table_id(STEDSVELGER_URL) == "stedsvelger"
    assert printed_license_url({}) is None
    assert printed_license_url({"license": {"url": "https://example.invalid/nlod"}}) == (
        "https://example.invalid/nlod"
    )
    assert not is_utdanning_url("https://data.norge.no/datasets/x")
    assert not is_utdanning_url("https://v3.api.utdanning.no/arbeidsmarkedskart/stedsvelger")
    assert not is_utdanning_url("https://old.api.utdanning.no/arbeidsmarkedskart/stedsvelger")
    assert not is_utdanning_url("https://utdanning.no/api/v1/data_norge--yrkesbeskrivelse")
    assert not is_utdanning_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = UtdanningSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["campus_yrke"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["stedsvelger"]
