from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.cli import main
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.mcp_server import TOOLS, call_tool
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"
STRANDSONE_ID = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
KLASS_URL = "https://data.ssb.no/api/klass/v1/versions/1168.json"
SSB_URL = "https://data.ssb.no/api/v0/no/table/11763"

KLASS_PAYLOAD = {
    "name": "Bydelsinndeling 2020",
    "id": 1168,
    "classificationItems": [
        {"code": "030101", "name": "Gamle Oslo", "level": "1", "parentCode": ""},
        {"code": "030102", "name": "Grünerløkka", "level": "1", "parentCode": ""},
        {"code": "999999", "name": "Not in SSB table", "level": "1", "parentCode": ""},
    ],
}

SSB_META = {
    "title": "11763: Folkemengde 31.12.",
    "variables": [
        {
            "code": "KOKalder0000",
            "text": "alder",
            "values": ["000", "F000-120"],
            "valueTexts": ["0 år", "I alt"],
        },
        {
            "code": "KOKbydelsregion0000",
            "text": "region",
            "values": ["EAB", "030101", "030102"],
            "valueTexts": ["Alle bydeler i Oslo", "Gamle Oslo", "Grünerløkka"],
        },
        {"code": "ContentsCode", "text": "statistikkvariabel", "values": ["KOSpersoner0000"], "valueTexts": ["Personer (antall)"]},
        {"code": "Tid", "text": "år", "values": ["2024", "2025"], "valueTexts": ["2024", "2025"], "time": True},
    ],
}

SSB_JSONSTAT = {
    "label": "11763: Folkemengde 31.12.",
    "source": "Statistisk sentralbyrå",
    "id": ["KOKalder0000", "KOKbydelsregion0000", "ContentsCode", "Tid"],
    "size": [1, 2, 1, 1],
    "value": [64920, 67039],
    "dimension": {
        "KOKalder0000": {"category": {"index": {"F000-120": 0}, "label": {"F000-120": "I alt"}}},
        "KOKbydelsregion0000": {
            "category": {
                "index": {"030101": 0, "030102": 1},
                "label": {"030101": "Gamle Oslo", "030102": "Grünerløkka"},
            }
        },
        "ContentsCode": {"category": {"index": {"KOSpersoner0000": 0}, "label": {"KOSpersoner0000": "Personer (antall)"}}},
        "Tid": {"category": {"index": {"2025": 0}, "label": {"2025": "2025"}}},
    },
}


def _jsonstat(year: str, values: list[int]) -> dict:
    return {
        "label": "11763: Folkemengde 31.12.",
        "source": "Statistisk sentralbyrå",
        "id": ["KOKalder0000", "KOKbydelsregion0000", "ContentsCode", "Tid"],
        "size": [1, 2, 1, 1],
        "value": values,
        "dimension": {
            "KOKalder0000": {"category": {"index": {"F000-120": 0}, "label": {"F000-120": "I alt"}}},
            "KOKbydelsregion0000": {
                "category": {
                    "index": {"030101": 0, "030102": 1},
                    "label": {"030101": "Gamle Oslo", "030102": "Grünerløkka"},
                }
            },
            "ContentsCode": {
                "category": {"index": {"KOSpersoner0000": 0}, "label": {"KOSpersoner0000": "Personer (antall)"}}
            },
            "Tid": {"category": {"index": {year: 0}, "label": {year: year}}},
        },
    }


class ScriptedHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == KLASS_URL:
            return JsonResponse(status=200, url=url, body=KLASS_PAYLOAD)
        if url == SSB_URL:
            return JsonResponse(status=200, url=url, body=SSB_META)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        if url != SSB_URL:
            raise AssertionError(f"unexpected POST {url}")
        tid = next((item for item in body["query"] if item["code"] == "Tid"), None)
        if tid is not None:
            year = tid["selection"]["values"][0]
            if year == "2024":
                return JsonResponse(status=200, url=url, body=_jsonstat("2024", [60000, 65000]))
            if year == "2025":
                return JsonResponse(status=200, url=url, body=_jsonstat("2025", [64920, 67039]))
        return JsonResponse(status=200, url=url, body=SSB_JSONSTAT)


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
    assert set(TOOLS) == {"search", "inspect", "ask", "fetch"}


def test_inspect_tool_returns_capability_and_null_license(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    payload = call_tool("inspect", {"dataset": STRANDSONE_ID, "db": db})
    assert payload["values_from"] == "registry"
    assert payload["metadata"]["fetch_supported"] is True
    assert "license" in payload["metadata"]


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

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
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

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
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
