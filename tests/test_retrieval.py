"""The retrieval entry point: ranking, then the two-lane split.

Each behaviour pinned here was a measured gain against the fetchable gold set,
not a preference.
"""

from __future__ import annotations

from pathlib import Path

from public_data_agent.registry import Registry
from public_data_agent.retrieval import find

FETCHABLE = "https://data.ssb.no/api/v0/no/table/08650"
DESCRIPTIVE = "https://www.example.org/some/landing/page.html"


def _registry(tmp_path: Path) -> Registry:
    registry = Registry(tmp_path / "r.sqlite")
    rows = [
        # Titles use the query word verbatim, so the test isolates the lane split
        # and the subject ordering rather than depending on compound matching --
        # "Byggekostnadsindeks" does not tokenize to "byggekostnader".
        ("ssbtable:08650", "08650: Byggekostnader for bustader, etter arbeidstype", FETCHABLE),
        ("ssbtable:10975", "10975: Formål med eiga heimeside, etter byggekostnader", FETCHABLE),
        ("datanorge:x", "Byggekostnader i Norge", DESCRIPTIVE),
    ]
    for dataset_id, title, access in rows:
        registry.conn.execute(
            """
            INSERT INTO datasets (id, source_id, ingest_reason, source_name,
                source_endpoints_json, missing_fields_json, payload_hash,
                first_ingested_at, last_ingested_at, last_seen_at, last_changed_at,
                title, access_path)
            VALUES (?, 's', 'test', 'S', '[]', '{}', 'h', 't', 't', 't', 't', ?, ?)
            """,
            (dataset_id, title, access),
        )
    registry.conn.commit()
    return registry


def test_fetchable_and_descriptive_results_are_kept_apart(tmp_path: Path) -> None:
    """A record that cannot return a number does not belong in the lane whose
    job is returning numbers -- worth 6.9 points of recall when measured."""

    registry = _registry(tmp_path)
    found = find(registry, "byggekostnader")
    assert "datanorge:x" not in found.observations
    assert "datanorge:x" in found.catalogue
    assert "ssbtable:08650" in found.observations
    registry.close()


def test_a_table_about_the_query_outranks_one_split_by_it(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    found = find(registry, "byggekostnader")
    assert found.observations.index("ssbtable:08650") < found.observations.index("ssbtable:10975")
    registry.close()


def test_retrieval_works_without_an_embedding_provider(tmp_path: Path) -> None:
    """Degrading to lexical is a real loss, not an optimisation, so it is
    reported rather than hidden."""

    registry = _registry(tmp_path)
    found = find(registry, "byggekostnader", provider=None)
    assert found.observations
    assert any("semantic ranking skipped" in step for step in found.steps)
    registry.close()


def test_every_ranking_step_is_reported(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    found = find(registry, "byggekostnader")
    assert found.steps
    assert any("lexical search returned" in step for step in found.steps)
    assert any("fetchable" in step for step in found.steps)
    assert found.as_dict()["query"] == "byggekostnader"
    registry.close()


def test_the_limit_applies_to_each_lane(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    found = find(registry, "byggekostnader", limit=1)
    assert len(found.observations) <= 1
    assert len(found.catalogue) <= 1
    registry.close()


BRREG_ENTITY = "https://data.brreg.no/enhetsregisteret/api/enheter/923609016"


def test_a_company_is_retrievable_even_though_it_is_not_a_statistic(tmp_path: Path) -> None:
    """The lane split tested `== "observations"` because statistics were the
    only retrievable kind when it was written. Every entity, feature and
    document connector would have landed in the lane for records that cannot be
    retrieved at all -- a company endpoint that fetches fine filed as
    "describes data we cannot retrieve"."""

    registry = _registry(tmp_path)
    registry.conn.execute(
        """
        INSERT INTO datasets (id, source_id, ingest_reason, source_name,
            source_endpoints_json, missing_fields_json, payload_hash,
            first_ingested_at, last_ingested_at, last_seen_at, last_changed_at,
            title, access_path)
        VALUES ('brenheter:923609016', 'brenheter', 'test', 'B', '[]', '{}', 'h',
                't', 't', 't', 't', 'EQUINOR ASA', ?)
        """,
        (BRREG_ENTITY,),
    )
    registry.conn.commit()

    found = find(registry, "Equinor")
    assert "brenheter:923609016" in found.observations
    assert "brenheter:923609016" not in found.catalogue
    registry.close()


def test_a_code_list_is_not_offered_as_an_answer(tmp_path: Path) -> None:
    """A classification supplies join keys, never measures. Offering one as an
    answer is the substitution the readiness gate exists to refuse, so `lookup`
    stays outside the retrievable set."""

    from public_data_agent.fetch import is_retrievable

    assert is_retrievable("observations")
    assert is_retrievable("entities")
    assert is_retrievable("features")
    assert is_retrievable("documents")
    assert not is_retrievable("lookup")
    assert not is_retrievable("unverified")
    assert not is_retrievable("none")
    assert not is_retrievable(None)
