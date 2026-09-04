"""Coded reads of FHI Statistikk tables, for joining.

`fetch.py` fetches an FHI table into the observation store, where dimensions are
kept as labels. A join matches on codes -- FHI prints geography as Klass codes
while labelling it "Bydel Grünerløkka" against Klass's "Grünerløkka" -- so the
join path needs the codes the store does not keep. This mirrors `ssb_pxweb.py`
for the FHI API and returns the same `CodedCell` shape.
"""

from __future__ import annotations

from typing import Any

from public_data_agent.fetch import JsonHttp, _fhi_selection
from public_data_agent.http_util import HttpClient
from public_data_agent.registry import utc_now
from public_data_agent.sources.fhi import (
    API_ROOT,
    flatten_categories,
    printed_table_data_url,
)
from public_data_agent.ssb_pxweb import CodedCell, SsbTableResult, cells_from_jsonstat_coded

FHI_PUBLISHER = "Folkehelseinstituttet"


def codes_matching_classification(
    dimensions: list[dict[str, Any]], key_codes: set[str]
) -> tuple[str, list[str]] | None:
    """Find the dimension whose printed values overlap a classification.

    The key is discovered rather than assumed to be GEO: a table that shares no
    codes with the classification genuinely has no join key, and saying so beats
    joining on a dimension that merely sounds geographic.
    """

    best: tuple[str, list[str]] | None = None
    best_overlap = 0
    for dim in dimensions:
        code = str(dim.get("code") or "")
        values = [value for value, _ in flatten_categories(dim.get("categories"))]
        overlap = [value for value in values if value in key_codes]
        if len(overlap) > best_overlap:
            best, best_overlap = (code, overlap), len(overlap)
    return best


def fetch_fhi_table_coded(
    source_id: str,
    table_id: str,
    *,
    year: int | None = None,
    http: JsonHttp | None = None,
    key_codes: set[str] | None = None,
) -> SsbTableResult:
    """Read one FHI table's cells, keeping dimension codes alongside labels."""

    client = http or HttpClient(timeout=60.0, max_retries=4)
    base = printed_table_data_url(source_id, table_id)
    meta = client.get_json_response(f"{base}/dimension?includeValues=true")
    if meta.status != 200:
        raise ValueError(f"FHI dimension metadata HTTP {meta.status} for {base}")
    dimensions = (meta.body or {}).get("dimensions") or []
    if not dimensions:
        raise ValueError(f"FHI table {table_id} prints no dimensions")

    select: dict[str, list[str]] | None = None
    if key_codes is not None:
        matched = codes_matching_classification(dimensions, key_codes)
        if matched is None:
            raise ValueError(
                f"FHI table {table_id} prints no dimension whose codes overlap the "
                "classification; these two do not share a join key"
            )
        select = {matched[0]: matched[1]}

    query = {
        "dimensions": _fhi_selection(
            dimensions,
            from_year=year,
            to_year=year,
            select=select,
            table_id=table_id,
        ),
        "response": {"format": "json-stat2"},
    }
    data_url = f"{base}/data"
    posted = client.post_json_response(data_url, query)
    if posted.status != 200:
        raise ValueError(f"FHI table query HTTP {posted.status} for {data_url}")
    body = posted.body
    if not isinstance(body, dict):
        raise ValueError("FHI table response is not a JSON object")
    return SsbTableResult(
        table_id=table_id,
        request_url=data_url,
        http_status=posted.status,
        source=FHI_PUBLISHER,
        label=str(body.get("label") or table_id),
        retrieved_at=utc_now(),
        cells=cells_from_jsonstat_coded(body),
    )


def parse_fhi_table_ref(ref: str) -> tuple[str, str] | None:
    """Read "fhi:<register>:<table>" as the pair it names.

    Returns None for anything else, so a caller can tell an FHI table apart from
    an SSB table id without guessing at the string.
    """

    parts = ref.split(":")
    if len(parts) == 3 and parts[0] == "fhi" and parts[1] and parts[2]:
        return parts[1], parts[2]
    return None


__all__ = [
    "API_ROOT",
    "CodedCell",
    "FHI_PUBLISHER",
    "codes_matching_classification",
    "fetch_fhi_table_coded",
    "parse_fhi_table_ref",
]
