from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "nbr"
SOURCE_NAME = "Utdanningsdirektoratet Nasjonalt barnehageregister"
OPENAPI_URL = "https://data-nbr.udir.no/swagger/v3/swagger.json"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a collection GET path in the official Nasjonalt barnehageregister "
    f"OpenAPI, capped at {DEFAULT_MAX_ITEMS} paths"
)
NBR_RPS = 2.0
NBR_BURST = 4
HOST = "data-nbr.udir.no"


class NbrSource(SourceBase):
    """Replaceable ingest adapter for Udir Nasjonalt barnehageregister.

    Listing copies collection GET paths the official OpenAPI document prints.
    It skips templated paths and does not invent endpoint ids. This first
    slice stays inside that document and caps the walk.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (OPENAPI_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        openapi_url: str = OPENAPI_URL,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.openapi_url = openapi_url
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(NBR_RPS, NBR_BURST),
            timeout=60.0,
        )
        self._spec: dict[str, Any] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = _listed_get_paths(self._openapi())
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for path, _item in sliced:
            endpoint = printed_endpoint_url(self._openapi(), path, self.openapi_url)
            refs.append(
                DatasetRef(
                    source_native_uri=endpoint,
                    source_native_id=printed_operation_id(path),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        spec = self._openapi()
        path = _path_for_ref(spec, ref)
        item = (spec.get("paths") or {}).get(path)
        if not isinstance(item, dict):
            raise SourceError(f"NBR OpenAPI has no printed path for {ref.source_native_uri}")
        operation = item.get("get") if isinstance(item.get("get"), dict) else {}
        summary = operation.get("summary")
        title = (
            summary
            if isinstance(summary, str) and summary.strip()
            else (ref.source_native_id or printed_operation_id(path))
        )
        info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
        info_description = info.get("description")
        payload = {
            "id": ref.source_native_id,
            "uri": ref.source_native_uri,
            "title": {"no": title},
            "description": (
                {"no": info_description} if isinstance(info_description, str) else None
            ),
            "publisher": None,
            "license": printed_license_url(info),
            "distribution": [
                {
                    "accessURL": [ref.source_native_uri],
                    "downloadURL": [ref.source_native_uri],
                }
            ],
            "landingPage": [self.openapi_url],
            "nbr_openapi_path": path,
            "nbr_openapi_operation": item,
            "nbr_openapi_info": info,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=ref.source_native_uri,
            fetched_from=self.openapi_url,
            payload=payload,
        )

    def _openapi(self) -> dict[str, Any]:
        if self._spec is not None:
            return self._spec
        try:
            spec = self.http.get_json(self.openapi_url)
        except Exception as exc:
            raise SourceError(f"NBR OpenAPI list failed for {self.openapi_url}: {exc}") from exc
        if not isinstance(spec, dict):
            raise SourceError(f"NBR OpenAPI is not a JSON object: {self.openapi_url}")
        self._spec = spec
        return spec


def printed_license_url(info: dict[str, Any]) -> str | None:
    license_info = info.get("license")
    if not isinstance(license_info, dict):
        return None
    url = license_info.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def printed_operation_id(path: str) -> str:
    segment = path.rstrip("/").split("/")[-1]
    if not segment:
        raise SourceError("NBR OpenAPI path has no printed operation id")
    return segment


def printed_endpoint_url(spec: dict[str, Any], path: str, openapi_url: str) -> str:
    """Join a printed path to a printed server or the OpenAPI document origin.

    The live NBR spec has no `servers` array. Joining the path onto the
    swagger.json directory 404s. The host that printed the spec is used
    instead. No table id is invented.
    """

    servers = spec.get("servers") if isinstance(spec.get("servers"), list) else []
    if servers and isinstance(servers[0], dict) and isinstance(servers[0].get("url"), str):
        server = servers[0]["url"].strip()
        if server.startswith("http://") or server.startswith("https://"):
            base = server if server.endswith("/") else f"{server}/"
            return urljoin(base, path.lstrip("/"))
    parts = urlsplit(openapi_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("NBR OpenAPI URL has no printed origin")
    origin = f"{parts.scheme}://{parts.netloc}"
    suffix = path if path.startswith("/") else f"/{path}"
    return origin + suffix


def is_nbr_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    return urlsplit(access_path).netloc.lower() == HOST


def nbr_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "nbr"


def cells_from_nbr(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed NBR JSON records into observation cells.

    Collection arrays keep printed `Navn` when present. Other scalars stay
    as dimensions. Nothing is invented.
    """

    if not isinstance(payload, list):
        raise ValueError("nbr payload is not a JSON array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        cells.extend(_cells_from_record(item))
    return cells


def _listed_get_paths(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise SourceError("NBR OpenAPI has no printed paths object")
    listed: list[tuple[str, dict[str, Any]]] = []
    for path, item in paths.items():
        if not isinstance(path, str) or not isinstance(item, dict):
            continue
        if "{" in path:
            continue
        if not isinstance(item.get("get"), dict):
            continue
        listed.append((path, item))
    return listed


def _path_for_ref(spec: dict[str, Any], ref: DatasetRef) -> str:
    for path, _item in _listed_get_paths(spec):
        if printed_endpoint_url(spec, path, OPENAPI_URL) == ref.source_native_uri:
            return path
        if printed_operation_id(path) == ref.source_native_id:
            return path
    raise SourceError(f"NBR OpenAPI has no printed path matching {ref.source_native_uri}")


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    if "Navn" in scalars:
        measure = "Navn"
        value = scalars["Navn"]
    elif "Kode" in scalars:
        measure = "Kode"
        value = scalars["Kode"]
    else:
        measure, value = next(iter(scalars.items()))
    dims = {key: _as_dim(other) for key, other in scalars.items() if key != measure}
    return [(measure, value, dims)]


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


# Small complete NBR catalogs. `enheter` stays on the observation decoder
# until it gets a bounded entity fetch. Members with an empty printed id
# (maalformer "Udefinert") are skipped, not stored as a blank key.
LOOKUP_CATALOGS: dict[str, dict[str, str]] = {
    "barnehagekategorier": {
        "code_field": "Id",
        "label_field": "Navn",
        "scheme": "nbr:barnehagekategori",
    },
    "maalformer": {
        "code_field": "Id",
        "label_field": "Navn",
        "scheme": "nbr:maalform",
    },
    "naeringskoder": {
        "code_field": "Kode",
        "label_field": "Navn",
        "scheme": "nbr:naeringskode",
    },
    "organisasjonsformer": {
        "code_field": "Id",
        "label_field": "Navn",
        "scheme": "nbr:organisasjonsform",
    },
    "utgaattyper": {
        "code_field": "Id",
        "label_field": "Navn",
        "scheme": "nbr:utgaattype",
    },
    "relasjonstyper": {
        "code_field": "Id",
        "label_field": "Navn",
        "scheme": "nbr:relasjonstype",
    },
}


def is_nbr_lookup_url(access_path: str | None) -> bool:
    if not is_nbr_url(access_path):
        return False
    return nbr_table_id(access_path or "") in LOOKUP_CATALOGS


def lookup_catalog(access_path: str) -> dict[str, str]:
    ident = nbr_table_id(access_path)
    spec = LOOKUP_CATALOGS.get(ident)
    if spec is None:
        raise ValueError(f"not an NBR lookup catalog: {access_path}")
    return spec


def entity_from_nbr_item(item: dict[str, Any], spec: dict[str, str]) -> dict[str, Any]:
    code = _lookup_id(item.get(spec["code_field"]))
    if not code:
        raise ValueError(f"NBR {spec['scheme']} member printed no {spec['code_field']}")
    raw = item.get(spec["label_field"])
    label = raw.strip() if isinstance(raw, str) and raw.strip() else code
    attributes: dict[str, Any] = {}
    for key, value in item.items():
        if isinstance(value, (dict, list)) or value is None:
            continue
        if key == spec["code_field"]:
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
    if not isinstance(payload, list):
        raise ValueError("nbr lookup payload is not a JSON array")
    out = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if not _lookup_id(item.get(spec["code_field"])):
            continue
        out.append(entity_from_nbr_item(item, spec))
    if not out:
        raise ValueError("nbr lookup payload printed no members with an id")
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
            "field_code": spec["code_field"],
            "field_label": spec["code_field"],
            "field_role": "key",
            "values": ids,
        },
        {
            "field_code": spec["label_field"],
            "field_label": spec["label_field"],
            "field_role": "attribute",
            "values": [],
        },
    ]
    keys = [
        {
            "scheme": spec["scheme"],
            "field_code": spec["code_field"],
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
            f"select names field(s) {unknown} that an NBR lookup fetch "
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

