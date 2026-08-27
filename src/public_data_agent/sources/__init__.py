from __future__ import annotations

from pathlib import Path

from public_data_agent.sources.base import CatalogSource, SourceBase
from public_data_agent.sources.brreg import BrregEnhetsregisterSource
from public_data_agent.sources.datanorge import DataNorgeSource
from public_data_agent.sources.entur import EnturGbfsSource
from public_data_agent.sources.fhi import FhiStatistikkSource
from public_data_agent.sources.fiskeridir import FiskeridirVesselSource
from public_data_agent.sources.fixture import FixtureSource
from public_data_agent.sources.geonorge import GeonorgeKartkatalogSource
from public_data_agent.sources.hi import HiFeaturesSource
from public_data_agent.sources.kystverket import KystverketSource
from public_data_agent.sources.mattilsynet import MattilsynetPlantevernSource
from public_data_agent.sources.met import MetMetalertsSource
from public_data_agent.sources.miljodir import MiljodirVannmiljoSource
from public_data_agent.sources.nbr import NbrSource
from public_data_agent.sources.nibio import NibioWeatherSource
from public_data_agent.sources.nve import NveMagasinSource
from public_data_agent.sources.oslo import OsloStatbankSource
from public_data_agent.sources.ssb import SsbStatbankSource
from public_data_agent.sources.statnett import StatnettDriftsdataSource
from public_data_agent.sources.trondheim import TrondheimOpenDataSource
from public_data_agent.sources.udir import UdirNsrSource
from public_data_agent.sources.utdanning import UtdanningSource
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
    "fiskeridir",
    "statnett",
    "utdanning",
    "met",
    "hi",
    "kystverket",
    "nibio",
    "miljodir",
    "oslo",
    "trondheim",
    "nbr",
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
    if source_id == "fiskeridir":
        return FiskeridirVesselSource()
    if source_id == "statnett":
        return StatnettDriftsdataSource()
    if source_id == "utdanning":
        return UtdanningSource()
    if source_id == "met":
        return MetMetalertsSource()
    if source_id == "hi":
        return HiFeaturesSource()
    if source_id == "kystverket":
        return KystverketSource()
    if source_id == "nibio":
        return NibioWeatherSource()
    if source_id == "miljodir":
        return MiljodirVannmiljoSource()
    if source_id == "oslo":
        return OsloStatbankSource()
    if source_id == "trondheim":
        return TrondheimOpenDataSource()
    if source_id == "nbr":
        return NbrSource()
    raise ValueError(f"unknown source {source_id!r}; known: {', '.join(SOURCE_IDS)}")


__all__ = [
    "BrregEnhetsregisterSource",
    "CatalogSource",
    "DataNorgeSource",
    "EnturGbfsSource",
    "FhiStatistikkSource",
    "FiskeridirVesselSource",
    "FixtureSource",
    "GeonorgeKartkatalogSource",
    "HiFeaturesSource",
    "KystverketSource",
    "MattilsynetPlantevernSource",
    "MetMetalertsSource",
    "MiljodirVannmiljoSource",
    "NbrSource",
    "NibioWeatherSource",
    "NveMagasinSource",
    "OsloStatbankSource",
    "SsbStatbankSource",
    "SOURCE_IDS",
    "SourceBase",
    "StatnettDriftsdataSource",
    "TrondheimOpenDataSource",
    "UdirNsrSource",
    "UtdanningSource",
    "ValgresultatSource",
    "build_source",
]
