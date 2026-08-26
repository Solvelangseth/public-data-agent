from __future__ import annotations

from typing import Iterable, Protocol

from public_data_agent.models import DatasetRef, HarvestedRecord


class CatalogSource(Protocol):
    """Replaceable ingest adapter. Data.norge is one implementation."""

    source_id: str
    source_name: str
    endpoints: tuple[str, ...]
    ingest_reason: str

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        """Return catalog members this source wants us to ingest."""

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        """Return the original harvested payload for one listing entry."""

    def fetch_many(self, refs: Iterable[DatasetRef]) -> list[HarvestedRecord]:
        """Fetch several records. May batch when the source supports it."""


class SourceBase:
    """Shared one-by-one fetch. Concrete adapters override fetch_many to batch."""

    def fetch_many(self, refs: Iterable[DatasetRef]) -> list[HarvestedRecord]:
        return [self.fetch_dataset(ref) for ref in refs]
