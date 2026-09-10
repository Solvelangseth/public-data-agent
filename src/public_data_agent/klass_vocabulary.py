"""A synonym source built from SSB's own classification history.

**Measured and rejected for retrieval. Do not wire this into a ranking without
reading the numbers below.** It is kept because the extraction rules are correct
and the downloaded mirror has other uses, not because it helps.

The idea was sound. Every retrieval failure left is a translation gap: the
asker's word is not the catalogue's word. A language model closes most of it but
translates everyday Norwegian into statistics vocabulary rather than one
statistics word into this catalogue's synonym for it -- asked about
`yrkesdeltakelse` it returns `yrkesdeltakelse`. Writing those pairs by hand would
fit the held-out set and is not allowed. Klass qualified because it owes nothing
to any question set: it is SSB's classification service, it keeps every version
of every standard, and one code carries different names across versions. Code
`2.03` was "Spesialiserte fosterhjem" and is now "Statlige familiehjem".

What it actually holds is administrative name history, which is a different
thing. Across all 151 classifications and 837 versions it proposes a term for
**8 of the 131 labelled questions, and every one of the eight is wrong**:

    hvor mange bor det i Bergen        -> Bergen amt        (abolished 1763)
    hva koster en bolig i Oslo         -> Christiania amt, Oslo Havn KF
    hva er gjennomsnittsalderen i Tromsø -> Tromsø Havn KF
    husholdninger størrelse            -> Andre næringer - stasjonær forbrenning

recall@5 is unchanged to three decimals on both sets -- 0.860 tuned, 0.811
held-out -- and combined with the model rewriter it lands inside that rewriter's
own run-to-run band. The last example is the instructive one: it is a *correct*
Klass rename, of a category code in an emissions standard, and it is catastrophic
as a synonym for a question about household size. A word common enough to appear
in a question is common enough to name different things in different standards,
and a word unambiguous enough to be safe is too rare to be asked about. That is
the same shape as the resource-index rejection in GAPS.md.

Most of what remains below is the machinery for refusing to believe Klass, and
that part was worth building. Read carelessly the source claims Trøndelag is
Vestlandet, because landsdel codes were renumbered; `build_vocabulary` drops any
name that has belonged to two codes in one standard. Most pairs are not renames
at all -- a code's names differ by punctuation ("Refne - Banken" against
"Refne/Banken"), by case ("Vold-Skog" against "Vold-skog"), or by a corrected
typo ("Sommerr0" against "Sommerro") -- and `is_rename` is where that judgement
is made and can be argued with.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterator

from public_data_agent.search import STOP_TOKENS, index_is_current, tokenize

# Two words this similar are one word spelled twice -- "sommerr0" against
# "sommerro", "barnevernloven" against "barnevernsloven". Comparing whole names
# instead of words does not work: it calls a corrected typo a rename because the
# names are short, and calls a renumbered legal reference a rename because the
# digits differ.
SPELLING_SIMILARITY = 0.85
MIN_NAME_LENGTH = 4
# A Klass name only expands a query when the query contains all of its words, so
# a long name is dead weight in the index and a one-word name is usually a place.
MAX_NAME_TOKENS = 4
MAX_TERMS = 5

_PUNCT = re.compile(r"[^0-9a-zæøåäöéèü]+", re.IGNORECASE)


def normalise(name: str | None) -> str:
    """A name reduced to the letters and digits that carry its meaning."""

    if not name:
        return ""
    return " ".join(_PUNCT.sub(" ", name.casefold()).split())


def is_rename(left: str, right: str) -> bool:
    """Whether two names for one code are two names rather than two spellings.

    A rename changes a word. Everything else a code's name history contains --
    punctuation, capitalisation, a corrected typo, a renumbered paragraph -- is
    the same name written differently, and pairing those as synonyms would fill
    the vocabulary with noise.

    So the names are compared word by word rather than as strings. Words the two
    share are set aside, numbers are ignored because they are paragraph and year
    references rather than vocabulary, and each remaining word is matched against
    the other side's remaining words: a close match is one word spelled twice. If
    a word is left over on either side, something was actually renamed.
    """

    a, b = normalise(left), normalise(right)
    if not a or not b or a == b:
        return False
    if len(a) < MIN_NAME_LENGTH or len(b) < MIN_NAME_LENGTH:
        return False
    def content(text: str, other: set[str]) -> list[str]:
        # Numbers are paragraph and year references, and connectives are
        # grammar: "Hestevold og Holme" and "Hestevold - Holme" are one name.
        return [
            word
            for word in text.split()
            if word not in other and not word.isdigit() and word not in STOP_TOKENS
        ]

    left_only = content(a, set(b.split()))
    right_only = content(b, set(a.split()))
    for word in list(left_only):
        match = next(
            (
                other
                for other in right_only
                if SequenceMatcher(None, word, other).ratio() >= SPELLING_SIMILARITY
            ),
            None,
        )
        if match is not None:
            left_only.remove(word)
            right_only.remove(match)
    return bool(left_only or right_only)


def iter_versions(directory: Path) -> Iterator[tuple[str, str, list[dict[str, Any]]]]:
    """Each downloaded version as (classification id, version id, items).

    A version that failed to download was written as an error file rather than
    left absent, so it is not silently refetched forever; it is skipped here.
    """

    for path in sorted((directory / "versions").glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not isinstance(payload, dict) or payload.get("error"):
            continue
        items = payload.get("classificationItems")
        if not isinstance(items, list):
            continue
        yield str(payload.get("classification_id") or ""), path.stem, items


def collect_names(directory: Path) -> dict[tuple[str, str], set[str]]:
    """Every name each code has ever carried, by (classification, code)."""

    names: dict[tuple[str, str], set[str]] = defaultdict(set)
    for classification_id, _version_id, items in iter_versions(directory):
        for item in items:
            if not isinstance(item, dict):
                continue
            code, name = item.get("code"), (item.get("name") or "").strip()
            if code is None or not name:
                continue
            names[(classification_id, str(code))].add(name)
    return names


def build_vocabulary(registry, directory: Path, *, progress=None) -> dict[str, int]:
    """Store the rename pairs Klass has recorded.

    Both directions of each pair are written, because a query may use either
    name and the lookup is by whichever one it used.
    """

    log = progress or (lambda _message: None)
    names = collect_names(directory)
    log(f"{len(names)} codes across the downloaded versions")

    # A standard that renumbers breaks the identity this whole source rests on.
    # Landsdel code 5 was "Trøndelag" in one version and "Vestlandet" in
    # another, and code 6 was "Trøndelag" too, so reading that history as a
    # rename claims Trøndelag and Vestlandet are the same place. The tell is the
    # name, not the code: a name that has belonged to two different codes in one
    # standard does not identify one thing, and every pair it appears in is
    # discarded.
    codes_per_name: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (classification_id, code), variants in names.items():
        for variant in variants:
            codes_per_name[(classification_id, normalise(variant))].add(code)
    reused = {key for key, codes in codes_per_name.items() if len(codes) > 1}
    log(f"{len(reused)} names have belonged to more than one code and are dropped")

    registry.conn.execute("DELETE FROM term_aliases")
    rows: list[tuple[str, str, str, str]] = []
    pairs = 0
    for (classification_id, code), variants in names.items():
        if len(variants) < 2:
            continue
        variants = {
            v for v in variants if (classification_id, normalise(v)) not in reused
        }
        if len(variants) < 2:
            continue
        ordered = sorted(variants)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1 :]:
                if not is_rename(left, right):
                    continue
                pairs += 1
                evidence = f"klass:{classification_id}:{code}"
                rows.append((normalise(left), right, "klass_rename", evidence))
                rows.append((normalise(right), left, "klass_rename", evidence))
    registry.conn.executemany(
        "INSERT OR IGNORE INTO term_aliases (term, alias, source, evidence) VALUES (?, ?, ?, ?)",
        rows,
    )
    registry.conn.commit()
    log(f"{pairs} rename pairs, {len(rows)} directed aliases")
    return {"codes": len(names), "pairs": pairs, "aliases": len(rows)}


class KlassRewriter:
    """Proposes the other names SSB has used for something the query names.

    Implements the same interface as the model-backed rewriter, so the two are
    interchangeable and can be combined. This one costs no network call, returns
    the same terms every time, and its evidence is a classification code rather
    than a model's word.

    A name only fires when the query contains all of its words. Requiring the
    whole name keeps `Spesialiserte fosterhjem` from matching every query with
    the word "hjem" in it.

    Most of what Klass records is not query vocabulary -- the largest standard by
    version count is the grunnkrets one, whose renames are neighbourhood names no
    one asks about. Rather than judging which classifications deserve to be in
    the table, an alias has to contribute a word the catalogue actually indexes.
    A name nothing is published under cannot change a search, so it never fires.
    """

    name = "klass"

    def __init__(self, registry, *, limit: int = MAX_TERMS) -> None:
        self.registry, self.limit = registry, limit
        self._known: dict[str, bool] = {}
        self._checkable = index_is_current(registry)

    def _is_published(self, token: str) -> bool:
        """Whether anything in the catalogue is described with this word."""

        if not self._checkable:
            # Without the search index there is no way to tell, and refusing
            # every alias would be worse than letting a useless one through.
            return True
        if token not in self._known:
            row = self.registry.conn.execute(
                "SELECT 1 FROM search_index WHERE search_index MATCH ? LIMIT 1",
                (f'"{token}"*',),
            ).fetchone()
            self._known[token] = row is not None
        return self._known[token]

    def terms(self, query: str) -> list[str]:
        normalised = normalise(query)
        if not normalised:
            return []
        asked = set(tokenize(query))
        words = normalised.split()
        candidates = {
            " ".join(words[start : start + length])
            for length in range(1, MAX_NAME_TOKENS + 1)
            for start in range(0, len(words) - length + 1)
        }
        out: list[str] = []
        # Longest phrase first: a specific name is a better reason to expand a
        # query than one of the words inside it.
        for phrase in sorted(candidates, key=len, reverse=True):
            if len(phrase) < MIN_NAME_LENGTH:
                continue
            for row in self.registry.aliases_for(phrase):
                alias = row["alias"]
                if normalise(alias) in normalised or alias in out:
                    continue
                fresh = [t for t in tokenize(alias) if t not in asked]
                if not any(self._is_published(token) for token in fresh):
                    continue
                out.append(alias)
                if len(out) >= self.limit:
                    return out
        return out
