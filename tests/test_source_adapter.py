from __future__ import annotations

from typing import Iterable

from public_data_agent.harvest import harvest
from public_data_agent.models import DatasetRef, HarvestedRecord
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.base import SourceBase
from public_data_agent.sources.datanorge import DataNorgeSource


def test_datanorge_is_one_registered_adapter() -> None:
    assert "datanorge" in SOURCE_IDS
    source = build_source("datanorge")
    assert isinstance(source, DataNorgeSource)
    assert source.source_id == "datanorge"
    assert source.endpoints[0].startswith("https://sparql.fellesdatakatalog.digdir.no")
    assert source.endpoints[1].startswith("https://resource.api.fellesdatakatalog.digdir.no")
    assert "dcat:Dataset" in source.ingest_reason


class ExtraSource(SourceBase):
    source_id = "extra"
    source_name = "Extra catalog"
    endpoints = ("https://example.org/extra",)
    ingest_reason = "listed in the extra test catalog"

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        refs = [
            DatasetRef(
                source_native_uri="https://example.org/datasets/a",
                source_native_id="a",
                catalog_modified="2026-01-01T00:00:00Z",
            )
        ]
        return refs[offset : None if limit is None else offset + limit]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=ref.source_native_uri,
            fetched_from="https://example.org/extra/a",
            payload={
                "id": "a",
                "uri": ref.source_native_uri,
                "title": {"en": "Extra dataset"},
                "publisher": {"id": "org", "name": "Example org", "uri": "https://example.org/org"},
                "distribution": [
                    {
                        "accessURL": ["https://example.org/a.csv"],
                        "license": [{"uri": "https://example.org/license"}],
                        "fdkFormat": [
                            {"code": "text/csv", "name": "csv", "type": "MEDIA_TYPE"},
                            {"code": "CSV", "name": "CSV", "type": "FILE_TYPE"},
                        ],
                    }
                ],
            },
            catalog_modified=ref.catalog_modified,
        )

    def fetch_many(self, refs: Iterable[DatasetRef]) -> list[HarvestedRecord]:
        return [self.fetch_dataset(ref) for ref in refs]


def test_harvest_accepts_a_non_datanorge_adapter(tmp_path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, ExtraSource())
    assert counts.inserted == 1
    row = registry.get_dataset("extra:a")
    assert row is not None
    assert row["source_id"] == "extra"
    assert row["source_name"] == "Extra catalog"
    assert row["ingest_reason"] == "listed in the extra test catalog"
    assert row["license"] == "https://example.org/license"
    registry.close()
