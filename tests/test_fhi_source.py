from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import (
    SelectionTooLarge,
    classify_access_path,
    fetch_observations,
)
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.fhi import (
    FhiStatistikkSource,
    cells_from_fhi,
    fhi_table_id,
    flatten_categories,
    is_fhi_table_url,
    is_fhi_url,
    printed_native_id,
    printed_table_data_url,
    printed_table_url,
    split_table_url,
    years_in,
)

ROOT = "https://statistikk-data.fhi.no/api/open/v1"
LIST_URL = f"{ROOT}/Common/source"
ABR_URL = f"{ROOT}/abr/Table"
T588 = f"{ROOT}/abr/Table/588"
DATASET_ID = "fhi:abr:588"

SOURCE_BODY = [
    {
        "id": "abr",
        "title": "Abortregisteret (ABR)",
        "description": "Om svangerskapsbrudd i Norge fra 1979 til i dag.",
        "aboutUrl": "https://www.fhi.no/op/abortregisteret",
        "publishedBy": "Folkehelseinstituttet",
    },
    {
        "id": "nokkel",
        "title": "Folkehelsestatistikk",
        "description": "Statistikk om befolkning.",
        "aboutUrl": "https://www.fhi.no/hn/",
        "publishedBy": "Folkehelseinstituttet",
    },
]
TABLE_BODY = [
    {
        "tableId": 588,
        "title": "A12b: Svangerskapsavbrot fordelt på prevensjonsbruk og alder",
        "publishedAt": "2026-05-12T05:00:00Z",
        "modifiedAt": "2026-05-11T12:31:46.265306Z",
    },
    {
        "tableId": 589,
        "title": "A12a: Svangerskapsavbrot fordelt på alder",
        "publishedAt": "2026-05-12T05:00:00Z",
        "modifiedAt": "2026-05-11T12:31:46.263593Z",
    },
]
NOKKEL_TABLES = [{"tableId": 670, "title": "Leseferdighet"}]

# GEO nests bydel under kommune under fylke, and every index is an array.
DIMENSIONS = {
    "dimensions": [
        {
            "code": "GEO",
            "label": "Geografi",
            "categories": [
                {
                    "value": "03",
                    "label": "Oslo (fylke)",
                    "children": [
                        {"value": "0301", "label": "Oslo", "children": [
                            {"value": "030102", "label": "Bydel Grünerløkka", "children": []},
                        ]},
                    ],
                }
            ],
        },
        {
            "code": "AAR",
            "label": "År",
            "categories": [
                {"value": "2019", "label": "2019"},
                {"value": "2024", "label": "2024"},
            ],
        },
        {
            "code": "MEASURE_TYPE",
            "label": "Måltall",
            "categories": [{"value": "RATE", "label": "andel (prosent)"}],
        },
    ]
}
JSONSTAT = {
    "class": "dataset",
    "label": "A12b",
    "id": ["GEO", "AAR", "MEASURE_TYPE"],
    "size": [1, 1, 1],
    "value": [20.14],
    "role": {"metric": ["MEASURE_TYPE"]},
    "dimension": {
        "GEO": {"category": {"index": ["030102"], "label": {"030102": "Bydel Grünerløkka"}}},
        "AAR": {"category": {"index": ["2024"], "label": {"2024": "2024"}}},
        "MEASURE_TYPE": {
            "category": {"index": ["RATE"], "label": {"RATE": "andel (prosent)"}}
        },
    },
}


class CatalogHttp:
    """Serves the register list and each register's table list."""

    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return SOURCE_BODY
        if url == ABR_URL:
            return TABLE_BODY
        if url == f"{ROOT}/nokkel/Table":
            return NOKKEL_TABLES
        raise AssertionError(f"unexpected GET {url}")


class TableHttp:
    """Serves one table's dimensions and its json-stat2 data."""

    def __init__(self) -> None:
        self.posted: list[dict] = []

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == f"{T588}/dimension?includeValues=true":
            return JsonResponse(status=200, url=url, body=DIMENSIONS)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        assert url == f"{T588}/data"
        self.posted.append(body)
        return JsonResponse(status=200, url=url, body=JSONSTAT)


def _harvested(tmp_path: Path) -> Registry:
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FhiStatistikkSource(http=CatalogHttp()))
    return registry


def test_listing_walks_registers_down_to_tables() -> None:
    """A register list URL names no cell, so refs must address tables."""

    refs = FhiStatistikkSource(http=CatalogHttp()).list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "abr:588",
        "abr:589",
        "nokkel:670",
    ]
    assert refs[0].source_native_uri == T588
    assert ABR_URL not in [ref.source_native_uri for ref in refs]


def test_fhi_is_a_registered_source() -> None:
    assert "fhi" in SOURCE_IDS
    assert isinstance(build_source("fhi"), FhiStatistikkSource)


def test_harvest_titles_the_table_not_the_register(tmp_path: Path) -> None:
    registry = _harvested(tmp_path)
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["access_path"] == T588
    assert row["title"].startswith("A12b")
    assert row["publisher_name"] == "Folkehelseinstituttet"
    assert row["license"] is None
    registry.close()


def test_a_table_url_is_fetchable_and_a_register_url_is_not() -> None:
    assert classify_access_path(T588)["kind"] == "observations"
    assert classify_access_path(ABR_URL)["kind"] != "observations"


def test_fetch_stores_numeric_cells(tmp_path: Path) -> None:
    registry = _harvested(tmp_path)
    http = TableHttp()
    result = fetch_observations(registry, DATASET_ID, table_id="588", http=http)

    assert result.request_url == f"{T588}/data"
    assert result.table_id == "588"
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID, ids=result.observation_ids)
    assert [json.loads(row["value_json"]) for row in rows] == [20.14]
    assert json.loads(rows[0]["dimensions_json"])["GEO"] == "Bydel Grünerløkka"
    assert rows[0]["measure"] == "andel (prosent)"
    registry.close()


def test_every_dimension_is_named_in_the_query(tmp_path: Path) -> None:
    """FHI 400s on an unfiltered dimension, so none may be left implicit."""

    registry = _harvested(tmp_path)
    http = TableHttp()
    fetch_observations(registry, DATASET_ID, table_id="588", http=http)
    sent = {d["code"] for d in http.posted[0]["dimensions"]}
    assert sent == {"GEO", "AAR", "MEASURE_TYPE"}
    assert http.posted[0]["response"] == {"format": "json-stat2"}
    registry.close()


def test_geography_selection_keeps_every_nested_level(tmp_path: Path) -> None:
    """Bydel sit under kommune under fylke; a query must name each one."""

    registry = _harvested(tmp_path)
    http = TableHttp()
    fetch_observations(registry, DATASET_ID, table_id="588", http=http)
    geo = next(d for d in http.posted[0]["dimensions"] if d["code"] == "GEO")
    assert geo["values"] == ["03", "0301", "030102"]
    registry.close()


def test_year_range_narrows_the_period_dimension(tmp_path: Path) -> None:
    registry = _harvested(tmp_path)
    http = TableHttp()
    fetch_observations(
        registry, DATASET_ID, table_id="588", from_year=2024, to_year=2024, http=http
    )
    aar = next(d for d in http.posted[0]["dimensions"] if d["code"] == "AAR")
    assert aar["values"] == ["2024"]
    registry.close()


def test_unsatisfiable_year_range_fails_instead_of_fetching_everything(
    tmp_path: Path,
) -> None:
    registry = _harvested(tmp_path)
    with pytest.raises(ValueError, match="prints no period"):
        fetch_observations(
            registry, DATASET_ID, table_id="588", from_year=1800, to_year=1801,
            http=TableHttp(),
        )
    registry.close()


def test_select_rejects_a_value_the_table_does_not_print(tmp_path: Path) -> None:
    """Dropping an unknown value silently would answer a different question."""

    registry = _harvested(tmp_path)
    with pytest.raises(ValueError, match="does not print"):
        fetch_observations(
            registry, DATASET_ID, table_id="588",
            select={"GEO": ["030102", "9999"]}, http=TableHttp(),
        )
    registry.close()


def test_selection_over_the_limit_names_what_to_narrow() -> None:
    from public_data_agent.fetch import _fhi_selection

    with pytest.raises(SelectionTooLarge) as excinfo:
        _fhi_selection(
            DIMENSIONS["dimensions"], from_year=None, to_year=None, select=None,
            table_id="588", cell_limit=2,
        )
    assert "588" in str(excinfo.value)
    assert {d["code"] for d in excinfo.value.dimensions} == {
        "GEO", "AAR", "MEASURE_TYPE",
    }


def test_flatten_categories_walks_the_whole_tree() -> None:
    assert flatten_categories(DIMENSIONS["dimensions"][0]["categories"]) == [
        ("03", "Oslo (fylke)"),
        ("0301", "Oslo"),
        ("030102", "Bydel Grünerløkka"),
    ]


def test_years_in_reads_plain_years_and_spans() -> None:
    assert years_in("2020") == [2020]
    assert years_in("2023_2025") == [2023, 2025]
    assert years_in("alle") == []


def test_cells_copy_printed_table_ids() -> None:
    cells = cells_from_fhi(TABLE_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure.startswith("A12b")
    assert value == 588
    assert dims["tableId"] == "588"
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_fhi({"tableId": 588})


def test_url_predicates_separate_tables_from_registers() -> None:
    assert is_fhi_url(LIST_URL)
    assert is_fhi_url(ABR_URL)
    assert is_fhi_table_url(T588)
    assert not is_fhi_table_url(ABR_URL)
    assert split_table_url(T588) == ("abr", "588")
    assert printed_table_data_url("abr", "588") == T588
    assert fhi_table_id(ABR_URL) == "abr"
    assert printed_native_id(ABR_URL) == "abr"
    assert printed_table_url("abr") == ABR_URL
    assert not is_fhi_url("https://data.norge.no/datasets/x")
    assert not is_fhi_url("https://www.fhi.no/api/open/v1/abr/Table")


def test_limit_and_offset_slice_the_table_listing() -> None:
    source = FhiStatistikkSource(http=CatalogHttp())
    assert [r.source_native_id for r in source.list_dataset_refs(limit=2)] == [
        "abr:588",
        "abr:589",
    ]
    assert [
        r.source_native_id for r in source.list_dataset_refs(limit=1, offset=2)
    ] == ["nokkel:670"]
