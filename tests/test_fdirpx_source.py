from __future__ import annotations

from pathlib import Path

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.mapping import map_harvested_record
from public_data_agent.registry import Registry
from public_data_agent.resource_index import index_dataset
from public_data_agent.sources import build_source
from public_data_agent.sources.fdirpx import (
    CATALOGUE_URL,
    TABLE_URL,
    FdirPxwebSource,
    is_fdirpx_url,
)

CATALOGUE = [
    {
        "id": "A06001.px",
        "type": "t",
        "text": "A.06.001 Totalt. Salg av oppdrettet fisk",
        "updated": "2026-06-01T15:26:35",
    },
    {
        "id": "A06002a.px",
        "type": "t",
        "text": "A.06.002a Matfisk. Salg av laks, regnbueørret og ørret (Art)",
        "updated": "2026-06-01T15:26:35",
    },
]

META = {
    "title": "A.06.002a Matfisk. Salg av laks, regnbueørret og ørret (Art) (1994-2025)",
    "variables": [
        {
            "code": "År",
            "text": "År",
            "values": ["1994", "2025"],
            "valueTexts": ["1994", "2025"],
            "time": True,
        },
        {
            "code": "Art",
            "text": "Art",
            "values": ["Laks", "Regnbueørret", "Ørret"],
            "valueTexts": ["Laks", "Regnbueørret", "Ørret"],
        },
        {
            "code": "Statistikkvariabel",
            "text": "Statistikkvariabel",
            "values": ["Kvantum (tonn)", "Verdi (1000 kroner)"],
            "valueTexts": ["Kvantum (tonn)", "Verdi (1000 kroner)"],
        },
    ],
}

JSONSTAT = {
    "class": "dataset",
    "label": "A.06.002a Matfisk. Salg av laks",
    "id": ["År", "Art", "Statistikkvariabel"],
    "size": [1, 1, 1],
    "value": [1_754_557],
    "role": {"time": ["År"], "metric": ["Statistikkvariabel"]},
    "dimension": {
        "År": {"category": {"index": {"2025": 0}, "label": {"2025": "2025"}}},
        "Art": {"category": {"index": {"Laks": 0}, "label": {"Laks": "Laks"}}},
        "Statistikkvariabel": {
            "category": {
                "index": {"Kvantum (tonn)": 0},
                "label": {"Kvantum (tonn)": "Kvantum (tonn)"},
            }
        },
    },
}


class ScriptedHttp:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict]] = []

    def get_json(self, url: str, *, headers=None):
        if url == CATALOGUE_URL:
            return CATALOGUE
        if url == TABLE_URL:
            return META
        raise AssertionError(url)

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        return JsonResponse(status=200, url=url, body=self.get_json(url, headers=headers))

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        self.posts.append((url, body))
        return JsonResponse(status=200, url=url, body=JSONSTAT)


def test_source_promotes_only_the_salmon_sales_table() -> None:
    source = FdirPxwebSource(http=ScriptedHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["A06002a"]
    assert refs[0].source_native_uri == TABLE_URL
    mapped = map_harvested_record(source.fetch_dataset(refs[0]))
    assert mapped.title.startswith("A.06.002a Matfisk. Salg av laks")
    assert mapped.publisher_name == "Fiskeridirektoratet"
    assert mapped.temporal == [{"start": "1994", "end": "2025", "uri": None}]
    assert mapped.license is None


def test_table_is_registered_as_a_pxweb_observation_source() -> None:
    assert is_fdirpx_url(TABLE_URL)
    assert not is_fdirpx_url(CATALOGUE_URL)
    assert classify_access_path(TABLE_URL)["kind"] == "observations"
    assert isinstance(build_source("fdirpx"), FdirPxwebSource)


def test_shape_and_one_cell_fetch_use_the_exact_table_endpoint(tmp_path: Path) -> None:
    http = ScriptedHttp()
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FdirPxwebSource(http=http))
    indexed = index_dataset(registry, "fdirpx:A06002a", http=http, catalogues={})
    assert indexed["fields"] == 3
    assert registry.get_capability("fdirpx:A06002a")["capability"] == "observations"

    result = fetch_observations(
        registry,
        "fdirpx:A06002a",
        table_id="A06002a.px",
        select={
            "År": ["2025"],
            "Art": ["Laks"],
            "Statistikkvariabel": ["Kvantum (tonn)"],
        },
        http=http,
    )
    assert result.request_url == TABLE_URL
    assert result.counts.listed == 1
    assert result.sample == [
        {
            "measure": "Kvantum (tonn)",
            "value": 1_754_557,
            "dimensions": {"År": "2025", "Art": "Laks"},
        }
    ]
    assert http.posts[0][0] == TABLE_URL
    picked = {
        item["code"]: item["selection"]["values"]
        for item in http.posts[0][1]["query"]
    }
    assert picked == {
        "År": ["2025"],
        "Art": ["Laks"],
        "Statistikkvariabel": ["Kvantum (tonn)"],
    }
    registry.close()
