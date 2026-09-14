"""Indexing what a resource contains, and searching it by contents.

A question naming a place misses a table that holds that place's code and never
says so in its title. These pin the reading of published metadata into a shape,
and the search that reaches a resource through it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.resource_index import (
    demote_breakdown_only,
    field_role,
    index_dataset,
    matches_subject,
    select_from_subjects,
    split_title,
    period_span,
    search_resources,
    shape_from_fhi,
    shape_from_jsonstat2,
    shape_from_pxweb,
)

# The published code lists a key is verified against. Real classifications, cut
# down: the point is that a code must be *in* the list, not shaped like it.
CATALOGUES = {
    "klass:131:kommune": {
        "0301": {"Oslo"}, "1103": {"Stavanger"}, "4601": {"Bergen"},
        "5001": {"Trondheim"}, "3401": {"Kongsvinger"},
    },
    "klass:104:fylke": {
        "01": {"Østfold"}, "02": {"Akershus"}, "03": {"Oslo"}, "04": {"Hedmark"},
        "11": {"Rogaland"}, "46": {"Vestland"}, "50": {"Trøndelag"},
    },
    # 030101 has been both, which is why a code keeps every name it was given.
    "klass:103:bydel": {
        "030101": {"Gamle Oslo", "Bygdøy-Frogner"},
        "030102": {"Grünerløkka", "Uranienborg-Majorstuen"},
        "030103": {"Sagene"}, "030104": {"St. Hanshaugen"},
    },
}

PXWEB_META = {
    "title": "08651: Byggekostnadsindeks for bustader",
    "variables": [
        {
            "code": "Region",
            "text": "region",
            "values": ["0301", "1103", "4601", "5001"],
            "valueTexts": ["Oslo", "Stavanger", "Bergen", "Trondheim"],
        },
        {
            "code": "ContentsCode",
            "text": "statistikkvariabel",
            "values": ["Byggindeks"],
            "valueTexts": ["Byggekostnadsindeks"],
        },
        {
            "code": "Tid",
            "text": "måned",
            "values": ["2019M01", "2024M12"],
            "valueTexts": ["2019M01", "2024M12"],
        },
    ],
}


def _registry(tmp_path: Path) -> Registry:
    registry = Registry(tmp_path / "r.sqlite")
    for did, title in (("ssbtable:08651", "08651: Byggekostnadsindeks for bustader"),
                       ("ssbtable:99999", "99999: Noe heilt anna")):
        registry.conn.execute(
            """
            INSERT INTO datasets (id, source_id, ingest_reason, source_name,
                source_endpoints_json, missing_fields_json, payload_hash,
                first_ingested_at, last_ingested_at, last_seen_at, last_changed_at, title)
            VALUES (?, 'ssbtable', 'test', 'S', '[]', '{}', 'h', 't', 't', 't', 't', ?)
            """,
            (did, title),
        )
    registry.conn.commit()
    return registry


def _indexed(tmp_path: Path) -> Registry:
    registry = _registry(tmp_path)
    fields, keys = shape_from_pxweb(PXWEB_META, CATALOGUES)
    registry.set_resource_shape("ssbtable:08651", fields, keys=keys)
    registry.set_capability("ssbtable:08651", {
        "capability": "observations", "period_start": "2019M01", "period_end": "2024M12",
    })
    return registry


# ---- reading a published shape ------------------------------------------


def test_pxweb_metadata_becomes_fields_values_and_keys() -> None:
    fields, keys = shape_from_pxweb(PXWEB_META, CATALOGUES)
    by_code = {f["field_code"]: f for f in fields}
    assert by_code["Region"]["field_role"] == "key"
    assert by_code["Tid"]["field_role"] == "period"
    assert by_code["ContentsCode"]["field_role"] == "measure"
    assert {v["value_label"] for v in by_code["Region"]["values"]} == {
        "Oslo", "Stavanger", "Bergen", "Trondheim",
    }
    assert [k["scheme"] for k in keys] == ["klass:131:kommune"]
    assert keys[0]["field_code"] == "Region"
    assert keys[0]["coverage_count"] == 4


def test_four_digit_years_are_a_period_not_a_geography_key() -> None:
    """A kommune code and a year are the same shape; claiming the wrong one
    offers a join key that matches nothing."""

    fields, keys = shape_from_pxweb({
        "variables": [{"code": "Tid", "text": "år",
                       "values": ["2019", "2020", "2021", "2022"],
                       "valueTexts": ["2019", "2020", "2021", "2022"]}]
    }, CATALOGUES)
    assert fields[0]["field_role"] == "period"
    assert keys == []


def test_a_scheme_is_not_claimed_from_one_coincidence() -> None:
    fields, keys = shape_from_pxweb({
        "variables": [{"code": "Kode", "text": "kode",
                       "values": ["0301", "abc", "def", "ghi", "jkl"],
                       "valueTexts": ["Oslo", "a", "b", "c", "d"]}]
    }, CATALOGUES)
    assert keys == []
    assert fields[0]["field_role"] == "attribute"


def test_codes_shaped_like_counties_but_not_counties_are_not_a_key() -> None:
    """Employer associations, transport types and livestock species all number
    themselves 01, 02, 03, and historical county codes do too, so the codes
    genuinely collide. The names do not: 01 is Østfold in one and Storfe in the
    other. A join on the wrong one would match "01" to "01" and produce
    nonsense carrying perfect provenance."""

    for label, values, texts in (
        ("landsforening", ["00", "01", "02", "03"],
         ["Alle", "Byggenæringen", "Norsk Industri", "Handel"]),
        ("type transport", ["01", "02", "03", "04"],
         ["Jernbane", "Sporveg", "Rutebil", "Drosje"]),
        ("husdyrslag", ["00", "01", "02", "03"],
         ["Alle husdyr", "Storfe", "Sau", "Gris"]),
    ):
        _, keys = shape_from_pxweb({
            "variables": [{"code": "X", "text": label, "values": values,
                           "valueTexts": texts}]
        }, CATALOGUES)
        assert keys == [], f"{label} was claimed as a key"


def test_the_same_codes_with_the_published_names_are_a_key() -> None:
    """The counterpart: identical codes, county names, and it is a key."""

    _, keys = shape_from_pxweb({
        "variables": [{"code": "Region", "text": "region",
                       "values": ["01", "02", "03", "04"],
                       "valueTexts": ["Østfold", "Akershus", "Oslo", "Hedmark"]}]
    }, CATALOGUES)
    assert [k["scheme"] for k in keys] == ["klass:104:fylke"]


def test_a_code_matches_any_name_it_has_carried(tmp_path: Path) -> None:
    """Codes are reused across reforms; a table may use either era's name."""

    for texts in (["Gamle Oslo", "Grünerløkka", "Sagene"],
                  ["Bygdøy-Frogner", "Uranienborg-Majorstuen", "Sagene"],
                  ["Bydel Gamle Oslo", "Bydel Grünerløkka", "Bydel Sagene"]):
        _, keys = shape_from_pxweb({
            "variables": [{"code": "GEO", "text": "bydel",
                           "values": ["030101", "030102", "030103"],
                           "valueTexts": texts}]
        }, CATALOGUES)
        assert [k["scheme"] for k in keys] == ["klass:103:bydel"], texts


def test_no_code_list_means_no_key_is_claimed() -> None:
    """A key that cannot be checked against what the publisher published is a
    guess, and a guessed join key is worse than none."""

    _, keys = shape_from_pxweb(PXWEB_META, None)
    assert keys == []


def test_fhi_dimensions_become_the_same_shape() -> None:
    fields, keys = shape_from_fhi([
        {"code": "GEO", "label": "Geografi", "categories": [
            {"value": "030101", "label": "Bydel Gamle Oslo", "children": [] },
            {"value": "030102", "label": "Bydel Grünerløkka", "children": []},
            {"value": "030103", "label": "Bydel Sagene", "children": []},
        ]},
        {"code": "AAR", "label": "År", "categories": [{"value": "2025", "label": "2025"}]},
    ], CATALOGUES)
    by_code = {f["field_code"]: f for f in fields}
    assert by_code["GEO"]["field_role"] == "key"
    assert by_code["AAR"]["field_role"] == "period"
    assert [k["scheme"] for k in keys] == ["klass:103:bydel"]


def test_a_truncated_field_still_reports_its_real_size() -> None:
    """Otherwise a field trimmed for the index reads as a smaller one."""

    values = [str(10000 + i) for i in range(500)]
    fields, _ = shape_from_pxweb({
        "variables": [{"code": "X", "text": "x", "values": values, "valueTexts": values}]
    }, CATALOGUES)
    assert fields[0]["value_count"] == 500
    assert len(fields[0]["values"]) == 400


def test_period_span_is_read_from_the_period_field() -> None:
    fields, _ = shape_from_pxweb(PXWEB_META)
    assert period_span(fields) == ("2019M01", "2024M12")
    assert period_span([{"field_role": "attribute", "values": []}]) == (None, None)


def test_field_role_names_the_time_field_whatever_it_is_called() -> None:
    assert field_role("AAR", []) == "period"
    assert field_role("Tid", []) == "period"
    assert field_role("year", []) == "period"


# ---- searching by contents ----------------------------------------------


def test_a_resource_is_found_by_a_place_its_title_never_mentions(tmp_path: Path) -> None:
    """The failure this exists to fix."""

    registry = _indexed(tmp_path)
    hits = search_resources(registry, "Stavanger")
    assert [h.dataset_id for h in hits] == ["ssbtable:08651"]
    assert "Stavanger" not in (hits[0].title or "")
    assert "Stavanger" in hits[0].why
    registry.close()


def test_an_exact_code_finds_the_resource_that_publishes_it(tmp_path: Path) -> None:
    registry = _indexed(tmp_path)
    hits = search_resources(registry, "0301")
    assert [h.dataset_id for h in hits] == ["ssbtable:08651"]
    assert "publishes code 0301" in hits[0].why
    registry.close()


def test_covering_more_of_the_question_outranks_matching_one_word_often(
    tmp_path: Path,
) -> None:
    registry = _indexed(tmp_path)
    hits = search_resources(registry, "Oslo Bergen")
    assert hits[0].dataset_id == "ssbtable:08651"
    assert set(hits[0].matched) >= {"oslo", "bergen"}
    registry.close()


def test_a_resource_that_cannot_return_data_is_not_offered(tmp_path: Path) -> None:
    registry = _indexed(tmp_path)
    registry.set_capability("ssbtable:08651", {"capability": "none"})
    assert search_resources(registry, "Stavanger") == []
    assert search_resources(registry, "Stavanger", capability=None)
    registry.close()


def test_a_resource_is_skipped_when_it_does_not_cover_the_period(tmp_path: Path) -> None:
    registry = _indexed(tmp_path)
    assert search_resources(registry, "Oslo", covers_period="2020")
    assert search_resources(registry, "Oslo", covers_period="1990") == []
    registry.close()


def test_an_unrecorded_period_does_not_exclude_a_resource(tmp_path: Path) -> None:
    """Absence of a period field is not evidence of failing to cover a year."""

    registry = _indexed(tmp_path)
    registry.set_capability("ssbtable:08651", {"capability": "observations"})
    assert search_resources(registry, "Oslo", covers_period="1990")
    registry.close()


def test_a_query_matching_nothing_returns_nothing(tmp_path: Path) -> None:
    registry = _indexed(tmp_path)
    assert search_resources(registry, "kraftproduksjon havbruk") == []
    registry.close()


# ---- subject versus breakdown -------------------------------------------

EMPLOYMENT_BREAKDOWN = "10975: Formål med eiga heimeside, etter sysselsetting og næring"
EMPLOYMENT_SUBJECT = "09174: Lønn, sysselsetting og produktivitet, etter næring 1970-2025"


def test_a_title_splits_into_subject_and_breakdown() -> None:
    subject, breakdown = split_title(EMPLOYMENT_SUBJECT)
    assert subject == "09174: Lønn, sysselsetting og produktivitet"
    assert breakdown.startswith("næring")
    # No separator means the whole title is the subject.
    assert split_title("09189: Makroøkonomiske hovedstørrelser 1970-2025")[1] == ""
    assert split_title(None) == ("", "")


def test_a_table_split_by_a_word_is_not_a_table_about_it() -> None:
    """The failure this exists for: a query naming employment reached
    e-commerce statistics that merely break down by employment size."""

    query = "sysselsetting etter næring"
    assert matches_subject(query, EMPLOYMENT_SUBJECT) is True
    assert matches_subject(query, EMPLOYMENT_BREAKDOWN) is False


def test_a_candidate_matched_on_something_other_than_its_title_is_not_judged() -> None:
    """An embedding match shares no word with the title; crediting or punishing
    it for that would rank on evidence the match never used."""

    assert matches_subject("kraftproduksjon", "05326: Elever i videregående") is None
    assert matches_subject("", EMPLOYMENT_SUBJECT) is None


def test_demoting_only_moves_breakdown_matches_down(tmp_path: Path) -> None:
    """It demotes and never promotes. An earlier version also lifted subject
    matches above candidates ranked on an embedding, which pushed correct
    answers off rank one and cost more ranking quality than it won in recall."""

    registry = _registry(tmp_path)
    registry.conn.execute("UPDATE datasets SET title = ? WHERE id = ?",
                          (EMPLOYMENT_BREAKDOWN, "ssbtable:08651"))
    registry.conn.execute("UPDATE datasets SET title = ? WHERE id = ?",
                          (EMPLOYMENT_SUBJECT, "ssbtable:99999"))
    registry.conn.commit()

    ranked = ["ssbtable:08651", "ssbtable:99999"]
    assert demote_breakdown_only(registry, ranked, "sysselsetting etter næring") == [
        "ssbtable:99999", "ssbtable:08651",
    ]
    # A query touching neither title leaves the order exactly as it was.
    assert demote_breakdown_only(registry, ranked, "kraftproduksjon") == ranked
    registry.close()


def test_reordering_never_reaches_past_the_head(tmp_path: Path) -> None:
    """Nothing the retriever placed far down may be lifted by a title rule."""

    registry = _registry(tmp_path)
    registry.conn.execute("UPDATE datasets SET title = ? WHERE id = ?",
                          (EMPLOYMENT_BREAKDOWN, "ssbtable:08651"))
    registry.conn.commit()
    ranked = ["x", "y", "ssbtable:08651"]
    assert demote_breakdown_only(registry, ranked, "sysselsetting", depth=2) == ranked
    registry.close()


# ---- coverage as a filter, not a ranking --------------------------------


def _covering_registry(tmp_path: Path) -> Registry:
    registry = _registry(tmp_path)
    # Two resources cover Bergen; one covers only Oslo.
    registry.set_resource_shape("ssbtable:08651", [
        {"field_code": "Region", "field_role": "key", "values": [
            {"value_code": "4601", "value_label": "Bergen"},
            {"value_code": "0301", "value_label": "Oslo"},
        ]},
    ])
    registry.set_resource_shape("ssbtable:99999", [
        {"field_code": "Region", "field_role": "key", "values": [
            {"value_code": "0301", "value_label": "Oslo"},
        ]},
    ])
    for did in ("ssbtable:08651", "ssbtable:99999"):
        registry.set_capability(did, {"capability": "observations"})
    return registry


def test_coverage_narrows_to_resources_holding_the_named_value(tmp_path: Path) -> None:
    from public_data_agent.resource_index import covering

    registry = _covering_registry(tmp_path)
    eligible, used = covering(registry, "hvor mange bor det i Bergen")
    assert eligible == {"ssbtable:08651"}
    assert used == ["bergen"]
    registry.close()


def test_two_named_places_narrow_to_what_covers_both(tmp_path: Path) -> None:
    from public_data_agent.resource_index import covering

    registry = _covering_registry(tmp_path)
    eligible, used = covering(registry, "Bergen og Oslo")
    assert eligible == {"ssbtable:08651"}
    assert set(used) == {"bergen", "oslo"}
    registry.close()


def test_a_query_naming_no_stored_value_is_not_a_constraint(tmp_path: Path) -> None:
    """A subject is not a value. "byggekostnader" names what a table is about,
    and constraining on it would filter to nothing rather than to everything."""

    from public_data_agent.resource_index import covering

    registry = _covering_registry(tmp_path)
    assert covering(registry, "byggekostnader") is None
    registry.close()


def test_coverage_lifts_without_demoting_below_the_ranking(tmp_path: Path) -> None:
    """The index is incomplete, so a resource missing a value there may simply
    not have been crawled yet; absence is not evidence of absence."""

    from public_data_agent.resource_index import rank_within_coverage

    registry = _covering_registry(tmp_path)
    ranked = ["ssbtable:99999", "ssbtable:08651"]
    assert rank_within_coverage(registry, ranked, "hvor mange bor det i Bergen") == [
        "ssbtable:08651", "ssbtable:99999",
    ]
    # Nothing recognised means the ranking is returned untouched.
    assert rank_within_coverage(registry, ranked, "byggekostnader") == ranked
    registry.close()


# ---- the shape a caller plans a fetch from -------------------------------


def test_shape_is_available_for_a_resource_nothing_has_fetched(tmp_path: Path) -> None:
    """`describe_observations` reports what has already been pulled, so it is
    empty for every resource a caller is about to fetch for the first time.
    Dimension names are source-defined and cannot be guessed from a title."""

    from public_data_agent.resource_index import resource_shape

    registry = _indexed(tmp_path)
    shape = resource_shape(registry, "ssbtable:08651")
    assert shape["indexed"] is True
    assert shape["capability"] == "observations"
    codes = {f["code"] for f in shape["fields"]}
    assert codes == {"Region", "ContentsCode", "Tid"}
    roles = {f["code"]: f["role"] for f in shape["fields"]}
    assert roles["Tid"] == "period"
    assert roles["ContentsCode"] == "measure"
    registry.close()


def test_a_period_field_shows_its_ends_and_others_show_a_head(tmp_path: Path) -> None:
    """A caller needs the range of a period and the shape of everything else."""

    from public_data_agent.resource_index import resource_shape

    registry = _indexed(tmp_path)
    fields = {f["code"]: f for f in resource_shape(registry, "ssbtable:08651")["fields"]}
    assert [v["code"] for v in fields["Tid"]["values"]] == ["2019M01", "2024M12"]
    assert len(fields["Region"]["values"]) == fields["Region"]["value_count"]
    registry.close()


def test_a_sampled_field_reports_how_many_values_it_really_has(tmp_path: Path) -> None:
    """A value absent from a sample is not absent from the resource, and a
    caller that assumed otherwise would rule out a valid selection."""

    from public_data_agent.resource_index import SAMPLE_VALUES, resource_shape

    registry = _registry(tmp_path)
    values = [{"value_code": f"c{i}", "value_label": f"v{i}"} for i in range(60)]
    registry.set_resource_shape("ssbtable:08651", [
        {"field_code": "Big", "field_role": "attribute", "values": values},
    ])
    registry.set_capability("ssbtable:08651", {"capability": "observations"})
    field = resource_shape(registry, "ssbtable:08651")["fields"][0]
    assert field["value_count"] == 60
    assert field["values_shown"] == SAMPLE_VALUES
    registry.close()


def test_an_unindexed_resource_says_so_rather_than_looking_empty(tmp_path: Path) -> None:
    from public_data_agent.resource_index import resource_shape

    registry = _registry(tmp_path)
    shape = resource_shape(registry, "ssbtable:99999")
    assert shape["indexed"] is False
    assert "not been recorded" in shape["reason"]
    registry.close()


def test_a_register_says_how_to_reach_one_subject(tmp_path: Path) -> None:
    """A register holds a million subjects. Filing each as its own dataset makes
    the catalogue the thing being searched rather than the index over it: search
    reads every dataset row per query, 1.8s at 13,744 rows and about 146s at a
    million."""

    from public_data_agent.resource_index import resource_shape, subject_url

    registry = _registry(tmp_path)
    registry.set_capability("ssbtable:08651", {
        "capability": "entities", "record_kind": "entity",
        "endpoint": "https://example.org/api/enheter",
        "subject_scheme": "brreg:orgnr",
        "subject_template": "https://example.org/api/enheter/{subject}",
        "subject_count": 1_100_000,
    })
    block = resource_shape(registry, "ssbtable:08651")["register"]
    assert block["subject_scheme"] == "brreg:orgnr"
    assert block["subject_count"] == 1_100_000
    assert subject_url(registry, "ssbtable:08651", "923609016").endswith("/923609016")
    registry.close()


def test_a_register_refuses_an_empty_subject(tmp_path: Path) -> None:
    """Its collection endpoint is millions of records and is not a fetch."""

    from public_data_agent.resource_index import subject_url

    registry = _registry(tmp_path)
    registry.set_capability("ssbtable:08651", {
        "capability": "entities", "subject_scheme": "brreg:orgnr",
        "subject_template": "https://example.org/api/enheter/{subject}",
        "subject_count": 1_100_000,
    })
    with pytest.raises(ValueError, match="needs a subject"):
        subject_url(registry, "ssbtable:08651", "  ")
    # A resource that is not a register says so rather than guessing a URL shape.
    registry.set_capability("ssbtable:99999", {"capability": "observations"})
    with pytest.raises(ValueError, match="not a register"):
        subject_url(registry, "ssbtable:99999", "923609016")
    registry.close()


def test_period_span_uses_year_labels_when_codes_are_positional() -> None:
    """Oslo PxWeb numbers years 0, 1, 2 and prints 1801 in the labels."""

    start, end = period_span(
        [
            {
                "field_code": "år",
                "field_role": "period",
                "values": [
                    {"value_code": "0", "value_label": "1801"},
                    {"value_code": "1", "value_label": "2026"},
                ],
            }
        ]
    )
    assert start == "1801"
    assert end == "2026"


def test_jsonstat2_metadata_becomes_fields_and_roles() -> None:
    fields, keys = shape_from_jsonstat2(
        {
            "id": ["Tid", "ContentsCode", "Region"],
            "role": {"time": ["Tid"], "metric": ["ContentsCode"]},
            "dimension": {
                "Tid": {
                    "label": "måned",
                    "category": {
                        "index": {"2026M07": 0},
                        "label": {"2026M07": "2026M07"},
                    },
                },
                "ContentsCode": {
                    "label": "statistikkvariabel",
                    "category": {
                        "index": {"Arbeidsstyrken": 0},
                        "label": {"Arbeidsstyrken": "Arbeidsstyrken (1000 personer)"},
                    },
                },
                "Region": {
                    "label": "region",
                    "category": {
                        "index": {"0301": 0, "1103": 1, "4601": 2, "5001": 3},
                        "label": {
                            "0301": "Oslo",
                            "1103": "Stavanger",
                            "4601": "Bergen",
                            "5001": "Trondheim",
                        },
                    },
                },
            },
        },
        CATALOGUES,
    )
    by_code = {field["field_code"]: field for field in fields}
    assert by_code["Tid"]["field_role"] == "period"
    assert by_code["ContentsCode"]["field_role"] == "measure"
    assert by_code["Region"]["field_role"] == "key"
    assert [key["scheme"] for key in keys] == ["klass:131:kommune"]


def test_index_dataset_reads_oslo_pxweb_metadata(tmp_path: Path) -> None:
    oslo_url = (
        "https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no/db1/"
        "Befolkning/Folkemengde/OK-BEF008.px"
    )
    meta = {
        "title": "BEF008: Folkemengden i Oslo",
        "variables": [
            {
                "code": "år",
                "text": "år",
                "values": ["0", "1"],
                "valueTexts": ["1801", "2026"],
            },
            {
                "code": "Statistikkvariabel",
                "text": "statistikkvariabel",
                "values": ["0"],
                "valueTexts": ["Folkemengden i alt (antall personer)"],
            },
        ],
    }

    class OsloHttp:
        def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
            if url.rstrip("/") == oslo_url:
                return JsonResponse(status=200, url=url, body=meta)
            raise AssertionError(url)

    registry = Registry(tmp_path / "r.sqlite")
    registry.ensure_observation_dataset(
        dataset_id="oslo:OK-BEF008.px",
        title="BEF008",
        publisher_name="Oslo kommune",
        access_path=oslo_url,
        license=None,
    )
    registry.conn.commit()
    indexed = index_dataset(
        registry, "oslo:OK-BEF008.px", http=OsloHttp(), catalogues=CATALOGUES
    )
    fields = {row["field_code"]: row for row in registry.resource_fields("oslo:OK-BEF008.px")}
    assert fields["år"]["field_role"] == "period"
    cap = registry.get_capability("oslo:OK-BEF008.px")
    assert cap["period_start"] == "1801"
    assert cap["period_end"] == "2026"
    assert indexed["fields"] >= 2
    registry.close()


def test_index_dataset_reads_ssbv2_jsonstat_metadata(tmp_path: Path) -> None:
    data_url = (
        "https://data.ssb.no/api/pxwebapi/v2/tables/13760/data"
        "?lang=no&outputFormat=json-stat2"
    )
    meta = {
        "id": ["Tid", "ContentsCode"],
        "role": {"time": ["Tid"], "metric": ["ContentsCode"]},
        "dimension": {
            "Tid": {
                "label": "måned",
                "category": {
                    "index": {"2006M01": 0, "2026M07": 1},
                    "label": {"2006M01": "2006M01", "2026M07": "2026M07"},
                },
            },
            "ContentsCode": {
                "label": "statistikkvariabel",
                "category": {
                    "index": {"Arbeidsstyrken": 0},
                    "label": {"Arbeidsstyrken": "Arbeidsstyrken (1000 personer)"},
                },
            },
        },
    }

    class V2Http:
        def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
            if "/metadata" in url:
                return JsonResponse(status=200, url=url, body=meta)
            raise AssertionError(url)

    registry = Registry(tmp_path / "r.sqlite")
    registry.ensure_observation_dataset(
        dataset_id="ssbv2:13760",
        title="13760",
        publisher_name="Statistisk sentralbyrå",
        access_path=data_url,
        license=None,
    )
    registry.conn.commit()
    index_dataset(registry, "ssbv2:13760", http=V2Http(), catalogues={})
    fields = {row["field_code"]: row for row in registry.resource_fields("ssbv2:13760")}
    assert fields["Tid"]["field_role"] == "period"
    assert fields["ContentsCode"]["field_role"] == "measure"
    cap = registry.get_capability("ssbv2:13760")
    assert cap["period_start"] == "2006M01"
    assert cap["period_end"] == "2026M07"
    registry.close()


def test_select_maps_klass_kommune_to_region_field(tmp_path: Path) -> None:
    registry = _indexed(tmp_path)
    select = select_from_subjects(registry, "ssbtable:08651", kommune="0301")
    assert select == {"Region": ["0301"]}
    select = select_from_subjects(
        registry, "ssbtable:08651", measure="Byggekostnadsindeks"
    )
    assert select == {"ContentsCode": ["Byggindeks"]}
    select = select_from_subjects(
        registry, "ssbtable:08651", select={"klass:131:kommune": ["1103"]}
    )
    assert select == {"Region": ["1103"]}
    with pytest.raises(ValueError, match="klass:103:bydel"):
        select_from_subjects(registry, "ssbtable:08651", bydel="030101")
    with pytest.raises(ValueError, match="not a printed value"):
        select_from_subjects(registry, "ssbtable:08651", measure="not-a-measure")
    leftover = select_from_subjects(
        registry, "ssbtable:99999", kommune="0301"
    )
    assert leftover == {"kommune": ["0301"]}
    registry.close()
