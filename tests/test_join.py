from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.cli import main
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.join import join_bydel_population
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource
from public_data_agent.ssb_klass import cells_from_klass
from public_data_agent.ssb_pxweb import (
    bydel_codes_from_meta,
    cells_from_jsonstat_coded,
    i_alt_age_selection,
    is_ssb_pxweb_url,
)

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
            "values": ["EAB", "030101", "030102", "888888"],
            "valueTexts": ["Alle bydeler i Oslo", "Gamle Oslo", "Grünerløkka", "Unknown"],
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


class JoinHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == KLASS_URL:
            return JsonResponse(status=200, url=url, body=KLASS_PAYLOAD)
        if url == SSB_URL:
            return JsonResponse(status=200, url=url, body=SSB_META)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        if url != SSB_URL:
            raise AssertionError(f"unexpected POST {url}")
        region = next(item for item in body["query"] if item["code"] == "KOKbydelsregion0000")
        assert "030101" in region["selection"]["values"]
        assert "EAB" not in region["selection"]["values"]
        age = next(item for item in body["query"] if item["code"] == "KOKalder0000")
        assert age["selection"]["values"] == ["F000-120"]
        return JsonResponse(status=200, url=url, body=SSB_JSONSTAT)


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?",
        (KLASS_URL, STRANDSONE_ID),
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


def test_ssb_meta_keeps_only_six_digit_bydel_codes() -> None:
    code, values = bydel_codes_from_meta(SSB_META)
    assert code == "KOKbydelsregion0000"
    assert values == ["030101", "030102", "888888"]
    assert i_alt_age_selection(SSB_META) == ("KOKalder0000", "F000-120")
    assert is_ssb_pxweb_url(SSB_URL)
    assert not is_ssb_pxweb_url(KLASS_URL)


def test_jsonstat_keeps_region_codes() -> None:
    cells = cells_from_jsonstat_coded(SSB_JSONSTAT)
    assert [cell.codes["KOKbydelsregion0000"] for cell in cells] == ["030101", "030102"]
    assert [cell.value for cell in cells] == [64920, 67039]
    assert cells[0].measure == "Personer (antall)"


def test_klass_cells_are_not_a_metric() -> None:
    cells = cells_from_klass(KLASS_PAYLOAD)
    assert cells[0][2]["code"] == "030101"
    assert cells[0][1] == "Gamle Oslo"


def test_join_on_exact_bydel_code_and_leaves_harvest_untouched(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    before = _harvest_bytes(registry)
    enrich_before = registry.enrichment_count()
    result = join_bydel_population(
        registry,
        klass_dataset_id=STRANDSONE_ID,
        ssb_table="11763",
        year=2025,
        http=JoinHttp(),
    )
    assert result.left_http_status == 200
    assert result.right_http_status == 200
    assert result.join_key == "bydel_code"
    assert result.counts.listed == 2
    assert result.counts.inserted == 2
    assert registry.joined_row_count() == 2
    assert registry.observation_count() == 3
    assert _harvest_bytes(registry) == before
    assert registry.enrichment_count() == enrich_before
    first = result.sample[0]
    assert first["join_key_value"] == "030101"
    assert first["population"] == 64920
    assert first["klass_name"] == "Gamle Oslo"
    assert first["ssb_region_label"] == "Gamle Oslo"
    assert "exact bydel_code 030101" in first["why_matched"]
    stored = registry.list_joined_rows()
    assert {json.loads(row["payload_json"])["population"] for row in stored} == {64920, 67039}
    assert all(row["left_request_url"] == KLASS_URL for row in stored)
    assert all(row["right_request_url"] == SSB_URL for row in stored)
    second = join_bydel_population(
        registry,
        klass_dataset_id=STRANDSONE_ID,
        ssb_table="11763",
        year=2025,
        http=JoinHttp(),
    )
    assert second.counts.unchanged == 2
    assert second.counts.inserted == 0
    assert registry.joined_row_count() == 2
    registry.close()


def test_cli_join_writes_proof(tmp_path: Path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "registry.sqlite"
    out = tmp_path / "join_proof.json"
    registry.close()

    from public_data_agent import fetch as fetch_mod
    from public_data_agent import ssb_pxweb as ssb_mod

    monkeypatch.setattr(fetch_mod, "HttpClient", lambda **kwargs: JoinHttp())
    monkeypatch.setattr(ssb_mod, "HttpClient", lambda **kwargs: JoinHttp())
    assert (
        main(
            [
                "join",
                "--dataset",
                STRANDSONE_ID,
                "--table",
                "11763",
                "--year",
                "2025",
                "--db",
                str(db),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["join_key"] == "bydel_code"
    assert payload["counts"]["joined"] == 2
    assert payload["sample"][0]["population"] == 64920
    assert payload["sources"]["left"]["http_status"] == 200
    assert payload["sources"]["right"]["http_status"] == 200
