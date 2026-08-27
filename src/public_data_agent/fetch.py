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
from public_data_agent.sources.fiskeridir import (
    cells_from_fiskeridir,
    fiskeridir_table_id,
    is_fiskeridir_vessel_url,
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
from public_data_agent.sources.oslo import is_oslo_statbank_url, oslo_table_id
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
    if is_klass_url(access_path):
        return _fetch_klass(registry, dataset, http=http)
    if is_geonorge_rest_url(access_path):
        return _fetch_geonorge_rest(registry, dataset, http=http)
    if is_nve_magasin_url(access_path):
        return _fetch_nve_magasin(registry, dataset, http=http)
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
