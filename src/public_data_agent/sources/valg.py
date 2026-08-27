from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "valg"
SOURCE_NAME = "Valgdirektoratet Valgresultat"
LIST_URL = "https://valgresultat.no/api"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed _sublinks href on the official Valgresultat API root, "
    f"capped at {DEFAULT_MAX_ITEMS}"
)
VALG_RPS = 2.0
VALG_BURST = 4
VALG_HOST = "valgresultat.no"
VALG_PATH = "/api"


class ValgresultatSource(SourceBase):
    """Replaceable ingest adapter for the official Valgresultat list API.

    Listing copies printed `_sublinks` hrefs on the API root. Ids and
    access paths are copied from those printed strings. This first slice
    caps the walk.
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
            limiter=RateLimiter(VALG_RPS, VALG_BURST),
            timeout=60.0,
        )

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(f"Valgresultat API root failed for {self.list_url}: {exc}") from exc
        if not isinstance(body, dict):
            raise SourceError(f"Valgresultat API root is not a JSON object: {self.list_url}")
        listed = _printed_sublink_hrefs(body)
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for href in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=printed_endpoint_url(self.list_url, href),
                    source_native_id=printed_native_id(href),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        href = ref.source_native_uri
        try:
            meta = self.http.get_json(href)
        except Exception as exc:
            raise SourceError(f"Valgresultat GET failed for {href}: {exc}") from exc
        if not isinstance(meta, dict):
            raise SourceError(f"Valgresultat response is not a JSON object: {href}")
        title = printed_title(meta, ref)
        payload = {
            "id": ref.source_native_id,
            "uri": href,
            "title": {"no": title},
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [href],
                    "downloadURL": [href],
                }
            ],
            "landingPage": [href],
            "valg_metadata": meta,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=href,
            fetched_from=href,
            payload=payload,
            catalog_modified=ref.catalog_modified,
        )


def printed_endpoint_url(list_url: str, href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return list_url.rstrip("/") + (href if href.startswith("/") else f"/{href}")


def printed_native_id(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        path = urlparse(href).path
        prefix = VALG_PATH
        rest = path[len(prefix) :] if path.startswith(prefix) else path
        ident = rest.strip("/")
        if not ident:
            raise SourceError("Valgresultat href has no printed path id")
        return ident
    ident = href.strip("/")
    if not ident:
        raise SourceError("Valgresultat href has no printed path id")
    return ident


def printed_title(meta: dict[str, Any], ref: DatasetRef) -> str:
    ident = meta.get("id") if isinstance(meta.get("id"), dict) else {}
    year = ident.get("valgaar")
    kind = ident.get("valgtype")
    if isinstance(year, str) and year.strip() and isinstance(kind, str) and kind.strip():
        return f"{year.strip()}/{kind.strip().lower()}"
    if ref.source_native_id:
        return ref.source_native_id
    return printed_native_id(ref.source_native_uri)


def is_valg_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlparse(access_path)
    return parsed.netloc.lower() == VALG_HOST and parsed.path.startswith(VALG_PATH)


def valg_table_id(access_path: str) -> str:
    path = urlparse(access_path).path
    rest = path[len(VALG_PATH) :] if path.startswith(VALG_PATH) else path
    return rest.strip("/") or "valg"


def cells_from_valg(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Valgresultat `partier` records into observation cells.

    Vote totals are copied from stemmer.resultat.antall.total. Party codes
    and names stay as printed dimensions. Nothing is invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("valg payload is not a JSON object")
    parties = payload.get("partier")
    if not isinstance(parties, list):
        raise ValueError("valg payload has no partier list")
    geo = payload.get("id") if isinstance(payload.get("id"), dict) else {}
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for party in parties:
        if not isinstance(party, dict):
            continue
        ident = party.get("id") if isinstance(party.get("id"), dict) else {}
        code = ident.get("partikode")
        name = ident.get("navn")
        votes = _vote_total(party)
        if votes is None and not isinstance(code, (str, int)):
            continue
        dims: dict[str, str] = {}
        for key in ("valgaar", "valgtype", "nivaa"):
            value = geo.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                dims[key] = str(value)
        if isinstance(code, (str, int)) and not isinstance(code, bool):
            dims["partikode"] = str(code)
        if isinstance(name, str) and name.strip():
            dims["navn"] = name
        measure = name if isinstance(name, str) and name.strip() else "partier"
        cells.append((measure, votes if votes is not None else code, dims))
    return cells


def _printed_sublink_hrefs(body: dict[str, Any]) -> list[str]:
    sublinks = body.get("_sublinks")
    if not isinstance(sublinks, dict):
        raise SourceError("Valgresultat API root has no _sublinks object")
    hrefs: list[str] = []
    for items in sublinks.values():
        if not isinstance(items, list):
            continue
        for item in items:
            href = _printed_href(item)
            if href is None:
                continue
            hrefs.append(href)
    return hrefs


def _printed_href(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    href = item.get("href")
    if isinstance(href, str) and href.strip():
        return href.strip()
    return None


def _vote_total(party: dict[str, Any]) -> int | float | None:
    stemmer = party.get("stemmer")
    if not isinstance(stemmer, dict):
        return None
    resultat = stemmer.get("resultat")
    if not isinstance(resultat, dict):
        return None
    antall = resultat.get("antall")
    if not isinstance(antall, dict):
        return None
    total = antall.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)):
        return None
    return total
