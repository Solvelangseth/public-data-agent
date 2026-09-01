from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "crbio"
SOURCE_NAME = "Cristin biobanks"
LIST_URL = "https://api.cristin.no/v2/biobanks"
PATH_PREFIX = "/v2/biobanks"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed biobank on the official Cristin "
    f"biobanks catalog, capped at {DEFAULT_MAX_ITEMS} organisations"
)
CRBIO_RPS = 2.0
CRBIO_BURST = 4
HOST = "api.cristin.no"
NAME_FIELDS = ("name", "biobank_id", "cristin_biobank_id")
LANG_ORDER = ("nb", "nn", "no", "en")


class CrbioSource(SourceBase):
    """Replaceable ingest adapter for leftover Cristin biobanks.

    Listing copies printed `cristin_biobank_id` values and the printed
    `url` from the official `/v2/biobanks` collection. Native ids are
    the printed `cristin_biobank_id` strings so `2052825` stays
    distinct from the next printed member. This first slice stays
    inside that catalog and caps the walk. It does not invent page,
    per_page, or other optional query filters. This is not the Cristin
    documentation path list (`--source cristin`), not leftover
    institutions (`--source crinst`), and not leftover units
    (`--source crunit`).
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
            limiter=RateLimiter(CRBIO_RPS, CRBIO_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_biobank_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or crbio_table_id(ref.source_native_uri or "")
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
            "crbio_biobank": {
                key: item[key]
                for key in item
                if key != "url"
            },
            "crbio_self_href": endpoint,
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
                f"Cristin biobanks catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_biobanks(body)
        if not listed:
            raise SourceError("Cristin biobanks catalog printed no biobanks")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_biobank_id(item) == ident:
                return item
        raise SourceError(
            f"Cristin biobanks catalog has no printed cristin_biobank_id {ident}"
        )


def printed_biobanks(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, list):
        raise SourceError("Cristin biobanks catalog is not a JSON array")
    listed: list[dict[str, Any]] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        try:
            printed_biobank_id(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_biobank_id(item: dict[str, Any]) -> str:
    ident = item.get("cristin_biobank_id")
    if isinstance(ident, bool):
        raise SourceError("Cristin biobank has no printed cristin_biobank_id")
    if isinstance(ident, int):
        return str(ident)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("Cristin biobank has no printed cristin_biobank_id")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Copy printed `url`, else join printed cristin_biobank_id.

    The catalog is `/v2/biobanks`. Each printed member has
    `cristin_biobank_id` and a public `url` on that same path.
    The printed url is copied. No page query is invented.
    """

    href = item.get("url")
    if isinstance(href, str) and href.strip():
        return href.strip()
    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Cristin biobanks catalog URL has no printed origin")
    ident = printed_biobank_id(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{ident}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    name = localized_name(item.get("name"))
    if name:
        return {"nb": name}
    biobank_id = item.get("biobank_id")
    if isinstance(biobank_id, str) and biobank_id.strip():
        return {"nb": biobank_id.strip()}
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


def is_crbio_url(access_path: str | None) -> bool:
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


def crbio_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "crbio"


def cells_from_crbio(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("crbio payload is not a JSON object")
    cells = _cells_from_record(payload)
    if not cells:
        raise ValueError("crbio payload printed no biobank members")
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
