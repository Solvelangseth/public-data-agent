from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.resource_index import index_dataset
from public_data_agent.sources.stortinget import (
    StortingetSource,
    cells_from_stortinget,
    entity_from_periode,
    is_stortinget_url,
    is_stortingsperioder_url,
    printed_eksport_paths,
    printed_endpoint_url,
    printed_operation_id,
    printed_path_from_href,
    stortinget_table_id,
)

DOCS_URL = "https://data.stortinget.no/dokumentasjon-og-hjelp/teknisk-dokumentasjon/"
PERIODER_URL = "https://data.stortinget.no/eksport/stortingsperioder?format=json"
SESIONER_URL = "https://data.stortinget.no/eksport/sesjoner?format=json"
ENVREPORTREG_URL = "https://api.fiskeridir.no/envreportreg-public/api/v2/report/search"
HIMAPS_URL = "https://kart.hi.no/data/ogc/maps/v1/collections"
CRISTIN_URL = "https://api.cristin.no/v2/countries"
DATASET_ID = "stortinget:stortingsperioder"

DOCS_HTML = """
<html>
  <a href="http://data.stortinget.no/eksport/representanter?stortingsperiodeid=2005-2009">representanter</a>
  <a href="/eksport/stortingsperioder">stortingsperioder</a>
  <a href="http://data.stortinget.no/eksport/sesjoner">sesjoner</a>
  <a href="http://data.stortinget.no/eksport/emner">emner</a>
  <a href="http://data.stortinget.no/eksport/fylker">fylker</a>
  <a href="http://data.stortinget.no/eksport/partier?sesjonid=2009-2010">partier</a>
  <a href="http://data.stortinget.no/eksport/allepartier">allepartier</a>
  <a href="http://data.stortinget.no/eksport/komiteer?sesjonid=2009-2010">komiteer</a>
  <a href="http://data.stortinget.no/eksport/allekomiteer">allekomiteer</a>
  <a href="http://data.stortinget.no/eksport/dagensrepresentanter">dagensrepresentanter</a>
  <a href="http://data.stortinget.no/eksport/personbilde?personid=SMY&amp;storrelse=middels">personbilde</a>
  <a href="/eksport/sak?sakid=47163">sak</a>
  <a href="/eksport/saksganger">saksganger</a>
  <a href="/eksport/moter?sesjonid=2014-2015">moter</a>
</html>
"""

PERIODER_BODY = {
    "respons_dato_tid": "/Date(1787880350648+0200)/",
    "versjon": "1.6",
    "innevaerende_stortingsperiode": {
        "id": "2021-2025",
        "fra": "/Date(1633046400000+0200)/",
        "til": "/Date(1756684800000+0200)/",
    },
    "stortingsperioder_liste": [
        {
            "id": "2021-2025",
            "fra": "/Date(1633046400000+0200)/",
            "til": "/Date(1756684800000+0200)/",
            "versjon": "1.6",
            "nested": {"skip": True},
        },
        {
            "id": "2017-2021",
            "fra": "/Date(1504224000000+0200)/",
            "til": "/Date(1632960000000+0200)/",
            "versjon": "1.6",
        },
    ],
}


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
        if url == PERIODER_URL:
            return JsonResponse(status=200, url=url, body=PERIODER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"stortinget fetch must GET, not POST {url}")


def test_printed_refs_skip_query_examples_and_keep_collection_paths() -> None:
    source = StortingetSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "stortingsperioder",
        "sesjoner",
        "emner",
        "fylker",
        "allepartier",
        "allekomiteer",
        "dagensrepresentanter",
        "saksganger",
    ]
    assert refs[0].source_native_uri == PERIODER_URL
    assert refs[1].source_native_uri == SESIONER_URL
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all("sesjonid=" not in (ref.source_native_uri or "") for ref in refs)
    assert all("sakid=" not in (ref.source_native_uri or "") for ref in refs)
    assert DOCS_URL not in [ref.source_native_uri for ref in refs]


def test_printed_path_from_href_skips_required_query_examples() -> None:
    assert printed_path_from_href("/eksport/stortingsperioder") == "/eksport/stortingsperioder"
    assert printed_path_from_href(
        "http://data.stortinget.no/eksport/sesjoner"
    ) == "/eksport/sesjoner"
    assert printed_path_from_href(
        "http://data.stortinget.no/eksport/partier?sesjonid=2009-2010"
    ) is None
    assert printed_path_from_href("/eksport/sak?sakid=47163") is None
    assert printed_path_from_href("/eksport/person/{personid}") is None


def test_printed_endpoint_url_adds_documented_json_format() -> None:
    url = printed_endpoint_url("/eksport/stortingsperioder", DOCS_URL)
    assert url == PERIODER_URL
    assert "teknisk-dokumentasjon" not in url
    paths = printed_eksport_paths(DOCS_HTML)
    assert [path for path, _href in paths] == [
        "/eksport/stortingsperioder",
        "/eksport/sesjoner",
        "/eksport/emner",
        "/eksport/fylker",
        "/eksport/allepartier",
        "/eksport/allekomiteer",
        "/eksport/dagensrepresentanter",
        "/eksport/saksganger",
    ]


def test_printed_operation_id_keeps_last_segment() -> None:
    assert printed_operation_id("/eksport/stortingsperioder") == "stortingsperioder"
    assert printed_operation_id("/eksport/dagensrepresentanter") == "dagensrepresentanter"


def test_stortinget_is_a_registered_source() -> None:
    assert "stortinget" in SOURCE_IDS
    assert "envreportreg" in SOURCE_IDS
    assert "hicoverages" in SOURCE_IDS
    assert "cristin" in SOURCE_IDS
    source = build_source("stortinget")
    assert isinstance(source, StortingetSource)
    assert source.source_id == "stortinget"


def test_harvest_writes_printed_id_and_keeps_license_null(tmp_path: Path) -> None:
    source = StortingetSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 8
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "stortinget"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == PERIODER_URL
    assert row["title"] == "stortingsperioder"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("envreportreg:")
    assert not str(row["id"]).startswith("cristin:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["stortinget_docs_path"] == "/eksport/stortingsperioder"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_period_catalog_is_lookup_not_id_observations() -> None:
    assert is_stortingsperioder_url(PERIODER_URL)
    assert classify_access_path(PERIODER_URL)["kind"] == "lookup"
    entity = entity_from_periode(PERIODER_BODY["stortingsperioder_liste"][0])
    assert entity["subject_code"] == "2021-2025"
    assert entity["subject_scheme"] == "stortinget:periode_id"
    assert "nested" not in entity["attributes"]


def test_fetch_stores_period_lookups_not_id_observations(tmp_path: Path) -> None:
    source = StortingetSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    indexed = index_dataset(registry, DATASET_ID, http=FetchHttp(), catalogues={})
    assert indexed["fields"] >= 1
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        select={"id": ["2021-2025"]},
        http=FetchHttp(),
    )
    assert result.request_url == PERIODER_URL
    assert result.table_id == "stortingsperioder"
    assert result.http_status == 200
    assert result.counts.listed == 1
    assert result.sample[0]["kind"] == "entity"
    assert result.sample[0]["subject_code"] == "2021-2025"
    assert registry.list_observations(DATASET_ID) == []
    cap = registry.get_capability(DATASET_ID)
    assert cap["capability"] == "lookup"
    assert cap["verified_sample_count"] == 1
    with pytest.raises(ValueError, match="not in stortingsperioder"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            select={"id": ["NOPE"]},
            http=FetchHttp(),
        )
    registry.close()


def test_cells_copy_printed_navn_or_id() -> None:
    cells = cells_from_stortinget(PERIODER_BODY)
    assert cells[0][0] == "id"
    assert cells[0][1] == "2021-2025"
    assert cells[0][2]["versjon"] == "1.6"
    assert "nested" not in cells[0][2]
    assert cells_from_stortinget({"fylker_liste": [{"navn": "Oslo", "id": "03"}]}) == [
        ("navn", "Oslo", {"id": "03"})
    ]
    assert cells_from_stortinget("Oslo") == [
        ("value", "Oslo", {"value": "Oslo"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_stortinget(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_stortinget({"stortingsperioder_liste": []})


def test_is_stortinget_url_accepts_only_eksport_path() -> None:
    assert is_stortinget_url(PERIODER_URL)
    assert is_stortinget_url("https://data.stortinget.no/eksport/fylker")
    assert stortinget_table_id(PERIODER_URL) == "stortingsperioder"
    assert printed_endpoint_url("/eksport/stortingsperioder", DOCS_URL) == PERIODER_URL
    assert not is_stortinget_url(ENVREPORTREG_URL)
    assert not is_stortinget_url(HIMAPS_URL)
    assert not is_stortinget_url(CRISTIN_URL)
    assert not is_stortinget_url("https://data.norge.no/datasets/x")
    assert not is_stortinget_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = StortingetSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "stortingsperioder"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["sesjoner"]
    assert source.list_dataset_refs(limit=1, offset=8) == []
