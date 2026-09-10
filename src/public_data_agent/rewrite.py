"""Translate a question into the words the catalogue uses.

Every retrieval failure left in the labelled sets is one gap. The asker writes
"hvor mye har prisene steget"; Statistics Norway writes "konsumprisindeks". The
lexical index cannot bridge that -- no token survives tokenisation as a word the
catalogue uses -- and `text-embedding-3-small` does not either. Six attempts to
close it by ranking better all failed, because ranking is not what is broken.

A language model bridges it in one call, and the knowledge comes from Norwegian
rather than from the labelled questions, so using it does not spend the held-out
set. Measured through `find`:

    tuned     recall@5 0.860 -> 0.884   MRR 0.763 -> 0.760
    held-out  recall@5 0.811 -> 0.892   MRR 0.723 -> 0.730

The held-out gain being the larger one is the reassuring part: a rule fitted to
the misses gains on the set it was fitted to and nothing elsewhere, which is what
happened to the previous attempt.

The trust boundary is unchanged and worth stating. The model proposes SEARCH
TERMS ONLY. It never sees a dataset, never names one, and nothing it returns is
reported as evidence -- results still come from the index and values still come
from a fetch. A bad term costs a bad search, not a wrong answer, and the terms
are recorded in the retrieval steps so a caller can see what was searched for.
"""

from __future__ import annotations

import json
from typing import Protocol

REWRITE_INSTRUCTIONS = """Du hjelper med å søke i en katalog over norsk offentlig statistikk (SSB, FHI).

Brukeren skriver dagligtale. Katalogen bruker statistikkfaglige termer.
Oppgaven din er å oversette spørsmålet til de ordene en tabelltittel ville brukt.

Svar med JSON: {"terms": ["...", "..."]}
- 2 til 5 termer, på norsk, hver på 1-3 ord
- bruk termen katalogen ville brukt, ikke brukerens ord
  ("hvor mye har prisene steget" -> "konsumprisindeks")
  ("hvor mye tjener en sykepleier" -> "månedslønn", "yrke")
- ikke ta med stedsnavn, årstall eller tabellnummer
- ikke gjett en tabell; foreslå bare søkeord
"""

MAX_TERMS = 5


class QueryRewriter(Protocol):
    # Identifies whose terms these are. It is the cache key, so two rewriters
    # sharing a name would read each other's answers: a Klass run once scored
    # 0.865 by reading terms a model had written under the default key.
    name: str

    def terms(self, query: str) -> list[str]: ...


def clean_terms(raw: object) -> list[str]:
    """What a model returned, reduced to what is usable as a search term.

    A model that ignores the instructions and returns a sentence, a table id or
    nothing at all is handled here rather than downstream: the worst case is an
    empty list, which leaves the ranking exactly as it was.
    """

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if isinstance(raw, dict):
        raw = raw.get("terms")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        term = " ".join(item.split()).strip()
        # Three words is the instruction; more than that is a sentence, and a
        # sentence searched as a term matches nothing useful.
        if term and len(term) <= 60 and len(term.split()) <= 3 and term not in out:
            out.append(term)
    return out[:MAX_TERMS]


def rewriter_name(rewriter: QueryRewriter) -> str:
    return getattr(rewriter, "name", None) or type(rewriter).__name__


def terms_for(registry, rewriter: QueryRewriter, query: str, *, model: str | None = None) -> list[str]:
    """The catalogue's words for this question, from cache where possible.

    A rewrite costs a network call, and an MCP server sees the same question
    more than once, so the result is stored. A failed call returns no terms and
    leaves the ranking untouched -- a rewriter that is down must not take the
    search down with it.
    """

    model = model or rewriter_name(rewriter)
    cached = registry.get_query_rewrite(query, model=model)
    if cached is not None:
        return cached
    try:
        terms = clean_terms(rewriter.terms(query))
    except Exception:
        return []
    registry.set_query_rewrite(query, terms, model=model)
    return terms


class CombinedRewriter:
    """Several rewriters as one, in the order given.

    They answer from different knowledge -- a model knows Norwegian, Klass knows
    what SSB has renamed -- so a term from either is worth searching. Terms are
    deduplicated and the combined list is capped like any other, which means an
    earlier rewriter can crowd out a later one; that is deliberate, since the
    order states which source is trusted first.
    """

    def __init__(self, rewriters: list[QueryRewriter | None]) -> None:
        self.rewriters = [r for r in rewriters if r is not None]
        self.name = "+".join(rewriter_name(r) for r in self.rewriters)

    def terms(self, query: str) -> list[str]:
        out: list[str] = []
        for rewriter in self.rewriters:
            try:
                proposed = clean_terms(rewriter.terms(query))
            except Exception:
                continue
            for term in proposed:
                if term not in out:
                    out.append(term)
        return out[:MAX_TERMS]
