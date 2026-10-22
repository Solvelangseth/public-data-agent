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

from typing import Any

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


# What a dataset's redistribution verdict can be. Deliberately the same four
# words as the stored vocabulary, so a resolved verdict and a recorded one
# cannot be told apart by their spelling and then treated differently.
ALLOWED = "allowed"
ALLOWED_WITH_ATTRIBUTION = "allowed_with_attribution"
DENIED = "denied"
UNKNOWN = "unknown"

# Kartverket answered on 2026-10-22: NorAtlas cannot join Norge digitalt as a
# commercial startup. So these are not "pending a credential" -- they are
# declined, and a resolver that returned `unknown` for them would keep
# inviting someone to go and ask again.
DECLINED_AGREEMENTS = {
    "Norge digitalt": (
        "Kartverket declined Norge digitalt membership for a commercial "
        "startup on 2026-10-22; see ACCESS.md section 10"
    ),
    "Geovekst": (
        "Geovekst distribution runs through the same Norge digitalt "
        "agreement that was declined; see ACCESS.md section 10"
    ),
}


def redistribution_verdict(
    registry: Any,
    dataset_id: str,
) -> dict[str, Any]:
    """May this dataset be passed on? With the reason, always.

    Resolution order, and each step is a fact rather than an inference:

        1. the dataset's licence, as the publisher declared it
        2. the family that licence belongs to (`licence_family`)
        3. a declined agreement overrides everything -- a permissive licence
           on data we may not obtain is still data we may not pass on
        4. the terms recorded for that family, read from a licence text
        5. otherwise `unknown`

    It never returns `allowed` by default. An unrecognised licence, a family
    nobody has recorded terms for, and a dataset with no licence at all are
    all `unknown`, because the alternative is a commercial service shipping
    data on the strength of a missing row.
    """

    dataset = registry.get_dataset(dataset_id)
    if dataset is None:
        raise ValueError(f"unknown dataset {dataset_id}")
    licence = dataset.get("license")
    family = licence_family(licence)
    out: dict[str, Any] = {
        "dataset_id": dataset_id,
        "licence": licence,
        "family": family,
        "verdict": UNKNOWN,
        "attribution_required": None,
        "basis": None,
        "source_url": None,
    }
    if family is None:
        out["basis"] = (
            "no licence recorded for this dataset"
            if not licence
            else f"licence {licence!r} belongs to no family this module names"
        )
        return out
    if family in DECLINED_AGREEMENTS:
        out["verdict"] = DENIED
        out["basis"] = DECLINED_AGREEMENTS[family]
        return out
    terms = registry.get_licence_terms(family)
    if terms is None:
        out["basis"] = f"no terms recorded for licence family {family!r}"
        return out
    out["verdict"] = terms["redistribution"]
    out["attribution_required"] = (
        None if terms["attribution_required"] is None else bool(terms["attribution_required"])
    )
    out["basis"] = f"terms recorded for licence family {family!r}"
    out["source_url"] = terms["source_url"]
    if family in NON_COMMERCIAL and out["verdict"] != DENIED:
        # A recorded row must not be able to contradict the licence's own
        # name. CC-BY-NC forbids commercial use whatever a later edit says.
        out["verdict"] = DENIED
        out["basis"] = (
            f"{family} forbids commercial use, which a commercial service "
            "cannot satisfy by attribution"
        )
    return out
