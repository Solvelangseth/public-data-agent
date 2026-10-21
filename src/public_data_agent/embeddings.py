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
import re
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
    # Scoped to this model: another model having embedded the same text is
    # not evidence that this one has.
    existing = registry.embedded_hashes(model)
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

    # Which index to read. Selecting by dimension alone was enough while only
    # one model was stored at each width, and stops being enough the moment two
    # are: `text-embedding-3-large` truncated to 1536 would be compared against
    # `text-embedding-3-small` vectors, which is meaningless and does not error.
    if model is None:
        model = getattr(provider, "model", None)
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
    lexical_weight: float = 1.0,
) -> list[str]:
    """Reciprocal rank fusion of two ranked id lists.

    Neither ranker's scores are comparable to the other's, so rank position is
    fused rather than score. An id both rankers like outranks one that only
    appears near the top of a single list.

    `lexical_weight` damps one side. At 1.0 every lexical hit outscores every
    semantic hit past roughly its own length, so a lexical list of 15 pushes
    the semantic list's last 15 places out of a 50-item output: `regnskapstall
    aksjeselskap` is ranked 41 and 42 semantically and survives in no fused
    list. A short lexical list means few terms matched, which is weak evidence,
    and weighting it by how much of its budget it filled is one way to say so.
    """

    scores: dict[str, float] = {}
    for weight, ranked in ((lexical_weight, lexical), (1.0, semantic)):
        for position, dataset_id in enumerate(ranked):
            scores[dataset_id] = scores.get(dataset_id, 0.0) + weight / (k + position + 1)
    order = {dataset_id: position for position, dataset_id in enumerate(lexical)}
    return sorted(
        scores,
        key=lambda dataset_id: (-scores[dataset_id], order.get(dataset_id, len(order))),
    )[:limit]


# Norwegian interrogatives and the auxiliaries that follow them. A query
# carrying these is someone asking a question; one without is someone naming a
# subject, and the two are best retrieved differently.
QUESTION_MARKERS = frozenset({
    "hva", "hvem", "hvilke", "hvilken", "hvilket", "hvor", "hvordan", "hvorfor",
    "når", "er", "har", "kan", "blir", "koster", "finnes", "ligger", "går",
    "mange", "mye", "stor", "stort", "gode", "høyt",
})


def looks_like_a_question(query: str) -> bool:
    """Whether a query is phrased as a question rather than as a subject.

    The distinction is worth drawing because the two retrieve differently.
    Measured against the gold set, adding lexical ranking to semantic is worth
    +24 points of recall on a query that names a subject ("byggekostnader") and
    costs 5 points on one that asks a question ("hva koster en bolig i Oslo"),
    where the lexical half mostly contributes noise from function words.
    """

    words = [w for w in re.findall(r"[0-9a-zæøåäöéèü]+", query.casefold()) if w]
    if not words:
        return False
    # A question mark settles it, and so does opening with an interrogative.
    if "?" in query or words[0] in QUESTION_MARKERS:
        return True
    # Otherwise it takes more than one marker, so a subject that happens to
    # contain one common word is not mistaken for a question.
    return sum(1 for w in words if w in QUESTION_MARKERS) >= 2


def rank_for_query(
    lexical: list[str],
    semantic: list[str],
    query: str,
    *,
    limit: int = 10,
    lexical_weight: float = 1.0,
) -> list[str]:
    """Rank by whichever combination suits how the query is phrased.

    A question is answered from the semantic ranking alone; a subject is
    answered from both fused. This is a measured choice, not a preference --
    see `looks_like_a_question`.
    """

    if looks_like_a_question(query):
        return semantic[:limit]
    return fuse(lexical, semantic, limit=limit, lexical_weight=lexical_weight)


def export_texts(registry: Any, path: Any, *, limit: int | None = None) -> dict[str, int]:
    """Write the text each dataset would be embedded as, for embedding elsewhere.

    Building an index of 13,281 texts on a laptop CPU is hours; on a rented GPU
    it is minutes. Only the bulk build needs to move -- a query is one short
    text and embeds fast anywhere -- so this exports what to embed and
    `import_vectors` takes the result back.

    The `text_hash` travels with each row so an import stays incremental: a
    vector is only accepted for text that still hashes the same.
    """

    import json
    from pathlib import Path

    out = Path(path)
    written = 0
    with out.open("w", encoding="utf-8") as handle:
        for row in registry.iter_datasets() if hasattr(registry, "iter_datasets") else _all_datasets(registry):
            text = embedding_text(row)
            if not text:
                continue
            handle.write(json.dumps(
                {"dataset_id": row["id"], "text": text, "text_hash": text_hash(text)},
                ensure_ascii=False,
            ) + "\n")
            written += 1
            if limit is not None and written >= limit:
                break
    return {"written": written, "path": str(out)}


def _all_datasets(registry: Any):
    for row in registry.conn.execute("SELECT * FROM datasets ORDER BY id"):
        yield dict(row)


def import_vectors(registry: Any, path: Any, *, model: str) -> dict[str, int]:
    """Load vectors embedded elsewhere, under their own model name.

    A vector is refused when the dataset's text no longer hashes to what was
    exported: the row changed after export, and storing a vector for text that
    is no longer there would rank a resource by a description it does not have.
    """

    import json
    from pathlib import Path

    current = {row["id"]: text_hash(embedding_text(dict(row)))
               for row in registry.conn.execute("SELECT * FROM datasets")}
    stored = stale = unknown = 0
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            dataset_id = record["dataset_id"]
            if dataset_id not in current:
                unknown += 1
                continue
            if record.get("text_hash") and record["text_hash"] != current[dataset_id]:
                stale += 1
                continue
            vector = record["vector"]
            registry.upsert_embedding(
                dataset_id=dataset_id,
                model=model,
                vector=pack(vector),
                dim=len(vector),
                text_hash=current[dataset_id],
            )
            stored += 1
    return {"stored": stored, "stale": stale, "unknown": unknown, "model": model}
