from __future__ import annotations

from pathlib import Path

from public_data_agent.sources.airquality import AirqualitySource
from public_data_agent.sources.aviationforecast import AviationforecastSource
from public_data_agent.sources.aqua import AquaSource
from public_data_agent.sources.arcticsdi import ArcticsdiSource
from public_data_agent.sources.artskart import ArtskartSource
from public_data_agent.sources.baf import BafSource
from public_data_agent.sources.base import CatalogSource, SourceBase
from public_data_agent.sources.brreg import BrregEnhetsregisterSource
from public_data_agent.sources.buyer import BuyerSource
from public_data_agent.sources.cristin import CristinSource
from public_data_agent.sources.datanorge import DataNorgeSource
from public_data_agent.sources.elcert import ElcertSource
from public_data_agent.sources.entur import EnturGbfsSource
from public_data_agent.sources.envreportreg import EnvreportregSource
from public_data_agent.sources.fhi import FhiStatistikkSource
from public_data_agent.sources.fiskeridir import FiskeridirVesselSource
from public_data_agent.sources.fiskerigis import FiskerigisSource
from public_data_agent.sources.fixture import FixtureSource
from public_data_agent.sources.frivillig import FrivilligSource
from public_data_agent.sources.geonorge import GeonorgeKartkatalogSource
from public_data_agent.sources.grep import GrepSource
from public_data_agent.sources.georegister import GeoregisterSource
from public_data_agent.sources.geosatellite import GeosatelliteSource
from public_data_agent.sources.gribfiles import GribfilesSource
from public_data_agent.sources.havnedata import HavnedataSource
from public_data_agent.sources.hi import HiFeaturesSource
from public_data_agent.sources.hicoverages import HicoveragesSource
from public_data_agent.sources.himaps import HimapsSource
from public_data_agent.sources.histyles import HistylesSource
from public_data_agent.sources.hitiles import HitilesSource
from public_data_agent.sources.hoydedata import HoydedataSource
from public_data_agent.sources.hoydegis import HoydegisSource
from public_data_agent.sources.icemap import IcemapSource
from public_data_agent.sources.isobaricgrib import IsobaricgribSource
from public_data_agent.sources.kommuneinfo import KommuneinfoSource
from public_data_agent.sources.kvwms import KvwmsSource
from public_data_agent.sources.kystverket import KystverketSource
from public_data_agent.sources.kystwfs import KystwfsSource
from public_data_agent.sources.ldirwms import LdirwmsSource
from public_data_agent.sources.lister import ListerSource
from public_data_agent.sources.locationforecast import LocationforecastSource
from public_data_agent.sources.mattilsynet import MattilsynetPlantevernSource
from public_data_agent.sources.met import MetMetalertsSource
from public_data_agent.sources.metgc import MetgcSource
from public_data_agent.sources.metgm import MetgmSource
from public_data_agent.sources.miljodir import MiljodirVannmiljoSource
from public_data_agent.sources.miljogis import MiljogisSource
from public_data_agent.sources.miljorapporter import MiljorapporterSource
from public_data_agent.sources.nbr import NbrSource
from public_data_agent.sources.nfr import NfrSource
from public_data_agent.sources.ngu import NguSource
from public_data_agent.sources.nguwms import NguwmsSource
from public_data_agent.sources.ncagalewarnings import NcagalewarningsSource
from public_data_agent.sources.nibio import NibioWeatherSource
from public_data_agent.sources.nibiowms import NibiowmsSource
from public_data_agent.sources.nin import NinSource
from public_data_agent.sources.nlaroutes import NlaroutesSource
from public_data_agent.sources.nor import NorSource
from public_data_agent.sources.norskelos import NorskelosSource
from public_data_agent.sources.npr import NprSource
from public_data_agent.sources.norgesbank import NorgesBankSource
from public_data_agent.sources.nbcodelist import NbcodelistSource
from public_data_agent.sources.nortaxa import NortaxaSource
from public_data_agent.sources.nowcast import NowcastSource
from public_data_agent.sources.ogccoverages import OgccoveragesSource
from public_data_agent.sources.omregning import OmregningSource
from public_data_agent.sources.npolar import NpolarSource
from public_data_agent.sources.npigis import NpigisSource
from public_data_agent.sources.npiintern import NpiinternSource
from public_data_agent.sources.npitema import NpitemaSource
from public_data_agent.sources.nve import NveMagasinSource
from public_data_agent.sources.nve2gis import Nve2gisSource
from public_data_agent.sources.nvemap import NvemapSource
from public_data_agent.sources.navwarnings import NavwarningsSource
from public_data_agent.sources.nvegis import NvegisSource
from public_data_agent.sources.nxr import NxrSource
from public_data_agent.sources.nytek import NytekSource
from public_data_agent.sources.oceanforecast import OceanforecastSource
from public_data_agent.sources.offshoremaps import OffshoremapsSource
from public_data_agent.sources.opencom import OpencomSource
from public_data_agent.sources.polarsatellite import PolarsatelliteSource
from public_data_agent.sources.portal import PortalSource
from public_data_agent.sources.radar import RadarSource
from public_data_agent.sources.ragis import RagisSource
from public_data_agent.sources.rawms import RawmsSource
from public_data_agent.sources.regnskap import RegnskapSource
from public_data_agent.sources.regobs import RegobsSource
from public_data_agent.sources.research import ResearchSource
from public_data_agent.sources.riksantikvaren import RiksantikvarenSource
from public_data_agent.sources.sandnes import SandnesSource
from public_data_agent.sources.routeforecast import RouteforecastSource
from public_data_agent.sources.sigcharts import SigchartsSource
from public_data_agent.sources.sigmets import SigmetsSource
from public_data_agent.sources.sikt import SiktSource
from public_data_agent.sources.sodir import SodirSource
from public_data_agent.sources.soundprofile import SoundprofileSource
from public_data_agent.sources.oslo import OsloStatbankSource
from public_data_agent.sources.oslofjord import OslofjordSource
from public_data_agent.sources.spotwind import SpotwindSource
from public_data_agent.sources.ssb import SsbStatbankSource
from public_data_agent.sources.ssbv2 import Ssbv2Source
from public_data_agent.sources.statnett import StatnettDriftsdataSource
from public_data_agent.sources.stedsnavn import StedsnavnSource
from public_data_agent.sources.stormflo import StormfloSource
from public_data_agent.sources.stortinget import StortingetSource
from public_data_agent.sources.subjectiveforecast import SubjectiveforecastSource
from public_data_agent.sources.subseasonal import SubseasonalSource
from public_data_agent.sources.sunrise import SunriseSource
from public_data_agent.sources.tafmetar import TafmetarSource
from public_data_agent.sources.textforecast import TextforecastSource
from public_data_agent.sources.tidalwater import TidalwaterSource
from public_data_agent.sources.transformering import TransformeringSource
from public_data_agent.sources.trondheim import TrondheimOpenDataSource
from public_data_agent.sources.turbulence import TurbulenceSource
from public_data_agent.sources.udir import UdirNsrSource
from public_data_agent.sources.utdanning import UtdanningSource
from public_data_agent.sources.valg import ValgresultatSource
from public_data_agent.sources.vannkraft import VannkraftSource
from public_data_agent.sources.vegogc import VegogcSource
from public_data_agent.sources.vegvesen import VegvesenSource
from public_data_agent.sources.vindkraft import VindkraftSource
from public_data_agent.sources.volcanicashforecast import VolcanicashforecastSource

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
    "norgesbank",
    "npolar",
    "stedsnavn",
    "sikt",
    "vegvesen",
    "buyer",
    "nor",
    "nytek",
    "npr",
    "nfr",
    "nxr",
    "baf",
    "aqua",
    "research",
    "portal",
    "opencom",
    "sodir",
    "kommuneinfo",
    "nin",
    "ngu",
    "hoydedata",
    "nowcast",
    "riksantikvaren",
    "airquality",
    "tidalwater",
    "oceanforecast",
    "sunrise",
    "radar",
    "spotwind",
    "textforecast",
    "icemap",
    "ncagalewarnings",
    "tafmetar",
    "subseasonal",
    "geosatellite",
    "metgm",
    "subjectiveforecast",
    "polarsatellite",
    "transformering",
    "soundprofile",
    "gribfiles",
    "metgc",
    "oslofjord",
    "isobaricgrib",
    "offshoremaps",
    "turbulence",
    "nlaroutes",
    "sigcharts",
    "volcanicashforecast",
    "routeforecast",
    "norskelos",
    "locationforecast",
    "georegister",
    "nortaxa",
    "artskart",
    "lister",
    "ogccoverages",
    "regnskap",
    "cristin",
    "omregning",
    "hicoverages",
    "envreportreg",
    "himaps",
    "stortinget",
    "histyles",
    "hitiles",
    "miljorapporter",
    "nvegis",
    "navwarnings",
    "havnedata",
    "miljogis",
    "hoydegis",
    "npigis",
    "nve2gis",
    "npitema",
    "nvemap",
    "arcticsdi",
    "fiskerigis",
    "npiintern",
    "ssbv2",
    "ragis",
    "nibiowms",
    "regobs",
    "sigmets",
    "grep",
    "kvwms",
    "aviationforecast",
    "vannkraft",
    "vindkraft",
    "vegogc",
    "rawms",
    "elcert",
    "ldirwms",
    "frivillig",
    "sandnes",
    "nguwms",
    "stormflo",
    "kystwfs",
    "nbcodelist",
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
    if source_id == "norgesbank":
        return NorgesBankSource()
    if source_id == "npolar":
        return NpolarSource()
    if source_id == "stedsnavn":
        return StedsnavnSource()
    if source_id == "sikt":
        return SiktSource()
    if source_id == "vegvesen":
        return VegvesenSource()
    if source_id == "buyer":
        return BuyerSource()
    if source_id == "nor":
        return NorSource()
    if source_id == "nytek":
        return NytekSource()
    if source_id == "npr":
        return NprSource()
    if source_id == "nfr":
        return NfrSource()
    if source_id == "nxr":
        return NxrSource()
    if source_id == "baf":
        return BafSource()
    if source_id == "aqua":
        return AquaSource()
    if source_id == "research":
        return ResearchSource()
    if source_id == "portal":
        return PortalSource()
    if source_id == "opencom":
        return OpencomSource()
    if source_id == "sodir":
        return SodirSource()
    if source_id == "kommuneinfo":
        return KommuneinfoSource()
    if source_id == "nin":
        return NinSource()
    if source_id == "ngu":
        return NguSource()
    if source_id == "hoydedata":
        return HoydedataSource()
    if source_id == "nowcast":
        return NowcastSource()
    if source_id == "riksantikvaren":
        return RiksantikvarenSource()
    if source_id == "airquality":
        return AirqualitySource()
    if source_id == "tidalwater":
        return TidalwaterSource()
    if source_id == "oceanforecast":
        return OceanforecastSource()
    if source_id == "sunrise":
        return SunriseSource()
    if source_id == "radar":
        return RadarSource()
    if source_id == "spotwind":
        return SpotwindSource()
    if source_id == "textforecast":
        return TextforecastSource()
    if source_id == "icemap":
        return IcemapSource()
    if source_id == "ncagalewarnings":
        return NcagalewarningsSource()
    if source_id == "tafmetar":
        return TafmetarSource()
    if source_id == "subseasonal":
        return SubseasonalSource()
    if source_id == "geosatellite":
        return GeosatelliteSource()
    if source_id == "metgm":
        return MetgmSource()
    if source_id == "subjectiveforecast":
        return SubjectiveforecastSource()
    if source_id == "polarsatellite":
        return PolarsatelliteSource()
    if source_id == "transformering":
        return TransformeringSource()
    if source_id == "soundprofile":
        return SoundprofileSource()
    if source_id == "gribfiles":
        return GribfilesSource()
    if source_id == "metgc":
        return MetgcSource()
    if source_id == "oslofjord":
        return OslofjordSource()
    if source_id == "isobaricgrib":
        return IsobaricgribSource()
    if source_id == "offshoremaps":
        return OffshoremapsSource()
    if source_id == "turbulence":
        return TurbulenceSource()
    if source_id == "nlaroutes":
        return NlaroutesSource()
    if source_id == "sigcharts":
        return SigchartsSource()
    if source_id == "volcanicashforecast":
        return VolcanicashforecastSource()
    if source_id == "routeforecast":
        return RouteforecastSource()
    if source_id == "norskelos":
        return NorskelosSource()
    if source_id == "locationforecast":
        return LocationforecastSource()
    if source_id == "georegister":
        return GeoregisterSource()
    if source_id == "nortaxa":
        return NortaxaSource()
    if source_id == "artskart":
        return ArtskartSource()
    if source_id == "lister":
        return ListerSource()
    if source_id == "ogccoverages":
        return OgccoveragesSource()
    if source_id == "regnskap":
        return RegnskapSource()
    if source_id == "cristin":
        return CristinSource()
    if source_id == "omregning":
        return OmregningSource()
    if source_id == "hicoverages":
        return HicoveragesSource()
    if source_id == "envreportreg":
        return EnvreportregSource()
    if source_id == "himaps":
        return HimapsSource()
    if source_id == "stortinget":
        return StortingetSource()
    if source_id == "histyles":
        return HistylesSource()
    if source_id == "hitiles":
        return HitilesSource()
    if source_id == "miljorapporter":
        return MiljorapporterSource()
    if source_id == "nvegis":
        return NvegisSource()
    if source_id == "navwarnings":
        return NavwarningsSource()
    if source_id == "havnedata":
        return HavnedataSource()
    if source_id == "miljogis":
        return MiljogisSource()
    if source_id == "hoydegis":
        return HoydegisSource()
    if source_id == "npigis":
        return NpigisSource()
    if source_id == "nve2gis":
        return Nve2gisSource()
    if source_id == "npitema":
        return NpitemaSource()
    if source_id == "nvemap":
        return NvemapSource()
    if source_id == "arcticsdi":
        return ArcticsdiSource()
    if source_id == "fiskerigis":
        return FiskerigisSource()
    if source_id == "npiintern":
        return NpiinternSource()
    if source_id == "ssbv2":
        return Ssbv2Source()
    if source_id == "ragis":
        return RagisSource()
    if source_id == "nibiowms":
        return NibiowmsSource()
    if source_id == "regobs":
        return RegobsSource()
    if source_id == "sigmets":
        return SigmetsSource()
    if source_id == "grep":
        return GrepSource()
    if source_id == "kvwms":
        return KvwmsSource()
    if source_id == "aviationforecast":
        return AviationforecastSource()
    if source_id == "vannkraft":
        return VannkraftSource()
    if source_id == "vindkraft":
        return VindkraftSource()
    if source_id == "vegogc":
        return VegogcSource()
    if source_id == "rawms":
        return RawmsSource()
    if source_id == "elcert":
        return ElcertSource()
    if source_id == "ldirwms":
        return LdirwmsSource()
    if source_id == "frivillig":
        return FrivilligSource()
    if source_id == "sandnes":
        return SandnesSource()
    if source_id == "nguwms":
        return NguwmsSource()
    if source_id == "stormflo":
        return StormfloSource()
    if source_id == "kystwfs":
        return KystwfsSource()
    if source_id == "nbcodelist":
        return NbcodelistSource()
    raise ValueError(f"unknown source {source_id!r}; known: {', '.join(SOURCE_IDS)}")


__all__ = [
    "AirqualitySource",
    "AviationforecastSource",
    "AquaSource",
    "ArcticsdiSource",
    "ArtskartSource",
    "BafSource",
    "BrregEnhetsregisterSource",
    "BuyerSource",
    "CatalogSource",
    "CristinSource",
    "DataNorgeSource",
    "ElcertSource",
    "EnturGbfsSource",
    "EnvreportregSource",
    "FhiStatistikkSource",
    "FiskeridirVesselSource",
    "FiskerigisSource",
    "FixtureSource",
    "FrivilligSource",
    "GeonorgeKartkatalogSource",
    "GrepSource",
    "GeoregisterSource",
    "GeosatelliteSource",
    "GribfilesSource",
    "HavnedataSource",
    "HiFeaturesSource",
    "HicoveragesSource",
    "HimapsSource",
    "HistylesSource",
    "HitilesSource",
    "HoydedataSource",
    "HoydegisSource",
    "IcemapSource",
    "IsobaricgribSource",
    "KommuneinfoSource",
    "KvwmsSource",
    "KystverketSource",
    "KystwfsSource",
    "LdirwmsSource",
    "ListerSource",
    "LocationforecastSource",
    "MattilsynetPlantevernSource",
    "MetMetalertsSource",
    "MetgcSource",
    "MetgmSource",
    "MiljodirVannmiljoSource",
    "MiljogisSource",
    "MiljorapporterSource",
    "NbrSource",
    "NcagalewarningsSource",
    "NfrSource",
    "NguSource",
    "NguwmsSource",
    "NibioWeatherSource",
    "NibiowmsSource",
    "NinSource",
    "NlaroutesSource",
    "NorSource",
    "NorskelosSource",
    "NprSource",
    "NorgesBankSource",
    "NbcodelistSource",
    "NortaxaSource",
    "NowcastSource",
    "OgccoveragesSource",
    "OmregningSource",
    "NpolarSource",
    "NpigisSource",
    "NpiinternSource",
    "NpitemaSource",
    "NveMagasinSource",
    "Nve2gisSource",
    "NvemapSource",
    "NavwarningsSource",
    "NvegisSource",
    "NxrSource",
    "NytekSource",
    "OceanforecastSource",
    "OffshoremapsSource",
    "OpencomSource",
    "PolarsatelliteSource",
    "PortalSource",
    "RadarSource",
    "RagisSource",
    "RawmsSource",
    "RegnskapSource",
    "RegobsSource",
    "ResearchSource",
    "RiksantikvarenSource",
    "RouteforecastSource",
    "SandnesSource",
    "SigchartsSource",
    "SigmetsSource",
    "SiktSource",
    "SodirSource",
    "SoundprofileSource",
    "OslofjordSource",
    "OsloStatbankSource",
    "SpotwindSource",
    "SsbStatbankSource",
    "Ssbv2Source",
    "SOURCE_IDS",
    "SourceBase",
    "StatnettDriftsdataSource",
    "StedsnavnSource",
    "StormfloSource",
    "StortingetSource",
    "SubjectiveforecastSource",
    "SubseasonalSource",
    "SunriseSource",
    "TafmetarSource",
    "TextforecastSource",
    "TidalwaterSource",
    "TransformeringSource",
    "TrondheimOpenDataSource",
    "TurbulenceSource",
    "UdirNsrSource",
    "UtdanningSource",
    "ValgresultatSource",
    "VannkraftSource",
    "VegogcSource",
    "VegvesenSource",
    "VindkraftSource",
    "VolcanicashforecastSource",
    "build_source",
]
