"""Discovering a capability nothing had declared.

3,232 datasets on 2026-10-03 had an access_path a connector recognises and no
capability row, so the lane that returns data left them out although a fetch
would have worked. Some fetch branches store cells without recording a
capability -- kikommuner:3419 held an observation and no capability because of
it -- so discovery writes the record its own fetch demonstrated.

The evidence is the cells that came back: nothing is written when none did.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from public_data_agent.models import HarvestCounts
from public_data_agent.registry import Registry
from public_data_agent.verify import (
    demonstrated_capability,
    discoverable,
    record_evidence,
    verify_capabilities,
)


@dataclass
class _Result:
    counts: HarvestCounts


def _dataset(registry: Registry, dataset_id: str, access_path: str) -> None:
    registry.ensure_observation_dataset(
        dataset_id=dataset_id, title=dataset_id, publisher_name="p",
        access_path=access_path, license=None,
    )
    registry.conn.commit()


FETCHABLE = "https://api.kartverket.no/kommuneinfo/v1/kommuner/3419"


def _cell(
    registry: Registry,
    dataset_id: str,
    *,
    measure: str,
    value: object,
    dimensions: dict[str, object] | None = None,
) -> None:
    """Store one observation cell, the way a connector's fetch leaves it."""

    run_id = registry.start_fetch_run(
        dataset_id=dataset_id, table_id="t", request_url=FETCHABLE, request_method="TEST",
    )
    registry.upsert_observation(
        {
            "id": f"{dataset_id}:{measure}:{value}",
            "dataset_id": dataset_id,
            "table_id": "t",
            "measure": measure,
            "value": value,
            "dimensions": dimensions or {},
            "retrieved_at": "2026-10-16T00:00:00Z",
            "request_url": FETCHABLE,
            "http_status": 200,
        },
        run_id,
    )
    registry.conn.commit()


def test_a_dataset_a_connector_can_fetch_is_discoverable(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:known", FETCHABLE)
        assert [d for d, _s in discoverable(registry)] == ["fixture:known"]
    finally:
        registry.close()


def test_a_dataset_no_connector_recognises_is_not(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:unknown", "https://example.invalid/whatever")
        assert discoverable(registry) == []
    finally:
        registry.close()


def test_a_dataset_that_already_declares_a_capability_is_not_rediscovered(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:declared", FETCHABLE)
        registry.set_capability("fixture:declared", {
            "capability": "observations", "record_kind": "observation",
            "endpoint": FETCHABLE,
        })
        registry.conn.commit()
        assert discoverable(registry) == []
    finally:
        registry.close()


def test_the_sample_count_recorded_is_the_cells_that_came_back(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:got", FETCHABLE)
        _cell(registry, "fixture:got", measure="befolkning", value=4215, dimensions={"år": "2025"})
        counts = HarvestCounts()
        counts.listed = 7
        assert record_evidence(registry, "fixture:got", _Result(counts)) is True
        capability = registry.get_capability("fixture:got")
        assert capability["capability"] == "observations"
        assert capability["verified_sample_count"] == 7
        assert capability["verified_at"]
    finally:
        registry.close()


def test_nothing_is_declared_when_no_row_was_stored_to_read_it_from(tmp_path: Path) -> None:
    """A counter saying cells came back is not a capability.

    Writing `observations` from the count alone is what filed a Cristin
    institution as an observation source.
    """

    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:counted", FETCHABLE)
        counts = HarvestCounts()
        counts.listed = 7
        assert record_evidence(registry, "fixture:counted", _Result(counts)) is False
        assert registry.get_capability("fixture:counted") is None
    finally:
        registry.close()


def test_a_fetch_that_returned_nothing_declares_nothing(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:empty", FETCHABLE)
        # HTTP 200 and no cells is not evidence that a resource answers.
        assert record_evidence(registry, "fixture:empty", _Result(HarvestCounts())) is False
        assert registry.get_capability("fixture:empty") is None
    finally:
        registry.close()


def test_an_existing_capability_is_never_overwritten(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:has", FETCHABLE)
        registry.set_capability("fixture:has", {
            "capability": "lookup", "record_kind": "entity", "endpoint": FETCHABLE,
            "verified_at": "2026-01-01T00:00:00Z", "verified_sample_count": 1,
        })
        registry.conn.commit()
        counts = HarvestCounts()
        counts.listed = 99
        assert record_evidence(registry, "fixture:has", _Result(counts)) is False
        assert registry.get_capability("fixture:has")["capability"] == "lookup"
    finally:
        registry.close()


def test_discovery_counts_what_it_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:a", FETCHABLE)

        def _one_cell(*_args: object, **_kwargs: object) -> _Result:
            _cell(registry, "fixture:a", measure="antall", value=12, dimensions={"år": "2025"})
            counts = HarvestCounts()
            counts.listed = 1
            return _Result(counts)

        monkeypatch.setattr("public_data_agent.verify.fetch_observations", _one_cell)
        got = verify_capabilities(registry, discover=True)
        assert (got.probed, got.verified, got.declared) == (1, 1, 1)
        assert registry.get_capability("fixture:a")["verified_sample_count"] == 1
    finally:
        registry.close()


def test_without_discovery_an_undeclared_dataset_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:b", FETCHABLE)
        monkeypatch.setattr(
            "public_data_agent.verify.fetch_observations",
            lambda *a, **k: pytest.fail("nothing should be fetched"),
        )
        got = verify_capabilities(registry)
        assert (got.probed, got.declared) == (0, 0)
        assert registry.get_capability("fixture:b") is None
    finally:
        registry.close()


def test_a_capability_that_was_never_verified_gets_its_evidence(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:claimed", FETCHABLE)
        registry.set_capability("fixture:claimed", {
            "capability": "observations", "record_kind": "observation",
            "endpoint": FETCHABLE, "subject_scheme": "kommune",
            "subject_template": "https://example.invalid/{subject}",
        })
        registry.conn.commit()
        counts = HarvestCounts()
        counts.listed = 4
        assert record_evidence(registry, "fixture:claimed", _Result(counts)) is True
        capability = registry.get_capability("fixture:claimed")
        assert capability["verified_sample_count"] == 4
        # set_capability replaces every column, so the rest of the row has to
        # survive the merge or the endpoint and addressing are erased.
        assert capability["endpoint"] == FETCHABLE
        assert capability["subject_scheme"] == "kommune"
        assert capability["subject_template"] == "https://example.invalid/{subject}"
        assert capability["record_kind"] == "observation"
    finally:
        registry.close()


def test_a_lookup_capability_keeps_its_kind_when_verified(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:lookup", FETCHABLE)
        registry.set_capability("fixture:lookup", {
            "capability": "lookup", "record_kind": "entity", "endpoint": FETCHABLE,
        })
        registry.conn.commit()
        counts = HarvestCounts()
        counts.listed = 1
        assert record_evidence(registry, "fixture:lookup", _Result(counts)) is True
        capability = registry.get_capability("fixture:lookup")
        assert (capability["capability"], capability["record_kind"]) == ("lookup", "entity")
    finally:
        registry.close()


def test_a_resource_whose_cells_are_numbers_is_an_observation_source(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:num", FETCHABLE)
        _cell(registry, "fixture:num", measure="antall", value=42, dimensions={"år": "2025"})
        assert demonstrated_capability(registry, "fixture:num") == ("observations", "observation")
    finally:
        registry.close()


def test_a_number_published_as_a_string_is_still_an_observation(tmp_path: Path) -> None:
    """Norges Bank publishes the key policy rate as `"4.25"`.

    Reading that as a label would file an interest-rate series as a list of
    things.
    """

    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:str", FETCHABLE)
        _cell(
            registry, "fixture:str",
            measure="Key policy rate", value="4.25", dimensions={"TIME_PERIOD": "2026-08-13"},
        )
        assert demonstrated_capability(registry, "fixture:str") == ("observations", "observation")
    finally:
        registry.close()


def test_a_suppressed_cell_is_still_an_observation(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:supp", FETCHABLE)
        _cell(registry, "fixture:supp", measure="årlig antall", value=":", dimensions={"år": "2024"})
        assert demonstrated_capability(registry, "fixture:supp") == ("observations", "observation")
    finally:
        registry.close()


def test_a_code_addressed_label_is_a_lookup(tmp_path: Path) -> None:
    """`Bydelsinndeling 2020` returns `Gamle Oslo` for a code: a join key."""

    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:klass", FETCHABLE)
        _cell(
            registry, "fixture:klass",
            measure="Bydelsinndeling 2020", value="Gamle Oslo",
            dimensions={"code": "030101", "level": "1"},
        )
        assert demonstrated_capability(registry, "fixture:klass") == ("lookup", None)
    finally:
        registry.close()


def test_a_cell_measured_as_a_code_is_a_lookup(tmp_path: Path) -> None:
    """GREP files every curriculum code under the measure `kode`."""

    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:grep", FETCHABLE)
        _cell(
            registry, "fixture:grep",
            measure="kode", value="aarstrinn1",
            dimensions={"grep-type": "aarstrinn", "uri": "https://example.invalid/1"},
        )
        assert demonstrated_capability(registry, "fixture:grep") == ("lookup", None)
    finally:
        registry.close()


def test_a_named_thing_is_an_entity(tmp_path: Path) -> None:
    """crinst:1000 stores `institution_name = "AOF Haugaland"`, which is a thing."""

    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:org", FETCHABLE)
        _cell(
            registry, "fixture:org",
            measure="institution_name", value="AOF Haugaland",
            dimensions={"acronym": "AOFHAUGALA", "country": "NO"},
        )
        assert demonstrated_capability(registry, "fixture:org") == ("entities", "entity")
    finally:
        registry.close()


def test_a_named_thing_with_a_coordinate_is_a_feature(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:geo", FETCHABLE)
        _cell(
            registry, "fixture:geo",
            measure="Description", value="Vestside av bukt",
            dimensions={"Lat": "69.6", "Long": "18.9", "fid": "7", "Station": "Strandnot"},
        )
        assert demonstrated_capability(registry, "fixture:geo") == ("features", "feature")
    finally:
        registry.close()


def test_a_records_row_states_its_own_kind(tmp_path: Path) -> None:
    """A `records` row says what it is, so it decides and nothing is inferred."""

    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:rec", FETCHABLE)
        run_id = registry.start_fetch_run(
            dataset_id="fixture:rec", table_id="t",
            request_url=FETCHABLE, request_method="TEST",
        )
        registry.upsert_record(
            {
                "id": "fixture:rec:1",
                "dataset_id": "fixture:rec",
                "kind": "entity",
                "subject_scheme": "brreg:orgnr",
                "subject_code": "974760673",
                "subject_label": "Universitetet i Oslo",
                # What Enhetsregisteret actually prints about a company. A
                # register says what the thing is; a code list says only what
                # the code stands for, and that is the whole difference.
                "attributes": {
                    "organisasjonsform": "ORGL",
                    "naeringskode1": "85.421",
                    "antallAnsatte": 7325,
                    "forretningsadresse": "Problemveien 7, 0313 Oslo",
                },
                "retrieved_at": "2026-10-16T00:00:00Z",
                "request_url": FETCHABLE,
                "http_status": 200,
            },
            run_id,
        )
        registry.conn.commit()
        assert demonstrated_capability(registry, "fixture:rec") == ("entities", "entity")
    finally:
        registry.close()


def test_a_resource_with_nothing_stored_demonstrates_nothing(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:none", FETCHABLE)
        assert demonstrated_capability(registry, "fixture:none") is None
    finally:
        registry.close()


def test_klass_items_stay_a_lookup_once_they_are_records(tmp_path: Path) -> None:
    """A code list does not stop being a join key by moving table.

    Klass items are entity records now, and read by kind alone every
    classification would have turned into an entity source -- the same
    overclaim as before, one table along.
    """

    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:klass", FETCHABLE)
        run_id = registry.start_fetch_run(
            dataset_id="fixture:klass", table_id="klass:1168",
            request_url=FETCHABLE, request_method="TEST",
        )
        for code, name in (("030101", "Gamle Oslo"), ("030102", "Grünerløkka")):
            registry.upsert_record(
                {
                    "id": f"entity:fixture:klass:klass:1168:{code}",
                    "dataset_id": "fixture:klass",
                    "kind": "entity",
                    "subject_scheme": "klass:1168",
                    "subject_code": code,
                    "subject_label": name,
                    "attributes": {"classification": "Bydelsinndeling 2020", "level": "1"},
                    "retrieved_at": "2026-10-20T00:00:00Z",
                    "request_url": FETCHABLE,
                    "http_status": 200,
                },
                run_id,
            )
        registry.conn.commit()
        assert demonstrated_capability(registry, "fixture:klass") == ("lookup", "entity")
    finally:
        registry.close()


def test_a_code_and_a_label_and_nothing_else_is_a_lookup(tmp_path: Path) -> None:
    """The plainest vocabulary there is.

    `brreg:kommunenummer` stores 365 of these -- 0301 is Oslo and the row says
    no more than that -- and `brkommuner` declares itself a lookup for exactly
    this reason. Read as an entity source it would compete for questions about
    municipalities instead of being the key that answers them.
    """

    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:kommuner", FETCHABLE)
        run_id = registry.start_fetch_run(
            dataset_id="fixture:kommuner", table_id="kommuner",
            request_url=FETCHABLE, request_method="TEST",
        )
        for code, name in (("0301", "Oslo"), ("1103", "Stavanger")):
            registry.upsert_record(
                {
                    "id": f"entity:fixture:kommuner:{code}",
                    "dataset_id": "fixture:kommuner",
                    "kind": "entity",
                    "subject_scheme": "brreg:kommunenummer",
                    "subject_code": code,
                    "subject_label": name,
                    "attributes": {},
                    "retrieved_at": "2026-10-20T00:00:00Z",
                    "request_url": FETCHABLE,
                    "http_status": 200,
                },
                run_id,
            )
        registry.conn.commit()
        assert demonstrated_capability(registry, "fixture:kommuner") == ("lookup", "entity")
    finally:
        registry.close()


def test_codes_with_no_names_are_a_lookup(tmp_path: Path) -> None:
    """Udir's curriculum vocabularies, and why attributes are not the test.

    A GREP item carries a code, a status and a modified date, and its title
    sits in a nested object the connector does not copy. Judged by its
    attributes it would look like a register of things; judged by whether it
    ever names one, it is a list of codes.
    """

    registry = Registry(tmp_path / "r.sqlite")
    try:
        _dataset(registry, "fixture:grep", FETCHABLE)
        run_id = registry.start_fetch_run(
            dataset_id="fixture:grep", table_id="aarstrinn",
            request_url=FETCHABLE, request_method="TEST",
        )
        for code in ("aarstrinn1", "aarstrinn2"):
            registry.upsert_record(
                {
                    "id": f"entity:fixture:grep:{code}",
                    "dataset_id": "fixture:grep",
                    "kind": "entity",
                    "subject_scheme": "grep:aarstrinn",
                    "subject_code": code,
                    "subject_label": None,
                    "attributes": {
                        "status": "publisert",
                        "sist-endret": "2024-06-24T08:27:16",
                        "uri": f"http://psi.udir.no/laereplan/aarstrinn/{code}",
                    },
                    "retrieved_at": "2026-10-20T00:00:00Z",
                    "request_url": FETCHABLE,
                    "http_status": 200,
                },
                run_id,
            )
        registry.conn.commit()
        assert demonstrated_capability(registry, "fixture:grep") == ("lookup", "entity")
    finally:
        registry.close()
