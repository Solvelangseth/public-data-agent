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


def test_coverage_is_complete_when_and_hits_cover_every_requirement(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    report = search_report(registry, "statistisk sentralbyrå")
    assert report.coverage.confidence == 1.0
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
    assert report.coverage.confidence == 1.0
    registry.close()


def test_same_query_follow_up_is_skipped(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    report = search_report(registry, "qxzzzyyqq")
    assert report.hits == []
    assert report.coverage.confidence == 0.0
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
    assert report.coverage.confidence == 1.0
    assert report.coverage.covered == ["heal"]
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
    assert payload["coverage"]["confidence"] == 1.0
    assert payload["coverage"]["covered"] == ["strandsone"]
