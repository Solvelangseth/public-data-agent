"""Statens vegvesen Dataportalen: its data services, pointed at the services.

Two decisions are held here. Only `dataservice` packages are harvested, because
every one of the portal's datasets is already catalogued through data.norge.
And a record points at the service rather than at CKAN's `package_show`, which
returns metadata: two tests that used to pin a fetch storing resource
descriptions as observations are replaced by one that holds the opposite.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.vegvesen import (
    VegvesenSource,
    is_vegvesen_url,
    printed_access_rights,
    printed_license_url,
    printed_package_show_url,
    printed_publisher,
    vegvesen_table_id,
)

LIST_URL = "https://dataut.vegvesen.no/api/3/action/package_list"
SEARCH_URL = "https://dataut.vegvesen.no/api/3/action/package_search"
ARTS_URL = "https://dataut.vegvesen.no/api/3/action/package_show?id=artsmangfold"
NLOD_URL = "https://data.norge.no/nlod/no"
PUBLIC = "http://publications.europa.eu/resource/authority/access-right/PUBLIC"
RESTRICTED = "http://publications.europa.eu/resource/authority/access-right/RESTRICTED"
ORG_ID = "e6d3dc7a-752e-418b-9afd-36533b370285"
DATEX_ENDPOINT = "https://datex-server-get-v3-1.atlas.vegvesen.no/"
DATEX_URI = "https://dataut.vegvesen.no/dataservice/15f2e7e5-8d0b-4b29-9c50-0e55a7991047"
ORG = {"id": ORG_ID, "name": "statens-vegvesen", "title": "Statens vegvesen"}

DATEX = {
    "name": "datex",
    "type": "dataservice",
    "title": "Trafikk informasjon",
    "notes": "Trafikkinformasjon i DATEX II-format.",
    "license_url": NLOD_URL,
    "license_id": "NLOD",
    "access_rights": PUBLIC,
    "end_point_url": DATEX_ENDPOINT,
    "uri": DATEX_URI,
    "url": "https://www.vegvesen.no/fag/teknologi/apne-data/et-utvalg-apne-data/hva-er-datex/",
    "metadata_modified": "2026-09-07T09:46:48.473773",
    "organization": ORG,
    "resources": [],
}

DATAFANGST = {
    "name": "datafangst-api",
    "type": "dataservice",
    "title": "Datafangst 2.0 API",
    "license_id": "notspecified",
    "access_rights": RESTRICTED,
    "end_point_url": "https://datafangst.api.vegvesen.no",
    "uri": "https://dataut.vegvesen.no/dataservice/aaaaaaaa-0000-4000-8000-000000000001",
    "organization": ORG,
    "resources": [],
}

UNLABELLED = {
    "name": "eierskifte",
    "type": "dataservice",
    "title": "Eierskifte",
    "end_point_url": "https://umopel.miljo.autodev.no/ws/no/vegvesen/kjoretoy",
    "uri": "https://dataut.vegvesen.no/dataservice/aaaaaaaa-0000-4000-8000-000000000002",
    "organization": ORG,
    "resources": [{"id": "r1", "name": "Dokumentasjon", "url": "https://example.test/doc.pdf"}],
}

# Returned even though the query asks for data services, to prove the listing
# checks the printed type itself rather than trusting the filter.
ARTS_DATASET = {"name": "artsmangfold", "type": "dataset", "title": "Artsmangfold", "resources": []}
BLANK = {"name": "", "type": "dataservice", "title": "No name"}

PACKAGES = [DATEX, ARTS_DATASET, DATAFANGST, BLANK, UNLABELLED]


class SearchHttp:
    """Serves package_search in pages of `rows`, honouring `start`."""

    def __init__(self, packages=PACKAGES) -> None:
        self.packages = packages
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        parts = urlsplit(url)
        assert f"{parts.scheme}://{parts.netloc}{parts.path}" == SEARCH_URL, f"unexpected GET {url}"
        query = parse_qs(parts.query)
        assert query["fq"] == ["type:dataservice"]
        start, rows = int(query["start"][0]), int(query["rows"][0])
        return {
            "success": True,
            "result": {"count": len(self.packages), "results": self.packages[start : start + rows]},
        }


def test_only_data_services_are_listed() -> None:
    refs = VegvesenSource(http=SearchHttp()).list_dataset_refs()
    # The dataset is skipped though returned, and a blank name is not a package.
    assert [ref.source_native_id for ref in refs] == ["datex", "datafangst-api", "eierskifte"]
    # The native uri is the publisher's own identifier for the service.
    assert refs[0].source_native_uri == DATEX_URI


def test_every_page_is_walked() -> None:
    http = SearchHttp()
    refs = VegvesenSource(http=http, page_size=2).list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["datex", "datafangst-api", "eierskifte"]
    assert len(http.gets) == 3


def test_limit_and_offset_slice_listed_services() -> None:
    source = VegvesenSource(http=SearchHttp())
    assert [r.source_native_id for r in source.list_dataset_refs(limit=1)] == ["datex"]
    assert [r.source_native_id for r in source.list_dataset_refs(limit=1, offset=1)] == ["datafangst-api"]


def test_package_show_url_joins_printed_origin_and_name() -> None:
    url = printed_package_show_url("artsmangfold", LIST_URL)
    assert url == ARTS_URL
    assert "package_list" not in url


def test_printed_license_and_publisher_copy_only_printed_fields() -> None:
    assert printed_license_url(DATEX) == NLOD_URL
    assert printed_license_url({"license_id": "notspecified"}) is None
    assert printed_license_url({"license_url": "notspecified"}) is None
    assert printed_publisher(DATEX) == {"title": {"no": "Statens vegvesen"}, "id": ORG_ID}
    assert printed_publisher({"organization": None}) is None
    assert printed_publisher({"organization": {"name": "statens-vegvesen"}}) is None


def test_access_rights_are_copied_and_absent_ones_stay_unknown() -> None:
    assert printed_access_rights(DATEX) == {"uri": PUBLIC, "code": "PUBLIC"}
    assert printed_access_rights(DATAFANGST) == {"uri": RESTRICTED, "code": "RESTRICTED"}
    # Printing nothing is not the same as being open.
    assert printed_access_rights(UNLABELLED) is None


def test_vegvesen_is_a_registered_source() -> None:
    assert "vegvesen" in SOURCE_IDS
    source = build_source("vegvesen")
    assert isinstance(source, VegvesenSource)
    assert source.source_id == "vegvesen"


def test_a_harvested_record_points_at_the_service(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        counts = harvest(registry, VegvesenSource(http=SearchHttp()))
        assert counts.inserted == 3
        row = registry.get_dataset("vegvesen:datex")
        assert row["access_path"] == DATEX_ENDPOINT
        assert row["title"] == "Trafikk informasjon"
        assert row["publisher_name"] == "Statens vegvesen"
        assert row["license"] == NLOD_URL
        assert row["access_rights_uri"] == PUBLIC
        assert DATEX_URI in json.loads(row["landing_pages_json"])

        restricted = registry.get_dataset("vegvesen:datafangst-api")
        assert restricted["access_rights_uri"] == RESTRICTED
        assert restricted["license"] is None

        unlabelled = registry.get_dataset("vegvesen:eierskifte")
        assert unlabelled["access_rights_uri"] is None
        # The endpoint is listed before any printed resource.
        assert unlabelled["access_path"] == UNLABELLED["end_point_url"]

        assert registry.get_dataset("vegvesen:artsmangfold") is None
        payload = json.loads(
            registry.conn.execute(
                "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
                ("vegvesen:datex",),
            ).fetchone()["payload_json"]
        )
        assert payload["vegvesen_package_name"] == "datex"
    finally:
        registry.close()


def test_a_catalogue_record_is_not_fetched_as_observations(tmp_path: Path) -> None:
    # The package_show action returns metadata. Fetching it once stored each
    # resource's name as an observation value; it must no longer be fetchable.
    assert classify_access_path(ARTS_URL)["kind"] == "none"

    registry = Registry(tmp_path / "registry.sqlite")
    try:
        registry.ensure_observation_dataset(
            dataset_id="vegvesen:artsmangfold", title="Artsmangfold",
            publisher_name="Statens vegvesen", access_path=ARTS_URL, license=None,
        )
        registry.conn.commit()
        with pytest.raises(Exception):
            fetch_observations(registry, "vegvesen:artsmangfold", table_id="ignored")
        assert registry.list_observations("vegvesen:artsmangfold") == []
    finally:
        registry.close()


def test_is_vegvesen_url_accepts_only_package_show() -> None:
    assert is_vegvesen_url(ARTS_URL)
    assert vegvesen_table_id(ARTS_URL) == "artsmangfold"
    assert not is_vegvesen_url(LIST_URL)
    assert not is_vegvesen_url("https://dataut.vegvesen.no/dataset/artsmangfold")
    assert not is_vegvesen_url("https://nvdbapiles-v3.atlas.vegvesen.no/")
    assert not is_vegvesen_url("https://data.norge.no/datasets/x")
    assert not is_vegvesen_url(None)
