from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "sandnes"
SOURCE_NAME = "Sandnes kommune - API Documentation"
DOCS_URL = "https://medvirkning.sandnes.kommune.no/api/docs"
API_PATH = "/api"
NATIVE_ID = "api"
DOCS_TITLE = "Sandnes kommune - API Documentation"
HOST = "medvirkning.sandnes.kommune.no"
PRINTED_QUERY = """{
  participatoryProcesses {
    id
    title {
      translations {
        locale
        text
      }
    }
  }

  decidim {
    version
  }
}
"""
INGEST_REASON = (
    "the official Sandnes kommune API docs print URL/api as the POST request route"
)
SANDNES_RPS = 2.0
SANDNES_BURST = 4


class SandnesSource(SourceBase):
    """Replaceable ingest adapter for the Sandnes kommune Decidim API.

    Listing is the one printed `/api` route on the official docs page. It
    does not invent process ids or extra endpoints. Native id is `api`.
    access_path is the docs origin joined to the printed `/api` path.
    Fetch POSTs the GraphiQL default_query printed on the same host.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (DOCS_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        docs_url: str = DOCS_URL,
        http: HttpClient | None = None,
    ) -> None:
        self.docs_url = docs_url
        self.http = http or HttpClient(
            limiter=RateLimiter(SANDNES_RPS, SANDNES_BURST),
            timeout=60.0,
        )

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        listed = [
            DatasetRef(
                source_native_uri=printed_api_url(self.docs_url),
                source_native_id=NATIVE_ID,
            )
        ]
        cap = 1 if limit is None else limit
        return listed[offset : offset + cap]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        endpoint = ref.source_native_uri or printed_api_url(self.docs_url)
        try:
            body = self.http.post_json(endpoint, {"query": PRINTED_QUERY})
        except Exception as exc:
            raise SourceError(f"Sandnes API POST failed for {endpoint}: {exc}") from exc
        titles = printed_process_titles(body)
        description = "; ".join(titles) if titles else None
        payload = {
            "id": NATIVE_ID,
            "uri": endpoint,
            "title": {"no": DOCS_TITLE},
            "description": ({"no": description} if description else None),
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.docs_url],
            "sandnes_graphql": body,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=NATIVE_ID,
            source_native_uri=endpoint,
            fetched_from=endpoint,
            payload=payload,
        )


def printed_api_url(docs_url: str) -> str:
    """Join the docs page origin to the printed `/api` request route."""

    parts = urlsplit(docs_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Sandnes docs URL has no printed origin")
    return f"{parts.scheme}://{parts.netloc}{API_PATH}"


def printed_process_titles(body: Any) -> list[str]:
    data = _graphql_data(body)
    processes = data.get("participatoryProcesses")
    if not isinstance(processes, list):
        return []
    titles: list[str] = []
    for item in processes:
        if not isinstance(item, dict):
            continue
        for _measure, value, _dims in _cells_from_process(item):
            if isinstance(value, str) and value not in titles:
                titles.append(value)
    return titles


def is_sandnes_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.rstrip("/") == API_PATH


def sandnes_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or NATIVE_ID


def cells_from_sandnes(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed GraphQL process title texts into observation cells.

    Null translation texts are skipped. Nested objects besides the printed
    title translations are not copied. Nothing is invented.
    """

    data = _graphql_data(payload)
    processes = data.get("participatoryProcesses")
    if not isinstance(processes, list):
        raise ValueError("sandnes payload has no printed participatoryProcesses array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in processes:
        if isinstance(item, dict):
            cells.extend(_cells_from_process(item))
    if not cells:
        raise ValueError("sandnes payload printed no process titles")
    return cells


def _graphql_data(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("sandnes payload is not a JSON object")
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    if isinstance(payload.get("participatoryProcesses"), list):
        return payload
    raise ValueError("sandnes payload has no printed data object")


def _cells_from_process(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    ident = item.get("id")
    title = item.get("title")
    if not isinstance(title, dict):
        return []
    translations = title.get("translations")
    if not isinstance(translations, list):
        return []
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for row in translations:
        if not isinstance(row, dict):
            continue
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        dims: dict[str, str] = {}
        if ident is not None and str(ident).strip() != "":
            dims["id"] = str(ident)
        locale = row.get("locale")
        if isinstance(locale, str) and locale.strip():
            dims["locale"] = locale.strip()
        cells.append(("text", text.strip(), dims))
    return cells
