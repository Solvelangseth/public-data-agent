"""Current Stortinget members as one person register.

``stortinget:dagensrepresentanter`` is already harvested. The generic
Stortinget fetch stored each member's name as an observation. A representative
is a person: one register, addressed by the printed ``id`` (e.g. ``MARNIL``).
The published roster is 168 members; that is a complete current list, not a
bulk dump of parliamentary history.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

HOST = "data.stortinget.no"
PATH = "/eksport/dagensrepresentanter"
SUBJECT_SCHEME = "stortinget:representant_id"
LIST_KEY = "dagensrepresentanter_liste"


def is_dagensrepresentanter_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.casefold() == HOST and parsed.path.rstrip("/") == PATH


def representant_table_id(access_path: str) -> str:
    return "dagensrepresentanter"


def entity_from_representant(item: dict[str, Any]) -> dict[str, Any]:
    code = _string(item.get("id"))
    if not code:
        raise ValueError("Stortinget representative printed no id")
    fornavn = _string(item.get("fornavn")) or ""
    etternavn = _string(item.get("etternavn")) or ""
    label = f"{fornavn} {etternavn}".strip() or code
    attributes: dict[str, Any] = {}
    for key, value in item.items():
        if key in {"respons_dato_tid", "versjon"}:
            continue
        if isinstance(value, dict):
            nested_id = _string(value.get("id"))
            nested_navn = _string(value.get("navn"))
            if nested_id:
                attributes[f"{key}.id"] = nested_id
            if nested_navn:
                attributes[f"{key}.navn"] = nested_navn
            continue
        if isinstance(value, list):
            continue
        if value is None:
            continue
        attributes[key] = value
    return {
        "subject_scheme": SUBJECT_SCHEME,
        "subject_code": code,
        "subject_label": label,
        "attributes": attributes,
    }


def representanter_from_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("dagensrepresentanter payload is not a JSON object")
    listed = payload.get(LIST_KEY)
    if not isinstance(listed, list) or not listed:
        raise ValueError("dagensrepresentanter payload printed no members")
    out = []
    for item in listed:
        if isinstance(item, dict):
            out.append(entity_from_representant(item))
    if not out:
        raise ValueError("dagensrepresentanter payload printed no member objects")
    return out


def shape_from_representanter(
    members: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ids = [{"value_code": m["subject_code"], "value_label": m["subject_label"]} for m in members[:20]]
    fields = [
        {
            "field_code": "id",
            "field_label": "id",
            "field_role": "key",
            "values": ids,
        },
        {
            "field_code": "parti.id",
            "field_label": "parti",
            "field_role": "attribute",
            "values": [],
        },
        {
            "field_code": "fylke.id",
            "field_label": "fylke",
            "field_role": "attribute",
            "values": [],
        },
    ]
    keys = [
        {
            "scheme": SUBJECT_SCHEME,
            "field_code": "id",
            "coverage_count": len(members),
        }
    ]
    return fields, keys


def selected_ids(select: dict[str, list[str]] | None) -> list[str] | None:
    if not select:
        return None
    unknown = sorted(key for key in select if key != "id")
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that a dagensrepresentanter fetch "
            "does not filter on; only id is accepted, or omit select for the current roster"
        )
    wanted = select.get("id") or []
    wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
    if not wanted:
        raise ValueError("select id is empty")
    return wanted


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
