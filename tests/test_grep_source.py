from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.grep import (
    GrepSource,
    cells_from_grep,
    grep_table_id,
    is_grep_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    printed_version,
)

OPENAPI_URL = "https://data.udir.no/swagger/docs/201906"
AARSTRINN_URL = "https://data.udir.no/kl06/v201906/aarstrinn"
DOKUMENTTYPE_URL = "https://data.udir.no/kl06/v201906/dokumenttype"
NSR_URL = "https://data-nsr.udir.no/v1/enheter"
NBR_URL = "https://data-nbr.udir.no/v1/enheter"
LICENSE_URL = "https://www.udir.no"
DATASET_ID = "grep:aarstrinn"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Grep API",
        "description": "Grep er den nasjonale databasen for fag og læreplaner.",
        "license": {"name": "Udir.no", "url": LICENSE_URL},
        "version": "v201906",
    },
    "paths": {
        "/kl06/v{version}/{kode}": {
            "get": {
                "summary": "lookup by kode",
                "parameters": [{"name": "version", "in": "path", "required": True}],
            }
        },
        "/kl06/v{version}/aarstrinn": {
            "get": {
                "summary": "Hent årstrinn",
                "parameters": [{"name": "version", "in": "path", "required": True}],
            }
        },
        "/kl06/v{version}/aarstrinn.{format}": {
            "get": {
                "summary": "årstrinn with format",
                "parameters": [{"name": "version", "in": "path", "required": True}],
            }
        },
        "/kl06/v{version}/dokumenttype": {
            "get": {
                "summary": "Hent dokumenttype",
                "parameters": [{"name": "version", "in": "path", "required": True}],
            }
        },
        "/kl06/v{version}/fagkoder/{kode}": {
            "get": {
                "summary": "one fagkode",
                "parameters": [
                    {"name": "version", "in": "path", "required": True},
                    {"name": "kode", "in": "path", "required": True},
                ],
            }
        },
    },
}
AARSTRINN_BODY = [
    {
        "id": "uuid:1",
        "kode": "aarstrinn1",
        "uri": "http://psi.udir.no/kl06/aarstrinn1",
        "status": "publisert",
        "tittel": [{"spraak": "nob", "verdi": "Første årstrinn"}],
    },
    {
        "id": "uuid:2",
        "kode": "aarstrinn2",
        "uri": "http://psi.udir.no/kl06/aarstrinn2",
        "nested": {"skip": True},
    },
]


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == OPENAPI_URL:
            return OPENAPI
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == AARSTRINN_URL:
            return JsonResponse(status=200, url=url, body=AARSTRINN_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"grep fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_keep_collection_gets() -> None:
    source = GrepSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["aarstrinn", "dokumenttype"]
    assert [ref.source_native_uri for ref in refs] == [AARSTRINN_URL, DOKUMENTTYPE_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_printed_docs_version() -> None:
    assert printed_version(OPENAPI_URL) == "201906"
    url = printed_endpoint_url(OPENAPI, "/kl06/v{version}/aarstrinn", OPENAPI_URL)
    assert url == AARSTRINN_URL
    origin_only = printed_endpoint_url({}, "/kl06/v{version}/aarstrinn", OPENAPI_URL)
    assert origin_only == AARSTRINN_URL


def test_printed_operation_id_keeps_last_segment() -> None:
    assert printed_operation_id("/kl06/v{version}/aarstrinn", OPENAPI_URL) == "aarstrinn"
    assert printed_operation_id("/kl06/v{version}/dokumenttype", OPENAPI_URL) == "dokumenttype"


def test_printed_license_url_copies_printed_url() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Grep API"}) is None
    assert printed_license_url({"license": {"name": "NLOD"}}) is None


def test_grep_is_a_registered_source() -> None:
    assert "grep" in SOURCE_IDS
    assert "udir" in SOURCE_IDS
    assert "nbr" in SOURCE_IDS
    assert "ssbv2" in SOURCE_IDS
    source = build_source("grep")
    assert isinstance(source, GrepSource)
    assert source.source_id == "grep"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = GrepSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "grep"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == AARSTRINN_URL
    assert row["title"] == "Hent årstrinn"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("udir:")
    assert not str(row["id"]).startswith("nbr:")
    assert not str(row["id"]).startswith("ssbv2:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["grep_swagger_path"] == "/kl06/v{version}/aarstrinn"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_aarstrinn(tmp_path: Path) -> None:
    source = GrepSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == AARSTRINN_URL
    assert result.table_id == "aarstrinn"
    assert result.http_status == 200
    assert result.counts.listed == 2
    # A curriculum code is a code. Udir prints its title in a nested object
    # the connector does not copy, so the record claims no label rather than
    # inventing one.
    assert registry.observation_count() == 0
    rows = registry.list_records(DATASET_ID, kind="entity")
    by_code = {row["subject_code"]: row for row in rows}
    assert set(by_code) == {"aarstrinn1", "aarstrinn2"}
    assert all(row["subject_label"] is None for row in rows)
    assert all(row["subject_scheme"] == "grep:aarstrinn" for row in rows)
    assert all(row["measure"] is None and row["value_json"] is None for row in rows)
    attributes = json.loads(by_code["aarstrinn1"]["attributes_json"])
    assert attributes["id"] == "uuid:1"
    assert attributes["status"] == "publisert"
    assert "tittel" not in attributes
    assert "nested" not in attributes
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["request_url"] == AARSTRINN_URL for row in rows)
    registry.close()


def test_cells_copy_printed_kode_or_id() -> None:
    cells = cells_from_grep(AARSTRINN_BODY)
    assert cells[0][0] == "kode"
    assert cells[0][1] == "aarstrinn1"
    assert cells[0][2]["id"] == "uuid:1"
    assert "tittel" not in cells[0][2]
    assert cells_from_grep({"id": "uuid:9", "uri": "http://psi.udir.no/kl06/x"}) == [
        ("id", "uuid:9", {"uri": "http://psi.udir.no/kl06/x"})
    ]
    assert cells_from_grep("aarstrinn1") == [
        ("value", "aarstrinn1", {"value": "aarstrinn1"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_grep(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_grep([])


def test_is_grep_url_accepts_only_kl06_path() -> None:
    assert is_grep_url(AARSTRINN_URL)
    assert is_grep_url("https://data.udir.no/kl06/v201906/fagkoder")
    assert grep_table_id(AARSTRINN_URL) == "aarstrinn"
    assert not is_grep_url(OPENAPI_URL)
    assert not is_grep_url(NSR_URL)
    assert not is_grep_url(NBR_URL)
    assert not is_grep_url("https://data.norge.no/datasets/x")
    assert not is_grep_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = GrepSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["aarstrinn"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["dokumenttype"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
