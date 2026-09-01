from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.broppdater import (
    BroppdaterSource,
    broppdater_table_id,
    cells_from_broppdater,
    is_broppdater_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/openapi.json"
ROLLER_URL = "https://data.brreg.no/enhetsregisteret/api/oppdateringer/roller"
ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/oppdateringer/enheter"
UNDERENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/oppdateringer/underenheter"
LICENSE_URL = "https://data.norge.no/nlod/no/2.0"
DATASET_ID = "broppdater:enheter"
BRREG_URL = "https://data.brreg.no/enhetsregisteret/api"
ROLLE_URL = "https://data.brreg.no/enhetsregisteret/api/roller/representanter"
ORGFORM_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer"
KOMMUNER_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner"
ROLLETYPE_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rolletyper"
ROLLEGRUPPE_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rollegruppetyper"

OPENAPI = {
    "openapi": "3.0.1",
    "info": {
        "title": "Enhetsregisterets dokumentasjon for åpne data",
        "description": "Åpne data inkludert oppdateringer",
        "license": {"name": "Norsk lisens for offentlige data (NLOD)", "url": LICENSE_URL},
    },
    "servers": [{"url": "https://data.brreg.no", "description": "Server"}],
    "paths": {
        "/enhetsregisteret/api/organisasjonsformer": {
            "get": {"summary": "Enhetsregisteret leftover, skip"},
        },
        "/enhetsregisteret/api/roller/representanter": {
            "get": {"summary": "roller leftover, skip"},
        },
        "/enhetsregisteret/api/oppdateringer/roller": {
            "get": {"summary": "Hent alle oppdateringer på roller"},
        },
        "/enhetsregisteret/api/oppdateringer/enheter": {
            "get": {"summary": "Hent alle oppdateringer på enheter"},
        },
        "/enhetsregisteret/api/oppdateringer/underenheter": {
            "get": {"summary": "Hent alle oppdateringer på underenheter"},
        },
        "/enhetsregisteret/api/oppdateringer/{id}": {
            "get": {
                "summary": "templated",
                "parameters": [
                    {
                        "name": "id",
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
ENHETER_BODY = {
    "_embedded": {
        "oppdaterteEnheter": [
            {
                "oppdateringsid": 1,
                "dato": "2018-04-23T06:03:29.443Z",
                "organisasjonsnummer": "913189892",
                "endringstype": "Ukjent",
                "_links": {
                    "enhet": {
                        "href": "https://data.brreg.no/enhetsregisteret/api/enheter/913189892"
                    }
                },
            },
            {
                "oppdateringsid": 2,
                "dato": "2018-04-23T06:03:29.500Z",
                "organisasjonsnummer": "913189900",
                "endringstype": "Ny",
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
        raise AssertionError(f"broppdater fetch must GET, not POST {url}")


def test_printed_refs_keep_leftover_oppdateringer_paths() -> None:
    source = BroppdaterSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "roller",
        "enheter",
        "underenheter",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        ROLLER_URL,
        ENHETER_URL,
        UNDERENHETER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "organisasjonsformer" for ref in refs)
    assert all(ref.source_native_id != "representanter" for ref in refs)
    assert all(ref.source_native_id != "icnpo-kategorier" for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_server_and_path() -> None:
    url = printed_endpoint_url(
        OPENAPI, "/enhetsregisteret/api/oppdateringer/enheter", OPENAPI_URL
    )
    assert url == ENHETER_URL
    assert "/frivillighetsregisteret/" not in url
    assert "/roller/" not in url


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/enhetsregisteret/api/oppdateringer/enheter") == "enheter"
    assert printed_operation_id("/enhetsregisteret/api/oppdateringer/roller") == "roller"


def test_printed_license_url_copies_openapi_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Enhetsregisteret"}) is None


def test_broppdater_is_a_registered_source() -> None:
    assert "broppdater" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "brroller" in SOURCE_IDS
    assert "brorgform" in SOURCE_IDS
    assert "brrolletype" in SOURCE_IDS
    assert "brkommuner" in SOURCE_IDS
    assert "brrollegruppe" in SOURCE_IDS
    assert "mdirgis" in SOURCE_IDS
    assert "ssbcorr" in SOURCE_IDS
    assert "bwgis" in SOURCE_IDS
    assert "nbdps" in SOURCE_IDS
    assert "nbagency" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "vegwms" in SOURCE_IDS
    assert "fdkorg" in SOURCE_IDS
    assert "nguminer" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("kvtopo") + 1] == "nbdps"
    assert SOURCE_IDS[SOURCE_IDS.index("nbdps") + 1] == "vegwms"
    assert SOURCE_IDS[SOURCE_IDS.index("vegwms") + 1] == "fdkorg"
    assert SOURCE_IDS[SOURCE_IDS.index("fdkorg") + 1] == "brrolletype"
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
    assert SOURCE_IDS[SOURCE_IDS.index("dsbgis") + 1] == "nibiogard"
    assert SOURCE_IDS[SOURCE_IDS.index("nibiogard") + 1] == "stskrift"
    assert SOURCE_IDS[SOURCE_IDS.index("stskrift") + 1] == "stinterp"
    assert SOURCE_IDS[-1] == "stinterp"
    source = build_source("broppdater")
    assert isinstance(source, BroppdaterSource)
    assert source.source_id == "broppdater"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = BroppdaterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "broppdater"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ENHETER_URL
    assert row["title"] == "Hent alle oppdateringer på enheter"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("brreg:")
    assert not str(row["id"]).startswith("brroller:")
    assert not str(row["id"]).startswith("brorgform:")
    assert not str(row["id"]).startswith("brrollegruppe:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["broppdater_openapi_path"] == "/enhetsregisteret/api/oppdateringer/enheter"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_endringstype(tmp_path: Path) -> None:
    source = BroppdaterSource(http=CatalogHttp())
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
    by_org = {
        json.loads(row["dimensions_json"])["organisasjonsnummer"]: row for row in rows
    }
    assert set(by_org) == {"913189892", "913189900"}
    assert json.loads(by_org["913189892"]["value_json"]) == "Ukjent"
    assert by_org["913189892"]["measure"] == "endringstype"
    dims = json.loads(by_org["913189892"]["dimensions_json"])
    assert dims["oppdateringsid"] == "1"
    assert "_links" not in dims
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == ENHETER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_endringstype() -> None:
    cells = cells_from_broppdater(ENHETER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "endringstype"
    assert value == "Ukjent"
    assert dims["organisasjonsnummer"] == "913189892"
    assert dims["oppdateringsid"] == "1"
    assert "_links" not in dims
    fallback = cells_from_broppdater(
        {"_embedded": {"oppdaterteEnheter": [{"oppdateringsid": 7}]}}
    )
    assert fallback == [("oppdateringsid", 7, {})]
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_broppdater({"_embedded": {"oppdaterteEnheter": []}})


def test_is_broppdater_url_accepts_only_oppdateringer_paths() -> None:
    assert is_broppdater_url(ENHETER_URL)
    assert is_broppdater_url(ROLLER_URL)
    assert is_broppdater_url(UNDERENHETER_URL)
    assert broppdater_table_id(ENHETER_URL) == "enheter"
    assert not is_broppdater_url(BRREG_URL)
    assert not is_broppdater_url(ROLLE_URL)
    assert not is_broppdater_url(ORGFORM_URL)
    assert not is_broppdater_url(KOMMUNER_URL)
    assert not is_broppdater_url(ROLLETYPE_URL)
    assert not is_broppdater_url(ROLLEGRUPPE_URL)
    assert not is_broppdater_url(OPENAPI_URL)
    assert not is_broppdater_url("https://data.norge.no/datasets/x")
    assert not is_broppdater_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = BroppdaterSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "roller"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["enheter"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
