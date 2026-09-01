from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brrollegruppe import (
    LIST_URL,
    BrrollegruppeSource,
    brrollegruppe_table_id,
    cells_from_brrollegruppe,
    is_brrollegruppe_url,
    printed_item_url,
)

ADOS_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rollegruppetyper/ADOS"
DAGL_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rollegruppetyper/DAGL"
AUTH_URL = "https://data.brreg.no/enhetsregisteret/autorisert-api/roller/rollegruppetyper/DAGL"
ROLLETYPE_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rolletyper/DAGL"
REPRESENTANT_URL = "https://data.brreg.no/enhetsregisteret/api/roller/representanter"
ORGFORM_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/AS"
KOMMUNER_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner/0301"
ROOT_URL = "https://data.brreg.no/enhetsregisteret/api"
DATASET_ID = "brrollegruppe:DAGL"

CATALOG = {
    "_embedded": {
        "rollegruppetyper": [
            {
                "kode": "ADOS",
                "beskrivelse": "Administrativ enhet - offentlig sektor",
                "_links": {"self": {"href": AUTH_URL.replace("DAGL", "ADOS")}},
            },
            {
                "kode": "DAGL",
                "beskrivelse": "Daglig leder",
                "_links": {"self": {"href": AUTH_URL}},
            },
            {
                "beskrivelse": "missing kode is skipped",
                "_links": {"self": {"href": AUTH_URL}},
            },
        ]
    }
}
ITEM_BODY = {
    "kode": "DAGL",
    "beskrivelse": "Daglig leder",
    "_links": {"self": {"href": AUTH_URL}},
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return CATALOG
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == DAGL_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"brrollegruppe fetch must GET, not POST {url}")


def test_printed_refs_copy_gruppe_kodes() -> None:
    source = BrrollegruppeSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["ADOS", "DAGL"]
    assert [ref.source_native_uri for ref in refs] == [ADOS_URL, DAGL_URL]
    assert all("autorisert-api" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/rolletyper/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/organisasjonsformer" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/kommuner" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_kode_onto_public_path() -> None:
    assert printed_item_url({"kode": "DAGL", "_links": {"self": {"href": AUTH_URL}}}, LIST_URL) == DAGL_URL
    assert printed_item_url({"kode": "DAGL"}, LIST_URL) == DAGL_URL
    assert printed_item_url({"kode": "ADOS"}, LIST_URL) == ADOS_URL


def test_brrollegruppe_is_a_registered_source() -> None:
    assert "brrollegruppe" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "brroller" in SOURCE_IDS
    assert "brorgform" in SOURCE_IDS
    assert "nbdps" in SOURCE_IDS
    assert "nbagency" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "vegwms" in SOURCE_IDS
    assert "fdkorg" in SOURCE_IDS
    assert "brrolletype" in SOURCE_IDS
    assert "brkommuner" in SOURCE_IDS
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
    assert SOURCE_IDS[-1] == "crinst"
    source = build_source("brrollegruppe")
    assert isinstance(source, BrrollegruppeSource)
    assert source.source_id == "brrollegruppe"


def test_harvest_writes_printed_kode_and_null_license(tmp_path: Path) -> None:
    source = BrrollegruppeSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "brrollegruppe"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == DAGL_URL
    assert row["title"] == "Daglig leder"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("brreg:")
    assert not str(row["id"]).startswith("brroller:")
    assert not str(row["id"]).startswith("brorgform:")
    ados = registry.get_dataset("brrollegruppe:ADOS")
    assert ados is not None
    assert ados["title"] == "Administrativ enhet - offentlig sektor"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "DAGL"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["brrollegruppe_rollegruppetype"]["kode"] == "DAGL"
    assert "_links" not in payload["brrollegruppe_rollegruppetype"]
    assert payload["brrollegruppe_self_href"] == DAGL_URL
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_beskrivelse(tmp_path: Path) -> None:
    source = BrrollegruppeSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == DAGL_URL
    assert result.table_id == "DAGL"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Daglig leder"]
    assert all(row["measure"] == "beskrivelse" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["kode"] == "DAGL"
    assert "_links" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == DAGL_URL for row in rows)
    registry.close()


def test_cells_copy_printed_gruppe() -> None:
    cells = cells_from_brrollegruppe(ITEM_BODY)
    assert cells == [("beskrivelse", "Daglig leder", {"kode": "DAGL"})]
    fallback = cells_from_brrollegruppe({"kode": "DAGL"})
    assert fallback == [("kode", "DAGL", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_brrollegruppe(["Daglig leder"])
    with pytest.raises(ValueError, match="rollegruppetype members"):
        cells_from_brrollegruppe({"_links": {"self": {"href": AUTH_URL}}})


def test_is_brrollegruppe_url_accepts_only_rollegruppetyper_item_paths() -> None:
    assert is_brrollegruppe_url(DAGL_URL)
    assert is_brrollegruppe_url(ADOS_URL)
    assert brrollegruppe_table_id(DAGL_URL) == "DAGL"
    assert not is_brrollegruppe_url(LIST_URL)
    assert not is_brrollegruppe_url(AUTH_URL)
    assert not is_brrollegruppe_url(ROLLETYPE_URL)
    assert not is_brrollegruppe_url(REPRESENTANT_URL)
    assert not is_brrollegruppe_url(ORGFORM_URL)
    assert not is_brrollegruppe_url(KOMMUNER_URL)
    assert not is_brrollegruppe_url(ROOT_URL)
    assert not is_brrollegruppe_url("https://data.norge.no/datasets/x")
    assert not is_brrollegruppe_url(None)


def test_limit_and_offset_slice_printed_grupper() -> None:
    source = BrrollegruppeSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["ADOS"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["DAGL"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
