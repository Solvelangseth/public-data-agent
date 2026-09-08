from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "brkommuner"
SOURCE_NAME = "Brønnøysundregistrene Enhetsregisteret kommuner"
LIST_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner"
PATH_PREFIX = "/enhetsregisteret/api/kommuner"
DEFAULT_MAX_ITEMS = 10_000
INGEST_REASON = (
    "listed across all printed pages of the official Enhetsregisteret "
    f"kommuner catalog, with a safety ceiling of {DEFAULT_MAX_ITEMS} codes"
)
BRKOMMUNER_RPS = 2.0
BRKOMMUNER_BURST = 4
HOST = "data.brreg.no"
NAME_FIELDS = ("navn", "nummer")
BRREG_KOMMUNE_SCHEME = "brreg:kommunenummer"


class BrkommunerSource(SourceBase):
    """Replaceable ingest adapter for leftover Enhetsregisteret kommuner.

    Listing copies printed `_embedded.kommuner[].nummer` values and the
    printed `_links.self.href` from the official
    `/enhetsregisteret/api/kommuner` collection. Native ids are the
    printed `nummer` strings so `0301` stays distinct from `1103`. This
    first slice stays inside that catalog and caps the walk. It does not
    invent page or size query parameters. This is not the Enhetsregisteret
    HAL root (`--source brreg`), not leftover organisasjonsformer
    (`--source brorgform`), not leftover roller lists
    (`--source brroller`), not Frivillighetsregisteret
    (`--source frivillig`), and not Kartverket kommuneinfo
    (`--source kommuneinfo`).
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (LIST_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        list_url: str = LIST_URL,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.list_url = list_url
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(BRKOMMUNER_RPS, BRKOMMUNER_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_nummer(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or brkommuner_table_id(ref.source_native_uri or "")
        item = self._catalog_item(ident)
        endpoint = printed_item_url(item, self.list_url)
        title = printed_title(item, ident)
        payload = {
            "id": ident,
            "uri": endpoint,
            "title": title,
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.list_url],
            "brkommuner_kommune": {
                key: item[key]
                for key in item
                if key != "_links"
            },
            "brkommuner_self_href": endpoint,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ident,
            source_native_uri=endpoint,
            fetched_from=self.list_url,
            payload=payload,
        )

    def _catalog(self) -> list[dict[str, Any]]:
        if self._listed is not None:
            return self._listed
        listed: list[dict[str, Any]] = []
        url: str | None = self.list_url
        visited: set[str] = set()
        while url is not None and len(listed) < self.max_items:
            if url in visited:
                raise SourceError(f"Enhetsregisteret kommuner pagination loop at {url}")
            visited.add(url)
            try:
                body = self.http.get_json(url)
            except Exception as exc:
                raise SourceError(
                    f"Enhetsregisteret kommuner catalog failed for {url}: {exc}"
                ) from exc
            listed.extend(printed_kommuner(body))
            url = printed_next_url(body, self.list_url)
        listed = listed[: self.max_items]
        if not listed:
            raise SourceError("Enhetsregisteret kommuner catalog printed no kommuner")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_nummer(item) == ident:
                return item
        raise SourceError(f"Enhetsregisteret kommuner catalog has no printed nummer {ident}")


def printed_kommuner(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Enhetsregisteret kommuner catalog is not a JSON object")
    embedded = body.get("_embedded")
    if not isinstance(embedded, dict):
        raise SourceError("Enhetsregisteret kommuner catalog has no printed _embedded object")
    items = embedded.get("kommuner")
    if not isinstance(items, list):
        raise SourceError("Enhetsregisteret kommuner catalog has no printed kommuner array")
    listed: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            printed_nummer(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_nummer(item: dict[str, Any]) -> str:
    nummer = item.get("nummer")
    if isinstance(nummer, str) and nummer.strip():
        return nummer.strip()
    raise SourceError("Enhetsregisteret kommune has no printed nummer")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    links = item.get("_links")
    if isinstance(links, dict):
        self_link = links.get("self")
        if isinstance(self_link, dict):
            href = self_link.get("href")
            if isinstance(href, str) and href.strip():
                return href.strip()
    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Enhetsregisteret kommuner catalog URL has no printed origin")
    nummer = printed_nummer(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{nummer}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    name = item.get("navn")
    if isinstance(name, str) and name.strip():
        return {"no": name.strip()}
    return {"no": ident}


def printed_next_url(body: Any, list_url: str) -> str | None:
    links = body.get("_links") if isinstance(body, dict) else None
    next_link = links.get("next") if isinstance(links, dict) else None
    href = next_link.get("href") if isinstance(next_link, dict) else None
    if not isinstance(href, str) or not href.strip():
        return None
    parsed = urlsplit(href.strip())
    origin = urlsplit(list_url)
    if parsed.scheme != "https" or parsed.netloc.casefold() != origin.netloc.casefold():
        raise SourceError("Enhetsregisteret kommuner printed an unsafe next-page URL")
    if parsed.path.rstrip("/") != PATH_PREFIX:
        raise SourceError("Enhetsregisteret kommuner next-page URL left the collection")
    return href.strip()


def is_brkommuner_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    path = parsed.path.rstrip("/")
    prefix = PATH_PREFIX + "/"
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :]
    return bool(rest) and "/" not in rest


def brkommuner_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "brkommuner"


def cells_from_brkommuner(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Legacy observation projection. Prefer entity_from_brkommuner."""

    if not isinstance(payload, dict):
        raise ValueError("brkommuner payload is not a JSON object")
    cells = _cells_from_record(
        {key: value for key, value in payload.items() if key != "_links"}
    )
    if not cells:
        raise ValueError("brkommuner payload printed no kommune members")
    return cells


def entity_from_brkommuner(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("brkommuner payload is not a JSON object")
    number = payload.get("nummer")
    if not isinstance(number, str) or not number.strip():
        raise ValueError("brkommuner payload printed no nummer")
    name = payload.get("navn")
    label = name.strip() if isinstance(name, str) and name.strip() else None
    attributes = {
        str(key): value
        for key, value in payload.items()
        if key not in {"nummer", "navn", "_links"}
    }
    return {
        "subject_scheme": BRREG_KOMMUNE_SCHEME,
        "subject_code": number.strip(),
        "subject_label": label,
        "attributes": attributes,
    }


def shape_from_brkommuner(
    payload: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entity = entity_from_brkommuner(payload)
    code, label = entity["subject_code"], entity["subject_label"]
    fields: list[dict[str, Any]] = [
        {
            "field_code": "nummer", "field_label": "nummer", "field_role": "key",
            "value_count": 1, "values": [{"value_code": code, "value_label": label}],
        }
    ]
    if label is not None:
        fields.append(
            {
                "field_code": "navn", "field_label": "navn", "field_role": "attribute",
                "value_count": 1, "values": [{"value_code": label, "value_label": label}],
            }
        )
    return fields, [
        {
            "scheme": BRREG_KOMMUNE_SCHEME,
            "field_code": "nummer",
            "coverage_count": 1,
        }
    ]


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    measure = None
    value: Any = None
    for field in NAME_FIELDS:
        printed = scalars.get(field)
        if printed is None:
            continue
        if isinstance(printed, str) and not printed.strip():
            continue
        measure = field
        value = printed
        break
    if measure is None:
        measure, value = next(iter(scalars.items()))
    dims = {key: _as_dim(other) for key, other in scalars.items() if key != measure}
    return [(measure, value, dims)]


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
