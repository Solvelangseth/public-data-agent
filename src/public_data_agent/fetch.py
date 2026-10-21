from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path as _Path
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse

from public_data_agent.brreg_hal import brreg_table_id, cells_from_brreg, is_brreg_url
from public_data_agent.entity_records import (
    AIRQUALITY_ID_FIELDS,
    MET_ID_FIELDS,
    AIRQUALITY_LABEL_FIELDS,
    BRORGFORMEN_ID_FIELDS,
    BRREG_ID_FIELDS,
    BUYER_ID_FIELDS,
    FDKORG_ID_FIELDS,
    FISKERIDIR_ID_FIELDS,
    FRIVILLIG_ID_FIELDS,
    FRIVILLIG_LABEL_FIELDS,
    GEOREGISTER_ID_FIELDS,
    KIKOMMUNER_ID_FIELDS,
    NORGESBANK_ID_FIELDS,
    cells_are_labels,
    BRREG_LABEL_FIELDS,
    CRISTIN_ID_FIELDS,
    ENTUR_ID_FIELDS,
    ENVREPORT_ID_FIELDS,
    FEATURE_ID_FIELDS,
    GREP_ID_FIELDS,
    GREP_LABEL_FIELDS,
    records_from_cells,
)
from public_data_agent.geonorge_rest import (
    cells_from_geonorge,
    collection_request_url,
    geonorge_table_id,
    is_geonorge_rest_url,
    openapi_url,
)
from public_data_agent.http_util import HttpClient, JsonResponse, RateLimiter
from public_data_agent.models import HarvestCounts, SourceError
from public_data_agent.registry import Registry, utc_now
from public_data_agent.sources.nve import (
    MAGASIN_MAX_CELLS,
    OMRADE_SCHEME,
    cells_from_nve,
    is_nve_magasin_url,
    is_nve_minmax_url,
    is_nve_omrader_url,
    is_nve_siste_uke_url,
    lookups_from_nve_omrader,
    nve_table_id,
    requestable_url,
    rows_matching_iso_uke,
    selected_nve_iso_uke,
)
from public_data_agent.sources.fhi import (
    cells_from_fhi,
    fhi_table_id,
    is_fhi_table_url,
    is_fhi_url,
)
from public_data_agent.sources.mattilsynet import (
    MAX_LIMIT as MATTILSYNET_MAX_LIMIT,
    SUBJECT_SCHEME as MATTILSYNET_SCHEME,
    is_mattilsynet_preparat_url,
    is_mattilsynet_url,
    mattilsynet_table_id,
    products_from_payload as mattilsynet_products_from_payload,
    selected_product as mattilsynet_selected_product,
    shape_from_preparater as shape_from_mattilsynet,
)
from public_data_agent.sources.entur import (
    VEHICLE_TYPES_FEED,
    cells_from_entur,
    entur_table_id,
    is_entur_gbfs_url,
    printed_feed_url,
)
from public_data_agent.sources.aqua import (
    AQUA_MAX_CELLS,
    FISH_CODE_SCHEME,
    INTENTION_SCHEME,
    aqua_overview_request_url,
    aqua_table_id,
    cells_from_aqua_overview,
    is_aqua_fish_codes_url,
    is_aqua_intentions_url,
    is_aqua_overview_url,
    is_aqua_url,
    lookups_from_aqua_fish_codes,
    lookups_from_aqua_intentions,
    selected_license_nr,
)
from public_data_agent.sources.bwfish import (
    LOCALITY_ID_FIELDS as BWFISH_ID_FIELDS,
    LOCALITY_LABEL_FIELDS as BWFISH_LABEL_FIELDS,
    MEASURE as BWFISH_MEASURE,
    BarentsWatchToken,
    bwfish_table_id,
    cells_from_bwfish_localities,
    cells_from_bwfish_week,
    is_bwfish_localities_url,
    is_bwfish_url,
    is_bwfish_week_url,
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
from public_data_agent.sources.fdirpx import fdirpx_table_id, is_fdirpx_url
from public_data_agent.sources.ldirmelk import (
    FARM_LIMIT,
    cells_from_ldirmelk,
    is_ldirmelk_url,
    ldirmelk_table_id,
    shape_from_ldirmelk,
)
from public_data_agent.sources.naturvern import (
    DEFAULT_LIMIT as NATURVERN_DEFAULT_LIMIT,
    MAX_LIMIT as NATURVERN_MAX_LIMIT,
    SUBJECT_SCHEME as NATURVERN_SCHEME,
    feature_from_arcgis,
    is_naturvern_url,
    naturvern_table_id,
    query_url as naturvern_query_url,
    shape_from_layer as shape_from_naturvern_layer,
)
from public_data_agent.sources.anadrom import (
    DEFAULT_LIMIT as ANADROM_DEFAULT_LIMIT,
    MAX_LIMIT as ANADROM_MAX_LIMIT,
    SUBJECT_SCHEME as ANADROM_SCHEME,
    anadrom_table_id,
    feature_from_arcgis as anadrom_feature_from_arcgis,
    is_anadrom_url,
    query_url as anadrom_query_url,
    shape_from_layer as shape_from_anadrom_layer,
)
from public_data_agent.sources.friluft import (
    DEFAULT_LIMIT as FRILUFT_DEFAULT_LIMIT,
    MAX_LIMIT as FRILUFT_MAX_LIMIT,
    SUBJECT_SCHEME as FRILUFT_SCHEME,
    feature_from_arcgis as friluft_feature_from_arcgis,
    friluft_table_id,
    is_friluft_url,
    query_url as friluft_query_url,
    shape_from_layer as shape_from_friluft_layer,
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
from public_data_agent.sources.crperson import (
    cells_from_crperson,
    crperson_table_id,
    is_crperson_url,
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
from public_data_agent.sources.crresult import (
    cells_from_crresult,
    crresult_table_id,
    is_crresult_url,
)
from public_data_agent.sources.cristin import (
    cells_from_cristin,
    cristin_table_id,
    is_cristin_url,
)
from public_data_agent.sources.omregning import (
    OMREGNING_MAX_CELLS,
    cells_from_omregning,
    is_omregning_search_url,
    is_omregning_url,
    omregning_request_url,
    omregning_table_id,
    selected_fish,
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
from public_data_agent.sources.miljogis import is_miljogis_url
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
    PERIODER_SCHEME,
    cells_from_stortinget,
    is_stortinget_lookup_url,
    is_stortinget_url,
    is_stortingsperioder_url,
    lookup_catalog,
    lookups_from_payload,
    periods_from_payload,
    selected_lookup_ids,
    selected_periode_ids,
    shape_from_lookups,
    shape_from_perioder,
    stortinget_table_id,
)
from public_data_agent.sources.strepresent import (
    SUBJECT_SCHEME as STREPRESENT_SCHEME,
    is_dagensrepresentanter_url,
    representant_table_id,
    representanter_from_payload,
    selected_ids as representant_selected_ids,
    shape_from_representanter,
)
from public_data_agent.sources.stkomiteer import (
    SUBJECT_SCHEME as STKOMITEER_SCHEME,
    committees_from_payload as stkomiteer_from_payload,
    is_stkomiteer_url,
    selected_ids as stkomiteer_selected_ids,
    shape_from_komiteer as shape_from_stkomiteer,
    stkomiteer_table_id,
)
from public_data_agent.sources.stperioder import (
    MAX_LIMIT as STPERIODER_MAX_LIMIT,
    is_stperioder_url,
    representanter_from_payload as stperioder_from_payload,
    selected_member as stperioder_selected_member,
    shape_from_representanter as shape_from_stperioder,
    stperioder_table_id,
)
from public_data_agent.sources.stsaker import (
    MAX_LIMIT as STSAKER_MAX_LIMIT,
    SUBJECT_SCHEME as STSAKER_SCHEME,
    documents_from_payload as stsaker_documents_from_payload,
    is_stsaker_url,
    selected_sak as stsaker_selected_sak,
    shape_from_saker as shape_from_stsaker,
    stsaker_table_id,
)
from public_data_agent.sources.stpartier import (
    SUBJECT_SCHEME as STPARTIER_SCHEME,
    is_stpartier_url,
    parties_from_payload as stpartier_from_payload,
    selected_ids as stpartier_selected_ids,
    shape_from_partier as shape_from_stpartier,
    stpartier_table_id,
)
from public_data_agent.sources.stsporre import (
    MAX_LIMIT as STSPORRE_MAX_LIMIT,
    SUBJECT_SCHEME as STSPORRE_SCHEME,
    documents_from_payload as stsporre_documents_from_payload,
    is_stsporre_url,
    selected_question as stsporre_selected_question,
    shape_from_sporsmal as shape_from_stsporre,
    stsporre_table_id,
)
from public_data_agent.sources.stmoter import (
    MAX_LIMIT as STMOTER_MAX_LIMIT,
    SUBJECT_SCHEME as STMOTER_SCHEME,
    documents_from_payload as stmoter_documents_from_payload,
    is_stmoter_url,
    selected_mote as stmoter_selected_mote,
    shape_from_moter as shape_from_stmoter,
    stmoter_table_id,
)
from public_data_agent.sources.stskrift import (
    MAX_LIMIT as STSKRIFT_MAX_LIMIT,
    SUBJECT_SCHEME as STSKRIFT_SCHEME,
    documents_from_payload as stskrift_documents_from_payload,
    is_stskrift_url,
    selected_question as stskrift_selected_question,
    shape_from_sporsmal as shape_from_stskrift,
    stskrift_table_id,
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
from public_data_agent.sources.ssbfritid import (
    cells_from_ssbfritid,
    is_ssbfritid_url,
    ssbfritid_table_id,
)
from public_data_agent.sources.ssbv2 import (
    SSBV2_MAX_CELLS,
    cells_from_ssbv2,
    is_ssbv2_data_url,
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
from public_data_agent.sources.nvdb import (
    DEFAULT_OBJECT_LIMIT,
    HEADERS as NVDB_HEADERS,
    MAX_OBJECT_LIMIT,
    OBJECT_API,
    REQUESTS_PER_SECOND as NVDB_RPS,
    SUBJECT_SCHEME as NVDB_SCHEME,
    feature_from_vegobjekt,
    is_nvdb_collection_url,
    is_nvdb_object_url,
    nvdb_type_id,
)
from public_data_agent.sources.brenheter import (
    BRENHETER_ORGNR_LIMIT,
    BRENHETER_RPS,
    BRENHETER_BURST,
    ORGNR_SCHEME,
    brenheter_table_id,
    cells_from_brenheter,
    entity_from_enhet,
    is_brenheter_collection_url,
    is_brenheter_url,
    shape_from_brenheter,
    valid_orgnr,
)
from public_data_agent.sources.brkommuner import (
    BRKOMMUNER_BURST,
    BRKOMMUNER_RPS,
    BRREG_KOMMUNE_SCHEME,
    brkommuner_table_id,
    entity_from_brkommuner,
    is_brkommuner_url,
    shape_from_brkommuner,
)
from public_data_agent.sources.brorgform import (
    BRORGFORM_BURST,
    BRORGFORM_RPS,
    ORGFORM_SCHEME,
    brorgform_table_id,
    entity_from_brorgform,
    is_brorgform_url,
    shape_from_brorgform,
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
from public_data_agent.sources.nibioar5f import (
    cells_from_nibioar5f,
    is_nibioar5f_url,
    nibioar5f_table_id,
)
from public_data_agent.sources.nibiogard import (
    cells_from_nibiogard,
    is_nibiogard_url,
    nibiogard_table_id,
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
from public_data_agent.sources.kvadm import (
    cells_from_kvadm,
    is_kvadm_url,
    kvadm_table_id,
)
from public_data_agent.sources.kvkrets import (
    cells_from_kvkrets,
    is_kvkrets_url,
    kvkrets_table_id,
)
from public_data_agent.sources.dsbgis import (
    cells_from_dsbgis,
    dsbgis_table_id,
    is_dsbgis_url,
)
from public_data_agent.sources.kvfkb import (
    cells_from_kvfkb,
    is_kvfkb_url,
    kvfkb_table_id,
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
    is_vannkraft_url,
)
from public_data_agent.sources.vindkraft import (
    VINDKRAFT_MAX_CELLS,
    cells_from_vindkraft_power,
    is_vindkraft_plants_url,
    is_vindkraft_url,
    plants_matching_id,
    selected_vindkraft_id,
    vindkraft_table_id,
)
from public_data_agent.sources.vegogc import (
    cells_from_vegogc,
    is_vegogc_url,
    vegogc_table_id,
)
from public_data_agent.sources.elcert import (
    ELCERT_MAX_CELLS,
    cells_from_elcert_quarter,
    cells_from_elcert_summary,
    elcert_summary_request_url,
    elcert_table_id,
    filter_quarter_rows as elcert_filter_quarter_rows,
    is_elcert_quarter_url,
    is_elcert_summary_url,
    is_elcert_url,
    selected_quarters as elcert_selected_quarters,
    selected_year_month as elcert_selected_year_month,
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
    BRREPRESENT_BURST,
    BRREPRESENT_RPS,
    REPRESENTANT_SCHEME,
    brrepresent_table_id,
    entity_from_brrepresent,
    is_brrepresent_url,
    shape_from_brrepresent,
)
from public_data_agent.sources.brunder import (
    BRUNDER_BURST,
    BRUNDER_ORGNR_LIMIT,
    BRUNDER_RPS,
    brunder_table_id,
    cells_from_brunder,
    entity_from_brunder,
    is_brunder_collection_url,
    is_brunder_url,
    shape_from_brunder,
)
from public_data_agent.sources.brrollegruppe import (
    BRROLLEGRUPPE_BURST,
    BRROLLEGRUPPE_RPS,
    ROLLEGRUPPETYPE_SCHEME,
    brrollegruppe_table_id,
    entity_from_brrollegruppe,
    is_brrollegruppe_url,
    shape_from_brrollegruppe,
)
from public_data_agent.sources.brrolletype import (
    BRROLLETYPE_BURST,
    BRROLLETYPE_RPS,
    ROLLETYPE_SCHEME,
    brrolletype_table_id,
    entity_from_brrolletype,
    is_brrolletype_url,
    shape_from_brrolletype,
)
from public_data_agent.sources.brroller import (
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
    STORMFLO_MAX_CELLS,
    cells_from_stormflo,
    is_stormflo_national_url,
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
    DATAKILDE_SCHEME,
    TERRENG_SCHEME,
    hoydedata_table_id,
    is_hoydedata_datakilder_url,
    is_hoydedata_lookup_url,
    is_hoydedata_url,
    lookups_from_hoydedata,
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
    AREA_SCHEME,
    COUNTY_SCHEME,
    KYSTVERKET_MAX_CELLS,
    cells_from_kystverket_vessels,
    is_kystverket_counties_url,
    is_kystverket_fvpomr_url,
    is_kystverket_url,
    is_kystverket_vessels_by_type_url,
    kystverket_table_id,
    lookups_from_kystverket_counties,
    lookups_from_kystverket_fvpomr,
)
from public_data_agent.sources.miljodir import (
    ACTIVITY_SCHEME,
    MEDIUM_SCHEME,
    UNIT_SCHEME,
    is_miljodir_activity_list_url,
    is_miljodir_medium_list_url,
    is_miljodir_unit_list_url,
    is_miljodir_url,
    lookups_from_miljodir_activities,
    lookups_from_miljodir_mediums,
    lookups_from_miljodir_units,
    miljodir_table_id,
)
from public_data_agent.sources.trondheim import (
    cells_from_trondheim,
    is_trondheim_url,
    trondheim_table_id,
)
from public_data_agent.sources.met import (
    cells_from_met,
    is_met_metalerts_url,
    met_table_id,
)
from public_data_agent.sources.statnett import (
    FREQUENCY_MAX_CELLS,
    cells_from_statnett,
    cells_from_statnett_frequency,
    is_statnett_frequency_url,
    is_statnett_url,
    statnett_table_id,
)
from public_data_agent.sources.utdanning import (
    UTDANNING_MAX_CELLS,
    cells_from_utdanning_tidsserie,
    is_utdanning_tidsserie_url,
    is_utdanning_url,
    selected_kommune,
    tidsserie_request_url,
    tidsserie_total_items,
    utdanning_table_id,
)
from public_data_agent.sources.frost import (
    ELEMENT_ID_FIELDS as FROST_ELEMENT_ID_FIELDS,
    ELEMENT_LABEL_FIELDS as FROST_ELEMENT_LABEL_FIELDS,
    FROST_LICENSE,
    STATION_ID_FIELDS as FROST_STATION_ID_FIELDS,
    STATION_LABEL_FIELDS as FROST_STATION_LABEL_FIELDS,
    basic_auth_headers,
    cells_from_frost,
    cells_from_frost_elements,
    cells_from_frost_sources,
    frost_table_id,
    is_frost_observations_url,
    is_frost_timeseries_url,
    is_frost_url,
    observation_request_is_complete,
    printed_license as frost_printed_license,
)
from public_data_agent.sources.hi import (
    cells_and_geometry_from_hi,
    cells_and_geometry_from_hi,
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
    is_nbr_lookup_url,
    is_nbr_url,
    lookup_catalog as nbr_lookup_catalog,
    lookups_from_payload as nbr_lookups_from_payload,
    nbr_table_id,
    selected_lookup_ids as nbr_selected_lookup_ids,
    shape_from_lookups as shape_from_nbr_lookups,
)
from public_data_agent.sources.baf import (
    FYLKE_SCHEME,
    baf_table_id,
    is_baf_fylker_url,
    is_baf_url,
    lookups_from_baf_fylker,
)
from public_data_agent.sources.nfr import (
    cells_from_nfr,
    is_nfr_lookup_url,
    is_nfr_url,
    lookup_catalog as nfr_lookup_catalog,
    lookups_from_payload as nfr_lookups_from_payload,
    nfr_table_id,
    selected_lookup_ids as nfr_selected_lookup_ids,
    shape_from_lookups as shape_from_nfr_lookups,
)
from public_data_agent.sources.nor import (
    cells_from_nor,
    is_nor_lookup_url,
    is_nor_url,
    lookup_catalog as nor_lookup_catalog,
    lookups_from_payload as nor_lookups_from_payload,
    nor_table_id,
    selected_lookup_ids as nor_selected_lookup_ids,
    shape_from_lookups as shape_from_nor_lookups,
)
from public_data_agent.sources.npr import (
    cells_from_npr,
    is_npr_lookup_url,
    is_npr_url,
    lookup_catalog as npr_lookup_catalog,
    lookups_from_payload as npr_lookups_from_payload,
    npr_table_id,
    selected_lookup_ids as npr_selected_lookup_ids,
    shape_from_lookups as shape_from_npr_lookups,
)
from public_data_agent.sources.nxr import (
    cells_from_nxr,
    is_nxr_lookup_url,
    is_nxr_url,
    lookup_catalog as nxr_lookup_catalog,
    lookups_from_payload as nxr_lookups_from_payload,
    nxr_table_id,
    selected_lookup_ids as nxr_selected_lookup_ids,
    shape_from_lookups as shape_from_nxr_lookups,
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
    is_norgesbank_observations_url,
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
    is_udir_lookup_url,
    is_udir_nsr_url,
    lookup_catalog as udir_lookup_catalog,
    lookups_from_payload as udir_lookups_from_payload,
    selected_lookup_ids as udir_selected_lookup_ids,
    shape_from_lookups as shape_from_udir_lookups,
    udir_table_id,
)
from public_data_agent.sources.valg import (
    cells_from_valg,
    is_valg_url,
    valg_table_id,
)
from public_data_agent.ssb_klass import is_klass_url, klass_table_id, records_from_klass

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
    # Identity keys of the cells THIS request covered. A row already present is
    # reported "unchanged" and keeps its original fetch_run_id, so neither the
    # run id nor the series identifies what a given fetch actually asked for.
    observation_ids: list[str] = field(default_factory=list)


def can_fetch_access_path(access_path: str | None) -> bool:
    """Return whether an existing URL connector can attempt a real fetch.

    Connector predicates are the single source of truth used by
    ``fetch_observations``. This helper is intentionally capability-only: it
    does not perform network I/O and does not claim the endpoint is healthy.
    """

    if not access_path:
        return False
    if _is_ssb_table_url(access_path) or is_oslo_statbank_url(access_path):
        return True
    return any(
        predicate(access_path)
        for name, predicate in globals().items()
        if name.startswith("is_") and name.endswith("_url") and callable(predicate)
    )


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


def _jsonstat_index(category: dict[str, Any]) -> dict[str, int]:
    """Return ``category.index`` as {code: position}, whichever form it arrived in.

    json-stat2 permits an object mapping code to position *and* an array in
    positional order. SSB emits the object, FHI the array, and both conform.
    Reading only the object shape raised AttributeError on any source that
    chose the other one, so the format we already support looked unsupported.
    """

    index = category.get("index")
    if isinstance(index, dict):
        return {str(code): int(pos) for code, pos in index.items()}
    if isinstance(index, list):
        return {str(code): pos for pos, code in enumerate(index)}
    return {}


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
        index = _jsonstat_index(category)
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
            # ContentsCode is what the cell measures. Skipping it dropped the
            # distinction entirely: the measure fell back to the table's title,
            # so two cells differing only in which statistic they report became
            # identical in (measure, dimensions) -- the key observations are
            # unique on -- and one silently overwrote the other. Fetching 08650
            # with both of its statistics returned six cells and stored three,
            # and the survivors were percentage changes labelled as an index.
            if dim_id == "ContentsCode" or dim_id == metric_id:
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
    select: dict[str, list[str]] | None = None,
    kommune: str | None = None,
    fylke: str | None = None,
    bydel: str | None = None,
    measure: str | None = None,
    max_cells: int | None = None,
) -> FetchResult:
    """Retrieve observation rows, optionally under a cell budget.

    `max_cells` bounds what one request may store. Over it nothing is stored
    and the error says what the response held, because a partial table
    reported as success is worse than no answer. See `cell_budget`.
    """

    with cell_budget(max_cells):
        result = _fetch_observations(
            registry,
            dataset_id,
            table_id=table_id,
            from_year=from_year,
            to_year=to_year,
            http=http,
            select=select,
            kommune=kommune,
            fylke=fylke,
            bydel=bydel,
            measure=measure,
        )
    # A fetch that stored rows is the evidence, whichever branch ran it. Only
    # the branches that happened to remember were writing a capability, so a
    # successful FHI fetch of 4,224 numeric cells left the resource reading
    # `verified_at NULL` -- the counter said it worked and the registry said
    # nothing had. `record_evidence` never overwrites a verification already
    # earned and writes nothing when no row was stored.
    from public_data_agent.verify import record_evidence

    record_evidence(registry, dataset_id, result)
    return result


def _fetch_observations(
    registry: Registry,
    dataset_id: str,
    *,
    table_id: str,
    from_year: int | None = None,
    to_year: int | None = None,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
    kommune: str | None = None,
    fylke: str | None = None,
    bydel: str | None = None,
    measure: str | None = None,
) -> FetchResult:
    dataset = registry.get_dataset(dataset_id)
    if dataset is None:
        raise ValueError(f"unknown dataset {dataset_id}")
    from public_data_agent.resource_index import select_from_subjects

    select = select_from_subjects(
        registry,
        dataset_id,
        select=select,
        kommune=kommune,
        fylke=fylke,
        bydel=bydel,
        measure=measure,
    )
    access_path = dataset.get("access_path") or ""
    # GetCapabilities / WMS / WFS catalogs are not data. Fetching them stored
    # layer names as observations. Classify already reports `none`; refuse
    # before a leftover WMS dispatcher can write those cells.
    lowered = access_path.casefold()
    if any(mark in lowered for mark in _MAP_SERVICE_MARKS):
        raise ValueError(
            "access_path is a map/tile service (WMS/WFS/OGC); "
            "it returns imagery or geometry, not numeric cells"
        )
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
        return _fetch_nve_magasin(registry, dataset, http=http, select=select)
    if is_nvdb_object_url(access_path) or is_nvdb_collection_url(access_path):
        return _fetch_nvdb(registry, dataset, http=http, select=select)
    if is_ldirmelk_url(access_path):
        return _fetch_ldirmelk(registry, dataset, http=http, select=select)
    if is_brkommuner_url(access_path):
        return _fetch_brkommuner(registry, dataset, http=http, select=select)
    if is_brenheter_url(access_path):
        return _fetch_brenheter(registry, dataset, http=http, select=select)
    if is_brenheter_collection_url(access_path):
        raise ValueError(
            "Enhetsregisteret enheter collection/lastned is too large to fetch as one "
            "request; narrow to a single organisasjonsnummer via "
            f"{access_path.rstrip('/')}/{{orgnr}}"
        )
    if is_brorgformen_url(access_path):
        return _fetch_brorgformen(registry, dataset, http=http)
    if is_brorgform_url(access_path):
        return _fetch_brorgform(registry, dataset, http=http, select=select)
    if is_brrollegruppe_url(access_path):
        return _fetch_brrollegruppe(registry, dataset, http=http, select=select)
    if is_brrolletype_url(access_path):
        return _fetch_brrolletype(registry, dataset, http=http, select=select)
    if is_brrepresent_url(access_path):
        return _fetch_brrepresent(registry, dataset, http=http, select=select)
    if is_brroller_url(access_path):
        return _fetch_brroller(registry, dataset, http=http)
    if is_broppdater_url(access_path):
        return _fetch_broppdater(registry, dataset, http=http)
    if is_brunder_url(access_path):
        return _fetch_brunder(registry, dataset, http=http, select=select)
    if is_brunder_collection_url(access_path):
        raise ValueError(
            "Enhetsregisteret underenheter collection/lastned is too large to fetch as one "
            "request; narrow to a single organisasjonsnummer via "
            f"{access_path.rstrip('/')}/{{orgnr}}"
        )
    if is_brreg_url(access_path):
        return _fetch_brreg(registry, dataset, http=http)
    if is_valg_url(access_path):
        return _fetch_valg(registry, dataset, http=http)
    if is_fhi_table_url(access_path):
        return _fetch_fhi_table(
            registry,
            dataset,
            from_year=from_year,
            to_year=to_year,
            select=select,
            http=http,
        )
    if is_fhi_url(access_path):
        return _fetch_fhi(registry, dataset, http=http)
    if is_mattilsynet_url(access_path):
        return _fetch_mattilsynet(registry, dataset, http=http, select=select)
    if is_udir_lookup_url(access_path):
        return _fetch_udir_lookup(registry, dataset, http=http, select=select)
    if is_udir_nsr_url(access_path):
        return _fetch_udir(registry, dataset, http=http)
    if is_nbr_lookup_url(access_path):
        return _fetch_nbr_lookup(registry, dataset, http=http, select=select)
    if is_nbr_url(access_path):
        return _fetch_nbr(registry, dataset, http=http)
    if is_nor_lookup_url(access_path):
        return _fetch_nor_lookup(registry, dataset, http=http, select=select)
    if is_nor_url(access_path):
        return _fetch_nor(registry, dataset, http=http)
    if is_npr_lookup_url(access_path):
        return _fetch_npr_lookup(registry, dataset, http=http, select=select)
    if is_npr_url(access_path):
        return _fetch_npr(registry, dataset, http=http)
    if is_nfr_lookup_url(access_path):
        return _fetch_nfr_lookup(registry, dataset, http=http, select=select)
    if is_nfr_url(access_path):
        return _fetch_nfr(registry, dataset, http=http)
    if is_nxr_lookup_url(access_path):
        return _fetch_nxr_lookup(registry, dataset, http=http, select=select)
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
        return _fetch_norgesbank(registry, dataset, http=http, select=select)
    if is_npolar_url(access_path):
        return _fetch_npolar(registry, dataset, http=http)
    if is_sikt_url(access_path):
        return _fetch_sikt(registry, dataset, http=http)
    if is_buyer_url(access_path):
        return _fetch_buyer(registry, dataset, http=http)
    if is_nytek_url(access_path):
        return _fetch_nytek(registry, dataset, http=http)
    if is_aqua_url(access_path):
        return _fetch_aqua(registry, dataset, http=http, select=select)
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
    if is_nibioar5f_url(access_path):
        return _fetch_nibioar5f(registry, dataset, http=http)
    if dataset.get("source_id") == "nibiogard" or is_nibiogard_url(access_path):
        return _fetch_nibiogard(registry, dataset, http=http)
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
    if is_crperson_url(access_path):
        return _fetch_crperson(registry, dataset, http=http)
    if is_crresult_url(access_path):
        return _fetch_crresult(registry, dataset, http=http)
    if is_cristin_url(access_path):
        return _fetch_cristin(registry, dataset, http=http)
    if is_omregning_url(access_path):
        return _fetch_omregning(registry, dataset, http=http, select=select)
    if is_hicoverages_url(access_path):
        return _fetch_hicoverages(registry, dataset, http=http)
    if is_envreportreg_url(access_path):
        return _fetch_envreportreg(registry, dataset, http=http)
    if is_himaps_url(access_path):
        return _fetch_himaps(registry, dataset, http=http)
    if is_stkomiteer_url(access_path):
        return _fetch_stkomiteer(registry, dataset, http=http, select=select)
    if is_stperioder_url(access_path):
        return _fetch_stperioder(registry, dataset, http=http, select=select)
    if is_stsaker_url(access_path):
        return _fetch_stsaker(registry, dataset, http=http, select=select)
    if is_stpartier_url(access_path):
        return _fetch_stpartier(registry, dataset, http=http, select=select)
    if is_stsporre_url(access_path):
        return _fetch_stsporre(registry, dataset, http=http, select=select)
    if is_stmoter_url(access_path):
        return _fetch_stmoter(registry, dataset, http=http, select=select)
    if is_stskrift_url(access_path):
        return _fetch_stskrift(registry, dataset, http=http, select=select)
    if is_dagensrepresentanter_url(access_path):
        return _fetch_dagensrepresentanter(registry, dataset, http=http, select=select)
    if is_stortingsperioder_url(access_path):
        return _fetch_stortingsperioder(registry, dataset, http=http, select=select)
    if is_stortinget_lookup_url(access_path):
        return _fetch_stortinget_lookup(registry, dataset, http=http, select=select)
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
    if is_naturvern_url(access_path):
        return _fetch_naturvern(registry, dataset, http=http, select=select)
    if is_anadrom_url(access_path):
        return _fetch_anadrom(registry, dataset, http=http, select=select)
    if is_friluft_url(access_path):
        return _fetch_friluft(registry, dataset, http=http, select=select)
    # No Miljødirektoratet MapServer-root dispatch. That JSON lists layer
    # names; fetching it stored each layer's name as an observation. The
    # vern, anadromous-stretch and statlig-sikra layers are handled above.
    # Other MapServer catalogs are not data.
    if is_hoydegis_url(access_path):
        return _fetch_hoydegis(registry, dataset, http=http)
    if is_npitema_url(access_path):
        return _fetch_npitema(registry, dataset, http=http)
    if is_arcticsdi_url(access_path):
        return _fetch_arcticsdi(registry, dataset, http=http)
    if is_npiintern_url(access_path):
        return _fetch_npiintern(registry, dataset, http=http)
    if dataset.get("source_id") == "ssbfritid" or (
        is_ssbfritid_url(access_path) and dataset.get("source_id") != "ssbgis"
    ):
        return _fetch_ssbfritid(registry, dataset, http=http)
    if is_dsbgis_url(access_path):
        return _fetch_dsbgis(registry, dataset, http=http)
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
    if is_kvadm_url(access_path):
        return _fetch_kvadm(registry, dataset, http=http)
    if dataset.get("source_id") == "kvkrets" or is_kvkrets_url(access_path):
        return _fetch_kvkrets(registry, dataset, http=http)
    if dataset.get("source_id") == "kvfkb" or (
        is_kvfkb_url(access_path) and dataset.get("source_id") != "kvtopo"
    ):
        return _fetch_kvfkb(registry, dataset, http=http)
    if is_kvtopo_url(access_path):
        return _fetch_kvtopo(registry, dataset, http=http)
    if is_kvwms_url(access_path):
        return _fetch_kvwms(registry, dataset, http=http)
    if is_aviationforecast_url(access_path):
        return _fetch_aviationforecast(registry, dataset, http=http)
    if is_vannkraft_url(access_path):
        return _fetch_vannkraft(registry, dataset, http=http)
    if is_vindkraft_url(access_path):
        return _fetch_vindkraft(registry, dataset, http=http, select=select)
    if is_vegogc_url(access_path):
        return _fetch_vegogc(registry, dataset, http=http)
    if is_elcert_url(access_path):
        return _fetch_elcert(registry, dataset, http=http, select=select)
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
    if is_statnett_frequency_url(access_path):
        return _fetch_statnett_frequency(registry, dataset, http=http)
    if is_statnett_url(access_path):
        return _fetch_statnett(registry, dataset, http=http)
    if is_utdanning_url(access_path):
        return _fetch_utdanning(registry, dataset, http=http, select=select)
    if is_met_metalerts_url(access_path):
        return _fetch_met(registry, dataset, http=http)
    if is_bwfish_url(access_path):
        return _fetch_bwfish(registry, dataset, http=http)
    if is_frost_url(access_path):
        return _fetch_frost(registry, dataset, http=http)
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
    # No Statens vegvesen Dataportalen dispatch, on purpose. Its package_show
    # action returns catalogue metadata, and fetching it stored each resource's
    # description as an observation. A Vegvesen record now points at the service
    # itself; there is no connector for those services yet.
    client = http or HttpClient(timeout=60.0, max_retries=4)
    if (
        _is_ssb_table_url(access_path)
        or is_oslo_statbank_url(access_path)
        or is_fdirpx_url(access_path)
    ):
        request_url = access_path.rstrip("/")
        if is_oslo_statbank_url(access_path):
            table_id = oslo_table_id(access_path)
        elif is_fdirpx_url(access_path):
            table_id = fdirpx_table_id(access_path)
        else:
            table_id = request_url.rsplit("/", 1)[-1]
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
    touched: list[str] = []
    try:
        meta = client.get_json_response(request_url)
        time_code, selected = time_codes(meta.body, from_year=from_year, to_year=to_year)
        query = _pxweb_query(meta.body, time_code, selected, select=select, table_id=table_id)
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
            touched=touched,
        )
        existing = registry.get_capability(dataset["id"]) or {}
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": request_url,
                "request_method": "POST",
                "period_start": existing.get("period_start"),
                "period_end": existing.get("period_end"),
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "subject_scheme": existing.get("subject_scheme"),
                "subject_template": existing.get("subject_template"),
                "subject_count": existing.get("subject_count"),
                "notes": (
                    f"{counts.listed} PxWeb cell(s); measures are printed "
                    "json-stat labels"
                ),
            },
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
        observation_ids=touched,
    )


# FHI refuses a query that leaves any dimension unfiltered, so a selection is
# always fully specified and can always be counted before it is sent.
FHI_CELL_LIMIT = 800_000


def _fhi_selection(
    dimensions: list[dict[str, Any]],
    *,
    from_year: int | None,
    to_year: int | None,
    select: dict[str, list[str]] | None,
    table_id: str,
    cell_limit: int = FHI_CELL_LIMIT,
) -> list[dict[str, Any]]:
    """Name every value this query wants, for every dimension the table has.

    FHI 400s on a missing dimension rather than defaulting to all of it, which
    makes an accidental whole-table pull impossible but means the selection has
    to be built from the printed values rather than left implicit.
    """

    from public_data_agent.sources.fhi import flatten_categories, years_in

    chosen: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []
    cells = 1
    for dim in dimensions:
        code = str(dim.get("code") or "")
        values = flatten_categories(dim.get("categories"))
        available = len(values)
        codes = [value for value, _ in values]
        if select and code in select:
            wanted = {str(v) for v in select[code]}
            # An asked-for value the table does not print is a failed request,
            # not an empty one: silently dropping it answers a question nobody
            # asked and reports success.
            missing = sorted(wanted - set(codes))
            if missing:
                raise ValueError(
                    f"table {table_id} dimension {code} does not print "
                    f"value(s) {', '.join(missing)}"
                )
            codes = [value for value in codes if value in wanted]
        elif code == "AAR" and (from_year is not None or to_year is not None):
            kept = []
            for value in codes:
                years = years_in(value)
                if not years:
                    continue
                if from_year is not None and max(years) < from_year:
                    continue
                if to_year is not None and min(years) > to_year:
                    continue
                kept.append(value)
            # An empty period selection would fetch the whole table instead of
            # nothing, so an unsatisfiable range fails here.
            if not kept:
                raise ValueError(
                    f"table {table_id} prints no period between {from_year} and {to_year}"
                )
            codes = kept
        if not codes:
            raise ValueError(f"table {table_id} dimension {code} prints no values")
        cells *= len(codes)
        chosen.append({"code": code, "filter": "item", "values": codes})
        report.append(
            {
                "code": code,
                "text": str(dim.get("label") or code),
                "selected": len(codes),
                "available": available,
            }
        )
    if cells > cell_limit:
        raise SelectionTooLarge(table_id, cells, cell_limit, report)
    return chosen


def _fetch_fhi_table(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    from_year: int | None = None,
    to_year: int | None = None,
    select: dict[str, list[str]] | None = None,
    http: JsonHttp | None = None,
) -> FetchResult:
    """Fetch numeric cells from one FHI Statistikk table.

    FHI speaks json-stat2, the same format as SSB PxWeb, and prints geography
    as Klass codes, so the stored cells join to SSB rows without translation.
    """

    from public_data_agent.sources.fhi import split_table_url

    access_path = dataset.get("access_path") or ""
    source_id, table_id = split_table_url(access_path)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    dim_url = f"{access_path.rstrip('/')}/dimension?includeValues=true"
    data_url = f"{access_path.rstrip('/')}/data"
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=data_url,
        request_method="POST",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    touched: list[str] = []
    try:
        meta = client.get_json_response(dim_url)
        dimensions = (meta.body or {}).get("dimensions") or []
        if not dimensions:
            raise ValueError(f"FHI table {table_id} prints no dimensions")
        query = {
            "dimensions": _fhi_selection(
                dimensions,
                from_year=from_year,
                to_year=to_year,
                select=select,
                table_id=table_id,
            ),
            "response": {"format": "json-stat2"},
        }
        registry.set_fetch_request(run_id, request_url=data_url, request_body=query)
        posted = client.post_json_response(data_url, query)
        http_status = posted.status
        cells = cells_from_jsonstat(posted.body)
        counts.listed = len(cells)
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=utc_now(),
            request_url=data_url,
            http_status=http_status,
            counts=counts,
            series=f"fhi:{source_id}:{table_id}",
            touched=touched,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": data_url})
        raise
    finally:
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=data_url,
        http_status=http_status,
        counts=counts,
        sample=sample,
        observation_ids=touched,
    )


def _fetch_brenheter(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch one Enhetsregisteret company entity by organisasjonsnummer.

    A company is not a measure of anything: the row lands in `records` with
    kind `entity` and subject scheme `brreg:orgnr`. The orgnr is checked with
    mod-11 before the request is sent, and claimed as a key only after the
    enhet returns. Collection and lastned URLs are refused before send.
    """

    if dataset.get("source_id") != "brenheter":
        return _fetch_brreg(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    if is_brenheter_collection_url(access_path):
        raise ValueError(
            "Enhetsregisteret enheter collection/lastned is too large to fetch as one "
            "request; narrow to a single organisasjonsnummer via /enheter/{orgnr}"
        )
    table_id = brenheter_table_id(access_path)
    if not valid_orgnr(table_id):
        raise ValueError(
            f"organisasjonsnummer {table_id!r} fails the mod-11 check digit; "
            "refusing to fetch an unsatisfiable enhet request"
        )
    select = {str(k): v for k, v in (select or {}).items()}
    if select:
        unknown = sorted(key for key in select if key != "organisasjonsnummer")
        if unknown:
            raise ValueError(
                f"select names field(s) {unknown} that a brenheter enhet fetch does not "
                "filter on; only organisasjonsnummer is accepted"
            )
        wanted = select.get("organisasjonsnummer") or []
        wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
        if len(wanted) > BRENHETER_ORGNR_LIMIT:
            raise SelectionTooLarge(
                table_id,
                len(wanted),
                BRENHETER_ORGNR_LIMIT,
                [
                    {
                        "code": "organisasjonsnummer",
                        "text": "organisasjonsnummer",
                        "selected": len(wanted),
                        "available": 1,
                    }
                ],
            )
        if wanted and wanted != [table_id]:
            raise ValueError(
                f"select[organisasjonsnummer]={wanted!r} does not match this enhet "
                f"{table_id!r}; refusing to silently widen or redirect the request"
            )
    client = http or HttpClient(
        limiter=RateLimiter(BRENHETER_RPS, BRENHETER_BURST),
        timeout=60.0,
        max_retries=4,
    )
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        if http_status == 404:
            raise ValueError(
                f"Enhetsregisteret has no enhet {table_id}; unsatisfiable request"
            )
        if http_status >= 400:
            raise ValueError(
                f"Enhetsregisteret enhet GET returned HTTP {http_status} for {access_path}"
            )
        entity = entity_from_enhet(got.body)
        if entity["subject_code"] != table_id:
            raise ValueError(
                f"Enhetsregisteret enhet at {access_path} printed organisasjonsnummer "
                f"{entity['subject_code']!r}, not the requested {table_id!r}"
            )
        retrieved_at = utc_now()
        record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
        action = registry.upsert_record(
            {
                "id": record_id,
                "dataset_id": dataset["id"],
                "kind": "entity",
                "series": f"brenheter:{entity['subject_code']}",
                "subject_scheme": entity["subject_scheme"],
                "subject_code": entity["subject_code"],
                "subject_label": entity["subject_label"],
                "period": None,
                "measure": None,
                "value": None,
                "attributes": entity["attributes"],
                "retrieved_at": retrieved_at,
                "request_url": access_path,
                "http_status": http_status,
                "publisher_name": dataset.get("publisher_name"),
                "license": dataset.get("license"),
            },
            run_id,
        )
        counts.listed = 1
        if action == "inserted":
            counts.inserted += 1
        elif action == "updated":
            counts.updated += 1
        else:
            counts.unchanged += 1
        sample.append(
            {
                "kind": "entity",
                "subject_scheme": ORGNR_SCHEME,
                "subject_code": entity["subject_code"],
                "subject_label": entity["subject_label"],
                "attributes": entity["attributes"],
            }
        )
        touched.append(record_id)
        fields, keys = shape_from_brenheter(got.body)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_ENTITIES,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": 1,
            },
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
        observation_ids=touched,
    )


def _fetch_brkommuner(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "brkommuner":
        return _fetch_brreg(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = brkommuner_table_id(access_path)
    select = {str(key): value for key, value in (select or {}).items()}
    if select:
        unknown = sorted(key for key in select if key != "nummer")
        if unknown:
            raise ValueError(
                f"select names field(s) {unknown}; only kommune nummer is accepted"
            )
        wanted = select.get("nummer") or []
        wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
        if len(wanted) > 1:
            raise SelectionTooLarge(
                table_id, len(wanted), 1,
                [{"code": "nummer", "text": "nummer", "selected": len(wanted), "available": 1}],
            )
        if wanted and wanted != [table_id]:
            raise ValueError(
                f"select[nummer]={wanted!r} does not match kommune {table_id!r}; "
                "refusing to silently widen or redirect the request"
            )
    client = http or HttpClient(
        limiter=RateLimiter(BRKOMMUNER_RPS, BRKOMMUNER_BURST),
        timeout=60.0,
        max_retries=4,
    )
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
        if http_status >= 400:
            raise ValueError(f"Brreg kommune GET returned HTTP {http_status} for {access_path}")
        entity = entity_from_brkommuner(got.body)
        if entity["subject_code"] != table_id:
            raise ValueError(
                f"Brreg kommune at {access_path} printed nummer {entity['subject_code']!r}, "
                f"not requested {table_id!r}"
            )
        retrieved_at = utc_now()
        record_id = f"entity:{dataset['id']}:{table_id}"
        action = registry.upsert_record(
            {
                "id": record_id, "dataset_id": dataset["id"], "kind": "entity",
                "series": f"brkommuner:{table_id}",
                "subject_scheme": BRREG_KOMMUNE_SCHEME,
                "subject_code": table_id, "subject_label": entity["subject_label"],
                "period": None, "measure": None, "value": None,
                "attributes": entity["attributes"], "retrieved_at": retrieved_at,
                "request_url": access_path, "http_status": http_status,
                "publisher_name": dataset.get("publisher_name"),
                "license": dataset.get("license"),
            },
            run_id,
        )
        counts.listed = 1
        setattr(counts, action, 1)
        sample = [{"kind": "entity", **entity}]
        fields, keys = shape_from_brkommuner(got.body)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP, "record_kind": "entity",
                "endpoint": access_path, "request_method": "GET",
                "verified_at": retrieved_at, "verified_sample_count": 1,
            },
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
        observation_ids=[record_id] if status == "completed" else [],
    )


def _fetch_brrollegruppe(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "brrollegruppe":
        return _fetch_brreg(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = brrollegruppe_table_id(access_path)
    select = {str(key): value for key, value in (select or {}).items()}
    if select:
        unknown = sorted(key for key in select if key != "kode")
        if unknown:
            raise ValueError(
                f"select names field(s) {unknown}; only rollegruppetype kode is accepted"
            )
        wanted = select.get("kode") or []
        wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
        if len(wanted) > 1:
            raise SelectionTooLarge(
                table_id,
                len(wanted),
                1,
                [
                    {
                        "code": "kode",
                        "text": "kode",
                        "selected": len(wanted),
                        "available": 1,
                    }
                ],
            )
        if wanted and wanted != [table_id]:
            raise ValueError(
                f"select[kode]={wanted!r} does not match rollegruppetype {table_id!r}"
            )
    client = http or HttpClient(
        limiter=RateLimiter(BRROLLEGRUPPE_RPS, BRROLLEGRUPPE_BURST),
        timeout=60.0,
        max_retries=4,
    )
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
        if http_status >= 400:
            raise ValueError(
                f"Brreg rollegruppetype GET returned HTTP {http_status} for {access_path}"
            )
        entity = entity_from_brrollegruppe(got.body)
        if entity["subject_code"] != table_id:
            raise ValueError(
                f"Brreg rollegruppetype at {access_path} printed kode "
                f"{entity['subject_code']!r}, not requested {table_id!r}"
            )
        retrieved_at = utc_now()
        record_id = f"entity:{dataset['id']}:{table_id}"
        action = registry.upsert_record(
            {
                "id": record_id,
                "dataset_id": dataset["id"],
                "kind": "entity",
                "series": f"brrollegruppe:{table_id}",
                "subject_scheme": ROLLEGRUPPETYPE_SCHEME,
                "subject_code": table_id,
                "subject_label": entity["subject_label"],
                "period": None,
                "measure": None,
                "value": None,
                "attributes": entity["attributes"],
                "retrieved_at": retrieved_at,
                "request_url": access_path,
                "http_status": http_status,
                "publisher_name": dataset.get("publisher_name"),
                "license": dataset.get("license"),
            },
            run_id,
        )
        counts.listed = 1
        setattr(counts, action, 1)
        sample = [{"kind": "entity", **entity}]
        fields, keys = shape_from_brrollegruppe(got.body)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": 1,
            },
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
        observation_ids=[record_id] if status == "completed" else [],
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
        # A legal form is a code and the Norwegian for it.
        records = records_from_cells(
            cells_from_brorgformen(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=BRORGFORMEN_ID_FIELDS,
            label_fields=(),
            prefix="brorgformen",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch one Brreg organisation-form lookup concept as an entity record."""

    if dataset.get("source_id") != "brorgform":
        return _fetch_brreg(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = brorgform_table_id(access_path)
    select = {str(key): value for key, value in (select or {}).items()}
    if select:
        unknown = sorted(key for key in select if key != "kode")
        if unknown:
            raise ValueError(
                f"select names field(s) {unknown} that an organisation-form lookup does "
                "not filter on; only kode is accepted"
            )
        wanted = select.get("kode") or []
        wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
        if len(wanted) > 1:
            raise SelectionTooLarge(
                table_id,
                len(wanted),
                1,
                [{"code": "kode", "text": "kode", "selected": len(wanted), "available": 1}],
            )
        if wanted and wanted != [table_id]:
            raise ValueError(
                f"select[kode]={wanted!r} does not match organisation form {table_id!r}; "
                "refusing to silently widen or redirect the request"
            )
    client = http or HttpClient(
        limiter=RateLimiter(BRORGFORM_RPS, BRORGFORM_BURST),
        timeout=60.0,
        max_retries=4,
    )
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
        if http_status == 404:
            raise ValueError(f"Brreg has no organisation form {table_id!r}")
        if http_status >= 400:
            raise ValueError(
                f"Brreg organisation-form GET returned HTTP {http_status} for {access_path}"
            )
        entity = entity_from_brorgform(got.body)
        if entity["subject_code"] != table_id:
            raise ValueError(
                f"Brreg organisation form at {access_path} printed kode "
                f"{entity['subject_code']!r}, not requested {table_id!r}"
            )
        retrieved_at = utc_now()
        record_id = f"entity:{dataset['id']}:{table_id}"
        action = registry.upsert_record(
            {
                "id": record_id,
                "dataset_id": dataset["id"],
                "kind": "entity",
                "series": f"brorgform:{table_id}",
                "subject_scheme": ORGFORM_SCHEME,
                "subject_code": table_id,
                "subject_label": entity["subject_label"],
                "period": None,
                "measure": None,
                "value": None,
                "attributes": entity["attributes"],
                "retrieved_at": retrieved_at,
                "request_url": access_path,
                "http_status": http_status,
                "publisher_name": dataset.get("publisher_name"),
                "license": dataset.get("license"),
            },
            run_id,
        )
        counts.listed = 1
        if action == "inserted":
            counts.inserted = 1
        elif action == "updated":
            counts.updated = 1
        else:
            counts.unchanged = 1
        sample = [{"kind": "entity", **entity}]
        fields, keys = shape_from_brorgform(got.body)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": 1,
            },
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
        observation_ids=[record_id] if status == "completed" else [],
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
        # A classification item is a code and the thing it names, not a
        # measurement of anything, so it is stored as a record.
        records = records_from_klass(got.body, dataset["id"])
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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


def _fetch_naturvern(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch protected-area features from the vern ArcGIS layer.

    Default is a page of ten attribute records, no geometry. A named
    ``naturvernId`` fetches that one area. ``antall`` raises the page size up
    to a hard cap. An empty response is an error, not "there are none".
    """

    access_path = dataset.get("access_path") or ""
    table_id = naturvern_table_id(access_path)
    select = {str(k): v for k, v in (select or {}).items()}
    allowed = {"naturvernId", "antall"}
    unknown = sorted(key for key in select if key not in allowed)
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that a naturvern fetch does not filter on; "
            f"accepted: {sorted(allowed)}"
        )
    limit = NATURVERN_DEFAULT_LIMIT
    if "antall" in select:
        wanted = select["antall"]
        wanted = [wanted] if isinstance(wanted, str) else list(wanted)
        try:
            limit = int(str(wanted[0]))
        except (ValueError, IndexError) as exc:
            raise ValueError(f"select[antall]={select['antall']!r} is not a number") from exc
        if limit < 1:
            raise ValueError(f"select[antall]={limit} must be at least 1")
        if limit > NATURVERN_MAX_LIMIT:
            raise SelectionTooLarge(
                table_id,
                limit,
                NATURVERN_MAX_LIMIT,
                [
                    {
                        "code": "antall",
                        "text": "features per request",
                        "selected": limit,
                        "available": NATURVERN_MAX_LIMIT,
                    }
                ],
            )
    naturvern_id = None
    if "naturvernId" in select:
        values = select["naturvernId"]
        values = [values] if isinstance(values, str) else [str(v) for v in values]
        if len(values) != 1:
            raise ValueError("select naturvernId accepts exactly one id")
        naturvern_id = values[0]
        limit = 1
    request_url = naturvern_query_url(access_path, naturvern_id=naturvern_id, limit=limit)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
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
    touched: list[str] = []
    try:
        got = client.get_json_response(request_url)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=request_url, request_body={"method": "GET"})
        features = [
            item
            for item in ((got.body or {}).get("features") or [])
            if isinstance(item, dict)
        ]
        retrieved_at = utc_now()
        for payload in features:
            feature = feature_from_arcgis(payload)
            record_id = f"feature:{dataset['id']}:{feature['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "feature",
                    "series": "naturvern:naturvern_omrade",
                    "subject_scheme": feature["subject_scheme"],
                    "subject_code": feature["subject_code"],
                    "subject_label": feature["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": feature["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": request_url,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "feature",
                        "subject_scheme": NATURVERN_SCHEME,
                        "subject_code": feature["subject_code"],
                        "subject_label": feature["subject_label"],
                        "attributes": {
                            key: feature["attributes"][key]
                            for key in (
                                "naturvernId",
                                "offisieltNavn",
                                "verneform",
                                "kommune",
                            )
                            if key in feature["attributes"]
                        },
                    }
                )
        if not features:
            raise ValueError(
                f"vern layer returned no features for {request_url}; nothing was stored"
            )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_FEATURES,
                "record_kind": "feature",
                "endpoint": access_path.split("?", 1)[0].rstrip("/"),
                "request_method": "GET",
                "subject_scheme": NATURVERN_SCHEME,
                "subject_template": access_path.split("?", 1)[0].rstrip("/")
                + "/query?where=naturvernId='{subject}'&f=json",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": f"{counts.listed} protected area(s) fetched without geometry",
            },
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
        observation_ids=touched,
    )


def _fetch_anadrom(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch anadromous-stretch features from the laksefisk ArcGIS layer.

    Default is a page of ten attribute records, no geometry. A named
    ``vassdragsNR`` fetches that one river. ``elvenavn`` matches the printed
    river name. ``nasjonaltLaksevassdrag`` filters the printed Ja/Nei flag.
    ``antall`` raises the page size up to a hard cap. An empty response is
    an error, not "there are none".
    """

    access_path = dataset.get("access_path") or ""
    table_id = anadrom_table_id(access_path)
    select = {str(k): v for k, v in (select or {}).items()}
    allowed = {"vassdragsNR", "elvenavn", "nasjonaltLaksevassdrag", "antall"}
    unknown = sorted(key for key in select if key not in allowed)
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that an anadrom fetch does not filter on; "
            f"accepted: {sorted(allowed)}"
        )
    limit = ANADROM_DEFAULT_LIMIT
    if "antall" in select:
        wanted = select["antall"]
        wanted = [wanted] if isinstance(wanted, str) else list(wanted)
        try:
            limit = int(str(wanted[0]))
        except (ValueError, IndexError) as exc:
            raise ValueError(f"select[antall]={select['antall']!r} is not a number") from exc
        if limit < 1:
            raise ValueError(f"select[antall]={limit} must be at least 1")
        if limit > ANADROM_MAX_LIMIT:
            raise SelectionTooLarge(
                table_id,
                limit,
                ANADROM_MAX_LIMIT,
                [
                    {
                        "code": "antall",
                        "text": "features per request",
                        "selected": limit,
                        "available": ANADROM_MAX_LIMIT,
                    }
                ],
            )

    def _one(name: str) -> str | None:
        if name not in select:
            return None
        values = select[name]
        values = [values] if isinstance(values, str) else [str(v) for v in values]
        if len(values) != 1:
            raise ValueError(f"select {name} accepts exactly one value")
        return values[0]

    vassdrags_nr = _one("vassdragsNR")
    elvenavn = _one("elvenavn")
    nasjonalt = _one("nasjonaltLaksevassdrag")
    if vassdrags_nr:
        limit = 1
    request_url = anadrom_query_url(
        access_path,
        vassdrags_nr=vassdrags_nr,
        elvenavn=elvenavn,
        nasjonalt_laksevassdrag=nasjonalt,
        limit=limit,
    )
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
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
    touched: list[str] = []
    try:
        got = client.get_json_response(request_url)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=request_url, request_body={"method": "GET"})
        features = [
            item
            for item in ((got.body or {}).get("features") or [])
            if isinstance(item, dict)
        ]
        retrieved_at = utc_now()
        for payload in features:
            feature = anadrom_feature_from_arcgis(payload)
            record_id = f"feature:{dataset['id']}:{feature['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "feature",
                    "series": "anadrom:anadrome_strekninger_lin",
                    "subject_scheme": feature["subject_scheme"],
                    "subject_code": feature["subject_code"],
                    "subject_label": feature["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": feature["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": request_url,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "feature",
                        "subject_scheme": ANADROM_SCHEME,
                        "subject_code": feature["subject_code"],
                        "subject_label": feature["subject_label"],
                        "attributes": {
                            key: feature["attributes"][key]
                            for key in (
                                "vassdragsNR",
                                "elvenavn",
                                "nasjonaltLaksevassdrag",
                                "lakseregURL",
                            )
                            if key in feature["attributes"]
                        },
                    }
                )
        if not features:
            raise ValueError(
                f"anadrom stretch layer returned no features for {request_url}; nothing was stored"
            )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_FEATURES,
                "record_kind": "feature",
                "endpoint": access_path.split("?", 1)[0].rstrip("/"),
                "request_method": "GET",
                "subject_scheme": ANADROM_SCHEME,
                "subject_template": access_path.split("?", 1)[0].rstrip("/")
                + "/query?where=vassdragsNR='{subject}'&f=json",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": f"{counts.listed} anadromous stretch(es) fetched without geometry",
            },
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
        observation_ids=touched,
    )


def _fetch_friluft(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch state-secured recreation-area features from the ArcGIS layer.

    Default is a page of ten attribute records, no geometry. A named
    ``friluftId`` fetches that one area. ``antall`` raises the page size up
    to a hard cap. An empty response is an error, not "there are none".
    """

    access_path = dataset.get("access_path") or ""
    table_id = friluft_table_id(access_path)
    select = {str(k): v for k, v in (select or {}).items()}
    allowed = {"friluftId", "antall"}
    unknown = sorted(key for key in select if key not in allowed)
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that a friluft fetch does not filter on; "
            f"accepted: {sorted(allowed)}"
        )
    limit = FRILUFT_DEFAULT_LIMIT
    if "antall" in select:
        wanted = select["antall"]
        wanted = [wanted] if isinstance(wanted, str) else list(wanted)
        try:
            limit = int(str(wanted[0]))
        except (ValueError, IndexError) as exc:
            raise ValueError(f"select[antall]={select['antall']!r} is not a number") from exc
        if limit < 1:
            raise ValueError(f"select[antall]={limit} must be at least 1")
        if limit > FRILUFT_MAX_LIMIT:
            raise SelectionTooLarge(
                table_id,
                limit,
                FRILUFT_MAX_LIMIT,
                [
                    {
                        "code": "antall",
                        "text": "features per request",
                        "selected": limit,
                        "available": FRILUFT_MAX_LIMIT,
                    }
                ],
            )
    friluft_id = None
    if "friluftId" in select:
        values = select["friluftId"]
        values = [values] if isinstance(values, str) else [str(v) for v in values]
        if len(values) != 1:
            raise ValueError("select friluftId accepts exactly one id")
        friluft_id = values[0]
        limit = 1
    request_url = friluft_query_url(access_path, friluft_id=friluft_id, limit=limit)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
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
    touched: list[str] = []
    try:
        got = client.get_json_response(request_url)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=request_url, request_body={"method": "GET"})
        features = [
            item
            for item in ((got.body or {}).get("features") or [])
            if isinstance(item, dict)
        ]
        retrieved_at = utc_now()
        for payload in features:
            feature = friluft_feature_from_arcgis(payload)
            record_id = f"feature:{dataset['id']}:{feature['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "feature",
                    "series": "friluft:friluftsliv_statlig_sikra",
                    "subject_scheme": feature["subject_scheme"],
                    "subject_code": feature["subject_code"],
                    "subject_label": feature["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": feature["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": request_url,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "feature",
                        "subject_scheme": FRILUFT_SCHEME,
                        "subject_code": feature["subject_code"],
                        "subject_label": feature["subject_label"],
                        "attributes": {
                            key: feature["attributes"][key]
                            for key in (
                                "friluftId",
                                "omraadeNavn",
                                "omraadeVerdi",
                                "faktaark",
                            )
                            if key in feature["attributes"]
                        },
                    }
                )
        if not features:
            raise ValueError(
                f"friluft layer returned no features for {request_url}; nothing was stored"
            )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_FEATURES,
                "record_kind": "feature",
                "endpoint": access_path.split("?", 1)[0].rstrip("/"),
                "request_method": "GET",
                "subject_scheme": FRILUFT_SCHEME,
                "subject_template": access_path.split("?", 1)[0].rstrip("/")
                + "/query?where=friluftId='{subject}'&f=json",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": f"{counts.listed} state-secured recreation area(s) fetched without geometry",
            },
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
        observation_ids=touched,
    )


def _fetch_ldirmelk(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch dairy-delivery litres from a Landbruksdirektoratet year CSV.

    Default is two national sums (kumelk, geitemelk). A farm extract must name
    organisasjonsnummer, and more than FARM_LIMIT farms is refused before parse
    of the selection, so a whole-register pull cannot look like success.
    """

    access_path = dataset.get("access_path") or ""
    table_id = ldirmelk_table_id(access_path)
    select = {str(k): v for k, v in (select or {}).items()}
    wanted = select.get("organisasjonsnummer")
    if wanted is not None:
        wanted_list = [wanted] if isinstance(wanted, str) else list(wanted)
        if len(wanted_list) > FARM_LIMIT:
            raise SelectionTooLarge(
                table_id,
                len(wanted_list),
                FARM_LIMIT,
                [
                    {
                        "code": "organisasjonsnummer",
                        "text": "organisasjonsnummer",
                        "selected": len(wanted_list),
                        "available": FARM_LIMIT,
                    }
                ],
            )
    client = http if http is not None and hasattr(http, "get_text") else HttpClient(
        timeout=60.0, max_retries=4
    )
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
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        cells = cells_from_ldirmelk(body, year=table_id, select=select or None)
        counts.listed = len(cells)
        retrieved_at = utc_now()
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=retrieved_at,
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        fields, keys = shape_from_ldirmelk(body, year=table_id)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        if cells:
            registry.set_capability(
                dataset["id"],
                {
                    "capability": CAPABILITY_OBSERVATIONS,
                    "record_kind": "observation",
                    "endpoint": access_path,
                    "request_method": "GET",
                    "verified_at": retrieved_at,
                    "verified_sample_count": len(cells),
                    "notes": (
                        f"{len(cells)} cell(s) from dairy deliveries; "
                        "litres to dairies, excluding local processing"
                    ),
                },
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


def _fetch_nve_magasin(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch last-week NVE Magasinstatistikk cells, extrema, or the area catalog.

    Measures are the printed float keys (fyllingsgrad, fylling_TWh, …).
    HentOmråder is lookup entities keyed by printed omrType and omrnr.
    MinMaxMedian is twenty-year extrema for one printed iso_uke.
    HentOffentligData is the 1995–present weekly dump and is refused.
    More than MAGASIN_MAX_CELLS is refused, not truncated.
    """

    access_path = dataset.get("access_path") or ""
    table_id = nve_table_id(access_path)
    if is_nve_omrader_url(access_path):
        return _fetch_nve_omrader(registry, dataset, http=http)
    if is_nve_minmax_url(access_path):
        return _fetch_nve_minmax(registry, dataset, http=http, select=select)
    if not is_nve_siste_uke_url(access_path):
        raise ValueError(
            "NVE Magasinstatistikk full dump is not a bounded observation "
            "fetch; use HentOffentligDataSisteUke or MinMaxMedian with "
            "select iso_uke"
        )
    request_url = requestable_url(access_path)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
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
        if len(cells) > MAGASIN_MAX_CELLS:
            raise SelectionTooLarge(
                table_id,
                len(cells),
                MAGASIN_MAX_CELLS,
                [
                    {
                        "code": "HentOffentligDataSisteUke",
                        "text": "last-week reservoir cells",
                        "selected": len(cells),
                        "available": MAGASIN_MAX_CELLS,
                    }
                ],
            )
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
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} last-week magasin cell(s); measures are "
                    "printed float keys"
                ),
            },
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


def _fetch_nve_minmax(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch one printed ISO week's twenty-year magasin extrema.

    Measures are printed min/median/max float keys. Unfiltered MinMaxMedian
    is 477 rows / 2862 cells and is refused. The request is the collection
    GET; rows are filtered to the printed ``iso_uke``.
    """

    access_path = dataset.get("access_path") or ""
    table_id = nve_table_id(access_path)
    iso_uke = selected_nve_iso_uke(select)
    request_url = requestable_url(access_path)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
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
        registry.set_fetch_request(
            run_id,
            request_url=request_url,
            request_body={"method": "GET", "select": select},
        )
        matched = rows_matching_iso_uke(got.body, iso_uke)
        cells = cells_from_nve(matched)
        if len(cells) > MAGASIN_MAX_CELLS:
            raise SelectionTooLarge(
                table_id,
                len(cells),
                MAGASIN_MAX_CELLS,
                [
                    {
                        "code": "iso_uke",
                        "text": "MinMaxMedian extrema cells",
                        "selected": len(cells),
                        "available": MAGASIN_MAX_CELLS,
                    }
                ],
            )
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
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} MinMaxMedian cell(s) for iso_uke="
                    f"{iso_uke}; measures are printed min/median/max floats"
                ),
            },
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


def _fetch_nve_omrader(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    """Fetch NVE magasin area catalog as lookup entities."""

    access_path = dataset.get("access_path") or ""
    table_id = nve_table_id(access_path)
    request_url = requestable_url(access_path)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
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
        registry.set_fetch_request(run_id, request_url=request_url, request_body={"method": "GET"})
        members = lookups_from_nve_omrader(got.body)
        retrieved_at = utc_now()
        for entity in members:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": "nve:omrader",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": request_url,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": entity["subject_scheme"],
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                    }
                )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "lookup",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": OMRADE_SCHEME,
                "subject_count": counts.listed,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} printed magasin area lookup entit"
                    f"{'y' if counts.listed == 1 else 'ies'} under {OMRADE_SCHEME}"
                ),
            },
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
        # An Enhetsregisteret HAL list is a register or a code list -- municipalities,
        # legal forms, role types, update notices. None of them measure anything.
        records = records_from_cells(
            cells_from_brreg(got.body, measure=measure),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=BRREG_ID_FIELDS,
            label_fields=BRREG_LABEL_FIELDS,
            prefix="brreg",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch plantevernmidler as product entities, not name observations.

    Default is a page of ten. ``select={"id": ["4572"]}`` returns that one
    product. ``antall`` raises the page size up to a hard cap. An unknown
    id is an error. Collection sizes vary; they are not all ingested.
    """

    access_path = dataset.get("access_path") or ""
    table_id = mattilsynet_table_id(access_path)
    wanted, limit = mattilsynet_selected_product(select)
    if wanted is None and limit > MATTILSYNET_MAX_LIMIT:
        raise SelectionTooLarge(
            table_id,
            limit,
            MATTILSYNET_MAX_LIMIT,
            [
                {
                    "code": "antall",
                    "text": "products per request",
                    "selected": limit,
                    "available": MATTILSYNET_MAX_LIMIT,
                }
            ],
        )
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        products = mattilsynet_products_from_payload(got.body)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in products}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"preparat id {missing} not in {table_id}; "
                    "the collection does not print that id"
                )
            products = [by_id[code] for code in wanted]
        else:
            products = products[:limit]
        retrieved_at = utc_now()
        for entity in products:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": f"mattilsynet:{table_id}",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": MATTILSYNET_SCHEME,
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                        "attributes": {
                            key: entity["attributes"][key]
                            for key in ("id", "navn", "registreringsnummer", "status", "form")
                            if key in entity["attributes"]
                        },
                    }
                )
        if not products:
            raise ValueError(
                f"plantevernmidler returned no products for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_mattilsynet(products)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_ENTITIES,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": MATTILSYNET_SCHEME,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} product record(s) from {table_id}; "
                    "names are labels, not observation values"
                ),
            },
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
        observation_ids=touched,
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
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch one printed aquaculture license's capacity cells, or fish-codes.

    Measures are printed ``capacity.current`` and ``capacity.accumulated``.
    Unfiltered overview defaults to range 0-9 and is refused. Fish-codes
    are lookup entities keyed by printed ``code``. Area and site catalogs
    store names and are refused.
    """

    access_path = dataset.get("access_path") or ""
    table_id = aqua_table_id(access_path)
    if is_aqua_fish_codes_url(access_path):
        return _fetch_aqua_lookup(
            registry,
            dataset,
            http=http,
            members_fn=lookups_from_aqua_fish_codes,
            scheme=FISH_CODE_SCHEME,
            series="aqua:fish-codes",
        )
    if is_aqua_intentions_url(access_path):
        return _fetch_aqua_lookup(
            registry,
            dataset,
            http=http,
            members_fn=lookups_from_aqua_intentions,
            scheme=INTENTION_SCHEME,
            series="aqua:intentions",
        )
    if not is_aqua_overview_url(access_path):
        raise ValueError(
            "Akvakulturregisteret name catalog is not a capacity observation "
            "fetch; use licenses-overview with select license-nr, or "
            "fish-codes for the printed species catalog"
        )
    license_nr = selected_license_nr(select)
    request_url = aqua_overview_request_url(access_path, license_nr)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
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
        registry.set_fetch_request(
            run_id,
            request_url=request_url,
            request_body={"method": "GET", "select": select},
        )
        if isinstance(got.body, list) and not got.body:
            raise ValueError(
                f"licenses-overview has no row matching license-nr={license_nr!r}; "
                "license-nr must be a printed license number"
            )
        cells = cells_from_aqua_overview(got.body)
        if len(cells) > AQUA_MAX_CELLS:
            raise SelectionTooLarge(
                table_id,
                len(cells),
                AQUA_MAX_CELLS,
                [
                    {
                        "code": "license-nr",
                        "text": "capacity cells",
                        "selected": len(cells),
                        "available": AQUA_MAX_CELLS,
                    }
                ],
            )
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
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} license capacity cell(s); measures are "
                    "printed capacity current and accumulated"
                ),
            },
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
        request_url=request_url,
        http_status=http_status,
        counts=counts,
        sample=sample,
    )


def _fetch_aqua_lookup(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    members_fn,
    scheme: str,
    series: str,
) -> FetchResult:
    """Fetch a printed Akvakulturregisteret catalog as lookup entities."""

    access_path = dataset.get("access_path") or ""
    table_id = aqua_table_id(access_path)
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
        members = members_fn(got.body)
        retrieved_at = utc_now()
        for entity in members:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": series,
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": entity["subject_scheme"],
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                    }
                )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "lookup",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": scheme,
                "subject_count": counts.listed,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} printed lookup entit"
                    f"{'y' if counts.listed == 1 else 'ies'} under {scheme}"
                ),
            },
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
        _refuse_service_catalogue(
            got.body, dataset_id=dataset["id"], url=access_path, what="layer"
        )
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
        # A fish buyer's registered location. Where no name is printed the connector
        # falls back to the location id, and a number that identifies is still not
        # a number that measures.
        records = records_from_cells(
            cells_from_buyer(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=BUYER_ID_FIELDS,
            label_fields=(),
            prefix="buyer",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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


def _fetch_nbr_lookup(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch a small NBR catalog as lookup entities, not name observations."""

    access_path = dataset.get("access_path") or ""
    spec = nbr_lookup_catalog(access_path)
    table_id = nbr_table_id(access_path)
    wanted = nbr_selected_lookup_ids(select)
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        members = nbr_lookups_from_payload(got.body, spec)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in members}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"id {missing} not in nbr:{table_id}; the catalog does not print that id"
                )
            members = [by_id[code] for code in wanted]
        retrieved_at = utc_now()
        for entity in members:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": f"nbr:{table_id}",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": entity["subject_scheme"],
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                    }
                )
        if not members:
            raise ValueError(
                f"nbr:{table_id} returned no members for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_nbr_lookups(members, spec)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": spec["scheme"],
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} lookup record(s) from nbr:{table_id}; "
                    "names are labels, not observation values"
                ),
            },
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
        observation_ids=touched,
    )


def _fetch_named_lookup(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None,
    select: dict[str, list[str]] | None,
    prefix: str,
    spec: dict[str, str],
    table_id: str,
    members: list[dict[str, Any]],
    access_path: str,
    request_url: str,
    http_status: int,
    run_id: int,
    retrieved_at: str,
    shape_fn,
) -> FetchResult:
    counts = HarvestCounts()
    sample: list[dict[str, Any]] = []
    touched: list[str] = []
    for entity in members:
        record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
        action = registry.upsert_record(
            {
                "id": record_id,
                "dataset_id": dataset["id"],
                "kind": "entity",
                "series": f"{prefix}:{table_id}",
                "subject_scheme": entity["subject_scheme"],
                "subject_code": entity["subject_code"],
                "subject_label": entity["subject_label"],
                "period": None,
                "measure": None,
                "value": None,
                "attributes": entity["attributes"],
                "retrieved_at": retrieved_at,
                "request_url": request_url,
                "http_status": http_status,
                "publisher_name": dataset.get("publisher_name"),
                "license": dataset.get("license"),
            },
            run_id,
        )
        counts.listed += 1
        if action == "inserted":
            counts.inserted += 1
        elif action == "updated":
            counts.updated += 1
        else:
            counts.unchanged += 1
        touched.append(record_id)
        if len(sample) < 3:
            sample.append(
                {
                    "kind": "entity",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                }
            )
    if not members:
        raise ValueError(
            f"{prefix}:{table_id} returned no members for {access_path}; nothing was stored"
        )
    fields, keys = shape_fn(members, spec)
    registry.set_resource_shape(dataset["id"], fields, keys=keys)
    registry.set_capability(
        dataset["id"],
        {
            "capability": CAPABILITY_LOOKUP,
            "record_kind": "entity",
            "endpoint": access_path,
            "request_method": "GET",
            "subject_scheme": spec["scheme"],
            "verified_at": retrieved_at,
            "verified_sample_count": counts.listed,
            "notes": (
                f"{counts.listed} lookup record(s) from {prefix}:{table_id}; "
                "names are labels, not observation values"
            ),
        },
    )
    return FetchResult(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=request_url,
        http_status=http_status,
        counts=counts,
        sample=sample,
        observation_ids=touched,
    )


def _fetch_nor_lookup(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    spec = nor_lookup_catalog(access_path)
    table_id = nor_table_id(access_path)
    wanted = nor_selected_lookup_ids(select)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    status = "failed"
    http_status = 0
    result: FetchResult | None = None
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        members = nor_lookups_from_payload(got.body, spec)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in members}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"id {missing} not in nor:{table_id}; the catalog does not print that id"
                )
            members = [by_id[code] for code in wanted]
        retrieved_at = utc_now()
        result = _fetch_named_lookup(
            registry,
            dataset,
            http=http,
            select=select,
            prefix="nor",
            spec=spec,
            table_id=table_id,
            members=members,
            access_path=access_path,
            request_url=access_path,
            http_status=http_status,
            run_id=run_id,
            retrieved_at=retrieved_at,
            shape_fn=shape_from_nor_lookups,
        )
        status = "completed"
        registry.finish_fetch_run(run_id, result.counts, status=status, http_status=http_status)
        return result
    except Exception as exc:
        counts = HarvestCounts()
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
        raise


def _fetch_npr_lookup(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    spec = npr_lookup_catalog(access_path)
    table_id = npr_table_id(access_path)
    wanted = npr_selected_lookup_ids(select)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    status = "failed"
    http_status = 0
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        members = npr_lookups_from_payload(got.body, spec)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in members}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"id {missing} not in npr:{table_id}; the catalog does not print that id"
                )
            members = [by_id[code] for code in wanted]
        retrieved_at = utc_now()
        result = _fetch_named_lookup(
            registry,
            dataset,
            http=http,
            select=select,
            prefix="npr",
            spec=spec,
            table_id=table_id,
            members=members,
            access_path=access_path,
            request_url=access_path,
            http_status=http_status,
            run_id=run_id,
            retrieved_at=retrieved_at,
            shape_fn=shape_from_npr_lookups,
        )
        status = "completed"
        registry.finish_fetch_run(run_id, result.counts, status=status, http_status=http_status)
        return result
    except Exception as exc:
        counts = HarvestCounts()
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
        raise


def _fetch_nfr_lookup(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    spec = nfr_lookup_catalog(access_path)
    table_id = nfr_table_id(access_path)
    wanted = nfr_selected_lookup_ids(select)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    status = "failed"
    http_status = 0
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        members = nfr_lookups_from_payload(got.body, spec)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in members}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"id {missing} not in nfr:{table_id}; the catalog does not print that id"
                )
            members = [by_id[code] for code in wanted]
        retrieved_at = utc_now()
        result = _fetch_named_lookup(
            registry,
            dataset,
            http=http,
            select=select,
            prefix="nfr",
            spec=spec,
            table_id=table_id,
            members=members,
            access_path=access_path,
            request_url=access_path,
            http_status=http_status,
            run_id=run_id,
            retrieved_at=retrieved_at,
            shape_fn=shape_from_nfr_lookups,
        )
        status = "completed"
        registry.finish_fetch_run(run_id, result.counts, status=status, http_status=http_status)
        return result
    except Exception as exc:
        counts = HarvestCounts()
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
        raise


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


def _fetch_nxr_lookup(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    spec = nxr_lookup_catalog(access_path)
    table_id = nxr_table_id(access_path)
    wanted = nxr_selected_lookup_ids(select)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=table_id,
        request_url=access_path,
        request_method="GET",
        started_at=started,
    )
    status = "failed"
    http_status = 0
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        members = nxr_lookups_from_payload(got.body, spec)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in members}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"id {missing} not in nxr:{table_id}; the catalog does not print that id"
                )
            members = [by_id[code] for code in wanted]
        retrieved_at = utc_now()
        result = _fetch_named_lookup(
            registry,
            dataset,
            http=http,
            select=select,
            prefix="nxr",
            spec=spec,
            table_id=table_id,
            members=members,
            access_path=access_path,
            request_url=access_path,
            http_status=http_status,
            run_id=run_id,
            retrieved_at=retrieved_at,
            shape_fn=shape_from_nxr_lookups,
        )
        status = "completed"
        registry.finish_fetch_run(run_id, result.counts, status=status, http_status=http_status)
        return result
    except Exception as exc:
        counts = HarvestCounts()
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": access_path})
        registry.finish_fetch_run(run_id, counts, status=status, http_status=http_status)
        raise


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
    """Fetch Barnehagefakta Fylker as lookup entities.

    Location is every kindergarten and is refused. Nested kommuner are
    not stored as separate entities.
    """

    access_path = dataset.get("access_path") or ""
    table_id = baf_table_id(access_path)
    if not is_baf_fylker_url(access_path):
        raise ValueError(
            "Barnehagefakta Location is every kindergarten; "
            "use Fylker for the printed county catalog"
        )
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
        members = lookups_from_baf_fylker(got.body)
        retrieved_at = utc_now()
        for entity in members:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": "baf:Fylker",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": entity["subject_scheme"],
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                    }
                )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "lookup",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": FYLKE_SCHEME,
                "subject_count": counts.listed,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} printed fylke lookup entit"
                    f"{'y' if counts.listed == 1 else 'ies'} under {FYLKE_SCHEME}"
                ),
            },
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
        # Felles datakatalog's organisation register.
        records = records_from_cells(
            cells_from_fdkorg(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=FDKORG_ID_FIELDS,
            label_fields=(),
            prefix="fdkorg",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
        # A municipality addressed by its number, which is what makes it a join key.
        records = records_from_cells(
            cells_from_kikommuner(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=KIKOMMUNER_ID_FIELDS,
            label_fields=(),
            prefix="kikommuner",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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


# A dataflow fetched as listed returns every series it holds for its whole
# history: EXR alone is decades of daily rates across dozens of currency pairs.
# SDMX takes `lastNObservations`, so the request is bounded at source rather
# than truncated after the fact.
NORGESBANK_DEFAULT_OBSERVATIONS = 5
NORGESBANK_MAX_OBSERVATIONS = 100
# `lastNObservations` bounds periods per series, not the number of series, and
# some flows have tens of thousands. MONEY_MARKET answered a one-period request
# with 34,906 cells and LIQUIDITY_FORECAST with 5,053, so a request can be
# bounded in one dimension and unbounded in the other. This is the other bound.
NORGESBANK_MAX_CELLS = 2000
# SDMX addresses one series inside a flow by key, which is how a caller narrows
# a flow that is too wide to read whole.
NORGESBANK_SUBJECT_SCHEME = "SDMX series key"


_SDMX_KEY_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")


def _norgesbank_series_key(
    registry: Registry,
    dataset_id: str,
    dimensions: list[dict[str, Any]],
    select: dict[str, Any],
) -> str | None:
    """An SDMX series key built from per-dimension selections, or None.

    Unselected dimensions are left empty, which SDMX reads as a wildcard, and
    several values for one dimension are joined with `+`. A value is checked
    before anything is sent, because the API answers a malformed key with a bare
    400 or 404 that says nothing about which position was wrong.
    """

    chosen = {field["field_code"]: select[field["field_code"]]
              for field in dimensions if field["field_code"] in select}
    if not chosen:
        return None
    positions: list[str] = []
    for field in sorted(dimensions, key=lambda item: item["position"]):
        code = field["field_code"]
        raw = chosen.get(code)
        if raw is None:
            positions.append("")
            continue
        values = [raw] if isinstance(raw, str) else [str(item) for item in raw]
        for value in values:
            if not _SDMX_KEY_SAFE.match(value):
                # GOVT_PRIMARY_MARKET's COUPON codes are like "0.00000000": the
                # dot is the key separator, so no key can carry that value.
                raise ValueError(
                    f"select[{code}]={value!r} contains characters an SDMX series key "
                    f"cannot carry; leave {code} unselected and narrow by another dimension"
                )
        stored = [
            row["value_code"]
            for row in registry.conn.execute(
                "SELECT value_code FROM resource_field_values WHERE dataset_id = ? AND field_code = ?",
                (dataset_id, code),
            )
        ]
        # Only a complete code list can refuse a value. MONEY_MARKET's COLL_ISIN
        # has 1,046 codes and the index keeps the first 400, so an absent code
        # there may still be real.
        if field.get("value_count") and len(stored) >= field["value_count"]:
            missing = [value for value in values if value not in stored]
            if missing:
                raise ValueError(
                    f"select[{code}] names {missing}, which this dataflow does not use; "
                    f"it uses {stored[:8]}{' ...' if len(stored) > 8 else ''}"
                )
        positions.append("+".join(values))
    return ".".join(positions)


def _norgesbank_request_url(access_path: str, observations: int) -> str:
    separator = "&" if "?" in access_path else "?"
    return f"{access_path}{separator}lastNObservations={observations}"


def _fetch_norgesbank(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    select = {str(key): value for key, value in (select or {}).items()}
    # A flow's series dimensions, in key order, when its shape has been
    # recorded. They are what a caller narrows by: selecting FX_CURRENCY=USD is
    # meaningful, while writing the positional key by hand is where a miscounted
    # dot turns into a bare 404.
    dimensions = [
        field for field in registry.resource_fields(dataset["id"])
        if field.get("position") is not None
    ]
    dimension_codes = [field["field_code"] for field in dimensions]
    unknown = sorted(
        key for key in select if key != "observations" and key not in dimension_codes
    )
    if unknown:
        accepted = ["observations", *dimension_codes]
        hint = (
            f"accepted: {accepted}"
            if dimension_codes
            else "only observations is accepted until this dataflow's dimensions are "
            "indexed; index it to narrow by dimension"
        )
        raise ValueError(
            f"select names field(s) {unknown} that a Norges Bank fetch does not "
            f"filter on; {hint}"
        )
    series_key = _norgesbank_series_key(registry, dataset["id"], dimensions, select)
    observations = NORGESBANK_DEFAULT_OBSERVATIONS
    wanted = select.get("observations")
    if wanted:
        wanted = [wanted] if isinstance(wanted, str) else [str(v) for v in wanted]
        try:
            observations = int(wanted[0])
        except ValueError as exc:
            raise ValueError(f"select[observations]={wanted[0]!r} is not a number") from exc
        if observations < 1:
            raise ValueError(f"select[observations]={observations} must be at least 1")
        if observations > NORGESBANK_MAX_OBSERVATIONS:
            raise SelectionTooLarge(
                norgesbank_table_id(access_path),
                observations,
                NORGESBANK_MAX_OBSERVATIONS,
                [{
                    "code": "observations",
                    "text": "periods per series",
                    "selected": observations,
                    "available": NORGESBANK_MAX_OBSERVATIONS,
                }],
            )
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = norgesbank_table_id(access_path)
    if series_key is not None:
        from urllib.parse import quote, urlsplit, urlunsplit

        parts = urlsplit(access_path)
        path = f"{parts.path.rstrip('/')}/{quote(series_key, safe='.+-_')}"
        access_path = urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))
    access_path = _norgesbank_request_url(access_path, observations)
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
        if len(cells) > NORGESBANK_MAX_CELLS:
            # Refused before anything is stored. Truncating would answer a
            # different question than the one asked and would look complete.
            #
            # The error lists the flow's real dimensions because the MCP tool
            # tells the caller to narrow by "the dimensions listed above". This
            # used to list one made-up dimension, `series`, which this fetcher
            # refuses as an unknown field -- so following the error's own
            # instructions failed.
            if dimensions:
                listed = []
                for field in dimensions:
                    chosen = select.get(field["field_code"])
                    chosen = [chosen] if isinstance(chosen, str) else list(chosen or [])
                    listed.append({
                        "code": field["field_code"],
                        "text": field.get("field_label") or field["field_code"],
                        "selected": len(chosen) or field.get("value_count"),
                        "available": field.get("value_count"),
                    })
            else:
                listed = [{
                    "code": "(dimensions not indexed)",
                    "text": "index this dataflow to learn the dimensions it can be narrowed by",
                    "selected": len(cells),
                    "available": NORGESBANK_MAX_CELLS,
                }]
            raise SelectionTooLarge(table_id, len(cells), NORGESBANK_MAX_CELLS, listed)
        counts.listed = len(cells)
        retrieved_at = utc_now()
        # Norges Bank publishes both kinds of thing through one SDMX endpoint:
        # interest-rate series, and auction calendars that print an ISIN per
        # date. The response says which this is, so each one is routed by what
        # came back rather than by a list of dataset ids kept somewhere.
        labels_only = cells_are_labels(cells)
        if labels_only:
            records = records_from_cells(
                cells,
                dataset_id=dataset["id"],
                table_id=table_id,
                id_fields=NORGESBANK_ID_FIELDS,
                prefix="norgesbank",
            )
            counts.listed = len(records)
            sample = _store_records(
                registry,
                dataset,
                run_id,
                records=records,
                retrieved_at=retrieved_at,
                request_url=access_path,
                http_status=http_status,
                counts=counts,
                series=f"fetch:{table_id}",
            )
        else:
            sample = _store_cells(
                registry,
                dataset,
                run_id,
                table_id=table_id,
                cells=cells,
                retrieved_at=retrieved_at,
                request_url=access_path,
                http_status=http_status,
                counts=counts,
            )
        if cells:
            # Observation flows classify as observations from the URL.
            # Calendars and wide dumps stay unverified until a bounded fetch
            # actually returns cells. This used to write `observations` for
            # whatever came back -- the comment said "having just read numeric
            # cells", but nothing had checked that they were numeric, and an
            # auction calendar of ISINs was filed as a rate series.
            registry.set_capability(
                dataset["id"],
                {
                    "capability": CAPABILITY_ENTITIES if labels_only else CAPABILITY_OBSERVATIONS,
                    "record_kind": "entity" if labels_only else "observation",
                    "endpoint": dataset.get("access_path"),
                    "request_method": "GET",
                    "subject_scheme": NORGESBANK_SUBJECT_SCHEME,
                    "subject_template": (
                        f"{(dataset.get('access_path') or '').split('?')[0]}/{{subject}}"
                    ),
                    "verified_at": retrieved_at,
                    "verified_sample_count": len(cells),
                    "notes": (
                        f"{len(cells)} row(s) read from a bounded request; "
                        + ("every value is a label" if labels_only else "values are numeric")
                    ),
                },
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
    """Fetch Høydedata datakilder/terrengtyper as lookup entities.

    Punkt needs printed coordinates and is refused. Leftover name cells
    are not stored.
    """

    access_path = dataset.get("access_path") or ""
    table_id = hoydedata_table_id(access_path)
    if not is_hoydedata_lookup_url(access_path):
        raise ValueError(
            "Kartverket Høydedata punkt needs printed coordinates; "
            "do not invent lat/lon. Fetch datakilder or terrengtyper"
        )
    kind = "datakilder" if is_hoydedata_datakilder_url(access_path) else "terrengtyper"
    scheme = DATAKILDE_SCHEME if kind == "datakilder" else TERRENG_SCHEME
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
        members = lookups_from_hoydedata(got.body, kind=kind)
        retrieved_at = utc_now()
        for entity in members:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": f"hoydedata:{kind}",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": entity["subject_scheme"],
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                    }
                )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "lookup",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": scheme,
                "subject_count": counts.listed,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} printed {kind} lookup entit"
                    f"{'y' if counts.listed == 1 else 'ies'} under {scheme}"
                ),
            },
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


def _fetch_udir_lookup(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch a small NSR catalog as lookup entities, not name observations."""

    access_path = dataset.get("access_path") or ""
    spec = udir_lookup_catalog(access_path)
    table_id = udir_table_id(access_path)
    wanted = udir_selected_lookup_ids(select)
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        members = udir_lookups_from_payload(got.body, spec)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in members}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"id {missing} not in udir:{table_id}; the catalog does not print that id"
                )
            members = [by_id[code] for code in wanted]
        retrieved_at = utc_now()
        for entity in members:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": f"udir:{table_id}",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": entity["subject_scheme"],
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                    }
                )
        if not members:
            raise ValueError(
                f"udir:{table_id} returned no members for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_udir_lookups(members, spec)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": spec["scheme"],
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} lookup entit(y/ies) from udir:{table_id}; "
                    "names are labels, not observation values"
                ),
            },
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
        observation_ids=touched,
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
        # A GBFS vehicle type is a model of scooter or bike, not a count of them.
        records = records_from_cells(
            cells_from_entur(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=ENTUR_ID_FIELDS,
            prefix="entur",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=request_url,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
        # A fishing vessel register. Its build year and engine power describe a
        # boat; they are not a published statistic about boats.
        records = records_from_cells(
            cells_from_fiskeridir(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=FISKERIDIR_ID_FIELDS,
            label_fields=(),
            prefix="fiskeridir",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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


def _bwfish_headers(token: BarentsWatchToken | None) -> dict[str, str]:
    """A bearer header for the api scope, from the environment or `.env`.

    The token is built per fetch rather than held module-wide: a long-running
    process that fetched a year of weeks would otherwise keep one object alive
    across hours, and the cache inside it is already per-object. Building it
    here also means a missing credential is reported by the fetch that needed
    it, named, rather than at import time for every connector.
    """

    token = token or BarentsWatchToken.from_env(dotenv=_Path(".env"))
    return token.headers()


def _fetch_frost(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    headers: dict[str, str] | None = None,
) -> FetchResult:
    """Fetch a Frost register, or a complete observation request.

    Three paths and two outcomes. `/sources` and `/elements` are registers and
    land in `records`. A `/observations` URL lands in `observations`, but only
    if it pins all three of sources, elements and referencetime -- Frost
    answers HTTP 400 to any request missing one, so an incomplete URL is not a
    resource and is refused here rather than fetched and recorded as broken.

    `/observations/availableTimeSeries` is refused outright. It is the service
    listing what it offers, which this project does not store; see
    `series_declared_by` for what it is read for instead.
    """

    access_path = dataset.get("access_path") or ""
    table_id = frost_table_id(access_path)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    if is_frost_timeseries_url(access_path):
        raise SourceError(
            "Frost availableTimeSeries lists what the service offers, which is "
            "metadata; it is read to build requests, never stored"
        )
    if is_frost_observations_url(access_path) and not observation_request_is_complete(access_path):
        raise SourceError(
            "a Frost observation request must pin sources, elements and "
            f"referencetime; {access_path} would answer HTTP 400"
        )
    if table_id not in ("sources", "elements", "observations"):
        raise SourceError(f"MET Frost has no reader for {access_path}")
    request_headers = dict(headers or basic_auth_headers(dotenv=_Path(".env")))
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
        got = client.get_json_response(access_path, headers=request_headers)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        retrieved_at = utc_now()
        declared = frost_printed_license(got.body)
        if declared is not None and declared != FROST_LICENSE:
            # The licence is copied from Frost rather than left null, so a
            # change in what Frost says must not pass unnoticed.
            raise SourceError(
                f"Frost now declares {declared!r}, not {FROST_LICENSE!r}; "
                "the recorded licence needs updating before this is stored"
            )
        if table_id == "observations":
            cells = cells_from_frost(got.body)
            counts.listed = len(cells)
            sample = _store_cells(
                registry,
                dataset,
                run_id,
                table_id=table_id,
                cells=cells,
                retrieved_at=retrieved_at,
                request_url=access_path,
                http_status=http_status,
                counts=counts,
            )
            registry.set_capability(
                dataset["id"],
                {
                    "capability": CAPABILITY_OBSERVATIONS,
                    "record_kind": "observation",
                    "endpoint": access_path,
                    "request_method": "GET",
                    "verified_at": retrieved_at,
                    "verified_sample_count": counts.listed,
                    "notes": (
                        f"{counts.listed} observation(s); one element at one instant can "
                        "appear several times at different level, timeResolution and "
                        "timeOffset, and all of them are kept"
                    ),
                },
            )
        else:
            if table_id == "sources":
                cells = cells_from_frost_sources(got.body)
                id_fields = FROST_STATION_ID_FIELDS
                label_fields = FROST_STATION_LABEL_FIELDS
            else:
                cells = cells_from_frost_elements(got.body)
                id_fields = FROST_ELEMENT_ID_FIELDS
                label_fields = FROST_ELEMENT_LABEL_FIELDS
            records = records_from_cells(
                cells,
                dataset_id=dataset["id"],
                table_id=table_id,
                id_fields=id_fields,
                label_fields=label_fields,
                prefix="frost",
                kind="entity",
            )
            counts.listed = len(records)
            sample = _store_records(
                registry,
                dataset,
                run_id,
                records=records,
                retrieved_at=retrieved_at,
                request_url=access_path,
                http_status=http_status,
                counts=counts,
                series=f"fetch:{table_id}",
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


def _fetch_bwfish(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    token: BarentsWatchToken | None = None,
) -> FetchResult:
    """Fetch BarentsWatch fish health: a week of lice counts, or the register.

    The two endpoints publish different kinds of thing and land in different
    tables. `/locality/{year}/{week}` is a measurement per farm and goes to
    `observations`; `/localities` is a list of places and goes to `records`.
    A path this connector claims but does not read is refused rather than
    guessed at, because the per-locality detail endpoint shares the first five
    segments with the weekly one and holds no lice count at all.
    """

    access_path = dataset.get("access_path") or ""
    table_id = bwfish_table_id(access_path)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    week = is_bwfish_week_url(access_path)
    register = is_bwfish_localities_url(access_path)
    if not (week or register):
        raise SourceError(
            f"BarentsWatch fish health has no reader for {access_path}; this "
            "connector reads /locality/{year}/{week} and /localities"
        )
    headers = _bwfish_headers(token)
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
        got = client.get_json_response(access_path, headers=headers)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        retrieved_at = utc_now()
        if week:
            cells = cells_from_bwfish_week(got.body)
            counts.listed = len(cells)
            sample = _store_cells(
                registry,
                dataset,
                run_id,
                table_id=table_id,
                cells=cells,
                retrieved_at=retrieved_at,
                request_url=access_path,
                http_status=http_status,
                counts=counts,
            )
            registry.set_capability(
                dataset["id"],
                {
                    "capability": CAPABILITY_OBSERVATIONS,
                    "record_kind": "observation",
                    "endpoint": access_path,
                    "request_method": "GET",
                    "verified_at": retrieved_at,
                    "verified_sample_count": counts.listed,
                    "notes": (
                        f"{counts.listed} locality/week {BWFISH_MEASURE} value(s); "
                        "localities reporting no count are absent, not zero; "
                        "municipalityNo is the publisher's own kommune key"
                    ),
                },
            )
        else:
            records = records_from_cells(
                cells_from_bwfish_localities(got.body),
                dataset_id=dataset["id"],
                table_id=table_id,
                id_fields=BWFISH_ID_FIELDS,
                label_fields=BWFISH_LABEL_FIELDS,
                prefix="bwfish",
                kind="entity",
            )
            counts.listed = len(records)
            sample = _store_records(
                registry,
                dataset,
                run_id,
                records=records,
                retrieved_at=retrieved_at,
                request_url=access_path,
                http_status=http_status,
                counts=counts,
                series=f"fetch:{table_id}",
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


def _fetch_statnett_frequency(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    """Fetch Statnett Frequency Measurements as Hz observations.

    Time for the i-th printed value is StartPointUTC + i * PeriodTickMs.
    An empty Measurements array is an error. More than FREQUENCY_MAX_CELLS
    is refused, not truncated.
    """

    access_path = dataset.get("access_path") or ""
    table_id = statnett_table_id(access_path)
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
        cells = cells_from_statnett_frequency(got.body)
        if len(cells) > FREQUENCY_MAX_CELLS:
            raise SelectionTooLarge(
                table_id,
                len(cells),
                FREQUENCY_MAX_CELLS,
                [
                    {
                        "code": "Measurements",
                        "text": "frequency samples",
                        "selected": len(cells),
                        "available": FREQUENCY_MAX_CELLS,
                    }
                ],
            )
        counts.listed = len(cells)
        retrieved_at = utc_now()
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=retrieved_at,
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} frequency Measurement(s); time is "
                    "StartPointUTC + i * PeriodTickMs"
                ),
            },
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
        # A spawning ground, a sampling station and a seismic advisory zone
        # are things in places, and the collection they come from is an OGC
        # features endpoint, not a table of measurements. The geometry rides
        # along with each cell so the record can keep it: a feature without
        # its geometry says a ground is a high-concentration spawning area and
        # never says where.
        paired = cells_and_geometry_from_hi(got.body)
        records = records_from_cells(
            [cell for cell, _geometry in paired],
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=FEATURE_ID_FIELDS,
            prefix="hi",
            kind="feature",
            # Where a feature publishes no identifier, its place is what tells
            # it from the next one: a bathymetry collection's contours all say
            # `depth = 1000` and differ only in geometry.
            distinguish=[geometry for _cell, geometry in paired],
        )
        for record, (_cell, geometry) in zip(records, paired):
            if geometry is not None:
                record["geometry"] = geometry
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch Utdanning.no tidsserie employment cells for one kommune.

    Measures are printed ``antall_ansatte`` and ``antall_aarsverk``.
    Unfiltered hydra (4171 rows) and name catalogs are refused. A page
    shorter than hydra:totalItems is refused, not truncated.
    """

    access_path = dataset.get("access_path") or ""
    table_id = utdanning_table_id(access_path)
    if not is_utdanning_tidsserie_url(access_path):
        raise ValueError(
            "Utdanning.no name catalog is not an employment observation fetch; "
            "use tidsserie with select kommune"
        )
    kommune = selected_kommune(select)
    request_url = tidsserie_request_url(access_path, kommune)
    client = http or HttpClient(timeout=90.0, max_retries=4)
    started = utc_now()
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
        registry.set_fetch_request(
            run_id,
            request_url=request_url,
            request_body={"method": "GET", "select": select},
        )
        if not isinstance(got.body, dict):
            raise ValueError("utdanning tidsserie response is not a JSON object")
        members = got.body.get("hydra:member")
        if not isinstance(members, list) or not members:
            raise ValueError(
                f"tidsserie has no row matching kommune={kommune!r}; "
                "kommune must be a printed municipality code"
            )
        total = tidsserie_total_items(got.body)
        if total is not None and total > len(members):
            raise SelectionTooLarge(
                table_id,
                total,
                len(members),
                [
                    {
                        "code": "kommune",
                        "text": "tidsserie hydra members",
                        "selected": total,
                        "available": len(members),
                    }
                ],
            )
        cells = cells_from_utdanning_tidsserie(got.body)
        if len(cells) > UTDANNING_MAX_CELLS:
            raise SelectionTooLarge(
                table_id,
                len(cells),
                UTDANNING_MAX_CELLS,
                [
                    {
                        "code": "kommune",
                        "text": "tidsserie cells",
                        "selected": len(cells),
                        "available": UTDANNING_MAX_CELLS,
                    }
                ],
            )
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
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} tidsserie cell(s); measures are printed "
                    "antall_ansatte and antall_aarsverk"
                ),
            },
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
        request_url=request_url,
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
        # An area class and a measuring station are things, not air quality readings.
        records = records_from_cells(
            cells_from_airquality(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=AIRQUALITY_ID_FIELDS,
            label_fields=AIRQUALITY_LABEL_FIELDS,
            prefix="airquality",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
        # met.no serves two listings through one connector. `/features` is the
        # set of products the service offers -- its own table of contents.
        # `/locations` is a register of real places: OSLO/GARDERMOEN under
        # ICAO ENGM is an airport, not a fact about the API.
        if table_id == "features":
            raise ServiceCatalogue(
                f"{dataset['id']}: {access_path} printed the products this service "
                f"offers, not a forecast. A product is requested by id with its own "
                f"parameters; nothing was stored."
            )
        records = records_from_cells(
            cells_from_gribfiles(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=MET_ID_FIELDS,
            prefix="gribfiles",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
        # Geonorge's register of object type definitions.
        records = records_from_cells(
            cells_from_georegister(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=GEOREGISTER_ID_FIELDS,
            label_fields=(),
            prefix="georegister",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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


def _fetch_crperson(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "crperson":
        return _fetch_cristin(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = crperson_table_id(access_path)
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
        # A Cristin member is a thing with a name, not a measurement of one.
        records = records_from_cells(
            cells_from_crperson(got.body), dataset_id=dataset["id"], table_id=table_id
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
        # A Cristin member is a thing with a name, not a measurement of one.
        records = records_from_cells(
            cells_from_crproj(got.body), dataset_id=dataset["id"], table_id=table_id
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
        # A Cristin member is a thing with a name, not a measurement of one.
        records = records_from_cells(
            cells_from_crbio(got.body), dataset_id=dataset["id"], table_id=table_id
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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


def _fetch_crresult(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "crresult":
        return _fetch_cristin(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = crresult_table_id(access_path)
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
        # A Cristin member is a thing with a name, not a measurement of one.
        records = records_from_cells(
            cells_from_crresult(got.body), dataset_id=dataset["id"], table_id=table_id
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
        # A Cristin member is a thing with a name, not a measurement of one.
        records = records_from_cells(
            cells_from_crunit(got.body), dataset_id=dataset["id"], table_id=table_id
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
        # A Cristin member is a thing with a name, not a measurement of one.
        records = records_from_cells(
            cells_from_crinst(got.body), dataset_id=dataset["id"], table_id=table_id
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
        # A Cristin member is a thing with a name, not a measurement of one.
        records = records_from_cells(
            cells_from_cristin(got.body), dataset_id=dataset["id"], table_id=table_id
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
        _refuse_service_catalogue(got.body, dataset_id=dataset["id"], url=access_path)
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
        _refuse_service_catalogue(
            got.body, dataset_id=dataset["id"], url=access_path, what="collection"
        )
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
        _refuse_service_catalogue(got.body, dataset_id=dataset["id"], url=access_path)
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
        # met.no serves two listings through one connector. `/features` is the
        # set of products the service offers -- its own table of contents.
        # `/locations` is a register of real places: OSLO/GARDERMOEN under
        # ICAO ENGM is an airport, not a fact about the API.
        if table_id == "features":
            raise ServiceCatalogue(
                f"{dataset['id']}: {access_path} printed the products this service "
                f"offers, not a forecast. A product is requested by id with its own "
                f"parameters; nothing was stored."
            )
        records = records_from_cells(
            cells_from_aviationforecast(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=MET_ID_FIELDS,
            prefix="aviationforecast",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch one printed wind plant's float cells.

    Measures are printed JSON float keys. Unfiltered GetWindPowerPlants
    and GetWindPowerPlantsInOperation copy ``Navn`` and are refused.
    Live ``/GetWindPowerPlants/{id}`` returns the same catalog as the
    collection, so the request is the collection GET and rows are
    filtered to the printed ``VindkraftAnleggId``.
    """

    access_path = dataset.get("access_path") or ""
    table_id = vindkraft_table_id(access_path)
    if not is_vindkraft_plants_url(access_path):
        raise ValueError(
            "NVE Vindkraftdatabase collection is 65 plant names; "
            "do not fetch Navn as observations. Use GetWindPowerPlants "
            "with select VindkraftAnleggId"
        )
    plant_id = selected_vindkraft_id(select)
    request_url = access_path
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
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
        registry.set_fetch_request(
            run_id,
            request_url=request_url,
            request_body={"method": "GET", "select": select},
        )
        matched = plants_matching_id(got.body, plant_id)
        cells = cells_from_vindkraft_power(matched)
        if len(cells) > VINDKRAFT_MAX_CELLS:
            raise SelectionTooLarge(
                table_id,
                len(cells),
                VINDKRAFT_MAX_CELLS,
                [
                    {
                        "code": "VindkraftAnleggId",
                        "text": "plant float cells",
                        "selected": len(cells),
                        "available": VINDKRAFT_MAX_CELLS,
                    }
                ],
            )
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
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} wind-plant cell(s); measures are "
                    "printed JSON float keys"
                ),
            },
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
        request_url=request_url,
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
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch NVE Elsertifikater summary cells.

    Quarterly and monthly totals copy printed IMaalet / IOvergangsordningen.
    GetApplications is a 914-name catalog and is refused.
    """

    access_path = dataset.get("access_path") or ""
    table_id = elcert_table_id(access_path)
    if not is_elcert_quarter_url(access_path) and not is_elcert_summary_url(access_path):
        raise ValueError(
            "NVE Elsertifikater GetApplications is a plant-name catalog; "
            "use GetSummaryValues or GetSummaryValuesPerQuarter"
        )
    request_url = access_path
    year = month = None
    if is_elcert_summary_url(access_path):
        year, month = elcert_selected_year_month(select)
        request_url = elcert_summary_request_url(access_path, year, month)
    client = http or HttpClient(timeout=120.0, max_retries=4)
    started = utc_now()
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
        registry.set_fetch_request(
            run_id, request_url=request_url, request_body={"method": "GET", "select": select}
        )
        if is_elcert_quarter_url(access_path):
            wanted = elcert_selected_quarters(select)
            rows = elcert_filter_quarter_rows(got.body, wanted)
            if wanted and not rows:
                raise ValueError(
                    f"GetSummaryValuesPerQuarter has no row matching {wanted}; "
                    "Year/Quarter must be printed values"
                )
            cells = cells_from_elcert_quarter(rows)
        else:
            cells = cells_from_elcert_summary(got.body, year=year, month=month)
        if len(cells) > ELCERT_MAX_CELLS:
            raise SelectionTooLarge(
                table_id,
                len(cells),
                ELCERT_MAX_CELLS,
                [
                    {
                        "code": table_id,
                        "text": "elsertifikat cells",
                        "selected": len(cells),
                        "available": ELCERT_MAX_CELLS,
                    }
                ],
            )
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
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} elsertifikat cell(s); measures are "
                    "printed IMaalet and IOvergangsordningen"
                ),
            },
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
        request_url=request_url,
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
    """Fetch SSB PxWebApi 2 json-stat2 cells from a printed data href.

    Measure names are the printed ContentsCode labels. The tables catalog
    lists table ids and is refused. More than SSBV2_MAX_CELLS is refused,
    not truncated. The default slice is the publisher's; no period is
    invented.
    """

    access_path = dataset.get("access_path") or ""
    table_id = ssbv2_table_id(access_path)
    if not is_ssbv2_data_url(access_path):
        raise ValueError(
            "SSB PxWebApi 2 tables catalog is not a json-stat2 observation "
            "fetch; use a printed /tables/{id}/data href"
        )
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
        if len(cells) > SSBV2_MAX_CELLS:
            raise SelectionTooLarge(
                table_id,
                len(cells),
                SSBV2_MAX_CELLS,
                [
                    {
                        "code": table_id,
                        "text": "json-stat2 cells",
                        "selected": len(cells),
                        "available": SSBV2_MAX_CELLS,
                    }
                ],
            )
        counts.listed = len(cells)
        retrieved_at = utc_now()
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=retrieved_at,
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} json-stat2 cell(s); measures are printed "
                    "ContentsCode labels"
                ),
            },
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


def _fetch_nibiogard(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nibiogard_table_id(access_path)
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
        cells = cells_from_nibiogard(body)
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


def _fetch_nibioar5f(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = nibioar5f_table_id(access_path)
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
        cells = cells_from_nibioar5f(body)
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


def _fetch_ssbfritid(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = ssbfritid_table_id(access_path)
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
        cells = cells_from_ssbfritid(body)
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


def _fetch_kvadm(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kvadm_table_id(access_path)
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
        cells = cells_from_kvadm(body)
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


def _fetch_kvkrets(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kvkrets_table_id(access_path)
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
        cells = cells_from_kvkrets(body)
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


def _fetch_dsbgis(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = dsbgis_table_id(access_path)
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
        cells = cells_from_dsbgis(body)
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


def _fetch_kvfkb(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=4)
    table_id = kvfkb_table_id(access_path)
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
        cells = cells_from_kvfkb(body)
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
        # A Udir curriculum code is a code, and the title it stands for is in
        # `tittel`, as language variants.
        records = records_from_cells(
            cells_from_grep(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=GREP_ID_FIELDS,
            label_fields=GREP_LABEL_FIELDS,
            prefix="grep",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
        )
        if records:
            # Udir publishes curriculum vocabularies: a code, the name it
            # stands for, when it was valid and where it sits in the order.
            # The connector says so itself rather than leaving it to be read
            # off the rows, because the row shape is a proxy that a connector
            # improvement can move -- copying the titles flipped 22 of these
            # from `lookup` to `entities` without the resources changing at
            # all. `brkommuner` declares its own role for the same reason.
            registry.set_capability(
                dataset["id"],
                {
                    "capability": CAPABILITY_LOOKUP,
                    "record_kind": "entity",
                    "endpoint": access_path,
                    "request_method": "GET",
                    "verified_at": utc_now(),
                    "verified_sample_count": len(records),
                    "notes": (
                        f"{len(records)} curriculum code(s) with the title Udir prints "
                        f"for them; a vocabulary, declared by the connector"
                    ),
                },
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
    """Refuse the hydropower plant-name catalog.

    Live GetHydroPowerPlantsInOperation is 1863 plants. The leftover
    decoder copies printed ``Navn``. That is not a bounded observation
    fetch. Plants have printed ``VannKraftverkID`` and ``MaksYtelse`` for
    a later entity or single-plant slice.
    """

    del registry, dataset, http
    raise ValueError(
        "NVE Vannkraftdatabase collection is 1863 plant names; "
        "do not fetch Navn as observations. A later slice can address "
        "one printed VannKraftverkID"
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
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "brrepresent":
        return _fetch_brroller(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = brrepresent_table_id(access_path)
    select = {str(key): value for key, value in (select or {}).items()}
    if select:
        unknown = sorted(key for key in select if key != "kode")
        if unknown:
            raise ValueError(
                f"select names field(s) {unknown}; only representant kode is accepted"
            )
        wanted = select.get("kode") or []
        wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
        if len(wanted) > 1:
            raise SelectionTooLarge(
                table_id,
                len(wanted),
                1,
                [
                    {
                        "code": "kode",
                        "text": "kode",
                        "selected": len(wanted),
                        "available": 1,
                    }
                ],
            )
        if wanted and wanted != [table_id]:
            raise ValueError(
                f"select[kode]={wanted!r} does not match representant {table_id!r}"
            )
    client = http or HttpClient(
        limiter=RateLimiter(BRREPRESENT_RPS, BRREPRESENT_BURST),
        timeout=60.0,
        max_retries=4,
    )
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
        if http_status >= 400:
            raise ValueError(
                f"Brreg representant GET returned HTTP {http_status} for {access_path}"
            )
        entity = entity_from_brrepresent(got.body)
        if entity["subject_code"] != table_id:
            raise ValueError(
                f"Brreg representant at {access_path} printed kode "
                f"{entity['subject_code']!r}, not requested {table_id!r}"
            )
        retrieved_at = utc_now()
        record_id = f"entity:{dataset['id']}:{table_id}"
        action = registry.upsert_record(
            {
                "id": record_id,
                "dataset_id": dataset["id"],
                "kind": "entity",
                "series": f"brrepresent:{table_id}",
                "subject_scheme": REPRESENTANT_SCHEME,
                "subject_code": table_id,
                "subject_label": entity["subject_label"],
                "period": None,
                "measure": None,
                "value": None,
                "attributes": entity["attributes"],
                "retrieved_at": retrieved_at,
                "request_url": access_path,
                "http_status": http_status,
                "publisher_name": dataset.get("publisher_name"),
                "license": dataset.get("license"),
            },
            run_id,
        )
        counts.listed = 1
        setattr(counts, action, 1)
        sample = [{"kind": "entity", **entity}]
        fields, keys = shape_from_brrepresent(got.body)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": 1,
            },
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
        observation_ids=[record_id] if status == "completed" else [],
    )


def _fetch_brrolletype(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    if dataset.get("source_id") != "brrolletype":
        return _fetch_brroller(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = brrolletype_table_id(access_path)
    select = {str(key): value for key, value in (select or {}).items()}
    if select:
        unknown = sorted(key for key in select if key != "kode")
        if unknown:
            raise ValueError(f"select names field(s) {unknown}; only rolletype kode is accepted")
        wanted = select.get("kode") or []
        wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
        if len(wanted) > 1:
            raise SelectionTooLarge(
                table_id, len(wanted), 1,
                [{"code": "kode", "text": "kode", "selected": len(wanted), "available": 1}],
            )
        if wanted and wanted != [table_id]:
            raise ValueError(f"select[kode]={wanted!r} does not match rolletype {table_id!r}")
    client = http or HttpClient(
        limiter=RateLimiter(BRROLLETYPE_RPS, BRROLLETYPE_BURST),
        timeout=60.0,
        max_retries=4,
    )
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
        if http_status >= 400:
            raise ValueError(f"Brreg rolletype GET returned HTTP {http_status} for {access_path}")
        entity = entity_from_brrolletype(got.body)
        if entity["subject_code"] != table_id:
            raise ValueError(
                f"Brreg rolletype at {access_path} printed kode {entity['subject_code']!r}, "
                f"not requested {table_id!r}"
            )
        retrieved_at = utc_now()
        record_id = f"entity:{dataset['id']}:{table_id}"
        action = registry.upsert_record(
            {
                "id": record_id, "dataset_id": dataset["id"], "kind": "entity",
                "series": f"brrolletype:{table_id}", "subject_scheme": ROLLETYPE_SCHEME,
                "subject_code": table_id, "subject_label": entity["subject_label"],
                "period": None, "measure": None, "value": None,
                "attributes": entity["attributes"], "retrieved_at": retrieved_at,
                "request_url": access_path, "http_status": http_status,
                "publisher_name": dataset.get("publisher_name"),
                "license": dataset.get("license"),
            },
            run_id,
        )
        counts.listed = 1
        setattr(counts, action, 1)
        sample = [{"kind": "entity", **entity}]
        fields, keys = shape_from_brrolletype(got.body)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP, "record_kind": "entity",
                "endpoint": access_path, "request_method": "GET",
                "verified_at": retrieved_at, "verified_sample_count": 1,
            },
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
        observation_ids=[record_id] if status == "completed" else [],
    )


def _fetch_brroller(
    _registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
) -> FetchResult:
    del http
    access_path = dataset.get("access_path") or ""
    raise ValueError(
        f"{access_path} is a Brreg code-list discovery collection, not company-role "
        "data; use the canonical brrolletype, brrollegruppe or brrepresent lookup "
        "datasets instead"
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
        # A change feed hands out an update id per notice; the notice is the thing.
        records = records_from_cells(
            cells_from_broppdater(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=BRREG_ID_FIELDS,
            label_fields=BRREG_LABEL_FIELDS,
            prefix="broppdater",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch one Enhetsregisteret sub-unit as an entity, never an observation."""

    if dataset.get("source_id") != "brunder":
        return _fetch_brreg(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = brunder_table_id(access_path)
    if not valid_orgnr(table_id):
        raise ValueError(
            f"organisasjonsnummer {table_id!r} fails the mod-11 check digit; "
            "refusing to fetch an unsatisfiable underenhet request"
        )
    select = {str(k): v for k, v in (select or {}).items()}
    if select:
        unknown = sorted(key for key in select if key != "organisasjonsnummer")
        if unknown:
            raise ValueError(
                f"select names field(s) {unknown} that a brunder underenhet fetch does not "
                "filter on; only organisasjonsnummer is accepted"
            )
        wanted = select.get("organisasjonsnummer") or []
        wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
        if len(wanted) > BRUNDER_ORGNR_LIMIT:
            raise SelectionTooLarge(
                table_id,
                len(wanted),
                BRUNDER_ORGNR_LIMIT,
                [
                    {
                        "code": "organisasjonsnummer",
                        "text": "organisasjonsnummer",
                        "selected": len(wanted),
                        "available": 1,
                    }
                ],
            )
        if wanted and wanted != [table_id]:
            raise ValueError(
                f"select[organisasjonsnummer]={wanted!r} does not match this underenhet "
                f"{table_id!r}; refusing to silently widen or redirect the request"
            )
    client = http or HttpClient(
        limiter=RateLimiter(BRUNDER_RPS, BRUNDER_BURST),
        timeout=60.0,
        max_retries=4,
    )
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=access_path, request_body={"method": "GET"})
        if http_status == 404:
            raise ValueError(f"Enhetsregisteret has no underenhet {table_id}; unsatisfiable request")
        if http_status >= 400:
            raise ValueError(
                f"Enhetsregisteret underenhet GET returned HTTP {http_status} for {access_path}"
            )
        entity = entity_from_brunder(got.body)
        if entity["subject_code"] != table_id:
            raise ValueError(
                f"Enhetsregisteret underenhet at {access_path} printed organisasjonsnummer "
                f"{entity['subject_code']!r}, not the requested {table_id!r}"
            )
        retrieved_at = utc_now()
        record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
        action = registry.upsert_record(
            {
                "id": record_id,
                "dataset_id": dataset["id"],
                "kind": "entity",
                "series": f"brunder:{entity['subject_code']}",
                "subject_scheme": entity["subject_scheme"],
                "subject_code": entity["subject_code"],
                "subject_label": entity["subject_label"],
                "period": None,
                "measure": None,
                "value": None,
                "attributes": entity["attributes"],
                "retrieved_at": retrieved_at,
                "request_url": access_path,
                "http_status": http_status,
                "publisher_name": dataset.get("publisher_name"),
                "license": dataset.get("license"),
            },
            run_id,
        )
        counts.listed = 1
        if action == "inserted":
            counts.inserted += 1
        elif action == "updated":
            counts.updated += 1
        else:
            counts.unchanged += 1
        sample.append(
            {
                "kind": "entity",
                "subject_scheme": ORGNR_SCHEME,
                "subject_code": entity["subject_code"],
                "subject_label": entity["subject_label"],
                "attributes": entity["attributes"],
            }
        )
        touched.append(record_id)
        fields, keys = shape_from_brunder(got.body)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_ENTITIES,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": 1,
            },
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
        observation_ids=touched,
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
        # The register of voluntary organisations, its category vocabulary and the
        # list of information types are all registers of things.
        records = records_from_cells(
            cells_from_frivillig(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=FRIVILLIG_ID_FIELDS,
            label_fields=FRIVILLIG_LABEL_FIELDS,
            prefix="frivillig",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
    """Fetch Kartverket national storm-surge consequence cells.

    Measures are the printed integer keys (offentlige_bygg, areal_total, …).
    Dimensions are printed scenario ``code`` and ``year``. alle_kommuner.json
    is 232 municipalities and is refused, not stored. More than
    STORMFLO_MAX_CELLS is refused, not truncated.
    """

    access_path = dataset.get("access_path") or ""
    table_id = stormflo_table_id(access_path)
    if not is_stormflo_national_url(access_path):
        raise ValueError(
            "Kartverket Stormflo alle_kommuner dump is not a bounded "
            "observation fetch; use national.json"
        )
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
        if len(cells) > STORMFLO_MAX_CELLS:
            raise SelectionTooLarge(
                table_id,
                len(cells),
                STORMFLO_MAX_CELLS,
                [
                    {
                        "code": "national.json",
                        "text": "national storm-surge cells",
                        "selected": len(cells),
                        "available": STORMFLO_MAX_CELLS,
                    }
                ],
            )
        counts.listed = len(cells)
        retrieved_at = utc_now()
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=retrieved_at,
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} national stormflo cell(s); measures are "
                    "printed integer keys"
                ),
            },
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
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch one printed fish code's conversion factor.

    Measure is the printed key ``factor``. The unfiltered search is the
    full catalog and is refused. More than OMREGNING_MAX_CELLS is refused,
    not truncated. Unknown fish codes error after the publisher returns
    no row; no fish code is invented.
    """

    access_path = dataset.get("access_path") or ""
    table_id = omregning_table_id(access_path)
    if not is_omregning_search_url(access_path):
        raise ValueError(
            "Omregningsfaktorer OpenAPI/codes paths are not a conversion-factor "
            "observation fetch; use conversionfactors/search with select fish"
        )
    fish = selected_fish(select)
    request_url = omregning_request_url(access_path, fish)
    client = http or HttpClient(timeout=60.0, max_retries=4)
    started = utc_now()
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
        registry.set_fetch_request(
            run_id,
            request_url=request_url,
            request_body={"method": "GET", "select": select},
        )
        if isinstance(got.body, list) and not got.body:
            raise ValueError(
                f"conversion-factor search has no row matching fish={fish!r}; "
                "fish must be a printed code"
            )
        cells = cells_from_omregning(got.body)
        if len(cells) > OMREGNING_MAX_CELLS:
            raise SelectionTooLarge(
                table_id,
                len(cells),
                OMREGNING_MAX_CELLS,
                [
                    {
                        "code": "fish",
                        "text": "conversion-factor cells",
                        "selected": len(cells),
                        "available": OMREGNING_MAX_CELLS,
                    }
                ],
            )
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
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} conversion-factor cell(s); measure is "
                    "printed factor"
                ),
            },
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
        request_url=request_url,
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
        # An environmental survey report is a document about a site, addressed by
        # its report id.
        records = records_from_cells(
            cells_from_envreportreg(got.body),
            dataset_id=dataset["id"],
            table_id=table_id,
            id_fields=ENVREPORT_ID_FIELDS,
            label_fields=(),
            prefix="envreportreg",
        )
        counts.listed = len(records)
        sample = _store_records(
            registry,
            dataset,
            run_id,
            records=records,
            retrieved_at=utc_now(),
            request_url=access_path,
            http_status=http_status,
            counts=counts,
            series=f"fetch:{table_id}",
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
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch session committees as lookup entities, not name observations.

    Default is the complete published list for the session (18 in 2025-2026).
    ``select={"id": ["ARBSOS"]}`` returns that one committee. An unknown id
    is an error, not an empty success.
    """

    if dataset.get("source_id") != "stkomiteer":
        return _fetch_stortinget(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = stkomiteer_table_id(access_path)
    wanted = stkomiteer_selected_ids(select)
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        committees = stkomiteer_from_payload(got.body)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in committees}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"komite id {missing} not in komiteer {table_id}; "
                    "the session list does not print that id"
                )
            committees = [by_id[code] for code in wanted]
        retrieved_at = utc_now()
        for entity in committees:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": "stkomiteer:komiteer",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": STKOMITEER_SCHEME,
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                        "attributes": {
                            key: entity["attributes"][key]
                            for key in ("id", "navn")
                            if key in entity["attributes"]
                        },
                    }
                )
        if not committees:
            raise ValueError(
                f"komiteer returned no committees for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_stkomiteer(committees)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": STKOMITEER_SCHEME,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} committee lookup record(s) from session {table_id}; "
                    "names are labels, not observation values"
                ),
            },
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
        observation_ids=touched,
    )


def _fetch_stperioder(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch period representatives as person entities, not name observations.

    Default is a page of ten. ``select={"id": ["MARNIL"]}`` returns that one
    member. ``antall`` raises the page size up to a hard cap. An unknown id
    is an error. A period holds ~169 members; they are not all ingested.
    """

    if dataset.get("source_id") != "stperioder":
        return _fetch_stortinget(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = stperioder_table_id(access_path)
    wanted, limit = stperioder_selected_member(select)
    if wanted is None and limit > STPERIODER_MAX_LIMIT:
        raise SelectionTooLarge(
            table_id,
            limit,
            STPERIODER_MAX_LIMIT,
            [
                {
                    "code": "antall",
                    "text": "members per request",
                    "selected": limit,
                    "available": STPERIODER_MAX_LIMIT,
                }
            ],
        )
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        members = stperioder_from_payload(got.body)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in members}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"representant id {missing} not in representanter {table_id}; "
                    "the period list does not print that id"
                )
            members = [by_id[code] for code in wanted]
        else:
            members = members[:limit]
        retrieved_at = utc_now()
        for entity in members:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": "stperioder:representanter",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": STREPRESENT_SCHEME,
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                        "attributes": {
                            key: entity["attributes"][key]
                            for key in ("parti.id", "parti.navn", "fylke.id", "fylke.navn")
                            if key in entity["attributes"]
                        },
                    }
                )
        if not members:
            raise ValueError(
                f"representanter returned no members for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_stperioder(members)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_ENTITIES,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": STREPRESENT_SCHEME,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} period member(s) from {table_id}; "
                    "names are labels, not observation values"
                ),
            },
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
        observation_ids=touched,
    )


def _fetch_stsaker(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch session cases as documents, not title observations.

    Default is a page of ten. ``select={"id": ["200391"]}`` returns that one
    case. ``antall`` raises the page size up to a hard cap. An unknown id is
    an error. The 665 cases in 2025-2026 are not all ingested.
    """

    if dataset.get("source_id") != "stsaker":
        return _fetch_stortinget(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = stsaker_table_id(access_path)
    wanted, limit = stsaker_selected_sak(select)
    if wanted is None and limit > STSAKER_MAX_LIMIT:
        raise SelectionTooLarge(
            table_id,
            limit,
            STSAKER_MAX_LIMIT,
            [
                {
                    "code": "antall",
                    "text": "cases per request",
                    "selected": limit,
                    "available": STSAKER_MAX_LIMIT,
                }
            ],
        )
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        documents = stsaker_documents_from_payload(got.body)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in documents}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"sak id {missing} not in saker {table_id}; "
                    "the session list does not print that id"
                )
            documents = [by_id[code] for code in wanted]
        else:
            documents = documents[:limit]
        retrieved_at = utc_now()
        for doc in documents:
            record_id = f"document:{dataset['id']}:{doc['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "document",
                    "series": "stsaker:saker",
                    "subject_scheme": doc["subject_scheme"],
                    "subject_code": doc["subject_code"],
                    "subject_label": doc["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": doc["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "document",
                        "subject_scheme": STSAKER_SCHEME,
                        "subject_code": doc["subject_code"],
                        "subject_label": doc["subject_label"],
                        "attributes": {
                            key: doc["attributes"][key]
                            for key in ("id", "korttittel", "henvisning", "status")
                            if key in doc["attributes"]
                        },
                    }
                )
        if not documents:
            raise ValueError(
                f"saker returned no cases for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_stsaker(documents)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_DOCUMENTS,
                "record_kind": "document",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": STSAKER_SCHEME,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} case document(s) from session {table_id}; "
                    "titles are labels, not observation values"
                ),
            },
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
        observation_ids=touched,
    )


def _fetch_stsporre(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch session questions as documents, not title observations.

    Default is a page of ten. ``select={"id": ["124284"]}`` returns that one
    question. ``antall`` raises the page size up to a hard cap. An unknown
    id is an error, not an empty success. The API has no per-question URL;
    the session collection is fetched and filtered.
    """

    if dataset.get("source_id") != "stsporre":
        return _fetch_stortinget(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = stsporre_table_id(access_path)
    wanted, limit = stsporre_selected_question(select)
    if wanted is None and limit > STSPORRE_MAX_LIMIT:
        raise SelectionTooLarge(
            table_id,
            limit,
            STSPORRE_MAX_LIMIT,
            [
                {
                    "code": "antall",
                    "text": "questions per request",
                    "selected": limit,
                    "available": STSPORRE_MAX_LIMIT,
                }
            ],
        )
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        documents = stsporre_documents_from_payload(got.body)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in documents}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"question id {missing} not in sporretimesporsmal {table_id}; "
                    "the session list does not print that id"
                )
            documents = [by_id[code] for code in wanted]
        else:
            documents = documents[:limit]
        retrieved_at = utc_now()
        for doc in documents:
            record_id = f"document:{dataset['id']}:{doc['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "document",
                    "series": "stsporre:sporretimesporsmal",
                    "subject_scheme": doc["subject_scheme"],
                    "subject_code": doc["subject_code"],
                    "subject_label": doc["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": doc["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "document",
                        "subject_scheme": STSPORRE_SCHEME,
                        "subject_code": doc["subject_code"],
                        "subject_label": doc["subject_label"],
                        "attributes": {
                            key: doc["attributes"][key]
                            for key in (
                                "id",
                                "sesjon_id",
                                "sporsmal_nummer",
                                "sporsmal_fra.id",
                                "sporsmal_til_minister_tittel",
                            )
                            if key in doc["attributes"]
                        },
                    }
                )
        if not documents:
            raise ValueError(
                f"sporretimesporsmal returned no questions for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_stsporre(documents)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_DOCUMENTS,
                "record_kind": "document",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": STSPORRE_SCHEME,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} question document(s) from session {table_id}; "
                    "titles are labels, not observation values"
                ),
            },
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
        observation_ids=touched,
    )


def _fetch_stpartier(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch session parties as lookup entities, not name observations.

    Default is the complete published list for the session (nine parties in
    2025-2026). ``select={"id": ["FrP"]}`` returns that one party. An unknown
    id is an error, not an empty success.
    """

    if dataset.get("source_id") != "stpartier":
        return _fetch_stortinget(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = stpartier_table_id(access_path)
    wanted = stpartier_selected_ids(select)
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        parties = stpartier_from_payload(got.body)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in parties}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"parti id {missing} not in partier {table_id}; "
                    "the session list does not print that id"
                )
            parties = [by_id[code] for code in wanted]
        retrieved_at = utc_now()
        for entity in parties:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": "stpartier:partier",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": STPARTIER_SCHEME,
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                        "attributes": {
                            key: entity["attributes"][key]
                            for key in ("id", "navn", "representert_parti")
                            if key in entity["attributes"]
                        },
                    }
                )
        if not parties:
            raise ValueError(
                f"partier returned no parties for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_stpartier(parties)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": STPARTIER_SCHEME,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} party lookup entit(y/ies) from session {table_id}; "
                    "names are labels, not observation values"
                ),
            },
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
        observation_ids=touched,
    )


def _fetch_stskrift(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch session written questions as documents, not title observations.

    Default is a page of ten. ``select={"id": ["127161"]}`` returns that one
    question. ``antall`` raises the page size up to a hard cap. An unknown
    id is an error. Session 2025-2026 has thousands of written questions;
    they are not all ingested. The API has no per-question URL.
    """

    if dataset.get("source_id") != "stskrift":
        return _fetch_stortinget(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = stskrift_table_id(access_path)
    wanted, limit = stskrift_selected_question(select)
    if wanted is None and limit > STSKRIFT_MAX_LIMIT:
        raise SelectionTooLarge(
            table_id,
            limit,
            STSKRIFT_MAX_LIMIT,
            [
                {
                    "code": "antall",
                    "text": "questions per request",
                    "selected": limit,
                    "available": STSKRIFT_MAX_LIMIT,
                }
            ],
        )
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        documents = stskrift_documents_from_payload(got.body)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in documents}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"question id {missing} not in skriftligesporsmal {table_id}; "
                    "the session list does not print that id"
                )
            documents = [by_id[code] for code in wanted]
        else:
            documents = documents[:limit]
        retrieved_at = utc_now()
        for doc in documents:
            record_id = f"document:{dataset['id']}:{doc['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "document",
                    "series": "stskrift:skriftligesporsmal",
                    "subject_scheme": doc["subject_scheme"],
                    "subject_code": doc["subject_code"],
                    "subject_label": doc["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": doc["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "document",
                        "subject_scheme": STSKRIFT_SCHEME,
                        "subject_code": doc["subject_code"],
                        "subject_label": doc["subject_label"],
                        "attributes": {
                            key: doc["attributes"][key]
                            for key in (
                                "id",
                                "sesjon_id",
                                "sporsmal_nummer",
                                "sporsmal_fra.id",
                                "sporsmal_til_minister_tittel",
                            )
                            if key in doc["attributes"]
                        },
                    }
                )
        if not documents:
            raise ValueError(
                f"skriftligesporsmal returned no questions for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_stskrift(documents)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_DOCUMENTS,
                "record_kind": "document",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": STSKRIFT_SCHEME,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} written-question document(s) from session {table_id}; "
                    "titles are labels, not observation values"
                ),
            },
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
        observation_ids=touched,
    )


def _fetch_stmoter(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch session meetings as documents, not referat_id observations.

    Default is a page of ten. ``select={"id": ["11513"]}`` returns that one
    meeting. ``antall`` raises the page size up to a hard cap. The 155
    meetings in 2025-2026 are not all ingested.
    """

    if dataset.get("source_id") != "stmoter":
        return _fetch_stortinget(registry, dataset, http=http)
    access_path = dataset.get("access_path") or ""
    table_id = stmoter_table_id(access_path)
    wanted, limit = stmoter_selected_mote(select)
    if wanted is None and limit > STMOTER_MAX_LIMIT:
        raise SelectionTooLarge(
            table_id,
            limit,
            STMOTER_MAX_LIMIT,
            [
                {
                    "code": "antall",
                    "text": "meetings per request",
                    "selected": limit,
                    "available": STMOTER_MAX_LIMIT,
                }
            ],
        )
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        documents = stmoter_documents_from_payload(got.body)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in documents}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"møte id {missing} not in moter {table_id}; "
                    "the session list does not print that id"
                )
            documents = [by_id[code] for code in wanted]
        else:
            documents = documents[:limit]
        retrieved_at = utc_now()
        for doc in documents:
            record_id = f"document:{dataset['id']}:{doc['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "document",
                    "series": "stmoter:moter",
                    "subject_scheme": doc["subject_scheme"],
                    "subject_code": doc["subject_code"],
                    "subject_label": doc["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": doc["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "document",
                        "subject_scheme": STMOTER_SCHEME,
                        "subject_code": doc["subject_code"],
                        "subject_label": doc["subject_label"],
                        "attributes": {
                            key: doc["attributes"][key]
                            for key in ("id", "referat_id", "merknad", "dagsorden_nummer")
                            if key in doc["attributes"]
                        },
                    }
                )
        if not documents:
            raise ValueError(
                f"moter returned no meetings for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_stmoter(documents)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_DOCUMENTS,
                "record_kind": "document",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": STMOTER_SCHEME,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} meeting document(s) from session {table_id}; "
                    "referat_id is a label, not an observation value"
                ),
            },
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
        observation_ids=touched,
    )


def _fetch_dagensrepresentanter(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch current Stortinget members as person entities.

    Default is the complete published roster. ``select={"id": ["MARNIL"]}``
    returns that one member. An unknown id is an error, not an empty success.
    """

    access_path = dataset.get("access_path") or ""
    table_id = representant_table_id(access_path)
    wanted = representant_selected_ids(select)
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        members = representanter_from_payload(got.body)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in members}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"representant id {missing} not in dagensrepresentanter; "
                    "the roster does not list that member"
                )
            members = [by_id[code] for code in wanted]
        retrieved_at = utc_now()
        for entity in members:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": "stortinget:dagensrepresentanter",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": STREPRESENT_SCHEME,
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                        "attributes": {
                            key: entity["attributes"][key]
                            for key in ("parti.id", "parti.navn", "fylke.id", "fylke.navn")
                            if key in entity["attributes"]
                        },
                    }
                )
        fields, keys = shape_from_representanter(members)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_ENTITIES,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": STREPRESENT_SCHEME,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": f"{counts.listed} current Stortinget member(s)",
            },
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
        observation_ids=touched,
    )


def _fetch_stortingsperioder(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch parliamentary periods as lookup entities, not id observations.

    Default is the complete published list (21 periods). ``select={"id":
    ["2025-2029"]}`` returns that one period. An unknown id is an error.
    """

    access_path = dataset.get("access_path") or ""
    table_id = stortinget_table_id(access_path)
    wanted = selected_periode_ids(select)
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        periods = periods_from_payload(got.body)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in periods}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"periode id {missing} not in stortingsperioder; "
                    "the catalog does not print that id"
                )
            periods = [by_id[code] for code in wanted]
        retrieved_at = utc_now()
        for entity in periods:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": "stortinget:stortingsperioder",
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": PERIODER_SCHEME,
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                        "attributes": {
                            key: entity["attributes"][key]
                            for key in ("id", "fra", "til")
                            if key in entity["attributes"]
                        },
                    }
                )
        if not periods:
            raise ValueError(
                f"stortingsperioder returned no periods for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_perioder(periods)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": PERIODER_SCHEME,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} parliamentary-period lookup entit(y/ies); "
                    "ids are labels, not observation values"
                ),
            },
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
        observation_ids=touched,
    )


def _fetch_stortinget_lookup(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch a remaining untemplated Stortinget catalog as lookup entities."""

    access_path = dataset.get("access_path") or ""
    spec = lookup_catalog(access_path)
    table_id = stortinget_table_id(access_path)
    wanted = selected_lookup_ids(select)
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
    touched: list[str] = []
    try:
        got = client.get_json_response(access_path)
        http_status = got.status
        registry.set_fetch_request(
            run_id, request_url=access_path, request_body={"method": "GET", "select": select}
        )
        members = lookups_from_payload(got.body, spec)
        if wanted is not None:
            by_id = {item["subject_code"]: item for item in members}
            missing = [code for code in wanted if code not in by_id]
            if missing:
                raise ValueError(
                    f"id {missing} not in {spec['series']}; "
                    "the catalog does not print that id"
                )
            members = [by_id[code] for code in wanted]
        retrieved_at = utc_now()
        for entity in members:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": spec["series"],
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": entity["subject_scheme"],
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                        "attributes": {
                            key: entity["attributes"][key]
                            for key in ("id", "navn")
                            if key in entity["attributes"]
                        },
                    }
                )
        if not members:
            raise ValueError(
                f"{spec['series']} returned no members for {access_path}; nothing was stored"
            )
        fields, keys = shape_from_lookups(members, spec)
        registry.set_resource_shape(dataset["id"], fields, keys=keys)
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "entity",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": spec["scheme"],
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} lookup entit(y/ies) from {spec['series']}; "
                    "names are labels, not observation values"
                ),
            },
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
        observation_ids=touched,
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
    """Fetch printed AIS ship counts by type, or printed area catalogs.

    Measure is the printed key ``number_of_ships``. Counties and
    forvaltningsplan areas are lookup entities. Location dumps and
    realtime GeoJSON are refused. More than KYSTVERKET_MAX_CELLS is
    refused, not truncated.
    """

    access_path = dataset.get("access_path") or ""
    table_id = kystverket_table_id(access_path)
    if is_kystverket_counties_url(access_path):
        return _fetch_kystverket_lookup(
            registry,
            dataset,
            http=http,
            members_fn=lookups_from_kystverket_counties,
            scheme=COUNTY_SCHEME,
            series="kystverket:counties",
            notes_kind="county",
        )
    if is_kystverket_fvpomr_url(access_path):
        return _fetch_kystverket_lookup(
            registry,
            dataset,
            http=http,
            members_fn=lookups_from_kystverket_fvpomr,
            scheme=AREA_SCHEME,
            series="kystverket:fvpomr",
            notes_kind="forvaltningsplan area",
        )
    if not is_kystverket_vessels_by_type_url(access_path):
        raise ValueError(
            "Kystdatahuset location and GeoJSON catalogs are not a bounded "
            "observation fetch; use vessels-by-type, location/counties, or "
            "maps/fvpomr/list"
        )
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
        cells = cells_from_kystverket_vessels(got.body)
        if len(cells) > KYSTVERKET_MAX_CELLS:
            raise SelectionTooLarge(
                table_id,
                len(cells),
                KYSTVERKET_MAX_CELLS,
                [
                    {
                        "code": "vessels-by-type",
                        "text": "AIS ship-type cells",
                        "selected": len(cells),
                        "available": KYSTVERKET_MAX_CELLS,
                    }
                ],
            )
        counts.listed = len(cells)
        retrieved_at = utc_now()
        sample = _store_cells(
            registry,
            dataset,
            run_id,
            table_id=table_id,
            cells=cells,
            retrieved_at=retrieved_at,
            request_url=access_path,
            http_status=http_status,
            counts=counts,
        )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_OBSERVATIONS,
                "record_kind": "observation",
                "endpoint": access_path,
                "request_method": "GET",
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} AIS ship-type cell(s); measure is printed "
                    "number_of_ships"
                ),
            },
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


def _fetch_kystverket_lookup(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    members_fn,
    scheme: str,
    series: str,
    notes_kind: str,
) -> FetchResult:
    """Fetch a printed Kystdatahuset catalog as lookup entities."""

    access_path = dataset.get("access_path") or ""
    table_id = kystverket_table_id(access_path)
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
        members = members_fn(got.body)
        retrieved_at = utc_now()
        for entity in members:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": series,
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": entity["subject_scheme"],
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                    }
                )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "lookup",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": scheme,
                "subject_count": counts.listed,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} printed {notes_kind} lookup entit"
                    f"{'y' if counts.listed == 1 else 'ies'} under {scheme}"
                ),
            },
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
    """Fetch printed Vannmiljø catalogs as lookup entities.

    Units, media, and activities are keyed by printed ``UnitID``,
    ``MediumID``, and ``ActivityID``. Other leftover name lists copy
    ``Name`` as an observation measure and are refused.
    """

    access_path = dataset.get("access_path") or ""
    if is_miljodir_unit_list_url(access_path):
        return _fetch_miljodir_lookup(
            registry,
            dataset,
            http=http,
            members_fn=lookups_from_miljodir_units,
            scheme=UNIT_SCHEME,
            series="miljodir:units",
            notes_kind="unit",
        )
    if is_miljodir_medium_list_url(access_path):
        return _fetch_miljodir_lookup(
            registry,
            dataset,
            http=http,
            members_fn=lookups_from_miljodir_mediums,
            scheme=MEDIUM_SCHEME,
            series="miljodir:mediums",
            notes_kind="medium",
        )
    if is_miljodir_activity_list_url(access_path):
        return _fetch_miljodir_lookup(
            registry,
            dataset,
            http=http,
            members_fn=lookups_from_miljodir_activities,
            scheme=ACTIVITY_SCHEME,
            series="miljodir:activities",
            notes_kind="activity",
        )
    raise ValueError(
        "Vannmiljø leftover name catalog is not a bounded lookup fetch; "
        "use GetUnitList, GetMediumList, or GetActivityList"
    )


def _fetch_miljodir_lookup(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    members_fn,
    scheme: str,
    series: str,
    notes_kind: str,
) -> FetchResult:
    """Fetch a printed Vannmiljø catalog as lookup entities."""

    access_path = dataset.get("access_path") or ""
    table_id = miljodir_table_id(access_path)
    client = http or HttpClient(timeout=60.0, max_retries=4)
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
        members = members_fn(got.body)
        retrieved_at = utc_now()
        for entity in members:
            record_id = f"entity:{dataset['id']}:{entity['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "entity",
                    "series": series,
                    "subject_scheme": entity["subject_scheme"],
                    "subject_code": entity["subject_code"],
                    "subject_label": entity["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": entity["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": access_path,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "entity",
                        "subject_scheme": entity["subject_scheme"],
                        "subject_code": entity["subject_code"],
                        "subject_label": entity["subject_label"],
                    }
                )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_LOOKUP,
                "record_kind": "lookup",
                "endpoint": access_path,
                "request_method": "GET",
                "subject_scheme": scheme,
                "subject_count": counts.listed,
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": (
                    f"{counts.listed} printed {notes_kind} lookup entit"
                    f"{'y' if counts.listed == 1 else 'ies'} under {scheme}"
                ),
            },
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


# How many cells one request may store. Connectors carry their own caps
# (MAGASIN_MAX_CELLS and the rest) for the shapes whose size is known in
# advance; this is the caller's bound for any fetch, whatever the connector.
#
# It exists because verifying a capability is cheap to ask for and expensive to
# store: probing 122 datasets on 2026-10-03 with only a year bound wrote 1.73
# million cells and took the registry from 406 MB to 1.9 GB, one table
# contributing 792,990 of them. The request looks small and the answer is not.
_CELL_BUDGET: ContextVar[int | None] = ContextVar("pda_cell_budget", default=None)


@contextmanager
def cell_budget(max_cells: int | None):
    """Limit how many cells the fetches inside this block may store."""

    token = _CELL_BUDGET.set(max_cells)
    try:
        yield
    finally:
        _CELL_BUDGET.reset(token)


def _check_cell_budget(dataset_id: str, table_id: str, count: int) -> None:
    """Refuse an oversized response rather than storing part of it.

    Storing the first N cells of a table and reporting success would make a
    partial answer look complete, which is worse than no answer. The caller is
    told what it would take and can narrow the selection instead.
    """

    cap = _CELL_BUDGET.get()
    if cap is None or count <= cap:
        return
    raise ValueError(
        f"{dataset_id} table {table_id} returned {count} cells, over the "
        f"{cap}-cell budget for this request; nothing was stored. Narrow the "
        f"selection (one year, one region, one measure) or raise the budget."
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
    series: str | None = None,
    touched: list[str] | None = None,
) -> list[dict[str, Any]]:
    # A raw table fetch and a joined subset of the same table both land under
    # one dataset_id with different dimension names.  Tagging the projection
    # keeps them separable instead of blending into one unusable pool.
    series = series or f"fetch:{table_id}"
    _check_cell_budget(dataset["id"], table_id, len(cells))
    sample: list[dict[str, Any]] = []
    with registry.deferred_commit():
        return _store_each(
            registry, dataset, run_id, table_id, cells, retrieved_at,
            request_url, http_status, counts, series, sample, touched,
        )


def _store_each(
    registry: Registry,
    dataset: dict[str, Any],
    run_id: int,
    table_id: str,
    cells: list[tuple[str, Any, dict[str, str]]],
    retrieved_at: str,
    request_url: str,
    http_status: int,
    counts: HarvestCounts,
    series: str,
    sample: list[dict[str, Any]],
    touched: list[str] | None,
) -> list[dict[str, Any]]:
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
                "series": series,
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
        if touched is not None:
            touched.append(observation.identity_key())
    return sample


def _store_records(
    registry: Registry,
    dataset: dict[str, Any],
    run_id: int,
    *,
    records: list[dict[str, Any]],
    retrieved_at: str,
    request_url: str,
    http_status: int,
    counts: HarvestCounts,
    series: str | None = None,
) -> list[dict[str, Any]]:
    """Store rows that are things rather than measurements.

    The counterpart of `_store_cells`, for a connector whose response is a list
    of named things -- a code list, a register entry, a stop place. Routing them
    here rather than into `observations` is what keeps a count over
    `observations` a count of measurements. Each record carries its own `id`,
    `kind` and subject; the provenance is filled in from the dataset, which is
    identical across kinds and is the trust boundary.
    """

    _check_cell_budget(dataset["id"], series or "records", len(records))
    # Two members that converge on one id do not become one row by agreement;
    # one silently overwrites the other and the count still reads as a clean
    # store. 157 bathymetry contours became 1 record this way.
    #
    # A publisher repeating itself is a different matter. The 3000m contour
    # collection prints 671 features of which 650 are distinct: 21 are
    # byte-identical in properties and geometry both, and two members that
    # agree on everything published are one member as far as anything here can
    # tell. Those are collapsed. An id shared by members that differ is the
    # dangerous case -- the identifier is not discriminating -- and is refused.
    seen: dict[str, dict[str, Any]] = {}
    for record in records:
        first = seen.get(record["id"])
        if first is None:
            seen[record["id"]] = record
        elif first != record:
            raise ValueError(
                f"{dataset['id']}: two different members share the id {record['id']!r}; "
                f"the identifier chosen for this source does not tell them apart"
            )
    records = list(seen.values())
    sample: list[dict[str, Any]] = []
    with registry.deferred_commit():
        for record in records:
            action = registry.upsert_record(
                {
                    "series": series,
                    "period": None,
                    "measure": None,
                    "value": None,
                    **record,
                    "dataset_id": dataset["id"],
                    "retrieved_at": retrieved_at,
                    "request_url": request_url,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
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
                sample.append(
                    {
                        "kind": record.get("kind"),
                        "subject_code": record.get("subject_code"),
                        "subject_label": record.get("subject_label"),
                        "attributes": record.get("attributes") or {},
                    }
                )
    return sample


class ServiceCatalogue(ValueError):
    """The response described the service instead of returning data.

    An ArcGIS MapServer root prints its `layers` array: id, parent, visibility,
    scale range, geometry type. That is the service's table of contents, and
    storing it as observations made `defaultVisibility` and `parentLayerId`
    into published figures and marked the dataset verified on the strength of
    them. 99 such rows were stored across Fiskeridirektoratet's and
    Norsk Polarinstitutt's map services.

    Raised rather than stored, because a fetch that came back with a menu has
    not reached the data, and anything else leaves a dataset looking fetchable
    when the data needs a per-layer query it has never made.
    """


# What a service prints when it is describing itself. `layers` and `services`
# are ArcGIS; `collections` is OGC API Features; `features` is how met.no lists
# the products it serves, which is the same kind of list under another name.
# `features` is deliberately absent from the GeoJSON sense -- a FeatureCollection
# of real features is read by connectors that never call this.
_CATALOGUE_KEYS = ("layers", "services", "collections")

# A single OGC collection's own page: what the collection holds and how much of
# it, with no item in sight.
_COLLECTION_DESCRIPTION_KEYS = frozenset({"itemType", "storageCrs", "extent", "crs"})


def _refuse_service_catalogue(
    payload: Any, *, dataset_id: str, url: str, what: str = "layer"
) -> None:
    """Stop a service's description of itself from being stored as data."""

    if not isinstance(payload, dict):
        return
    for key in _CATALOGUE_KEYS:
        listed = payload.get(key)
        if isinstance(listed, list) and listed:
            raise ServiceCatalogue(
                f"{dataset_id}: {url} printed {len(listed)} {key} -- the service's own "
                f"table of contents, not data. Each {what} has to be requested in its "
                f"own right; nothing was stored."
            )
    # One level below a MapServer root: a single layer's descriptor. `fields`
    # with no `features` is the service listing its own columns -- OBJECTID,
    # alias, domain, editable, nullable -- which a probe stored as 840 rows
    # across 39 Sokkeldirektoratet layers and recorded as verified entities.
    # A query response carries `fields` and `features` together, so requiring
    # the absence of `features` leaves real data alone.
    if (
        isinstance(payload.get("fields"), list)
        and payload["fields"]
        and "features" not in payload
        and {"capabilities", "drawingInfo", "geometryType", "type"} & set(payload)
    ):
        raise ServiceCatalogue(
            f"{dataset_id}: {url} printed one layer's field definitions -- its own "
            f"columns, not rows. The data is at <layer>/query?where=1=1&outFields=*; "
            f"nothing was stored."
        )
    if "features" not in payload and _COLLECTION_DESCRIPTION_KEYS & set(payload):
        raise ServiceCatalogue(
            f"{dataset_id}: {url} printed what the collection holds -- its item type, "
            f"count and coordinate system -- and no item. The items are at "
            f"{url.rstrip('/')}/items; nothing was stored."
        )


class SelectionTooLarge(ValueError):
    """A query would ask for more cells than the source will return.

    Carries the per-dimension sizes so a caller can narrow instead of guessing.
    """

    def __init__(self, table_id: str, cells: int, limit: int, dimensions: list[dict[str, Any]]) -> None:
        self.table_id, self.cells, self.limit, self.dimensions = table_id, cells, limit, dimensions
        super().__init__(
            f"selection is {cells:,} cells, over the {limit:,} limit for table {table_id}. "
            f"Narrow it with select={{dimension: [values]}}. Dimensions: "
            + "; ".join(
                f"{d['code']} ({d['text']}) {d['selected']} of {d['available']}"
                for d in dimensions
            )
        )


# SSB PxWeb refuses a query above roughly this many cells. Checking before the
# POST turns an opaque HTTP 403 into a message naming what to narrow.
PXWEB_CELL_LIMIT = 800_000


def _pxweb_selection(
    meta: dict[str, Any],
    time_code: str,
    time_values: list[str],
    select: dict[str, list[str]] | None,
) -> list[dict[str, Any]]:
    """Resolve, per dimension, which stored values this query will ask for.

    Selected values must exist in the table metadata: an unknown value is an
    error, never silently dropped, because dropping it would quietly widen the
    query to every value of that dimension.
    """

    select = {str(k): v for k, v in (select or {}).items()}
    known = {str(v.get("code")) for v in meta.get("variables") or []}
    unknown = sorted(key for key in select if key not in known)
    if unknown:
        raise ValueError(
            f"select names dimension(s) {unknown} that this table does not have; "
            f"available dimensions are {sorted(known)}"
        )
    resolved: list[dict[str, Any]] = []
    for variable in meta.get("variables") or []:
        code = str(variable["code"])
        available = [str(item) for item in (variable.get("values") or [])]
        if code in select:
            wanted = select[code]
            wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
            missing = [item for item in wanted if item not in available]
            if missing:
                raise ValueError(
                    f"select[{code}] names value(s) {missing} that are not stored; "
                    f"stored values are {available[:20]}"
                    + (" (truncated)" if len(available) > 20 else "")
                )
            chosen = wanted
        elif code == time_code:
            chosen = time_values
        else:
            chosen = available
        resolved.append(
            {
                "code": code,
                "text": str(variable.get("text") or code),
                "values": chosen,
                "selected": len(chosen),
                "available": len(available),
                "explicit": code in select or code == time_code,
            }
        )
    return resolved


def _pxweb_query(
    meta: dict[str, Any],
    time_code: str,
    time_values: list[str],
    *,
    select: dict[str, list[str]] | None = None,
    table_id: str = "",
    cell_limit: int = PXWEB_CELL_LIMIT,
) -> dict[str, Any]:
    resolved = _pxweb_selection(meta, time_code, time_values, select)
    cells = 1
    for item in resolved:
        cells *= max(1, item["selected"])
    if cells > cell_limit:
        raise SelectionTooLarge(table_id or "?", cells, cell_limit, resolved)
    query = [
        {"code": item["code"], "selection": {"filter": "item", "values": item["values"]}}
        for item in resolved
    ]
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


# Capability kinds returned by ``classify_access_path``.
CAPABILITY_OBSERVATIONS = "observations"
CAPABILITY_ENTITIES = "entities"
CAPABILITY_FEATURES = "features"
CAPABILITY_DOCUMENTS = "documents"
CAPABILITY_LOOKUP = "lookup"
CAPABILITY_UNVERIFIED = "unverified"
# The publisher has taken the resource down. Separate from `unverified`, which
# means nobody has checked: 30 SSB tables answer the v0 API with HTTP 400
# "Parameter error", which reads as a bad query and is what made this look like
# a bug in the request for weeks. The v2 API says what is actually true --
# `{"title": "Non-existent table", "status": 404}` -- and a resource that is
# gone should not be retried, nor ranked as though a fetch might reach it.
CAPABILITY_WITHDRAWN = "withdrawn"
# The endpoint answers and holds nothing. Ten NVDB road object types are in
# this state -- `Vinterberedskap`, `Vegreferanse`, several marked "(test)" --
# and it is not the same as withdrawn: the type exists, the request is
# correct, and it may hold objects next month. Nothing can be answered from it
# today, so it is not retrievable, and the date it was probed is recorded so
# the claim stays attached to when it was true.
CAPABILITY_EMPTY = "empty"
# The publisher serves it, but not to us. Eight NVDB types -- the `uoffisiell`
# load-class ones and `Historisk_Bruksklasse` -- answer HTTP 401. The data is
# real and the connector is right; what is missing is authorisation, which is
# a different thing from the resource being broken or gone.
CAPABILITY_RESTRICTED = "restricted"
# The URL is reachable and it is the wrong door. An ArcGIS MapServer root, an
# OGC collections listing and met.no's product list all answer with the
# service describing itself; the data behind them needs a different request
# that no connector makes yet. Distinct from `empty`, which is the right door
# to an empty room, and it doubles as the work queue for making these
# resources genuinely fetchable.
CAPABILITY_CATALOGUE = "catalogue"
CAPABILITY_NONE = "none"

# Capabilities that can return data a question is answered from. Statistics were
# the only kind when the lane split was written, so it tested `== "observations"`
# and every other retrievable kind fell into the lane for records that cannot be
# retrieved at all -- a company endpoint that fetches fine was filed as
# "describes data we cannot retrieve".
#
# `lookup` is deliberately outside this set: a classification supplies join keys,
# never measures, and offering one as an answer is the substitution the readiness
# gate exists to refuse.
RETRIEVABLE_CAPABILITIES = frozenset({
    CAPABILITY_OBSERVATIONS,
    CAPABILITY_ENTITIES,
    CAPABILITY_FEATURES,
    CAPABILITY_DOCUMENTS,
})


def is_retrievable(capability: str | None) -> bool:
    """Whether a capability can return data, whatever shape that data takes."""

    return capability in RETRIEVABLE_CAPABILITIES

_MAP_SERVICE_MARKS = ("/geoserver/", "/ows", "/wms", "/wfs", "service=wms", "service=wfs")
_DOC_MARKS = ("/dokumentasjon/", ".html", "/swagger", "/openapi", "/docs/")


def classify_access_path(access_path: str | None) -> dict[str, Any]:
    """Say what a stored access_path can actually yield, and why.

    ``can_fetch_access_path`` answers only "does some predicate match", which is
    true for a bare hostname, an HTML documentation page, and a map-tile
    endpoint alike. Reporting those as fetchable told the agent it could get
    numbers from things that never return a numeric cell. The kinds are:

    ``observations`` a connector verified to return numeric cells;
    ``entities``     a connector verified to return company/person/thing records;
    ``features``     geospatial features;
    ``documents``    document records;
    ``lookup``       a code list / classification: join keys, not facts;
    ``unverified``   a connector predicate matches but the payload shape has not
                     been confirmed to hold numeric cells. Not a promise;
    ``none``         nothing here can be fetched.
    """

    if not access_path:
        return {"kind": CAPABILITY_NONE, "reason": "no access_path is stored"}
    lowered = access_path.casefold()

    if (
        _is_ssb_table_url(access_path)
        or is_oslo_statbank_url(access_path)
        or is_fdirpx_url(access_path)
    ):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": "PxWeb table endpoint; returns numeric observation cells",
        }
    if is_ldirmelk_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "Landbruksdirektoratet dairy-delivery CSV; national litre totals "
                "or one farm by organisasjonsnummer"
            ),
        }
    if is_elcert_quarter_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "NVE Elsertifikater GetSummaryValuesPerQuarter; printed "
                "IMaalet and IOvergangsordningen cells by Year and Quarter"
            ),
        }
    if is_elcert_summary_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "NVE Elsertifikater GetSummaryValues; printed IMaalet and "
                "IOvergangsordningen cells for one printed Year and Month"
            ),
        }
    if is_statnett_frequency_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "Statnett Frequency Measurements; Hz values timed from "
                "printed StartPointUTC and PeriodTickMs"
            ),
        }
    if is_nve_siste_uke_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "NVE Magasinstatistikk last-week cells; printed fyllingsgrad "
                "and TWh measures by area"
            ),
        }
    if is_nve_omrader_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "NVE Magasinstatistikk HentOmråder; printed area catalog as "
                f"lookup entities under {OMRADE_SCHEME}"
            ),
        }
    if is_baf_fylker_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "Barnehagefakta Fylker; printed county catalog as lookup "
                f"entities under {FYLKE_SCHEME}"
            ),
        }
    if is_nve_minmax_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "NVE Magasinstatistikk MinMaxMedian; printed min/median/max "
                "fyllingsgrad and TWh cells for one printed iso_uke"
            ),
        }
    if is_stormflo_national_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "Kartverket Stormflo national.json; printed building and area "
                "counts by scenario code and year"
            ),
        }
    if is_ssbv2_data_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "SSB PxWebApi 2 json-stat2 data href; printed ContentsCode "
                "cells for the publisher's default slice"
            ),
        }
    if is_omregning_search_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "Fiskeridirektoratet conversion-factor search; printed factor "
                "cells for one printed fish code"
            ),
        }
    if is_utdanning_tidsserie_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "Utdanning.no tidsserie; printed antall_ansatte and "
                "antall_aarsverk for one printed kommune"
            ),
        }
    if is_aqua_overview_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "Akvakulturregisteret licenses-overview; printed capacity "
                "current and accumulated for one printed license-nr"
            ),
        }
    if is_aqua_fish_codes_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "Akvakulturregisteret fish-codes; printed species catalog as "
                f"lookup entities under {FISH_CODE_SCHEME}"
            ),
        }
    if is_aqua_intentions_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "Akvakulturregisteret license-types/intentions; printed "
                f"purpose catalog as lookup entities under {INTENTION_SCHEME}"
            ),
        }
    if is_hoydedata_lookup_url(access_path):
        scheme = (
            DATAKILDE_SCHEME
            if is_hoydedata_datakilder_url(access_path)
            else TERRENG_SCHEME
        )
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                f"Kartverket Høydedata catalog as lookup entities under {scheme}"
            ),
        }
    if is_kystverket_vessels_by_type_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "Kystdatahuset AIS vessels-by-type; printed number_of_ships "
                "cells by ship_type"
            ),
        }
    if is_kystverket_counties_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "Kystdatahuset location/counties; printed county catalog as "
                f"lookup entities under {COUNTY_SCHEME}"
            ),
        }
    if is_kystverket_fvpomr_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "Kystdatahuset maps/fvpomr/list; printed forvaltningsplan "
                f"area catalog as lookup entities under {AREA_SCHEME}"
            ),
        }
    if is_miljodir_unit_list_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "Vannmiljø GetUnitList; printed unit catalog as lookup "
                f"entities under {UNIT_SCHEME}"
            ),
        }
    if is_miljodir_medium_list_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "Vannmiljø GetMediumList; printed medium catalog as lookup "
                f"entities under {MEDIUM_SCHEME}"
            ),
        }
    if is_miljodir_activity_list_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "Vannmiljø GetActivityList; printed activity catalog as "
                f"lookup entities under {ACTIVITY_SCHEME}"
            ),
        }
    if is_miljodir_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "Vannmiljø leftover name catalog; leftover decoder copies "
                "Name. Use GetUnitList, GetMediumList, or GetActivityList"
            ),
        }
    if is_norgesbank_observations_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "Norges Bank SDMX dataflow; printed observation values "
                "bounded by lastNObservations and a series key"
            ),
        }
    if is_mattilsynet_preparat_url(access_path):
        return {
            "kind": CAPABILITY_ENTITIES,
            "reason": (
                "Mattilsynet plantevernmidler collection; products as entities "
                "addressed by printed id, fetched a bounded page at a time"
            ),
        }
    if is_udir_lookup_url(access_path):
        spec = udir_lookup_catalog(access_path)
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                f"Udir NSR {udir_table_id(access_path)}; printed catalog as "
                f"lookup entities under {spec['scheme']}"
            ),
        }
    if is_nbr_lookup_url(access_path):
        spec = nbr_lookup_catalog(access_path)
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                f"NBR {nbr_table_id(access_path)}; printed catalog as "
                f"lookup entities under {spec['scheme']}"
            ),
        }
    if is_nor_lookup_url(access_path):
        spec = nor_lookup_catalog(access_path)
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                f"NOR {nor_table_id(access_path)}; printed catalog as "
                f"lookup entities under {spec['scheme']}"
            ),
        }
    if is_npr_lookup_url(access_path):
        spec = npr_lookup_catalog(access_path)
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                f"NPR {npr_table_id(access_path)}; printed catalog as "
                f"lookup entities under {spec['scheme']}"
            ),
        }
    if is_nfr_lookup_url(access_path):
        spec = nfr_lookup_catalog(access_path)
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                f"NFR {nfr_table_id(access_path)}; printed catalog as "
                f"lookup entities under {spec['scheme']}"
            ),
        }
    if is_nxr_lookup_url(access_path):
        spec = nxr_lookup_catalog(access_path)
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                f"NXR {nxr_table_id(access_path)}; printed catalog as "
                f"lookup entities under {spec['scheme']}"
            ),
        }
    if is_naturvern_url(access_path):
        return {
            "kind": CAPABILITY_FEATURES,
            "reason": (
                "Miljødirektoratet vern ArcGIS layer; protected-area features "
                "addressed by naturvernId, fetched a bounded page at a time"
            ),
        }
    if is_dagensrepresentanter_url(access_path):
        return {
            "kind": CAPABILITY_ENTITIES,
            "reason": (
                "Stortinget dagensrepresentanter; current members as person "
                "entities addressed by printed id"
            ),
        }
    if is_stperioder_url(access_path):
        return {
            "kind": CAPABILITY_ENTITIES,
            "reason": (
                "Stortinget period representanter; historical members as person "
                "entities addressed by printed id, fetched a bounded page at a time"
            ),
        }
    if is_stpartier_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "Stortinget partier; session party list as lookup entities "
                "addressed by printed id"
            ),
        }
    if is_stortingsperioder_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "Stortinget stortingsperioder; parliamentary-period list as "
                "lookup entities addressed by printed id"
            ),
        }
    if is_stortinget_lookup_url(access_path):
        spec = lookup_catalog(access_path)
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                f"Stortinget {spec['series']}; printed catalog as lookup "
                "entities addressed by id"
            ),
        }
    if is_stkomiteer_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": (
                "Stortinget komiteer; session committee list as lookup entities "
                "addressed by printed id"
            ),
        }
    if is_stsporre_url(access_path):
        return {
            "kind": CAPABILITY_DOCUMENTS,
            "reason": (
                "Stortinget sporretimesporsmal; session questions as documents "
                "addressed by printed id, fetched a bounded page at a time"
            ),
        }
    if is_stsaker_url(access_path):
        return {
            "kind": CAPABILITY_DOCUMENTS,
            "reason": (
                "Stortinget saker; session cases as documents addressed by "
                "printed id, fetched a bounded page at a time"
            ),
        }
    if is_stskrift_url(access_path):
        return {
            "kind": CAPABILITY_DOCUMENTS,
            "reason": (
                "Stortinget skriftligesporsmal; session written questions as "
                "documents addressed by printed id, fetched a bounded page at a time"
            ),
        }
    if is_stmoter_url(access_path):
        return {
            "kind": CAPABILITY_DOCUMENTS,
            "reason": (
                "Stortinget moter; session meetings as documents addressed by "
                "printed id, fetched a bounded page at a time"
            ),
        }
    if is_anadrom_url(access_path):
        return {
            "kind": CAPABILITY_FEATURES,
            "reason": (
                "Miljødirektoratet anadrome_laksefisk stretch layer; river "
                "features addressed by vassdragsNR, fetched a bounded page at a time"
            ),
        }
    if is_friluft_url(access_path):
        return {
            "kind": CAPABILITY_FEATURES,
            "reason": (
                "Miljødirektoratet friluftsliv_statlig_sikra layer; recreation-area "
                "features addressed by friluftId, fetched a bounded page at a time"
            ),
        }
    if is_miljogis_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "Miljødirektoratet ArcGIS MapServer catalog; lists layer names, "
                "does not return protected-area or other feature records"
            ),
        }
    if is_fhi_table_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": "FHI Statistikk table endpoint; returns numeric observation cells",
        }
    if is_brenheter_url(access_path):
        return {
            "kind": CAPABILITY_ENTITIES,
            "reason": "Enhetsregisteret enhet endpoint; returns one company entity by orgnr",
        }
    if is_brenheter_collection_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": "Enhetsregisteret enheter collection/lastned; too large and not a single entity",
        }
    if is_nvdb_object_url(access_path):
        return {
            "kind": CAPABILITY_FEATURES,
            "reason": "NVDB vegobjekt endpoint; returns one road feature with geometry and attributes",
        }
    if is_nvdb_collection_url(access_path):
        return {
            "kind": CAPABILITY_FEATURES,
            "reason": (
                "NVDB vegobjekt type endpoint; returns road features with geometry, "
                "fetched a bounded page at a time rather than whole"
            ),
        }
    if is_brunder_url(access_path):
        return {
            "kind": CAPABILITY_ENTITIES,
            "reason": "Enhetsregisteret underenhet endpoint; returns one sub-unit entity by orgnr",
        }
    if is_brunder_collection_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": "Enhetsregisteret underenheter collection/lastned; too large and not a single entity",
        }
    if is_brorgform_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": "Brreg organisation-form item; returns one published code-list concept",
        }
    if is_brkommuner_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": "Brreg municipality item; returns one published code-to-name concept",
        }
    if is_brrolletype_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": "Brreg role-type item; returns one published code-list concept",
        }
    if is_brrollegruppe_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": "Brreg role-group-type item; returns one published code-list concept",
        }
    if is_brrepresent_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": "Brreg representative item; returns one published code-list concept",
        }
    if is_brroller_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "Brreg role discovery collection; duplicates canonical per-code lookup "
                "datasets and does not return company roles"
            ),
        }
    if is_klass_url(access_path):
        return {
            "kind": CAPABILITY_LOOKUP,
            "reason": "SSB Klass classification; code-to-name rows usable as join keys, not measures",
        }
    # A bare host is a landing page, not an endpoint, whatever the predicate says.
    without_scheme = lowered.split("://", 1)[-1]
    if "/" not in without_scheme.rstrip("/"):
        return {
            "kind": CAPABILITY_NONE,
            "reason": "bare hostname with no endpoint path; not a fetchable resource",
        }
    if any(mark in lowered for mark in _DOC_MARKS):
        return {
            "kind": CAPABILITY_NONE,
            "reason": "documentation or API-description page; describes data but returns none",
        }
    if any(mark in lowered for mark in _MAP_SERVICE_MARKS):
        return {
            "kind": CAPABILITY_NONE,
            "reason": "map/tile service (WMS/WFS/OGC); returns imagery or geometry, not numeric cells",
        }
    if is_nve_magasin_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "NVE Magasinstatistikk full weekly dump; last-week cells are "
                "HentOffentligDataSisteUke; extrema are MinMaxMedian with "
                "select iso_uke"
            ),
        }
    if is_stormflo_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "Kartverket Stormflo alle_kommuner dump; national totals are "
                "national.json"
            ),
        }
    if is_ssbv2_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "SSB PxWebApi 2 tables catalog; lists table ids, does not "
                "return json-stat cells"
            ),
        }
    if is_kystverket_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "Kystdatahuset county, location, or GeoJSON catalog; ship "
                "counts are vessels-by-type"
            ),
        }
    if is_utdanning_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "Utdanning.no name catalog or hydra listing; employment "
                "cells are tidsserie with select kommune"
            ),
        }
    if is_elcert_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "NVE Elsertifikater GetApplications plant-name catalog; "
                "numeric cells are GetSummaryValues or GetSummaryValuesPerQuarter"
            ),
        }
    if is_vannkraft_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "NVE Vannkraftdatabase plant-name catalog; leftover decoder "
                "copies Navn. Do not dump 1863 plants"
            ),
        }
    if is_aqua_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "Akvakulturregisteret name catalog; capacity cells are "
                "licenses-overview with select license-nr; species codes "
                "are fish-codes"
            ),
        }
    if is_hoydedata_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "Kartverket Høydedata punkt needs printed coordinates; "
                "do not invent lat/lon. Catalogs are datakilder/terrengtyper"
            ),
        }
    if is_baf_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "Barnehagefakta Location is every kindergarten; county "
                "catalog is Fylker"
            ),
        }
    if is_vindkraft_plants_url(access_path):
        return {
            "kind": CAPABILITY_OBSERVATIONS,
            "reason": (
                "NVE Vindkraftdatabase GetWindPowerPlants; printed "
                "InstallertEffekt_MW and other float cells for one printed "
                "VindkraftAnleggId"
            ),
        }
    if is_vindkraft_url(access_path):
        return {
            "kind": CAPABILITY_NONE,
            "reason": (
                "NVE Vindkraftdatabase plant-name catalog; leftover decoder "
                "copies Navn. Do not dump 65 plants. Numeric cells are "
                "GetWindPowerPlants with select VindkraftAnleggId"
            ),
        }
    if can_fetch_access_path(access_path):
        return {
            "kind": CAPABILITY_UNVERIFIED,
            "reason": "a connector predicate matches, but this payload shape is not confirmed "
                      "to yield numeric cells; inspect the result before relying on it",
        }
    return {"kind": CAPABILITY_NONE, "reason": "no registered connector matches this access_path"}


def _fetch_nvdb(
    registry: Registry,
    dataset: dict[str, Any],
    *,
    http: JsonHttp | None = None,
    select: dict[str, list[str]] | None = None,
) -> FetchResult:
    """Fetch road features from NVDB: one object, or a bounded page of a type.

    A road object is not a measure of anything, so rows land in `records` with
    kind `feature` and subject scheme `NVDB vegobjekt-id`.

    "Fetch this type" cannot mean "fetch all of it" -- type 5 alone holds
    245,616 guardrails -- so a collection request returns a bounded page and
    says so. `select` narrows it: `kommune` and `fylke` take Klass codes, which
    is what makes a road object reachable from a question about a place, and
    `antall` raises the page size up to a hard cap rather than without limit.
    """

    access_path = dataset.get("access_path") or ""
    type_id = nvdb_type_id(access_path)
    single = is_nvdb_object_url(access_path)
    select = {str(key): value for key, value in (select or {}).items()}

    allowed = {"kommune", "fylke", "antall"}
    unknown = sorted(key for key in select if key not in allowed)
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that an NVDB fetch does not filter on; "
            f"accepted: {sorted(allowed)}"
        )

    limit = DEFAULT_OBJECT_LIMIT
    if "antall" in select:
        wanted = select["antall"]
        wanted = [wanted] if isinstance(wanted, str) else list(wanted)
        try:
            limit = int(str(wanted[0]))
        except (ValueError, IndexError) as exc:
            raise ValueError(f"select[antall]={select['antall']!r} is not a number") from exc
        if limit < 1:
            raise ValueError(f"select[antall]={limit} must be at least 1")
        if limit > MAX_OBJECT_LIMIT:
            raise SelectionTooLarge(
                type_id,
                limit,
                MAX_OBJECT_LIMIT,
                [{
                    "code": "antall",
                    "text": "objects per request",
                    "selected": limit,
                    "available": MAX_OBJECT_LIMIT,
                }],
            )

    def _codes(name: str) -> str:
        values = select.get(name)
        if values is None:
            return ""
        values = [values] if isinstance(values, str) else [str(v) for v in values]
        for value in values:
            if not value.isdigit():
                raise ValueError(
                    f"select[{name}]={value!r} is not a numeric Klass code; NVDB filters "
                    "on kommune and fylke numbers, not names"
                )
        return ",".join(values)

    if single:
        request_url = f"{access_path}?inkluder=metadata,egenskaper,lokasjon"
        if select:
            raise ValueError(
                "select does not apply when fetching one object by id; drop it, or "
                f"address the type at {OBJECT_API}/{type_id} to filter"
            )
    else:
        query = [f"antall={limit}", "inkluder=metadata,egenskaper,lokasjon"]
        for name in ("kommune", "fylke"):
            codes = _codes(name)
            if codes:
                query.append(f"{name}={codes}")
        request_url = f"{OBJECT_API}/{type_id}?" + "&".join(query)

    client = http or HttpClient(
        limiter=RateLimiter(NVDB_RPS, 1), timeout=60.0, max_retries=3
    )
    started = utc_now()
    run_id = registry.start_fetch_run(
        dataset_id=dataset["id"],
        table_id=type_id,
        request_url=request_url,
        request_method="GET",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    http_status = 0
    sample: list[dict[str, Any]] = []
    touched: list[str] = []
    try:
        got = client.get_json_response(request_url, headers=dict(NVDB_HEADERS))
        http_status = got.status
        registry.set_fetch_request(run_id, request_url=request_url, request_body={"method": "GET"})
        if http_status == 404:
            raise ValueError(f"NVDB has no object at {request_url}; unsatisfiable request")
        if http_status >= 400:
            raise ValueError(f"NVDB GET returned HTTP {http_status} for {request_url}")

        body = got.body
        objects = [body] if single else [o for o in (body.get("objekter") or []) if isinstance(o, dict)]
        retrieved_at = utc_now()
        type_name = dataset.get("title") or ""
        for payload in objects:
            feature = feature_from_vegobjekt(payload, type_name=type_name)
            record_id = f"feature:{dataset['id']}:{feature['subject_code']}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": dataset["id"],
                    "kind": "feature",
                    "series": f"nvdb:{type_id}",
                    "subject_scheme": feature["subject_scheme"],
                    "subject_code": feature["subject_code"],
                    "subject_label": feature["subject_label"],
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": feature["attributes"],
                    "retrieved_at": retrieved_at,
                    "request_url": request_url,
                    "http_status": http_status,
                    "publisher_name": dataset.get("publisher_name"),
                    "license": dataset.get("license"),
                },
                run_id,
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            touched.append(record_id)
            if len(sample) < 3:
                sample.append(
                    {
                        "kind": "feature",
                        "subject_scheme": NVDB_SCHEME,
                        "subject_code": feature["subject_code"],
                        "subject_label": feature["subject_label"],
                        "attributes": feature["attributes"],
                    }
                )
        if not objects:
            raise ValueError(
                f"NVDB returned no objects for {request_url}; nothing was stored"
            )
        registry.set_capability(
            dataset["id"],
            {
                "capability": CAPABILITY_FEATURES,
                "record_kind": "feature",
                "endpoint": f"{OBJECT_API}/{type_id}",
                "request_method": "GET",
                "subject_scheme": NVDB_SCHEME,
                "subject_template": f"{OBJECT_API}/{type_id}/{{subject}}",
                "subject_count": (registry.get_capability(dataset["id"]) or {}).get("subject_count"),
                "verified_at": retrieved_at,
                "verified_sample_count": counts.listed,
                "notes": f"{counts.listed} object(s) fetched and stored",
            },
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
        table_id=type_id,
        request_url=request_url,
        http_status=http_status,
        counts=counts,
        sample=sample,
        observation_ids=touched,
    )
