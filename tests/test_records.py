"""The resource index and the widened record store.

These pin the behaviour that earlier bugs cost us: identity wide enough that
records cannot overwrite each other, a suppression marker kept apart from a
value, and a capability that cannot be claimed without having seen a record.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.registry import Registry

RETRIEVED = {
    "retrieved_at": "2026-09-04T10:00:00Z",
    "request_url": "https://example.org/api/data",
    "http_status": 200,
}


def _registry(tmp_path: Path) -> Registry:
    registry = Registry(tmp_path / "r.sqlite")
    registry.conn.execute(
        """
        INSERT INTO datasets (
            id, source_id, ingest_reason, source_name, source_endpoints_json,
            missing_fields_json, payload_hash, first_ingested_at, last_ingested_at,
            last_seen_at, last_changed_at, title
        ) VALUES ('src:1', 'src', 'test', 'S', '[]', '{}', 'h', 't', 't', 't', 't',
                  'Byggekostnadsindeks')
        """
    )
    registry.conn.execute(
        """
        INSERT INTO fetch_runs (id, dataset_id, table_id, request_url, request_method,
                                started_at, status)
        VALUES (1, 'src:1', 't', 'https://example.org/api/data', 'GET', 't', 'completed')
        """
    )
    registry.conn.commit()
    return registry


def _record(**overrides):
    row = {
        "id": "r1",
        "dataset_id": "src:1",
        "kind": "observation",
        "subject_scheme": "klass:1168",
        "subject_code": "030102",
        "subject_label": "Grünerløkka",
        "period": "2025",
        "measure": "andel (prosent)",
        "value": 20.14,
        "attributes": {"TRINN": "5. trinn"},
        **RETRIEVED,
    }
    row.update(overrides)
    return row


# ---- records ------------------------------------------------------------


def test_a_record_round_trips_with_its_provenance(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    assert registry.upsert_record(_record(), 1) == "inserted"
    stored = registry.list_records("src:1")[0]
    assert stored["value_num"] == pytest.approx(20.14)
    assert stored["subject_code"] == "030102"
    assert stored["request_url"] == RETRIEVED["request_url"]
    assert stored["retrieved_at"] == RETRIEVED["retrieved_at"]
    assert stored["license"] is None
    registry.close()


def test_records_differing_only_by_attributes_do_not_collide(tmp_path: Path) -> None:
    """A resource that splits a subject several ways must not overwrite itself."""

    registry = _registry(tmp_path)
    registry.upsert_record(_record(id="r1", attributes={"TRINN": "5. trinn"}), 1)
    registry.upsert_record(_record(id="r2", attributes={"TRINN": "8. trinn"}), 1)
    registry.upsert_record(_record(id="r3", measure="årlig antall", value=103.3), 1)
    assert registry.record_count("src:1") == 3
    registry.close()


def test_every_record_kind_is_storable(tmp_path: Path) -> None:
    """A company and a building are not measures of anything."""

    registry = _registry(tmp_path)
    registry.upsert_record(
        _record(id="c1", kind="entity", subject_scheme="brreg:orgnr",
                subject_code="923609016", subject_label="EQUINOR ASA",
                measure=None, value=None, period=None,
                attributes={"organisasjonsform": "ASA", "ansatte": 21000}), 1
    )
    registry.upsert_record(
        _record(id="b1", kind="feature", subject_scheme="matrikkel:bygningsnummer",
                subject_code="80112233", measure=None, value=None, period=None,
                attributes={"bygningstype": "Enebolig"},
                geometry={"type": "Point", "coordinates": [10.75, 59.91]}), 1
    )
    kinds = {row["kind"] for row in registry.list_records("src:1")}
    assert kinds == {"entity", "feature"}
    feature = registry.list_records("src:1", kind="feature")[0]
    assert feature["geometry_json"] is not None
    assert feature["value_num"] is None
    registry.close()


def test_an_unknown_kind_is_refused(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    with pytest.raises(ValueError, match="unknown record kind"):
        registry.upsert_record(_record(kind="spreadsheet"), 1)
    registry.close()


def test_a_suppression_marker_never_becomes_a_number(tmp_path: Path) -> None:
    """":" stored as a value lets a later mean count a censored cell."""

    registry = _registry(tmp_path)
    registry.upsert_record(_record(value=":", suppressed=":"), 1)
    stored = registry.list_records("src:1")[0]
    assert stored["value_num"] is None
    assert stored["suppressed"] == ":"
    registry.close()


def test_records_are_readable_by_subject_across_datasets(tmp_path: Path) -> None:
    """"Everything known about this municipality" is the shape of the question."""

    registry = _registry(tmp_path)
    registry.upsert_record(_record(id="a"), 1)
    registry.upsert_record(_record(id="b", subject_code="030101"), 1)
    hits = registry.list_records(subject_scheme="klass:1168", subject_code="030102")
    assert [row["id"] for row in hits] == ["a"]
    registry.close()


def test_an_unchanged_record_is_reported_as_such(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.upsert_record(_record(), 1)
    assert registry.upsert_record(_record(), 1) == "unchanged"
    assert registry.upsert_record(_record(value=21.0), 1) == "updated"
    registry.close()


def test_a_changed_entity_label_is_not_mistaken_for_an_unchanged_record(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    entity = _record(kind="entity", measure=None, period=None, value=None)
    registry.upsert_record(entity, 1)
    assert registry.upsert_record({**entity, "subject_label": "Nytt navn AS"}, 1) == "updated"
    assert registry.list_records("src:1")[0]["subject_label"] == "Nytt navn AS"
    registry.close()


# ---- resource index -----------------------------------------------------


def test_a_capability_cannot_be_claimed_without_having_seen_a_record(tmp_path: Path) -> None:
    """Claiming reach from a URL pattern is the overreach `unverified` exists for."""

    registry = _registry(tmp_path)
    with pytest.raises(ValueError, match="verified_sample_count"):
        registry.set_capability(
            "src:1", {"capability": "observations", "verified_at": "2026-09-04T10:00:00Z"}
        )
    assert registry.set_capability("src:1", {"capability": "unverified"}) == "inserted"
    assert registry.get_capability("src:1")["capability"] == "unverified"
    registry.close()


def test_a_verified_capability_records_what_it_saw(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.set_capability("src:1", {
        "capability": "observations", "record_kind": "observation",
        "endpoint": "https://example.org/api/data", "request_method": "POST",
        "period_start": "2000", "period_end": "2025",
        "verified_at": "2026-09-04T10:00:00Z", "verified_sample_count": 12,
    })
    cap = registry.get_capability("src:1")
    assert cap["capability"] == "observations"
    assert cap["verified_sample_count"] == 12
    assert cap["period_end"] == "2025"
    assert registry.set_capability("src:1", {"capability": "none"}) == "updated"
    registry.close()


def test_a_resource_shape_is_replaced_not_merged(tmp_path: Path) -> None:
    """A field the source dropped must disappear, or a later query offers a
    selection the resource will refuse."""

    registry = _registry(tmp_path)
    registry.set_resource_shape("src:1", [
        {"field_code": "GEO", "field_role": "key",
         "values": [{"value_code": "030102", "value_label": "Grünerløkka"}]},
        {"field_code": "GONE", "field_role": "attribute", "values": ["x"]},
    ])
    assert {f["field_code"] for f in registry.resource_fields("src:1")} == {"GEO", "GONE"}
    registry.set_resource_shape("src:1", [
        {"field_code": "GEO", "field_role": "key", "values": ["030102"]},
    ])
    assert {f["field_code"] for f in registry.resource_fields("src:1")} == {"GEO"}
    assert registry.datasets_containing_value("x") == []
    registry.close()


def test_a_resource_is_found_by_a_code_its_title_never_mentions(tmp_path: Path) -> None:
    """This is the failure the index exists to fix: a question about a
    municipality missing a table whose name says nothing about one."""

    registry = _registry(tmp_path)
    registry.set_capability("src:1", {"capability": "observations"})
    registry.set_resource_shape(
        "src:1",
        [{"field_code": "Region", "field_role": "key",
          "values": [{"value_code": "0301", "value_label": "Oslo"}]}],
        keys=[{"scheme": "klass:131", "field_code": "Region", "coverage_count": 1}],
    )
    hits = registry.datasets_containing_value("0301")
    assert [h["dataset_id"] for h in hits] == ["src:1"]
    assert hits[0]["title"] == "Byggekostnadsindeks"
    assert hits[0]["capability"] == "observations"
    registry.close()


def test_resources_are_listable_by_identifier_scheme(tmp_path: Path) -> None:
    """"Which resources speak organisation numbers" must be a query, not a crawl."""

    registry = _registry(tmp_path)
    registry.set_resource_shape("src:1", [{"field_code": "orgnr", "field_role": "key"}],
                                keys=[{"scheme": "brreg:orgnr", "coverage_count": 4200}])
    hits = registry.datasets_with_key("brreg:orgnr")
    assert [h["dataset_id"] for h in hits] == ["src:1"]
    assert hits[0]["coverage_count"] == 4200
    assert registry.datasets_with_key("klass:1168") == []
    registry.close()


def test_one_scheme_on_two_fields_is_recorded_once(tmp_path: Path) -> None:
    """A resource can carry the same scheme on more than one field; the scheme
    belongs to the field that carries most of it, which is what a join uses."""

    registry = _registry(tmp_path)
    written = registry.set_resource_shape(
        "src:1",
        [{"field_code": "Region"}, {"field_code": "Bosted"}],
        keys=[
            {"scheme": "klass:131", "field_code": "Region", "coverage_count": 356},
            {"scheme": "klass:131", "field_code": "Bosted", "coverage_count": 12},
        ],
    )
    assert written["keys"] == 1
    hits = registry.datasets_with_key("klass:131")
    assert len(hits) == 1
    assert hits[0]["field_code"] == "Region"
    assert hits[0]["coverage_count"] == 356
    registry.close()


def test_a_table_title_is_refused_as_a_measure(tmp_path: Path) -> None:
    """A table's title is never what one of its cells measures. Storing it there
    gave two cells reporting different statistics one identity, and one silently
    overwrote the other -- 588,442 rows ended up labelled with a title, with
    percentage changes stored as index levels."""

    registry = _registry(tmp_path)
    row = {
        "id": "o1", "dataset_id": "src:1", "table_id": "t",
        "measure": "08650: Byggekostnadsindeks for bustader i alt, etter arbeidstype",
        "value": 4.3, "dimensions": {"Tid": "2025"}, **RETRIEVED,
    }
    with pytest.raises(ValueError, match="is a table title"):
        registry.upsert_observation(row, 1)

    # What the cell actually measures is accepted.
    row["measure"] = "Endring frå førre år (prosent)"
    assert registry.upsert_observation(row, 1) == "inserted"
    registry.close()


def test_the_guard_does_not_refuse_a_real_measure(tmp_path: Path) -> None:
    """It has to be narrow enough that nothing a publisher legitimately calls a
    measure trips it."""

    from public_data_agent.registry import _reject_title_as_measure

    for measure in ("Byggekostnadsindeks", "andel (prosent)", "Personer (antall)",
                    "Bydelsinndeling 2020", "forholdstall (Norge=100), standardisert",
                    "1000 tonn CO2-ekvivalenter"):
        _reject_title_as_measure(measure)
