from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ngu"
SOURCE_NAME = "Norges geologiske undersøkelse OGC API Features"
LIST_URL = "https://geo.ngu.no/api/features"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a dataset id on the official Norges geologiske undersøkelse "
    f"OGC API Features catalog, capped at {DEFAULT_MAX_ITEMS} datasets"
)
NGU_RPS = 2.0
NGU_BURST = 4
HOST = "geo.ngu.no"
PATH_PREFIX = "/api/features"
NAME_FIELDS = ("title", "rel", "href")


class NguSource(SourceBase):
    """Replaceable ingest adapter for Norges geologiske undersøkelse OGC Features.

    Listing copies dataset ids the official catalog JSON prints in `apis`.
    It does not invent ids. Native ids are those printed ids. access_path is
    the printed landingPageUri. This first slice stays inside that apis
    array and caps the walk.
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
            limiter=RateLimiter(NGU_RPS, NGU_BURST),
            timeout=60.0,
        )
        self._spec: dict[str, Any] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = printed_apis(self._catalog())
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=printed_landing_page(item),
                    source_native_id=printed_api_id(item),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        spec = self._catalog()
        item = _api_for_ref(spec, ref)
        ident = printed_api_id(item)
        endpoint = printed_landing_page(item)
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            title = ident
        description = item.get("description")
        payload = {
            "id": ident,
            "uri": endpoint,
            "title": {"no": title},
            "description": (
                {"no": description} if isinstance(description, str) else None
            ),
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.list_url],
            "ngu_api": item,
            "ngu_catalog": {
                key: spec.get(key)
                for key in ("title", "catalogUri")
                if key in spec
            },
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

    def _catalog(self) -> dict[str, Any]:
        if self._spec is not None:
            return self._spec
        try:
            spec = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(
                f"Norges geologiske undersøkelse catalog failed for {self.list_url}: {exc}"
            ) from exc
        if not isinstance(spec, dict):
            raise SourceError(
                f"Norges geologiske undersøkelse catalog is not a JSON object: {self.list_url}"
            )
        if not printed_apis(spec):
            raise SourceError(
                f"Norges geologiske undersøkelse catalog printed no datasets: {self.list_url}"
            )
        self._spec = spec
        return spec


def printed_apis(spec: dict[str, Any]) -> list[dict[str, Any]]:
    apis = spec.get("apis")
    if not isinstance(apis, list):
        raise SourceError("Norges geologiske undersøkelse catalog has no printed apis array")
    listed: list[dict[str, Any]] = []
    for item in apis:
        if not isinstance(item, dict):
            continue
        try:
            printed_api_id(item)
            printed_landing_page(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_api_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if not isinstance(ident, str) or not ident.strip():
        raise SourceError("Norges geologiske undersøkelse dataset has no printed id")
    return ident.strip()


def printed_landing_page(item: dict[str, Any]) -> str:
    href = item.get("landingPageUri")
    if not isinstance(href, str) or not href.strip():
        raise SourceError("Norges geologiske undersøkelse dataset has no printed landingPageUri")
    return href.strip()


def is_ngu_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    path = parsed.path.rstrip("/")
    if not path.startswith(PATH_PREFIX):
        return False
    rest = path[len(PATH_PREFIX) :].lstrip("/")
    return bool(rest)


def ngu_table_id(access_path: str) -> str:
    path = urlsplit(access_path).path.rstrip("/")
    prefix = PATH_PREFIX.rstrip("/")
    rest = path[len(prefix) :].lstrip("/") if path.startswith(prefix) else ""
    segment = rest.split("/", 1)[0]
    return segment or "ngu"


# The link a landing page prints to say where its data is. Following it is
# reading the publisher's own declaration, not guessing a path.
# OGC API Features defines both a compact relation name and a full URI for
# the same link, and publishers use either. geo.ngu.no prints the URI; the
# spec's own examples use the compact form. Accepting one would work against
# this publisher today and break against the next.
DATA_REL = "http://www.opengis.net/def/rel/ogc/1.0/data"
DATA_RELS = (DATA_REL, "data")
ITEMS_RELS = ("items", "http://www.opengis.net/def/rel/ogc/1.0/items")
ITEMS_REL = "items"

# What NGU calls a feature's name. `NAME_FIELDS` above is for the landing
# page's links -- title, rel, href -- and means nothing on a seabed polygon.
# NGU's own convention is a `*Navn` field beside the code it names:
# `ankringsforhold` / `ankringsforholdNavn`, `geolPavisningstype` /
# `geolPavisningstypeNavn`. The suffix is the publisher's, not a guess.
FEATURE_NAME_SUFFIX = "Navn"
FEATURE_ID_FIELDS = ("identifikasjon.lokalId", "lokalId", "id", "objectid")


def cells_from_ngu(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Refuse a landing page. It is a door, not a room.

    This function used to copy the landing page's `links` array into
    observation cells, and its own docstring said so. Fetching
    `ngu:ankringsforhold` stored seventeen rows whose measure was `title` and
    whose values were "This document as HTML" and "OGC API conformance
    classes implemented by this server", and marked the dataset verified with
    a sample count of 17.

    That is the mistake this project spent the session removing from eleven
    thousand rows elsewhere: a listing of what a service offers is metadata,
    and a listing of things the world contains is data. An OGC landing page
    is the first kind. It prints a `data` link saying where the second kind
    is, and `collections_url` reads it.
    """

    raise ValueError(
        "an NGU landing page lists links, not features; follow its "
        f"{DATA_REL!r} link to /collections and read a collection's items"
    )


def collections_url(payload: Any, access_path: str) -> str:
    """Where the landing page says its data is.

    Taken from the printed `data` link. Composing `access_path + /collections`
    would usually give the same string and would be a guess; when a publisher
    moves it, a guess breaks silently and a declaration does not.
    """

    if not isinstance(payload, dict):
        raise ValueError("ngu landing page is not a JSON object")
    for link in payload.get("links") or []:
        if not isinstance(link, dict):
            continue
        if link.get("rel") not in DATA_RELS:
            continue
        href = link.get("href")
        if isinstance(href, str) and href.startswith("http"):
            return href
    raise ValueError(
        f"ngu landing page {access_path} prints no {' or '.join(repr(r) for r in DATA_RELS)} "
        "link, so it does not say where its data is"
    )


def printed_collections(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("ngu collections payload is not a JSON object")
    listed = payload.get("collections")
    if not isinstance(listed, list) or not listed:
        raise ValueError("ngu collections payload printed no collections array")
    return [item for item in listed if isinstance(item, dict)]


def items_url(collection: dict[str, Any]) -> str | None:
    """The JSON items link a collection prints, or None if it prints none."""

    for link in collection.get("links") or []:
        if not isinstance(link, dict) or link.get("rel") not in ITEMS_RELS:
            continue
        kind = str(link.get("type") or "").casefold()
        if "json" not in kind:
            continue
        href = link.get("href")
        if isinstance(href, str) and href.startswith("http"):
            return href
    return None


def cells_from_ngu_items(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed features into cells, one per feature.

    NGU publishes seabed and bedrock polygons -- things in places -- so these
    become `feature` records, not observations. Property names arrive dotted
    (`identifikasjon.lokalId`) and are kept exactly as printed.
    """

    if not isinstance(payload, dict):
        raise ValueError("ngu items payload is not a JSON object")
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("ngu items payload printed no features array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict) or not properties:
            continue
        scalars = {k: v for k, v in properties.items() if _is_scalar(v) and v is not None}
        if not scalars:
            continue
        measure = None
        for field in sorted(scalars):
            if field.endswith(FEATURE_NAME_SUFFIX) and isinstance(scalars[field], str) \
                    and str(scalars[field]).strip():
                measure = field
                break
        if measure is None:
            for field in FEATURE_ID_FIELDS:
                if scalars.get(field) is not None:
                    measure = field
                    break
        if measure is None:
            measure = next(iter(scalars))
        value = scalars[measure]
        dims = {k: _as_dim(v) for k, v in scalars.items() if k != measure}
        fid = feature.get("id")
        if fid is not None and "id" not in dims:
            dims["id"] = _as_dim(fid)
        cells.append((measure, value, dims))
    if not cells:
        raise ValueError("ngu items payload printed no feature with properties")
    return cells


def _api_for_ref(spec: dict[str, Any], ref: DatasetRef) -> dict[str, Any]:
    for item in printed_apis(spec):
        if printed_landing_page(item) == ref.source_native_uri:
            return item
        if printed_api_id(item) == ref.source_native_id:
            return item
    raise SourceError(
        f"Norges geologiske undersøkelse catalog has no printed dataset matching {ref.source_native_uri}"
    )


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    measure = None
    value: Any = None
    for field in NAME_FIELDS:
        printed = scalars.get(field)
        if isinstance(printed, str) and printed.strip():
            measure = field
            value = printed
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
