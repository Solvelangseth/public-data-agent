from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from public_data_agent.mapping import localized_text
from public_data_agent.registry import Registry

# title > keyword > description. Scores are a sum of these weights, one per
# matched query token per field. That is the whole ranking method.
FIELD_WEIGHTS = {
    "title": 10,
    "keyword": 5,
    "description": 2,
}

TOKEN_RE = re.compile(r"[0-9a-zæøåäöéèü]+", re.IGNORECASE)
QUOTE_RE = re.compile(r'"([^"]+)"')
MIN_TOKEN_LEN = 2
PUBLISHER_WEIGHT = 5
VARIABLES_UNKNOWN_REASON = (
    "no variable or column list is stored in the registry or harvested payload"
)


@dataclass(frozen=True)
class Requirement:
    text: str
    tokens: tuple[str, ...]


@dataclass
class FieldMatch:
    field: str
    token: str
    weight: int


@dataclass
class SearchHit:
    dataset_id: str
    title: str | None
    relevance: int
    matches: list[FieldMatch]
    why: str
    publisher: dict[str, Any] | None
    license: str | None
    licenses: list[str]
    access_path: str | None
    access_rights: str | None
    access_rights_uri: str | None
    distributions: list[dict[str, Any]]
    issued: str | None
    modified: str | None
    temporal: list[dict[str, Any]]
    spatial: list[dict[str, Any]]
    variables: dict[str, Any]
    keywords: list[str]
    source_native_uri: str | None
    landing_pages: list[str]
    missing_fields: dict[str, str]
    ranking_method: str = (
        "token overlap; weights title=10, keyword=5, description=2"
    )
    requirements: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.dataset_id,
            "title": self.title,
            "relevance": self.relevance,
            "why": {
                "summary": self.why,
                "matches": [
                    {"field": m.field, "token": m.token, "weight": m.weight}
                    for m in self.matches
                ],
                "method": self.ranking_method,
                "requirements": self.requirements,
            },
            "publisher": self.publisher,
            "license": self.license,
            "licenses": self.licenses,
            "access": {
                "access_path": self.access_path,
                "access_rights": self.access_rights,
                "access_rights_uri": self.access_rights_uri,
                "distributions": self.distributions,
            },
            "time": {
                "issued": self.issued,
                "modified": self.modified,
                "temporal": self.temporal,
            },
            "geography": self.spatial,
            "variables": self.variables,
            "keywords": self.keywords,
            "original_link": {
                "source_native_uri": self.source_native_uri,
                "landing_pages": self.landing_pages,
            },
            "missing_fields": self.missing_fields,
        }


def tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    return [tok for tok in TOKEN_RE.findall(text.casefold()) if len(tok) >= MIN_TOKEN_LEN]


def decompose(query: str) -> list[Requirement]:
    """Split a query into independent requirements.

    Quoted phrases stay one requirement. Remaining tokens are each one
    requirement. This does not change token-overlap weights.
    """

    requirements: list[Requirement] = []
    remainder = query
    for match in QUOTE_RE.finditer(query):
        phrase = match.group(1).strip()
        tokens = tuple(tokenize(phrase))
        if tokens:
            requirements.append(Requirement(text=phrase, tokens=tokens))
        remainder = remainder.replace(match.group(0), " ", 1)
    for token in tokenize(remainder):
        requirements.append(Requirement(text=token, tokens=(token,)))
    return requirements


def keywords_from_payload(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    raw = payload.get("keyword")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        texts = localized_text(item).values() if not isinstance(item, str) else [item]
        for text in texts:
            for part in re.split(r"\s*,\s*", text):
                value = part.strip()
                if value and value not in seen:
                    seen.add(value)
                    out.append(value)
    return out


def variables_from_stored(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Variables are unknown unless the harvested payload has an explicit list.

    We do not treat keywords, formats, or description nouns as variables.
    """

    if payload:
        for key in ("variables", "variableList", "variable_list"):
            value = payload.get(key)
            if isinstance(value, list) and value:
                names = [item for item in value if isinstance(item, str) and item.strip()]
                if names:
                    return {"status": "known", "values": names}
    return {"status": "unknown", "reason": VARIABLES_UNKNOWN_REASON}


def score_document(query_tokens: list[str], fields: dict[str, list[str]]) -> list[FieldMatch]:
    matches: list[FieldMatch] = []
    for field_name, weight in FIELD_WEIGHTS.items():
        field_tokens = set(fields.get(field_name, []))
        for token in query_tokens:
            if token in field_tokens:
                matches.append(FieldMatch(field=field_name, token=token, weight=weight))
    return matches


def why_summary(matches: list[FieldMatch]) -> str:
    if not matches:
        return "no query tokens matched title, keyword, or description"
    by_field: dict[str, list[str]] = {}
    for match in matches:
        by_field.setdefault(match.field, []).append(match.token)
    parts = [f"{field} matched {', '.join(tokens)}" for field, tokens in by_field.items()]
    return "; ".join(parts)


def search(
    registry: Registry,
    query: str,
    *,
    limit: int = 10,
    decompose_query: bool = True,
) -> list[SearchHit]:
    if limit <= 0:
        return []
    requirements = decompose(query) if decompose_query else []
    if decompose_query and len(requirements) > 1:
        return _search_requirements(registry, requirements, limit=limit)
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    return _rank_rows(registry, query_tokens, limit=limit)


def _search_requirements(
    registry: Registry,
    requirements: list[Requirement],
    *,
    limit: int,
) -> list[SearchHit]:
    """Search each requirement, then keep rows that satisfy every one."""

    hits: list[SearchHit] = []
    req_texts = [req.text for req in requirements]
    for row, fields, keywords, payload in _iter_scored_rows(registry):
        combined: list[FieldMatch] = []
        failed = False
        for req in requirements:
            matches = _requirement_matches(req.tokens, fields, row.get("publisher_name"))
            if matches is None:
                failed = True
                break
            combined.extend(matches)
        if failed:
            continue
        hits.append(
            _hit_from_row(
                row,
                payload,
                keywords,
                combined,
                why=_requirement_why(req_texts, combined),
                ranking_method=(
                    "decompose AND requirements; each scored with token overlap "
                    "title=10, keyword=5, description=2"
                ),
                requirements=req_texts,
            )
        )
    hits.sort(key=lambda hit: (-hit.relevance, hit.title or "", hit.dataset_id))
    return hits[:limit]


def _rank_rows(
    registry: Registry,
    query_tokens: list[str],
    *,
    limit: int,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for row, fields, keywords, payload in _iter_scored_rows(registry):
        matches = score_document(query_tokens, fields)
        if not matches:
            continue
        hits.append(_hit_from_row(row, payload, keywords, matches, why=why_summary(matches)))
    hits.sort(key=lambda hit: (-hit.relevance, hit.title or "", hit.dataset_id))
    return hits[:limit]


def _iter_scored_rows(registry: Registry):
    for row in registry.iter_search_rows():
        payload = _json_obj(row.get("payload_json"))
        keywords = keywords_from_payload(payload)
        title_i18n = _json_obj(row.get("title_i18n_json"))
        description_i18n = _json_obj(row.get("description_i18n_json"))
        title_text = " ".join([row.get("title") or "", *title_i18n.values()])
        description_text = " ".join([row.get("description") or "", *description_i18n.values()])
        fields = {
            "title": tokenize(title_text),
            "keyword": tokenize(" ".join(keywords)),
            "description": tokenize(description_text),
        }
        yield row, fields, keywords, payload


def _requirement_matches(
    tokens: tuple[str, ...],
    fields: dict[str, list[str]],
    publisher_name: str | None,
) -> list[FieldMatch] | None:
    matches = score_document(list(tokens), fields)
    matched = {match.token for match in matches}
    if set(tokens) <= matched:
        return matches
    publisher_tokens = set(tokenize(publisher_name))
    if set(tokens) <= publisher_tokens:
        return [
            FieldMatch(field="publisher_name", token=token, weight=PUBLISHER_WEIGHT)
            for token in tokens
        ]
    return None


def _requirement_why(req_texts: list[str], matches: list[FieldMatch]) -> str:
    joined = " AND ".join(req_texts)
    return f"requirements {joined}; {why_summary(matches)}"


def _hit_from_row(
    row: dict[str, Any],
    payload: dict[str, Any],
    keywords: list[str],
    matches: list[FieldMatch],
    *,
    why: str,
    ranking_method: str | None = None,
    requirements: list[str] | None = None,
) -> SearchHit:
    publisher = _json_obj(row.get("publisher_json")) or None
    return SearchHit(
        dataset_id=row["id"],
        title=row.get("title"),
        relevance=sum(match.weight for match in matches),
        matches=matches,
        why=why,
        publisher=publisher,
        license=row.get("license"),
        licenses=_json_list(row.get("licenses_json")),
        access_path=row.get("access_path"),
        access_rights=row.get("access_rights"),
        access_rights_uri=row.get("access_rights_uri"),
        distributions=_json_list(row.get("distributions_json")),
        issued=row.get("issued"),
        modified=row.get("modified"),
        temporal=_json_list(row.get("temporal_json")),
        spatial=_json_list(row.get("spatial_json")),
        variables=variables_from_stored(payload),
        keywords=keywords,
        source_native_uri=row.get("source_native_uri"),
        landing_pages=_json_list(row.get("landing_pages_json")),
        missing_fields=_json_obj(row.get("missing_fields_json")),
        ranking_method=ranking_method
        or "token overlap; weights title=10, keyword=5, description=2",
        requirements=requirements,
    )


def _json_obj(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    return []
