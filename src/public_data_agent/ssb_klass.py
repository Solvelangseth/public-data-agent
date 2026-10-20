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


def klass_table_id(payload: dict[str, Any], access_path: str) -> str:
    version = payload.get("id")
    if version is not None:
        return f"klass:{version}"
    path = urlparse(access_path).path.rstrip("/").split("/")[-1]
    return path or "klass"


def records_from_klass(payload: dict[str, Any], dataset_id: str) -> list[dict[str, Any]]:
    """Map SSB Klass classificationItems to entity records.

    A classification item is a code and the name that code stands for --
    `030101` is `Gamle Oslo`. Stored as an observation cell that reads as a
    measurement of `Bydelsinndeling 2020` whose value happens to be a word, and
    7,127 occupation titles then count as published statistics. Stored as a
    record the code becomes `subject_code`, which is what every join actually
    looks it up by, and `kind` says plainly that this is a named thing.

    The level and the parent code stay in `attributes`: they describe where the
    item sits in the hierarchy, not what it is.
    """

    classification = str(payload.get("name") or "classification")
    items = payload.get("classificationItems")
    if not isinstance(items, list):
        raise ValueError("klass payload has no classificationItems list")
    scheme = klass_table_id(payload, "")
    records: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        name = item.get("name")
        if code is None or name is None:
            continue
        attributes = {"classification": classification, "level": str(item.get("level") or "")}
        parent = item.get("parentCode")
        if parent:
            attributes["parentCode"] = str(parent)
        for field in ("shortName", "notes", "validFrom", "validTo"):
            value = item.get(field)
            if value:
                attributes[field] = str(value)
        records.append(
            {
                "id": f"entity:{dataset_id}:{scheme}:{code}",
                "kind": "entity",
                "subject_scheme": scheme,
                "subject_code": str(code),
                "subject_label": str(name),
                "attributes": attributes,
            }
        )
    return records
