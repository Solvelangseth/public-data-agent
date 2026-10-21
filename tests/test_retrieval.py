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


def test_a_verified_capability_beats_a_guess_from_the_url(tmp_path: Path) -> None:
    """`classify_access_path` reads a pattern; `resource_capability` records what
    a fetch actually returned. A register's stored access path is its collection
    endpoint, which the classifier rightly calls unfetchable -- a million
    companies is not one request -- while the resource is reachable by naming a
    subject. Classifying from the URL alone hid Enhetsregisteret from every
    query, including the literal word "Enhetsregisteret"."""

    from public_data_agent.fetch import classify_access_path

    collection = "https://data.brreg.no/enhetsregisteret/api/enheter"
    assert classify_access_path(collection)["kind"] == "none"

    registry = _registry(tmp_path)
    registry.conn.execute(
        """
        INSERT INTO datasets (id, source_id, ingest_reason, source_name,
            source_endpoints_json, missing_fields_json, payload_hash,
            first_ingested_at, last_ingested_at, last_seen_at, last_changed_at,
            title, access_path)
        VALUES ('brreg:enhetsregisteret', 'brreg', 't', 'B', '[]', '{}', 'h',
                't', 't', 't', 't', 'Enhetsregisteret', ?)
        """,
        (collection,),
    )
    registry.conn.commit()
    registry.set_capability("brreg:enhetsregisteret", {
        "capability": "entities", "record_kind": "entity", "endpoint": collection,
        "subject_scheme": "brreg:orgnr",
        "subject_template": collection + "/{subject}",
        "subject_count": 1_100_000,
    })

    found = find(registry, "Enhetsregisteret")
    assert "brreg:enhetsregisteret" in found.observations
    assert "brreg:enhetsregisteret" not in found.catalogue
    registry.close()


class _Rewriter:
    """A rewriter whose term finds the answer, but not in its first few hits.

    This is the shape of `regnskapstall aksjeselskap`: the rewrite lane ranked
    07371 sixth of its twenty alternatives, and the interleave was taking
    three.
    """

    name = "stub"

    def terms(self, query: str) -> list[str]:
        return ["avfall"]


def _many(tmp_path: Path) -> Registry:
    registry = _registry(tmp_path)
    # Three tables the rewritten term finds and the original query does not,
    # plus the one that answers. Lexical relevance orders them by how much of
    # the title the term accounts for, so the bare titles come first and the
    # answer is reachable only by taking enough of the lane's hits.
    for index in range(3):
        registry.conn.execute(
            """
            INSERT INTO datasets (id, source_id, ingest_reason, source_name,
                source_endpoints_json, missing_fields_json, payload_hash,
                first_ingested_at, last_ingested_at, last_seen_at, last_changed_at,
                title, access_path)
            VALUES (?, 's', 'test', 'S', '[]', '{}', 'h', 't', 't', 't', 't', ?, ?)
            """,
            (f"ssbtable:1{index:04d}", f"1{index:04d}: Avfall", FETCHABLE),
        )
    registry.conn.execute(
        """
        INSERT INTO datasets (id, source_id, ingest_reason, source_name,
            source_endpoints_json, missing_fields_json, payload_hash,
            first_ingested_at, last_ingested_at, last_seen_at, last_changed_at,
            title, access_path)
        VALUES (?, 's', 'test', 'S', '[]', '{}', 'h', 't', 't', 't', 't', ?, ?)
        """,
        ("ssbtable:answer", "Avfall og gjenvinning etter behandling i Noreg", FETCHABLE),
    )
    registry.conn.commit()
    return registry


def test_the_interleave_can_keep_more_of_the_rewrite_than_it_leads_with(tmp_path: Path) -> None:
    """How much head to keep and how many hits to insert are separate questions.

    One number answered both, and the second is where a retrieved answer was
    being discarded: the rewrite lane had it and three were taken. The lead
    and the take are independent now, and the take defaults to the lead so
    wiring them apart changed nothing by itself.
    """

    registry = _many(tmp_path)
    try:
        lane = find(registry, "avfall", depth=50).observations
        assert lane.index("ssbtable:answer") == 3, (
            "the fixture only tests the take if the answer is fourth in the "
            f"rewrite lane; it is at {lane.index('ssbtable:answer')}"
        )

        narrow = find(registry, "byggekostnader", rewriter=_Rewriter(), depth=50,
                      rewrite_take=1).observations
        wide = find(registry, "byggekostnader", rewriter=_Rewriter(), depth=50,
                    rewrite_take=4).observations
        # The original query never reaches it, so the take alone decides
        # whether the answer is in the result at all.
        assert "ssbtable:answer" not in narrow
        assert "ssbtable:answer" in wide
    finally:
        registry.close()


def test_the_working_list_can_outlive_the_output_depth(tmp_path: Path) -> None:
    """Fusing two lists and keeping D discards the deeper ranker's tail.

    `regnskapstall aksjeselskap` is ranked 41 and 42 by the semantic lane and
    appears in no fused list at all, because 15 lexical hits plus 50 semantic
    ones are cut to 50. The working list is what the ranking stages operate
    on; the output depth is a different question, and conflating them loses
    answers silently.
    """

    registry = _many(tmp_path)
    try:
        # With no provider the fusion does not run, so this pins the plumbing:
        # a working list longer than the depth must not truncate earlier.
        short = find(registry, "avfall", depth=2).observations
        long = find(registry, "avfall", depth=2, work_depth=10).observations
        assert len(short) <= 2
        assert len(long) >= len(short)
        assert "ssbtable:answer" in find(registry, "avfall", depth=10).observations
    finally:
        registry.close()
