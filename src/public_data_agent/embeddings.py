"""Provider-neutral embedding retrieval primitives."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Protocol, Sequence


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class EmbeddedCandidate:
    dataset_id: str
    text: str
    vector: tuple[float, ...]


def rank_candidates(
    query: str,
    candidates: Sequence[EmbeddedCandidate],
    provider: EmbeddingProvider,
    *,
    limit: int = 10,
) -> list[tuple[EmbeddedCandidate, float]]:
    """Rank candidates by cosine similarity; values are not factual answers."""
    if not candidates:
        return []
    query_vector = provider.embed([query])[0]
    scored = [(candidate, _cosine(query_vector, candidate.vector)) for candidate in candidates]
    scored.sort(key=lambda item: (-item[1], item[0].dataset_id))
    return scored[:limit]


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions must match")
    denominator = sqrt(sum(value * value for value in left) * sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


import array
import hashlib
import json
from typing import Any, Callable, Iterable

# Batch size for provider calls. Large enough to keep the round trips down,
# small enough that one failure does not lose much work.
BATCH_SIZE = 100
# Reciprocal-rank-fusion constant. The standard value; it damps the influence
# of any single ranker's top position so neither list can dominate outright.
RRF_K = 60


def embedding_text(row: dict[str, Any]) -> str:
    """The text embedded for one dataset. Stored fields only, nothing invented."""

    parts: list[str] = []
    for key in ("title", "description"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    publisher = row.get("publisher_name")
    if isinstance(publisher, str) and publisher.strip():
        parts.append(publisher.strip())
    # Keywords and themes live in the harvested payload, not on the dataset row.
    # They carry the vocabulary a title often lacks -- SSB files a table titled
    # "Personer i arbeidsstyrken" under the subject "Arbeidsledighet" -- so the
    # embedded text uses the same fields the lexical ranker scores.
    payload = row.get("payload_json")
    if isinstance(payload, str) and payload.strip():
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            from public_data_agent.search import keywords_from_payload, themes_from_payload

            parts.extend(keywords_from_payload(obj))
            parts.extend(themes_from_payload(obj))
    return "\n".join(parts)[:4000]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def pack(vector: Iterable[float]) -> bytes:
    return array.array("f", vector).tobytes()


def unpack(blob: bytes) -> array.array:
    out = array.array("f")
    out.frombytes(blob)
    return out


def build_index(
    registry: Any,
    provider: EmbeddingProvider,
    *,
    model: str,
    limit: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """Embed dataset text into the registry. Incremental by text hash.

    Rows whose text has not changed are skipped, so re-running after a harvest
    costs only the rows that actually moved.
    """

    rows = registry.conn.execute(
        """
        SELECT d.id, d.title, d.description, d.publisher_name, p.payload_json
        FROM datasets d
        LEFT JOIN harvested_payloads p ON p.dataset_id = d.id
        ORDER BY d.id
        """
    ).fetchall()
    existing = registry.embedded_hashes()
    pending: list[tuple[str, str, str]] = []
    skipped = 0
    for row in rows:
        record = dict(row)
        text = embedding_text(record)
        if not text.strip():
            continue
        digest = text_hash(text)
        if existing.get(record["id"]) == digest:
            skipped += 1
            continue
        pending.append((record["id"], text, digest))
        if limit is not None and len(pending) >= limit:
            break

    embedded = 0
    failed = 0
    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start : start + BATCH_SIZE]
        # One flaky batch should not end an index build. Work already committed
        # stays committed, and the next run picks up what is still missing
        # because progress is tracked by text hash rather than by position.
        try:
            vectors = provider.embed([text for _id, text, _digest in batch])
        except Exception as exc:
            failed += len(batch)
            if progress:
                progress(f"batch at {start} failed, continuing: {exc}")
            continue
        if len(vectors) != len(batch):
            raise ValueError("embedding provider returned the wrong number of vectors")
        with registry.deferred_commit():
            for (dataset_id, _text, digest), vector in zip(batch, vectors):
                registry.upsert_embedding(
                    dataset_id=dataset_id,
                    model=model,
                    vector=pack(vector),
                    dim=len(vector),
                    text_hash=digest,
                )
        embedded += len(batch)
        if progress:
            progress(f"embedded {embedded}/{len(pending)}")
    return {
        "embedded": embedded,
        "skipped": skipped,
        "failed": failed,
        "candidates": len(pending),
    }


def semantic_ranking(
    registry: Any,
    provider: EmbeddingProvider,
    query: str,
    *,
    limit: int = 50,
    model: str | None = None,
) -> list[tuple[str, float]]:
    """Rank stored datasets by cosine similarity to the query.

    Returns dataset ids and scores. A score is a ranking signal, never evidence
    about the data itself.
    """

    query_vector = provider.embed([query])[0]
    dim = len(query_vector)
    rows = [(did, blob) for did, stored_dim, blob in registry.iter_embeddings(model) if stored_dim == dim]
    if not rows:
        return []

    try:
        import numpy as np
    except ImportError:  # pragma: no cover - numpy ships with matplotlib
        return _semantic_ranking_pure(query_vector, rows, limit)

    # One matrix multiply beats a Python loop per row by orders of magnitude:
    # scoring the whole corpus per query is otherwise seconds, not milliseconds.
    matrix = np.frombuffer(b"".join(blob for _did, blob in rows), dtype=np.float32).reshape(len(rows), dim)
    query = np.asarray(query_vector, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1) * float(np.linalg.norm(query))
    with np.errstate(divide="ignore", invalid="ignore"):
        scores = np.where(norms > 0, matrix @ query / norms, 0.0)
    top = np.argsort(-scores, kind="stable")[:limit]
    return [(rows[int(i)][0], float(scores[int(i)])) for i in top]


def _semantic_ranking_pure(
    query_vector: Sequence[float], rows: list[tuple[str, bytes]], limit: int
) -> list[tuple[str, float]]:
    """Fallback used only when numpy is unavailable. Same result, slower."""

    norm = sqrt(sum(value * value for value in query_vector))
    if not norm:
        return []
    scored: list[tuple[str, float]] = []
    for dataset_id, blob in rows:
        vector = unpack(blob)
        dot = sum(a * b for a, b in zip(query_vector, vector))
        magnitude = sqrt(sum(b * b for b in vector))
        if magnitude:
            scored.append((dataset_id, dot / (norm * magnitude)))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored[:limit]


def fuse(
    lexical: list[str],
    semantic: list[str],
    *,
    limit: int = 10,
    k: int = RRF_K,
) -> list[str]:
    """Reciprocal rank fusion of two ranked id lists.

    Neither ranker's scores are comparable to the other's, so rank position is
    fused rather than score. An id both rankers like outranks one that only
    appears near the top of a single list.
    """

    scores: dict[str, float] = {}
    for ranked in (lexical, semantic):
        for position, dataset_id in enumerate(ranked):
            scores[dataset_id] = scores.get(dataset_id, 0.0) + 1.0 / (k + position + 1)
    order = {dataset_id: position for position, dataset_id in enumerate(lexical)}
    return sorted(
        scores,
        key=lambda dataset_id: (-scores[dataset_id], order.get(dataset_id, len(order))),
    )[:limit]
