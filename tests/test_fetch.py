from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.cli import main
from public_data_agent.fetch import cells_from_jsonstat, fetch_observations, pxweb_api_url
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"
STRANDSONE_ID = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
PXWEB_UI = "https://statistikkbanken.oslo.kommune.no/statbank/pxweb/no/db1/"
TABLE_ID = "Befolkning/Folkemengde/OK-BEF008.px"

META = {
    "title": "BEF008",
    "variables": [
        {
            "code": "år",
            "values": ["49", "50"],
            "valueTexts": ["2020", "2021"],
            "time": True,
        },
        {"code": "geografisk område", "values": ["0"], "valueTexts": ["Oslo i alt"]},
        {
            "code": "Statistikkvariabel",
            "values": ["0"],
            "valueTexts": ["Folkemengden i alt (antall personer)"],
        },
    ],
}

JSONSTAT = {
    "label": "BEF008",
    "id": ["år", "geografisk område", "Statistikkvariabel"],
    "size": [2, 1, 1],
    "value": [693494, 697010],
    "role": {"metric": ["Statistikkvariabel"]},
    "dimension": {
        "år": {
            "category": {
                "index": {"49": 0, "50": 1},
                "label": {"49": "2020", "50": "2021"},
            }
        },
        "geografisk område": {
            "category": {"index": {"0": 0}, "label": {"0": "Oslo i alt"}}
        },
        "Statistikkvariabel": {
            "category": {
                "index": {"0": 0},
                "label": {"0": "Folkemengden i alt (antall personer)"},
            }
        },
    },
}


class ScriptedHttp:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict]] = []

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        return JsonResponse(status=200, url=url, body=META)

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        self.posts.append((url, body))
        return JsonResponse(status=200, url=url, body=JSONSTAT)


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?",
        (PXWEB_UI, STRANDSONE_ID),
    )
    registry.conn.commit()
    return registry


def _harvest_bytes(registry: Registry) -> list[tuple]:
    rows = registry.conn.execute(
        """
        SELECT d.id, d.publisher_name, d.license, p.payload_json
        FROM datasets d
        JOIN harvested_payloads p ON p.dataset_id = d.id
        ORDER BY d.id
        """
    ).fetchall()
    return [(row["id"], row["publisher_name"], row["license"], row["payload_json"]) for row in rows]


def test_pxweb_api_url_rewrites_ui_path() -> None:
    url = pxweb_api_url(PXWEB_UI, TABLE_ID)
    assert url == (
        "https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no/db1/"
        "Befolkning/Folkemengde/OK-BEF008.px"
    )


def test_cells_from_jsonstat_keep_source_values() -> None:
    cells = cells_from_jsonstat(JSONSTAT)
    assert cells == [
        (
            "Folkemengden i alt (antall personer)",
            693494,
            {"år": "2020", "geografisk område": "Oslo i alt"},
        ),
        (
            "Folkemengden i alt (antall personer)",
            697010,
            {"år": "2021", "geografisk område": "Oslo i alt"},
        ),
    ]


def test_fetch_stores_observations_and_leaves_harvest_untouched(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    before = _harvest_bytes(registry)
    enrich_before = registry.enrichment_count()
    http = ScriptedHttp()
    result = fetch_observations(
        registry,
        STRANDSONE_ID,
        table_id=TABLE_ID,
        from_year=2020,
        to_year=2021,
        http=http,
    )
    assert result.http_status == 200
    assert result.counts.listed == 2
    assert result.counts.inserted == 2
    assert registry.observation_count() == 2
    assert _harvest_bytes(registry) == before
    assert registry.enrichment_count() == enrich_before
    row = registry.list_observations(STRANDSONE_ID)[0]
    assert row["publisher_name"]
    assert row["request_url"].endswith(TABLE_ID)
    assert row["http_status"] == 200
    assert json.loads(row["value_json"]) in {693494, 697010}
    assert json.loads(row["dimensions_json"])["år"] in {"2020", "2021"}
    second = fetch_observations(
        registry,
        STRANDSONE_ID,
        table_id=TABLE_ID,
        from_year=2020,
        to_year=2021,
        http=ScriptedHttp(),
    )
    assert second.counts.unchanged == 2
    assert second.counts.inserted == 0
    assert registry.observation_count() == 2
    registry.close()


def test_cli_fetch_uses_scripted_path(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "registry.sqlite"
    registry.close()

    from public_data_agent import fetch as fetch_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: ScriptedHttp())
    assert (
        main(
            [
                "fetch",
                "--dataset",
                STRANDSONE_ID,
                "--table",
                TABLE_ID,
                "--from-year",
                "2020",
                "--to-year",
                "2021",
                "--db",
                str(db),
            ]
        )
        == 0
    )
    opened = Registry(db)
    assert opened.observation_count() == 2
    opened.close()
