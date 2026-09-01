from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse

from public_data_agent.brreg_hal import brreg_table_id, cells_from_brreg, is_brreg_url
from public_data_agent.geonorge_rest import (
    cells_from_geonorge,
    collection_request_url,
    geonorge_table_id,
    is_geonorge_rest_url,
    openapi_url,
)
from public_data_agent.http_util import HttpClient, JsonResponse
from public_data_agent.models import HarvestCounts
from public_data_agent.registry import Registry, utc_now
from public_data_agent.sources.nve import (
    cells_from_nve,
    is_nve_magasin_url,
    nve_table_id,
    requestable_url,
)
from public_data_agent.sources.fhi import (
    cells_from_fhi,
    fhi_table_id,
    is_fhi_url,
)
from public_data_agent.sources.mattilsynet import (
    cells_from_mattilsynet,
    is_mattilsynet_url,
    mattilsynet_table_id,
)
from public_data_agent.sources.entur import (
    VEHICLE_TYPES_FEED,
    cells_from_entur,
    entur_table_id,
    is_entur_gbfs_url,
    printed_feed_url,
)
from public_data_agent.sources.aqua import (
    aqua_table_id,
    cells_from_aqua,
    is_aqua_url,
)
from public_data_agent.sources.buyer import (
    buyer_table_id,
    cells_from_buyer,
    is_buyer_url,
)
from public_data_agent.sources.nytek import (
    cells_from_nytek,
    is_nytek_url,
    nytek_table_id,
)
from public_data_agent.sources.opencom import (
    cells_from_opencom,
    is_opencom_url,
    opencom_table_id,
)
from public_data_agent.sources.portal import (
    cells_from_portal,
    is_portal_url,
    portal_table_id,
)
from public_data_agent.sources.sodir import (
    cells_from_sodir,
    is_sodir_url,
    sodir_table_id,
)
from public_data_agent.sources.ragis import (
    cells_from_ragis,
    is_ragis_url,
    ragis_table_id,
)
from public_data_agent.sources.ldirwms import (
    cells_from_ldirwms,
    is_ldirwms_url,
    ldirwms_table_id,
)
from public_data_agent.sources.mdirgis import (
    cells_from_mdirgis,
    is_mdirgis_url,
    mdirgis_table_id,
)
from public_data_agent.sources.nordatlas import (
    cells_from_nordatlas,
    is_nordatlas_url,
    nordatlas_table_id,
)
from public_data_agent.sources.mdirwms import (
    cells_from_mdirwms,
    is_mdirwms_url,
    mdirwms_table_id,
)
from public_data_agent.sources.mattilsyn import (
    cells_from_mattilsyn,
    is_mattilsyn_url,
    mattilsyn_table_id,
)
from public_data_agent.sources.fdirwms import (
    cells_from_fdirwms,
    fdirwms_table_id,
    is_fdirwms_url,
)
from public_data_agent.sources.hiwms import (
    cells_from_hiwms,
    hiwms_table_id,
    is_hiwms_url,
)
from public_data_agent.sources.vegwms import (
    cells_from_vegwms,
    is_vegwms_url,
    vegwms_table_id,
)
from public_data_agent.sources.bwgis import (
    cells_from_bwgis,
    bwgis_table_id,
    is_bwgis_url,
)
from public_data_agent.sources.fbgis import (
    cells_from_fbgis,
    fbgis_table_id,
    is_fbgis_url,
)
from public_data_agent.sources.barmark import (
    cells_from_barmark,
    barmark_table_id,
    is_barmark_url,
)
from public_data_agent.sources.kystwfs import (
    cells_from_kystwfs,
    is_kystwfs_url,
    kystwfs_table_id,
)
from public_data_agent.sources.riksantikvaren import (
    cells_from_riksantikvaren,
    is_riksantikvaren_url,
    riksantikvaren_table_id,
)
from public_data_agent.sources.nin import (
    cells_from_nin,
    is_nin_url,
    nin_table_id,
)
from public_data_agent.sources.ngu import (
    cells_from_ngu,
    is_ngu_url,
    ngu_table_id,
)
from public_data_agent.sources.nguminer import (
    cells_from_nguminer,
    is_nguminer_url,
    nguminer_table_id,
)
from public_data_agent.sources.nguwms import (
    cells_from_nguwms,
    is_nguwms_url,
    nguwms_table_id,
)
from public_data_agent.sources.airquality import (
    airquality_table_id,
    cells_from_airquality,
    is_airquality_url,
)
from public_data_agent.sources.nowcast import (
    cells_from_nowcast,
    is_nowcast_url,
    nowcast_table_id,
)
from public_data_agent.sources.ncagalewarnings import (
    cells_from_ncagalewarnings,
    is_ncagalewarnings_url,
    ncagalewarnings_table_id,
)
from public_data_agent.sources.subseasonal import (
    cells_from_subseasonal,
    is_subseasonal_url,
    subseasonal_table_id,
)
from public_data_agent.sources.metgm import (
    cells_from_metgm,
    is_metgm_url,
    metgm_table_id,
)
from public_data_agent.sources.polarsatellite import (
    cells_from_polarsatellite,
    is_polarsatellite_url,
    polarsatellite_table_id,
)
from public_data_agent.sources.soundprofile import (
    cells_from_soundprofile,
    is_soundprofile_url,
    soundprofile_table_id,
)
from public_data_agent.sources.gribfiles import (
    cells_from_gribfiles,
    gribfiles_table_id,
    is_gribfiles_url,
)
from public_data_agent.sources.metgc import (
    cells_from_metgc,
    is_metgc_url,
    metgc_table_id,
)
from public_data_agent.sources.oslofjord import (
    cells_from_oslofjord,
    is_oslofjord_url,
    oslofjord_table_id,
)
from public_data_agent.sources.isobaricgrib import (
    cells_from_isobaricgrib,
    is_isobaricgrib_url,
    isobaricgrib_table_id,
)
from public_data_agent.sources.offshoremaps import (
    cells_from_offshoremaps,
    is_offshoremaps_url,
    offshoremaps_table_id,
)
from public_data_agent.sources.turbulence import (
    cells_from_turbulence,
    is_turbulence_url,
    turbulence_table_id,
)
from public_data_agent.sources.nlaroutes import (
    cells_from_nlaroutes,
    is_nlaroutes_url,
    nlaroutes_table_id,
)
from public_data_agent.sources.sigcharts import (
    cells_from_sigcharts,
    is_sigcharts_url,
    sigcharts_table_id,
)
from public_data_agent.sources.sigmets import (
    cells_from_sigmets,
    is_sigmets_url,
    sigmets_table_id,
)
from public_data_agent.sources.volcanicashforecast import (
    cells_from_volcanicashforecast,
    is_volcanicashforecast_url,
    volcanicashforecast_table_id,
)
from public_data_agent.sources.routeforecast import (
    cells_from_routeforecast,
    is_routeforecast_url,
    routeforecast_table_id,
)
from public_data_agent.sources.norskelos import (
    cells_from_norskelos,
    is_norskelos_url,
    norskelos_table_id,
)
from public_data_agent.sources.locationforecast import (
    cells_from_locationforecast,
    is_locationforecast_url,
    locationforecast_table_id,
)
from public_data_agent.sources.georegister import (
    cells_from_georegister,
    georegister_table_id,
    is_georegister_url,
)
from public_data_agent.sources.nortaxa import (
    cells_from_nortaxa,
    is_nortaxa_url,
    nortaxa_table_id,
)
from public_data_agent.sources.artskart import (
    artskart_table_id,
    cells_from_artskart,
    is_artskart_url,
)
from public_data_agent.sources.lister import (
    cells_from_lister,
    is_lister_url,
    lister_table_id,
)
from public_data_agent.sources.ogccoverages import (
    cells_from_ogccoverages,
    is_ogccoverages_url,
    ogccoverages_table_id,
)
from public_data_agent.sources.regnskap import (
    cells_from_regnskap,
    is_regnskap_url,
    regnskap_table_id,
)
from public_data_agent.sources.crinst import (
    cells_from_crinst,
    crinst_table_id,
    is_crinst_url,
)
from public_data_agent.sources.crproj import (
    cells_from_crproj,
    crproj_table_id,
    is_crproj_url,
)
from public_data_agent.sources.crunit import (
    cells_from_crunit,
    crunit_table_id,
    is_crunit_url,
)
from public_data_agent.sources.crbio import (
    cells_from_crbio,
    crbio_table_id,
    is_crbio_url,
)
from public_data_agent.sources.cristin import (
    cells_from_cristin,
    cristin_table_id,
    is_cristin_url,
)
from public_data_agent.sources.omregning import (
    cells_from_omregning,
    is_omregning_url,
    omregning_table_id,
)
from public_data_agent.sources.hicoverages import (
    cells_from_hicoverages,
    hicoverages_table_id,
    is_hicoverages_url,
)
from public_data_agent.sources.envreportreg import (
    cells_from_envreportreg,
    envreportreg_table_id,
    is_envreportreg_url,
)
from public_data_agent.sources.himaps import (
    cells_from_himaps,
    himaps_table_id,
    is_himaps_url,
)
from public_data_agent.sources.hitiles import (
    cells_from_hitiles,
    hitiles_table_id,
    is_hitiles_url,
)
from public_data_agent.sources.miljogis import (
    cells_from_miljogis,
    is_miljogis_url,
    miljogis_table_id,
)
from public_data_agent.sources.hoydegis import (
    cells_from_hoydegis,
    hoydegis_table_id,
    is_hoydegis_url,
)
from public_data_agent.sources.fiskerigis import (
    cells_from_fiskerigis,
    fiskerigis_table_id,
    is_fiskerigis_url,
)
from public_data_agent.sources.nve2gis import (
    cells_from_nve2gis,
    is_nve2gis_url,
    nve2gis_table_id,
)
from public_data_agent.sources.nvemap import (
    cells_from_nvemap,
    is_nvemap_url,
    nvemap_table_id,
)
from public_data_agent.sources.navwarnings import (
    cells_from_navwarnings,
    is_navwarnings_url,
    navwarnings_table_id,
)
from public_data_agent.sources.nvegis import (
    cells_from_nvegis,
    is_nvegis_url,
    nvegis_table_id,
)
from public_data_agent.sources.stortinget import (
    cells_from_stortinget,
    is_stortinget_url,
    stortinget_table_id,
)
from public_data_agent.sources.stkomiteer import (
    cells_from_stkomiteer,
    is_stkomiteer_url,
    stkomiteer_table_id,
)
from public_data_agent.sources.stperioder import (
    cells_from_stperioder,
    is_stperioder_url,
    stperioder_table_id,
)
from public_data_agent.sources.stsaker import (
    cells_from_stsaker,
    is_stsaker_url,
    stsaker_table_id,
)
from public_data_agent.sources.stpartier import (
    cells_from_stpartier,
    is_stpartier_url,
    stpartier_table_id,
)
from public_data_agent.sources.histyles import (
    cells_from_histyles,
    histyles_table_id,
    is_histyles_url,
)
from public_data_agent.sources.miljorapporter import (
    cells_from_miljorapporter,
    is_miljorapporter_url,
    miljorapporter_table_id,
)
from public_data_agent.sources.havnedata import (
    cells_from_havnedata,
    havnedata_table_id,
    is_havnedata_url,
)
from public_data_agent.sources.npigis import (
    cells_from_npigis,
    is_npigis_url,
    npigis_table_id,
)
from public_data_agent.sources.npitema import (
    cells_from_npitema,
    is_npitema_url,
    npitema_table_id,
)
from public_data_agent.sources.arcticsdi import (
    arcticsdi_table_id,
    cells_from_arcticsdi,
    is_arcticsdi_url,
)
from public_data_agent.sources.npiintern import (
    cells_from_npiintern,
    is_npiintern_url,
    npiintern_table_id,
)
from public_data_agent.sources.ssbfam import (
    cells_from_ssbfam,
    is_ssbfam_url,
    ssbfam_table_id,
)
from public_data_agent.sources.ssbgis import (
    cells_from_ssbgis,
    is_ssbgis_url,
    ssbgis_table_id,
)
from public_data_agent.sources.ssbv2 import (
    cells_from_ssbv2,
    is_ssbv2_url,
    ssbv2_table_id,
)
from public_data_agent.sources.ssbsec import (
    cells_from_ssbsec,
    is_ssbsec_url,
    ssbsec_table_id,
)
from public_data_agent.sources.ssclass import (
    cells_from_ssclass,
    is_ssclass_url,
    ssclass_table_id,
)
from public_data_agent.sources.brenheter import (
    brenheter_table_id,
    cells_from_brenheter,
    is_brenheter_url,
)
from public_data_agent.sources.brkommuner import (
    brkommuner_table_id,
    cells_from_brkommuner,
    is_brkommuner_url,
)
from public_data_agent.sources.brorgform import (
    brorgform_table_id,
    cells_from_brorgform,
    is_brorgform_url,
)
from public_data_agent.sources.brorgformen import (
    brorgformen_table_id,
    cells_from_brorgformen,
    is_brorgformen_url,
)
from public_data_agent.sources.ssbcorr import (
    cells_from_ssbcorr,
    is_ssbcorr_url,
    ssbcorr_table_id,
)
from public_data_agent.sources.ssbsubj import (
    cells_from_ssbsubj,
    is_ssbsubj_url,
    ssbsubj_table_id,
)
from public_data_agent.sources.ssbvar import (
    cells_from_ssbvar,
    is_ssbvar_url,
    ssbvar_table_id,
)
from public_data_agent.sources.ssbver import (
    cells_from_ssbver,
    is_ssbver_url,
    ssbver_table_id,
)
from public_data_agent.sources.nibiowms import (
    cells_from_nibiowms,
    is_nibiowms_url,
    nibiowms_table_id,
)
from public_data_agent.sources.nibiorest import (
    cells_from_nibiorest,
    is_nibiorest_url,
    nibiorest_table_id,
)
from public_data_agent.sources.nibioar50 import (
    cells_from_nibioar50,
    is_nibioar50_url,
    nibioar50_table_id,
)
from public_data_agent.sources.rawms import (
    cells_from_rawms,
    is_rawms_url,
    rawms_table_id,
)
from public_data_agent.sources.regobs import (
    cells_from_regobs,
    is_regobs_url,
    regobs_table_id,
)
from public_data_agent.sources.grep import (
    cells_from_grep,
    grep_table_id,
    is_grep_url,
)
from public_data_agent.sources.kvgrunn import (
    cells_from_kvgrunn,
    is_kvgrunn_url,
    kvgrunn_table_id,
)
from public_data_agent.sources.kvtopo import (
    cells_from_kvtopo,
    is_kvtopo_url,
    kvtopo_table_id,
)
from public_data_agent.sources.kvwms import (
    cells_from_kvwms,
    is_kvwms_url,
    kvwms_table_id,
)
from public_data_agent.sources.aviationforecast import (
    aviationforecast_table_id,
    cells_from_aviationforecast,
    is_aviationforecast_url,
)
from public_data_agent.sources.vannkraft import (
    cells_from_vannkraft,
    is_vannkraft_url,
    vannkraft_table_id,
)
from public_data_agent.sources.vindkraft import (
    cells_from_vindkraft,
    is_vindkraft_url,
    vindkraft_table_id,
)
from public_data_agent.sources.vegogc import (
    cells_from_vegogc,
    is_vegogc_url,
    vegogc_table_id,
)
from public_data_agent.sources.elcert import (
    cells_from_elcert,
    elcert_table_id,
    is_elcert_url,
)
from public_data_agent.sources.frivillig import (
    cells_from_frivillig,
    frivillig_table_id,
    is_frivillig_url,
)
from public_data_agent.sources.broppdater import (
    broppdater_table_id,
    cells_from_broppdater,
    is_broppdater_url,
)
from public_data_agent.sources.brrepresent import (
    brrepresent_table_id,
    cells_from_brrepresent,
    is_brrepresent_url,
)
from public_data_agent.sources.brunder import (
    brunder_table_id,
    cells_from_brunder,
    is_brunder_url,
)
from public_data_agent.sources.brrollegruppe import (
    brrollegruppe_table_id,
    cells_from_brrollegruppe,
    is_brrollegruppe_url,
)
from public_data_agent.sources.brrolletype import (
    brrolletype_table_id,
    cells_from_brrolletype,
    is_brrolletype_url,
)
from public_data_agent.sources.brroller import (
    brroller_table_id,
    cells_from_brroller,
    is_brroller_url,
)
from public_data_agent.sources.kystwms import (
    cells_from_kystwms,
    is_kystwms_url,
    kystwms_table_id,
)
from public_data_agent.sources.kystnav import (
    cells_from_kystnav,
    is_kystnav_url,
    kystnav_table_id,
)
from public_data_agent.sources.banegis import (
    cells_from_banegis,
    is_banegis_url,
    banegis_table_id,
)
from public_data_agent.sources.avinorgis import (
    cells_from_avinorgis,
    is_avinorgis_url,
    avinorgis_table_id,
)
from public_data_agent.sources.sandnes import (
    PRINTED_QUERY,
    cells_from_sandnes,
    is_sandnes_url,
    sandnes_table_id,
)
from public_data_agent.sources.stormflo import (
    cells_from_stormflo,
    is_stormflo_url,
    stormflo_table_id,
)
from public_data_agent.sources.nbdsd import (
    cells_from_nbdsd,
    is_nbdsd_url,
    nbdsd_table_id,
)
from public_data_agent.sources.nbdps import (
    cells_from_nbdps,
    is_nbdps_url,
    nbdps_table_id,
)
from public_data_agent.sources.nbprov import (
    cells_from_nbprov,
    is_nbprov_url,
    nbprov_table_id,
)
from public_data_agent.sources.spotwind import (
    cells_from_spotwind,
    is_spotwind_url,
    spotwind_table_id,
)
from public_data_agent.sources.sunrise import (
    cells_from_sunrise,
    is_sunrise_url,
    sunrise_table_id,
)
from public_data_agent.sources.tidalwater import (
    cells_from_tidalwater,
    is_tidalwater_url,
    tidalwater_table_id,
)
from public_data_agent.sources.oceanforecast import (
    cells_from_oceanforecast,
    is_oceanforecast_url,
    oceanforecast_table_id,
)
from public_data_agent.sources.radar import (
    cells_from_radar,
    is_radar_url,
    radar_table_id,
)
from public_data_agent.sources.textforecast import (
    cells_from_textforecast,
    is_textforecast_url,
    textforecast_table_id,
)
from public_data_agent.sources.icemap import (
    cells_from_icemap,
    icemap_table_id,
    is_icemap_url,
)
from public_data_agent.sources.tafmetar import (
    cells_from_tafmetar,
    is_tafmetar_url,
    tafmetar_table_id,
)
from public_data_agent.sources.geosatellite import (
    cells_from_geosatellite,
    geosatellite_table_id,
    is_geosatellite_url,
)
from public_data_agent.sources.subjectiveforecast import (
    cells_from_subjectiveforecast,
    is_subjectiveforecast_url,
    subjectiveforecast_table_id,
)
from public_data_agent.sources.research import (
    cells_from_research,
    is_research_url,
    research_table_id,
)
from public_data_agent.sources.fiskeridir import (
    cells_from_fiskeridir,
    fiskeridir_table_id,
    is_fiskeridir_vessel_url,
)
from public_data_agent.sources.hoydedata import (
    cells_from_hoydedata,
    hoydedata_table_id,
    is_hoydedata_url,
)
from public_data_agent.sources.transformering import (
    cells_from_transformering,
    is_transformering_url,
    transformering_table_id,
)
from public_data_agent.sources.kifylker import (
    cells_from_kifylker,
    is_kifylker_url,
    kifylker_table_id,
)
from public_data_agent.sources.kikommuner import (
    cells_from_kikommuner,
    is_kikommuner_url,
    kikommuner_table_id,
)
from public_data_agent.sources.kommuneinfo import (
    cells_from_kommuneinfo,
    is_kommuneinfo_url,
    kommuneinfo_table_id,
)
from public_data_agent.sources.kystverket import (
    cells_from_kystverket,
    is_kystverket_url,
    kystverket_table_id,
)
from public_data_agent.sources.miljodir import (
    cells_from_miljodir,
    is_miljodir_url,
    miljodir_table_id,
)
from public_data_agent.sources.trondheim import (
    cells_from_trondheim,
    is_trondheim_url,
    trondheim_table_id,
)
from public_data_agent.sources.vegvesen import (
    cells_from_vegvesen,
    is_vegvesen_url,
    vegvesen_table_id,
)
from public_data_agent.sources.met import (
    cells_from_met,
    is_met_metalerts_url,
    met_table_id,
)
from public_data_agent.sources.statnett import (
    cells_from_statnett,
    is_statnett_url,
    statnett_table_id,
)
from public_data_agent.sources.utdanning import (
    cells_from_utdanning,
    is_utdanning_url,
    utdanning_table_id,
)
from public_data_agent.sources.hi import (
    cells_from_hi,
    hi_table_id,
    is_hi_url,
)
from public_data_agent.sources.nibio import (
    cells_from_nibio,
    is_nibio_url,
    nibio_table_id,
)
from public_data_agent.sources.nbr import (
    cells_from_nbr,
    is_nbr_url,
    nbr_table_id,
)
from public_data_agent.sources.baf import (
    baf_table_id,
    cells_from_baf,
    is_baf_url,
)
from public_data_agent.sources.nfr import (
    cells_from_nfr,
    is_nfr_url,
    nfr_table_id,
)
from public_data_agent.sources.nor import (
    cells_from_nor,
    is_nor_url,
    nor_table_id,
)
from public_data_agent.sources.npr import (
    cells_from_npr,
    is_npr_url,
    npr_table_id,
)
from public_data_agent.sources.nxr import (
    cells_from_nxr,
    is_nxr_url,
    nxr_table_id,
)
from public_data_agent.sources.fdkorg import (
    cells_from_fdkorg,
    fdkorg_table_id,
    is_fdkorg_url,
)
from public_data_agent.sources.nbagency import (
    cells_from_nbagency,
    is_nbagency_url,
    nbagency_table_id,
)
from public_data_agent.sources.nbconcept import (
    cells_from_nbconcept,
    is_nbconcept_url,
    nbconcept_table_id,
)
from public_data_agent.sources.norgesbank import (
    cells_from_norgesbank,
    is_norgesbank_url,
    norgesbank_table_id,
)
from public_data_agent.sources.nbcodelist import (
    cells_from_nbcodelist,
    is_nbcodelist_url,
    nbcodelist_table_id,
)
from public_data_agent.sources.npolar import (
    cells_from_npolar,
    is_npolar_url,
    npolar_table_id,
)
from public_data_agent.sources.stedsnavn import (
    cells_from_stedsnavn,
    is_stedsnavn_url,
    stedsnavn_table_id,
)
from public_data_agent.sources.oslo import is_oslo_statbank_url, oslo_table_id
from public_data_agent.sources.sikt import (
    cells_from_sikt,
    is_sikt_url,
    sikt_table_id,
)
from public_data_agent.sources.udir import (
    cells_from_udir,
    is_udir_nsr_url,
    udir_table_id,
)
from public_data_agent.sources.valg import (
    cells_from_valg,
    is_valg_url,
    valg_table_id,
)
from public_data_agent.ssb_klass import cells_from_klass, is_klass_url, klass_table_id

PXWEB_UI_MARK = "/statbank/pxweb/"
PXWEB_API_MARK = "/statbank/api/v1/"
DEFAULT_OSLO_DATASET = "datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57"
DEFAULT_OSLO_TABLE = "Befolkning/Folkemengde/OK-BEF008.px"


class JsonHttp(Protocol):
    def get_json_response(self, url: str, *, headers: dict[str, str] | None = None) -> JsonResponse: ...

    def post_json_response(
        self,
        url: str,
        body: Any,
        *,
        headers: dict[str, str] | None = None,
    ) -> JsonResponse: ...


@dataclass
class Observation:
    dataset_id: str
    table_id: str
    measure: str
    value: Any
    dimensions: dict[str, str]
    retrieved_at: str
    request_url: str
    http_status: int
    publisher_name: str | None
    license: str | None
    access_path: str | None
    source_native_uri: str | None

    def identity_key(self) -> str:
        dims = json.dumps(self.dimensions, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        raw = "\0".join([self.dataset_id, self.table_id, self.measure, dims])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


@dataclass
class FetchResult:
    dataset_id: str
    table_id: str
    request_url: str
    http_status: int
    counts: HarvestCounts = field(default_factory=HarvestCounts)
    sample: list[dict[str, Any]] = field(default_factory=list)


def pxweb_api_url(access_path: str, table_id: str) -> str:
    """Derive the PxWeb API URL from a stored access path plus a table path.

    This rewrites the well-known `/statbank/pxweb/` UI prefix to `/statbank/api/v1/`.
    It does not invent observation values.
    """

    if not access_path:
        raise ValueError("dataset has no access_path")
    root = access_path.rstrip("/") + "/"
    if PXWEB_UI_MARK in root:
        root = root.replace(PXWEB_UI_MARK, PXWEB_API_MARK, 1)
    elif PXWEB_API_MARK not in root and "/api/" not in root:
        raise ValueError(f"access_path is not a PxWeb or API URL: {access_path}")
    return urljoin(root, table_id.lstrip("/"))


def time_codes(meta: dict[str, Any], *, from_year: int | None, to_year: int | None) -> tuple[str, list[str]]:
    for variable in meta.get("variables") or []:
        if not variable.get("time"):
            continue
        codes = list(variable.get("values") or [])
        labels = list(variable.get("valueTexts") or [])
        if from_year is None and to_year is None:
            return str(variable["code"]), codes
        selected: list[str] = []
        for code, label in zip(codes, labels):
            year = _year_from_label(label)
            if year is None:
                continue
            if from_year is not None and year < from_year:
                continue
            if to_year is not None and year > to_year:
                continue
            selected.append(code)
        if not selected:
            raise ValueError("no time codes in the requested year range")
        return str(variable["code"]), selected
    raise ValueError("table metadata has no time variable")


def cells_from_jsonstat(payload: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    ids = list(payload.get("id") or [])
    sizes = list(payload.get("size") or [])
    values = list(payload.get("value") or [])
    dimension = payload.get("dimension") or {}
    if len(ids) != len(sizes):
        raise ValueError("json-stat id and size length differ")
    axes: list[list[tuple[str, str]]] = []
    for dim_id, size in zip(ids, sizes):
        category = (dimension.get(dim_id) or {}).get("category") or {}
        index = category.get("index") or {}
        labels = category.get("label") or {}
        by_pos: list[tuple[str, str] | None] = [None] * size
        for code, pos in index.items():
            by_pos[int(pos)] = (str(code), str(labels.get(code, code)))
        if any(item is None for item in by_pos):
            raise ValueError(f"json-stat dimension {dim_id} is missing an index position")
        axes.append([(code, label) for code, label in by_pos if code is not None])
    metric_id = _metric_dimension(payload, ids)
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for i, value in enumerate(values):
        coords = _unravel(i, sizes)
        measure = ""
        dims: dict[str, str] = {}
        for dim_id, pos, axis in zip(ids, coords, axes):
            _code, label = axis[pos]
            if dim_id == "ContentsCode":
                continue
            if dim_id == metric_id:
                measure = label
                continue
            dims[dim_id] = label
        if not measure:
            measure = str(payload.get("label") or "value")
        cells.append((measure, value, dims))
    return cells


def fetch_observations(
    registry: Registry,
    dataset_id: str,
    *,
    table_id: str,
    from_year: int | None = None,
    to_year: int | None = None,
    http: JsonHttp | None = None,
) -> FetchResult:
    dataset = registry.get_dataset(dataset_id)
    if dataset is None:
        raise ValueError(f"unknown dataset {dataset_id}")
    access_path = dataset.get("access_path") or ""
    if is_ssbfam_url(access_path):
        return _fetch_ssbfam(registry, dataset, http=http)
    if is_ssbsec_url(access_path):
        return _fetch_ssbsec(registry, dataset, http=http)
    if is_ssclass_url(access_path):
        return _fetch_ssclass(registry, dataset, http=http)
    if is_ssbver_url(access_path):
        return _fetch_ssbver(registry, dataset, http=http)
    if is_ssbcorr_url(access_path):
        return _fetch_ssbcorr(registry, dataset, http=http)
    if is_ssbvar_url(access_path):
        return _fetch_ssbvar(registry, dataset, http=http)
    if is_ssbsubj_url(access_path):
        return _fetch_ssbsubj(registry, dataset, http=http)
    if is_klass_url(access_path):
        return _fetch_klass(registry, dataset, http=http)
    if is_stedsnavn_url(access_path):
        return _fetch_stedsnavn(registry, dataset, http=http)
    if is_kifylker_url(access_path):
        return _fetch_kifylker(registry, dataset, http=http)
    if is_kikommuner_url(access_path):
        return _fetch_kikommuner(registry, dataset, http=http)
    if is_kommuneinfo_url(access_path):
        return _fetch_kommuneinfo(registry, dataset, http=http)
    if is_hoydedata_url(access_path):
        return _fetch_hoydedata(registry, dataset, http=http)
    if is_transformering_url(access_path):
        return _fetch_transformering(registry, dataset, http=http)
    if is_geonorge_rest_url(access_path):
        return _fetch_geonorge_rest(registry, dataset, http=http)
    if is_nve_magasin_url(access_path):
        return _fetch_nve_magasin(registry, dataset, http=http)
    if is_brkommuner_url(access_path):
        return _fetch_brkommuner(registry, dataset, http=http)
    if is_brenheter_url(access_path):
        return _fetch_brenheter(registry, dataset, http=http)
    if is_brorgformen_url(access_path):
        return _fetch_brorgformen(registry, dataset, http=http)
    if is_brorgform_url(access_path):
        return _fetch_brorgform(registry, dataset, http=http)
    if is_brrollegruppe_url(access_path):
        return _fetch_brrollegruppe(registry, dataset, http=http)
    if is_brrolletype_url(access_path):
        return _fetch_brrolletype(registry, dataset, http=http)
    if is_brrepresent_url(access_path):
        return _fetch_brrepresent(registry, dataset, http=http)
    if is_brroller_url(access_path):
        return _fetch_brroller(registry, dataset, http=http)
    if is_broppdater_url(access_path):
        return _fetch_broppdater(registry, dataset, http=http)
    if is_brunder_url(access_path):
        return _fetch_brunder(registry, dataset, http=http)
    if is_brreg_url(access_path):
        return _fetch_brreg(registry, dataset, http=http)
    if is_valg_url(access_path):
        return _fetch_valg(registry, dataset, http=http)
    if is_fhi_url(access_path):
        return _fetch_fhi(registry, dataset, http=http)
    if is_mattilsynet_url(access_path):
        return _fetch_mattilsynet(registry, dataset, http=http)
    if is_udir_nsr_url(access_path):
        return _fetch_udir(registry, dataset, http=http)
    if is_nbr_url(access_path):
        return _fetch_nbr(registry, dataset, http=http)
    if is_nor_url(access_path):
        return _fetch_nor(registry, dataset, http=http)
    if is_npr_url(access_path):
        return _fetch_npr(registry, dataset, http=http)
    if is_nfr_url(access_path):
        return _fetch_nfr(registry, dataset, http=http)
    if is_nxr_url(access_path):
        return _fetch_nxr(registry, dataset, http=http)
    if is_baf_url(access_path):
        return _fetch_baf(registry, dataset, http=http)
    if is_nbcodelist_url(access_path):
        return _fetch_nbcodelist(registry, dataset, http=http)
    if is_fdkorg_url(access_path):
        return _fetch_fdkorg(registry, dataset, http=http)
    if is_nbagency_url(access_path):
        return _fetch_nbagency(registry, dataset, http=http)
    if is_nbconcept_url(access_path):
        return _fetch_nbconcept(registry, dataset, http=http)
    if is_norgesbank_url(access_path):
        return _fetch_norgesbank(registry, dataset, http=http)
    if is_npolar_url(access_path):
        return _fetch_npolar(registry, dataset, http=http)
    if is_sikt_url(access_path):
        return _fetch_sikt(registry, dataset, http=http)
    if is_buyer_url(access_path):
        return _fetch_buyer(registry, dataset, http=http)
    if is_nytek_url(access_path):
        return _fetch_nytek(registry, dataset, http=http)
    if is_aqua_url(access_path):
        return _fetch_aqua(registry, dataset, http=http)
    if is_research_url(access_path):
        return _fetch_research(registry, dataset, http=http)
    if is_portal_url(access_path):
        return _fetch_portal(registry, dataset, http=http)
    if is_opencom_url(access_path):
        return _fetch_opencom(registry, dataset, http=http)
    if is_sodir_url(access_path):
        return _fetch_sodir(registry, dataset, http=http)
    if is_riksantikvaren_url(access_path):
        return _fetch_riksantikvaren(registry, dataset, http=http)
    if is_ragis_url(access_path):
        return _fetch_ragis(registry, dataset, http=http)
    if is_nibioar50_url(access_path):
        return _fetch_nibioar50(registry, dataset, http=http)
    if is_nibiorest_url(access_path):
        return _fetch_nibiorest(registry, dataset, http=http)
    if is_ldirwms_url(access_path):
        return _fetch_ldirwms(registry, dataset, http=http)
    if is_mdirwms_url(access_path):
        return _fetch_mdirwms(registry, dataset, http=http)
    if is_mdirgis_url(access_path):
        return _fetch_mdirgis(registry, dataset, http=http)
    if is_barmark_url(access_path):
        return _fetch_barmark(registry, dataset, http=http)
    if is_nordatlas_url(access_path):
        return _fetch_nordatlas(registry, dataset, http=http)
    if is_mattilsyn_url(access_path):
        return _fetch_mattilsyn(registry, dataset, http=http)
    if is_fdirwms_url(access_path):
        return _fetch_fdirwms(registry, dataset, http=http)
    if is_vegwms_url(access_path):
        return _fetch_vegwms(registry, dataset, http=http)
    if is_hiwms_url(access_path):
        return _fetch_hiwms(registry, dataset, http=http)
    if is_bwgis_url(access_path):
        return _fetch_bwgis(registry, dataset, http=http)
    if is_fbgis_url(access_path):
        return _fetch_fbgis(registry, dataset, http=http)
    if is_kystwfs_url(access_path):
        return _fetch_kystwfs(registry, dataset, http=http)
    if is_nin_url(access_path):
        return _fetch_nin(registry, dataset, http=http)
    if is_nguminer_url(access_path):
        return _fetch_nguminer(registry, dataset, http=http)
    if is_nguwms_url(access_path):
        return _fetch_nguwms(registry, dataset, http=http)
    if is_ngu_url(access_path):
        return _fetch_ngu(registry, dataset, http=http)
    if is_nowcast_url(access_path):
        return _fetch_nowcast(registry, dataset, http=http)
    if is_airquality_url(access_path):
        return _fetch_airquality(registry, dataset, http=http)
    if is_tidalwater_url(access_path):
        return _fetch_tidalwater(registry, dataset, http=http)
    if is_oceanforecast_url(access_path):
        return _fetch_oceanforecast(registry, dataset, http=http)
    if is_sunrise_url(access_path):
        return _fetch_sunrise(registry, dataset, http=http)
    if is_radar_url(access_path):
        return _fetch_radar(registry, dataset, http=http)
    if is_spotwind_url(access_path):
        return _fetch_spotwind(registry, dataset, http=http)
    if is_textforecast_url(access_path):
        return _fetch_textforecast(registry, dataset, http=http)
    if is_icemap_url(access_path):
        return _fetch_icemap(registry, dataset, http=http)
    if is_ncagalewarnings_url(access_path):
        return _fetch_ncagalewarnings(registry, dataset, http=http)
    if is_tafmetar_url(access_path):
        return _fetch_tafmetar(registry, dataset, http=http)
    if is_subseasonal_url(access_path):
        return _fetch_subseasonal(registry, dataset, http=http)
    if is_geosatellite_url(access_path):
        return _fetch_geosatellite(registry, dataset, http=http)
    if is_metgm_url(access_path):
        return _fetch_metgm(registry, dataset, http=http)
    if is_subjectiveforecast_url(access_path):
        return _fetch_subjectiveforecast(registry, dataset, http=http)
    if is_polarsatellite_url(access_path):
        return _fetch_polarsatellite(registry, dataset, http=http)
    if is_soundprofile_url(access_path):
        return _fetch_soundprofile(registry, dataset, http=http)
    if is_gribfiles_url(access_path):
        return _fetch_gribfiles(registry, dataset, http=http)
    if is_metgc_url(access_path):
        return _fetch_metgc(registry, dataset, http=http)
    if is_oslofjord_url(access_path):
        return _fetch_oslofjord(registry, dataset, http=http)
    if is_isobaricgrib_url(access_path):
        return _fetch_isobaricgrib(registry, dataset, http=http)
    if is_offshoremaps_url(access_path):
        return _fetch_offshoremaps(registry, dataset, http=http)
    if is_turbulence_url(access_path):
        return _fetch_turbulence(registry, dataset, http=http)
    if is_nlaroutes_url(access_path):
        return _fetch_nlaroutes(registry, dataset, http=http)
    if is_sigcharts_url(access_path):
        return _fetch_sigcharts(registry, dataset, http=http)
    if is_volcanicashforecast_url(access_path):
        return _fetch_volcanicashforecast(registry, dataset, http=http)
    if is_routeforecast_url(access_path):
        return _fetch_routeforecast(registry, dataset, http=http)
    if is_norskelos_url(access_path):
        return _fetch_norskelos(registry, dataset, http=http)
    if is_locationforecast_url(access_path):
        return _fetch_locationforecast(registry, dataset, http=http)
    if is_georegister_url(access_path):
        return _fetch_georegister(registry, dataset, http=http)
    if is_nortaxa_url(access_path):
        return _fetch_nortaxa(registry, dataset, http=http)
    if is_artskart_url(access_path):
        return _fetch_artskart(registry, dataset, http=http)
    if is_lister_url(access_path):
        return _fetch_lister(registry, dataset, http=http)
    if is_ogccoverages_url(access_path):
        return _fetch_ogccoverages(registry, dataset, http=http)
    if is_regnskap_url(access_path):
        return _fetch_regnskap(registry, dataset, http=http)
    if is_crinst_url(access_path):
        return _fetch_crinst(registry, dataset, http=http)
    if is_crunit_url(access_path):
        return _fetch_crunit(registry, dataset, http=http)
    if is_crproj_url(access_path):
        return _fetch_crproj(registry, dataset, http=http)
    if is_crbio_url(access_path):
        return _fetch_crbio(registry, dataset, http=http)
    if is_cristin_url(access_path):
        return _fetch_cristin(registry, dataset, http=http)
    if is_omregning_url(access_path):
        return _fetch_omregning(registry, dataset, http=http)
    if is_hicoverages_url(access_path):
        return _fetch_hicoverages(registry, dataset, http=http)
    if is_envreportreg_url(access_path):
        return _fetch_envreportreg(registry, dataset, http=http)
    if is_himaps_url(access_path):
        return _fetch_himaps(registry, dataset, http=http)
    if is_stkomiteer_url(access_path):
        return _fetch_stkomiteer(registry, dataset, http=http)
    if is_stperioder_url(access_path):
        return _fetch_stperioder(registry, dataset, http=http)
    if is_stsaker_url(access_path):
        return _fetch_stsaker(registry, dataset, http=http)
    if is_stpartier_url(access_path):
        return _fetch_stpartier(registry, dataset, http=http)
    if is_stortinget_url(access_path):
        return _fetch_stortinget(registry, dataset, http=http)
    if is_histyles_url(access_path):
        return _fetch_histyles(registry, dataset, http=http)
    if is_hitiles_url(access_path):
        return _fetch_hitiles(registry, dataset, http=http)
    if is_miljorapporter_url(access_path):
        return _fetch_miljorapporter(registry, dataset, http=http)
    if is_nvemap_url(access_path):
        return _fetch_nvemap(registry, dataset, http=http)
    if is_nvegis_url(access_path):
        return _fetch_nvegis(registry, dataset, http=http)
    if is_navwarnings_url(access_path):
        return _fetch_navwarnings(registry, dataset, http=http)
    if is_havnedata_url(access_path):
        return _fetch_havnedata(registry, dataset, http=http)
    if is_miljogis_url(access_path):
        return _fetch_miljogis(registry, dataset, http=http)
    if is_hoydegis_url(access_path):
        return _fetch_hoydegis(registry, dataset, http=http)
    if is_npitema_url(access_path):
        return _fetch_npitema(registry, dataset, http=http)
    if is_arcticsdi_url(access_path):
        return _fetch_arcticsdi(registry, dataset, http=http)
    if is_npiintern_url(access_path):
        return _fetch_npiintern(registry, dataset, http=http)
    if is_ssbgis_url(access_path):
        return _fetch_ssbgis(registry, dataset, http=http)
    if is_ssbv2_url(access_path):
        return _fetch_ssbv2(registry, dataset, http=http)
    if is_nibiowms_url(access_path):
        return _fetch_nibiowms(registry, dataset, http=http)
    if is_rawms_url(access_path):
        return _fetch_rawms(registry, dataset, http=http)
    if is_regobs_url(access_path):
        return _fetch_regobs(registry, dataset, http=http)
    if is_sigmets_url(access_path):
        return _fetch_sigmets(registry, dataset, http=http)
    if is_grep_url(access_path):
        return _fetch_grep(registry, dataset, http=http)
    if is_kvgrunn_url(access_path):
        return _fetch_kvgrunn(registry, dataset, http=http)
    if is_kvtopo_url(access_path):
        return _fetch_kvtopo(registry, dataset, http=http)
    if is_kvwms_url(access_path):
        return _fetch_kvwms(registry, dataset, http=http)
    if is_aviationforecast_url(access_path):
        return _fetch_aviationforecast(registry, dataset, http=http)
    if is_vannkraft_url(access_path):
        return _fetch_vannkraft(registry, dataset, http=http)
    if is_vindkraft_url(access_path):
        return _fetch_vindkraft(registry, dataset, http=http)
    if is_vegogc_url(access_path):
        return _fetch_vegogc(registry, dataset, http=http)
    if is_elcert_url(access_path):
        return _fetch_elcert(registry, dataset, http=http)
    if is_kystwms_url(access_path):
        return _fetch_kystwms(registry, dataset, http=http)
    if is_kystnav_url(access_path):
        return _fetch_kystnav(registry, dataset, http=http)
    if is_banegis_url(access_path):
        return _fetch_banegis(registry, dataset, http=http)
    if is_avinorgis_url(access_path):
        return _fetch_avinorgis(registry, dataset, http=http)
    if is_frivillig_url(access_path):
        return _fetch_frivillig(registry, dataset, http=http)
    if is_sandnes_url(access_path):
        return _fetch_sandnes(registry, dataset, http=http)
    if is_stormflo_url(access_path):
        return _fetch_stormflo(registry, dataset, http=http)
    if is_nbdsd_url(access_path):
        return _fetch_nbdsd(registry, dataset, http=http)
    if is_nbdps_url(access_path):
        return _fetch_nbdps(registry, dataset, http=http)
    if is_nbprov_url(access_path):
        return _fetch_nbprov(registry, dataset, http=http)
    if is_npigis_url(access_path):
        return _fetch_npigis(registry, dataset, http=http)
    if is_nve2gis_url(access_path):
        return _fetch_nve2gis(registry, dataset, http=http)
    if is_fiskerigis_url(access_path):
        return _fetch_fiskerigis(registry, dataset, http=http)
    if is_entur_gbfs_url(access_path):
        return _fetch_entur(registry, dataset, http=http)
    if is_fiskeridir_vessel_url(access_path):
        return _fetch_fiskeridir(registry, dataset, http=http)
    if is_statnett_url(access_path):
        return _fetch_statnett(registry, dataset, http=http)
    if is_utdanning_url(access_path):
        return _fetch_utdanning(registry, dataset, http=http)
    if is_met_metalerts_url(access_path):
        return _fetch_met(registry, dataset, http=http)
    if is_hi_url(access_path):
        return _fetch_hi(registry, dataset, http=http)
    if is_kystverket_url(access_path):
        return _fetch_kystverket(registry, dataset, http=http)
    if is_nibio_url(access_path):
        return _fetch_nibio(registry, dataset, http=http)
    if is_miljodir_url(access_path):
        return _fetch_miljodir(registry, dataset, http=http)
    if is_trondheim_url(access_path):
        return _fetch_trondheim(registry, dataset, http=http)
    if is_vegvesen_url(access_path):
        return _fetch_vegvesen(registry, dataset, http=http)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    if _is_ssb_table_url(access_path) or is_oslo_statbank_url(access_path):
        request_url = access_path.rstrip("/")
        table_id = (
            oslo_table_id(access_path)
            if is_oslo_statbank_url(access_path)
            else request_url.rsplit("/", 1)[-1]
        )
    else:
        request_url = pxweb_api_url(access_path, table_id)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset_id,
        table_id=table_id,
        request_url=request_url,
        request_method="POST",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        meta = client.get_json_response(request_url)
        time_code, selected = time_codes(meta.body, from_year=from_year, to_year=to_year)
        query = _pxweb_query(meta.body, time_code, selected)
        registry.set_fetch_request(run_id, request_url=request_url, request_body=query)
        posted = client.post_json_response(request_url, query)
        http_status = posted.status
        cells = cells_from_jsonstat(posted.body)
        counts.listed = len(cells)
        retrieved_at = utc_now()
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=retrieved_at,
            request_url=request_url,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": request_url})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset_id,
        table_id=table_id,
        request_url=request_url,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_brenheter(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "brenheter":
        return _fetch_brreg(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = brenheter_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_brenheter(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_brkommuner(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "brkommuner":
        return _fetch_brreg(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = brkommuner_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_brkommuner(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_brrollegruppe(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "brrollegruppe":
        return _fetch_brreg(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = brrollegruppe_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_brrollegruppe(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_brorgformen(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = brorgformen_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_brorgformen(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_brorgform(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "brorgform":
        return _fetch_brreg(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = brorgform_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_brorgform(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ssclass(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ssclass_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ssclass(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ssbvar(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ssbvar_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ssbvar(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ssbsubj(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ssbsubj_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ssbsubj(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ssbcorr(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ssbcorr_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ssbcorr(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ssbver(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ssbver_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ssbver(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_klass(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id="klass",
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    table_id = "klass"
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        if not isinstance(got.body, dict):
            raise ValueError("klass response is not a JSON object")
        table_id = klass_table_id(got.body, access_path)
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_klass(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_geonorge_rest(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    spec_url = openapi_url(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id="geonorge",
        request_url=spec_url,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    table_id = "geonorge"
    request_url = spec_url
    sample: list[dict[str, Any]] = []
    try:
        spec = client.get_json_response(spec_url)
        if not isinstance(spec.body, dict):
            raise ValueError("geonorge openapi response is not a JSON object")
        request_url = collection_request_url(access_path, spec.body)
        table_id = geonorge_table_id(request_url)
        registry.set_fetch_request(run_id, request_url=request_url, request_body={"method": "GET"})
        got = client.get_json_response(request_url)
        http_status = got.status
        measure = str(dataset.get("title") or table_id)
        cells = cells_from_geonorge(got.body, measure=measure)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=request_url,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": request_url})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=request_url,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nve_magasin(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    request_url = requestable_url(access_path)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
    table_id = nve_table_id(access_path)
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=request_url,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(request_url)
        http_status = got.status
        if not isinstance(got.body, (list, dict)):
            raise ValueError("NVE Magasinstatistikk response is not JSON")
        table_id = nve_table_id(access_path)
        registry.set_fetch_request(run_id, request_url=request_url, request_body={"method": "GET"})
        cells = cells_from_nve(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=request_url,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": request_url})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=request_url,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_brreg(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = brreg_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        measure = str(dataset.get("title") or table_id)
        cells = cells_from_brreg(got.body, measure=measure)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_valg(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = valg_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_valg(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_mattilsynet(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = mattilsynet_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_mattilsynet(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_fhi(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = fhi_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_fhi(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_npolar(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = npolar_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_npolar(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_aqua(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = aqua_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_aqua(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_opencom(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = opencom_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_opencom(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_portal(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = portal_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_portal(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nin(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nin_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nin(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ngu(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ngu_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ngu(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_sodir(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = sodir_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_sodir(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_riksantikvaren(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = riksantikvaren_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_riksantikvaren(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ragis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ragis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ragis(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_kystwfs(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kystwfs_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path)
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_kystwfs(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ldirwms(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ldirwms_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path)
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ldirwms(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_mdirgis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = mdirgis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path, headers={"Accept": "application/xml, text/xml, */*"})
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_mdirgis(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_barmark(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = barmark_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path, headers={"Accept": "application/xml, text/xml, */*"})
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_barmark(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nordatlas(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nordatlas_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path, headers={"Accept": "application/xml, text/xml, */*"})
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nordatlas(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_mdirwms(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = mdirwms_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path, headers={"Accept": "application/xml, text/xml, */*"})
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_mdirwms(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_vegwms(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = vegwms_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path, headers={"Accept": "application/xml, text/xml, */*"})
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_vegwms(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_hiwms(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = hiwms_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path, headers={"Accept": "application/xml, text/xml, */*"})
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_hiwms(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_bwgis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = bwgis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path, headers={"Accept": "application/xml, text/xml, */*"})
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_bwgis(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_fbgis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = fbgis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path, headers={"Accept": "application/xml, text/xml, */*"})
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_fbgis(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_mattilsyn(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = mattilsyn_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path, headers={"Accept": "application/xml, text/xml, */*"})
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_mattilsyn(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_research(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = research_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_research(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nytek(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nytek_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nytek(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_buyer(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = buyer_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_buyer(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_sikt(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = sikt_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_sikt(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nbr(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nbr_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nbr(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nor(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nor_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nor(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_npr(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = npr_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_npr(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nfr(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nfr_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nfr(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nxr(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nxr_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nxr(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_baf(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = baf_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_baf(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nbcodelist(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nbcodelist_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nbcodelist(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_fdkorg(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = fdkorg_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_fdkorg(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_kikommuner(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kikommuner_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_kikommuner(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_kifylker(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kifylker_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_kifylker(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nbagency(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nbagency_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nbagency(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nbconcept(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nbconcept_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nbconcept(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_norgesbank(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = norgesbank_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_norgesbank(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_hoydedata(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = hoydedata_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_hoydedata(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_transformering(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = transformering_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_transformering(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_kommuneinfo(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kommuneinfo_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_kommuneinfo(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_stedsnavn(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = stedsnavn_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_stedsnavn(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_udir(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = udir_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_udir(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_entur(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = entur_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    request_url = access_path
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        feed_url = printed_feed_url(got.body, VEHICLE_TYPES_FEED)
        if feed_url:
            request_url = feed_url
            got = client.get_json_response(feed_url)
            http_status = got.status
        registry.set_fetch_request(run_id, request_url=request_url, request_body={"method": "GET"})
        cells = cells_from_entur(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=request_url,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": request_url})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=request_url,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_fiskeridir(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = fiskeridir_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_fiskeridir(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_statnett(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = statnett_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_statnett(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_hi(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = hi_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_hi(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_utdanning(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = utdanning_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_utdanning(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nowcast(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nowcast_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nowcast(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_textforecast(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = textforecast_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_textforecast(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_icemap(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = icemap_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_icemap(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_tafmetar(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = tafmetar_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_tafmetar(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_geosatellite(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = geosatellite_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_geosatellite(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_subjectiveforecast(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = subjectiveforecast_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_subjectiveforecast(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_radar(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = radar_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_radar(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_oceanforecast(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = oceanforecast_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_oceanforecast(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_airquality(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = airquality_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_airquality(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_tidalwater(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = tidalwater_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_tidalwater(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ncagalewarnings(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ncagalewarnings_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ncagalewarnings(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_metgm(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = metgm_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_metgm(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_polarsatellite(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = polarsatellite_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_polarsatellite(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_soundprofile(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = soundprofile_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_soundprofile(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_oslofjord(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = oslofjord_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_oslofjord(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_gribfiles(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = gribfiles_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_gribfiles(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_metgc(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = metgc_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_metgc(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_isobaricgrib(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = isobaricgrib_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_isobaricgrib(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_offshoremaps(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = offshoremaps_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_offshoremaps(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_turbulence(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = turbulence_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_turbulence(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nlaroutes(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nlaroutes_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nlaroutes(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_sigcharts(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = sigcharts_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_sigcharts(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_norskelos(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = norskelos_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_norskelos(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_georegister(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = georegister_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_georegister(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_lister(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = lister_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_lister(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_crproj(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "crproj":
        return _fetch_cristin(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = crproj_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_crproj(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_crbio(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "crbio":
        return _fetch_cristin(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = crbio_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_crbio(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_crunit(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "crunit":
        return _fetch_cristin(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = crunit_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_crunit(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_crinst(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "crinst":
        return _fetch_cristin(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = crinst_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_crinst(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_cristin(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = cristin_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_cristin(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_artskart(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = artskart_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_artskart(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_volcanicashforecast(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = volcanicashforecast_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_volcanicashforecast(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_routeforecast(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = routeforecast_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_routeforecast(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_locationforecast(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = locationforecast_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_locationforecast(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nortaxa(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nortaxa_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nortaxa(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ogccoverages(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ogccoverages_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ogccoverages(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_hicoverages(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = hicoverages_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_hicoverages(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nvemap(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nvemap_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nvemap(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nvegis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nvegis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nvegis(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_navwarnings(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = navwarnings_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_navwarnings(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_hoydegis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = hoydegis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_hoydegis(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_fiskerigis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = fiskerigis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_fiskerigis(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nve2gis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nve2gis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nve2gis(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_miljogis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = miljogis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_miljogis(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_hitiles(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = hitiles_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_hitiles(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_himaps(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = himaps_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_himaps(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_havnedata(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = havnedata_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_havnedata(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_npigis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = npigis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_npigis(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_npitema(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = npitema_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_npitema(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_arcticsdi(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = arcticsdi_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_arcticsdi(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_aviationforecast(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = aviationforecast_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_aviationforecast(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_vindkraft(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = vindkraft_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_vindkraft(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nbdsd(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nbdsd_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nbdsd(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ssbsec(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ssbsec_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ssbsec(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nbdps(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nbdps_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nbdps(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nbprov(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nbprov_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nbprov(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_elcert(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = elcert_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_elcert(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_regobs(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = regobs_table_id(access_path, dataset.get("source_native_id"))
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_regobs(got.body, table_id=table_id)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_npiintern(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = npiintern_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_npiintern(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ssbfam(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ssbfam_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ssbfam(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ssbv2(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ssbv2_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ssbv2(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nibiowms(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nibiowms_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path)
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nibiowms(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_fdirwms(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = fdirwms_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path, headers={"Accept": "application/xml, text/xml, */*"})
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_fdirwms(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nibioar50(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nibioar50_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path, headers={"Accept": "application/xml, text/xml, */*"})
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nibioar50(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nibiorest(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nibiorest_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path)
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nibiorest(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nguminer(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nguminer_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(
            access_path,
            headers={"Accept": "application/xml, text/xml, */*"},
        )
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nguminer(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_ssbgis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ssbgis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(
            access_path,
            headers={"Accept": "application/xml, text/xml, */*"},
        )
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_ssbgis(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nguwms(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nguwms_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(
            access_path,
            headers={"Accept": "application/xml, text/xml, */*"},
        )
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nguwms(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_kvgrunn(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kvgrunn_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(
            access_path,
            headers={"Accept": "application/xml, text/xml, */*"},
        )
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_kvgrunn(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_kvtopo(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kvtopo_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(
            access_path,
            headers={"Accept": "application/xml, text/xml, */*"},
        )
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_kvtopo(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_kvwms(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kvwms_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(
            access_path,
            headers={"Accept": "application/xml, text/xml, */*"},
        )
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_kvwms(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_rawms(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = rawms_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path)
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_rawms(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_sigmets(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = sigmets_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_sigmets(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_grep(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = grep_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_grep(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_vannkraft(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = vannkraft_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_vannkraft(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_vegogc(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = vegogc_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path)
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_vegogc(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_brrepresent(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "brrepresent":
        return _fetch_brroller(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = brrepresent_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_brrepresent(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_brrolletype(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "brrolletype":
        return _fetch_brroller(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = brrolletype_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_brrolletype(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_brroller(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = brroller_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_brroller(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_broppdater(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = broppdater_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_broppdater(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_brunder(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = brunder_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_brunder(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_frivillig(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = frivillig_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_frivillig(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_sandnes(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = sandnes_table_id(access_path)
    query = {"query": PRINTED_QUERY}
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="POST",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        posted = client.post_json_response(access_path, query)
        http_status = posted.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body=query)
        cells = cells_from_sandnes(posted.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_stormflo(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = stormflo_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_stormflo(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_kystwms(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kystwms_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path)
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_kystwms(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_banegis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = banegis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path)
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_banegis(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_avinorgis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = avinorgis_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path)
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_avinorgis(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_kystnav(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kystnav_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        body = client.get_text(access_path)
        http_status = 200
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_kystnav(body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_miljorapporter(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = miljorapporter_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_miljorapporter(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_histyles(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = histyles_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_histyles(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_regnskap(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = regnskap_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_regnskap(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_omregning(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = omregning_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_omregning(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_envreportreg(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = envreportreg_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_envreportreg(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_stkomiteer(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "stkomiteer":
        return _fetch_stortinget(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = stkomiteer_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_stkomiteer(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_stperioder(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "stperioder":
        return _fetch_stortinget(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = stperioder_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_stperioder(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_stsaker(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "stsaker":
        return _fetch_stortinget(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = stsaker_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_stsaker(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_stpartier(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "stpartier":
        return _fetch_stortinget(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = stpartier_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_stpartier(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_stortinget(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = stortinget_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_stortinget(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_subseasonal(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = subseasonal_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_subseasonal(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_spotwind(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = spotwind_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_spotwind(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_sunrise(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = sunrise_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_sunrise(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_met(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = met_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_met(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_kystverket(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kystverket_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_kystverket(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_nibio(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nibio_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_nibio(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_miljodir(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = miljodir_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_miljodir(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_vegvesen(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = vegvesen_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_vegvesen(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_trondheim(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = trondheim_table_id(access_path)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        cells = cells_from_trondheim(got.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _store_cells(
    registry: Registry,
    dataset: dict[str, Any],
    run_id: int,
    *,
    table_id: str,
    cells: list[tuple[str, Any, dict[str, str]]],
    retrieved_at: str,
    request_url: str,
    http_status: int,
    counts: HarvestCounts,
) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for measure, value, dims in cells:
        observation = Observation(
            dataset_id=dataset["id"],
            table_id=table_id,
            measure=measure,
            value=value,
            dimensions=dims,
            retrieved_at=retrieved_at,
            request_url=request_url,
            http_status=http_status,
            publisher_name=dataset.get("publisher_name"),
            license=dataset.get("license"),
            access_path=dataset.get("access_path"),
            source_native_uri=dataset.get("source_native_uri"),
        )
        action = registry.upsert_observation(
            {
                "id": observation.identity_key(),
                "dataset_id": observation.dataset_id,
                "table_id": observation.table_id,
                "measure": observation.measure,
                "value": observation.value,
                "dimensions": observation.dimensions,
                "retrieved_at": observation.retrieved_at,
                "request_url": observation.request_url,
                "http_status": observation.http_status,
                "publisher_name": observation.publisher_name,
                "license": observation.license,
                "access_path": observation.access_path,
                "source_native_uri": observation.source_native_uri,
            },
            run_id,
        )
        if action == "inserted":
            counts.inserted += 1
        elif action == "updated":
            counts.updated += 1
        else:
            counts.unchanged += 1
        if len(sample) < 5:
            sample.append({"measure": measure, "value": value, "dimensions": dims})
    return sample


def _pxweb_query(meta: dict[str, Any], time_code: str, time_values: list[str]) -> dict[str, Any]:
    query: list[dict[str, Any]] = []
    for variable in meta.get("variables") or []:
        code = str(variable["code"])
        if code == time_code:
            query.append({"code": code, "selection": {"filter": "item", "values": time_values}})
        else:
            query.append({"code": code, "selection": {"filter": "all", "values": ["*"]}})
    return {"query": query, "response": {"format": "json-stat2"}}


def _metric_dimension(payload: dict[str, Any], ids: list[str]) -> str | None:
    if "Statistikkvariabel" in ids:
        return "Statistikkvariabel"
    role = payload.get("role") or {}
    metric = role.get("metric")
    if isinstance(metric, list) and metric:
        name = str(metric[0])
        if name != "ContentsCode":
            return name
    return None


def _unravel(index: int, sizes: list[int]) -> list[int]:
    coords: list[int] = []
    remaining = index
    for size in reversed(sizes):
        coords.append(remaining % size)
        remaining //= size
    coords.reverse()
    return coords


def _is_ssb_table_url(access_path: str) -> bool:
    parsed = urlparse(access_path)
    return parsed.netloc == "data.ssb.no" and parsed.path.startswith("/api/v0/")


def _year_from_label(label: str) -> int | None:
    digits = "".join(ch for ch in label if ch.isdigit())
    if len(digits) < 4:
        return None
    try:
        return int(digits[:4])
    except ValueError:
        return None
