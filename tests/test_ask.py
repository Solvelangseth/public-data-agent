from __future__ import annotations

import csv
import json
from pathlib import Path

from public_data_agent.ask import AskResult, DEMO_QUESTION, ask
from public_data_agent.cli import main
from public_data_agent.export import OBSERVATION_COLUMNS, write_ask_csv
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
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


class AskHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == KLASS_URL:
            return JsonResponse(status=200, url=url, body=KLASS_PAYLOAD)
        if url == SSB_URL:
            return JsonResponse(status=200, url=url, body=SSB_META)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        if url != SSB_URL:
            raise AssertionError(f"unexpected POST {url}")
        tid = next(item for item in body["query"] if item["code"] == "Tid")
        year = tid["selection"]["values"][0]
        if year == "2024":
            return JsonResponse(status=200, url=url, body=_jsonstat("2024", [60000, 65000]))
        if year == "2025":
            return JsonResponse(status=200, url=url, body=_jsonstat("2025", [64920, 67039]))
        raise AssertionError(f"unexpected year {year}")


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


def test_ask_ranks_size_and_yoy_from_joined_cells(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    result = ask(
        registry,
        DEMO_QUESTION,
        klass_dataset_id=STRANDSONE_ID,
        ssb_table="11763",
        latest_year=2025,
        prior_year=2024,
        http=AskHttp(),
    )
    assert result.question == DEMO_QUESTION
    assert result.joined_rows == 4
    assert result.joins[0].left_http_status == 200
    assert result.joins[0].right_http_status == 200
    assert result.joins[1].right_http_status == 200
    assert result.largest[0]["bydel_code"] == "030102"
    assert result.largest[0]["population"] == 67039
    assert result.largest[1]["population"] == 64920
    assert result.growing[0]["bydel_code"] == "030101"
    assert result.growing[0]["yoy_growth"] == (64920 - 60000) / 60000
    assert result.growing[0]["yoy_formula"] == "(v_t - v_{t-1}) / v_{t-1}"
    assert result.search["returned"] >= 0
    stored_11763 = registry.list_observations("ssb:11763")
    assert len(stored_11763) == 4
    years = {json.loads(row["dimensions_json"])["år"] for row in stored_11763}
    assert years == {"2024", "2025"}
    registry.close()


def test_cli_ask_writes_proof(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "registry.sqlite"
    out = tmp_path / "ask_proof.json"
    registry.close()

    from public_data_agent import fetch as fetch_mod
    from public_data_agent import ssb_pxweb as ssb_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: AskHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: AskHttp())
    assert (
        main(
            [
                "ask",
                DEMO_QUESTION,
                "--dataset",
                STRANDSONE_ID,
                "--table",
                "11763",
                "--year",
                "2025",
                "--prior-year",
                "2024",
                "--db",
                str(db),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["question"] == DEMO_QUESTION
    assert payload["joined_rows"] == 4
    assert payload["largest"][0]["population"] == 67039
    assert payload["growing"][0]["bydel_code"] == "030101"
    assert payload["joins"][0]["left_http_status"] == 200
    assert payload["joins"][1]["right_http_status"] == 200


def test_cli_ask_reports_planned_fetch_failure(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "registry.sqlite"
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?",
        (SSB_URL, STRANDSONE_ID),
    )
    registry.conn.commit()
    registry.close()

    def fail_fetch(*args, **kwargs):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr("public_data_agent.ask.fetch_observations", fail_fetch)
    assert (
        main(
            [
                "ask",
                "Hvilke strandsone-data finnes?",
                "--db",
                str(db),
            ]
        )
        == 1
    )


def test_cli_ask_writes_stable_csv(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "registry.sqlite"
    out = tmp_path / "ask_export.csv"
    registry.close()

    from public_data_agent import fetch as fetch_mod
    from public_data_agent import ssb_pxweb as ssb_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: AskHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: AskHttp())
    assert (
        main(
            [
                "ask",
                DEMO_QUESTION,
                "--dataset",
                STRANDSONE_ID,
                "--table",
                "11763",
                "--year",
                "2025",
                "--prior-year",
                "2024",
                "--db",
                str(db),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    with out.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == [
        "bydel_code",
        "name",
        "year",
        "personer",
        "yoy",
        "klass_publisher",
        "klass_license",
        "ssb_publisher",
        "ssb_license",
        "join_key",
        "lineage",
    ]
    assert rows[0]["bydel_code"] == "030102"
    assert rows[0]["personer"] == "67039"
    gamle = next(row for row in rows if row["bydel_code"] == "030101")
    assert gamle["yoy"]
    assert float(gamle["yoy"]) == (64920 - 60000) / 60000
    assert gamle["join_key"] == "bydel_code"
    charts = tmp_path / "ask_export_charts"
    assert (charts / "yoy_bar.png").is_file()
    assert (charts / "chart.png").is_file()
    proof = json.loads((tmp_path / "ask_export_proof.json").read_text(encoding="utf-8"))
    assert proof["csv_rows"] == 2
    assert proof["chart_helper"] == "methods.emit.emit"


def test_generic_observations_export_with_provenance(tmp_path: Path) -> None:
    out = tmp_path / "observations.csv"
    result = AskResult(
        question="test",
        latest_year="2025",
        prior_year="2024",
        join_key="",
        search={},
        execution={
            "observations": [
                {
                    "observation_id": "obs-1",
                    "dataset_id": "ssb:demo",
                    "table_id": "demo",
                    "measure": "Antall",
                    "value": 42,
                    "dimensions": {"år": "2025"},
                    "publisher_name": "Example publisher",
                    "license": None,
                    "access_path": "https://example.test/data",
                    "request_url": "https://example.test/data",
                    "http_status": 200,
                }
            ]
        },
    )
    write_ask_csv(result, out)
    with out.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == list(OBSERVATION_COLUMNS)
    assert rows[0]["value"] == "42"
    assert rows[0]["license"] == ""
    assert rows[0]["lineage"].startswith("copied from stored observation")
