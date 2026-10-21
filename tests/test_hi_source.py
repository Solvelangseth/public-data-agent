from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.hi import (
    HiFeaturesSource,
    cells_and_geometry_from_hi,
    cells_from_hi,
    hi_table_id,
    is_hi_url,
    printed_collections,
    printed_items_url,
)

LIST_URL = "https://kart.hi.no/data/ogc/features/v1/collections"
MAREANO_URL = (
    "https://kart.hi.no/data/ogc/features/v1/collections/"
    "hi_basemap:Mareano_observerte_vme/items?f=application%2Fjson"
)
STRANDNOT_URL = (
    "https://kart.hi.no/data/ogc/features/v1/collections/"
    "hi_basemap:Strandnot/items?f=application%2Fjson"
)
RUTENETT_URL = (
    "https://kart.hi.no/data/ogc/features/v1/collections/"
    "hi_basemap:Rutenett/items?f=application%2Fjson"
)
DATASET_ID = "hi:hi_basemap:Strandnot"

COLLECTIONS = {
    "links": [{"href": LIST_URL, "rel": "self", "type": "application/json"}],
    "collections": [
        {
            "id": "hi_basemap:Mareano_observerte_vme",
            "title": "Mareano_observerte_vme",
            "description": "test til christian",
            "links": [
                {
                    "href": "https://kart.hi.no/data/ogc/features/v1/collections/hi_basemap:Mareano_observerte_vme/items?f=text%2Fhtml",
                    "rel": "items",
                    "type": "text/html",
                },
                {"href": MAREANO_URL, "rel": "items", "type": "application/json"},
            ],
        },
        {
            "id": "hi_basemap:Rutenett",
            "title": "Rutenett",
            "links": [
                {"href": RUTENETT_URL, "rel": "items", "type": "application/json"},
            ],
        },
        {
            "id": "hi_basemap:Strandnot",
            "title": "Strandnot",
            "description": "Strandnotstasjoner",
            "links": [
                {"href": STRANDNOT_URL, "rel": "items", "type": "application/json"},
            ],
        },
        {
            "id": "skip-no-items",
            "title": "Missing items",
            "links": [],
        },
        {
            "title": "Missing id",
            "links": [{"href": STRANDNOT_URL, "rel": "items", "type": "application/json"}],
        },
    ],
}
STRANDNOT_BODY = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "Strandnot.1",
            "geometry": {"type": "Point", "coordinates": [5.3, 60.4]},
            "properties": {
                "fid": "Strandnot.1",
                "StationNumber": 12,
                "Lat": 60.4,
                "Long": 5.3,
                "Description": "Bergen",
                "Station": "BN-01",
            },
        },
        {
            "type": "Feature",
            "properties": {
                "fid": "Strandnot.2",
                "StationNumber": 13,
                "Description": "Oslo",
                "Station": "OS-02",
            },
        },
    ],
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return COLLECTIONS
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == STRANDNOT_URL:
            return JsonResponse(status=200, url=url, body=STRANDNOT_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"hi fetch must GET, not POST {url}")


def test_printed_refs_copy_id_and_json_items_href() -> None:
    source = HiFeaturesSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "hi_basemap:Mareano_observerte_vme",
        "hi_basemap:Rutenett",
        "hi_basemap:Strandnot",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        MAREANO_URL,
        RUTENETT_URL,
        STRANDNOT_URL,
    ]
    assert all("f=application%2Fjson" in (ref.source_native_uri or "") for ref in refs)


def test_hi_is_a_registered_source() -> None:
    assert "hi" in SOURCE_IDS
    source = build_source("hi")
    assert isinstance(source, HiFeaturesSource)
    assert source.source_id == "hi"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = HiFeaturesSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "hi"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == STRANDNOT_URL
    assert row["title"] == "Strandnot"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["hi_collection"]["id"] == "hi_basemap:Strandnot"
    assert payload["hi_collection"]["items_url"] == STRANDNOT_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_strandnot_items(tmp_path: Path) -> None:
    source = HiFeaturesSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == STRANDNOT_URL
    assert result.table_id == "hi_basemap:Strandnot"
    assert result.http_status == 200
    assert result.counts.listed == 2
    # A beach-seine station is a thing in a place, and the record now carries
    # the place. The geometry comes from the feature it was published on,
    # copied as GeoJSON, never derived from the Lat/Long properties beside it.
    assert registry.observation_count() == 0
    rows = registry.list_records(DATASET_ID, kind="feature")
    by_name = {row["subject_label"]: row for row in rows}
    assert set(by_name) == {"Bergen", "Oslo"}
    assert all(row["measure"] is None and row["value_json"] is None for row in rows)
    assert json.loads(by_name["Bergen"]["geometry_json"]) == {
        "type": "Point",
        "coordinates": [5.3, 60.4],
    }
    assert by_name["Bergen"]["subject_code"] == "Strandnot.1"
    assert all(row["subject_scheme"] == "hi:hi_basemap:Strandnot" for row in rows)
    attributes = json.loads(by_name["Bergen"]["attributes_json"])
    assert attributes["Station"] == "BN-01"
    assert attributes["StationNumber"] == "12"
    assert "fid" not in attributes
    assert "geometry" not in attributes
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["request_url"] == STRANDNOT_URL for row in rows)
    registry.close()


def test_cells_copy_printed_properties_and_skip_geometry() -> None:
    cells = cells_from_hi(STRANDNOT_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "Description"
    assert value == "Bergen"
    assert dims["Station"] == "BN-01"
    assert "geometry" not in dims
    catalog = cells_from_hi(
        {
            "collections": [
                {"id": "hi_basemap:Strandnot", "title": "Strandnot", "extent": {"skip": True}}
            ]
        }
    )
    assert catalog == [("title", "Strandnot", {"id": "hi_basemap:Strandnot"})]
    named = cells_from_hi(
        {"features": [{"properties": {"navn": "Gytefelt hvitting", "omrade_nr": "1"}}]}
    )
    assert named == [("navn", "Gytefelt hvitting", {"omrade_nr": "1"})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_hi({"title": "Strandnot"})


def test_is_hi_url_accepts_only_kart_host() -> None:
    assert is_hi_url(STRANDNOT_URL)
    assert is_hi_url(LIST_URL)
    assert hi_table_id(STRANDNOT_URL) == "hi_basemap:Strandnot"
    assert printed_items_url(COLLECTIONS["collections"][2]) == STRANDNOT_URL
    assert printed_collections(COLLECTIONS)[2]["id"] == "hi_basemap:Strandnot"
    assert not is_hi_url("https://data.norge.no/datasets/x")
    assert not is_hi_url("https://www.hi.no/data/ogc/features/v1/collections")
    assert not is_hi_url("https://kart.hi.no/geoserver/wms")
    assert not is_hi_url(None)


def test_limit_and_offset_slice_printed_collections() -> None:
    source = HiFeaturesSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "hi_basemap:Mareano_observerte_vme"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["hi_basemap:Strandnot"]


def test_a_member_with_no_geometry_carries_none(tmp_path: Path) -> None:
    """A collections catalog and a bare feature have no place to carry.

    `None` rather than an empty shape: an empty geometry would read as "known
    to be nowhere", which is a different claim from "the publisher did not say".
    """

    body = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": "a", "properties": {"fid": "a", "navn": "Uten geometri"}},
            {
                "type": "Feature",
                "id": "b",
                "geometry": {"type": "Point", "coordinates": [10.7, 59.9]},
                "properties": {"fid": "b", "navn": "Med geometri"},
            },
        ],
    }
    paired = cells_and_geometry_from_hi(body)
    assert [geometry for _cell, geometry in paired] == [
        None,
        {"type": "Point", "coordinates": [10.7, 59.9]},
    ]
    # And the cells are exactly what the properties-only reader produces.
    assert [cell for cell, _geometry in paired] == cells_from_hi(body)


def test_a_batch_whose_members_share_an_id_is_refused(tmp_path: Path) -> None:
    """One row overwriting another still reports as a clean store.

    That is how 157 bathymetry contours became a single record: the count said
    157 listed, the table held one, and nothing anywhere said so. Refused only
    when the members differ -- a publisher repeating itself is handled below.
    """

    from public_data_agent.fetch import _store_records
    from public_data_agent.models import HarvestCounts

    registry = Registry(tmp_path / "registry.sqlite")
    try:
        registry.ensure_observation_dataset(
            dataset_id="hi:x", title="hi:x", publisher_name=None,
            access_path="https://example.test/x", license=None,
        )
        registry.conn.commit()
        dataset = {"id": "hi:x", "publisher_name": None, "license": None}
        run_id = registry.start_fetch_run(
            dataset_id="hi:x", table_id="x",
            request_url="https://example.test/x", request_method="TEST",
        )
        same = [
            {"id": "feature:hi:x:same", "kind": "feature", "subject_code": None,
             "subject_label": "Kontur", "attributes": {}},
            {"id": "feature:hi:x:same", "kind": "feature", "subject_code": None,
             "subject_label": "En annen kontur", "attributes": {}},
        ]
        with pytest.raises(ValueError, match="does not tell them apart"):
            _store_records(
                registry, dataset, run_id, records=same,
                retrieved_at="2026-10-21T00:00:00Z",
                request_url="https://example.test/x", http_status=200,
                counts=HarvestCounts(),
            )
        assert registry.list_records("hi:x") == []
    finally:
        registry.close()


def test_a_member_the_publisher_repeated_is_stored_once(tmp_path: Path) -> None:
    """671 features, 650 distinct: the 3000m contour collection repeats 21.

    Two members that agree on everything published -- properties and geometry
    both -- are one member as far as anything here can tell, and refusing the
    whole collection over them would lose 650 real contours.
    """

    from public_data_agent.fetch import _store_records
    from public_data_agent.models import HarvestCounts

    registry = Registry(tmp_path / "registry.sqlite")
    try:
        registry.ensure_observation_dataset(
            dataset_id="hi:y", title="hi:y", publisher_name=None,
            access_path="https://example.test/y", license=None,
        )
        registry.conn.commit()
        run_id = registry.start_fetch_run(
            dataset_id="hi:y", table_id="y",
            request_url="https://example.test/y", request_method="TEST",
        )
        repeated = {
            "id": "feature:hi:y:same", "kind": "feature", "subject_code": None,
            "subject_label": "Kontur", "attributes": {},
            "geometry": {"type": "Point", "coordinates": [5.0, 60.0]},
        }
        counts = HarvestCounts()
        _store_records(
            registry, {"id": "hi:y", "publisher_name": None, "license": None}, run_id,
            records=[dict(repeated), dict(repeated)],
            retrieved_at="2026-10-21T00:00:00Z",
            request_url="https://example.test/y", http_status=200, counts=counts,
        )
        assert len(registry.list_records("hi:y")) == 1
        assert counts.inserted == 1
    finally:
        registry.close()
