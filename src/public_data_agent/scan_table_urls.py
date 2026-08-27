from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from public_data_agent.models import HarvestCounts
from public_data_agent.registry import Registry, utc_now

URL_RE = re.compile(r"https?://[^\s\"'\\<>]+", re.I)
SSB_TABLE_RE = re.compile(
    r"^https?://data\.ssb\.no/api/v0/(?:no|en|nn)/table/\d+$",
    re.I,
)
PXWEB_API_TABLE_RE = re.compile(
    r"^https?://[^/]+/statbank/api/v1/.+\.px$",
    re.I,
)
PXWEB_UI_TABLE_RE = re.compile(
    r"^https?://[^/]+/statbank/pxweb/.+\.px$",
    re.I,
)
KLASS_MARK = "/api/klass/"


@dataclass(frozen=True)
class PrintedTableUrl:
    dataset_id: str
    url: str
    kind: str
    found_in: str
    already_access_path: bool


@dataclass
class ScanResult:
    counts: HarvestCounts = field(default_factory=HarvestCounts)
    printed: list[PrintedTableUrl] = field(default_factory=list)
    new_urls: list[PrintedTableUrl] = field(default_factory=list)
    already_access_path: list[PrintedTableUrl] = field(default_factory=list)
    klass_skipped: int = 0
    payloads_scanned: int = 0
    datasets_scanned: int = 0
    probes: list[dict[str, Any]] = field(default_factory=list)


def classify_table_url(url: str) -> str | None:
    cleaned = url.rstrip(").,;]}>")
    if KLASS_MARK in cleaned.lower():
        return None
    if SSB_TABLE_RE.match(cleaned):
        return "ssb_pxweb_table"
    if PXWEB_API_TABLE_RE.match(cleaned):
        return "pxweb_api_table"
    if PXWEB_UI_TABLE_RE.match(cleaned):
        return "pxweb_ui_table"
    return None


def urls_in_text(text: str) -> list[str]:
    found: list[str] = []
    for match in URL_RE.findall(text or ""):
        found.append(match.rstrip(").,;]}>"))
    return found


def walk_strings(obj: Any, out: list[str]) -> None:
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            walk_strings(value, out)
    elif isinstance(obj, list):
        for value in obj:
            walk_strings(value, out)


def extract_printed_table_urls(
    *,
    dataset_id: str,
    access_path: str | None,
    payload_json: str | None,
    distributions_json: str | None,
    landing_pages_json: str | None,
) -> tuple[list[PrintedTableUrl], int]:
    """Copy table URLs already printed in harvest text. Do not construct ids."""

    access = (access_path or "").rstrip("/")
    klass_skipped = 0
    printed: list[PrintedTableUrl] = []
    seen: set[str] = set()
    sources = (
        ("payload", payload_json),
        ("distributions_json", distributions_json),
        ("landing_pages_json", landing_pages_json),
    )
    for found_in, blob in sources:
        if not blob:
            continue
        strings: list[str] = []
        if found_in == "payload":
            try:
                walk_strings(json.loads(blob), strings)
            except json.JSONDecodeError:
                strings = [blob]
        else:
            try:
                walk_strings(json.loads(blob), strings)
            except json.JSONDecodeError:
                strings = [blob]
        for text in strings:
            for raw in urls_in_text(text):
                if KLASS_MARK in raw.lower():
                    klass_skipped += 1
                    continue
                kind = classify_table_url(raw)
                if kind is None:
                    continue
                if raw in seen:
                    continue
                seen.add(raw)
                printed.append(
                    PrintedTableUrl(
                        dataset_id=dataset_id,
                        url=raw,
                        kind=kind,
                        found_in=found_in,
                        already_access_path=raw.rstrip("/") == access,
                    )
                )
    return printed, klass_skipped


def scan_printed_table_urls(
    registry: Registry,
    *,
    probe: bool = False,
    probe_limit: int = 20,
) -> ScanResult:
    result = ScanResult()
    rows = registry.conn.execute(
        """
        SELECT d.id, d.access_path, d.distributions_json, d.landing_pages_json,
               p.payload_json
        FROM datasets d
        LEFT JOIN harvested_payloads p ON p.dataset_id = d.id
        """
    ).fetchall()
    result.datasets_scanned = len(rows)
    harvest_before = _payload_fingerprint(registry)
    for row in rows:
        if row["payload_json"] is not None:
            result.payloads_scanned += 1
        printed, skipped = extract_printed_table_urls(
            dataset_id=row["id"],
            access_path=row["access_path"],
            payload_json=row["payload_json"],
            distributions_json=row["distributions_json"],
            landing_pages_json=row["landing_pages_json"],
        )
        result.klass_skipped += skipped
        result.counts.listed += len(printed)
        for item in printed:
            result.printed.append(item)
            if item.already_access_path:
                result.already_access_path.append(item)
                continue
            result.new_urls.append(item)
            action = registry.upsert_printed_table_url(
                dataset_id=item.dataset_id,
                url=item.url,
                kind=item.kind,
                found_in=item.found_in,
            )
            if action == "inserted":
                result.counts.inserted += 1
            elif action == "updated":
                result.counts.updated += 1
            else:
                result.counts.unchanged += 1
    if _payload_fingerprint(registry) != harvest_before:
        raise RuntimeError("scan wrote harvested_payloads")
    if probe:
        result.probes = _probe_urls([item.url for item in result.new_urls[:probe_limit]])
    return result


def scan_proof_payload(
    result: ScanResult,
    *,
    command: str,
    db: str,
) -> dict[str, Any]:
    return {
        "command": command,
        "db": db,
        "datasets_scanned": result.datasets_scanned,
        "payloads_scanned": result.payloads_scanned,
        "printed_table_urls": result.counts.listed,
        "new_stored": len(result.new_urls),
        "already_access_path": len(result.already_access_path),
        "inserted": result.counts.inserted,
        "updated": result.counts.updated,
        "unchanged": result.counts.unchanged,
        "klass_skipped": result.klass_skipped,
        "constructed_07459": False,
        "sample_printed_urls": [
            {
                "dataset_id": item.dataset_id,
                "url": item.url,
                "kind": item.kind,
                "found_in": item.found_in,
                "already_access_path": item.already_access_path,
            }
            for item in (result.new_urls or result.printed)[:10]
        ],
        "probes": result.probes,
        "get_200_json": sum(1 for item in result.probes if item.get("ok_json")),
        "sit": len(result.new_urls) == 0,
    }


def _probe_urls(urls: list[str]) -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            probes.append({"url": url, "error": "not http", "ok_json": False})
            continue
        req = Request(url, method="GET", headers={"User-Agent": "pda-table-url-scan/1"})
        try:
            with urlopen(req, timeout=20) as response:
                content_type = response.headers.get("Content-Type") or ""
                status = int(response.status)
                probes.append(
                    {
                        "url": url,
                        "http_status": status,
                        "content_type": content_type,
                        "ok_json": status == 200
                        and (
                            "json" in content_type.lower()
                            or "json-stat" in content_type.lower()
                        ),
                    }
                )
        except Exception as exc:
            probes.append(
                {
                    "url": url,
                    "error": f"{type(exc).__name__}: {exc}",
                    "ok_json": False,
                }
            )
    return probes


def _payload_fingerprint(registry: Registry) -> list[tuple[str, str]]:
    rows = registry.conn.execute(
        "SELECT dataset_id, payload_json FROM harvested_payloads ORDER BY dataset_id"
    ).fetchall()
    return [(row["dataset_id"], row["payload_json"]) for row in rows]
