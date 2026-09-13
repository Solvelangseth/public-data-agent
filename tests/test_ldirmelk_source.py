from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.fetch import SelectionTooLarge, classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.mapping import map_harvested_record
from public_data_agent.registry import Registry
from public_data_agent.resource_index import index_dataset
from public_data_agent.sources import build_source
from public_data_agent.sources.ldirmelk import (
    CSV_PATH,
    FARM_LIMIT,
    GITHUB_API,
    RAW_PREFIX,
    LdirMelkSource,
    cells_from_ldirmelk,
    is_ldirmelk_url,
    ldirmelk_table_id,
)

YEAR = "2025"
CSV_URL = f"{RAW_PREFIX}/{YEAR}/dataset.csv"
CSV = (
    "orgnr;navn;komnr;kumelk_liter;geitemelk_liter\n"
    "811580082;BOB SAMDRIFT DA;1124;857721;\n"
    "811891452;MARIUS VINJARENGEN;3448;97402;1200\n"
)
LISTING = [
    {"name": "2024", "type": "dir", "sha": "abc"},
    {"name": "2025", "type": "dir", "sha": "def"},
    {"name": "meta.xml", "type": "file", "sha": "meta"},
]


class ScriptedHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == GITHUB_API:
            return LISTING
        raise AssertionError(url)

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url == CSV_URL:
            return CSV
        raise AssertionError(url)


def test_url_predicate_only_matches_the_printed_csv() -> None:
    assert is_ldirmelk_url(CSV_URL)
    assert ldirmelk_table_id(CSV_URL) == YEAR
    assert not is_ldirmelk_url(
        "https://github.com/LandbruksdirektoratetGIT/opendata/tree/main/"
        "datasets/leveransedata-melk/2025"
    )
    assert not is_ldirmelk_url(
        "https://raw.githubusercontent.com/LandbruksdirektoratetGIT/opendata/"
        "refs/heads/main/datasets/leveransedata-egg/2025/dataset.csv"
    )
    assert classify_access_path(CSV_URL)["kind"] == "observations"
    assert isinstance(build_source("ldirmelk"), LdirMelkSource)


def test_national_cells_sum_printed_litres_and_skip_empty() -> None:
    cells = cells_from_ldirmelk(CSV, year=YEAR)
    assert cells == [
        ("kumelk_liter", 955123, {"år": "2025"}),
        ("geitemelk_liter", 1200, {"år": "2025"}),
    ]


def test_farm_select_uses_printed_orgnr_and_refuses_unknown() -> None:
    cells = cells_from_ldirmelk(
        CSV, year=YEAR, select={"organisasjonsnummer": ["811580082"]}
    )
    assert cells == [
        (
            "kumelk_liter",
            857721,
            {"år": "2025", "organisasjonsnummer": "811580082", "komnr": "1124"},
        )
    ]
    with pytest.raises(ValueError, match="not in the 2025 melk CSV"):
        cells_from_ldirmelk(
            CSV, year=YEAR, select={"organisasjonsnummer": ["999999999"]}
        )


def test_source_lists_year_directories_only(tmp_path: Path) -> None:
    source = LdirMelkSource(http=ScriptedHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["2024", "2025"]
    mapped = map_harvested_record(source.fetch_dataset(refs[-1]))
    assert mapped.title == "Leveranser til meieri i landbruket 2025"
    assert mapped.publisher_name == "Landbruksdirektoratet"
    assert mapped.access_path == CSV_URL
    assert mapped.license is None


def test_fetch_stores_national_totals_not_every_farm(tmp_path: Path) -> None:
    http = ScriptedHttp()
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, LdirMelkSource(http=http), limit=1, offset=1)
    indexed = index_dataset(registry, "ldirmelk:2025", http=http, catalogues={})
    assert indexed["fields"] == 5
    assert registry.get_capability("ldirmelk:2025")["capability"] == "observations"

    result = fetch_observations(registry, "ldirmelk:2025", table_id="2025", http=http)
    assert result.request_url == CSV_URL
    assert result.counts.listed == 2
    assert result.sample == [
        {"measure": "kumelk_liter", "value": 955123, "dimensions": {"år": "2025"}},
        {"measure": "geitemelk_liter", "value": 1200, "dimensions": {"år": "2025"}},
    ]
    assert registry.get_capability("ldirmelk:2025")["verified_sample_count"] == 2
    schemes = [
        row["scheme"]
        for row in registry.conn.execute(
            "SELECT scheme FROM resource_keys WHERE dataset_id = ?",
            ("ldirmelk:2025",),
        )
    ]
    assert schemes == ["brreg:orgnr"]
    registry.close()


def test_too_many_farms_is_refused_before_the_csv_is_needed(tmp_path: Path) -> None:
    http = ScriptedHttp()
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, LdirMelkSource(http=http), limit=1, offset=1)
    many = [f"{i:09d}" for i in range(FARM_LIMIT + 1)]
    with pytest.raises(SelectionTooLarge):
        fetch_observations(
            registry,
            "ldirmelk:2025",
            table_id="2025",
            select={"organisasjonsnummer": many},
            http=http,
        )
    assert CSV_URL not in http.gets or http.gets.count(CSV_URL) == 0
    registry.close()


def test_path_regex_captures_year() -> None:
    match = CSV_PATH.search(
        "/LandbruksdirektoratetGIT/opendata/refs/heads/main/"
        "datasets/leveransedata-melk/2025/dataset.csv"
    )
    assert match is not None
    assert match.group("year") == "2025"
