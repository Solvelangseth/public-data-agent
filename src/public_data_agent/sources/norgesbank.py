from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "norgesbank"
SOURCE_NAME = "Norges Bank Open Data"
LIST_URL = "https://data.norges-bank.no/api/dataflow?format=sdmx-json"
DATA_PATH_PREFIX = "/api/data/"
FORMAT_QUERY = "format=sdmx-json"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a dataflow on the official Norges Bank SDMX list API, "
    f"capped at {DEFAULT_MAX_ITEMS} dataflows"
)
NORGESBANK_RPS = 2.0
NORGESBANK_BURST = 4
HOST = "data.norges-bank.no"


class NorgesBankSource(SourceBase):
    """Replaceable ingest adapter for Norges Bank open SDMX dataflows.

    Listing copies dataflow ids the official `/api/dataflow` list prints. It
    does not invent ids. `access_path` joins each printed id to the same host
    `/api/data/{id}` path the live data message prints on `meta.links.href`,
    keeping the same `format=sdmx-json` query the list API uses. This first
    slice stays inside that list and caps the walk.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (LIST_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        list_url: str = LIST_URL,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.list_url = list_url
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(NORGESBANK_RPS, NORGESBANK_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_dataflow_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_data_url(ident, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or norgesbank_table_id(ref.source_native_uri or "")
        item = self._catalog_item(ident)
        description = printed_localized(
            item.get("descriptions"),
            item.get("description"),
            None,
        )
        endpoint = printed_data_url(ident, self.list_url)
        payload = {
            "id": ident,
            "uri": endpoint,
            "title": printed_title(item, ident),
            "description": ({"no": description} if description else None),
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.list_url],
            "norgesbank_dataflow": item,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ident,
            source_native_uri=endpoint,
            fetched_from=self.list_url,
            payload=payload,
        )

    def _catalog(self) -> list[dict[str, Any]]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(
                f"Norges Bank dataflow list failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_dataflows(body)
        if not listed:
            raise SourceError("Norges Bank dataflow list printed no dataflows")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_dataflow_id(item) == ident:
                return item
        raise SourceError(f"Norges Bank dataflow list has no printed dataflow {ident}")


def printed_dataflows(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Norges Bank dataflow list is not a JSON object")
    data = body.get("data")
    if not isinstance(data, dict):
        raise SourceError("Norges Bank dataflow list has no printed data object")
    flows = data.get("dataflows")
    if not isinstance(flows, list):
        raise SourceError("Norges Bank dataflow list has no printed dataflows array")
    listed: list[dict[str, Any]] = []
    for item in flows:
        if not isinstance(item, dict):
            continue
        ident = item.get("id")
        if not isinstance(ident, str) or not ident.strip():
            continue
        listed.append(item)
    return listed


def printed_dataflow_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if not isinstance(ident, str) or not ident.strip():
        raise SourceError("Norges Bank dataflow has no printed id")
    return ident.strip()


def printed_data_url(ident: str, list_url: str) -> str:
    """Join a printed dataflow id to the same-host /api/data/{id} path.

    The list API is `/api/dataflow?format=sdmx-json`. Live data messages print
    `meta.links.href` values such as `/data/EXR?format=sdmx-json` under that
    `/api` origin. The `format=sdmx-json` query is copied from the list URL
    because `/api/data/{id}` without it returns XML. No dataflow id is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Norges Bank list URL has no printed origin")
    suffix = ident if ident.startswith("/") else ident
    return f"{parts.scheme}://{parts.netloc}{DATA_PATH_PREFIX}{suffix}?{FORMAT_QUERY}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    names = item.get("names") if isinstance(item.get("names"), dict) else {}
    title: dict[str, str] = {}
    for lang in ("no", "nb", "nn", "en"):
        value = names.get(lang)
        if isinstance(value, str) and value.strip():
            title[lang] = value.strip()
    if title:
        return title
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return {"en": name.strip()}
    return {"en": ident}


def printed_localized(names: Any, fallback: Any, default: str | None) -> str | None:
    if isinstance(names, dict):
        for lang in ("no", "nb", "nn", "en"):
            value = names.get(lang)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return default


def is_norgesbank_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(DATA_PATH_PREFIX)


def norgesbank_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "norgesbank"


def cells_from_norgesbank(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed SDMX-JSON series observations into cells.

    Series keys map onto printed `structure.dimensions.series` values.
    Observation keys map onto printed `structure.dimensions.observation`
    values (TIME_PERIOD). The observation value is the first printed array
    element. Nothing is invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("norgesbank payload is not a JSON object")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("norgesbank payload has no printed data object")
    datasets = data.get("dataSets")
    structure = data.get("structure")
    if not isinstance(datasets, list):
        raise ValueError("norgesbank payload has no printed dataSets array")
    if not isinstance(structure, dict):
        raise ValueError("norgesbank payload has no printed structure object")
    series_dims = _dimension_list(structure, "series")
    obs_dims = _dimension_list(structure, "observation")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for dataset in datasets:
        if not isinstance(dataset, dict):
            continue
        series = dataset.get("series")
        if isinstance(series, dict):
            for key, item in series.items():
                if not isinstance(item, dict):
                    continue
                series_values = _decode_key(str(key), series_dims)
                observations = item.get("observations")
                if not isinstance(observations, dict):
                    continue
                measure = _measure(series_values, structure)
                measure_dim = _measure_dimension(series_values, series_dims)
                for obs_key, obs_val in observations.items():
                    obs_values = _decode_key(str(obs_key), obs_dims)
                    dims = {
                        name: value
                        for name, value in {**series_values, **obs_values}.items()
                        if name != measure_dim
                    }
                    cells.append((measure, _observation_value(obs_val), dims))
            continue
        observations = dataset.get("observations")
        if isinstance(observations, dict):
            measure = _structure_name(structure)
            for obs_key, obs_val in observations.items():
                dims = _decode_key(str(obs_key), obs_dims)
                cells.append((measure, _observation_value(obs_val), dims))
    if not cells:
        raise ValueError("norgesbank payload printed no observations")
    return cells


def _dimension_list(structure: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    dimensions = structure.get("dimensions")
    if not isinstance(dimensions, dict):
        return []
    listed = dimensions.get(kind)
    if not isinstance(listed, list):
        return []
    return [item for item in listed if isinstance(item, dict)]


def _decode_key(key: str, dims: list[dict[str, Any]]) -> dict[str, str]:
    parts = key.split(":")
    decoded: dict[str, str] = {}
    for dim, part in zip(dims, parts):
        dim_id = dim.get("id")
        if not isinstance(dim_id, str) or not dim_id.strip():
            continue
        try:
            index = int(part)
        except ValueError:
            continue
        values = dim.get("values") if isinstance(dim.get("values"), list) else []
        if index < 0 or index >= len(values) or not isinstance(values[index], dict):
            continue
        item = values[index]
        label = item.get("name")
        if not isinstance(label, str) or not label.strip():
            label = item.get("id")
        if isinstance(label, str) and label.strip():
            decoded[dim_id] = label.strip()
    return decoded


def _measure(series_values: dict[str, str], structure: dict[str, Any]) -> str:
    if len(series_values) == 1:
        return next(iter(series_values.values()))
    return _structure_name(structure)


def _measure_dimension(
    series_values: dict[str, str],
    series_dims: list[dict[str, Any]],
) -> str | None:
    if len(series_values) != 1:
        return None
    dim_id = next(iter(series_values))
    if any(dim.get("id") == dim_id for dim in series_dims):
        return dim_id
    return None


def _structure_name(structure: dict[str, Any]) -> str:
    names = structure.get("names")
    localized = printed_localized(names, structure.get("name"), None)
    if localized:
        return localized
    raise ValueError("norgesbank structure printed no name")


def _observation_value(obs_val: Any) -> Any:
    if isinstance(obs_val, list) and obs_val:
        return obs_val[0]
    return obs_val
