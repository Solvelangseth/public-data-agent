"""Let a model reorder a shortlist of results that already exist.

The stack finds the right table more often than it ranks it first. Held-out
misses sat at rank 10, 11 and 32, and `pda benchmark` scores 0.938 at ten against
0.892 at five: the answer is usually retrieved and merely placed too low. Reading
twenty real titles and judging which one answers a question is something a model
does well and token overlap does not.

Measured through `find`, on top of query rewriting:

    tuned     recall@5 0.872 -> see GAPS.md   held-out 0.865 -> 0.892
    held-out  MRR      0.733 -> 0.778

How many titles it reads is itself measured; see `RERANK_DEPTH` below.

The trust boundary holds by construction, and that is the point of ranking by
position rather than by name. The model is shown only titles the index returned
and answers with positions in that list, so it cannot introduce a dataset that
does not exist; a position outside the list is discarded. Whatever it does not
rank keeps its original order behind what it did, so a truncated, lazy or failed
answer degrades to the ranking that was already there rather than to nothing.
It reorders candidates; it never supplies a value, and it never authorises a
fetch.
"""

from __future__ import annotations

import json
from typing import Protocol

# How many titles the model is shown. Measured 2026-10-21 on the tuned set,
# with coverage as the veto:
#
#     20  tuned 0.898/0.761   coverage 1.000/0.652
#     35  tuned 0.918/0.759   coverage 1.000/0.639
#     50  tuned 0.929/0.764   coverage 1.000/0.652
#
# 50 dominates: three questions gained and none lost, coverage untouched. The
# cheaper middle is not cheaper in quality -- 35 gains less and costs coverage
# MRR, which is why this is 50 and not "as small as works".
#
# What it is not: reach. The three questions gained sat at ranks 6, 7 and 12,
# already inside 20, so the model could always see them. With fifty titles in
# front of it, it chooses differently among candidates it could already read.
RERANK_DEPTH = 50
MAX_RANKED = 8
# How the model's judgement is merged with the ranking it was given. Named
# rather than inlined so the choice can be measured instead of argued about:
# it has moved the tuned MRR three times this session without anything in the
# ranking itself changing.
RERANK_KEEP = 1
RERANK_LIFT = 3

RERANK_INSTRUCTIONS = """Du får et spørsmål og en nummerert liste over datasett fra en katalog over norsk offentlig statistikk.

Ranger datasettene etter hvor godt de kan svare på spørsmålet.

Svar med JSON: {"order": [3, 1, 7]}
- bare tall som finnes i listen
- de mest relevante først, høyst 8 tall
- ta bare med datasett som faktisk kan svare på spørsmålet
- et datasett som er delt opp etter et ord i spørsmålet er mindre relevant enn ett som handler om det
- ikke finn på datasett, ikke svar på spørsmålet
"""


class Reranker(Protocol):
    name: str

    def order(self, query: str, titles: list[str]) -> list[int]: ...


def clean_order(raw: object, count: int, *, limit: int = MAX_RANKED) -> list[int]:
    """A model's answer reduced to positions that exist in the list it was given.

    Anything else is dropped rather than repaired: a position the model invented
    names no dataset, and guessing what it meant would be inventing a result.
    """

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if isinstance(raw, dict):
        raw = raw.get("order")
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if 1 <= value <= count and value not in out:
            out.append(value)
    return out[:limit]


def rerank(
    registry,
    reranker: Reranker,
    query: str,
    ranked: list[str],
    *,
    depth: int = RERANK_DEPTH,
    keep: int = RERANK_KEEP,
    lift: int = RERANK_LIFT,
) -> list[str]:
    """Reorder the head of a ranking, keeping everything it does not mention.

    `keep` positions of the original ranking are held in front of the model's
    choices. Handing the model the whole ordering measured worse than this on
    the tuned set -- its judgement is worth a lot as a promotion and less as a
    replacement -- and the merge is the one thing here chosen by measurement
    rather than by argument.
    """

    head = ranked[:depth]
    if not head:
        return ranked
    titles = [(registry.get_dataset(d) or {}).get("title") or d for d in head]
    cached = registry.get_rerank(query, head, model=reranker.name)
    if cached is None:
        try:
            positions = clean_order(reranker.order(query, titles), len(head))
        except Exception:
            # A reranker that is down must not take the ranking down with it.
            return ranked
        registry.set_rerank(query, head, positions, model=reranker.name)
    else:
        positions = cached
    lifted = [head[position - 1] for position in positions]
    return list(dict.fromkeys(ranked[:keep] + lifted[:lift] + ranked))
