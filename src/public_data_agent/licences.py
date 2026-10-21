"""Name the licence family a URL belongs to, so two spellings stop disagreeing.

The registry holds licences in whatever vocabulary each harvest used. The
datanorge harvest writes EU publications-office URIs; Geonorge's own API
writes the canonical licence URL. So
`publications.europa.eu/.../licence/CC_BY_4_0` and
`creativecommons.org/licenses/by/4.0/` are the same permission written twice,
and comparing the strings reported 668 disagreements of which zero were real.

This maps both to a family name. The names are deliberately coarse -- the
question a search needs answered is "may I use this, and may I pass it on",
not which minor version. `GAPS.md` proposed exactly this as the honest first
step before any redistribution verdict, because a family is a lookup over
published identifiers while a verdict is a legal reading.

Anything unrecognised returns None rather than a guess. A licence this does
not know is not thereby permissive.
"""

from __future__ import annotations

# family -> the marks that identify it in any vocabulary seen in the registry.
# Order matters: the non-commercial and no-derivatives marks are checked before
# the plain CC-BY ones, because `CC_BYNC_4_0` contains `CC_BY`.
_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("CC0", ("cc0", "publicdomain/zero")),
    ("CC-BY-NC", ("cc_bync", "by-nc", "licenses/by-nc")),
    ("CC-BY-ND", ("cc_bynd", "by-nd")),
    ("CC-BY-SA", ("cc_bysa", "by-sa")),
    ("CC-BY", ("cc_by", "licenses/by/")),
    ("NLOD", ("nlod",)),
    ("Norge digitalt", ("norge-digitalt", "norge digitalt", "norgedigitalt")),
    ("INSPIRE no-conditions", ("noconditionsapply",)),
    ("INSPIRE conditions unknown", ("conditionsunknown",)),
    ("Geovekst", ("geovekst",)),
    ("OGL", ("open-government-licence", "ogl-uk")),
    ("MIT", ("licenses/mit", "opensource.org/licenses/mit")),
)

# Families whose terms forbid commercial use outright. Relevant because this
# registry is headed for a commercial service, and no credential opens these.
NON_COMMERCIAL = frozenset({"CC-BY-NC"})

# Families that are an access agreement rather than a use licence: holding one
# does not mean the data is open, which is why `datasets.license` is not an
# access signal. See ACCESS.md section 8.
AGREEMENT_REQUIRED = frozenset({"Norge digitalt", "Geovekst"})


def licence_family(url: str | None) -> str | None:
    """The family a licence URL belongs to, or None if it is not recognised."""

    if not url or not isinstance(url, str):
        return None
    lowered = url.casefold()
    for family, marks in _FAMILIES:
        if any(mark in lowered for mark in marks):
            return family
    return None


def same_licence(left: str | None, right: str | None) -> bool:
    """Whether two licence URLs express the same permission.

    Two unrecognised URLs are only the same if the strings match: refusing to
    call them equal is the conservative answer, since this cannot read them.
    """

    left_family = licence_family(left)
    right_family = licence_family(right)
    if left_family and right_family:
        return left_family == right_family
    if not left or not right:
        return False
    return left.rstrip("/").casefold() == right.rstrip("/").casefold()
