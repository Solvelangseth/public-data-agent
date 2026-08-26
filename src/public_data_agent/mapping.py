from __future__ import annotations

import hashlib
import json
from typing import Any

from public_data_agent.models import HarvestedRecord, NormalizedDataset

# Display preference only. All present languages stay in *_i18n.
TITLE_LANG_ORDER = ("no", "nb", "nn", "en")


def map_harvested_record(record: HarvestedRecord) -> NormalizedDataset:
    """Deterministic projection. Never invents values that the payload lacks."""

    payload = record.payload
    title_i18n = localized_text(payload.get("title"))
    description_i18n = localized_text(payload.get("description"))
    publisher = _publisher(payload.get("publisher"))
    licenses = _licenses(payload)
    distributions = _distributions(payload.get("distribution"))
    landing_pages = string_list(payload.get("landingPage"))
    access_path = _access_path(distributions, landing_pages)
    temporal = _temporal(payload.get("temporal"))
    spatial = _spatial(payload.get("spatial"))
    media_types, formats = _formats(payload.get("distribution"))
    conforms_to = unique_strings(
        _conforms_to_values(payload.get("conformsTo"))
        + [uri for dist in distributions for uri in dist.get("conforms_to", [])]
    )
    access_rights, access_rights_uri = _access_rights(payload.get("accessRights"))
    harvest = payload.get("harvest") if isinstance(payload.get("harvest"), dict) else {}
    harvest_modified = harvest.get("modified") if isinstance(harvest.get("modified"), str) else None

    native_id = record.source_native_id or (payload.get("id") if isinstance(payload.get("id"), str) else None)
    native_uri = record.source_native_uri or (
        payload.get("uri") if isinstance(payload.get("uri"), str) else None
    )
    dataset_id = stable_id(record.source_id, native_id, native_uri)

    missing: dict[str, str] = {}
    if publisher is None:
        missing["publisher"] = "absent from Resource Service dataset JSON"
    if not licenses:
        missing["license"] = (
            "absent from Resource Service dataset JSON "
            "(no dataset-level license and no distribution license URI)"
        )
    if access_path is None:
        missing["access_path"] = (
            "absent from Resource Service dataset JSON "
            "(no distribution downloadURL/accessURL and no landingPage)"
        )
    if not record.source_name or not record.source_endpoints:
        missing["original_source"] = "source adapter did not provide a name and endpoints"
    if not title_i18n:
        missing["title"] = "absent from Resource Service dataset JSON"
    if not description_i18n:
        missing["description"] = "absent from Resource Service dataset JSON"
    if payload.get("issued") in (None, ""):
        missing["issued"] = "absent from Resource Service dataset JSON"
    if payload.get("modified") in (None, ""):
        missing["modified"] = "absent from Resource Service dataset JSON"
    if not temporal:
        missing["temporal"] = "absent from Resource Service dataset JSON"
    if not spatial:
        missing["spatial"] = "absent from Resource Service dataset JSON"
    if not media_types and not formats:
        missing["structure"] = "absent from Resource Service dataset JSON (no distribution fdkFormat)"

    return NormalizedDataset(
        id=dataset_id,
        source_id=record.source_id,
        source_native_id=native_id,
        source_native_uri=native_uri,
        title=preferred_text(title_i18n),
        title_i18n=title_i18n,
        description=preferred_text(description_i18n),
        description_i18n=description_i18n,
        publisher_id=publisher.get("id") if publisher else None,
        publisher_name=publisher.get("name") if publisher else None,
        publisher_uri=publisher.get("uri") if publisher else None,
        publisher=publisher,
        license=licenses[0] if licenses else None,
        licenses=licenses,
        access_path=access_path,
        access_rights=access_rights,
        access_rights_uri=access_rights_uri,
        issued=_scalar_str(payload.get("issued")),
        modified=_scalar_str(payload.get("modified")),
        temporal_start=temporal[0].get("start") if temporal else None,
        temporal_end=temporal[0].get("end") if temporal else None,
        temporal=temporal,
        spatial=spatial,
        media_types=media_types,
        formats=formats,
        conforms_to=conforms_to,
        distributions=distributions,
        landing_pages=landing_pages,
        ingest_reason=record.ingest_reason,
        source_name=record.source_name,
        source_endpoints=record.source_endpoints,
        missing_fields=missing,
        payload_hash=payload_hash(payload),
        source_catalog_modified=record.catalog_modified,
        source_harvest_modified=harvest_modified,
        fetched_from=record.fetched_from,
        payload=payload,
    )


def stable_id(source_id: str, native_id: str | None, native_uri: str | None) -> str:
    if native_id:
        return f"{source_id}:{native_id}"
    if native_uri:
        digest = hashlib.sha256(native_uri.encode("utf-8")).hexdigest()[:20]
        return f"{source_id}:uri:{digest}"
    raise ValueError("cannot assign a stable id without a native id or URI")


def payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def localized_text(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, str) and value.strip():
        return {"und": value}
    if isinstance(value, dict):
        out: dict[str, str] = {}
        for lang, text in value.items():
            if isinstance(text, str) and text.strip():
                out[str(lang)] = text
        return out
    return {}


def preferred_text(i18n: dict[str, str]) -> str | None:
    for lang in TITLE_LANG_ORDER:
        if lang in i18n:
            return i18n[lang]
    if not i18n:
        return None
    return next(iter(i18n.values()))


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str) and value.strip():
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    return []


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _scalar_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _publisher(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    name_i18n = localized_text(value.get("title")) or localized_text(value.get("prefLabel"))
    name = _scalar_str(value.get("name")) or preferred_text(name_i18n)
    publisher_id = _scalar_str(value.get("id"))
    uri = _scalar_str(value.get("uri"))
    if not any((name, publisher_id, uri)):
        return None
    return {
        "id": publisher_id,
        "name": name,
        "uri": uri,
        "title": name_i18n,
    }


def _licenses(payload: dict[str, Any]) -> list[str]:
    uris: list[str] = []
    uris.extend(_license_uris(payload.get("license")))
    distributions = payload.get("distribution")
    if isinstance(distributions, list):
        for dist in distributions:
            if isinstance(dist, dict):
                uris.extend(_license_uris(dist.get("license")))
    return unique_strings(uris)


def _license_uris(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str) and value.strip():
        return [value]
    if isinstance(value, dict):
        uri = _scalar_str(value.get("uri"))
        return [uri] if uri else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_license_uris(item))
        return out
    return []


def _distributions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        media_types, formats = _format_lists(item.get("fdkFormat"))
        access_urls = string_list(item.get("accessURL"))
        download_urls = string_list(item.get("downloadURL"))
        out.append(
            {
                "uri": _scalar_str(item.get("uri")),
                "title": localized_text(item.get("title")),
                "access_url": download_urls[0] if download_urls else (access_urls[0] if access_urls else None),
                "access_urls": access_urls,
                "download_urls": download_urls,
                "formats": formats,
                "media_types": media_types,
                "license_uris": _license_uris(item.get("license")),
                "conforms_to": _conforms_to_values(item.get("conformsTo")),
            }
        )
    return out


def _access_path(distributions: list[dict[str, Any]], landing_pages: list[str]) -> str | None:
    for dist in distributions:
        if dist.get("download_urls"):
            return dist["download_urls"][0]
        if dist.get("access_urls"):
            return dist["access_urls"][0]
    if landing_pages:
        return landing_pages[0]
    return None


def _temporal(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        start = _scalar_str(item.get("startDate"))
        end = _scalar_str(item.get("endDate"))
        uri = _scalar_str(item.get("uri"))
        if not any((start, end, uri)):
            continue
        out.append({"start": start, "end": end, "uri": uri})
    return out


def _spatial(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            out.append({"uri": item, "code": None, "pref_label": {}})
            continue
        if not isinstance(item, dict):
            continue
        uri = _scalar_str(item.get("uri"))
        code = _scalar_str(item.get("code"))
        pref_label = localized_text(item.get("prefLabel"))
        if not any((uri, code, pref_label)):
            continue
        out.append({"uri": uri, "code": code, "pref_label": pref_label})
    return out


def _formats(value: Any) -> tuple[list[str], list[str]]:
    media: list[str] = []
    formats: list[str] = []
    if not isinstance(value, list):
        return [], []
    for item in value:
        if isinstance(item, dict):
            m, f = _format_lists(item.get("fdkFormat"))
            media.extend(m)
            formats.extend(f)
    return unique_strings(media), unique_strings(formats)


def _format_lists(value: Any) -> tuple[list[str], list[str]]:
    if not isinstance(value, list):
        return [], []
    media: list[str] = []
    formats: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        code = _scalar_str(item.get("code"))
        name = _scalar_str(item.get("name"))
        kind = _scalar_str(item.get("type"))
        label = code or name
        if not label:
            continue
        if kind == "MEDIA_TYPE":
            media.append(label)
        else:
            formats.append(label)
    return media, formats


def _conforms_to_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str) and value.strip():
        return [value]
    if isinstance(value, dict):
        uri = _scalar_str(value.get("uri"))
        return [uri] if uri else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_conforms_to_values(item))
        return out
    return []


def _access_rights(value: Any) -> tuple[str | None, str | None]:
    if isinstance(value, str) and value.strip():
        return value, value
    if not isinstance(value, dict):
        return None, None
    uri = _scalar_str(value.get("uri"))
    code = _scalar_str(value.get("code"))
    label = preferred_text(localized_text(value.get("prefLabel")))
    return label or code, uri
