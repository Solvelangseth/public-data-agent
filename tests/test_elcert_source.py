from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from urllib.parse import parse_qs, urlsplit

from public_data_agent.sources.elcert import (
    ElcertSource,
    cells_from_elcert,
    cells_from_elcert_quarter,
    cells_from_elcert_summary,
    elcert_table_id,
    is_elcert_quarter_url,
    is_elcert_summary_url,
    is_elcert_url,
    printed_base_url,
    printed_endpoint_url,
    printed_get_paths,
)

DOCS_URL = "https://api.nve.no/doc/elsertifikater/"
BASE_URL = "https://api.nve.no/web/ElCert"
APPLICATIONS_URL = f"{BASE_URL}/GetApplications"
SUMMARY_URL = f"{BASE_URL}/GetSummaryValues"
QUARTER_URL = f"{BASE_URL}/GetSummaryValuesPerQuarter"
MAGASIN_URL = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk"
VANNKRAFT_URL = "https://api.nve.no/web/Powerplant/GetHydroPowerPlantsInOperation"
VINDKRAFT_URL = "https://api.nve.no/web/WindPowerplant/GetWindPowerPlants"
DATASET_ID = "elcert:GetApplications"

DOCS_HTML = """
<div>[ <b>Base url:</b> <span class="currentScheme">https://</span>api.nve.no/web/ElCert ]</div>
<div class="opblock-summary opblock-summary-get">
    <div>
        <span class="opblock-summary-method">GET</span>
        <span class="opblock-summary-path"><span>/GetApplications</span></span>
    </div>
    <div>
        <div class="opblock-summary-description">Hent alle s&#248;knader om elsertifikat</div>
    </div>
</div>
<div class="opblock-summary opblock-summary-get">
    <div>
        <span class="opblock-summary-method">GET</span>
        <span class="opblock-summary-path"><span>/GetSummaryValues</span></span>
    </div>
    <div>
        <div class="opblock-summary-description">Hent summerte verdier for et gitt &#229;r og m&#229;ned eller kvartal</div>
    </div>
</div>
<div class="opblock-summary opblock-summary-get">
    <div>
        <span class="opblock-summary-method">GET</span>
        <span class="opblock-summary-path"><span>/GetSummaryValuesPerQuarter</span></span>
    </div>
    <div>
        <div class="opblock-summary-description">Hent summerte verdier per kvartal siden elsertifikatordningen startet</div>
    </div>
</div>
<div class="opblock-summary opblock-summary-get">
    <div>
        <span class="opblock-summary-method">GET</span>
        <span class="opblock-summary-path"><span>/GetApplications/{id}</span></span>
    </div>
    <div>
        <div class="opblock-summary-description">skip templated</div>
    </div>
</div>
"""

QUARTER_BODY = [
    {
        "Values": {"IMaalet": 0.0, "IOvergangsordningen": 8.842},
        "Year": 2012,
        "Quarter": 1,
    },
    {
        "Values": {"IMaalet": 1094.94, "IOvergangsordningen": 150.511},
        "Year": 2026,
        "Quarter": 3,
    },
]
SUMMARY_BODY = {"IMaalet": 1585.51, "IOvergangsordningen": 175.483}

APPLICATIONS_BODY = [
    {
        "Status": "Godkjent",
        "TypeAnlegg": "Vannkraft",
        "KraftverksNavn": "Myrbekk",
        "GWh": 0.8,
        "Fylke": "Rogaland",
        "Eiere": [{"Navn": "skip nested"}],
    },
    {
        "Status": "Godkjent",
        "TypeAnlegg": "Vannkraft",
        "KraftverksNavn": "Vaage",
        "Fylke": "Rogaland",
    },
]


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url == DOCS_URL:
            return DOCS_HTML
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        parts = urlsplit(url)
        if parts.path.rstrip("/") == urlsplit(SUMMARY_URL).path.rstrip("/"):
            query = parse_qs(parts.query)
            if query.get("year") == ["2025"] and query.get("month") == ["1"]:
                return JsonResponse(status=200, url=url, body=SUMMARY_BODY)
            return JsonResponse(status=200, url=url, body={})
        if url == APPLICATIONS_URL:
            return JsonResponse(status=200, url=url, body=APPLICATIONS_BODY)
        if url == QUARTER_URL:
            return JsonResponse(status=200, url=url, body=QUARTER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"elcert fetch must GET, not POST {url}")


def test_printed_refs_copy_get_paths() -> None:
    source = ElcertSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "GetApplications",
        "GetSummaryValues",
        "GetSummaryValuesPerQuarter",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        APPLICATIONS_URL,
        SUMMARY_URL,
        QUARTER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)


def test_printed_paths_keep_document_order() -> None:
    listed = printed_get_paths(DOCS_HTML)
    assert [item[0] for item in listed] == [
        "/GetApplications",
        "/GetSummaryValues",
        "/GetSummaryValuesPerQuarter",
    ]
    assert printed_base_url(DOCS_HTML) == BASE_URL
    assert printed_endpoint_url("/GetApplications", BASE_URL) == APPLICATIONS_URL


def test_elcert_is_a_registered_source() -> None:
    assert "elcert" in SOURCE_IDS
    assert "nve" in SOURCE_IDS
    assert "regobs" in SOURCE_IDS
    assert "grep" in SOURCE_IDS
    assert "sigmets" in SOURCE_IDS
    assert "aviationforecast" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    assert "vannkraft" in SOURCE_IDS
    assert "vindkraft" in SOURCE_IDS
    assert "vegogc" in SOURCE_IDS
    assert "rawms" in SOURCE_IDS
    source = build_source("elcert")
    assert isinstance(source, ElcertSource)
    assert source.source_id == "elcert"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = ElcertSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "elcert"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == APPLICATIONS_URL
    assert row["title"] == "Hent alle søknader om elsertifikat"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("nve:")
    assert not str(row["id"]).startswith("vannkraft:")
    assert not str(row["id"]).startswith("vindkraft:")
    nxt = registry.get_dataset("elcert:GetSummaryValuesPerQuarter")
    assert nxt is not None
    assert nxt["access_path"] == QUARTER_URL
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["elcert_docs_path"] == "/GetApplications"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_refuses_plant_name_catalog(tmp_path: Path) -> None:
    source = ElcertSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(ValueError, match="GetSummaryValues"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
        )
    registry.close()


def test_quarter_url_is_observations_not_plant_names() -> None:
    assert is_elcert_quarter_url(QUARTER_URL)
    assert classify_access_path(QUARTER_URL)["kind"] == "observations"
    assert not is_elcert_quarter_url(APPLICATIONS_URL)
    assert is_elcert_summary_url(SUMMARY_URL)
    assert classify_access_path(SUMMARY_URL)["kind"] == "observations"
    assert classify_access_path(APPLICATIONS_URL)["kind"] == "none"


def test_fetch_summary_stores_printed_monthly_cells(tmp_path: Path) -> None:
    source = ElcertSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        "elcert:GetSummaryValues",
        table_id="ignored",
        select={"Year": ["2025"], "Month": ["1"]},
        http=FetchHttp(),
    )
    assert "year=2025" in result.request_url
    assert "month=1" in result.request_url
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations("elcert:GetSummaryValues")
    by_measure = {row["measure"]: json.loads(row["value_json"]) for row in rows}
    assert by_measure["IMaalet"] == 1585.51
    assert by_measure["IOvergangsordningen"] == 175.483
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["Year"] == "2025"
    assert dims["Month"] == "1"
    cap = registry.get_capability("elcert:GetSummaryValues")
    assert cap["capability"] == "observations"
    registry.close()


def test_fetch_summary_refuses_missing_year_month(tmp_path: Path) -> None:
    source = ElcertSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(ValueError, match="Year and Month"):
        fetch_observations(
            registry,
            "elcert:GetSummaryValues",
            table_id="GetSummaryValues",
            http=FetchHttp(),
        )
    registry.close()


def test_cells_from_summary_copy_printed_values() -> None:
    cells = cells_from_elcert_summary(SUMMARY_BODY, year="2025", month="1")
    assert cells == [
        ("IMaalet", 1585.51, {"Year": "2025", "Month": "1"}),
        ("IOvergangsordningen", 175.483, {"Year": "2025", "Month": "1"}),
    ]


def test_cells_from_quarter_copy_printed_values() -> None:
    cells = cells_from_elcert_quarter(QUARTER_BODY)
    assert cells == [
        ("IMaalet", 0.0, {"Year": "2012", "Quarter": "1"}),
        ("IOvergangsordningen", 8.842, {"Year": "2012", "Quarter": "1"}),
        ("IMaalet", 1094.94, {"Year": "2026", "Quarter": "3"}),
        ("IOvergangsordningen", 150.511, {"Year": "2026", "Quarter": "3"}),
    ]


def test_fetch_quarter_stores_numeric_cells(tmp_path: Path) -> None:
    source = ElcertSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        "elcert:GetSummaryValuesPerQuarter",
        table_id="ignored",
        select={"Year": ["2026"], "Quarter": ["3"]},
        http=FetchHttp(),
    )
    assert result.request_url == QUARTER_URL
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations("elcert:GetSummaryValuesPerQuarter")
    by_measure = {row["measure"]: json.loads(row["value_json"]) for row in rows}
    assert by_measure["IMaalet"] == 1094.94
    assert by_measure["IOvergangsordningen"] == 150.511
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["Year"] == "2026"
    assert dims["Quarter"] == "3"
    cap = registry.get_capability("elcert:GetSummaryValuesPerQuarter")
    assert cap["capability"] == "observations"
    registry.close()


def test_cells_copy_printed_kraftverksnavn() -> None:
    cells = cells_from_elcert(APPLICATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "KraftverksNavn"
    assert value == "Myrbekk"
    assert dims["Status"] == "Godkjent"
    assert "Eiere" not in dims
    fallback = cells_from_elcert([{"Status": "Godkjent", "TypeAnlegg": "Vannkraft"}])
    assert fallback == [("Status", "Godkjent", {"TypeAnlegg": "Vannkraft"})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_elcert({"KraftverksNavn": "Myrbekk"})
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_elcert([])


def test_is_elcert_url_accepts_only_elcert_path() -> None:
    assert is_elcert_url(APPLICATIONS_URL)
    assert is_elcert_url(QUARTER_URL)
    assert elcert_table_id(APPLICATIONS_URL) == "GetApplications"
    assert elcert_table_id(QUARTER_URL) == "GetSummaryValuesPerQuarter"
    assert not is_elcert_url(MAGASIN_URL)
    assert not is_elcert_url(VANNKRAFT_URL)
    assert not is_elcert_url(VINDKRAFT_URL)
    assert not is_elcert_url("https://api.nve.no/doc/elsertifikater/")
    assert not is_elcert_url("https://data.norge.no/datasets/x")
    assert not is_elcert_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = ElcertSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "GetApplications"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["GetSummaryValuesPerQuarter"]
