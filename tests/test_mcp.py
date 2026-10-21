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
    assert set(TOOLS) == {
        "search", "inspect", "run_analysis", "export_artifact", "create_visualization", "get_provenance", "ask", "fetch"
    }


def test_inspect_tool_returns_capability_and_null_license(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    payload = call_tool("inspect", {"dataset": STRANDSONE_ID, "db": db})
    assert payload["values_from"] == "registry"
    assert payload["metadata"]["fetch_supported"] is True
    assert "license" in payload["metadata"]


def test_provenance_tool_returns_stored_metadata(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    payload = call_tool("get_provenance", {"dataset": STRANDSONE_ID, "db": db})
    assert payload["values_from"] == "registry"
    assert payload["observation_count"] == 0
    assert payload["metadata"]["access_path"] == KLASS_URL


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


def test_search_tool_marks_connector_capability_and_candidates(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    payload = call_tool("search", {"query": "strandsone", "db": db, "limit": 5})
    assert "connector" in payload["results"][0]
    assert payload["results"][0]["connector"]["fetch_supported"] is True
    assert payload["connector_candidates"] == []


def test_fetch_without_table_uses_the_dataset_native_id(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    native = registry.get_dataset(STRANDSONE_ID)["source_native_id"]
    registry.close()
    seen: dict[str, str] = {}

    def fake_fetch(reg, dataset_id, *, table_id, **kwargs):
        from public_data_agent.fetch import FetchResult
        from public_data_agent.models import HarvestCounts

        seen["table_id"] = table_id
        return FetchResult(
            dataset_id=dataset_id,
            table_id=table_id,
            request_url="https://example.test",
            http_status=200,
            counts=HarvestCounts(),
        )

    monkeypatch.setattr("public_data_agent.mcp_server.fetch_observations", fake_fetch)
    payload = call_tool("fetch", {"dataset": STRANDSONE_ID, "db": db})
    assert seen["table_id"] == native
    assert payload["table"] == native


def test_join_without_table_is_refused(tmp_path: Path) -> None:
    _registry(tmp_path).close()
    payload = call_tool(
        "fetch",
        {"dataset": STRANDSONE_ID, "join": True, "db": str(tmp_path / "registry.sqlite")},
    )
    assert payload["numbers_retrieved"] is False
    assert payload["error"]["code"] == "table_required"


def test_fetch_rejects_unregistered_access_path(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.conn.execute("UPDATE datasets SET access_path = ? WHERE id = ?", ("https://example.invalid/landing", STRANDSONE_ID))
    registry.conn.commit()
    registry.close()
    payload = call_tool("fetch", {"dataset": STRANDSONE_ID, "table": "11763", "db": db})
    assert payload["numbers_retrieved"] is False
    assert payload["error"]["code"] == "unsupported_access_path"


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


def test_call_tool_refuses_unknown_arguments_instead_of_dropping_them(tmp_path: Path) -> None:
    """A dropped filter turns "in 2025" into "in every year" and still says completed."""

    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    try:
        call_tool("run_analysis", {"dataset": STRANDSONE_ID, "db": db, "year": 2025})
    except ValueError as exc:
        assert "year" in str(exc)
        assert "filters" in str(exc)
    else:  # pragma: no cover - the silent-drop regression
        raise AssertionError("run_analysis accepted an unknown argument")


def test_inspect_reports_stored_dimensions_so_filters_are_not_guessed(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    from public_data_agent import fetch as fetch_mod
    from public_data_agent import ssb_pxweb as ssb_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    call_tool("fetch", {"dataset": STRANDSONE_ID, "table": "11763", "db": db, "year": 2025, "join": True})

    payload = call_tool("inspect", {"dataset": "ssb:11763", "db": db})
    schema = payload["observation_schema"]
    assert schema["observation_count"] > 0
    assert "bydel_code" in schema["dimensions"]
    stored_years = schema["dimensions"]["år"]["values"]
    assert stored_years, "the stored period values must be listed, not inferred"
    # Every listed value must be one a connector actually wrote.
    assert all(isinstance(value, str) for value in stored_years)


def test_run_analysis_explains_an_empty_result_instead_of_returning_it_bare(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    from public_data_agent import fetch as fetch_mod
    from public_data_agent import ssb_pxweb as ssb_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    call_tool("fetch", {"dataset": STRANDSONE_ID, "table": "11763", "db": db, "year": 2025, "join": True})

    payload = call_tool("run_analysis", {"dataset": "ssb:11763", "db": db, "filters": {"Tid": "2025"}})
    assert payload["values"] == []
    assert payload["warnings"], "an empty result must carry a reason"
    assert "Tid" in " ".join(payload["warnings"])


def test_run_analysis_warns_when_an_aggregate_would_double_count(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    from public_data_agent import fetch as fetch_mod
    from public_data_agent import ssb_pxweb as ssb_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    call_tool("fetch", {"dataset": STRANDSONE_ID, "table": "11763", "db": db, "year": 2025, "join": True})

    payload = call_tool(
        "run_analysis",
        {"dataset": "ssb:11763", "db": db, "group_by": ["region"], "aggregate": "sum", "measure": "value"},
    )
    joined = " ".join(payload["warnings"])
    assert "double counts" in joined or "total" in joined


def test_join_payload_states_that_sample_is_not_a_ranking(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    from public_data_agent import fetch as fetch_mod
    from public_data_agent import ssb_pxweb as ssb_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    payload = call_tool(
        "fetch", {"dataset": STRANDSONE_ID, "table": "11763", "db": db, "year": 2025, "join": True}
    )
    assert payload["row_count"] == len(payload["rows"])
    assert "not a ranking" in payload["sample_note"].lower()


def test_connector_candidates_are_not_offered_for_unrelated_questions(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    payload = call_tool("search", {"query": "fiskeoppdrett", "db": db, "limit": 5})
    assert payload["connector_candidates"] == []
    assert "not fetchable" in payload["connector_candidates_note"]


def test_search_separates_fetchable_sources_from_catalogue_records(tmp_path: Path) -> None:
    """Two questions share one ranked list; neither may crowd the other out."""

    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    payload = call_tool("search", {"query": "strandsone", "db": db, "limit": 5})

    assert "observation_sources" in payload
    assert "catalogue_records" in payload
    # A dataset appears in exactly one lane, decided by what it can actually return.
    obs = {hit["id"] for hit in payload["observation_sources"]}
    cat = {hit["id"] for hit in payload["catalogue_records"]}
    assert not (obs & cat)
    for hit in payload["observation_sources"]:
        assert hit["connector"]["capability"] == "observations"
    for hit in payload["catalogue_records"]:
        assert hit["connector"]["capability"] != "observations"
    assert "observation_sources" in payload["lanes_note"]


def test_lanes_are_filled_from_a_deeper_ranking_than_the_returned_page(tmp_path: Path) -> None:
    """A lane cannot be filled from a list already truncated to the other's winners."""

    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()
    payload = call_tool("search", {"query": "strandsone", "db": db, "limit": 1})

    assert len(payload["results"]) <= 1
    # Each lane still gets its own top-N even though `results` holds one row.
    assert len(payload["observation_sources"]) <= 1
    assert len(payload["catalogue_records"]) <= 1
    lane_ids = {hit["id"] for hit in payload["observation_sources"]}
    lane_ids |= {hit["id"] for hit in payload["catalogue_records"]}
    assert lane_ids, "lanes must not be empty just because the page is small"


def test_search_reports_when_it_ranked_on_tokens_alone(tmp_path: Path, monkeypatch) -> None:
    """Ranking without meaning finds the right table for 44% of gold questions
    against 86% with it, so a caller is told which one it got."""

    from public_data_agent import mcp_server

    monkeypatch.setattr(mcp_server, "_embedding_provider", lambda: None)
    registry = _registry(tmp_path)
    registry.close()

    payload = mcp_server.tool_search("strandsone", db=str(tmp_path / "registry.sqlite"))
    assert payload["ranking"] == "lexical only"
    assert "44%" in payload["ranking_note"]


def test_a_result_found_by_meaning_alone_is_not_dropped(tmp_path: Path, monkeypatch) -> None:
    """35 of 86 gold questions name a table whose title shares no word with the
    question. Those have no lexical hit to carry their metadata, and keeping
    only hits that had one would drop exactly what the ranking was added to
    find."""

    from public_data_agent import mcp_server

    registry = _registry(tmp_path)
    unrelated = registry.conn.execute(
        "SELECT id FROM datasets ORDER BY id"
    ).fetchall()[0]["id"]
    registry.close()

    class OnlyFindsTheUnrelatedOne:
        steps = ["stubbed"]
        observations: list[str] = []
        catalogue = [unrelated]

    monkeypatch.setattr(mcp_server, "_embedding_provider", lambda: object())
    monkeypatch.setattr(mcp_server, "find", lambda *a, **k: OnlyFindsTheUnrelatedOne())

    payload = mcp_server.tool_search(
        "a query matching no stored token at all", db=str(tmp_path / "registry.sqlite")
    )
    returned = {hit["id"] for hit in payload["results"]}
    assert unrelated in returned
    entry = next(hit for hit in payload["results"] if hit["id"] == unrelated)
    # Not matched by tokens, so it carries no token score and says why.
    assert entry["relevance"] == 0
    assert "shares no query token" in entry["why"]


def test_inspect_reports_the_shape_of_a_resource_never_fetched(tmp_path: Path) -> None:
    """The point of inspecting before fetching is to learn the dimension names,
    and `observation_schema` only knows the ones already pulled."""

    from public_data_agent.resource_index import resource_shape as _shape

    registry = _registry(tmp_path)
    dataset = registry.conn.execute("SELECT id FROM datasets ORDER BY id").fetchall()[0]["id"]
    registry.set_resource_shape(dataset, [
        {"field_code": "Region", "field_label": "region", "field_role": "key",
         "values": [{"value_code": "0301", "value_label": "Oslo"}]},
        {"field_code": "Tid", "field_role": "period",
         "values": [{"value_code": "2020", "value_label": "2020"}]},
    ], keys=[{"scheme": "klass:131:kommune", "field_code": "Region", "coverage_count": 1}])
    registry.set_capability(dataset, {
        "capability": "observations", "request_method": "POST",
        "period_start": "2020", "period_end": "2020",
    })
    db = str(tmp_path / "registry.sqlite")
    registry.close()

    payload = call_tool("inspect", {"dataset": dataset, "db": db})
    shape = payload["resource_shape"]
    assert shape["indexed"] is True
    assert {f["code"] for f in shape["fields"]} == {"Region", "Tid"}
    assert shape["keys"][0]["scheme"] == "klass:131:kommune"
    # Nothing has been fetched, so the observation schema is still empty --
    # which is exactly why the indexed shape has to be there too.
    assert payload["observation_schema"]["observation_count"] == 0
    assert _shape is not None


def test_the_server_actually_builds_and_exposes_its_tools() -> None:
    """Every other test here calls `call_tool` directly, so all of them passed
    while `build_server` raised ModuleNotFoundError on an import path that does
    not exist in the mcp package. The tools worked; nothing could connect to
    them, which for an MCP server is the whole product."""

    import asyncio

    from public_data_agent.mcp_server import TOOLS, build_server

    server = build_server()
    exposed = {tool.name for tool in asyncio.run(server.list_tools())}
    assert exposed == set(TOOLS), f"registered {sorted(TOOLS)} but exposed {sorted(exposed)}"


def test_every_exposed_tool_carries_a_description() -> None:
    """A tool an agent cannot tell apart from another is not usable."""

    import asyncio

    from public_data_agent.mcp_server import build_server

    for tool in asyncio.run(build_server().list_tools()):
        assert tool.description, f"{tool.name} has no description"


def _with_entity_record(tmp_path: Path) -> str:
    """A dataset holding one company record and no observations."""

    from public_data_agent.registry import Registry as _R

    db = str(tmp_path / "registry.sqlite")
    registry = _R(db)
    url = "https://data.brreg.no/enhetsregisteret/api/enheter/923609016"
    registry.conn.execute(
        """
        INSERT INTO datasets (id, source_id, ingest_reason, source_name,
            source_endpoints_json, missing_fields_json, payload_hash,
            first_ingested_at, last_ingested_at, last_seen_at, last_changed_at,
            title, access_path, publisher_name)
        VALUES ('b:1', 'brenheter', 't', 'B', '[]', '{}', 'h', 't', 't', 't', 't',
                'EQUINOR ASA', ?, 'Brønnøysundregistrene')
        """,
        (url,),
    )
    registry.conn.execute(
        """
        INSERT INTO fetch_runs (id, dataset_id, table_id, request_url, request_method,
                                started_at, status)
        VALUES (1, 'b:1', 'enheter', ?, 'GET', 't', 'completed')
        """,
        (url,),
    )
    registry.conn.commit()
    registry.upsert_record({
        "id": "r1", "dataset_id": "b:1", "kind": "entity",
        "subject_scheme": "brreg:orgnr", "subject_code": "923609016",
        "subject_label": "EQUINOR ASA", "attributes": {"ansatte": 21126},
        "retrieved_at": "t", "request_url": url, "http_status": 200,
    }, 1)
    registry.close()
    return db


def test_provenance_counts_records_not_only_observations(tmp_path: Path) -> None:
    """Reporting the observation count alone said "0" for a dataset holding a
    company, which reads as "there is nothing here" rather than "what is here is
    not an observation"."""

    payload = call_tool("get_provenance", {"dataset": "b:1", "db": _with_entity_record(tmp_path)})
    assert payload["observation_count"] == 0
    assert payload["record_counts"] == {"entity": 1}
    assert payload["stored_total"] == 1
    # The record's request URL is lineage too.
    assert any("brreg" in url for url in payload["request_urls"])


def test_run_analysis_reads_the_record_store_and_names_it(tmp_path: Path) -> None:
    """It used to report "completed" with no rows for a dataset full of things.

    First it explained that it could not read them, which was honest and
    useless -- there was no other tool that could. It returns them now, and
    says which store they came from, because a measurement and a thing are not
    interchangeable even when both arrive as `values`.
    """

    payload = call_tool("run_analysis", {"dataset": "b:1", "db": _with_entity_record(tmp_path)})
    assert payload["values_from"] == "stored_records"
    assert payload["stored_records"] == {"entity": 1}
    assert "1 entity" in payload["explanation"]
    (row,) = payload["values"]
    assert row["kind"] == "entity"
    assert row["subject_code"]
    assert row["value"] is None


def test_run_analysis_does_not_silently_drop_an_aggregation(tmp_path: Path) -> None:
    """Answering a different question than the one asked is worse than refusing.

    The record store has no measured value, so `aggregate` cannot be applied;
    returning the rows as though it had been would read as a computed answer.
    """

    payload = call_tool(
        "run_analysis",
        {
            "dataset": "b:1",
            "db": _with_entity_record(tmp_path),
            "group_by": ["kind"],
            "aggregate": "sum",
        },
    )
    assert payload["values_from"] == "stored_records"
    assert any("was not applied" in warning for warning in payload["warnings"])


def test_inspect_reports_what_kinds_are_stored(tmp_path: Path) -> None:
    payload = call_tool("inspect", {"dataset": "b:1", "db": _with_entity_record(tmp_path)})
    assert payload["stored_records"] == {"entity": 1}
    assert payload["observation_schema"]["observation_count"] == 0


def test_a_catalogue_record_says_when_its_rows_are_already_readable(tmp_path: Path) -> None:
    """"Cannot be retrieved" stopped being true for most of this lane.

    571 datasets read `lookup` -- Oslo's 42 bydeler, 365 municipalities, 7,127
    occupation titles -- and every one holds entity records that run_analysis
    reads. Saying nothing told the caller its data was out of reach while it
    sat in the record store.
    """

    payload = call_tool("search", {"query": "Equinor", "db": _with_entity_record(tmp_path)})
    lane = payload["catalogue_records"] + payload["observation_sources"]
    hit = next((h for h in lane if h["id"] == "b:1"), None)
    assert hit is not None, "the fixture dataset should be ranked for its own name"
    if not hit["connector"]["fetch_supported"]:
        assert hit["connector"]["stored_records"] == {"entity": 1}
        assert "1 entity record" in hit["connector"]["readable"]
        assert "run_analysis" in hit["connector"]["readable"]
    assert "stored_records" in payload["lanes_note"]
