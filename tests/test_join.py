from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.cli import main
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.join import join_bydel_population
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource
from public_data_agent.ssb_klass import cells_from_klass
from public_data_agent.ssb_pxweb import (
    bydel_codes_from_meta,
    cells_from_jsonstat_coded,
    i_alt_age_selection,
    is_ssb_pxweb_url,
)

FIXTURES = Path(__file__).parent / "fixtures"
STRANDSONE_ID = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
KLASS_URL = "https://data.ssb.no/api/klass/v1/versions/1168.json"
SSB_URL = "https://data.ssb.no/api/v0/no/table/11763"

KLASS_PAYLOAD = {
    "name": "Bydelsinndeling 2020",
    "id": 1168,
    "classificationItems": [
        {"code": "030101", "name": "Gamle Oslo", "level": "1", "parentCode": ""},
        {"code": "030102", "name": "Grünerløkka", "level": "1", "parentCode": ""},
        {"code": "999999", "name": "Not in SSB table", "level": "1", "parentCode": ""},
    ],
}

SSB_META = {
    "title": "11763: Folkemengde 31.12.",
    "variables": [
        {
            "code": "KOKalder0000",
            "text": "alder",
            "values": ["000", "F000-120"],
            "valueTexts": ["0 år", "I alt"],
        },
        {
            "code": "KOKbydelsregion0000",
            "text": "region",
            "values": ["EAB", "030101", "030102", "888888"],
            "valueTexts": ["Alle bydeler i Oslo", "Gamle Oslo", "Grünerløkka", "Unknown"],
        },
        {"code": "ContentsCode", "text": "statistikkvariabel", "values": ["KOSpersoner0000"], "valueTexts": ["Personer (antall)"]},
        {"code": "Tid", "text": "år", "values": ["2024", "2025"], "valueTexts": ["2024", "2025"], "time": True},
    ],
}

SSB_JSONSTAT = {
    "label": "11763: Folkemengde 31.12.",
    "source": "Statistisk sentralbyrå",
    "id": ["KOKalder0000", "KOKbydelsregion0000", "ContentsCode", "Tid"],
    "size": [1, 2, 1, 1],
    "value": [64920, 67039],
    "dimension": {
        "KOKalder0000": {"category": {"index": {"F000-120": 0}, "label": {"F000-120": "I alt"}}},
        "KOKbydelsregion0000": {
            "category": {
                "index": {"030101": 0, "030102": 1},
                "label": {"030101": "Gamle Oslo", "030102": "Grünerløkka"},
            }
        },
        "ContentsCode": {"category": {"index": {"KOSpersoner0000": 0}, "label": {"KOSpersoner0000": "Personer (antall)"}}},
        "Tid": {"category": {"index": {"2025": 0}, "label": {"2025": "2025"}}},
    },
}


class JoinHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == KLASS_URL:
            return JsonResponse(status=200, url=url, body=KLASS_PAYLOAD)
        if url == SSB_URL:
            return JsonResponse(status=200, url=url, body=SSB_META)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        if url != SSB_URL:
            raise AssertionError(f"unexpected POST {url}")
        region = next(item for item in body["query"] if item["code"] == "KOKbydelsregion0000")
        assert "030101" in region["selection"]["values"]
        assert "EAB" not in region["selection"]["values"]
        age = next(item for item in body["query"] if item["code"] == "KOKalder0000")
        assert age["selection"]["values"] == ["F000-120"]
        return JsonResponse(status=200, url=url, body=SSB_JSONSTAT)


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?",
        (KLASS_URL, STRANDSONE_ID),
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


def test_ssb_meta_keeps_only_six_digit_bydel_codes() -> None:
    code, values = bydel_codes_from_meta(SSB_META)
    assert code == "KOKbydelsregion0000"
    assert values == ["030101", "030102", "888888"]
    assert i_alt_age_selection(SSB_META) == ("KOKalder0000", "F000-120")
    assert is_ssb_pxweb_url(SSB_URL)
    assert not is_ssb_pxweb_url(KLASS_URL)


def test_jsonstat_keeps_region_codes() -> None:
    cells = cells_from_jsonstat_coded(SSB_JSONSTAT)
    assert [cell.codes["KOKbydelsregion0000"] for cell in cells] == ["030101", "030102"]
    assert [cell.value for cell in cells] == [64920, 67039]
    assert cells[0].measure == "Personer (antall)"


def test_klass_cells_are_not_a_metric() -> None:
    cells = cells_from_klass(KLASS_PAYLOAD)
    assert cells[0][2]["code"] == "030101"
    assert cells[0][1] == "Gamle Oslo"


def test_join_on_exact_bydel_code_and_leaves_harvest_untouched(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    before = _harvest_bytes(registry)
    enrich_before = registry.enrichment_count()
    result = join_bydel_population(
        registry,
        klass_dataset_id=STRANDSONE_ID,
        ssb_table="11763",
        year=2025,
        http=JoinHttp(),
    )
    assert result.left_http_status == 200
    assert result.right_http_status == 200
    assert result.join_key == "bydel_code"
    assert result.counts.listed == 2
    assert result.counts.inserted == 2
    assert registry.joined_row_count() == 2
    stored_11763 = registry.list_observations("ssb:11763")
    assert len(stored_11763) == 2
    assert registry.observation_count() == 5
    grunnerlokka = next(
        row
        for row in stored_11763
        if json.loads(row["dimensions_json"])["bydel_code"] == "030102"
    )
    assert json.loads(grunnerlokka["value_json"]) == 67039
    assert json.loads(grunnerlokka["dimensions_json"])["region"] == "Grünerløkka"
    assert json.loads(grunnerlokka["dimensions_json"])["år"] == "2025"
    assert grunnerlokka["request_url"] == SSB_URL
    assert grunnerlokka["http_status"] == 200
    assert grunnerlokka["publisher_name"] == "Statistisk sentralbyrå"
    assert grunnerlokka["license"] is None
    assert grunnerlokka["access_path"] == SSB_URL
    assert _harvest_bytes(registry) == before
    assert registry.enrichment_count() == enrich_before
    assert registry.conn.execute(
        "SELECT COUNT(*) AS n FROM harvested_payloads"
    ).fetchone()["n"] == 3
    first = result.sample[0]
    assert first["join_key_value"] == "030101"
    assert first["population"] == 64920
    assert first["klass_name"] == "Gamle Oslo"
    assert first["ssb_region_label"] == "Gamle Oslo"
    assert "exact bydel_code 030101" in first["why_matched"]
    stored = registry.list_joined_rows()
    assert {json.loads(row["payload_json"])["population"] for row in stored} == {64920, 67039}
    assert all(row["left_request_url"] == KLASS_URL for row in stored)
    assert all(row["right_request_url"] == SSB_URL for row in stored)
    second = join_bydel_population(
        registry,
        klass_dataset_id=STRANDSONE_ID,
        ssb_table="11763",
        year=2025,
        http=JoinHttp(),
    )
    assert second.counts.unchanged == 2
    assert second.counts.inserted == 0
    assert registry.joined_row_count() == 2
    registry.close()


def test_cli_join_writes_proof(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "registry.sqlite"
    out = tmp_path / "join_proof.json"
    registry.close()

    from public_data_agent import fetch as fetch_mod
    from public_data_agent import ssb_pxweb as ssb_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: JoinHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: JoinHttp())
    assert (
        main(
            [
                "join",
                "--dataset",
                STRANDSONE_ID,
                "--table",
                "11763",
                "--year",
                "2025",
                "--db",
                str(db),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["join_key"] == "bydel_code"
    assert payload["counts"]["joined"] == 2
    assert payload["counts"]["datasets_unchanged"] == 4
    assert payload["sample"][0]["population"] == 64920
    assert payload["sources"]["left"]["http_status"] == 200
    assert payload["sources"]["right"]["http_status"] == 200


def test_classification_join_discovers_the_key_from_both_payloads() -> None:
    """The key is proved by overlap, not assumed from a code's shape."""

    from public_data_agent.ssb_pxweb import codes_matching_classification

    meta = {
        "variables": [
            {"code": "Region", "values": ["030101", "030102", "999999"]},
            {"code": "Tid", "values": ["2024", "2025"]},
        ]
    }
    dimension, values = codes_matching_classification(meta, {"030101", "030102"})
    assert dimension == "Region"
    assert values == ["030101", "030102"]
    # A value the classification does not store is never carried into the join.
    assert "999999" not in values


def test_classification_join_refuses_when_no_dimension_overlaps() -> None:
    from public_data_agent.ssb_pxweb import codes_matching_classification

    meta = {"variables": [{"code": "Region", "values": ["030101"]}, {"code": "Tid", "values": ["2025"]}]}
    assert codes_matching_classification(meta, {"1234567", "7654321"}) is None


# A health table splits one region across several breakdowns and measures.
# Keyed on (code, year) alone, all of them collapse onto one joined id.
FHI_T = "fhi:nokkel:670"
FHI_BASE = "https://statistikk-data.fhi.no/api/open/v1/nokkel/Table/670"
FHI_DIMENSIONS = {
    "dimensions": [
        {
            "code": "GEO",
            "label": "Geografi",
            "categories": [
                {"value": "030101", "label": "Bydel Gamle Oslo", "children": []},
                {"value": "030102", "label": "Bydel Grünerløkka", "children": []},
            ],
        },
        {"code": "AAR", "label": "År", "categories": [{"value": "2025", "label": "2025"}]},
        {
            "code": "TRINN",
            "label": "Klassetrinn",
            "categories": [{"value": "5", "label": "5. trinn"}, {"value": "8", "label": "8. trinn"}],
        },
        {
            "code": "MEASURE_TYPE",
            "label": "Måltall",
            "categories": [
                {"value": "TELLER", "label": "årlig antall"},
                {"value": "RATE", "label": "andel (prosent)"},
            ],
        },
    ]
}
FHI_JSONSTAT = {
    "class": "dataset",
    "label": "Leseferdighet",
    "id": ["GEO", "AAR", "TRINN", "MEASURE_TYPE"],
    "size": [2, 1, 2, 2],
    # Two regions x two school years x two measures; ":" is a withheld cell.
    "value": [103.3, 25.4, 90.1, 22.2, 88.0, 19.5, ":", 18.0],
    "role": {"metric": ["MEASURE_TYPE"]},
    "dimension": {
        "GEO": {"category": {"index": ["030101", "030102"],
                             "label": {"030101": "Bydel Gamle Oslo",
                                       "030102": "Bydel Grünerløkka"}}},
        "AAR": {"category": {"index": ["2025"], "label": {"2025": "2025"}}},
        "TRINN": {"category": {"index": ["5", "8"],
                               "label": {"5": "5. trinn", "8": "8. trinn"}}},
        "MEASURE_TYPE": {"category": {"index": ["TELLER", "RATE"],
                                      "label": {"TELLER": "årlig antall",
                                                "RATE": "andel (prosent)"}}},
    },
}


class FhiJoinHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == KLASS_URL:
            return JsonResponse(status=200, url=url, body=KLASS_PAYLOAD)
        if url == f"{FHI_BASE}/dimension?includeValues=true":
            return JsonResponse(status=200, url=url, body=FHI_DIMENSIONS)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        assert url == f"{FHI_BASE}/data"
        geo = next(d for d in body["dimensions"] if d["code"] == "GEO")
        # Only codes the classification also stores may be asked for.
        assert set(geo["values"]) == {"030101", "030102"}
        return JsonResponse(status=200, url=url, body=FHI_JSONSTAT)


def _fhi_join(tmp_path: Path):
    from public_data_agent.join import join_classification_to_table

    registry = _registry(tmp_path)
    result = join_classification_to_table(
        registry, klass_dataset_id=STRANDSONE_ID, ssb_table=FHI_T,
        year=2025, http=FhiJoinHttp(),
    )
    return registry, result


def test_fhi_table_joins_to_a_klass_classification(tmp_path: Path) -> None:
    registry, result = _fhi_join(tmp_path)
    assert result.right_dataset_id == "fhi:nokkel:670"
    assert result.right_publisher == "Folkehelseinstituttet"
    assert {row["bydel_code"] for row in result.rows} == {"030101", "030102"}
    # 999999 is in the classification but not the table, and must not appear.
    assert "999999" not in {row["bydel_code"] for row in result.rows}
    registry.close()


def test_every_joined_row_is_stored_not_just_the_last(tmp_path: Path) -> None:
    """Rows differing by breakdown or measure must not share an id."""

    registry, result = _fhi_join(tmp_path)
    stored = registry.conn.execute(
        "SELECT COUNT(*) FROM joined_rows WHERE right_dataset_id = ?", (FHI_T,)
    ).fetchone()[0]
    assert len(result.rows) == 8
    assert stored == 8
    registry.close()


def test_measure_alone_distinguishes_two_joined_rows(tmp_path: Path) -> None:
    from public_data_agent.join import _joined_id

    common = ("bydel_code", "030101", "2025", "left", "right", {"TRINN": "5. trinn"})
    assert _joined_id(*common, "årlig antall") != _joined_id(*common, "andel (prosent)")


def test_a_withheld_cell_is_not_stored_as_a_value(tmp_path: Path) -> None:
    """":" means the cell was suppressed; kept as-is it reads as data."""

    registry, result = _fhi_join(tmp_path)
    withheld = [row for row in result.rows if row.get("suppressed")]
    assert len(withheld) == 1
    assert withheld[0]["population"] is None
    assert withheld[0]["suppressed"] == ":"
    assert all(
        isinstance(row["population"], (int, float))
        for row in result.rows
        if not row.get("suppressed")
    )
    registry.close()


def test_joined_rows_carry_the_breakdown_that_distinguishes_them(tmp_path: Path) -> None:
    registry, result = _fhi_join(tmp_path)
    trinn = {row["dimensions"].get("TRINN") for row in result.rows}
    assert trinn == {"5. trinn", "8. trinn"}
    registry.close()


class BothTablesHttp:
    """Serves the classification and both tables, for a table-to-table join."""

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == KLASS_URL:
            return JsonResponse(status=200, url=url, body=KLASS_PAYLOAD)
        if url == SSB_URL:
            return JsonResponse(status=200, url=url, body=SSB_META)
        if url == f"{FHI_BASE}/dimension?includeValues=true":
            return JsonResponse(status=200, url=url, body=FHI_DIMENSIONS)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        if url == SSB_URL:
            return JsonResponse(status=200, url=url, body=SSB_JSONSTAT)
        if url == f"{FHI_BASE}/data":
            return JsonResponse(status=200, url=url, body=FHI_JSONSTAT)
        raise AssertionError(f"unexpected POST {url}")


def _table_join(tmp_path: Path, **kwargs):
    from public_data_agent.join import join_table_to_table

    registry = _registry(tmp_path)
    result = join_table_to_table(
        registry, left_table="11763", right_table=FHI_T,
        klass_dataset_id=STRANDSONE_ID, year=2025, http=BothTablesHttp(), **kwargs
    )
    return registry, result


def test_two_tables_join_through_a_shared_classification(tmp_path: Path) -> None:
    registry, result = _table_join(tmp_path)
    assert result.left_table == "11763"
    assert result.right_table == FHI_T
    # Both sides carry a value for every merged row.
    assert result.rows
    assert all(row["left_value"] is not None for row in result.rows)
    assert all(row["right_value"] is not None for row in result.rows)
    # Each row names where each half came from.
    assert {row["left_table"] for row in result.rows} == {"11763"}
    assert {row["right_table"] for row in result.rows} == {FHI_T}
    registry.close()


def test_a_merged_row_pairs_one_cell_from_each_side(tmp_path: Path) -> None:
    registry, result = _table_join(tmp_path)
    per_key: dict[str, int] = {}
    for row in result.rows:
        per_key[row["bydel_code"]] = per_key.get(row["bydel_code"], 0) + 1
    # Each region has one population cell. 030101 has four usable health cells
    # (two school years x two measures); 030102 has three, its fourth withheld.
    assert per_key["030101"] == 4
    assert per_key["030102"] == 3
    registry.close()


def test_a_withheld_cell_is_never_paired(tmp_path: Path) -> None:
    """Pairing a real value with a censored one invents a relationship."""

    registry, result = _table_join(tmp_path)
    assert result.withheld == 1
    assert all(row["right_value"] is not None for row in result.rows)
    registry.close()


def test_codes_on_only_one_side_are_reported_not_dropped(tmp_path: Path) -> None:
    registry, result = _table_join(tmp_path)
    # 999999 is in the classification but in neither table, so it is in neither
    # list; a code both tables print appears in neither either.
    assert "999999" not in result.left_only
    assert "999999" not in result.right_only
    assert isinstance(result.left_only, list)
    assert isinstance(result.right_only, list)
    registry.close()


def test_pairing_over_the_limit_refuses_and_says_what_to_narrow(tmp_path: Path) -> None:
    from public_data_agent.join import TableJoinTooLarge

    import pytest as _pytest

    with _pytest.raises(TableJoinTooLarge) as excinfo:
        _table_join(tmp_path, max_pairs=2)
    message = str(excinfo.value)
    assert "Narrow a breakdown or a measure" in message
    assert excinfo.value.worst
    assert excinfo.value.worst[0]["left"] * excinfo.value.worst[0]["right"] >= 1


def test_a_table_join_does_not_relabel_rows_an_earlier_join_wrote(tmp_path: Path) -> None:
    """The series tag separates dimension shapes, not callers.

    An observation id does not include the series, so writing the same cells
    under a different tag moves the existing rows rather than adding new ones,
    and a later read scoped to the original tag silently loses them.
    """

    from public_data_agent.join import JOIN_SERIES, join_classification_to_table

    registry = _registry(tmp_path)
    join_classification_to_table(
        registry, klass_dataset_id=STRANDSONE_ID, ssb_table="11763",
        year=2025, http=BothTablesHttp(),
    )
    before = len(registry.list_observations("ssb:11763", series=JOIN_SERIES))
    assert before > 0

    _table_join_on(registry)
    after = len(registry.list_observations("ssb:11763", series=JOIN_SERIES))
    assert after == before
    registry.close()


def _table_join_on(registry):
    from public_data_agent.join import join_table_to_table

    return join_table_to_table(
        registry, left_table="11763", right_table=FHI_T,
        klass_dataset_id=STRANDSONE_ID, year=2025, http=BothTablesHttp(),
    )
