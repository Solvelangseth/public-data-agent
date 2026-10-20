from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.cristin import (
    CristinSource,
    cells_from_cristin,
    cristin_table_id,
    is_cristin_url,
    printed_endpoint_url,
    printed_get_paths,
    printed_path_from_title,
)

DOCS_URL = "https://api.cristin.no/v2/"
COUNTRIES_URL = "https://api.cristin.no/v2/countries"
MATERIALS_URL = "https://api.cristin.no/v2/biobanks/materials"
SOURCES_URL = "https://api.cristin.no/v2/fundings/sources"
CATEGORIES_URL = "https://api.cristin.no/v2/results/categories"
BIOBANK_URL = "https://api.cristin.no/v2/biobanks/{id}"
DATASET_ID = "cristin:countries"

DOCS_HTML = """
<html>
  <span class="font-medium">GET biobanks?{parameters}</span>
  <span class="font-medium">GET biobanks/{id}</span>
  <span class="font-medium">GET biobanks/{id}/projects</span>
  <span class="font-medium">GET biobanks/materials</span>
  <span class="font-medium">GET countries</span>
  <span class="font-medium">GET fundings?{parameters}</span>
  <span class="font-medium">GET fundings/{id}</span>
  <span class="font-medium">GET fundings/sources</span>
  <span class="font-medium">GET institutions?{parameters}</span>
  <span class="font-medium">GET keywords?{parameters}</span>
  <span class="font-medium">GET persons?{parameters}</span>
  <span class="font-medium">GET persons/orcid</span>
  <span class="font-medium">GET /projects/participants/roles</span>
  <span class="font-medium">GET results/categories</span>
  <span class="font-medium">GET units?{parameters}</span>
</html>
"""

COUNTRIES_BODY = [
    {"code": "AD", "code_alpha3": "AND", "name": {"en": "Andorra"}},
    {"code": "NO", "code_alpha3": "NOR", "name": {"en": "Norway", "nb": "Norge"}},
]


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_text(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == DOCS_URL:
            return DOCS_HTML
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == COUNTRIES_URL:
            return JsonResponse(status=200, url=url, body=COUNTRIES_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"cristin fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_leading_slash_paths() -> None:
    source = CristinSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "biobanks",
        "biobanks/materials",
        "countries",
        "fundings",
        "fundings/sources",
        "institutions",
        "keywords",
        "persons",
        "persons/orcid",
        "results/categories",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        "https://api.cristin.no/v2/biobanks",
        MATERIALS_URL,
        COUNTRIES_URL,
        "https://api.cristin.no/v2/fundings",
        SOURCES_URL,
        "https://api.cristin.no/v2/institutions",
        "https://api.cristin.no/v2/keywords",
        "https://api.cristin.no/v2/persons",
        "https://api.cristin.no/v2/persons/orcid",
        CATEGORIES_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert BIOBANK_URL not in [ref.source_native_uri for ref in refs]
    assert "projects/participants/roles" not in [ref.source_native_id for ref in refs]
    assert all(ref.source_native_id != "" for ref in refs)


def test_printed_path_from_title_skips_required_templates() -> None:
    assert printed_path_from_title("GET countries") == "countries"
    assert printed_path_from_title("GET institutions?{parameters}") == "institutions"
    assert printed_path_from_title("GET biobanks/materials") == "biobanks/materials"
    assert printed_path_from_title("GET biobanks/{id}") is None
    assert printed_path_from_title("GET /projects/participants/roles") is None
    assert printed_path_from_title("POST countries") is None


def test_printed_get_paths_keep_document_order() -> None:
    listed = printed_get_paths(DOCS_HTML)
    assert [path for path, _title in listed][:3] == [
        "biobanks",
        "biobanks/materials",
        "countries",
    ]


def test_endpoint_url_joins_docs_origin() -> None:
    assert printed_endpoint_url("countries", DOCS_URL) == COUNTRIES_URL
    assert printed_endpoint_url("biobanks/materials", DOCS_URL) == MATERIALS_URL
    assert "docs" not in printed_endpoint_url("countries", DOCS_URL)


def test_cristin_is_a_registered_source() -> None:
    assert "cristin" in SOURCE_IDS
    assert "lister" in SOURCE_IDS
    assert "ogccoverages" in SOURCE_IDS
    assert "regnskap" in SOURCE_IDS
    assert "sikt" in SOURCE_IDS
    assert "nortaxa" in SOURCE_IDS
    source = build_source("cristin")
    assert isinstance(source, CristinSource)
    assert source.source_id == "cristin"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = CristinSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 10
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "cristin"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == COUNTRIES_URL
    assert row["title"] == "GET countries"
    materials = registry.get_dataset("cristin:biobanks/materials")
    assert materials is not None
    assert materials["title"] == "GET biobanks/materials"
    assert materials["access_path"] == MATERIALS_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("sikt:")
    assert not str(row["id"]).startswith("lister:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["cristin_docs_path"] == "countries"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_country_names(tmp_path: Path) -> None:
    source = CristinSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == COUNTRIES_URL
    assert result.table_id == "countries"
    assert result.http_status == 200
    assert result.counts.listed == 2
    assert registry.observation_count() == 0
    rows = registry.list_records(DATASET_ID, kind="entity")
    by_label = {row["subject_label"]: row for row in rows}
    assert set(by_label) == {"Andorra", "Norway"}
    assert all(row["measure"] is None and row["value_json"] is None for row in rows)
    assert by_label["Andorra"]["subject_code"] == "AD"
    attributes = json.loads(by_label["Andorra"]["attributes_json"])
    assert attributes["code_alpha3"] == "AND"
    assert "nb" not in attributes
    assert "code" not in attributes
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["request_url"] == COUNTRIES_URL for row in rows)
    registry.close()


def test_cells_copy_printed_localized_names_or_scalar() -> None:
    cells = cells_from_cristin(COUNTRIES_BODY)
    assert cells == [
        ("name", "Andorra", {"code": "AD", "code_alpha3": "AND"}),
        ("name", "Norway", {"code": "NO", "code_alpha3": "NOR"}),
    ]
    assert cells_from_cristin([{"code": "BASICRESEARCH"}]) == [
        ("code", "BASICRESEARCH", {})
    ]
    assert cells_from_cristin("Cristin") == [("value", "Cristin", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_cristin(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_cristin([])


def test_is_cristin_url_accepts_only_cristin_host_path() -> None:
    assert is_cristin_url(COUNTRIES_URL)
    assert is_cristin_url(MATERIALS_URL)
    assert is_cristin_url(DOCS_URL)
    assert cristin_table_id(COUNTRIES_URL) == "countries"
    assert cristin_table_id(MATERIALS_URL) == "biobanks/materials"
    assert cristin_table_id(CATEGORIES_URL) == "results/categories"
    assert not is_cristin_url("https://lister.artsdatabanken.no/odata/v1/naturetypesassessment2025")
    assert not is_cristin_url("https://dataverse.no/api/dataverses/:root/contents")
    assert not is_cristin_url("https://api7.cristin-test.uio.no/v2/countries")
    assert not is_cristin_url("https://data.norge.no/datasets/x")
    assert not is_cristin_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = CristinSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "biobanks"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["countries"]
