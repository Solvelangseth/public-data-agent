from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.cli import main
from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.search import (
    VARIABLES_UNKNOWN_REASON,
    decompose,
    keywords_from_payload,
    load_prompt_pack,
    run_search_pack,
    search,
    search_report,
    tokenize,
)
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"
STRANDSONE_ID = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
HELSEDATA_ID = "fixture:66c8fb46-da24-35a0-83b8-930cf175339d"
SPARSE_ID = "fixture:00000000-0000-4000-8000-000000000001"


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    return registry


def test_tokenize_is_casefold_and_keeps_norwegian_letters() -> None:
    assert tokenize("Forurensning i Oslo") == ["forurensning", "oslo"]
    assert tokenize("Åpne data") == ["åpne", "data"]


def test_tokenize_drops_short_norwegian_function_words() -> None:
    assert tokenize("Hvilke Oslo-bydeler er størst og hvilke vokser mest?") == [
        "hvilke",
        "oslo",
        "bydeler",
        "størst",
        "hvilke",
        "vokser",
        "mest",
    ]
    assert tokenize("boliger på vei for barn") == ["boliger", "vei", "barn"]
    assert tokenize("oslo i på for og bydeler") == ["oslo", "bydeler"]


def test_tokenize_maps_folketall_to_stored_befolkning() -> None:
    assert tokenize("folketall i oslo") == ["befolkning", "oslo"]
    assert tokenize("folketall for trondheim") == ["befolkning", "trondheim"]
    assert tokenize("befolkning på tromsø") == ["befolkning", "tromsø"]


def test_kraftsituasjonen_query_matches_stored_kraft_and_nve(tmp_path: Path) -> None:
    payloads = [
        {
            "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "uri": "https://example.org/elsertifikater",
            "type": "datasets",
            "title": {"nb": "Elsertifikater"},
            "description": {
                "nb": (
                    "Elsertifikater er en støtteordning for kraft produsert fra "
                    "fornybare energikilder."
                )
            },
            "publisher": {"name": "Norges vassdrags- og energidirektorat (nve)"},
            "harvest": {
                "modified": "2026-01-01T00:00:00Z",
                "firstHarvested": "2026-01-01T00:00:00Z",
            },
        },
        {
            "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "uri": "https://example.org/ortofoto-nve",
            "type": "datasets",
            "title": {"nb": "Ortofoto NVE Dirdalsåna 2026"},
            "description": {"nb": "flyfoto"},
            "keyword": [{"nb": "nve"}],
            "harvest": {
                "modified": "2026-01-01T00:00:00Z",
                "firstHarvested": "2026-01-01T00:00:00Z",
            },
        },
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    assert tokenize("kraftsituasjonen nve") == ["kraftsituasjonen", "nve"]
    hits = search(registry, "kraftsituasjonen nve")
    assert [hit.dataset_id for hit in hits] == [
        "fixture:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    ]
    tokens = {match.token for match in hits[0].matches}
    assert "kraft" in tokens
    assert "nve" in tokens
    assert "description matched kraft" in hits[0].why
    assert "nve" in hits[0].why
    report = search_report(registry, "kraftsituasjonen nve")
    assert report.coverage.missing == []
    assert "kraftsituasjonen" in report.coverage.covered
    assert "nve" in report.coverage.covered
    registry.close()


def test_folketall_query_matches_stored_befolkning_and_place(tmp_path: Path) -> None:
    payloads = [
        {
            "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "uri": "https://example.org/oslo-befolkning",
            "type": "datasets",
            "title": {"nb": "Oslo befolkning"},
            "description": {"nb": "statistikk"},
            "keyword": [{"nb": "oslo"}],
            "harvest": {
                "modified": "2026-01-01T00:00:00Z",
                "firstHarvested": "2026-01-01T00:00:00Z",
            },
        },
        {
            "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "uri": "https://example.org/ortofoto-oslo",
            "type": "datasets",
            "title": {"nb": "Ortofoto Oslo"},
            "description": {"nb": "flyfoto"},
            "keyword": [{"nb": "oslo"}],
            "harvest": {
                "modified": "2026-01-01T00:00:00Z",
                "firstHarvested": "2026-01-01T00:00:00Z",
            },
        },
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    hits = search(registry, "folketall i oslo")
    assert [hit.dataset_id for hit in hits] == [
        "fixture:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    ]
    tokens = {match.token for match in hits[0].matches}
    assert tokens == {"befolkning", "oslo"}
    assert "befolkning" in hits[0].why
    assert "oslo" in hits[0].why
    registry.close()


def test_title_match_ranks_above_description_match(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    hits = search(registry, "ssb")
    assert [hit.dataset_id for hit in hits] == [HELSEDATA_ID, STRANDSONE_ID]
    assert hits[0].relevance == 10
    assert hits[1].relevance == 2
    assert hits[0].matches[0].field == "title"
    assert hits[1].matches[0].field == "description"
    registry.close()


def test_keyword_match_is_explained_and_outranks_description(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    hits = search(registry, "friluftsliv")
    assert hits[0].dataset_id == STRANDSONE_ID
    assert hits[0].matches[0].field == "keyword"
    assert hits[0].matches[0].weight == 5
    assert "keyword matched friluftsliv" in hits[0].why
    registry.close()


def test_why_lists_each_matched_field_and_token(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    hits = search(registry, "strandsone")
    assert len(hits) == 1
    fields = {match.field for match in hits[0].matches}
    tokens = {match.token for match in hits[0].matches}
    assert "title" in fields
    assert tokens == {"strandsone"}
    assert "title matched strandsone" in hits[0].why
    registry.close()


def test_sparse_hit_keeps_nulls_and_does_not_invent_values(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    hits = search(registry, "sparse")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.dataset_id == SPARSE_ID
    assert hit.publisher is None
    assert hit.license is None
    assert hit.access_path is None
    assert hit.issued is None
    assert hit.modified is None
    assert hit.spatial == []
    assert hit.distributions == []
    assert hit.landing_pages == []
    assert hit.missing_fields["publisher"] == "absent from Resource Service dataset JSON"
    assert "license" in hit.missing_fields
    assert "access_path" in hit.missing_fields
    assert hit.variables == {"status": "unknown", "reason": VARIABLES_UNKNOWN_REASON}
    assert hit.source_native_uri == "https://example.org/datasets/sparse"
    registry.close()


def test_known_row_uses_stored_publisher_license_access_time_geo(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    hit = search(registry, "strandsone")[0]
    assert hit.publisher["name"] == "Statistisk sentralbyrå"
    assert hit.license == "http://publications.europa.eu/resource/authority/licence/NLOD_1_0"
    assert hit.access_path == "https://kart.ssb.no/"
    assert hit.issued == "2014-07-04"
    assert hit.temporal[0]["start"] == "2014-01-01T00:00:00Z"
    assert hit.spatial == []
    assert "spatial" in hit.missing_fields
    assert hit.variables["status"] == "unknown"
    assert "Friluftsliv" in hit.keywords
    registry.close()


def test_keywords_come_from_stored_payload_not_guessed() -> None:
    payload = json.loads((FIXTURES / "helsedata-ssb.json").read_text(encoding="utf-8"))
    keywords = keywords_from_payload(payload)
    assert "Health registry" in keywords
    assert "Helsedata" in keywords


def test_decompose_quoted_phrase_stays_one_requirement() -> None:
    reqs = decompose('pollution in "energy cooperatives" oslo')
    texts = [req.text for req in reqs]
    assert "energy cooperatives" in texts
    assert "oslo" in texts
    phrase = next(req for req in reqs if req.text == "energy cooperatives")
    assert phrase.tokens == ("energy", "cooperatives")


def test_two_token_and_drops_single_token_only_hits(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    and_hits = search(registry, "strandsone sparse")
    assert and_hits == []
    or_hits = search(registry, "strandsone sparse", decompose_query=False)
    assert {hit.dataset_id for hit in or_hits} == {STRANDSONE_ID, SPARSE_ID}
    registry.close()


def test_publisher_tokens_can_satisfy_a_requirement(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    hits = search(registry, "statistisk sentralbyrå")
    assert {hit.dataset_id for hit in hits} == {STRANDSONE_ID, HELSEDATA_ID}
    assert any(match.field == "publisher_name" for hit in hits for match in hit.matches)
    assert "requirements" in hits[0].why
    registry.close()


def test_single_token_publisher_is_ranked(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    hits = search(registry, "sentralbyrå")
    assert {hit.dataset_id for hit in hits} == {STRANDSONE_ID, HELSEDATA_ID}
    assert all(
        any(match.field == "publisher_name" and match.token == "sentralbyrå" for match in hit.matches)
        for hit in hits
    )
    registry.close()


def test_coverage_is_complete_when_and_hits_cover_every_requirement(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    report = search_report(registry, "statistisk sentralbyrå")
    assert report.coverage.requirement_coverage == 1.0
    assert "confidence" not in report.coverage.to_dict()
    assert report.coverage.missing == []
    assert report.follow_up is None
    registry.close()


def test_empty_and_triggers_follow_up_on_each_missing_requirement(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    report = search_report(registry, "strandsone sparse")
    assert report.follow_up is not None
    assert report.follow_up["ran"] is True
    assert set(report.follow_up["queries"]) == {"strandsone", "sparse"}
    assert {hit.dataset_id for hit in report.hits} == {STRANDSONE_ID, SPARSE_ID}
    assert report.coverage.requirement_coverage == 1.0
    assert "confidence" not in report.coverage.to_dict()
    registry.close()


def test_same_query_follow_up_is_skipped(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    report = search_report(registry, "qxzzzyyqq")
    assert report.hits == []
    assert report.coverage.requirement_coverage == 0.0
    assert "confidence" not in report.coverage.to_dict()
    assert report.follow_up is not None
    assert report.follow_up["ran"] is False
    registry.close()


def test_theme_code_participates_in_score_and_coverage(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    hits = search(registry, "HEAL")
    assert {hit.dataset_id for hit in hits} == {STRANDSONE_ID, HELSEDATA_ID}
    assert all(
        any(match.field == "theme" and match.token == "heal" for match in hit.matches)
        for hit in hits
    )
    report = search_report(registry, "HEAL")
    assert report.coverage.requirement_coverage == 1.0
    assert "confidence" not in report.coverage.to_dict()
    assert report.coverage.covered == ["heal"]
    registry.close()


def test_theme_label_query_counts_theme_strings_and_drops_title_flood(tmp_path: Path) -> None:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    payloads.append(
        {
            "id": "11111111-1111-4111-8111-111111111111",
            "uri": "https://example.org/health-title",
            "type": "datasets",
            "title": {"en": "Health title flood"},
            "description": {"en": "health"},
            "keyword": [{"en": "health"}],
            "harvest": {"modified": "2026-01-01T00:00:00Z", "firstHarvested": "2026-01-01T00:00:00Z"},
        }
    )
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    hits = search(registry, "Health")
    assert [hit.dataset_id for hit in hits] == [HELSEDATA_ID, STRANDSONE_ID]
    assert hits[0].relevance == 10
    assert hits[1].relevance == 5
    assert all(match.field == "theme" for hit in hits for match in hit.matches)
    registry.close()


def test_cli_search_uses_fixture_registry(tmp_path: Path, capsys) -> None:
    db = tmp_path / "registry.sqlite"
    assert main(["ingest", "--source", "fixture", "--fixtures", str(FIXTURES), "--db", str(db), "--quiet"]) == 0
    capsys.readouterr()
    assert main(["search", "strandsone", "--db", str(db), "--limit", "5"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "strandsone"
    assert payload["results"][0]["id"] == STRANDSONE_ID
    assert payload["results"][0]["why"]["matches"]
    assert payload["results"][0]["publisher"]["name"] == "Statistisk sentralbyrå"
    assert payload["coverage"]["requirement_coverage"] == 1.0
    assert "confidence" not in payload["coverage"]
    assert payload["coverage"]["covered"] == ["strandsone"]


def test_load_prompt_pack_rejects_gold_ids(tmp_path: Path) -> None:
    path = tmp_path / "pack.json"
    path.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "id": "bad",
                        "query": "folketall i oslo",
                        "expected": [{"dataset_id": "datanorge:x"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    try:
        load_prompt_pack(path)
    except ValueError as exc:
        assert "gold ids" in str(exc)
    else:
        raise AssertionError("expected gold id rejection")


def test_search_pack_emits_tokens_and_search_report_hits(tmp_path: Path, capsys) -> None:
    db = tmp_path / "registry.sqlite"
    questions = tmp_path / "pack.json"
    out = tmp_path / "report.json"
    questions.write_text(
        json.dumps(
            {
                "kind": "live_prompt_pack",
                "questions": [
                    {"id": "fx-lp", "query": "strandsone i"},
                    {"id": "fx-empty", "query": "qxzzzyyqq"},
                ],
            }
        ),
        encoding="utf-8",
    )
    assert main(["ingest", "--source", "fixture", "--fixtures", str(FIXTURES), "--db", str(db), "--quiet"]) == 0
    capsys.readouterr()
    registry = Registry(db)
    packed = run_search_pack(registry, load_prompt_pack(questions), limit=5)
    registry.close()
    by_id = {row["id"]: row for row in packed["questions"]}
    assert by_id["fx-lp"]["tokens"] == ["strandsone"]
    assert by_id["fx-lp"]["returned"] == 1
    assert by_id["fx-lp"]["hits"][0]["id"] == STRANDSONE_ID
    assert by_id["fx-lp"]["coverage"]["covered"]
    assert by_id["fx-empty"]["returned"] == 0
    assert main(
        [
            "search",
            "--questions",
            str(questions),
            "--out",
            str(out),
            "--db",
            str(db),
            "--limit",
            "5",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "live_prompt_pack_report"
    assert payload["question_count"] == 2
    assert payload["registry_rows"] == 3
    assert json.loads(out.read_text(encoding="utf-8"))["question_count"] == 2


def test_follow_up_ranks_uncovered_topic_above_place_title_flood(tmp_path: Path) -> None:
    payloads = [
        {
            "id": "11111111-1111-4111-8111-111111111111",
            "uri": "https://example.org/ortofoto-fosen-sør",
            "type": "datasets",
            "title": {"nb": "Ortofoto Fosen sør 2017"},
            "description": {"nb": "flyfoto"},
            "keyword": [{"nb": "fosen"}],
            "harvest": {
                "modified": "2026-01-01T00:00:00Z",
                "firstHarvested": "2026-01-01T00:00:00Z",
            },
        },
        {
            "id": "22222222-2222-4222-8222-222222222222",
            "uri": "https://example.org/ortofoto-indre-fosen",
            "type": "datasets",
            "title": {"nb": "Ortofoto Indre Fosen 2018"},
            "description": {"nb": "flyfoto"},
            "keyword": [{"nb": "fosen"}],
            "harvest": {
                "modified": "2026-01-01T00:00:00Z",
                "firstHarvested": "2026-01-01T00:00:00Z",
            },
        },
        {
            "id": "33333333-3333-4333-8333-333333333333",
            "uri": "https://example.org/ortofoto-fosen-2016",
            "type": "datasets",
            "title": {"nb": "Ortofoto Fosen 2016"},
            "description": {"nb": "flyfoto"},
            "keyword": [{"nb": "fosen"}],
            "harvest": {
                "modified": "2026-01-01T00:00:00Z",
                "firstHarvested": "2026-01-01T00:00:00Z",
            },
        },
        {
            "id": "44444444-4444-4444-8444-444444444444",
            "uri": "https://example.org/vindkraftverk",
            "type": "datasets",
            "title": {"nb": "Vindkraftverk"},
            "description": {"nb": "vindkraft"},
            "keyword": [],
            "harvest": {
                "modified": "2026-01-01T00:00:00Z",
                "firstHarvested": "2026-01-01T00:00:00Z",
            },
        },
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    topic_id = "fixture:44444444-4444-4444-8444-444444444444"
    report = search_report(registry, "vindkraft på fosen")
    ids = [hit.dataset_id for hit in report.hits]
    topic = next(hit for hit in report.hits if hit.dataset_id == topic_id)
    assert topic_id in ids[:2]
    assert {match.token for match in topic.matches} == {"vindkraft"}
    assert "description matched vindkraft" in topic.why
    assert any(
        (hit.title or "").startswith("Ortofoto")
        and {match.token for match in hit.matches} == {"fosen"}
        for hit in report.hits
    )
    assert not all((hit.title or "").startswith("Ortofoto") for hit in report.hits)
    registry.close()


def test_live_prompt_pack_queries_are_not_gold_queries() -> None:
    gold = json.loads(Path("data/benchmark_questions.json").read_text(encoding="utf-8"))
    pack = json.loads(Path("data/live_prompt_pack.json").read_text(encoding="utf-8"))
    gold_queries = {item["query"] for item in gold["questions"]}
    pack_queries = [item["query"] for item in pack["questions"]]
    pack_ids = [item["id"] for item in pack["questions"]]
    assert 15 <= len(pack_queries) <= 30
    assert not (set(pack_queries) & gold_queries)
    assert not (set(pack_ids) & {item["id"] for item in gold["questions"]})
    assert all("expected" not in item and "dataset_id" not in item for item in pack["questions"])
