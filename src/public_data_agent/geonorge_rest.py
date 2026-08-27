from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

GEONORGE_REST_HOSTS = frozenset({"ws.geonorge.no", "api.kartverket.no"})
PREFERRED_COLLECTION = "/kommuner"


def is_geonorge_rest_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlparse(access_path)
    return parsed.netloc.lower() in GEONORGE_REST_HOSTS


def api_root(access_path: str) -> str:
    return access_path if access_path.endswith("/") else f"{access_path}/"


def openapi_url(access_path: str) -> str:
    return urljoin(api_root(access_path), "openapi.json")


def printed_collection_paths(spec: dict[str, Any]) -> list[str]:
    """Copy GET collection paths the OpenAPI document printed.

    Path-parameter routes and GET operations with a required query/path
    parameter are skipped. Nothing is invented.
    """

    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("openapi document has no paths object")
    out: list[str] = []
    for path, ops in paths.items():
        if not isinstance(path, str) or "{" in path:
            continue
        if not isinstance(ops, dict) or "get" not in ops:
            continue
        get_op = ops.get("get")
        params = []
        if isinstance(get_op, dict):
            raw = get_op.get("parameters")
            if isinstance(raw, list):
                params.extend(raw)
        raw = ops.get("parameters")
        if isinstance(raw, list):
            params.extend(raw)
        if any(isinstance(param, dict) and param.get("required") is True for param in params):
            continue
        out.append(path)
    return out


def pick_collection_path(spec: dict[str, Any]) -> str:
    printed = printed_collection_paths(spec)
    if not printed:
        raise ValueError("openapi printed no parameter-free GET collection")
    if PREFERRED_COLLECTION in printed:
        return PREFERRED_COLLECTION
    return printed[0]


def collection_request_url(access_path: str, spec: dict[str, Any]) -> str:
    rel = pick_collection_path(spec).lstrip("/")
    return urljoin(api_root(access_path), rel)


def geonorge_table_id(request_url: str) -> str:
    path = urlparse(request_url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] or "geonorge"


def cells_from_geonorge(
    payload: Any,
    *,
    measure: str,
) -> list[tuple[str, Any, dict[str, str]]]:
    """Map a printed JSON/GeoJSON record list to observation cells.

    Values are copied from the JSON. Nothing is invented.
    """

    items = _record_items(payload)
    if items is None:
        raise ValueError("geonorge payload has no record list")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in items:
        record = _record_dict(item)
        if record is None:
            continue
        dims = {
            str(key): str(value)
            for key, value in record.items()
            if isinstance(value, (str, int, float, bool))
        }
        value = _printed_value(record)
        if value is None:
            continue
        cells.append((measure, value, dims))
    return cells


def _record_items(payload: Any) -> list[Any] | None:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    if payload.get("type") == "FeatureCollection" and isinstance(payload.get("features"), list):
        return payload["features"]
    for value in payload.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value
    if _looks_like_record(payload):
        return [payload]
    return None


def _record_dict(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    if item.get("type") == "Feature" and isinstance(item.get("properties"), dict):
        return item["properties"]
    return item


def _looks_like_record(payload: dict[str, Any]) -> bool:
    return any(isinstance(value, (str, int, float, bool)) for value in payload.values())


def _printed_value(record: dict[str, Any]) -> Any:
    for key in (
        "kommunenavn",
        "kommunenavnNorsk",
        "fylkesnavn",
        "navn",
        "name",
        "kommunenummer",
        "fylkesnummer",
    ):
        value = record.get(key)
        if isinstance(value, (str, int, float, bool)):
            return value
    for value in record.values():
        if isinstance(value, (str, int, float, bool)):
            return value
    return None
