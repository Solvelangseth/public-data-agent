from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "nbdsd"
SOURCE_NAME = "Norges Bank SDMX data structures"
LIST_URL = "https://data.norges-bank.no/api/datastructure?format=sdmx-json"
PATH_PREFIX = "/api/datastructure"
FORMAT_QUERY = "format=sdmx-json"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a data structure on the official Norges Bank SDMX "
    f"datastructure catalog, capped at {DEFAULT_MAX_ITEMS} structures"
)
NBDSD_RPS = 2.0
NBDSD_BURST = 4
HOST = "data.norges-bank.no"


class NbdsdSource(SourceBase):
    """Replaceable ingest adapter for leftover Norges Bank SDMX data structures.

    Listing copies printed `data.dataStructures[].id` and `agencyID` from the
    official `/api/datastructure` catalog. It does not invent ids.
    `access_path` joins those printed fields onto
    `/api/datastructure/{agencyID}/{id}` and keeps the same
    `format=sdmx-json` query the list API uses. This first slice stays
    inside that list and caps the walk. This is not the dataflow list
    (`--source norgesbank`).
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
            limiter=RateLimiter(NBDSD_RPS, NBDSD_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_structure_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_structure_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or nbdsd_table_id(ref.source_native_uri or "")
        item = self._catalog_item(ident)
        description = printed_localized(
            item.get("descriptions"),
            item.get("description"),
            None,
        )
        endpoint = printed_structure_url(item, self.list_url)
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
            "nbdsd_datastructure": item,
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
                f"Norges Bank datastructure list failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_structures(body)
        if not listed:
            raise SourceError("Norges Bank datastructure list printed no data structures")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_structure_id(item) == ident:
                return item
        raise SourceError(
            f"Norges Bank datastructure list has no printed structure {ident}"
        )


def printed_structures(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Norges Bank datastructure list is not a JSON object")
    data = body.get("data")
    if not isinstance(data, dict):
        raise SourceError("Norges Bank datastructure list has no printed data object")
    structures = data.get("dataStructures")
    if not isinstance(structures, list):
        raise SourceError(
            "Norges Bank datastructure list has no printed dataStructures array"
        )
    listed: list[dict[str, Any]] = []
    for item in structures:
        if not isinstance(item, dict):
            continue
        ident = item.get("id")
        agency = item.get("agencyID")
        if not isinstance(ident, str) or not ident.strip():
            continue
        if not isinstance(agency, str) or not agency.strip():
            continue
        listed.append(item)
    return listed


def printed_structure_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if not isinstance(ident, str) or not ident.strip():
        raise SourceError("Norges Bank data structure has no printed id")
    return ident.strip()


def printed_agency_id(item: dict[str, Any]) -> str:
    agency = item.get("agencyID")
    if not isinstance(agency, str) or not agency.strip():
        raise SourceError("Norges Bank data structure has no printed agencyID")
    return agency.strip()


def printed_structure_url(item: dict[str, Any], list_url: str) -> str:
    """Join printed agencyID and id onto the same-host datastructure path.

    The list API is `/api/datastructure?format=sdmx-json`. A structure GET
    keeps that path plus the printed agency and id. The `format=sdmx-json`
    query is copied from the list URL because the same path without it
    returns XML. No agency or structure id is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Norges Bank datastructure list URL has no printed origin")
    agency = printed_agency_id(item)
    ident = printed_structure_id(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{agency}/{ident}?{FORMAT_QUERY}"


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


def is_nbdsd_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    path = parsed.path.rstrip("/")
    if parsed.netloc.lower() != HOST or not path.startswith(PATH_PREFIX + "/"):
        return False
    leftover = path[len(PATH_PREFIX) + 1 :]
    return bool(leftover)


def nbdsd_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "nbdsd"


def cells_from_nbdsd(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed SDMX data-structure component ids into cells.

    Each printed dimension, time dimension, attribute, and primary measure
    keeps its `id`. Other printed scalars stay as dimensions. Nested
    objects and arrays are not copied. Nothing is invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("nbdsd payload is not a JSON object")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("nbdsd payload has no printed data object")
    structures = data.get("dataStructures")
    if not isinstance(structures, list):
        raise ValueError("nbdsd payload has no printed dataStructures array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in structures:
        if not isinstance(item, dict):
            continue
        comps = item.get("dataStructureComponents")
        if not isinstance(comps, dict):
            continue
        dim_list = comps.get("dimensionList")
        if isinstance(dim_list, dict):
            for key in ("dimensions", "timeDimensions"):
                listed = dim_list.get(key)
                if isinstance(listed, list):
                    for component in listed:
                        cells.extend(_cells_from_component(component))
        attr_list = comps.get("attributeList")
        if isinstance(attr_list, dict):
            attributes = attr_list.get("attributes")
            if isinstance(attributes, list):
                for component in attributes:
                    cells.extend(_cells_from_component(component))
        measure_list = comps.get("measureList")
        if isinstance(measure_list, dict):
            primary = measure_list.get("primaryMeasure")
            if isinstance(primary, dict):
                cells.extend(_cells_from_component(primary))
    if not cells:
        raise ValueError("nbdsd payload printed no structure components")
    return cells


def _cells_from_component(item: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(item, dict):
        return []
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    ident = scalars.get("id")
    if not isinstance(ident, str) or not ident.strip():
        return []
    dims = {key: _as_dim(other) for key, other in scalars.items() if key != "id"}
    return [("id", ident, dims)]


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
