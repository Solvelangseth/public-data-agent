"""What a question pins down, taken only from names the registry can confirm.

A question about two kommuner in one year fetched 264,033 rows covering every
kommune and every year, because nothing between the question and the request
read the words "Bærum", "Asker" or "2024". `PlanStep` has had `periods` and
`parameters` since it was written; nothing fills them outside one
special-cased intent.

This fills them, and it will only name a place the registry already holds.
The authority is `brkommuner` -- the Brønnøysund kommune register, 365 rows,
`subject_scheme = "brreg:kommunenummer"`, one code per name, fetched and dated
like any other record. A name that is not in it is not resolved to a code
here. That is the same rule as everywhere else in this registry: a
publisher-declared key is a fact, a pattern that looks like one is a guess.

**It refuses rather than choosing.** Three ways a match goes wrong, and all
three are quiet if the code picks a winner:

    one name, several codes   `dataset_coverage` lists 107 names twice, most
                              of them an `X` and an `X (gammel)` pair, and
                              Oslo appears as both `0301` and `301`
    a name inside a name      `Asker` sits inside `Asker (gammel)`, `Alta`
                              inside `Alvdal`; 18 kommuner have names of four
                              letters or fewer -- `Bø`, `Hå`, `Gol`, `Hol`
    a number that is not a year
                              `3201` is Bærum, `13035` is an SSB table

So matching is whole-word and longest-name-first, years are bounded, and a
name that resolves to more than one code comes back as `ambiguous` with every
candidate attached, for the caller to refuse on.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

# A statistic can be published for the year that has just begun and a planner
# may reasonably ask for it, so the window runs a year ahead of nothing in
# particular -- what it excludes is kommune numbers (3201), SSB table ids
# (13035) and postcodes, which is the whole job.
EARLIEST_YEAR = 1800
LATEST_YEAR = 2100

SCHEME = "brreg:kommunenummer"

# `\b` does not cut Norwegian letters the way this needs: in `Bø` the `ø` is a
# word character, so a plain boundary works, but the names also carry hyphens,
# spaces and en dashes (`Deatnu – Tana`). The boundary is therefore checked
# against the characters either side rather than by `\b`.
_WORD = re.compile(r"[^\W\d_]", re.UNICODE)


@dataclass(frozen=True)
class Place:
    """A place named in a question, as the register spells it."""

    name: str                       # the words as they appear in the question
    scheme: str = SCHEME
    code: str | None = None         # None when ambiguous
    label: str | None = None        # the register's own spelling
    candidates: tuple[str, ...] = ()

    @property
    def ambiguous(self) -> bool:
        return self.code is None and len(self.candidates) > 1

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"name": self.name, "scheme": self.scheme}
        if self.code is not None:
            out["code"] = self.code
            out["label"] = self.label
        if self.candidates:
            out["candidates"] = list(self.candidates)
        return out


@dataclass(frozen=True)
class Constraints:
    """Everything a question pins down that a request can carry."""

    years: tuple[int, ...] = ()
    places: tuple[Place, ...] = ()
    unresolved: tuple[str, ...] = field(default=())

    @property
    def resolved_places(self) -> tuple[Place, ...]:
        return tuple(p for p in self.places if p.code is not None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "years": list(self.years),
            "places": [p.to_dict() for p in self.places],
            "unresolved": list(self.unresolved),
        }


def _fold(text: str) -> str:
    """Case-folded and width-normalised, but Norwegian letters left alone.

    `casefold` is used rather than `lower` because the register writes its
    labels in capitals (`BÆRUM`), and NFC so that a decomposed `å` from a
    pasted question matches a composed one in the register.
    """

    return unicodedata.normalize("NFC", text).casefold()


def years_in(question: str) -> tuple[int, ...]:
    """Every four-digit year in the question, in the order written.

    Bounded, because the alternative matches kommune numbers and table ids.
    A repeated year is returned once: "fra 2020 til 2020" pins one year.
    """

    found: list[int] = []
    for match in re.finditer(r"(?<!\d)(\d{4})(?!\d)", question or ""):
        year = int(match.group(1))
        if EARLIEST_YEAR <= year <= LATEST_YEAR and year not in found:
            found.append(year)
    return tuple(found)


def kommune_index(registry: Any) -> dict[str, list[tuple[str, str]]]:
    """Folded name -> [(code, label)], from the register and nothing else.

    Read once per call site rather than cached on the module: the registry is
    a file that other processes write, and a cached index would quietly answer
    from a registry that no longer exists.
    """

    index: dict[str, list[tuple[str, str]]] = {}
    rows = registry.conn.execute(
        "SELECT DISTINCT subject_code, subject_label FROM records "
        "WHERE subject_scheme = ? AND subject_label IS NOT NULL "
        "AND subject_code IS NOT NULL",
        (SCHEME,),
    ).fetchall()
    for row in rows:
        code, label = str(row[0]), str(row[1])
        index.setdefault(_fold(label), []).append((code, label))
    return index


def _is_bounded(haystack: str, start: int, end: int) -> bool:
    """True when the span is not glued to a letter on either side.

    `Alta` inside `Alvdal` fails this; `Alta` in `i Alta i 2024` passes. Digits
    are deliberately not treated as boundaries either, so `Bø3` is not Bø.
    """

    before = haystack[start - 1] if start > 0 else ""
    after = haystack[end] if end < len(haystack) else ""
    return not (_WORD.match(before) or before.isdigit()) and not (
        _WORD.match(after) or after.isdigit()
    )


def places_in(question: str, registry: Any) -> tuple[Place, ...]:
    """Kommuner the question names, longest name first, never overlapping.

    Longest first because `Nord-Aurdal` contains `Aurdal` and `Nord-Odal`
    contains `Odal`; taking the short one would answer about a different
    kommune with no sign anything went wrong. Once a span is taken, nothing
    else may use those characters.
    """

    index = kommune_index(registry)
    folded = _fold(question or "")
    taken: list[tuple[int, int]] = []
    found: list[tuple[int, Place]] = []
    for name in sorted(index, key=len, reverse=True):
        start = folded.find(name)
        while start != -1:
            end = start + len(name)
            overlaps = any(start < t_end and t_start < end for t_start, t_end in taken)
            if not overlaps and _is_bounded(folded, start, end):
                taken.append((start, end))
                entries = index[name]
                codes = tuple(sorted({code for code, _label in entries}))
                written = (question or "")[start:end]
                if len(codes) == 1:
                    found.append((start, Place(
                        name=written, code=codes[0], label=entries[0][1])))
                else:
                    found.append((start, Place(name=written, candidates=codes)))
                break
            start = folded.find(name, start + 1)
    return tuple(place for _start, place in sorted(found, key=lambda pair: pair[0]))


def constraints_in(question: str, registry: Any) -> Constraints:
    """What the question pins down, with the ambiguous parts kept ambiguous."""

    places = places_in(question, registry)
    return Constraints(
        years=years_in(question),
        places=places,
        unresolved=tuple(p.name for p in places if p.ambiguous),
    )
