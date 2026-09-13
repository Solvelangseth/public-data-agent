"""Landbruksdirektoratet dairy-delivery CSVs.

Each calendar year is one CSV of farm-level litres delivered to dairies,
published on GitHub and already stored as Data.norge catalogue rows. This
module does not re-catalogue those years. It recognises the printed raw CSV
URL, reads the printed columns, and returns either the national sums or one
farm. It does not import every farm as a dataset or as a stored row.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any
from urllib.parse import urlparse

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ldirmelk"
SOURCE_NAME = "Landbruksdirektoratet melkeleveranser"
PUBLISHER = "Landbruksdirektoratet"
GITHUB_API = (
    "https://api.github.com/repos/LandbruksdirektoratetGIT/opendata/contents/"
    "datasets/leveransedata-melk"
)
RAW_PREFIX = (
    "https://raw.githubusercontent.com/LandbruksdirektoratetGIT/opendata/"
    "refs/heads/main/datasets/leveransedata-melk"
)
LANDING_PAGE = (
    "https://www.landbruksdirektoratet.no/nb/statistikk-og-utviklingstrekk/"
    "utvikling-i-jordbruket/ravarestatistikk"
)
INGEST_REASON = (
    "listed as a year directory under LandbruksdirektoratetGIT/opendata "
    "datasets/leveransedata-melk"
)
HOST = "raw.githubusercontent.com"
PATH_MARK = "/landbruksdirektoratetgit/opendata/"
CSV_PATH = re.compile(
    r"/datasets/leveransedata-melk/(?P<year>20\d{2})/dataset\.csv$",
    re.IGNORECASE,
)
YEAR_DIR = re.compile(r"^20\d{2}$")
MEASURES = ("kumelk_liter", "geitemelk_liter")
FARM_LIMIT = 20
REQUESTS_PER_SECOND = 2.0
BURST = 4


class LdirMelkSource(SourceBase):
    """Year listing over the publisher's GitHub dairy-delivery folders.

    V1 fetch of an existing Data.norge row does not need this harvest. The
    listing exists so tests, and a year Data.norge has not stored, can still
    reach the same CSV. Do not ingest it into a registry that already holds
    the Data.norge year cards — that would duplicate the same file.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (GITHUB_API,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        catalogue_url: str = GITHUB_API,
        raw_prefix: str = RAW_PREFIX,
        http: Any | None = None,
    ) -> None:
        self.catalogue_url = catalogue_url
        self.raw_prefix = raw_prefix.rstrip("/")
        self.http = http or HttpClient(
            limiter=RateLimiter(REQUESTS_PER_SECOND, BURST),
            timeout=60.0,
            max_retries=3,
        )
        self._listed: list[dict[str, Any]] = []

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        listed = self.http.get_json(self.catalogue_url)
        if not isinstance(listed, list):
            raise SourceError(
                f"Landbruksdirektoratet melk listing is not a list: {self.catalogue_url}"
            )
        refs: list[DatasetRef] = []
        for item in listed:
            if not isinstance(item, dict) or item.get("type") != "dir":
                continue
            year = item.get("name")
            if not isinstance(year, str) or not YEAR_DIR.match(year):
                continue
            self._listed.append(item)
            refs.append(
                DatasetRef(
                    source_native_uri=f"{self.raw_prefix}/{year}/dataset.csv",
                    source_native_id=year,
                    catalog_modified=_string(item.get("sha")),
                )
            )
        refs.sort(key=lambda ref: ref.source_native_id or "")
        end = None if limit is None else offset + limit
        return refs[offset:end]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        year = ref.source_native_id or ldirmelk_table_id(ref.source_native_uri)
        title = f"Leveranser til meieri i landbruket {year}"
        payload: dict[str, Any] = {
            "id": year,
            "uri": ref.source_native_uri,
            "title": {"no": title},
            "description": {
                "no": (
                    "Leveranser av melk som er levert fra jordbruksforetak til "
                    "meieri i landbruket. Dataene inkluderer ikke melk som er "
                    "levert til lokal foredling."
                )
            },
            "publisher": {"title": {"no": PUBLISHER}, "id": None, "uri": None},
            "distribution": [
                {
                    "uri": ref.source_native_uri,
                    "title": {"no": title},
                    "downloadURL": [ref.source_native_uri],
                    "accessURL": [ref.source_native_uri],
                    "fdkFormat": [
                        {"code": "CSV", "type": "MEDIA_TYPE", "name": "text/csv"}
                    ],
                }
            ],
            "landingPage": [LANDING_PAGE],
            "keyword": [
                {"no": "melk"},
                {"no": "meieri"},
                {"no": "kumelk"},
                {"no": "geitemelk"},
                {"no": "melkeleveranser"},
            ],
            "temporal": [{"startDate": year, "endDate": year}],
            # The CSV does not print a licence. Data.norge states NLOD on the
            # matching catalogue card; this harvest does not copy that across.
            "license": None,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=year,
            source_native_uri=ref.source_native_uri,
            fetched_from=self.catalogue_url,
            payload=payload,
            catalog_modified=ref.catalog_modified,
        )


def is_ldirmelk_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlparse(access_path)
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.netloc.casefold() != HOST:
        return False
    return CSV_PATH.search(parsed.path) is not None


def ldirmelk_table_id(access_path: str) -> str:
    match = CSV_PATH.search(urlparse(access_path).path)
    if match is None:
        raise ValueError(f"not a Landbruksdirektoratet melk CSV: {access_path}")
    return match.group("year")


def cells_from_ldirmelk(
    body: str,
    *,
    year: str,
    select: dict[str, list[str]] | None = None,
) -> list[tuple[str, Any, dict[str, str]]]:
    """Turn one year CSV into observation cells.

    Default is the national sum of each printed litre column. A farm-level
    extract requires ``organisasjonsnummer``. Empty cells are skipped, not
    stored as zero. Asking for more farms than ``FARM_LIMIT`` is refused by
    the caller before this runs.
    """

    rows = _rows(body)
    wanted = _selected_orgnrs(select)
    if wanted is not None:
        by_org = {row["orgnr"]: row for row in rows}
        missing = [code for code in wanted if code not in by_org]
        if missing:
            raise ValueError(
                f"organisasjonsnummer {missing} not in the {year} melk CSV; "
                "the file does not list that farm"
            )
        chosen = [by_org[code] for code in wanted]
        cells: list[tuple[str, Any, dict[str, str]]] = []
        for row in chosen:
            dims = {
                "år": year,
                "organisasjonsnummer": row["orgnr"],
                "komnr": row["komnr"],
            }
            for measure in MEASURES:
                value = row.get(measure)
                if value is None:
                    continue
                cells.append((measure, value, dict(dims)))
        return cells
    cells = []
    for measure in MEASURES:
        total = sum(row[measure] for row in rows if row.get(measure) is not None)
        if not any(row.get(measure) is not None for row in rows):
            continue
        cells.append((measure, total, {"år": year}))
    return cells


def shape_from_ldirmelk(body: str, *, year: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = _rows(body)
    orgnrs = sorted({row["orgnr"] for row in rows})
    komnr = sorted({row["komnr"] for row in rows if row.get("komnr")})
    fields = [
        {
            "field_code": "år",
            "field_label": "år",
            "field_role": "period",
            "values": [{"value_code": year, "value_label": year}],
        },
        {
            "field_code": "organisasjonsnummer",
            "field_label": "organisasjonsnummer",
            "field_role": "key",
            "values": [
                {"value_code": code, "value_label": code} for code in orgnrs[:20]
            ],
        },
        {
            "field_code": "komnr",
            "field_label": "komnr",
            "field_role": "attribute",
            "values": [
                {"value_code": code, "value_label": code} for code in komnr[:20]
            ],
        },
        {
            "field_code": "kumelk_liter",
            "field_label": "kumelk_liter",
            "field_role": "measure",
            "values": [],
        },
        {
            "field_code": "geitemelk_liter",
            "field_label": "geitemelk_liter",
            "field_role": "measure",
            "values": [],
        },
    ]
    # Organisation numbers are verified by the printed column plus mod-11 on
    # the values that column actually holds. Municipality numbers are stored
    # as attributes: the CSV prints no names, so klass:131 is not claimed.
    keys = []
    if orgnrs and all(_mod11(code) for code in orgnrs[:50]):
        keys.append(
            {
                "scheme": "brreg:orgnr",
                "field_code": "organisasjonsnummer",
                "coverage_count": len(orgnrs),
            }
        )
    return fields, keys


def _rows(body: str) -> list[dict[str, Any]]:
    text = body.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        raise ValueError("melk CSV has no header")
    required = {"orgnr", "navn", "komnr", "kumelk_liter", "geitemelk_liter"}
    got = {name.strip() for name in reader.fieldnames if name}
    missing = required - got
    if missing:
        raise ValueError(f"melk CSV header missing {sorted(missing)}; printed {sorted(got)}")
    rows: list[dict[str, Any]] = []
    for item in reader:
        orgnr = (item.get("orgnr") or "").strip()
        if not orgnr:
            continue
        rows.append(
            {
                "orgnr": orgnr,
                "navn": (item.get("navn") or "").strip(),
                "komnr": (item.get("komnr") or "").strip(),
                "kumelk_liter": _number(item.get("kumelk_liter")),
                "geitemelk_liter": _number(item.get("geitemelk_liter")),
            }
        )
    if not rows:
        raise ValueError("melk CSV printed no farm rows")
    return rows


def _selected_orgnrs(select: dict[str, list[str]] | None) -> list[str] | None:
    if not select:
        return None
    unknown = sorted(key for key in select if key != "organisasjonsnummer")
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that a melk fetch does not filter on; "
            "only organisasjonsnummer is accepted, or omit select for the national total"
        )
    wanted = select.get("organisasjonsnummer") or []
    wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
    if not wanted:
        raise ValueError("select organisasjonsnummer is empty")
    return wanted


def _number(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text.replace(",", ".")))
        except ValueError:
            raise ValueError(f"melk CSV value is not a number: {text!r}") from None


def _mod11(orgnr: str) -> bool:
    if len(orgnr) != 9 or not orgnr.isdigit():
        return False
    weights = (3, 2, 7, 6, 5, 4, 3, 2)
    total = sum(int(digit) * weight for digit, weight in zip(orgnr[:8], weights))
    remainder = total % 11
    check = 0 if remainder == 0 else 11 - remainder
    return check != 10 and check == int(orgnr[8])


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
