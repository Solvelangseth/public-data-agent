"""Index the corpus with local embedding models and score each against gold.

Meant to run unattended. Every step is resumable: an index already built is not
rebuilt, so a crash or a Ctrl-C costs only the step it was in.

Answers one question -- does a Norwegian or multilingual model find data that
`text-embedding-3-small` misses -- against the two labelled sets rather than
against an impression. The failures it is aimed at are Norwegian vocabulary
distance: `domfelte` against `straffede personer`, `yrkesdeltakelse` against
`arbeidsstyrken`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from pathlib import Path

from public_data_agent.embeddings import embedding_text, fuse, pack, semantic_ranking, text_hash

MODELS = [
    # Norwegian sentence-BERT from the National Library. Small, and the most
    # direct test of whether Norwegian-specific training is what is missing.
    "NbAiLab/nb-sbert-base",
    # Strong multilingual retrieval model. If this wins and the Norwegian one
    # does not, size rather than language is doing the work.
    "intfloat/multilingual-e5-large",
]
BASELINE = "text-embedding-3-small"
SETS = [("tuned", "data/fetchable_gold.json", "data/answerable_questions.json"),
        ("held-out", "data/heldout_gold.json", "data/heldout_questions.json")]


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# Weights, roughly, so a model is refused before it fills the disk rather than
# after. A first run of this script drove free space from 3.0 GB to 1.4 GB while
# downloading a 2.2 GB model and had to be killed; leaving a machine with no disk
# is worse than not running the benchmark.
APPROX_SIZE_GB = {
    "NbAiLab/nb-sbert-base": 0.7,
    "intfloat/multilingual-e5-large": 2.3,
}
HEADROOM_GB = 3.0


def free_gb() -> float:
    import shutil

    return shutil.disk_usage(pathlib.Path.home()).free / 1e9


class NotEnoughDisk(RuntimeError):
    pass


def check_disk(name: str) -> None:
    """Refuse a model that would not leave the machine room to work."""

    need = APPROX_SIZE_GB.get(name, 2.5) + HEADROOM_GB
    have = free_gb()
    if have < need:
        raise NotEnoughDisk(
            f"{name} needs about {APPROX_SIZE_GB.get(name, 2.5):.1f} GB and "
            f"{HEADROOM_GB:.0f} GB should stay free; only {have:.1f} GB available"
        )
    log(f"disk: {have:.1f} GB free, {name} needs ~{APPROX_SIZE_GB.get(name, 2.5):.1f} GB")


class LocalProvider:
    """Wraps a sentence-transformers model in the one method the project needs."""

    def __init__(self, name: str) -> None:
        from sentence_transformers import SentenceTransformer
        import torch

        check_disk(name)
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        log(f"loading {name} on {device}")
        self.model = SentenceTransformer(name, device=device)
        self.name = name

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False
        )
        return [[float(x) for x in v] for v in vectors]


def build(registry, provider: LocalProvider) -> None:
    """Embed every dataset under this model, skipping what is already done."""

    done = registry.embedded_hashes(provider.name)
    rows = [dict(r) for r in registry.conn.execute("SELECT * FROM datasets ORDER BY id")]
    todo = []
    for row in rows:
        text = embedding_text(row)
        if not text:
            continue
        digest = text_hash(text)
        if done.get(row["id"]) == digest:
            continue
        todo.append((row["id"], text, digest))
    log(f"{provider.name}: {len(rows) - len(todo)} already indexed, {len(todo)} to do")
    started = time.time()
    for i in range(0, len(todo), 256):
        if free_gb() < 1.0:
            raise NotEnoughDisk(f"stopping: only {free_gb():.1f} GB free mid-run")
        chunk = todo[i : i + 256]
        vectors = provider.embed([text for _id, text, _d in chunk])
        with registry.deferred_commit():
            for (dataset_id, _text, digest), vector in zip(chunk, vectors):
                registry.upsert_embedding(
                    dataset_id=dataset_id, model=provider.name,
                    vector=pack(vector), dim=len(vector), text_hash=digest,
                )
        done_n = i + len(chunk)
        rate = done_n / max(time.time() - started, 1)
        log(f"  {done_n}/{len(todo)}  {rate:.0f}/s  eta {(len(todo)-done_n)/max(rate,0.01)/60:.0f}m")


def score(registry, provider, model: str, gold_path: str, meta_path: str) -> dict:
    """recall@5 and MRR over the fetchable lane, split by phrasing."""

    from public_data_agent.fetch import classify_access_path
    from public_data_agent.search import search_report

    gold = {q["id"]: set(q["expected"]) for q in json.load(open(gold_path))["questions"]}
    meta = {q["id"]: q for q in json.load(open(meta_path))["questions"]}
    scored = [q for q, e in gold.items() if e]
    kind: dict[str, str] = {}

    def fetchable(dataset_id: str) -> bool:
        if dataset_id not in kind:
            row = registry.get_dataset(dataset_id) or {}
            kind[dataset_id] = classify_access_path(row.get("access_path"))["kind"]
        return kind[dataset_id] == "observations"

    hits = rr = 0
    by_style: dict[str, list[int]] = {"keyword": [0, 0], "natural": [0, 0]}
    for qid in scored:
        query, want = meta[qid]["query"], gold[qid]
        lexical = [h.dataset_id for h in search_report(registry, query, limit=50).hits]
        semantic = [d for d, _ in semantic_ranking(registry, provider, query, limit=50, model=model)]
        ranked = [d for d in fuse(lexical, semantic, limit=50) if fetchable(d)]
        got = bool(want & set(ranked[:5]))
        hits += got
        rank = next((i for i, d in enumerate(ranked, 1) if d in want), None)
        rr += (1.0 / rank) if rank else 0.0
        style = by_style[meta[qid]["style"]]
        style[0] += got
        style[1] += 1
    n = len(scored)
    return {
        "recall@5": hits / n, "mrr": rr / n, "n": n,
        "keyword": by_style["keyword"][0] / max(by_style["keyword"][1], 1),
        "natural": by_style["natural"][0] / max(by_style["natural"][1], 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--models", nargs="*", default=MODELS)
    parser.add_argument("--out", default="data/embedding_bench.json")
    args = parser.parse_args()

    from public_data_agent.registry import Registry

    registry = Registry(args.db)
    results: dict[str, dict] = {}
    try:
        for model in args.models:
            log(f"=== {model} ===")
            try:
                provider = LocalProvider(model)
                build(registry, provider)
                for label, gold_path, meta_path in SETS:
                    results[f"{model} | {label}"] = score(
                        registry, provider, model, gold_path, meta_path
                    )
                    log(f"  {label}: {results[f'{model} | {label}']}")
            except Exception as exc:
                log(f"  FAILED: {type(exc).__name__}: {exc}")
                results[f"{model} | error"] = {"error": f"{type(exc).__name__}: {exc}"}

        # The baseline is scored the same way, through the same code path, so
        # the comparison is not against a differently-measured number.
        log(f"=== {BASELINE} (baseline) ===")
        try:
            from public_data_agent.openai_agent import OpenAIEmbeddingProvider

            openai = OpenAIEmbeddingProvider.from_env(dotenv=Path(".env"))
            for label, gold_path, meta_path in SETS:
                results[f"{BASELINE} | {label}"] = score(
                    registry, openai, BASELINE, gold_path, meta_path
                )
                log(f"  {label}: {results[f'{BASELINE} | {label}']}")
        except Exception as exc:
            log(f"  FAILED: {type(exc).__name__}: {exc}")
    finally:
        registry.close()

    Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print()
    print(f"{'model | set':46} {'recall@5':>9} {'MRR':>7} {'keyword':>9} {'natural':>9}")
    for key, value in results.items():
        if "error" in value:
            print(f"{key:46} {value['error'][:40]}")
            continue
        print(f"{key:46} {value['recall@5']:9.3f} {value['mrr']:7.3f} "
              f"{value['keyword']:9.3f} {value['natural']:9.3f}")
    print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
