from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.cli import main
from public_data_agent.fetch import (
    cells_from_jsonstat,
    fetch_observations,
    filter_held,
    pxweb_api_url,
)
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"
STRANDSONE_ID = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
PXWEB_UI = "https://statistikkbanken.oslo.kommune.no/statbank/pxweb/no/db1/"
TABLE_ID = "Befolkning/Folkemengde/OK-BEF008.px"

META = {
    "title": "BEF008",
    "variables": [
        {
            "code": "år",
            "values": ["49", "50"],
            "valueTexts": ["2020", "2021"],
            "time": True,
        },
        {"code": "geografisk område", "values": ["0"], "valueTexts": ["Oslo i alt"]},
        {
            "code": "Statistikkvariabel",
            "values": ["0"],
            "valueTexts": ["Folkemengden i alt (antall personer)"],
        },
    ],
}

JSONSTAT = {
    "label": "BEF008",
    "id": ["år", "geografisk område", "Statistikkvariabel"],
    "size": [2, 1, 1],
    "value": [693494, 697010],
    "role": {"metric": ["Statistikkvariabel"]},
    "dimension": {
        "år": {
            "category": {
                "index": {"49": 0, "50": 1},
                "label": {"49": "2020", "50": "2021"},
            }
        },
        "geografisk område": {
            "category": {"index": {"0": 0}, "label": {"0": "Oslo i alt"}}
        },
        "Statistikkvariabel": {
            "category": {
                "index": {"0": 0},
                "label": {"0": "Folkemengden i alt (antall personer)"},
            }
        },
    },
}


class ScriptedHttp:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict]] = []

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        return JsonResponse(status=200, url=url, body=META)

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        self.posts.append((url, body))
        return JsonResponse(status=200, url=url, body=JSONSTAT)


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?",
        (PXWEB_UI, STRANDSONE_ID),
    )
    registry.conn.commit()
    return registry


def _harvest_bytes(registry: Registry) -> list[tuple]:
    rows = registry.conn.execute(
        """
        SELECT d.id, d.publisher_name, d.license, p.payload_json
        FROM datasets d
        JOIN harvested_payloads p ON p.dataset_id = d.id
        ORDER BY d.id
        """
    ).fetchall()
    return [(row["id"], row["publisher_name"], row["license"], row["payload_json"]) for row in rows]


def test_pxweb_api_url_rewrites_ui_path() -> None:
    url = pxweb_api_url(PXWEB_UI, TABLE_ID)
    assert url == (
        "https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no/db1/"
        "Befolkning/Folkemengde/OK-BEF008.px"
    )


def test_cells_from_jsonstat_keep_source_values() -> None:
    cells = cells_from_jsonstat(JSONSTAT)
    assert cells == [
        (
            "Folkemengden i alt (antall personer)",
            693494,
            {"år": "2020", "geografisk område": "Oslo i alt"},
        ),
        (
            "Folkemengden i alt (antall personer)",
            697010,
            {"år": "2021", "geografisk område": "Oslo i alt"},
        ),
    ]


def test_filter_evidence_can_disprove_from_a_partial_sample() -> None:
    rows = [
        {"dimensions": {"municipalityNo": "5060", "year": "2024"}},
        {"dimensions": {"municipalityNo": "4617", "year": "2024"}},
    ]
    assert filter_held(
        rows, kommune="5060", from_year=2024, to_year=2024, complete=False
    ) is False


def test_partial_matching_sample_cannot_prove_the_whole_response() -> None:
    rows = [{"dimensions": {"municipalityNo": "5060", "year": "2024"}}]
    assert filter_held(
        rows, kommune="5060", from_year=2024, to_year=2024, complete=False
    ) is None


def test_complete_rows_must_prove_every_requested_filter_kind() -> None:
    only_year = [{"dimensions": {"year": "2024", "product": "salmon"}}]
    assert filter_held(
        only_year, kommune="5060", from_year=2024, to_year=2024, complete=True
    ) is None

    place_and_year = [
        {"dimensions": {"municipalityNo": "5060", "year": "2024"}}
    ]
    assert filter_held(
        place_and_year,
        kommune="5060",
        from_year=2024,
        to_year=2024,
        complete=True,
    ) is True


def test_unrelated_four_digit_dimension_does_not_disprove_place_filter() -> None:
    rows = [{
        "dimensions": {
            "municipalityNo": "5060",
            "productCode": "4617",
            "year": "2024",
        }
    }]
    assert filter_held(
        rows,
        kommune="5060",
        from_year=2024,
        to_year=2024,
        complete=True,
    ) is True


def test_subannual_period_proves_its_year() -> None:
    rows = [{"dimensions": {"municipalityNo": "5060", "Tid": "2024K1"}}]
    assert filter_held(
        rows,
        kommune="5060",
        from_year=2024,
        to_year=2024,
        complete=True,
    ) is True


def test_fetch_stores_observations_and_leaves_harvest_untouched(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    before = _harvest_bytes(registry)
    enrich_before = registry.enrichment_count()
    http = ScriptedHttp()
    result = fetch_observations(
        registry,
        STRANDSONE_ID,
        table_id=TABLE_ID,
        from_year=2020,
        to_year=2021,
        http=http,
    )
    assert result.http_status == 200
    assert result.counts.listed == 2
    assert result.counts.inserted == 2
    assert result.filter_applied is True
    assert registry.observation_count() == 2
    assert _harvest_bytes(registry) == before
    assert registry.enrichment_count() == enrich_before
    row = registry.list_observations(STRANDSONE_ID)[0]
    assert row["publisher_name"]
    assert row["request_url"].endswith(TABLE_ID)
    assert row["http_status"] == 200
    assert json.loads(row["value_json"]) in {693494, 697010}
    assert json.loads(row["dimensions_json"])["år"] in {"2020", "2021"}
    second = fetch_observations(
        registry,
        STRANDSONE_ID,
        table_id=TABLE_ID,
        from_year=2020,
        to_year=2021,
        http=ScriptedHttp(),
    )
    assert second.counts.unchanged == 2
    assert second.counts.inserted == 0
    assert registry.observation_count() == 2
    registry.close()


def test_cli_fetch_uses_scripted_path(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "registry.sqlite"
    registry.close()

    from public_data_agent import fetch as fetch_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    assert (
        main(
            [
                "fetch",
                "--dataset",
                STRANDSONE_ID,
                "--table",
                TABLE_ID,
                "--from-year",
                "2020",
                "--to-year",
                "2021",
                "--db",
                str(db),
            ]
        )
        == 0
    )
    opened = Registry(db)
    assert opened.observation_count() == 2
    opened.close()


def test_capability_does_not_promise_numbers_from_pages_that_have_none() -> None:
    """can_fetch_access_path says yes to all three of these; none returns a cell."""

    from public_data_agent.fetch import classify_access_path

    assert classify_access_path("https://data.ssb.no/api/v0/no/table/11763")["kind"] == "observations"
    assert classify_access_path("https://data.ssb.no/api/klass/v1/versions/1168.json")["kind"] == "lookup"
    # A bare host is a landing page, not an endpoint.
    assert classify_access_path("https://data-nsr.udir.no")["kind"] == "none"
    # Documentation describes data; it does not return it.
    assert classify_access_path(
        "https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/index.html"
    )["kind"] == "none"
    # Map tiles are imagery/geometry, not numeric cells.
    assert classify_access_path(
        "https://kart.miljodirektoratet.no/geoserver/villmarksnatur_svalbard/ows"
    )["kind"] == "none"
    assert classify_access_path(None)["kind"] == "none"


def test_selection_refuses_an_oversized_query_with_the_sizes_to_narrow() -> None:
    """An over-large request must name what to narrow, not return an opaque error."""

    from public_data_agent.fetch import SelectionTooLarge, _pxweb_query

    meta = {
        "variables": [
            {"code": "Region", "text": "region", "values": [str(i) for i in range(1000)]},
            {"code": "Alder", "text": "alder", "values": [str(i) for i in range(100)]},
            {"code": "Tid", "text": "år", "values": ["2024", "2025"], "time": True},
        ]
    }
    try:
        # 1000 x 100 x 2 = 200,000 cells, under the limit; force it over with a
        # low limit rather than inventing an implausibly large fixture table.
        _pxweb_query(meta, "Tid", ["2024", "2025"], table_id="T1", cell_limit=1000)
    except SelectionTooLarge as exc:
        assert exc.cells == 1000 * 100 * 2
        assert exc.limit == 1000
        assert {d["code"] for d in exc.dimensions} == {"Region", "Alder", "Tid"}
        assert "Region" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("an oversized selection must be refused before the request")


def test_selection_narrows_the_query_to_the_requested_slice() -> None:
    from public_data_agent.fetch import _pxweb_query

    meta = {
        "variables": [
            {"code": "Region", "text": "region", "values": [str(i) for i in range(1000)]},
            {"code": "Alder", "text": "alder", "values": [str(i) for i in range(100)]},
            {"code": "Tid", "text": "år", "values": ["2024", "2025"], "time": True},
        ]
    }
    query = _pxweb_query(meta, "Tid", ["2025"], select={"Region": ["7"], "Alder": ["3"]}, table_id="T1")
    picked = {item["code"]: item["selection"]["values"] for item in query["query"]}
    assert picked == {"Region": ["7"], "Alder": ["3"], "Tid": ["2025"]}


def test_selection_rejects_values_and_dimensions_the_table_does_not_have() -> None:
    """Silently dropping an unknown key would widen the query to every value."""

    from public_data_agent.fetch import _pxweb_query

    meta = {"variables": [{"code": "Region", "text": "region", "values": ["1", "2"]},
                          {"code": "Tid", "text": "år", "values": ["2025"], "time": True}]}
    for bad, needle in (
        ({"Kjonn": ["1"]}, "does not have"),
        ({"Region": ["999"]}, "not stored"),
    ):
        try:
            _pxweb_query(meta, "Tid", ["2025"], select=bad, table_id="T1")
        except ValueError as exc:
            assert needle in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"{bad} must be refused")


# json-stat2 permits `category.index` as an object or as a positional array.
# SSB emits the object, FHI the array; a decoder that reads only one of them
# rejects a conforming payload from a source it otherwise fully supports.
FHI_JSONSTAT = {
    "class": "dataset",
    "label": "Leseferdighet_utdann_3",
    "id": ["GEO", "MEASURE_TYPE"],
    "size": [3, 1],
    "value": [19.7019607843137, 25.4934210526316, 20.136186770428],
    "role": {"metric": ["MEASURE_TYPE"]},
    "dimension": {
        "GEO": {
            "category": {
                "index": ["0301", "030101", "030102"],
                "label": {
                    "0301": "Oslo",
                    "030101": "Bydel Gamle Oslo",
                    "030102": "Bydel Grünerløkka",
                },
            }
        },
        "MEASURE_TYPE": {
            "category": {"index": ["RATE"], "label": {"RATE": "andel (prosent)"}}
        },
    },
}


def test_jsonstat_index_accepts_both_conforming_forms() -> None:
    from public_data_agent.fetch import _jsonstat_index

    assert _jsonstat_index({"index": {"a": 0, "b": 1}}) == {"a": 0, "b": 1}
    assert _jsonstat_index({"index": ["a", "b"]}) == {"a": 0, "b": 1}
    assert _jsonstat_index({}) == {}


def test_cells_from_jsonstat_reads_array_index() -> None:
    cells = cells_from_jsonstat(FHI_JSONSTAT)
    assert cells == [
        ("andel (prosent)", 19.7019607843137, {"GEO": "Oslo"}),
        ("andel (prosent)", 25.4934210526316, {"GEO": "Bydel Gamle Oslo"}),
        ("andel (prosent)", 20.136186770428, {"GEO": "Bydel Grünerløkka"}),
    ]


def test_cells_from_jsonstat_coded_keeps_array_index_codes() -> None:
    """The codes are the join key, so an array index must still yield them."""

    from public_data_agent.ssb_pxweb import cells_from_jsonstat_coded

    cells = cells_from_jsonstat_coded(FHI_JSONSTAT)
    assert [cell.codes["GEO"] for cell in cells] == ["0301", "030101", "030102"]
    assert [cell.labels["GEO"] for cell in cells] == [
        "Oslo",
        "Bydel Gamle Oslo",
        "Bydel Grünerløkka",
    ]


# A table with two statistics variables: the same dimensions, different things
# measured. This is the ordinary shape of an SSB table, not an edge case.
TWO_STATISTICS = {
    "label": "08650: Byggekostnadsindeks for bustader i alt",
    "id": ["Arbeidstype", "ContentsCode", "Tid"],
    "size": [2, 2, 1],
    "value": [152.7, 4.3, 133.6, 3.9],
    "dimension": {
        "Arbeidstype": {"category": {"index": {"01": 0, "02": 1},
                                     "label": {"01": "I alt", "02": "Arbeidskraft"}}},
        "ContentsCode": {"category": {
            "index": {"Byggindeks": 0, "EndringForrAar": 1},
            "label": {"Byggindeks": "Byggekostnadsindeks",
                      "EndringForrAar": "Endring frå førre år (prosent)"}}},
        "Tid": {"category": {"index": {"2025": 0}, "label": {"2025": "2025"}}},
    },
}


def test_what_a_cell_measures_is_not_dropped() -> None:
    """ContentsCode was skipped, so the measure fell back to the table title and
    two cells differing only in which statistic they report became identical in
    (measure, dimensions) -- the key observations are unique on. Fetching 08650
    with both statistics returned six cells and stored three, and the survivors
    were percentage changes labelled as an index."""

    cells = cells_from_jsonstat(TWO_STATISTICS)
    assert len(cells) == 4
    measures = {measure for measure, _, _ in cells}
    assert measures == {"Byggekostnadsindeks", "Endring frå førre år (prosent)"}
    # The table title is not a measure of anything.
    assert not any(m.startswith("08650:") for m in measures)


def test_two_statistics_over_one_dimension_stay_distinct() -> None:
    """Identity is (measure, dimensions); if the measure collapses, so do the
    rows."""

    cells = cells_from_jsonstat(TWO_STATISTICS)
    identities = {(measure, tuple(sorted(dims.items()))) for measure, _, dims in cells}
    assert len(identities) == len(cells)
