from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from public_data_agent.mapping import localized_text
from public_data_agent.registry import Registry

# title > keyword = theme > description. Scores are a sum of these weights,
# one per matched query token per field. That is the whole ranking method.
FIELD_WEIGHTS = {
    "title": 10,
    "keyword": 5,
    "theme": 5,
    "description": 2,
}

TOKEN_RE = re.compile(r"[0-9a-zæøåäöéèü]+", re.IGNORECASE)
QUOTE_RE = re.compile(r'"([^"]+)"')
MIN_TOKEN_LEN = 2
STOP_TOKENS = frozenset({
    "av",
    "er",
    "for",
    "fra",
    "har",
    "i",
    "kan",
    "med",
    "og",
    "om",
    "på",
    "til",
    # Question words and copulas carry no retrieval signal, but AND-decompose
    # makes each one a hard requirement.  Leaving them in is why a natural
    # question ("hvor mange bor det i ...") ranked unrelated records.
    "hva",
    "hvem",
    "hvilke",
    "hvilken",
    "hvilket",
    "hvor",
    "hvordan",
    "hvorfor",
    "den",
    "det",
    "de",
    "en",
    "et",
    "som",
    "vi",
    "jeg",
    "du",
    "meg",
    "man",
    "noen",
    "være",
    "var",
    "vil",
    "skal",
    "bli",
    "blir",
    "ble",
    "gi",
    "finn",
    "finne",
    "vis",
    "hente",
    "sammenlign",
    "mange",
    "mye",
    "ved",
    "under",
    "over",
    "etter",
    "mellom",
    "eller",
    "ikke",
    "sin",
    "sine",
    "der",
    "her",
    "nå",
    "per",
    "siste",
    "mest",
    "minst",
})
QUERY_SYNONYMS = {
    # Norwegian is heavily inflected and compounded; the registry stores the
    # base form.  These map query surface forms onto the stored token so a
    # plural or definite form is not treated as an unmatchable requirement.
    "folketall": "befolkning",
    "folkemengde": "befolkning",
    "innbyggere": "innbygger",
    "innbyggertall": "befolkning",
    "befolkningen": "befolkning",
    "bydeler": "bydel",
    "bydelen": "bydel",
    "bydelene": "bydel",
    "kommuner": "kommune",
    "kommunen": "kommune",
    "kommunene": "kommune",
    "fylker": "fylke",
    "fylket": "fylke",
    "fylkene": "fylke",
    "bor": "befolkning",
    "største": "størst",
    "storste": "størst",
    "vokser": "vekst",
    "voksende": "vekst",
    "veksten": "vekst",
}
QUERY_COMPOUND_SPLITS = {
    "befolkningsvekst": ("befolkning", "vekst"),
    "kraftsituasjonen": ("kraft", "situasjonen"),
}
PUBLISHER_WEIGHT = 5
DISTRIBUTION_WEIGHT = 2
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
        "token overlap; weights title=10, keyword=5, theme=5, description=2"
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


@dataclass
class Coverage:
    requirements: list[str]
    covered: list[str]
    missing: list[str]
    requirement_coverage: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirements": self.requirements,
            "covered": self.covered,
            "missing": self.missing,
            "requirement_coverage": self.requirement_coverage,
        }


@dataclass
class SearchReport:
    hits: list[SearchHit]
    coverage: Coverage
    follow_up: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "returned": len(self.hits),
            "results": [hit.to_dict() for hit in self.hits],
            "coverage": self.coverage.to_dict(),
            "follow_up": self.follow_up,
        }


def tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    return [
        QUERY_SYNONYMS.get(tok, tok)
        for tok in TOKEN_RE.findall(text.casefold())
        if len(tok) >= MIN_TOKEN_LEN and tok not in STOP_TOKENS
    ]


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


def themes_from_payload(payload: dict[str, Any] | None) -> list[str]:
    """Codes and stored labels from harvest theme / losTheme. Nothing invented."""

    if not payload:
        return []
    labels: list[str] = []
    for key in ("theme", "losTheme"):
        value = payload.get(key)
        items = value if isinstance(value, list) else [value] if value else []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("name") or item.get("prefLabel")
            if isinstance(title, dict):
                labels.extend(str(part) for part in title.values() if part)
            elif isinstance(title, str):
                labels.append(title)
            code = item.get("code")
            if isinstance(code, str):
                labels.append(code)
    return labels


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


def titles_from_distributions(distributions: list[Any] | None) -> list[str]:
    if not distributions:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in distributions:
        if not isinstance(item, dict):
            continue
        for text in localized_text(item.get("title")).values():
            value = text.strip()
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


def _token_alts(token: str) -> tuple[str, ...]:
    parts = QUERY_COMPOUND_SPLITS.get(token)
    if parts is None:
        return (token,)
    return (token, *parts)


def _first_stored_token(token: str, field_tokens: set[str]) -> str | None:
    for alt in _token_alts(token):
        if alt in field_tokens:
            return alt
    return None


def score_document(query_tokens: list[str], fields: dict[str, list[str]]) -> list[FieldMatch]:
    matches: list[FieldMatch] = []
    for field_name, weight in FIELD_WEIGHTS.items():
        field_tokens = set(fields.get(field_name, []))
        for token in query_tokens:
            stored = _first_stored_token(token, field_tokens)
            if stored is not None:
                matches.append(FieldMatch(field=field_name, token=stored, weight=weight))
    return matches


def why_summary(matches: list[FieldMatch]) -> str:
    if not matches:
        return "no query tokens matched title, keyword, theme, or description"
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
    match_distribution: bool = False,
) -> list[SearchHit]:
    if limit <= 0:
        return []
    # Narrow to candidates before scoring. None means the filter had nothing
    # to say and every row is scored, which is what happened before it existed.
    candidates = prefilter(registry, query)
    requirements = decompose(query) if decompose_query else []
    if decompose_query and len(requirements) > 1:
        return _search_requirements(registry, requirements, limit=limit, candidates=candidates)
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    return _rank_rows(
        registry,
        query_tokens,
        limit=limit,
        match_distribution=match_distribution,
        candidates=candidates,
    )


def search_report(
    registry: Registry,
    query: str,
    *,
    limit: int = 10,
    decompose_query: bool = True,
    follow_up: bool = True,
) -> SearchReport:
    """Search, then report which requirements the retrieved rows cover.

    Coverage uses stored title, keyword, theme, description, publisher_name,
    and distribution titles. If any requirement is missing, one follow-up
    search runs per missing requirement and new hits are merged.
    """

    requirements = _coverage_requirements(query, decompose_query=decompose_query)
    hits = search(registry, query, limit=limit, decompose_query=decompose_query)
    coverage = assess_coverage(registry, hits, requirements)
    follow: dict[str, Any] | None = None
    if follow_up and coverage.missing:
        added: list[SearchHit] = []
        queries: list[str] = []
        seen = {hit.dataset_id for hit in hits}
        original_tokens = tokenize(query)
        for text in coverage.missing:
            if tokenize(text) == original_tokens:
                continue
            queries.append(text)
            for extra in search(
                registry,
                text,
                limit=limit,
                decompose_query=False,
                match_distribution=True,
            ):
                if extra.dataset_id in seen:
                    continue
                seen.add(extra.dataset_id)
                added.append(extra)
                hits.append(extra)
        kept_ids = set()
        if added:
            hits = _select_hits(hits, limit)
            kept_ids = {hit.dataset_id for hit in hits}
        coverage_after = assess_coverage(registry, hits, requirements)
        if queries:
            follow = {
                "ran": True,
                "reason": "requirement coverage below 1.0 on stored fields of the first-pass hits",
                "queries": queries,
                "added": [
                    {"id": hit.dataset_id, "title": hit.title}
                    for hit in added
                    if hit.dataset_id in kept_ids
                ],
                "skipped_same_query": [
                    text for text in coverage.missing if tokenize(text) == original_tokens
                ],
                "requirement_coverage_before": coverage.requirement_coverage,
                "requirement_coverage_after": coverage_after.requirement_coverage,
            }
        else:
            follow = {
                "ran": False,
                "reason": "missing requirement is the same query; a second pass would repeat it",
                "queries": [],
                "added": [],
            }
        coverage = coverage_after
    return SearchReport(hits=hits, coverage=coverage, follow_up=follow)


def assess_coverage(
    registry: Registry,
    hits: list[SearchHit],
    requirements: list[Requirement],
) -> Coverage:
    texts = [req.text for req in requirements]
    covered: list[str] = []
    missing: list[str] = []
    for req in requirements:
        if any(_hit_covers(registry, hit.dataset_id, req) for hit in hits):
            covered.append(req.text)
        else:
            missing.append(req.text)
    requirement_coverage = (len(covered) / len(requirements)) if requirements else 0.0
    return Coverage(
        requirements=texts,
        covered=covered,
        missing=missing,
        requirement_coverage=requirement_coverage,
    )


def _coverage_requirements(query: str, *, decompose_query: bool) -> list[Requirement]:
    if decompose_query:
        reqs = decompose(query)
        if reqs:
            return reqs
    tokens = tokenize(query)
    return [Requirement(text=token, tokens=(token,)) for token in tokens]


def _hit_covers(registry: Registry, dataset_id: str, req: Requirement) -> bool:
    row = registry.get_dataset(dataset_id)
    if row is None:
        return False
    payload = registry.get_payload(dataset_id) or {}
    keywords = keywords_from_payload(payload)
    themes = themes_from_payload(payload)
    title_i18n = _json_obj(row.get("title_i18n_json"))
    description_i18n = _json_obj(row.get("description_i18n_json"))
    fields = {
        "title": tokenize(" ".join([row.get("title") or "", *title_i18n.values()])),
        "keyword": tokenize(" ".join(keywords)),
        "theme": tokenize(" ".join(themes)),
        "description": tokenize(" ".join([row.get("description") or "", *description_i18n.values()])),
        "distribution": tokenize(
            " ".join(titles_from_distributions(_json_list(row.get("distributions_json"))))
        ),
    }
    return (
        _requirement_matches(
            req.tokens,
            fields,
            row.get("publisher_name"),
            allow_distribution=True,
        )
        is not None
    )


def _search_requirements(
    registry: Registry,
    requirements: list[Requirement],
    *,
    limit: int,
    candidates: set[str] | None = None,
) -> list[SearchHit]:
    """Search each requirement, then keep rows that satisfy every one."""

    hits: list[SearchHit] = []
    req_texts = [req.text for req in requirements]
    for row, fields, keywords, payload in _iter_scored_rows(registry, candidates):
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
                    "title=10, keyword=5, theme=5, description=2"
                ),
                requirements=req_texts,
            )
        )
    return _select_hits(hits, limit)


def _theme_string_matches(query_tokens: list[str], themes: list[str]) -> list[FieldMatch]:
    matches: list[FieldMatch] = []
    seen: set[str] = set()
    weight = FIELD_WEIGHTS["theme"]
    for theme in themes:
        key = theme.casefold()
        if key in seen:
            continue
        seen.add(key)
        theme_tokens = set(tokenize(theme))
        for token in query_tokens:
            stored = _first_stored_token(token, theme_tokens)
            if stored is not None:
                matches.append(FieldMatch(field="theme", token=stored, weight=weight))
    return matches


def _rank_rows(
    registry: Registry,
    query_tokens: list[str],
    *,
    limit: int,
    match_distribution: bool = False,
    candidates: set[str] | None = None,
) -> list[SearchHit]:
    query_text = " ".join(query_tokens)
    theme_hits: list[SearchHit] = []
    other_hits: list[SearchHit] = []
    for row, fields, keywords, payload in _iter_scored_rows(registry, candidates):
        themes = themes_from_payload(payload)
        if any(theme.casefold() == query_text for theme in themes):
            matches = _theme_string_matches(query_tokens, themes)
            if matches:
                theme_hits.append(
                    _hit_from_row(row, payload, keywords, matches, why=why_summary(matches))
                )
            continue
        matches = score_document(query_tokens, fields)
        if not matches:
            matches = (
                _requirement_matches(
                    tuple(query_tokens),
                    fields,
                    row.get("publisher_name"),
                    allow_distribution=match_distribution,
                )
                or []
            )
        if not matches:
            continue
        other_hits.append(_hit_from_row(row, payload, keywords, matches, why=why_summary(matches)))
    hits = theme_hits if theme_hits else other_hits
    return _select_hits(hits, limit)


def _iter_scored_rows(registry: Registry, candidates: set[str] | None = None):
    for row in registry.iter_search_rows(ids=candidates):
        payload = _json_obj(row.get("payload_json"))
        keywords = keywords_from_payload(payload)
        themes = themes_from_payload(payload)
        title_i18n = _json_obj(row.get("title_i18n_json"))
        description_i18n = _json_obj(row.get("description_i18n_json"))
        title_text = " ".join([row.get("title") or "", *title_i18n.values()])
        description_text = " ".join([row.get("description") or "", *description_i18n.values()])
        fields = {
            "title": tokenize(title_text),
            "keyword": tokenize(" ".join(keywords)),
            "theme": tokenize(" ".join(themes)),
            "description": tokenize(description_text),
            "distribution": tokenize(
                " ".join(titles_from_distributions(_json_list(row.get("distributions_json"))))
            ),
        }
        yield row, fields, keywords, payload


def _matched_tokens(hit: SearchHit) -> set[str]:
    return {match.token for match in hit.matches}


def _select_hits(hits: list[SearchHit], limit: int) -> list[SearchHit]:
    selected: list[SearchHit] = []
    remaining = list(hits)
    covered: set[str] = set()
    while remaining and len(selected) < limit:
        remaining.sort(
            key=lambda hit: (
                -len(_matched_tokens(hit) - covered),
                -len(_matched_tokens(hit)),
                -hit.relevance,
                hit.title or "",
                hit.dataset_id,
            )
        )
        pick = remaining.pop(0)
        selected.append(pick)
        covered |= _matched_tokens(pick)
    return selected


def _requirement_satisfied(tokens: tuple[str, ...], matched: set[str]) -> bool:
    return all(any(alt in matched for alt in _token_alts(token)) for token in tokens)


def _requirement_matches(
    tokens: tuple[str, ...],
    fields: dict[str, list[str]],
    publisher_name: str | None,
    *,
    allow_distribution: bool = False,
) -> list[FieldMatch] | None:
    matches = score_document(list(tokens), fields)
    matched = {match.token for match in matches}
    if _requirement_satisfied(tokens, matched):
        return matches
    publisher_tokens = set(tokenize(publisher_name))
    if _requirement_satisfied(tokens, publisher_tokens):
        return [
            FieldMatch(
                field="publisher_name",
                token=_first_stored_token(token, publisher_tokens) or token,
                weight=PUBLISHER_WEIGHT,
            )
            for token in tokens
        ]
    if not allow_distribution:
        return None
    distribution_tokens = set(fields.get("distribution", []))
    if _requirement_satisfied(tokens, distribution_tokens):
        return [
            FieldMatch(
                field="distribution",
                token=_first_stored_token(token, distribution_tokens) or token,
                weight=DISTRIBUTION_WEIGHT,
            )
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
        or "token overlap; weights title=10, keyword=5, theme=5, description=2",
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


def load_prompt_pack(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError(f"{path} has no questions")
    for question in questions:
        if not isinstance(question, dict) or not str(question.get("query") or "").strip():
            raise ValueError(f"{path} has a question without query")
        if question.get("expected") or question.get("dataset_id"):
            raise ValueError(f"{path}: live pack questions must not carry gold ids")
    return payload


def run_search_pack(
    registry: Registry,
    payload: dict[str, Any],
    *,
    limit: int = 10,
    decompose_query: bool = True,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for question in payload["questions"]:
        query = question["query"]
        report = search_report(
            registry, query, limit=limit, decompose_query=decompose_query
        )
        rows.append(
            {
                "id": question.get("id"),
                "query": query,
                "tokens": tokenize(query),
                "returned": len(report.hits),
                "coverage": report.coverage.to_dict(),
                "follow_up": report.follow_up,
                "hits": [
                    {
                        "id": hit.dataset_id,
                        "title": hit.title,
                        "why": hit.why,
                        "matches": [
                            {
                                "field": match.field,
                                "token": match.token,
                                "weight": match.weight,
                            }
                            for match in hit.matches
                        ],
                    }
                    for hit in report.hits
                ],
            }
        )
    return {
        "kind": "live_prompt_pack_report",
        "question_count": len(rows),
        "questions": rows,
    }


# How many candidates the pre-filter hands the scorer. Measured against the
# held-out questions: 2,000 keeps every one of the scorer's top 20, 500 keeps
# 73% of them. The cut has to be generous because BM25 and this scorer do not
# rank the same way -- BM25 only has to put a row somewhere in the candidates,
# not near the top.
PREFILTER_DEPTH = 2000


def _index_body(fields: dict[str, list[str]], publisher: str | None) -> str:
    """The text the pre-filter indexes for one row.

    Built from the tokens the scorer scores, so the filter cannot drop a row the
    scorer would have matched. Indexing less is the failure mode: title and
    description alone kept only 80% of the scorer's top 20, because the scorer
    also matches keywords, themes and publisher.
    """

    parts = [token for tokens in fields.values() for token in tokens]
    parts.extend(tokenize(publisher))
    return " ".join(parts)


def build_search_index(registry: Registry, *, progress=None) -> dict[str, int]:
    """Rebuild the lexical pre-filter over every dataset."""

    log = progress or (lambda _message: None)
    registry.conn.execute("DELETE FROM search_index")
    batch: list[tuple[str, str]] = []
    total = 0
    for row, fields, _keywords, _payload in _iter_scored_rows(registry):
        batch.append((row["id"], _index_body(fields, row.get("publisher_name"))))
        total += 1
        if len(batch) >= 2000:
            registry.conn.executemany("INSERT INTO search_index VALUES (?, ?)", batch)
            batch = []
            log(f"indexed {total}")
    if batch:
        registry.conn.executemany("INSERT INTO search_index VALUES (?, ?)", batch)
    registry.conn.execute(
        "INSERT OR REPLACE INTO search_index_state (id, dataset_count, built_at) "
        "VALUES (1, ?, ?)",
        (total, datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    registry.conn.commit()
    log(f"indexed {total}")
    return {"indexed": total}


def index_is_current(registry: Registry) -> bool:
    """Whether the pre-filter covers every dataset the search would score."""

    try:
        state = registry.conn.execute(
            "SELECT dataset_count FROM search_index_state WHERE id = 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if state is None:
        return False
    datasets = registry.conn.execute("SELECT COUNT(*) AS n FROM datasets").fetchone()
    return int(state["dataset_count"]) == int(datasets["n"])


def prefilter(
    registry: Registry, query: str, *, depth: int = PREFILTER_DEPTH
) -> set[str] | None:
    """Candidate ids for a query, or None when the filter has nothing to say.

    None means score every row, which is what the search did before this
    existed: a stale or unbuilt index, a query with no tokens, or a query that
    matches nothing must not be confused with a query that legitimately has no
    answer. Returning an empty set for those would answer nothing at all.

    Matches are by prefix and include the compound splits `score_document`
    accepts, so the candidate set is a superset of what the scorer would match
    on a full scan -- up to the depth cut.
    """

    if not index_is_current(registry):
        return None
    tokens: list[str] = []
    for token in tokenize(query):
        tokens.extend(_token_alts(token))
    if not tokens:
        return None
    match = " OR ".join(f'"{token}"*' for token in dict.fromkeys(tokens))
    try:
        rows = registry.conn.execute(
            "SELECT dataset_id FROM search_index WHERE search_index MATCH ? "
            "ORDER BY bm25(search_index) LIMIT ?",
            (match, depth),
        ).fetchall()
    except sqlite3.OperationalError:
        # No index in this database, or a query FTS5 will not parse. Either way
        # the full scan still answers correctly, only slower.
        return None
    if not rows:
        return None
    return {row["dataset_id"] for row in rows}
