from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "crunit"
SOURCE_NAME = "Cristin units"
LIST_URL = "https://api.cristin.no/v2/units"
PATH_PREFIX = "/v2/units"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed unit on the official Cristin "
    f"units catalog, capped at {DEFAULT_MAX_ITEMS} organisations"
)
CRUNIT_RPS = 2.0
CRUNIT_BURST = 4
HOST = "api.cristin.no"
NAME_FIELDS = ("unit_name", "acronym", "cristin_unit_id")
LANG_ORDER = ("nb", "nn", "no", "en")


class CrunitSource(SourceBase):
    """Replaceable ingest adapter for leftover Cristin units.

    Listing copies printed `cristin_unit_id` values and the printed
    `url` from the official `/v2/units` collection. Native ids are
    the printed `cristin_unit_id` strings so `1000.0.0.0` stays
    distinct from the next printed member. This first slice stays
    inside that catalog and caps the walk. It does not invent page,
    per_page, or other optional query filters. This is not the Cristin
    documentation path list (`--source cristin`) and not leftover
    institutions (`--source crinst`).
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
            limiter=RateLimiter(CRUNIT_RPS, CRUNIT_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_unit_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or crunit_table_id(ref.source_native_uri or "")
        item = self._catalog_item(ident)
        endpoint = printed_item_url(item, self.list_url)
        title = printed_title(item, ident)
        payload = {
            "id": ident,
            "uri": endpoint,
            "title": title,
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.list_url],
            "crunit_unit": {
                key: item[key]
                for key in item
                if key != "url"
            },
            "crunit_self_href": endpoint,
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
                f"Cristin units catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_units(body)
        if not listed:
            raise SourceError("Cristin units catalog printed no units")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_unit_id(item) == ident:
                return item
        raise SourceError(
            f"Cristin units catalog has no printed cristin_unit_id {ident}"
        )


def printed_units(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, list):
        raise SourceError("Cristin units catalog is not a JSON array")
    listed: list[dict[str, Any]] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        try:
            printed_unit_id(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_unit_id(item: dict[str, Any]) -> str:
    ident = item.get("cristin_unit_id")
    if isinstance(ident, bool):
        raise SourceError("Cristin unit has no printed cristin_unit_id")
    if isinstance(ident, int):
        return str(ident)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("Cristin unit has no printed cristin_unit_id")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Copy printed `url`, else join printed cristin_unit_id.

    The catalog is `/v2/units`. Each printed member has
    `cristin_unit_id` and a public `url` on that same path.
    The printed url is copied. No page query is invented.
    """

    href = item.get("url")
    if isinstance(href, str) and href.strip():
        return href.strip()
    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Cristin units catalog URL has no printed origin")
    ident = printed_unit_id(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{ident}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    name = localized_name(item.get("unit_name"))
    if name:
        return {"nb": name}
    acronym = item.get("acronym")
    if isinstance(acronym, str) and acronym.strip():
        return {"nb": acronym.strip()}
    return {"nb": ident}


def localized_name(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for lang in LANG_ORDER:
            printed = value.get(lang)
            if isinstance(printed, str) and printed.strip():
                return printed.strip()
    return None


def is_crunit_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    path = parsed.path.rstrip("/")
    prefix = PATH_PREFIX + "/"
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :]
    return bool(rest) and "/" not in rest


def crunit_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "crunit"


def cells_from_crunit(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("crunit payload is not a JSON object")
    cells = _cells_from_record(payload)
    if not cells:
        raise ValueError("crunit payload printed no unit members")
    return cells


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    values: dict[str, Any] = {}
    for key, value in item.items():
        if key == "url":
            continue
        copied = _copy_value(value)
        if copied is not None:
            values[key] = copied
    if not values:
        return []
    measure = None
    value: Any = None
    for field in NAME_FIELDS:
        printed = values.get(field)
        if printed is None:
            continue
        if isinstance(printed, str) and not printed.strip():
            continue
        measure = field
        value = printed
        break
    if measure is None:
        measure, value = next(iter(values.items()))
    dims = {key: _as_dim(other) for key, other in values.items() if key != measure}
    return [(measure, value, dims)]


def _copy_value(value: Any) -> Any:
    if _is_scalar(value):
        return value
    if isinstance(value, dict):
        return localized_name(value)
    return None


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
