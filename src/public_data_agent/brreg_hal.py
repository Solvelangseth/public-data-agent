from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

BRREG_HOST = "data.brreg.no"
BRREG_PATH = "/enhetsregisteret/api"


def is_brreg_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlparse(access_path)
    return parsed.netloc.lower() == BRREG_HOST and parsed.path.startswith(BRREG_PATH)


def brreg_table_id(access_path: str) -> str:
    path = urlparse(access_path).path.rstrip("/")
    return path.rsplit("/", 1)[-1] or "brreg"


def cells_from_brreg(
    payload: Any,
    measure: str,
) -> list[tuple[str, Any, dict[str, str]]]:
    """Map a printed HAL `_embedded` record list to observation cells.

    Values are copied from the JSON. Nothing is invented.
    """

    items = _embedded_records(payload)
    if items is None:
        raise ValueError("brreg payload has no _embedded list of dicts")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        dims = {
            str(key): str(value)
            for key, value in item.items()
            if key != "_links" and isinstance(value, (str, int, float, bool))
        }
        value = _printed_value(item)
        if value is None:
            continue
        cells.append((measure, value, dims))
    return cells


def _embedded_records(payload: Any) -> list[Any] | None:
    if not isinstance(payload, dict):
        return None
    embedded = payload.get("_embedded")
    if not isinstance(embedded, dict):
        return None
    for value in embedded.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value
    return None


def _printed_value(record: dict[str, Any]) -> Any:
    for key in ("kode", "navn", "beskrivelse"):
        value = record.get(key)
        if isinstance(value, (str, int, float, bool)):
            return value
    for key, value in record.items():
        if key == "_links":
            continue
        if isinstance(value, (str, int, float, bool)):
            return value
    return None
