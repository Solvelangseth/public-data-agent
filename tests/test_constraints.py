"""What a question pins down, and the four ways reading it goes quietly wrong.

A question about two kommuner in one year fetched 264,033 rows because nothing
read the words. These are the cases where reading them badly would be worse
than not reading them at all: a wrong kommune answers confidently about the
wrong place, and nothing downstream can tell.
"""

from __future__ import annotations

import sqlite3

import pytest

from public_data_agent.constraints import (
    SCHEME,
    Place,
    constraints_in,
    kommune_index,
    places_in,
    years_in,
)

# The register as it really is: capitals, one code per name. Plus the traps --
# a name inside another name, names of one and two letters, and a pair that
# differs only by a prefix.
REGISTER = [
    ("3201", "BÆRUM"),
    ("3203", "ASKER"),
    ("0301", "OSLO"),
    ("3428", "ALVDAL"),
    ("5403", "ALTA"),
    ("1867", "BØ"),
    ("1119", "HÅ"),
    ("3451", "NORD-AURDAL"),
    ("3449", "SØR-AURDAL"),
    ("5630", "DEATNU – TANA"),
]


class _Registry:
    """Only what `constraints` touches: a `conn` that answers one query."""

    def __init__(self, rows: list[tuple[str, str]]) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE records (subject_scheme TEXT, subject_code TEXT, subject_label TEXT)"
        )
        self.conn.executemany(
            "INSERT INTO records VALUES (?, ?, ?)",
            [(SCHEME, code, label) for code, label in rows],
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


@pytest.fixture
def registry() -> _Registry:
    reg = _Registry(REGISTER)
    yield reg
    reg.close()


def test_the_question_that_started_this(registry: _Registry) -> None:
    found = constraints_in(
        "Hvor mye husholdningsavfall per innbygger hadde Bærum i 2024 "
        "sammenlignet med Asker?",
        registry,
    )
    assert found.years == (2024,)
    assert [(p.name, p.code) for p in found.places] == [("Bærum", "3201"), ("Asker", "3203")]
    assert found.unresolved == ()


def test_a_kommune_number_is_not_a_year(registry: _Registry) -> None:
    """3201 is Bærum and 13035 is an SSB table.

    An unbounded four-digit match reads both as years, and the request then
    carries a year nobody asked for.
    """

    assert years_in("tabell 13035 for kommune 3201") == ()
    assert years_in("fra 1990 til 2024") == (1990, 2024)
    assert years_in("postnummer 0150") == ()  # below EARLIEST_YEAR
    assert years_in("befolkning 2024") == (2024,)


def test_a_year_written_twice_is_one_year(registry: _Registry) -> None:
    assert years_in("fra 2020 til 2020") == (2020,)


def test_a_name_inside_another_name_is_not_a_match(registry: _Registry) -> None:
    """`Alta` sits inside `Alvdal`, and answering about Alta would be silent."""

    assert [p.name for p in places_in("utslipp i Alvdal 2019", registry)] == ["Alvdal"]
    assert [p.code for p in places_in("utslipp i Alvdal 2019", registry)] == ["3428"]
    assert [p.name for p in places_in("utslipp i Alta 2019", registry)] == ["Alta"]


def test_the_longer_name_wins(registry: _Registry) -> None:
    """`Nord-Aurdal` contains no bare `Aurdal` to find, but `Sør-Aurdal`
    and `Nord-Aurdal` both end in the same word, and a short-first scan
    would take the wrong one."""

    found = places_in("befolkning i Nord-Aurdal og Sør-Aurdal", registry)
    assert [(p.name, p.code) for p in found] == [
        ("Nord-Aurdal", "3451"),
        ("Sør-Aurdal", "3449"),
    ]


def test_two_letter_names_match_only_as_whole_words(registry: _Registry) -> None:
    """18 kommuner have names of four letters or fewer. `Bø` and `Hå` are the
    hardest: a substring match finds them in ordinary Norwegian text."""

    assert [p.code for p in places_in("folketall i Bø og Hå 2020", registry)] == [
        "1867", "1119",
    ]
    for sentence in ("en bøtte med vann", "håndtering av avfall", "Bøler i Oslo"):
        names = [p.name for p in places_in(sentence, registry)]
        assert "Bø" not in names and "Hå" not in names, sentence


def test_a_digit_is_a_boundary_too(registry: _Registry) -> None:
    assert places_in("sone Bø3 og Hå7", registry) == ()


def test_a_name_in_two_schemes_comes_back_ambiguous_not_guessed() -> None:
    """107 names in `dataset_coverage` map to more than one code, and Oslo
    appears as both `0301` and `301`. Picking one is a coin toss recorded as
    a fact; the caller has to see both.
    """

    registry = _Registry([("0301", "OSLO"), ("301", "OSLO"), ("3201", "BÆRUM")])
    try:
        found = constraints_in("avfall i Oslo og Bærum 2024", registry)
        oslo = next(p for p in found.places if p.name == "Oslo")
        assert oslo.code is None
        assert oslo.ambiguous
        assert oslo.candidates == ("0301", "301")
        assert found.unresolved == ("Oslo",)
        # The unambiguous one beside it still resolves.
        assert found.resolved_places == (
            Place(name="Bærum", scheme=SCHEME, code="3201", label="BÆRUM"),
        )
    finally:
        registry.close()


def test_the_register_is_read_case_insensitively(registry: _Registry) -> None:
    """The register writes `BÆRUM`; people write `Bærum` and `bærum`."""

    for written in ("Bærum", "BÆRUM", "bærum", "BæRuM"):
        assert [p.code for p in places_in(f"avfall i {written}", registry)] == ["3201"]


def test_a_decomposed_vowel_still_matches(registry: _Registry) -> None:
    """`å` pasted from some systems arrives as `a` plus a combining ring.

    It renders identically and compares unequal, so `Hå` typed one way finds
    the kommune and the other way finds nothing, with nothing saying which
    happened. `æ` and `ø` do not decompose; `å` does, which is why the
    normalisation is not decoration.
    """

    import unicodedata

    decomposed = unicodedata.normalize("NFD", "Hå")
    assert decomposed != "Hå", "the fixture is not actually decomposed"
    assert [p.code for p in places_in(f"jordbruk i {decomposed} 2024", registry)] == ["1119"]


def test_a_name_with_a_space_and_an_en_dash(registry: _Registry) -> None:
    """`DEATNU – TANA` is one kommune whose name carries both."""

    assert [p.code for p in places_in("folketall i Deatnu – Tana", registry)] == ["5630"]


def test_a_place_the_register_does_not_hold_is_not_resolved(registry: _Registry) -> None:
    """Grounding is the whole point: a name is a code only if a publisher
    said so. `Nordmarka` is a real place and not a kommune."""

    assert places_in("skogbruk i Nordmarka og Finnmarksvidda", registry) == ()


def test_the_index_comes_only_from_the_declared_scheme() -> None:
    registry = _Registry([("3201", "BÆRUM")])
    try:
        registry.conn.execute(
            "INSERT INTO records VALUES ('geonorge:area', '9999', 'ANDEBY')"
        )
        registry.conn.commit()
        index = kommune_index(registry)
        assert "bærum" in index
        assert "andeby" not in index, "a code from another scheme must not be a kommune"
    finally:
        registry.close()


def test_places_come_back_in_the_order_written(registry: _Registry) -> None:
    """A comparison question's first-named place is usually the subject."""

    found = places_in("sammenlign Asker med Bærum og Alvdal", registry)
    assert [p.name for p in found] == ["Asker", "Bærum", "Alvdal"]
