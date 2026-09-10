from __future__ import annotations

from public_data_agent.mapping import map_harvested_record
from public_data_agent.sources.ssbtable import SsbTableSource

PAGE = {
    "language": "no",
    "tables": [
        {
            "id": "11763",
            "label": "11763: Folkemengde 31.12., etter alder, region og år",
            "updated": "2026-02-25T07:00:00Z",
            "firstPeriod": "2024",
            "lastPeriod": "2025",
            "variableNames": ["alder", "region", "år"],
            "source": "Statistisk sentralbyrå",
            "paths": [[{"id": "be", "label": "Befolkning"}]],
        }
    ],
    "page": {"pageNumber": 1, "pageSize": 500, "totalElements": 1, "totalPages": 1},
}


class ScriptedHttp:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get_json(self, url, headers=None):
        self.urls.append(url)
        return PAGE


def test_source_lists_tables_and_stops_at_the_last_page() -> None:
    http = ScriptedHttp()
    refs = SsbTableSource(http=http).list_dataset_refs()
    # Both catalogues list this table; one table is one dataset.
    assert [ref.source_native_id for ref in refs] == ["11763"]
    # Requesting a page past the end is a 404, so totalPages must bound the
    # loop -- once per catalogue, and no further.
    assert len(http.urls) == 2
    assert all("pageNumber=1" in url for url in http.urls)


def test_both_catalogues_are_paged_because_neither_is_complete() -> None:
    # The stable listing omits 245 tables the beta one has, and the beta one
    # omits 154 the registry holds from the stable one. Spot checks showed
    # tables from each still answering, so the union is the catalogue.
    class TwoCatalogues:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def get_json(self, url, headers=None):
            self.urls.append(url)
            table_id = "11763" if "v2-beta" not in url else "01301"
            return {
                "tables": [{**PAGE["tables"][0], "id": table_id}],
                "page": {"pageNumber": 1, "pageSize": 500, "totalElements": 1, "totalPages": 1},
            }

    http = TwoCatalogues()
    refs = SsbTableSource(http=http).list_dataset_refs()
    assert sorted(ref.source_native_id for ref in refs) == ["01301", "11763"]


def test_a_single_catalogue_url_is_still_accepted() -> None:
    http = ScriptedHttp()
    refs = SsbTableSource(http=http, catalogue_url="https://example.test/tables").list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["11763"]
    assert len(http.urls) == 1


def test_mapped_row_is_fetchable_and_keeps_harvested_variables() -> None:
    source = SsbTableSource(http=ScriptedHttp())
    ref = source.list_dataset_refs()[0]
    record = source.fetch_dataset(ref)
    assert record.payload["variables"] == ["alder", "region", "år"]

    mapped = map_harvested_record(record)
    assert mapped.access_path == "https://data.ssb.no/api/v0/no/table/11763"
    assert mapped.publisher_name == "Statistisk sentralbyrå"
    # Licence is genuinely unknown in this catalogue and must stay null.
    assert mapped.license is None
    assert mapped.temporal == [{"start": "2024", "end": "2025", "uri": None}]


def test_catalogue_rows_report_observation_capability() -> None:
    from public_data_agent.fetch import classify_access_path

    source = SsbTableSource(http=ScriptedHttp())
    mapped = map_harvested_record(source.fetch_dataset(source.list_dataset_refs()[0]))
    assert classify_access_path(mapped.access_path)["kind"] == "observations"
