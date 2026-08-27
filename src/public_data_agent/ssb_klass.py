from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

KLASS_HOST = "data.ssb.no"
KLASS_PATH = "/api/klass/"


def is_klass_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlparse(access_path)
    return parsed.netloc == KLASS_HOST and parsed.path.startswith(KLASS_PATH)


def cells_from_klass(payload: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    """Map SSB Klass classificationItems to observation cells.

    Values are copied from the JSON. Nothing is invented.
    """

    measure = str(payload.get("name") or "classification")
    items = payload.get("classificationItems")
    if not isinstance(items, list):
        raise ValueError("klass payload has no classificationItems list")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        name = item.get("name")
        if code is None or name is None:
            continue
        dims = {"code": str(code), "level": str(item.get("level") or "")}
        parent = item.get("parentCode")
        if parent:
            dims["parentCode"] = str(parent)
        cells.append((measure, name, dims))
    return cells


def klass_table_id(payload: dict[str, Any], access_path: str) -> str:
    version = payload.get("id")
    if version is not None:
        return f"klass:{version}"
    path = urlparse(access_path).path.rstrip("/").split("/")[-1]
    return path or "klass"
