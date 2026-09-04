from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from public_data_agent.fetch import JsonHttp, _jsonstat_index
from public_data_agent.http_util import HttpClient
from public_data_agent.registry import utc_now

SSB_PXWEB_HOST = "data.ssb.no"
SSB_PXWEB_PATH = "/api/v0/"
DEFAULT_SSB_TABLE = "11763"
DEFAULT_SSB_TABLE_URL = f"https://data.ssb.no/api/v0/no/table/{DEFAULT_SSB_TABLE}"


@dataclass
class CodedCell:
    measure: str
    value: Any
    labels: dict[str, str]
    codes: dict[str, str]


@dataclass
class SsbTableResult:
    table_id: str
    request_url: str
    http_status: int
    source: str | None
    label: str | None
    retrieved_at: str
    cells: list[CodedCell] = field(default_factory=list)


def is_ssb_pxweb_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlparse(access_path)
    return parsed.netloc == SSB_PXWEB_HOST and parsed.path.startswith(SSB_PXWEB_PATH)


def ssb_table_url(table_id: str) -> str:
    return f"https://data.ssb.no/api/v0/no/table/{table_id}"


def bydel_codes_from_meta(meta: dict[str, Any]) -> tuple[str, list[str]]:
    """Return the region variable code and its 6-digit bydel values.

    Codes come from the metadata `values` list. Nothing is invented.
    """

    for variable in meta.get("variables") or []:
        text = str(variable.get("text") or "").casefold()
        code = str(variable.get("code") or "")
        if code not in {"Region", "KOKbydelsregion0000"} and "region" not in text:
            continue
        selected = [str(item) for item in (variable.get("values") or []) if _is_bydel_code(str(item))]
        if selected:
            return code, selected
    raise ValueError("table metadata has no 6-digit bydel region codes")


def codes_matching_classification(
    meta: dict[str, Any], classification_codes: set[str]
) -> tuple[str, list[str]] | None:
    """Find the table variable whose stored codes overlap a Klass code list.

    This is the generic form of ``bydel_codes_from_meta``: instead of assuming
    a six-digit bydel region, it asks which dimension of this table literally
    stores the same code strings the classification stores. The join key is
    therefore discovered from both payloads, never assumed. Returns the
    variable code and the overlapping values, or None when nothing overlaps.
    """

    best: tuple[str, list[str]] | None = None
    for variable in meta.get("variables") or []:
        code = str(variable.get("code") or "")
        if not code:
            continue
        overlap = [
            str(item)
            for item in (variable.get("values") or [])
            if str(item) in classification_codes
        ]
        if overlap and (best is None or len(overlap) > len(best[1])):
            best = (code, overlap)
    return best


def i_alt_age_selection(meta: dict[str, Any]) -> tuple[str, str] | None:
    for variable in meta.get("variables") or []:
        text = str(variable.get("text") or "").casefold()
        code = str(variable.get("code") or "")
        if "alder" not in text and "alder" not in code.casefold():
            continue
        for value, label in zip(variable.get("values") or [], variable.get("valueTexts") or []):
            if str(label).casefold() == "i alt":
                return code, str(value)
    return None


def time_year_selection(meta: dict[str, Any], year: int | None) -> tuple[str, str]:
    for variable in meta.get("variables") or []:
        if not variable.get("time"):
            continue
        values = [str(item) for item in (variable.get("values") or [])]
        if not values:
            raise ValueError("time variable has no values")
        if year is None:
            return str(variable["code"]), values[-1]
        wanted = str(year)
        if wanted not in values:
            raise ValueError(f"year {year} is not in the table time axis")
        return str(variable["code"]), wanted
    raise ValueError("table metadata has no time variable")


def cells_from_jsonstat_coded(payload: dict[str, Any]) -> list[CodedCell]:
    """Copy json-stat2 cells and keep both dimension codes and labels."""

    ids = list(payload.get("id") or [])
    sizes = list(payload.get("size") or [])
    values = list(payload.get("value") or [])
    dimension = payload.get("dimension") or {}
    if len(ids) != len(sizes):
        raise ValueError("json-stat id and size length differ")
    axes: list[list[tuple[str, str]]] = []
    for dim_id, size in zip(ids, sizes):
        category = (dimension.get(dim_id) or {}).get("category") or {}
        index = _jsonstat_index(category)
        labels = category.get("label") or {}
        by_pos: list[tuple[str, str] | None] = [None] * size
        for code, pos in index.items():
            by_pos[int(pos)] = (str(code), str(labels.get(code, code)))
        if any(item is None for item in by_pos):
            raise ValueError(f"json-stat dimension {dim_id} is missing an index position")
        axes.append([(code, label) for code, label in by_pos if code is not None])
    cells: list[CodedCell] = []
    for i, value in enumerate(values):
        coords = _unravel(i, sizes)
        measure = ""
        labels: dict[str, str] = {}
        codes: dict[str, str] = {}
        for dim_id, pos, axis in zip(ids, coords, axes):
            code, label = axis[pos]
            codes[dim_id] = code
            if dim_id == "ContentsCode":
                measure = label
                continue
            labels[dim_id] = label
        if not measure:
            measure = str(payload.get("label") or "value")
        cells.append(CodedCell(measure=measure, value=value, labels=labels, codes=codes))
    return cells


def fetch_ssb_table(
    table_id: str,
    *,
    year: int | None = None,
    http: JsonHttp | None = None,
    key_codes: set[str] | None = None,
) -> SsbTableResult:
    client = http or HttpClient(timeout=60.0, max_retries=4)
    request_url = ssb_table_url(table_id)
    meta = client.get_json_response(request_url)
    if meta.status != 200:
        raise ValueError(f"SSB table metadata HTTP {meta.status} for {request_url}")
    if not isinstance(meta.body, dict):
        raise ValueError("SSB table metadata is not a JSON object")
    if key_codes is None:
        region_code, region_values = bydel_codes_from_meta(meta.body)
    else:
        matched = codes_matching_classification(meta.body, key_codes)
        if matched is None:
            raise ValueError(
                f"table {table_id} stores no dimension whose codes overlap the classification; "
                "these two do not share a join key"
            )
        region_code, region_values = matched
    time_code, time_value = time_year_selection(meta.body, year)
    query = _ssb_query(meta.body, region_code, region_values, time_code, time_value)
    posted = client.post_json_response(request_url, query)
    if posted.status != 200:
        raise ValueError(f"SSB table query HTTP {posted.status} for {request_url}")
    if not isinstance(posted.body, dict):
        raise ValueError("SSB table response is not a JSON object")
    source = posted.body.get("source")
    label = posted.body.get("label") or meta.body.get("title")
    return SsbTableResult(
        table_id=table_id,
        request_url=request_url,
        http_status=posted.status,
        source=str(source) if source else None,
        label=str(label) if label else None,
        retrieved_at=utc_now(),
        cells=cells_from_jsonstat_coded(posted.body),
    )


def _ssb_query(
    meta: dict[str, Any],
    region_code: str,
    region_values: list[str],
    time_code: str,
    time_value: str,
) -> dict[str, Any]:
    age = i_alt_age_selection(meta)
    query: list[dict[str, Any]] = []
    for variable in meta.get("variables") or []:
        code = str(variable["code"])
        if code == region_code:
            query.append({"code": code, "selection": {"filter": "item", "values": region_values}})
        elif code == time_code:
            query.append({"code": code, "selection": {"filter": "item", "values": [time_value]}})
        elif age is not None and code == age[0]:
            query.append({"code": code, "selection": {"filter": "item", "values": [age[1]]}})
        else:
            query.append({"code": code, "selection": {"filter": "all", "values": ["*"]}})
    return {"query": query, "response": {"format": "json-stat2"}}


def _is_bydel_code(code: str) -> bool:
    return len(code) == 6 and code.isdigit()


def _unravel(index: int, sizes: list[int]) -> list[int]:
    coords: list[int] = []
    remaining = index
    for size in reversed(sizes):
        coords.append(remaining % size)
        remaining //= size
    coords.reverse()
    return coords
