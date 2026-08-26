from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.mapping import map_harvested_record, payload_hash
from public_data_agent.models import HarvestedRecord
from public_data_agent.sources.datanorge import INGEST_REASON, SOURCE_ID, SOURCE_NAME
from public_data_agent.sources.datanorge import RESOURCE_URL, SPARQL_URL

FIXTURES = Path(__file__).parent / "fixtures"


def _record(payload: dict, *, source_id: str = SOURCE_ID) -> HarvestedRecord:
    return HarvestedRecord(
        source_id=source_id,
        source_name=SOURCE_NAME,
        source_endpoints=(SPARQL_URL, RESOURCE_URL),
        ingest_reason=INGEST_REASON,
        source_native_id=payload.get("id"),
        source_native_uri=payload.get("uri"),
        fetched_from=f"{RESOURCE_URL}/v1/datasets/{payload.get('id')}",
        payload=payload,
        catalog_modified=(payload.get("harvest") or {}).get("modified"),
    )


def test_maps_live_ssb_payload_without_inventing_values() -> None:
    payload = json.loads((FIXTURES / "ssb-strandsone.json").read_text(encoding="utf-8"))
    mapped = map_harvested_record(_record(payload))

    assert mapped.id == "datanorge:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
    assert mapped.source_native_uri == payload["uri"]
    assert mapped.title == "Potensielt tilgjengelig strandsone"
    assert mapped.title_i18n == {"no": "Potensielt tilgjengelig strandsone"}
    assert "en" not in mapped.title_i18n
    assert mapped.publisher_name == "Statistisk sentralbyrå"
    assert mapped.publisher_id == "971526920"
    assert mapped.license == "http://publications.europa.eu/resource/authority/licence/NLOD_1_0"
    assert mapped.access_path == "https://kart.ssb.no/"
    assert mapped.issued == "2014-07-04"
    assert mapped.modified == "2014-07-04"
    assert mapped.temporal_start == "2014-01-01T00:00:00Z"
    assert mapped.temporal_end is None
    assert mapped.spatial == []
    assert "application/vnd.shp" in mapped.media_types
    assert "SHP" in mapped.formats
    assert mapped.source_name == SOURCE_NAME
    assert mapped.source_endpoints == (SPARQL_URL, RESOURCE_URL)
    assert mapped.ingest_reason == INGEST_REASON
    assert mapped.missing_fields["spatial"] == "absent from Resource Service dataset JSON"
    assert "publisher" not in mapped.missing_fields
    assert "license" not in mapped.missing_fields
    assert "access_path" not in mapped.missing_fields
    assert "original_source" not in mapped.missing_fields
    assert mapped.payload is payload
    assert mapped.payload_hash == payload_hash(payload)


def test_maps_multilingual_title_and_spatial_from_helsedata() -> None:
    payload = json.loads((FIXTURES / "helsedata-ssb.json").read_text(encoding="utf-8"))
    mapped = map_harvested_record(_record(payload))

    assert mapped.title == "Data fra SSB"
    assert mapped.title_i18n == {"nb": "Data fra SSB"}
    assert mapped.spatial[0]["uri"] == "http://publications.europa.eu/resource/authority/country/NOR"
    assert mapped.access_rights_uri == (
        "http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC"
    )
    assert mapped.issued is None
    assert mapped.missing_fields["issued"] == "absent from Resource Service dataset JSON"
    assert "spatial" not in mapped.missing_fields


def test_sparse_payload_records_nulls_and_missing_reasons() -> None:
    payload = json.loads((FIXTURES / "sparse.json").read_text(encoding="utf-8"))
    mapped = map_harvested_record(_record(payload))

    assert mapped.title == "Sparse fixture"
    assert mapped.description is None
    assert mapped.publisher is None
    assert mapped.license is None
    assert mapped.access_path is None
    assert mapped.issued is None
    assert mapped.distributions == []
    assert mapped.missing_fields["publisher"] == "absent from Resource Service dataset JSON"
    assert mapped.missing_fields["license"].startswith("absent from Resource Service dataset JSON")
    assert mapped.missing_fields["access_path"].startswith("absent from Resource Service dataset JSON")
    assert "original_source" not in mapped.missing_fields


def test_does_not_invent_a_title_when_all_languages_are_empty() -> None:
    payload = {
        "id": "empty-title",
        "uri": "https://example.org/datasets/empty-title",
        "title": {"en": None, "nb": None, "nn": None, "no": None},
        "publisher": {"id": "1", "name": "Org", "uri": "https://example.org/org"},
        "distribution": [
            {
                "accessURL": ["https://example.org/file.csv"],
                "license": [{"uri": "https://example.org/license"}],
            }
        ],
    }
    mapped = map_harvested_record(_record(payload))
    assert mapped.title is None
    assert mapped.title_i18n == {}
    assert mapped.missing_fields["title"] == "absent from Resource Service dataset JSON"
