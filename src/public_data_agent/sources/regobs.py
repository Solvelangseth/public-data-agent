from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "regobs"
SOURCE_NAME = "NVE RegObs KDV"
SWAGGER_URL = "https://api.regobs.no/v5/swagger/docs/V5"
LIST_URL = "https://api.regobs.no/v5/KdvElements"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed KdvRepositories key on the official NVE RegObs "
    f"KdvElements GET, capped at {DEFAULT_MAX_ITEMS} tables"
)
REGOBS_RPS = 2.0
REGOBS_BURST = 4
HOST = "api.regobs.no"
PATH_PREFIX = "/v5/KdvElements"
REPOS_KEY = "KdvRepositories"
NAME_FIELDS = ("Name", "Id")


class RegobsSource(SourceBase):
    """Replaceable ingest adapter for NVE RegObs KDV tables.

    Listing copies printed `KdvRepositories` keys the official
    `/v5/KdvElements` GET prints. That path is an untemplated collection
    GET in the official RegObs swagger.     It skips empty keys,
    empty lists, and non-list repositories. Native ids are those printed keys so
    `Dirt_DangerSignKDV` stays distinct from `Dirt_ActivityInfluencedKDV`.
    Native URIs append the printed key as a fragment so each
    repository stays distinct. Fetch still GETs the printed
    KdvElements path. This first slice stays
    inside that document and caps the walk. Account paths that print
    HTTP 401 stay unused. This is not NVE Magasinstatistikk
    (`--source nve`).
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (SWAGGER_URL, LIST_URL)
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
            limiter=RateLimiter(REGOBS_RPS, REGOBS_BURST),
            timeout=60.0,
        )
        self._listed: list[tuple[str, str]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._listed_repos()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for ident, href in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=href,
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident, href = _href_for_ref(self._listed_repos(), ref)
        payload = {
            "id": ident,
            "uri": href,
            "title": {"en": ident},
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [self.list_url],
                    "downloadURL": [self.list_url],
                }
            ],
            "landingPage": [SWAGGER_URL],
            "regobs_repo_id": ident,
            "regobs_repo_href": self.list_url,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ident,
            source_native_uri=href,
            fetched_from=self.list_url,
            payload=payload,
        )

    def _listed_repos(self) -> list[tuple[str, str]]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(f"RegObs KdvElements catalog failed for {self.list_url}: {exc}") from exc
        listed = printed_repositories(body, self.list_url)
        if not listed:
            raise SourceError(f"RegObs KdvElements catalog printed no repositories: {self.list_url}")
        self._listed = listed
        return listed


def printed_repositories(body: Any, list_url: str) -> list[tuple[str, str]]:
    """Copy printed KdvRepositories keys the KdvElements GET prints."""

    if not isinstance(body, dict):
        raise SourceError("RegObs KdvElements catalog is not a JSON object")
    repos = body.get(REPOS_KEY)
    if not isinstance(repos, dict):
        raise SourceError("RegObs KdvElements catalog has no printed KdvRepositories object")
    listed: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, items in repos.items():
        if not isinstance(key, str) or not key.strip():
            continue
        if not isinstance(items, list) or not items:
            continue
        ident = key.strip()
        if ident in seen:
            continue
        seen.add(ident)
        listed.append((ident, f"{list_url}#{ident}"))
    return listed


def is_regobs_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def regobs_table_id(access_path: str, source_native_id: str | None = None) -> str:
    if isinstance(source_native_id, str) and source_native_id.strip():
        return source_native_id.strip()
    path = urlsplit(access_path).path.rstrip("/")
    ident = path.split("/")[-1]
    return ident or "regobs"


def cells_from_regobs(
    payload: Any,
    *,
    table_id: str | None = None,
) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed RegObs KDV rows into observation cells.

    The matching `KdvRepositories` list keeps printed `Name` when present,
    otherwise `Id`. Other scalars stay as dimensions. Nested objects and
    arrays are not copied. Nothing is invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("regobs payload is not a JSON object")
    repos = payload.get(REPOS_KEY)
    if not isinstance(repos, dict):
        raise ValueError("regobs payload printed no KdvRepositories object")
    if table_id and table_id in repos and isinstance(repos[table_id], list):
        blocks = [repos[table_id]]
    else:
        blocks = [items for items in repos.values() if isinstance(items, list)]
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for block in blocks:
        for item in block:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
            elif _is_scalar(item) and item is not None:
                cells.append(("value", item, {}))
    if not cells:
        raise ValueError("regobs payload printed no collection members")
    return cells


def _href_for_ref(listed: list[tuple[str, str]], ref: DatasetRef) -> tuple[str, str]:
    for ident, href in listed:
        if ident == ref.source_native_id:
            return ident, href
        if href == ref.source_native_uri and ident == ref.source_native_id:
            return ident, href
    if ref.source_native_id:
        for ident, href in listed:
            if ident == ref.source_native_id:
                return ident, href
    raise SourceError(
        f"RegObs KdvElements catalog has no printed repository matching {ref.source_native_id}"
    )


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
