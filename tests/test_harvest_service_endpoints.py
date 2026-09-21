"""An API's own plumbing is not a dataset.

Harvesting every path an API spec lists catalogued health checks, status pages
and OGC conformance declarations as datasets -- 46 of them, 30 `healthz` alone.
"""

from __future__ import annotations

from pathlib import Path

from public_data_agent.harvest import harvest, is_service_endpoint
from public_data_agent.models import DatasetRef, HarvestedRecord
from public_data_agent.registry import Registry
from public_data_agent.sources.base import SourceBase

BASE = "https://api.met.no/weatherapi/airqualityforecast/0.1"


class ApiPathsSource(SourceBase):
    source_id = "apipaths"
    source_name = "A source that lists every path of an API"
    endpoints = (BASE,)
    ingest_reason = "test"

    def __init__(self, paths: list[str]) -> None:
        self.paths = paths

    def list_dataset_refs(self, *, limit=None, offset=0):
        return [DatasetRef(source_native_uri=f"{BASE}/{p}", source_native_id=p) for p in self.paths]

    def fetch_dataset(self, ref):
        url = ref.source_native_uri
        return HarvestedRecord(
            source_id=self.source_id, source_name=self.source_name, source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason, source_native_id=ref.source_native_id,
            source_native_uri=url, fetched_from=url,
            payload={"id": ref.source_native_id, "uri": url, "title": {"no": ref.source_native_id},
                     "distribution": [{"accessURL": [url]}]},
        )


def test_service_endpoints_are_recognised_by_their_last_segment() -> None:
    for segment in ("healthz", "ping", "status", "test", "conformance"):
        assert is_service_endpoint(f"{BASE}/{segment}")
        assert is_service_endpoint(f"{BASE}/{segment}/")
    assert is_service_endpoint("https://artskart.artsdatabanken.no/publicapi/api/PING")


def test_a_data_path_is_not_a_service_endpoint() -> None:
    assert not is_service_endpoint(f"{BASE}/aqi_description")
    assert not is_service_endpoint(f"{BASE}/test-results")
    assert not is_service_endpoint("https://kartkatalog.geonorge.no/Metadata/uuid/72f50772")
    assert not is_service_endpoint(None)


def test_harvest_skips_service_endpoints_and_counts_them(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        counts = harvest(registry, ApiPathsSource(["areas", "healthz", "status", "aqi_description"]))
        # The source printed four paths; two of them describe the API itself.
        assert counts.listed == 4
        assert counts.ignored == 2
        assert counts.inserted == 2
        stored = {row["source_native_id"] for row in registry.conn.execute("SELECT source_native_id FROM datasets")}
        assert stored == {"areas", "aqi_description"}
    finally:
        registry.close()
