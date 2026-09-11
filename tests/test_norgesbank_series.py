"""Addressing one series inside a Norges Bank dataflow too wide to read whole.

MONEY_MARKET answers a one-period request with 34,906 cells, so it can only be
read by narrowing. SDMX narrows positionally -- a key like `B.USD.NOK.SP` puts
one code in each dimension slot -- and a miscounted dot comes back as a bare
404. These tests hold the pieces that make narrowing safe: the recorded order,
the key built from it, and the refusals that happen before anything is sent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.resource_index import resource_shape, shape_from_sdmx_serieskeys

FLOW_URL = "https://data.norges-bank.no/api/data/EXR?format=sdmx-json"
DATASET_ID = "norgesbank:EXR"

SERIESKEYS = {
    "data": {
        "structure": {
            "dimensions": {
                "series": [
                    {"id": "FREQ", "name": "Frequency", "values": [{"id": "B", "name": "Business"}]},
                    {"id": "BASE_CUR", "name": "Base currency", "values": [
                        {"id": "USD", "name": "US dollar"}, {"id": "EUR", "name": "Euro"},
                    ]},
                    {"id": "QUOTE_CUR", "name": "Quote currency", "values": [{"id": "NOK", "name": "Krone"}]},
                    {"id": "TENOR", "name": "Tenor", "values": [{"id": "SP", "name": "Spot"}]},
                ]
            }
        },
        "dataSets": [{"series": {"0:0:0:0": {}, "0:1:0:0": {}}}],
    }
}

ONE_CELL = {
    "data": {
        "structure": {
            "name": "Exchange rates",
            "dimensions": {
                "series": [
                    {"id": "FREQ", "values": [{"id": "B", "name": "Business"}]},
                    {"id": "BASE_CUR", "values": [{"id": "USD", "name": "US dollar"}]},
                    {"id": "QUOTE_CUR", "values": [{"id": "NOK", "name": "Krone"}]},
                    {"id": "TENOR", "values": [{"id": "SP", "name": "Spot"}]},
                ],
                "observation": [{"id": "TIME_PERIOD", "values": [{"id": "2026-09-11", "name": "2026-09-11"}]}],
            },
        },
        "dataSets": [{"series": {"0:0:0:0": {"observations": {"0": ["9.2999"]}}}}],
    }
}


class RecordingHttp:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        self.urls.append(url)
        return JsonResponse(status=200, url=url, body=ONE_CELL)


def _registry(tmp_path: Path, *, shaped: bool = True) -> Registry:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id=DATASET_ID, title="Valutakurser", publisher_name="Norges Bank",
        access_path=FLOW_URL, license=None,
    )
    if shaped:
        registry.set_resource_shape(DATASET_ID, shape_from_sdmx_serieskeys(SERIESKEYS))
    registry.conn.commit()
    return registry


def test_the_shape_keeps_key_order_not_alphabetical_order(tmp_path: Path) -> None:
    fields = shape_from_sdmx_serieskeys(SERIESKEYS)
    assert [(f["field_code"], f["position"]) for f in fields] == [
        ("FREQ", 0), ("BASE_CUR", 1), ("QUOTE_CUR", 2), ("TENOR", 3),
    ]
    registry = _registry(tmp_path)
    try:
        # Alphabetically BASE_CUR would come first; the key starts with FREQ.
        assert [f["field_code"] for f in registry.resource_fields(DATASET_ID)] == [
            "FREQ", "BASE_CUR", "QUOTE_CUR", "TENOR",
        ]
        shape = resource_shape(registry, DATASET_ID)
        assert [f["position"] for f in shape["fields"]] == [0, 1, 2, 3]
    finally:
        registry.close()


def test_a_named_field_without_a_position_keeps_alphabetical_order(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        registry.ensure_observation_dataset(
            dataset_id="ssbtable:1", title="t", publisher_name="SSB",
            access_path="https://data.ssb.no/api/v0/no/table/1", license=None,
        )
        registry.set_resource_shape("ssbtable:1", [
            {"field_code": "Tid", "values": []}, {"field_code": "Alder", "values": []},
        ])
        registry.conn.commit()
        assert [f["field_code"] for f in registry.resource_fields("ssbtable:1")] == ["Alder", "Tid"]
    finally:
        registry.close()


def test_selecting_a_dimension_writes_the_key_in_order(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    http = RecordingHttp()
    try:
        fetch_observations(
            registry, DATASET_ID, table_id="", http=http,
            select={"BASE_CUR": ["USD"], "observations": ["1"]},
        )
        # Unselected dimensions are empty slots, which SDMX reads as wildcards.
        assert http.urls[0] == (
            "https://data.norges-bank.no/api/data/EXR/.USD..?format=sdmx-json&lastNObservations=1"
        )
    finally:
        registry.close()


def test_several_values_for_one_dimension_are_joined_with_plus(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    http = RecordingHttp()
    try:
        fetch_observations(
            registry, DATASET_ID, table_id="", http=http,
            select={"BASE_CUR": ["USD", "EUR"], "TENOR": ["SP"]},
        )
        assert "/EXR/.USD+EUR..SP?" in http.urls[0]
    finally:
        registry.close()


def test_a_value_containing_the_key_separator_is_refused_before_sending(tmp_path: Path) -> None:
    # GOVT_PRIMARY_MARKET's COUPON codes look like "0.00000000". No key can carry
    # them, and the API answers the attempt with a bare 400.
    registry = _registry(tmp_path)
    http = RecordingHttp()
    try:
        with pytest.raises(ValueError, match="cannot carry"):
            fetch_observations(
                registry, DATASET_ID, table_id="", http=http, select={"TENOR": ["0.00000000"]}
            )
        assert http.urls == []
    finally:
        registry.close()


def test_a_code_the_flow_does_not_use_is_refused_when_the_list_is_complete(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    http = RecordingHttp()
    try:
        with pytest.raises(ValueError, match="does not use"):
            fetch_observations(
                registry, DATASET_ID, table_id="", http=http, select={"BASE_CUR": ["SEK"]}
            )
        assert http.urls == []
    finally:
        registry.close()


def test_an_incomplete_code_list_does_not_refuse(tmp_path: Path) -> None:
    # The index keeps at most 400 values per field; MONEY_MARKET's COLL_ISIN has
    # 1,046. A code missing from a truncated list may still be real.
    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE resource_fields SET value_count = 1046 WHERE dataset_id = ? AND field_code = 'BASE_CUR'",
        (DATASET_ID,),
    )
    registry.conn.commit()
    http = RecordingHttp()
    try:
        fetch_observations(
            registry, DATASET_ID, table_id="", http=http, select={"BASE_CUR": ["SEK"]}
        )
        assert "/EXR/.SEK..?" in http.urls[0]
    finally:
        registry.close()


def test_a_dimension_selection_needs_a_recorded_shape(tmp_path: Path) -> None:
    registry = _registry(tmp_path, shaped=False)
    try:
        with pytest.raises(ValueError, match="indexed"):
            fetch_observations(
                registry, DATASET_ID, table_id="", http=RecordingHttp(), select={"BASE_CUR": ["USD"]}
            )
    finally:
        registry.close()


def test_no_selection_still_reads_the_flow_as_listed(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    http = RecordingHttp()
    try:
        fetch_observations(registry, DATASET_ID, table_id="", http=http)
        assert http.urls[0] == f"{FLOW_URL}&lastNObservations=5"
    finally:
        registry.close()


def test_indexing_asks_for_series_keys_and_keeps_a_proven_capability(tmp_path: Path) -> None:
    """Re-reading a flow's shape must not undo what a fetch already proved.

    `set_capability` replaces the row. Indexing used to write the URL's
    `unverified` over a verified `observations` and drop the subject template,
    so recording a flow's dimensions made it unfindable and unaddressable.
    """

    from public_data_agent.resource_index import index_dataset

    class ShapeHttp:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
            self.urls.append(url)
            return JsonResponse(status=200, url=url, body=SERIESKEYS)

    registry = _registry(tmp_path, shaped=False)
    registry.set_capability(
        DATASET_ID,
        {
            "capability": "observations",
            "record_kind": "observation",
            "endpoint": FLOW_URL,
            "request_method": "GET",
            "subject_scheme": "SDMX series key",
            "subject_template": "https://data.norges-bank.no/api/data/EXR/{subject}",
            "verified_at": "2026-09-11T15:24:47Z",
            "verified_sample_count": 123,
        },
    )
    registry.conn.commit()
    http = ShapeHttp()
    try:
        index_dataset(registry, DATASET_ID, http=http)
        # No observations are requested to learn a flow's dimensions.
        assert http.urls == [f"{FLOW_URL}&detail=serieskeysonly"]
        capability = registry.get_capability(DATASET_ID)
        assert capability["capability"] == "observations"
        assert capability["verified_sample_count"] == 123
        assert capability["subject_template"].endswith("/EXR/{subject}")
        assert [f["field_code"] for f in registry.resource_fields(DATASET_ID)][0] == "FREQ"
    finally:
        registry.close()


def test_indexing_an_unproven_flow_does_not_claim_it_works(tmp_path: Path) -> None:
    from public_data_agent.resource_index import index_dataset

    class ShapeHttp:
        def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
            return JsonResponse(status=200, url=url, body=SERIESKEYS)

    registry = _registry(tmp_path, shaped=False)
    try:
        index_dataset(registry, DATASET_ID, http=ShapeHttp())
        capability = registry.get_capability(DATASET_ID)
        # A shape says what a flow claims to hold, not that reading it works.
        assert capability["capability"] == "unverified"
        assert capability["verified_at"] is None
    finally:
        registry.close()


def test_a_flow_too_wide_to_read_names_the_dimensions_that_narrow_it(tmp_path: Path, monkeypatch) -> None:
    """The error must be something a caller can act on.

    The MCP tool tells a caller to narrow by "the dimensions listed above". A
    made-up `series` entry there sent callers to a field this fetcher refuses.
    """

    import public_data_agent.fetch as fetch_module
    from public_data_agent.fetch import SelectionTooLarge

    monkeypatch.setattr(fetch_module, "NORGESBANK_MAX_CELLS", 0)
    registry = _registry(tmp_path)
    try:
        with pytest.raises(SelectionTooLarge) as caught:
            fetch_observations(
                registry, DATASET_ID, table_id="", http=RecordingHttp(),
                select={"BASE_CUR": ["USD"]},
            )
        listed = caught.value.dimensions
        assert [d["code"] for d in listed] == ["FREQ", "BASE_CUR", "QUOTE_CUR", "TENOR"]
        # A dimension already narrowed says so; the rest show their full width.
        assert {d["code"]: d["selected"] for d in listed}["BASE_CUR"] == 1
        assert {d["code"]: d["selected"] for d in listed}["FREQ"] == 1
        # Every listed code is one this fetcher accepts as a select key: using
        # it hits the same size refusal again rather than "does not filter on".
        for dimension in listed:
            value = "USD" if dimension["code"] == "BASE_CUR" else {
                "FREQ": "B", "QUOTE_CUR": "NOK", "TENOR": "SP",
            }[dimension["code"]]
            with pytest.raises(SelectionTooLarge):
                fetch_observations(
                    registry, DATASET_ID, table_id="", http=RecordingHttp(),
                    select={dimension["code"]: [value]},
                )
        assert registry.list_observations(DATASET_ID) == []
    finally:
        registry.close()
