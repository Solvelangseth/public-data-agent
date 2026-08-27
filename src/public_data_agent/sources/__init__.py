from __future__ import annotations

from pathlib import Path

from public_data_agent.sources.base import CatalogSource, SourceBase
from public_data_agent.sources.brreg import BrregEnhetsregisterSource
from public_data_agent.sources.datanorge import DataNorgeSource
from public_data_agent.sources.entur import EnturGbfsSource
from public_data_agent.sources.fhi import FhiStatistikkSource
from public_data_agent.sources.fixture import FixtureSource
from public_data_agent.sources.geonorge import GeonorgeKartkatalogSource
from public_data_agent.sources.mattilsynet import MattilsynetPlantevernSource
from public_data_agent.sources.nve import NveMagasinSource
from public_data_agent.sources.ssb import SsbStatbankSource
from public_data_agent.sources.udir import UdirNsrSource
from public_data_agent.sources.valg import ValgresultatSource

SOURCE_IDS = (
    "datanorge",
    "fixture",
    "ssb",
    "geonorge",
    "nve",
    "brreg",
    "valg",
    "fhi",
    "mattilsynet",
    "udir",
    "entur",
)


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
    if source_id == "fhi":
        return FhiStatistikkSource()
    if source_id == "mattilsynet":
        return MattilsynetPlantevernSource()
    if source_id == "udir":
        return UdirNsrSource()
    if source_id == "entur":
        return EnturGbfsSource()
    raise ValueError(f"unknown source {source_id!r}; known: {', '.join(SOURCE_IDS)}")


__all__ = [
    "BrregEnhetsregisterSource",
    "CatalogSource",
    "DataNorgeSource",
    "EnturGbfsSource",
    "FhiStatistikkSource",
    "FixtureSource",
    "GeonorgeKartkatalogSource",
    "MattilsynetPlantevernSource",
    "NveMagasinSource",
    "SsbStatbankSource",
    "SOURCE_IDS",
    "SourceBase",
    "UdirNsrSource",
    "ValgresultatSource",
    "build_source",
]
