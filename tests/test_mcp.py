from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.cli import main
from public_data_agent.harvest import harvest
from public_data_agent.mcp_server import TOOLS, call_tool
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource

from tests.test_ask import AskHttp, STRANDSONE_ID
from tests.test_join import JoinHttp, KLASS_URL

FIXTURES = Path(__file__).parent / "fixtures"


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    registry.conn.execute(
        "UPDATE datasets SET access_path = ?, title = ? WHERE id = ?",
        (KLASS_URL, "Bydelsinndeling Oslo", STRANDSONE_ID),
    )
    registry.conn.commit()
    return registry


def test_tools_are_search_ask_fetch() -> None:
    assert set(TOOLS) == {"search", "ask", "fetch"}


def test_search_tool_passes_through_stored_provenance(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    payload = call_tool("search", {"query": "strandsone", "db": db, "limit": 5})
    assert payload["tool"] == "search"
    assert payload["values_from"] == "registry"
    hit = payload["results"][0]
    assert hit["id"].startswith("fixture:")
    assert hit["why"]["summary"]
    assert "publisher" in hit
    assert "license" in hit
    assert hit["access"]["access_path"] is not None or hit["missing_fields"]
    assert "source_native_uri" in hit["original_link"]


def test_fetch_join_tool_reuses_existing_join(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    from public_data_agent import fetch as fetch_mod
    from public_data_agent import ssb_pxweb as ssb_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: JoinHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: JoinHttp())
    payload = call_tool(
        "fetch",
        {"dataset": STRANDSONE_ID, "table": "11763", "db": db, "year": 2025, "join": True},
    )
    assert payload["mode"] == "join"
    assert payload["sources"]["right"]["http_status"] == 200
    assert payload["sources"]["right"]["license"] is None
    assert payload["sample"][0]["population"] == 64920
    assert payload["sample"][0]["bydel_code"] == "030101"


def test_ask_tool_returns_sources_from_joined_cells(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    from public_data_agent import fetch as fetch_mod
    from public_data_agent import ssb_pxweb as ssb_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: AskHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: AskHttp())
    payload = call_tool(
        "ask",
        {
            "question": "Hvilke Oslo-bydeler er størst og hvilke vokser mest?",
            "dataset": STRANDSONE_ID,
            "table": "11763",
            "db": db,
            "year": 2025,
            "prior_year": 2024,
        },
    )
    assert payload["tool"] == "ask"
    assert payload["largest"][0]["population"] == 67039
    sources = payload["largest"][0]["sources"]
    assert sources[1]["dataset_id"] == "ssb:11763"
    assert sources[1]["license"] is None
    assert sources[1]["request_url"].endswith("/table/11763")


def test_cli_mcp_call_search_writes_proof(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "registry.sqlite"
    out = tmp_path / "mcp_proof.json"
    registry.close()
    assert (
        main(
            [
                "mcp",
                "--call",
                "search",
                "--query",
                "strandsone",
                "--db",
                str(db),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["tool"] == "search"
    assert payload["arguments"]["query"] == "strandsone"
    assert payload["results"][0]["why"]["summary"]


def test_unknown_tool_raises() -> None:
    try:
        call_tool("enrich", {})
    except ValueError as exc:
        assert "unknown tool" in str(exc)
    else:
        raise AssertionError("expected ValueError")
