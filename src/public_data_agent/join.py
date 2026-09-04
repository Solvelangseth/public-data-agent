from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from public_data_agent.fetch import JsonHttp, _store_cells, fetch_observations
from public_data_agent.models import HarvestCounts
from public_data_agent.registry import Registry, utc_now
from public_data_agent.fhi_stat import fetch_fhi_table_coded, parse_fhi_table_ref
from public_data_agent.ssb_pxweb import (
    DEFAULT_SSB_TABLE,
    DEFAULT_SSB_TABLE_URL,
    SsbTableResult,
    fetch_ssb_table,
)

DEFAULT_KLASS_DATASET = "datanorge:0c89041e-ae88-32ef-a765-8e1ccbd64fdd"
JOIN_KEY = "bydel_code"
# The join stores an "I alt" per-bydel projection whose dimension names differ
# from a raw 11763 fetch; the tag keeps the two apart in the observation store.
JOIN_SERIES = "join:bydel_population"
SSB_PUBLISHER = "Statistisk sentralbyrå"
FHI_API_ROOT = "https://statistikk-data.fhi.no/api/open/v1"

WHY_NOT_M7_M8 = (
    "OK-BEF008 is Oslo city totals with no bydel or kommune code. "
    "Klass 1168 is classification names keyed by 0301xx. "
    "Those two do not share a key to a metric."
)
WHY_NOT_07459 = (
    "07459 is live at data.ssb.no/api/v0/no/table/07459 and has kommune 0301, "
    "but it is still not an access_path in the registry and it has no bydel codes. "
    "Joining one Oslo total onto 42 bydels is the same glue the milestone forbids."
)
WHY_11763 = (
    "Table 11763 is a public no-auth SSB PxWeb befolkning/bydel table. "
    "Its Region codes 030101-030117 and 030199 are the same strings Klass 1168 stores. "
    "07459 and 11763 are both absent from stored access_path values."
)


@dataclass
class JoinResult:
    join_key: str
    left_dataset_id: str
    right_dataset_id: str
    left_request_url: str
    right_request_url: str
    left_http_status: int
    right_http_status: int
    right_title: str | None = None
    right_publisher: str | None = None
    counts: HarvestCounts = field(default_factory=HarvestCounts)
    sample: list[dict[str, Any]] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)


def join_bydel_population(
    registry: Registry,
    *,
    klass_dataset_id: str = DEFAULT_KLASS_DATASET,
    ssb_table: str = DEFAULT_SSB_TABLE,
    year: int | None = 2025,
    http: JsonHttp | None = None,
) -> JoinResult:
    """Inner-join Klass bydel codes to SSB 11763 population on the exact code.

    This is the Oslo-shaped entry point kept for the demo and the CLI. It is a
    thin call into :func:`join_classification_to_table`, which does the same
    thing for any Klass classification and any SSB table.
    """

    return join_classification_to_table(
        registry,
        klass_dataset_id=klass_dataset_id,
        ssb_table=ssb_table,
        year=year,
        http=http,
        join_key=JOIN_KEY,
        series=JOIN_SERIES,
    )


def join_classification_to_table(
    registry: Registry,
    *,
    klass_dataset_id: str = DEFAULT_KLASS_DATASET,
    ssb_table: str = DEFAULT_SSB_TABLE,
    year: int | None = 2025,
    http: JsonHttp | None = None,
    join_key: str = JOIN_KEY,
    series: str = JOIN_SERIES,
) -> JoinResult:
    """Inner-join any SSB Klass code list to any SSB PxWeb table on exact codes.

    The key is discovered, not assumed: the classification's stored codes are
    matched against the table's stored dimension values, and only exact string
    equality counts. If no dimension overlaps, the two genuinely do not share a
    key and the join refuses rather than inventing glue.
    """

    klass_dataset = registry.get_dataset(klass_dataset_id)
    if klass_dataset is None:
        raise ValueError(f"unknown dataset {klass_dataset_id}")
    fhi_ref = parse_fhi_table_ref(ssb_table)
    right_dataset_id = f"fhi:{ssb_table.split(':', 1)[1]}" if fhi_ref else f"ssb:{ssb_table}"
    started = utc_now()
    run_id = registry.start_join_run(
        join_key=join_key,
        left_dataset_id=klass_dataset_id,
        right_dataset_id=right_dataset_id,
        left_request_url=klass_dataset.get("access_path") or "",
        right_request_url=(
            f"{FHI_API_ROOT}/{fhi_ref[0]}/Table/{fhi_ref[1]}/data"
            if fhi_ref
            else DEFAULT_SSB_TABLE_URL
            if ssb_table == DEFAULT_SSB_TABLE
            else f"https://data.ssb.no/api/v0/no/table/{ssb_table}"
        ),
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    left_http = 0
    right_http = 0
    left_url = klass_dataset.get("access_path") or ""
    right_url = ""
    sample: list[dict[str, Any]] = []
    stored: list[dict[str, Any]] = []
    try:
        klass_fetch = fetch_observations(registry, klass_dataset_id, table_id="klass", http=http)
        left_http = klass_fetch.http_status
        left_url = klass_fetch.request_url
        klass_by_code = _klass_by_code(registry.list_observations(klass_dataset_id))
        if not klass_by_code:
            raise ValueError(f"{klass_dataset_id} stored no classification codes to join on")
        if fhi_ref:
            ssb = fetch_fhi_table_coded(
                fhi_ref[0], fhi_ref[1], year=year, http=http, key_codes=set(klass_by_code)
            )
        else:
            ssb = fetch_ssb_table(ssb_table, year=year, http=http, key_codes=set(klass_by_code))
        right_http = ssb.http_status
        right_url = ssb.request_url
        right_title = ssb.label
        right_publisher = ssb.source or SSB_PUBLISHER
        _persist_ssb_observations(
            registry,
            ssb,
            right_dataset_id,
            series=series,
            join_key=join_key,
            known_codes=set(klass_by_code),
        )
        retrieved_left = utc_now()
        for cell in ssb.cells:
            code = _region_code(cell.codes, set(klass_by_code))
            if code is None:
                continue
            klass_row = klass_by_code.get(code)
            if klass_row is None:
                continue
            year_label = (
                cell.labels.get("Tid")
                or cell.labels.get("AAR")
                or cell.codes.get("Tid")
                or cell.codes.get("AAR")
                or ""
            )
            why = (
                f"exact {join_key} {code} in "
                f"{'FHI ' + ssb_table if fhi_ref else 'SSB ' + ssb_table} and "
                f"Klass classificationItems.code"
            )
            value, suppressed = _numeric_or_suppressed(cell.value)
            # The dimensions that are not the key or the period are what make
            # two cells for one region different rows rather than duplicates.
            breakdown = {
                name: label
                for name, label in cell.labels.items()
                if name not in {"Tid", "AAR"} and label != code
            }
            payload = {
                join_key: code,
                "year": year_label,
                "dimensions": breakdown,
                "age": cell.labels.get("KOKalder0000") or cell.labels.get("Alder"),
                "population": value,
                "population_measure": cell.measure,
                "suppressed": suppressed,
                "ssb_region_label": (
                    cell.labels.get("KOKbydelsregion0000")
                    or cell.labels.get("Region")
                    or cell.labels.get("GEO")
                ),
                "klass_name": json.loads(klass_row["value_json"]),
            }
            record = {
                "id": _joined_id(
                    join_key, code, year_label, klass_dataset_id, right_dataset_id,
                    breakdown, cell.measure,
                ),
                "join_key": join_key,
                "join_key_value": code,
                "why_matched": why,
                "left_dataset_id": klass_dataset_id,
                "right_dataset_id": right_dataset_id,
                "left_publisher_name": klass_dataset.get("publisher_name"),
                "right_publisher_name": right_publisher,
                "left_license": klass_dataset.get("license"),
                "right_license": None,
                "left_access_path": klass_dataset.get("access_path"),
                "right_access_path": ssb.request_url,
                "left_request_url": left_url,
                "right_request_url": right_url,
                "left_retrieved_at": klass_row.get("retrieved_at") or retrieved_left,
                "right_retrieved_at": ssb.retrieved_at,
                "payload": payload,
            }
            action = registry.upsert_joined_row(record, run_id)
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            stored.append({**payload, "why_matched": why})
            if len(sample) < 5:
                sample.append(
                    {
                        "join_key": join_key,
                        "join_key_value": code,
                        "why_matched": why,
                        **payload,
                    }
                )
        counts.listed = len(stored)
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc)})
        raise
    finally:
        registry.finish_join_run(
            run_id,
            counts,
            status=status,
            left_http_status=left_http or None,
            right_http_status=right_http or None,
        )
    return JoinResult(
        join_key=join_key,
        left_dataset_id=klass_dataset_id,
        right_dataset_id=right_dataset_id,
        left_request_url=left_url,
        right_request_url=right_url,
        left_http_status=left_http,
        right_http_status=right_http,
        right_title=right_title,
        right_publisher=right_publisher,
        counts=counts,
        sample=sample,
        rows=stored,
    )


# A merged row pairs one cell from each side. Two tables that each split a
# region several ways multiply, so the pairing is counted before it is built
# and refuses rather than returning a cross product nobody asked for.
MAX_PAIRS = 200_000


class TableJoinTooLarge(ValueError):
    """Pairing two tables would produce more rows than the limit allows."""

    def __init__(self, pairs: int, limit: int, worst: list[dict[str, Any]]) -> None:
        self.pairs, self.limit, self.worst = pairs, limit, worst
        detail = "; ".join(
            f"{item['key']}: {item['left']} x {item['right']}" for item in worst
        )
        super().__init__(
            f"pairing would produce {pairs:,} rows, over the {limit:,} limit. "
            f"Narrow a breakdown or a measure on either table. Widest keys: {detail}"
        )


@dataclass
class TableJoinResult:
    join_key: str
    classification_id: str
    left_table: str
    right_table: str
    left: JoinResult
    right: JoinResult
    rows: list[dict[str, Any]] = field(default_factory=list)
    left_only: list[str] = field(default_factory=list)
    right_only: list[str] = field(default_factory=list)
    withheld: int = 0


def join_table_to_table(
    registry: Registry,
    *,
    left_table: str,
    right_table: str,
    klass_dataset_id: str = DEFAULT_KLASS_DATASET,
    year: int | None = 2025,
    http: JsonHttp | None = None,
    join_key: str = JOIN_KEY,
    max_pairs: int = MAX_PAIRS,
) -> TableJoinResult:
    """Join two statistical tables to each other through a shared classification.

    Each table is first joined to the classification on its own, so both sides'
    keys are proved against the same published code list rather than against
    each other. A code neither table prints cannot appear, and a code only one
    side prints is reported rather than dropped in silence.

    Tables may be named as an SSB table id or as "fhi:<register>:<table>", so a
    population table and a health table join on the kommune or bydel code that
    both publishers happen to print.
    """

    # Both sides keep the default series. The tag separates incompatible
    # dimension shapes within one dataset_id, and the two tables already differ
    # by dataset_id; a per-table suffix instead relabels rows an earlier join
    # wrote, because the observation id does not include the series.
    left = join_classification_to_table(
        registry, klass_dataset_id=klass_dataset_id, ssb_table=left_table,
        year=year, http=http, join_key=join_key,
    )
    right = join_classification_to_table(
        registry, klass_dataset_id=klass_dataset_id, ssb_table=right_table,
        year=year, http=http, join_key=join_key,
    )

    withheld = sum(
        1 for row in (*left.rows, *right.rows) if row.get("suppressed") is not None
    )
    left_by_key = _rows_by_key(left.rows, join_key)
    right_by_key = _rows_by_key(right.rows, join_key)
    shared = sorted(set(left_by_key) & set(right_by_key))

    pairs = sum(len(left_by_key[key]) * len(right_by_key[key]) for key in shared)
    if pairs > max_pairs:
        worst = sorted(
            (
                {
                    "key": key,
                    "left": len(left_by_key[key]),
                    "right": len(right_by_key[key]),
                }
                for key in shared
            ),
            key=lambda item: -(item["left"] * item["right"]),
        )[:3]
        raise TableJoinTooLarge(pairs, max_pairs, worst)

    rows: list[dict[str, Any]] = []
    for key in shared:
        for left_row in left_by_key[key]:
            for right_row in right_by_key[key]:
                rows.append(
                    {
                        join_key: key,
                        "name": left_row.get("klass_name") or right_row.get("klass_name"),
                        "year": left_row.get("year") or right_row.get("year"),
                        "left_table": left_table,
                        "left_value": left_row.get("population"),
                        "left_measure": left_row.get("population_measure"),
                        "left_dimensions": left_row.get("dimensions") or {},
                        "right_table": right_table,
                        "right_value": right_row.get("population"),
                        "right_measure": right_row.get("population_measure"),
                        "right_dimensions": right_row.get("dimensions") or {},
                        "why_matched": (
                            f"exact {join_key} {key} printed by {left_table}, "
                            f"{right_table} and {klass_dataset_id}"
                        ),
                    }
                )
    return TableJoinResult(
        join_key=join_key,
        classification_id=klass_dataset_id,
        left_table=left_table,
        right_table=right_table,
        left=left,
        right=right,
        rows=rows,
        left_only=sorted(set(left_by_key) - set(right_by_key)),
        right_only=sorted(set(right_by_key) - set(left_by_key)),
        withheld=withheld,
    )


def _rows_by_key(rows: list[dict[str, Any]], join_key: str) -> dict[str, list[dict[str, Any]]]:
    """Group joined rows by key, keeping only cells that carry a value.

    A withheld cell has no number to pair with, so pairing it would invent a
    relationship between one real value and a censored one.
    """

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("suppressed") is not None or row.get("population") is None:
            continue
        key = row.get(join_key)
        if key is None:
            continue
        grouped.setdefault(str(key), []).append(row)
    return grouped


def join_proof_payload(
    result: JoinResult,
    *,
    command: str,
    db: str,
    klass_dataset: dict[str, Any] | None,
    datasets: int | None = None,
    enrichments: int | None = None,
) -> dict[str, Any]:
    return {
        "produced_at": utc_now(),
        "command": command,
        "why_not_m7_m8": WHY_NOT_M7_M8,
        "why_not_07459": WHY_NOT_07459,
        "why_this_table": WHY_11763,
        "join_key": result.join_key,
        "sources": {
            "left": {
                "dataset_id": result.left_dataset_id,
                "title": (klass_dataset or {}).get("title"),
                "publisher_name": (klass_dataset or {}).get("publisher_name"),
                "license": (klass_dataset or {}).get("license"),
                "access_path": (klass_dataset or {}).get("access_path"),
                "request_url": result.left_request_url,
                "http_status": result.left_http_status,
            },
            "right": {
                "dataset_id": result.right_dataset_id,
                "title": result.right_title,
                "publisher_name": result.right_publisher or SSB_PUBLISHER,
                "license": None,
                "access_path": result.right_request_url,
                "request_url": result.right_request_url,
                "http_status": result.right_http_status,
                "auth": "none",
            },
        },
        "db": db,
        "counts": {
            "joined": result.counts.listed,
            "inserted": result.counts.inserted,
            "updated": result.counts.updated,
            "unchanged": result.counts.unchanged,
            "failed": result.counts.failed,
            "datasets_unchanged": datasets,
            "enrichments_unchanged": enrichments,
        },
        "sample": result.sample,
        "rows": result.rows,
    }


def _persist_ssb_observations(
    registry: Registry,
    ssb: SsbTableResult,
    dataset_id: str,
    *,
    series: str = JOIN_SERIES,
    join_key: str = JOIN_KEY,
    known_codes: set[str] | None = None,
) -> None:
    """Write the cells already in hand into the observations store.

    The key dimension is named after the join actually performed, so a kommune
    or fylke join does not store its codes under a column called bydel_code.
    """

    registry.ensure_observation_dataset(
        dataset_id=dataset_id,
        title=ssb.label,
        publisher_name=ssb.source or SSB_PUBLISHER,
        access_path=ssb.request_url,
        license=None,
    )
    dataset = registry.get_dataset(dataset_id)
    if dataset is None:
        raise ValueError(f"unknown dataset {dataset_id}")
    run_id = registry.start_fetch_run(
        dataset_id=dataset_id,
        table_id=ssb.table_id,
        request_url=ssb.request_url,
        request_method="POST",
        started_at=ssb.retrieved_at,
    )
    counts = HarvestCounts()
    status = "failed"
    cells: list[tuple[str, Any, dict[str, str]]] = []
    try:
        for cell in ssb.cells:
            code = _region_code(cell.codes, known_codes)
            if code is None:
                continue
            year_label = cell.labels.get("Tid") or cell.codes.get("Tid") or ""
            region_label = (
                cell.labels.get("KOKbydelsregion0000") or cell.labels.get("Region") or code
            )
            cells.append(
                (
                    cell.measure,
                    cell.value,
                    {"region": region_label, "år": year_label, join_key: code},
                )
            )
        counts.listed = len(cells)
        _store_cells(
            registry,
            dataset,
            run_id,
            table_id=ssb.table_id,
            cells=cells,
            retrieved_at=ssb.retrieved_at,
            request_url=ssb.request_url,
            http_status=ssb.http_status,
            counts=counts,
            series=series,
        )
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": ssb.request_url})
        raise
    finally:
        registry.finish_fetch_run(
            run_id, counts, status=status, http_status=ssb.http_status
        )


def _klass_by_code(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        dims = json.loads(row["dimensions_json"])
        code = dims.get("code")
        if code:
            out[str(code)] = row
    return out


def _numeric_or_suppressed(value: Any) -> tuple[Any, str | None]:
    """Separate a number from a marker standing in for one.

    FHI prints ":" where a cell is withheld. Stored unchanged it reads as data,
    and a later mean over the column silently treats a censored cell as a value.
    """

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value, None
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(text), None
        except ValueError:
            return None, text or None
    return (value, None) if value is not None else (None, None)


def _region_code(codes: dict[str, str], known: set[str] | None = None) -> str | None:
    """Pick the cell code that the joined classification also stores.

    When ``known`` is given the match is exact membership, so the key is proved
    by both payloads rather than inferred from a code's shape. The six-digit
    fallback preserves the original Oslo bydel behaviour.
    """

    if known:
        for key in ("KOKbydelsregion0000", "Region"):
            value = codes.get(key)
            if value and value in known:
                return value
        for value in codes.values():
            if value in known:
                return value
        return None
    for key in ("KOKbydelsregion0000", "Region"):
        value = codes.get(key)
        if value and len(value) == 6 and value.isdigit():
            return value
    for value in codes.values():
        if len(value) == 6 and value.isdigit():
            return value
    return None


def _joined_id(
    join_key: str,
    key_value: str,
    year: str,
    left_dataset_id: str,
    right_dataset_id: str,
    dimensions: dict[str, str] | None = None,
    measure: str = "",
) -> str:
    """Identify a joined row by everything that distinguishes it.

    Keyed on (key, year) alone, every breakdown of one region collapsed onto a
    single id and overwrote the last: a table split by school year, mastery
    level and parents' education stored one arbitrary survivor per region while
    reporting the full row count as joined.
    """

    # Two cells for one region that count different things are different rows,
    # so what is measured belongs in the identity alongside the breakdown.
    parts = [join_key, key_value, year, left_dataset_id, right_dataset_id, measure]
    for name in sorted(dimensions or {}):
        parts.append(f"{name}={dimensions[name]}")
    raw = "\0".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
