from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.resource_index import index_dataset
from public_data_agent.sources.strepresent import (
    entity_from_representant,
    is_dagensrepresentanter_url,
)

REPS_URL = "https://data.stortinget.no/eksport/dagensrepresentanter?format=json"
PAYLOAD = {
    "dagensrepresentanter_liste": [
        {
            "id": "MARNIL",
            "fornavn": "Marius Arion",
            "etternavn": "Nilsen",
            "epost": "marius.arion.nilsen@stortinget.no",
            "kjoenn": 2,
            "vara_representant": False,
            "parti": {"id": "FrP", "navn": "Fremskrittspartiet"},
            "fylke": {"id": "AA", "navn": "Aust-Agder"},
            "komiteer_liste": [{"id": "ENERGI"}],
        },
        {
            "id": "ERIKST",
            "fornavn": "Erna",
            "etternavn": "Solberg",
            "parti": {"id": "H", "navn": "Høyre"},
            "fylke": {"id": "Ho", "navn": "Hordaland"},
        },
    ]
}


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if "dagensrepresentanter" in url:
            return JsonResponse(status=200, url=url, body=PAYLOAD)
        raise AssertionError(url)


def test_url_is_the_current_roster_not_other_eksport_paths() -> None:
    assert is_dagensrepresentanter_url(REPS_URL)
    assert not is_dagensrepresentanter_url(
        "https://data.stortinget.no/eksport/stortingsperioder?format=json"
    )
    assert classify_access_path(REPS_URL)["kind"] == "entities"


def test_entity_uses_printed_id_and_flattens_parti_fylke() -> None:
    entity = entity_from_representant(PAYLOAD["dagensrepresentanter_liste"][0])
    assert entity["subject_code"] == "MARNIL"
    assert entity["subject_label"] == "Marius Arion Nilsen"
    assert entity["attributes"]["parti.id"] == "FrP"
    assert entity["attributes"]["fylke.navn"] == "Aust-Agder"
    assert "komiteer_liste" not in entity["attributes"]


def test_fetch_stores_people_not_name_observations(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id="stortinget:dagensrepresentanter",
        title="dagensrepresentanter",
        publisher_name=None,
        access_path=REPS_URL,
        license=None,
    )
    registry.conn.execute(
        "UPDATE datasets SET source_native_id = ? WHERE id = ?",
        ("dagensrepresentanter", "stortinget:dagensrepresentanter"),
    )
    registry.conn.commit()

    indexed = index_dataset(
        registry, "stortinget:dagensrepresentanter", http=FetchHttp(), catalogues={}
    )
    assert indexed["fields"] >= 1
    result = fetch_observations(
        registry,
        "stortinget:dagensrepresentanter",
        table_id="dagensrepresentanter",
        select={"id": ["MARNIL"]},
        http=FetchHttp(),
    )
    assert result.counts.listed == 1
    assert result.sample[0]["kind"] == "entity"
    assert result.sample[0]["subject_code"] == "MARNIL"
    assert registry.list_observations("stortinget:dagensrepresentanter") == []
    cap = registry.get_capability("stortinget:dagensrepresentanter")
    assert cap["capability"] == "entities"
    assert cap["verified_sample_count"] == 1
    with pytest.raises(ValueError, match="not in dagensrepresentanter"):
        fetch_observations(
            registry,
            "stortinget:dagensrepresentanter",
            table_id="dagensrepresentanter",
            select={"id": ["NOPE"]},
            http=FetchHttp(),
        )
    registry.close()
