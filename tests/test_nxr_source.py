from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nxr import (
    NxrSource,
    cells_from_nxr,
    is_nxr_url,
    nxr_table_id,
    printed_endpoint_url,
    printed_license_url,
)

OPENAPI_URL = "https://data-nxr-fellestjeneste.udir.no/swagger/v2/swagger.json"
FYLKEDATA_URL = "https://data-nxr-fellestjeneste.udir.no/api/v2/fylkedata"
KOMMUNEDATA_URL = "https://data-nxr-fellestjeneste.udir.no/api/v2/kommunedata"
NLOD_URL = "https://data.norge.no/nlod/no"
DATASET_ID = "nxr:fylkedata"

OPENAPI = {
    "info": {
        "title": "NXR Fellestjeneste API",
        "description": "NXR fellestjeneste tilbyr data om fylker, kommuner, bydeler, postnummer og KOSTRA-grupper.",
        "license": {"name": "Lisens: Norsk lisens for offentlige data (NLOD)", "url": NLOD_URL},
        "version": "2.0",
    },
    "paths": {
        "/api/v2/fylkedata": {"get": {"summary": "Hent liste med fylkedata"}},
        "/api/v2/enhetinfo/{organisasjonsnummer}": {"get": {"summary": "Hent info om en enhet"}},
        "/api/v2/kommunedata": {"get": {"summary": "Hent liste med kommunedata"}},
        "/api/v2/enheter/sok": {"post": {"summary": "Søk"}},
    },
}
FYLKEDATA_BODY = [
    {
        "FylkeDataId": "FYLKE_01_1900_01_01",
        "Fylkesnummer": "01",
        "Fylkesnavn": "Smaalenenes amt",
        "ForloeperFylkeDataIdListe": [],
        "nested": {"skip": "dict"},
    },
    {
        "FylkeDataId": "FYLKE_03_1919_01_01",
        "Fylkesnummer": "03",
        "Fylkesnavn": "Kristiania",
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
        if url == FYLKEDATA_URL:
            return JsonResponse(status=200, url=url, body=FYLKEDATA_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nxr fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_post_paths() -> None:
    source = NxrSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["fylkedata", "kommunedata"]
    assert [ref.source_native_uri for ref in refs] == [FYLKEDATA_URL, KOMMUNEDATA_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_openapi_origin_when_servers_absent() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/v2/fylkedata", OPENAPI_URL)
    assert url == FYLKEDATA_URL
    assert "/swagger/" not in url
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://data-nxr-fellestjeneste.udir.no/"}]},
        "/api/v2/fylkedata",
        OPENAPI_URL,
    )
    assert with_server == FYLKEDATA_URL


def test_nxr_is_a_registered_source() -> None:
    assert "nxr" in SOURCE_IDS
    source = build_source("nxr")
    assert isinstance(source, NxrSource)
    assert source.source_id == "nxr"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = NxrSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nxr"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FYLKEDATA_URL
    assert row["title"] == "Hent liste med fylkedata"
    assert row["publisher_name"] is None
    assert row["license"] == NLOD_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("udir:")
    assert not str(row["id"]).startswith("nbr:")
    assert not str(row["id"]).startswith("nor:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nxr_openapi_path"] == "/api/v2/fylkedata"
    assert payload["license"] == NLOD_URL
    assert payload["publisher"] is None
    assert registry.enrichment_count() == 0
    registry.close()


def test_fetch_gets_printed_fylkedata(tmp_path: Path) -> None:
    source = NxrSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == FYLKEDATA_URL
    assert result.table_id == "fylkedata"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Smaalenenes amt", "Kristiania"]
    assert all(row["measure"] == "Fylkesnavn" for row in rows)
    by_name = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_name["Smaalenenes amt"]["dimensions_json"])
    assert dims["Fylkesnummer"] == "01"
    assert "nested" not in dims
    assert "ForloeperFylkeDataIdListe" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == NLOD_URL for row in rows)
    assert all(row["access_path"] == FYLKEDATA_URL for row in rows)
    registry.close()


def test_cells_copy_printed_fylkesnavn() -> None:
    cells = cells_from_nxr(FYLKEDATA_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "Fylkesnavn"
    assert value == "Smaalenenes amt"
    assert dims["Fylkesnummer"] == "01"
    assert "nested" not in dims
    fallback = cells_from_nxr({"KodeListe": [{"Kode": "EAFK01", "Versjon": "1.0"}]})
    assert fallback == [("Kode", "EAFK01", {"Versjon": "1.0"})]
    unwrapped = cells_from_nxr([{"Id": "POSTNUMMERKATEGORI_B", "Navn": "[B] Både gateadresser og postbokser"}])
    assert unwrapped == [("Navn", "[B] Både gateadresser og postbokser", {"Id": "POSTNUMMERKATEGORI_B"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nxr("fylkedata")
    with pytest.raises(ValueError, match="printed no collection list"):
        cells_from_nxr({"Sidenummer": 1, "AntallPerSide": 1000})
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_nxr({"FylkeListe": []})


def test_is_nxr_url_accepts_only_nxr_host() -> None:
    assert is_nxr_url(FYLKEDATA_URL)
    assert is_nxr_url(OPENAPI_URL)
    assert nxr_table_id(FYLKEDATA_URL) == "fylkedata"
    assert printed_license_url(OPENAPI["info"]) == NLOD_URL
    assert printed_license_url({}) is None
    assert not is_nxr_url("https://data-nsr.udir.no/skoletyper")
    assert not is_nxr_url("https://data-nbr.udir.no/v3/barnehagekategorier")
    assert not is_nxr_url("https://data-nor.udir.no/v4/maalformer")
    assert not is_nxr_url("https://data-npr.udir.no/v4/naeringskoder")
    assert not is_nxr_url("https://data-nfr.udir.no/v4/skolefritidsordningskategorier")
    assert not is_nxr_url("https://data.norge.no/datasets/x")
    assert not is_nxr_url("https://www.udir.no/fylkedata")
    assert not is_nxr_url("https://nlr.udir.no/api/v2/fylkedata")
    assert not is_nxr_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = NxrSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["fylkedata"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["kommunedata"]
