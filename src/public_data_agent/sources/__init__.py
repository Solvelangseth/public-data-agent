from __future__ import annotations

from pathlib import Path

from public_data_agent.sources.base import CatalogSource, SourceBase
from public_data_agent.sources.datanorge import DataNorgeSource
from public_data_agent.sources.fixture import FixtureSource
from public_data_agent.sources.ssb import SsbStatbankSource

SOURCE_IDS = ("datanorge", "fixture", "ssb")


def build_source(source_id: str, *, fixtures: Path | None = None) -> CatalogSource:
    if source_id == "datanorge":
        return DataNorgeSource()
    if source_id == "fixture":
        if fixtures is None:
            raise ValueError("fixture source needs --fixtures DIR")
        return FixtureSource.from_directory(fixtures)
    if source_id == "ssb":
        return SsbStatbankSource()
    raise ValueError(f"unknown source {source_id!r}; known: {', '.join(SOURCE_IDS)}")


__all__ = [
    "CatalogSource",
    "DataNorgeSource",
    "FixtureSource",
    "SsbStatbankSource",
    "SOURCE_IDS",
    "SourceBase",
    "build_source",
]
