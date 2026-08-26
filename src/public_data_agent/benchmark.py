from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from public_data_agent.http_util import HttpClient, RateLimiter, SourceHttpError
from public_data_agent.registry import Registry
from public_data_agent.search import keywords_from_payload, search, tokenize

DATANORGE_SEARCH = "https://search.api.fellesdatakatalog.digdir.no/search/datasets"
DATANORGE_RATE = 10 / 60
DEFAULT_QUESTIONS = Path("data/benchmark_questions.json")

ProgressFn = Callable[[str], None]


def load_questions(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError(f"{path} has no questions")
    return payload


def validate_questions(registry: Registry, payload: dict[str, Any]) -> None:
    """Every expected id must exist. Every reason must match a stored field."""

    for question in payload["questions"]:
        for item in question["expected"]:
            dataset_id = item["dataset_id"]
            row = registry.get_dataset(dataset_id)
            if row is None:
                raise ValueError(f"{question['id']}: missing dataset {dataset_id}")
            payload_json = registry.get_payload(dataset_id) or {}
            for reason in item["reasons"]:
                if not _reason_holds(row, payload_json, reason):
                    raise ValueError(
                        f"{question['id']}: reason {reason} does not match {dataset_id}"
                    )


def run_benchmark(
    registry: Registry,
    payload: dict[str, Any],
    *,
    baseline: str | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    validate_questions(registry, payload)
    log = progress or (lambda _message: None)
    our_rows: list[dict[str, Any]] = []
    for question in payload["questions"]:
        hits = search(registry, question["query"], limit=10)
        ranked = [hit.dataset_id for hit in hits]
        our_rows.append(_score_question(question, ranked, registry))
        log(f"scored {question['id']} hits={len(ranked)}")

    result: dict[str, Any] = {
        "question_count": len(payload["questions"]),
        "our_search": _aggregate(our_rows),
        "questions": our_rows,
        "datanorge_baseline": None,
    }

    if baseline == "datanorge":
        result["datanorge_baseline"] = _run_datanorge_baseline(
            registry, payload["questions"], progress=log
        )
    elif baseline:
        raise ValueError(f"unknown baseline {baseline}")
    return result


def _score_question(
    question: dict[str, Any],
    ranked: list[str],
    registry: Registry | None,
) -> dict[str, Any]:
    gold = [item["dataset_id"] for item in question["expected"]]
    gold_set = set(gold)
    return {
        "id": question["id"],
        "kind": question["kind"],
        "query": question["query"],
        "expected": gold,
        "ranked": ranked,
        "recall_at_5": _recall_at(ranked, gold_set, 5),
        "recall_at_10": _recall_at(ranked, gold_set, 10),
        "mrr": _mrr(ranked, gold_set),
        "requirement_coverage_at_5": _requirement_coverage(question, ranked, registry, 5),
        "requirement_coverage_at_10": _requirement_coverage(question, ranked, registry, 10),
    }


def _recall_at(ranked: list[str], gold: set[str], k: int) -> float:
    if not gold:
        return 0.0
    return len(set(ranked[:k]) & gold) / len(gold)


def _mrr(ranked: list[str], gold: set[str]) -> float:
    for index, dataset_id in enumerate(ranked, start=1):
        if dataset_id in gold:
            return 1.0 / index
    return 0.0


def _requirement_coverage(
    question: dict[str, Any],
    ranked: list[str],
    registry: Registry | None,
    k: int,
) -> float:
    requirements = question.get("requirements") or []
    if not requirements:
        return 0.0
    top = ranked[:k]
    covered = 0
    for req in requirements:
        if any(_id_covers(registry, dataset_id, req) for dataset_id in top):
            covered += 1
    return covered / len(requirements)


def _id_covers(registry: Registry | None, dataset_id: str, req: dict[str, Any]) -> bool:
    if req["kind"] == "gold_id":
        return dataset_id == req["dataset_id"]
    if registry is None:
        return False
    row = registry.get_dataset(dataset_id)
    if row is None:
        return False
    token = (req.get("token") or "").casefold()
    field = req.get("field")
    if field == "publisher_name":
        return token in (row.get("publisher_name") or "").casefold()
    payload = registry.get_payload(dataset_id) or {}
    keywords = keywords_from_payload(payload)
    if field == "title":
        return token in tokenize(row.get("title"))
    if field == "keyword":
        return token in tokenize(" ".join(keywords))
    if field == "description":
        return token in tokenize(row.get("description"))
    if field == "theme":
        return token in tokenize(" ".join(_theme_labels(payload)))
    blob = " ".join(
        [
            row.get("title") or "",
            row.get("description") or "",
            " ".join(keywords),
        ]
    )
    return token in tokenize(blob)


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def mean(key: str) -> float:
        if not rows:
            return 0.0
        return sum(row[key] for row in rows) / len(rows)

    by_kind: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_kind.setdefault(row["kind"], []).append(row)
    return {
        "recall_at_5": mean("recall_at_5"),
        "recall_at_10": mean("recall_at_10"),
        "mrr": mean("mrr"),
        "requirement_coverage_at_5": mean("requirement_coverage_at_5"),
        "requirement_coverage_at_10": mean("requirement_coverage_at_10"),
        "by_kind": {
            kind: {
                "n": len(group),
                "recall_at_5": sum(row["recall_at_5"] for row in group) / len(group),
                "recall_at_10": sum(row["recall_at_10"] for row in group) / len(group),
                "mrr": sum(row["mrr"] for row in group) / len(group),
            }
            for kind, group in sorted(by_kind.items())
        },
    }


def _run_datanorge_baseline(
    registry: Registry,
    questions: list[dict[str, Any]],
    *,
    progress: ProgressFn,
) -> dict[str, Any]:
    client = HttpClient(limiter=RateLimiter(DATANORGE_RATE, 1), timeout=30.0, max_retries=3)
    rows: list[dict[str, Any]] = []
    skipped = None
    for question in questions:
        try:
            ranked = _datanorge_ranked(client, question["query"])
        except SourceHttpError as exc:
            skipped = {
                "reason": "Search API error; remaining questions not scored",
                "status": exc.status,
                "query": question["query"],
                "completed": len(rows),
            }
            progress(f"datanorge baseline stopped after {len(rows)}: HTTP {exc.status}")
            break
        rows.append(_score_question(question, ranked, registry))
        progress(f"datanorge {question['id']} hits={len(ranked)}")
    result: dict[str, Any] = {
        "endpoint": DATANORGE_SEARCH,
        "rate_limit_per_minute": 10,
        "completed": len(rows),
        "skipped": skipped,
    }
    if rows:
        result["scores"] = _aggregate(rows)
        result["questions"] = rows
    return result


def _datanorge_ranked(client: HttpClient, query: str) -> list[str]:
    body = client.post_json(DATANORGE_SEARCH, {"query": query, "size": 10})
    hits = body.get("hits") if isinstance(body, dict) else None
    if not isinstance(hits, list):
        return []
    ranked: list[str] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        fdk_id = hit.get("id")
        if isinstance(fdk_id, str) and fdk_id:
            ranked.append(f"datanorge:{fdk_id}")
    return ranked


def _reason_holds(row: dict[str, Any], payload: dict[str, Any], reason: dict[str, Any]) -> bool:
    field = reason["field"]
    stored = reason["stored"]
    if field == "title":
        return stored == row.get("title") or stored.casefold() in (row.get("title") or "").casefold()
    if field == "publisher_name":
        return stored == row.get("publisher_name")
    if field == "keyword":
        keywords = keywords_from_payload(payload)
        return any(stored.casefold() == item.casefold() or stored.casefold() in item.casefold() for item in keywords)
    if field == "theme":
        themes = _theme_labels(payload)
        return any(stored.casefold() == item.casefold() for item in themes)
    if field == "description":
        return stored.casefold() in (row.get("description") or "").casefold()
    return False


def _theme_labels(payload: dict[str, Any]) -> list[str]:
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
