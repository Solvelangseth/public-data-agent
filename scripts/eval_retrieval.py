"""Score `retrieval.find` against a labelled set.

Measures the entry point a caller actually reaches, not a reconstruction of the
ranking chain. An earlier evaluation rebuilt that chain by hand, never exercised
a step `find` applies, and reported 0.860 for code that would have handed a
caller 0.802.

    python scripts/eval_retrieval.py                      # held-out set
    python scripts/eval_retrieval.py --set tuned          # the tuned set
    python scripts/eval_retrieval.py --no-provider        # lexical only

Questions labelled `expected: []` hold no answer in the registry and are
excluded: scoring a retriever for failing to find what is not there measures the
corpus, not the retriever.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

SETS = {
    "held-out": ("data/heldout_gold.json", "data/heldout_questions.json"),
    "tuned": ("data/fetchable_gold.json", "data/answerable_questions.json"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", dest="which", choices=sorted(SETS), default="held-out")
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--no-provider", action="store_true",
                        help="Rank lexically only, to show what an absent API key costs")
    parser.add_argument("--depth", type=int, default=50)
    parser.add_argument("--embedding-model", dest="embedding_model", default=None,
                        help="Rank with this embedding index instead of the default")
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--rewrite", choices=("openai", "klass", "both"), default=None,
                        help="Also search the catalogue's words for the question")
    args = parser.parse_args()

    from public_data_agent.registry import Registry
    from public_data_agent.retrieval import find

    provider = None
    if not args.no_provider:
        from public_data_agent.openai_agent import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider.from_env(
            dotenv=Path(".env"),
            **({"model": args.embedding_model} if args.embedding_model else {}),
            dimensions=args.dimensions,
        )

    registry = Registry(args.db)

    rewriter = None
    if args.rewrite in ("openai", "both"):
        from public_data_agent.openai_agent import OpenAIQueryRewriter

        rewriter = OpenAIQueryRewriter.from_env(dotenv=Path(".env"))
    if args.rewrite in ("klass", "both"):
        from public_data_agent.klass_vocabulary import KlassRewriter
        from public_data_agent.rewrite import CombinedRewriter

        klass = KlassRewriter(registry)
        rewriter = CombinedRewriter([rewriter, klass]) if rewriter else klass

    gold_path, meta_path = SETS[args.which]
    gold = {q["id"]: set(q["expected"]) for q in json.load(open(gold_path))["questions"]}
    meta = {q["id"]: q for q in json.load(open(meta_path))["questions"]}
    scored = [qid for qid, expected in gold.items() if expected]
    unanswerable = [qid for qid, expected in gold.items() if not expected]

    hits = 0
    reciprocal = 0.0
    by_style: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    misses: list[tuple[str, str, int | None]] = []
    try:
        for i, qid in enumerate(scored, 1):
            query, style, want = meta[qid]["query"], meta[qid]["style"], gold[qid]
            ranked = find(
                registry, query, provider=provider, limit=args.depth, rewriter=rewriter
            ).observations
            got = bool(want & set(ranked[:5]))
            hits += got
            rank = next((j for j, d in enumerate(ranked, 1) if d in want), None)
            reciprocal += (1.0 / rank) if rank else 0.0
            by_style[style][0] += got
            by_style[style][1] += 1
            if not got:
                misses.append((style, query, rank))
            print(f"  ..{i}/{len(scored)}", file=sys.stderr, flush=True)
    finally:
        registry.close()

    n = len(scored)
    ranking = "lexical only" if provider is None else f"full stack [{provider.model}]"
    if rewriter is not None:
        ranking += f" + {args.rewrite} rewriting"
    print(f"\n{args.which} set, {ranking}: {n} scored, "
          f"{len(unanswerable)} with no answer in the registry\n")
    print(f"  recall@5 {hits / n:.3f}   MRR {reciprocal / n:.3f}")
    for style, (got, total) in sorted(by_style.items()):
        print(f"  {style:9} {got}/{total} = {got / total:.3f}")
    print(f"\nmisses ({len(misses)}):")
    for style, query, rank in misses:
        where = f"rank {rank}" if rank else "not in depth"
        print(f"  [{style[:3]}] {query[:44]:46} {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
