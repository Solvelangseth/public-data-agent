from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "vegvesen"
SOURCE_NAME = "Statens vegvesen Dataportalen"
LIST_URL = "https://dataut.vegvesen.no/api/3/action/package_list"
SHOW_PATH = "/api/3/action/package_show"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a package name on the official Statens vegvesen Dataportalen "
    f"CKAN package_list, capped at {DEFAULT_MAX_ITEMS} packages"
)
VEGVESEN_RPS = 2.0
VEGVESEN_BURST = 4
HOST = "dataut.vegvesen.no"
NAME_FIELDS = ("name", "title", "url", "id")


class VegvesenSource(SourceBase):
    """Replaceable ingest adapter for Statens vegvesen Dataportalen.

    Listing copies package names the official CKAN package_list prints. It
    does not invent ids. Native ids are those printed names. access_path is
    the catalog's own package_show action with the printed name. This first
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
            limiter=RateLimiter(VEGVESEN_RPS, VEGVESEN_BURST),
            timeout=60.0,
        )
        self._listed: list[str] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for name in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=printed_package_show_url(name, self.list_url),
                    source_native_id=name,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        name = ref.source_native_id or vegvesen_table_id(ref.source_native_uri or "")
        item = self._package(name)
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            title = name
        notes = item.get("notes")
        endpoint = printed_package_show_url(name, self.list_url)
        payload = {
            "id": name,
            "uri": endpoint,
            "title": {"no": title},
            "description": (
                {"no": notes} if isinstance(notes, str) and notes.strip() else None
            ),
            "publisher": printed_publisher(item),
            "license": printed_license_url(item),
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.list_url],
            "vegvesen_package_name": name,
            "vegvesen_package": item,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=name,
            source_native_uri=endpoint,
            fetched_from=self.list_url,
            payload=payload,
        )

    def _catalog(self) -> list[str]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(
                f"Vegvesen Dataportalen list failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_package_names(body)
        if not listed:
            raise SourceError(f"Vegvesen Dataportalen printed no packages: {self.list_url}")
        self._listed = listed
        return listed

    def _package(self, name: str) -> dict[str, Any]:
        url = printed_package_show_url(name, self.list_url)
        try:
            body = self.http.get_json(url)
        except Exception as exc:
            raise SourceError(f"Vegvesen Dataportalen package_show failed for {url}: {exc}") from exc
        item = printed_package(body)
        printed_name = item.get("name")
        if isinstance(printed_name, str) and printed_name.strip() and printed_name.strip() != name:
            raise SourceError(
                f"Vegvesen Dataportalen package_show printed name {printed_name!r}, not {name!r}"
            )
        return item


def printed_package_names(body: Any) -> list[str]:
    if not isinstance(body, dict):
        raise SourceError("Vegvesen Dataportalen package_list is not a JSON object")
    result = body.get("result")
    if not isinstance(result, list):
        raise SourceError("Vegvesen Dataportalen package_list has no printed result array")
    listed: list[str] = []
    for item in result:
        if isinstance(item, str) and item.strip():
            listed.append(item.strip())
    return listed


def printed_package(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise SourceError("Vegvesen Dataportalen package_show is not a JSON object")
    result = body.get("result")
    if not isinstance(result, dict):
        raise SourceError("Vegvesen Dataportalen package_show has no printed result object")
    name = result.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SourceError("Vegvesen Dataportalen package_show has no printed name")
    return result


def printed_package_show_url(name: str, list_url: str) -> str:
    """Join a printed package name to the catalog's own package_show action.

    The live list API is CKAN `/api/3/action/package_list`. The same action
    API prints `/api/3/action/package_show?id=`. The origin is copied from
    the list URL. No package name is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Vegvesen Dataportalen list URL has no printed origin")
    return f"{parts.scheme}://{parts.netloc}{SHOW_PATH}?id={name}"


def printed_license_url(item: dict[str, Any]) -> str | None:
    url = item.get("license_url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return url.strip()
    return None


def printed_publisher(item: dict[str, Any]) -> dict[str, Any] | None:
    organization = item.get("organization")
    if not isinstance(organization, dict):
        return None
    title = organization.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    publisher: dict[str, Any] = {"title": {"no": title.strip()}}
    ident = organization.get("id")
    if isinstance(ident, str) and ident.strip():
        publisher["id"] = ident.strip()
    return publisher


def is_vegvesen_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.rstrip("/") == SHOW_PATH


def vegvesen_table_id(access_path: str) -> str:
    query = parse_qs(urlsplit(access_path).query)
    values = query.get("id") or []
    if values and values[0].strip():
        return values[0].strip()
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "vegvesen"


def cells_from_vegvesen(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed CKAN resources into observation cells.

    package_show keeps printed `name` when present. Other scalars stay as
    dimensions. Nested objects are not copied. Nothing is invented.
    """

    item = _package_result(payload)
    resources = item.get("resources")
    if not isinstance(resources, list):
        raise ValueError("vegvesen payload has no printed resources array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for resource in resources:
        if isinstance(resource, dict):
            cells.extend(_cells_from_record(resource))
    if not cells:
        raise ValueError("vegvesen payload printed no resources")
    return cells


def _package_result(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("vegvesen payload is not a JSON object")
    result = payload.get("result")
    if isinstance(result, dict):
        return result
    if isinstance(payload.get("resources"), list):
        return payload
    raise ValueError("vegvesen payload has no printed result object")


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    measure = None
    value: Any = None
    for field in NAME_FIELDS:
        if field in scalars and scalars[field] not in (None, ""):
            measure = field
            value = scalars[field]
            break
    if measure is None:
        measure, value = next(iter(scalars.items()))
    dims = {key: _as_dim(other) for key, other in scalars.items() if key != measure}
    return [(measure, value, dims)]


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
