from __future__ import annotations

from pathlib import Path

from public_data_agent.sources.base import CatalogSource, SourceBase
from public_data_agent.sources.brreg import BrregEnhetsregisterSource
from public_data_agent.sources.datanorge import DataNorgeSource
from public_data_agent.sources.fixture import FixtureSource
from public_data_agent.sources.geonorge import GeonorgeKartkatalogSource
from public_data_agent.sources.nve import NveMagasinSource
from public_data_agent.sources.ssb import SsbStatbankSource
from public_data_agent.sources.valg import ValgresultatSource

SOURCE_IDS = ("datanorge", "fixture", "ssb", "geonorge", "nve", "brreg", "valg")


def build_source(source_id: str, *, fixtures: Path | None = None) -> CatalogSource:
    if source_id == "datanorge":
        return DataNorgeSource()
    if source_id == "fixture":
        if fixtures is None:
            raise ValueError("fixture source needs --fixtures DIR")
        return FixtureSource.from_directory(fixtures)
    if source_id == "ssb":
        return SsbStatbankSource()
    if source_id == "geonorge":
        return GeonorgeKartkatalogSource()
    if source_id == "nve":
        return NveMagasinSource()
    if source_id == "brreg":
        return BrregEnhetsregisterSource()
    if source_id == "valg":
        return ValgresultatSource()
    raise ValueError(f"unknown source {source_id!r}; known: {', '.join(SOURCE_IDS)}")


__all__ = [
    "BrregEnhetsregisterSource",
    "CatalogSource",
    "DataNorgeSource",
    "FixtureSource",
    "GeonorgeKartkatalogSource",
    "NveMagasinSource",
    "SsbStatbankSource",
    "SOURCE_IDS",
    "SourceBase",
    "ValgresultatSource",
    "build_source",
]
