from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.fdkorg import (
    LIST_URL,
    FdkorgSource,
    fdkorg_table_id,
    cells_from_fdkorg,
    is_fdkorg_url,
    printed_item_url,
)

BEIARN_URL = (
    "https://organization-catalogue.fellesdatakatalog.digdir.no/organizations/961147867"
)
BINDAL_URL = (
    "https://organization-catalogue.fellesdatakatalog.digdir.no/organizations/964983380"
)
BRREG_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/961147867"
KOMMUNEINFO_URL = "https://api.kartverket.no/kommuneinfo/v1/kommuner"
DATANORGE_URL = "https://data.norge.no/datasets/x"
NORGES_BANK_URL = "https://data.norges-bank.no/api/agencyscheme?format=sdmx-json"
DATASET_ID = "fdkorg:961147867"

CATALOG = [
    {
        "organizationId": "961147867",
        "name": "BEIARN KOMMUNE",
        "orgType": "KOMM",
        "prefLabel": {"nb": "Beiarn kommune"},
    },
    {
        "organizationId": "964983380",
        "name": "BINDAL KOMMUNE",
        "orgType": "KOMM",
        "prefLabel": {"nb": "Bindal kommune"},
    },
    {
        "name": "missing organizationId is skipped",
    },
]
ITEM_BODY = {
    "organizationId": "961147867",
    "name": "BEIARN KOMMUNE",
    "orgType": "KOMM",
    "norwegianRegistry": BRREG_URL,
    "prefLabel": {"nb": "Beiarn kommune"},
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
        if url == BEIARN_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"fdkorg fetch must GET, not POST {url}")


def test_printed_refs_copy_organization_ids() -> None:
    source = FdkorgSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["961147867", "964983380"]
    assert [ref.source_native_uri for ref in refs] == [BEIARN_URL, BINDAL_URL]
    assert all("data.brreg.no" not in (ref.source_native_uri or "") for ref in refs)
    assert all("norges-bank.no" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_organization_id() -> None:
    assert printed_item_url({"organizationId": "961147867"}, LIST_URL) == BEIARN_URL


def test_fdkorg_is_a_registered_source() -> None:
    assert "fdkorg" in SOURCE_IDS
    assert "datanorge" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "kommuneinfo" in SOURCE_IDS
    assert "nbagency" in SOURCE_IDS
    assert "hiwms" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "nbdps" in SOURCE_IDS
    assert "vegwms" in SOURCE_IDS
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
    assert SOURCE_IDS[-1] == "nibioar50"
    source = build_source("fdkorg")
    assert isinstance(source, FdkorgSource)
    assert source.source_id == "fdkorg"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = FdkorgSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "fdkorg"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == BEIARN_URL
    assert row["title"] == "Beiarn kommune"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("brreg:")
    assert not str(row["id"]).startswith("datanorge:")
    nxt = registry.get_dataset("fdkorg:964983380")
    assert nxt is not None
    assert nxt["title"] == "Bindal kommune"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "961147867"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["fdkorg_organization"]["organizationId"] == "961147867"
    assert "prefLabel" not in payload["fdkorg_organization"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_name(tmp_path: Path) -> None:
    source = FdkorgSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == BEIARN_URL
    assert result.table_id == "961147867"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["BEIARN KOMMUNE"]
    assert all(row["measure"] == "name" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["organizationId"] == "961147867"
    assert "prefLabel" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == BEIARN_URL for row in rows)
    registry.close()


def test_cells_copy_printed_organization() -> None:
    cells = cells_from_fdkorg(ITEM_BODY)
    assert cells[0][0] == "name"
    assert cells[0][1] == "BEIARN KOMMUNE"
    assert cells[0][2]["organizationId"] == "961147867"
    fallback = cells_from_fdkorg({"organizationId": "961147867"})
    assert fallback == [("organizationId", "961147867", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_fdkorg(["BEIARN KOMMUNE"])
    with pytest.raises(ValueError, match="organization members"):
        cells_from_fdkorg({"prefLabel": {"nb": "Beiarn kommune"}})


def test_is_fdkorg_url_accepts_only_organization_item_paths() -> None:
    assert is_fdkorg_url(BEIARN_URL)
    assert not is_fdkorg_url(LIST_URL)
    assert fdkorg_table_id(BEIARN_URL) == "961147867"
    assert not is_fdkorg_url(BRREG_URL)
    assert not is_fdkorg_url(KOMMUNEINFO_URL)
    assert not is_fdkorg_url(DATANORGE_URL)
    assert not is_fdkorg_url(NORGES_BANK_URL)
    assert not is_fdkorg_url(None)


def test_limit_and_offset_slice_printed_organizations() -> None:
    source = FdkorgSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["961147867"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["964983380"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
