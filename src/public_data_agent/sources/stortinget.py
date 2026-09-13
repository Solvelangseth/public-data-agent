from __future__ import annotations

import html as html_lib
import re
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "stortinget"
SOURCE_NAME = "Stortinget åpne data"
DOCS_URL = "https://data.stortinget.no/dokumentasjon-og-hjelp/teknisk-dokumentasjon/"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as an untemplated collection GET path in the official Stortinget "
    f"technical documentation, capped at {DEFAULT_MAX_ITEMS} paths"
)
STORTINGET_RPS = 2.0
STORTINGET_BURST = 4
HOST = "data.stortinget.no"
PATH_PREFIX = "/eksport/"
JSON_FORMAT = "json"
HREF_RE = re.compile(r'href="([^"]*eksport/[^"]+)"', re.IGNORECASE)
NAME_FIELDS = ("navn", "id", "fornavn", "etternavn")


class StortingetSource(SourceBase):
    """Replaceable ingest adapter for Stortinget åpne data.

    Listing copies untemplated `/eksport/` hrefs the official technical
    documentation prints. It skips printed example URIs that include a
    query string (those examples name required parameters) and templated
    paths. Native ids are the printed last path segment so
    `stortingsperioder` and `sesjoner` stay distinct. Access URLs keep the
    printed path and the documented `format=json` parameter. This first
    slice stays inside that document and caps the walk.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (DOCS_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        docs_url: str = DOCS_URL,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.docs_url = docs_url
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(STORTINGET_RPS, STORTINGET_BURST),
            timeout=60.0,
        )
        self._listed: list[tuple[str, str]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._listed_paths()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for path, _href in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=printed_endpoint_url(path, self.docs_url),
                    source_native_id=printed_operation_id(path),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        path, href = _path_for_ref(self._listed_paths(), ref, self.docs_url)
        endpoint = printed_endpoint_url(path, self.docs_url)
        title = printed_operation_id(path)
        payload = {
            "id": title,
            "uri": endpoint,
            "title": {"no": title},
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.docs_url],
            "stortinget_docs_path": path,
            "stortinget_docs_href": href,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=ref.source_native_uri,
            fetched_from=self.docs_url,
            payload=payload,
        )

    def _listed_paths(self) -> list[tuple[str, str]]:
        if self._listed is not None:
            return self._listed
        try:
            page = self.http.get_text(self.docs_url)
        except Exception as exc:
            raise SourceError(
                f"Stortinget documentation list failed for {self.docs_url}: {exc}"
            ) from exc
        if not isinstance(page, str) or not page.strip():
            raise SourceError(f"Stortinget documentation is empty: {self.docs_url}")
        listed = printed_eksport_paths(page)
        if not listed:
            raise SourceError(
                f"Stortinget documentation printed no collection GET paths: {self.docs_url}"
            )
        self._listed = listed
        return listed


def printed_eksport_paths(page: str) -> list[tuple[str, str]]:
    """Copy untemplated collection `/eksport/` hrefs the documentation prints."""

    listed: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in HREF_RE.findall(page):
        href = html_lib.unescape(raw).strip()
        path = printed_path_from_href(href)
        if path is None or path in seen:
            continue
        seen.add(path)
        listed.append((path, href))
    return listed


def printed_path_from_href(href: str) -> str | None:
    if not href:
        return None
    parsed = urlsplit(href)
    path = parsed.path or ""
    if not path.startswith(PATH_PREFIX):
        return None
    if "{" in path or "}" in path:
        return None
    if parsed.query:
        return None
    ident = path[len(PATH_PREFIX) :].strip("/")
    if not ident or "/" in ident:
        return None
    return path


def printed_endpoint_url(path: str, docs_url: str) -> str:
    """Join a printed `/eksport/` path to the documentation origin.

    The official technical documentation prints that requests may include
    `format=JSON`. No other query filter is invented.
    """

    parts = urlsplit(docs_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Stortinget documentation URL has no printed origin")
    suffix = path if path.startswith("/") else f"/{path}"
    query = urlencode({"format": JSON_FORMAT})
    return urlunsplit((parts.scheme, parts.netloc, suffix, query, ""))


def printed_operation_id(path: str) -> str:
    ident = path.rstrip("/").split("/")[-1]
    if not ident:
        raise SourceError("Stortinget documentation path has no printed operation id")
    return ident


def is_stortinget_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def stortinget_table_id(access_path: str) -> str:
    path = urlsplit(access_path).path
    if path.startswith(PATH_PREFIX):
        ident = path[len(PATH_PREFIX) :].strip("/")
        if ident:
            return ident
    ident = path.rstrip("/").split("/")[-1]
    return ident or "stortinget"


def cells_from_stortinget(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Stortinget JSON records into observation cells.

    A printed overview object keeps each `*_liste` member. Each record
    keeps printed `navn` when present, otherwise `id`, `fornavn`, or
    `etternavn`. Other scalars stay as dimensions. Nested objects and
    arrays are not copied. Nothing is invented.
    """

    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(payload, dict):
        lists = [
            value
            for key, value in payload.items()
            if isinstance(value, list) and str(key).endswith("_liste")
        ]
        if not lists:
            lists = [value for value in payload.values() if isinstance(value, list)]
        if lists:
            for block in lists:
                for item in block:
                    if isinstance(item, dict):
                        cells.extend(_cells_from_record(item))
                    elif _is_scalar(item) and item is not None:
                        cells.append(("value", item, {"value": _as_dim(item)}))
        else:
            cells.extend(_cells_from_record(payload))
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
            elif _is_scalar(item) and item is not None:
                cells.append(("value", item, {"value": _as_dim(item)}))
    elif _is_scalar(payload) and payload is not None:
        cells.append(("value", payload, {"value": _as_dim(payload)}))
    else:
        raise ValueError("stortinget payload is not a JSON object, array, or scalar")
    if not cells:
        raise ValueError("stortinget payload printed no collection members")
    return cells


def _path_for_ref(
    listed: list[tuple[str, str]],
    ref: DatasetRef,
    docs_url: str,
) -> tuple[str, str]:
    for path, href in listed:
        if printed_endpoint_url(path, docs_url) == ref.source_native_uri:
            return path, href
        if printed_operation_id(path) == ref.source_native_id:
            return path, href
    raise SourceError(
        f"Stortinget documentation has no printed path matching {ref.source_native_uri}"
    )


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    measure = None
    value: Any = None
    for field in NAME_FIELDS:
        printed = scalars.get(field)
        if printed is None:
            continue
        if isinstance(printed, str) and not printed.strip():
            continue
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


PERIODER_PATH = "/eksport/stortingsperioder"
PERIODER_SCHEME = "stortinget:periode_id"
PERIODER_LIST_KEY = "stortingsperioder_liste"
_PERIODER_SKIP = {"respons_dato_tid", "versjon"}


def is_stortingsperioder_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.casefold() == HOST and parsed.path.rstrip("/") == PERIODER_PATH


def entity_from_periode(item: dict[str, Any]) -> dict[str, Any]:
    code = _period_id(item.get("id"))
    if not code:
        raise ValueError("Stortinget period printed no id")
    attributes: dict[str, Any] = {}
    for key, value in item.items():
        if key in _PERIODER_SKIP:
            continue
        if isinstance(value, (dict, list)) or value is None:
            continue
        if key == "id":
            attributes[key] = code
            continue
        attributes[key] = value
    return {
        "subject_scheme": PERIODER_SCHEME,
        "subject_code": code,
        "subject_label": code,
        "attributes": attributes,
    }


def periods_from_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("stortingsperioder payload is not a JSON object")
    listed = payload.get(PERIODER_LIST_KEY)
    if not isinstance(listed, list) or not listed:
        raise ValueError("stortingsperioder payload printed no periods")
    out = []
    for item in listed:
        if isinstance(item, dict):
            out.append(entity_from_periode(item))
    if not out:
        raise ValueError("stortingsperioder payload printed no period objects")
    return out


def shape_from_perioder(
    periods: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ids = [
        {"value_code": item["subject_code"], "value_label": item["subject_label"]}
        for item in periods
    ]
    fields = [
        {
            "field_code": "id",
            "field_label": "id",
            "field_role": "key",
            "values": ids,
        },
        {
            "field_code": "fra",
            "field_label": "fra",
            "field_role": "period",
            "values": [],
        },
        {
            "field_code": "til",
            "field_label": "til",
            "field_role": "period",
            "values": [],
        },
    ]
    keys = [
        {
            "scheme": PERIODER_SCHEME,
            "field_code": "id",
            "coverage_count": len(periods),
        }
    ]
    return fields, keys


def selected_periode_ids(select: dict[str, list[str]] | None) -> list[str] | None:
    if not select:
        return None
    unknown = sorted(key for key in select if key != "id")
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that a stortingsperioder fetch "
            "does not filter on; only id is accepted, or omit select for the full list"
        )
    wanted = select.get("id") or []
    wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
    if not wanted:
        raise ValueError("select id is empty")
    return wanted


def _period_id(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


# Remaining untemplated /eksport/ catalogs that were harvested as
# stortinget:* and still used the name-as-observation decoder. Each is a
# small complete list. Nested arrays (underemner, saksgang steps) are skipped.
LOOKUP_CATALOGS: dict[str, dict[str, str]] = {
    "/eksport/sesjoner": {
        "list_key": "sesjoner_liste",
        "scheme": "stortinget:sesjon_id",
        "label_field": "id",
        "series": "stortinget:sesjoner",
    },
    "/eksport/emner": {
        "list_key": "emne_liste",
        "scheme": "stortinget:emne_id",
        "label_field": "navn",
        "series": "stortinget:emner",
    },
    "/eksport/fylker": {
        "list_key": "fylker_liste",
        "scheme": "stortinget:fylke_id",
        "label_field": "navn",
        "series": "stortinget:fylker",
    },
    "/eksport/allepartier": {
        "list_key": "partier_liste",
        "scheme": "stortinget:parti_id",
        "label_field": "navn",
        "series": "stortinget:allepartier",
    },
    "/eksport/allekomiteer": {
        "list_key": "komiteer_liste",
        "scheme": "stortinget:komite_id",
        "label_field": "navn",
        "series": "stortinget:allekomiteer",
    },
    "/eksport/saksganger": {
        "list_key": "saksgang_liste",
        "scheme": "stortinget:saksgang_id",
        "label_field": "navn",
        "series": "stortinget:saksganger",
    },
}
_LOOKUP_SKIP = {"respons_dato_tid", "versjon"}


def is_stortinget_lookup_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.casefold() != HOST:
        return False
    return parsed.path.rstrip("/") in LOOKUP_CATALOGS


def lookup_catalog(access_path: str) -> dict[str, str]:
    parsed = urlsplit(access_path)
    spec = LOOKUP_CATALOGS.get(parsed.path.rstrip("/"))
    if spec is None:
        raise ValueError(f"not a Stortinget lookup catalog: {access_path}")
    return spec


def entity_from_lookup_item(item: dict[str, Any], spec: dict[str, str]) -> dict[str, Any]:
    code = _lookup_id(item.get("id"))
    if not code:
        raise ValueError(f"{spec['series']} member printed no id")
    label_field = spec["label_field"]
    raw = item.get(label_field)
    if label_field == "id":
        label = code
    elif isinstance(raw, str) and raw.strip():
        label = raw.strip()
    else:
        label = code
    attributes: dict[str, Any] = {}
    for key, value in item.items():
        if key in _LOOKUP_SKIP:
            continue
        if isinstance(value, (dict, list)) or value is None:
            continue
        if key == "id":
            attributes[key] = code
            continue
        attributes[key] = value
    return {
        "subject_scheme": spec["scheme"],
        "subject_code": code,
        "subject_label": label,
        "attributes": attributes,
    }


def lookups_from_payload(payload: Any, spec: dict[str, str]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError(f"{spec['series']} payload is not a JSON object")
    listed = payload.get(spec["list_key"])
    if not isinstance(listed, list) or not listed:
        raise ValueError(f"{spec['series']} payload printed no members")
    out = []
    for item in listed:
        if isinstance(item, dict):
            out.append(entity_from_lookup_item(item, spec))
    if not out:
        raise ValueError(f"{spec['series']} payload printed no member objects")
    return out


def shape_from_lookups(
    members: list[dict[str, Any]], spec: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ids = [
        {"value_code": item["subject_code"], "value_label": item["subject_label"]}
        for item in members
    ]
    fields = [
        {
            "field_code": "id",
            "field_label": "id",
            "field_role": "key",
            "values": ids,
        },
    ]
    if spec["label_field"] != "id":
        fields.append(
            {
                "field_code": spec["label_field"],
                "field_label": spec["label_field"],
                "field_role": "attribute",
                "values": [],
            }
        )
    keys = [
        {
            "scheme": spec["scheme"],
            "field_code": "id",
            "coverage_count": len(members),
        }
    ]
    return fields, keys


def selected_lookup_ids(select: dict[str, list[str]] | None) -> list[str] | None:
    if not select:
        return None
    unknown = sorted(key for key in select if key != "id")
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that a Stortinget lookup fetch "
            "does not filter on; only id is accepted, or omit select for the full list"
        )
    wanted = select.get("id") or []
    wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
    if not wanted:
        raise ValueError("select id is empty")
    return wanted


def _lookup_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None

