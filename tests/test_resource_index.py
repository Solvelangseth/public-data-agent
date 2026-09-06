"""Indexing what a resource contains, and searching it by contents.

A question naming a place misses a table that holds that place's code and never
says so in its title. These pin the reading of published metadata into a shape,
and the search that reaches a resource through it.
"""

from __future__ import annotations

from pathlib import Path

from public_data_agent.registry import Registry
from public_data_agent.resource_index import (
    demote_breakdown_only,
    field_role,
    matches_subject,
    split_title,
    period_span,
    search_resources,
    shape_from_fhi,
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
