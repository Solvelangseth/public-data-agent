from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from public_data_agent.cli import main
from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.search import search_report
from public_data_agent.sources.fixture import FixtureSource
from public_data_agent.sources.user import (
    USER_SOURCE_ID,
    annotate_search_hits,
    ingest_user_file,
)

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLE_CSV = Path(__file__).resolve().parents[1] / "data" / "examples" / "user_bydel.csv"


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    return registry


def _harvest_bytes(registry: Registry) -> list[tuple]:
    rows = registry.conn.execute(
        """
        SELECT d.id, d.source_id, d.publisher_name, d.license, p.payload_json
        FROM datasets d
        JOIN harvested_payloads p ON p.dataset_id = d.id
        WHERE d.source_id != ?
        ORDER BY d.id
        """,
        (USER_SOURCE_ID,),
    ).fetchall()
    return [
        (row["id"], row["source_id"], row["publisher_name"], row["license"], row["payload_json"])
        for row in rows
    ]


def test_user_csv_is_searched_next_to_public_hits(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    before = _harvest_bytes(registry)
    enrich_before = registry.enrichment_count()
    ingest_user_file(registry, EXAMPLE_CSV)
    assert _harvest_bytes(registry) == before
    assert registry.enrichment_count() == enrich_before
    user_row = registry.get_dataset("user:user-bydel-notes")
    assert user_row is not None
    assert user_row["source_id"] == USER_SOURCE_ID
    assert user_row["publisher_name"] == "user"
    assert user_row["license"] is None
    report = search_report(registry, "strandsone oslo", limit=10, decompose_query=False)
    payload = report.to_dict()
    annotate_search_hits(payload["results"], registry)
    sources = {hit["id"]: hit for hit in payload["results"]}
    public = next(hit for hit in payload["results"] if not hit["user_supplied"])
    user = sources["user:user-bydel-notes"]
    assert public["source"] == "fixture"
    assert public["license"]
    assert user["user_supplied"] is True
    assert user["source"] == USER_SOURCE_ID
    assert user["publisher"]["name"] == "user"
    assert user["license"] is None
    assert user["why"]["summary"]
    registry.close()


def test_user_sqlite_maps_the_same_columns(tmp_path: Path) -> None:
    db = tmp_path / "user.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE notes (id TEXT, title TEXT, description TEXT, publisher TEXT, license TEXT, access_path TEXT, keywords TEXT)"
    )
    conn.execute(
        "INSERT INTO notes VALUES (?,?,?,?,?,?,?)",
        ("row-1", "strandsone notes", "user copy", "user", None, str(db), "strandsone"),
    )
    conn.commit()
    conn.close()
    registry = _registry(tmp_path)
    ingest_user_file(registry, db)
    payload = search_report(registry, "strandsone", limit=10).to_dict()
    annotate_search_hits(payload["results"], registry)
    user = next(hit for hit in payload["results"] if hit["id"] == "user:row-1")
    assert user["user_supplied"] is True
    assert user["source"] == USER_SOURCE_ID
    public = next(hit for hit in payload["results"] if hit["source"] == "fixture")
    assert public["id"].startswith("fixture:")
    registry.close()


def test_cli_keeps_user_hit_on_the_demo_query(tmp_path: Path, capsys) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "registry.sqlite"
    registry.close()
    assert (
        main(
            [
                "search",
                "Hvilke Oslo-bydeler er størst og hvilke vokser mest?",
                "--db",
                str(db),
                "--user-file",
                str(EXAMPLE_CSV),
                "--limit",
                "5",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert any(hit["user_supplied"] for hit in payload["results"])
    assert any(not hit["user_supplied"] for hit in payload["results"])


def test_cli_search_user_file(tmp_path: Path, capsys) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "registry.sqlite"
    registry.close()
    assert (
        main(
            [
                "search",
                "strandsone oslo",
                "--no-decompose",
                "--db",
                str(db),
                "--user-file",
                str(EXAMPLE_CSV),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    user = next(hit for hit in payload["results"] if hit["user_supplied"])
    public = next(hit for hit in payload["results"] if not hit["user_supplied"])
    assert user["id"] == "user:user-bydel-notes"
    assert public["source"] == "fixture"
