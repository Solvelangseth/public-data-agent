from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "vegvesen"
SOURCE_NAME = "Statens vegvesen Dataportalen"
LIST_URL = "https://dataut.vegvesen.no/api/3/action/package_list"
SEARCH_URL = "https://dataut.vegvesen.no/api/3/action/package_search"
SHOW_PATH = "/api/3/action/package_show"
# Only data services are harvested. Measured against the registry, every one of
# the portal's 62 `dataset` packages is already catalogued through data.norge --
# matched by CKAN package id -- and none of its 23 `dataservice` packages is.
# Harvesting both would put a second copy of 62 records into search, and
# data.norge's copies already carry the licences (no licence disagreed).
SERVICE_TYPE = "dataservice"
PAGE_SIZE = 100
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a data service on the official Statens vegvesen Dataportalen CKAN "
    f"package_search, capped at {DEFAULT_MAX_ITEMS} packages; the portal's datasets "
    "are already catalogued through data.norge"
)
VEGVESEN_RPS = 2.0
VEGVESEN_BURST = 4
HOST = "dataut.vegvesen.no"


class VegvesenSource(SourceBase):
    """Replaceable ingest adapter for Statens vegvesen Dataportalen data services.

    Listing copies the packages CKAN `package_search` prints for
    `type:dataservice`, which carries each package's full metadata, so no
    per-package request is needed. Native ids are the printed package names.

    A record points at the service, not at the catalogue that describes it:
    the printed `end_point_url` and resource URLs become its distributions, and
    the printed `uri` and `url` its landing pages. It used to point at CKAN's own
    `package_show` action, which returns metadata -- and a fetch of that stored
    each resource's description as if it were an observation.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (SEARCH_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        search_url: str = SEARCH_URL,
        list_url: str = LIST_URL,
        max_items: int = DEFAULT_MAX_ITEMS,
        page_size: int = PAGE_SIZE,
        http: HttpClient | None = None,
    ) -> None:
        self.search_url = search_url
        self.list_url = list_url
        self.max_items = max_items
        self.page_size = page_size
        self.http = http or HttpClient(
            limiter=RateLimiter(VEGVESEN_RPS, VEGVESEN_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        refs: list[DatasetRef] = []
        for item in self._catalog()[offset : offset + cap]:
            name = item["name"].strip()
            refs.append(
                DatasetRef(
                    source_native_uri=printed_service_uri(item)
                    or printed_package_show_url(name, self.list_url),
                    source_native_id=name,
                    catalog_modified=_string(item.get("metadata_modified")),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        name = ref.source_native_id or vegvesen_table_id(ref.source_native_uri or "")
        item = self._listed_package(name) or self._package(name)
        title = _string(item.get("title")) or name
        notes = _string(item.get("notes"))
        show_url = printed_package_show_url(name, self.list_url)
        distribution = printed_distributions(item, title)
        landing = printed_landing_pages(item)
        payload: dict[str, Any] = {
            "id": name,
            "uri": printed_service_uri(item) or show_url,
            "title": {"no": title},
            "description": {"no": notes} if notes else None,
            "publisher": printed_publisher(item),
            "license": printed_license_url(item),
            "distribution": distribution,
            "landingPage": landing,
            "vegvesen_package_name": name,
            "vegvesen_package": item,
        }
        rights = printed_access_rights(item)
        if rights:
            payload["accessRights"] = rights
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=name,
            source_native_uri=ref.source_native_uri or payload["uri"],
            fetched_from=self.search_url,
            payload=payload,
            catalog_modified=_string(item.get("metadata_modified")) or None,
        )

    def _catalog(self) -> list[dict[str, Any]]:
        if self._listed is not None:
            return self._listed
        listed: list[dict[str, Any]] = []
        start = 0
        while True:
            url = (
                f"{self.search_url}?fq=type:{SERVICE_TYPE}"
                f"&rows={self.page_size}&start={start}"
            )
            try:
                body = self.http.get_json(url)
            except Exception as exc:
                raise SourceError(f"Vegvesen Dataportalen search failed for {url}: {exc}") from exc
            count, page = printed_search_page(body)
            for item in page:
                # Checked here as well as asked for in the query: a portal that
                # ignored `fq` would otherwise hand back the 62 datasets
                # data.norge already carries.
                if item.get("type") != SERVICE_TYPE or item.get("private") is True:
                    continue
                if _string(item.get("name")):
                    listed.append(item)
            start += len(page)
            if not page or start >= count:
                break
        self._listed = listed
        return listed

    def _listed_package(self, name: str) -> dict[str, Any] | None:
        for item in self._listed or []:
            if _string(item.get("name")) == name:
                return item
        return None

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


def printed_search_page(body: Any) -> tuple[int, list[dict[str, Any]]]:
    if not isinstance(body, dict):
        raise SourceError("Vegvesen Dataportalen package_search is not a JSON object")
    result = body.get("result")
    if not isinstance(result, dict):
        raise SourceError("Vegvesen Dataportalen package_search has no printed result object")
    results = result.get("results")
    if not isinstance(results, list):
        raise SourceError("Vegvesen Dataportalen package_search has no printed results array")
    count = result.get("count")
    page = [item for item in results if isinstance(item, dict)]
    return (count if isinstance(count, int) else len(page)), page


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

    The origin is copied from the list URL. No package name is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Vegvesen Dataportalen list URL has no printed origin")
    return f"{parts.scheme}://{parts.netloc}{SHOW_PATH}?id={name}"


def printed_service_uri(item: dict[str, Any]) -> str | None:
    """The publisher's own identifier for a data service, a live page on the portal."""

    return _http_url(item.get("uri"))


def printed_distributions(item: dict[str, Any], title: str) -> list[dict[str, Any]]:
    """Where the service's data is, as the portal prints it.

    The API endpoint comes first, since for a data service it is the thing
    itself; printed resources follow. Formats are left in the stored package
    rather than mapped, because the portal prints "xml" or "ukjent" and turning
    that into a media type would be a guess.
    """

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    endpoint = _http_url(item.get("end_point_url"))
    if endpoint:
        out.append({"accessURL": [endpoint], "title": {"no": title}})
        seen.add(endpoint)
    for resource in item.get("resources") or []:
        if not isinstance(resource, dict):
            continue
        url = _http_url(resource.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        entry: dict[str, Any] = {"accessURL": [url]}
        name = _string(resource.get("name"))
        if name:
            entry["title"] = {"no": name}
        out.append(entry)
    return out


def printed_landing_pages(item: dict[str, Any]) -> list[str]:
    pages: list[str] = []
    for value in (item.get("uri"), item.get("url")):
        url = _http_url(value)
        if url and url not in pages:
            pages.append(url)
    return pages


def printed_access_rights(item: dict[str, Any]) -> dict[str, str] | None:
    """The printed EU access-right authority URI, with its code copied from the URI.

    A restricted or unlabelled service must not read as open data because it
    appears in an open portal. Of the 23 data services, 13 print PUBLIC, five
    print RESTRICTED -- NVDB Skriv, Datafangst, vehicle data with owner details,
    eCOC, driving-log submission -- and five print nothing, which stays unknown
    rather than becoming open.
    """

    uri = _http_url(item.get("access_rights"))
    if not uri:
        return None
    return {"uri": uri, "code": uri.rstrip("/").split("/")[-1]}


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
    """Whether a URL is the portal's package_show action.

    Deliberately not imported by `fetch.py`: that action returns catalogue
    metadata, and a connector predicate there would make it look fetchable.
    """

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


def _http_url(value: Any) -> str | None:
    if isinstance(value, str) and value.strip().startswith(("http://", "https://")):
        return value.strip()
    return None


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
