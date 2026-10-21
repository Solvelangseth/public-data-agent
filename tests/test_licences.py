"""Licence families, and the 668 disagreements that were not disagreements."""

from __future__ import annotations

from public_data_agent.licences import (
    AGREEMENT_REQUIRED, NON_COMMERCIAL, licence_family, same_licence,
)

EU = "http://publications.europa.eu/resource/authority/licence/"


def test_the_two_vocabularies_in_the_registry_agree() -> None:
    """The datanorge harvest writes EU URIs; Geonorge writes canonical URLs.

    Comparing the strings reported 668 disagreements and every one was the
    same permission written twice.
    """

    for eu, canonical in (
        (EU + "CC_BY_4_0", "https://creativecommons.org/licenses/by/4.0/"),
        (EU + "NLOD_2_0", "https://data.norge.no/nlod/no/2.0"),
        (EU + "NLOD_1_0", "http://data.norge.no/nlod/no/1.0"),
        (EU + "CC_BYNC_4_0", "https://creativecommons.org/licenses/by-nc/4.0/"),
        (EU + "CC0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    ):
        assert licence_family(eu) == licence_family(canonical), (eu, canonical)
        assert same_licence(eu, canonical)


def test_non_commercial_is_not_read_as_plain_attribution() -> None:
    """`CC_BYNC_4_0` contains `CC_BY`, so order in the table is load-bearing."""

    assert licence_family(EU + "CC_BYNC_4_0") == "CC-BY-NC"
    assert licence_family("https://creativecommons.org/licenses/by-nc/4.0/") == "CC-BY-NC"
    assert licence_family(EU + "CC_BY_4_0") == "CC-BY"
    assert not same_licence(EU + "CC_BYNC_4_0", EU + "CC_BY_4_0")
    assert "CC-BY-NC" in NON_COMMERCIAL
    assert "CC-BY" not in NON_COMMERCIAL


def test_an_access_agreement_is_marked_as_one() -> None:
    """Holding a Norge digitalt licence does not make the data open."""

    nd = "https://www.geonorge.no/Geodataarbeid/Norge-digitalt/Avtaler-og-maler/Norge-digitalt-lisens/"
    assert licence_family(nd) == "Norge digitalt"
    assert licence_family(nd) in AGREEMENT_REQUIRED
    other = "https://www.kartverket.no/geodataarbeid/norge-digitalt/partsinformasjon/avtaler-og-vilkar/norge-digitalt-lisens"
    assert same_licence(nd, other), "both Norge digitalt URLs are one family"


def test_the_inspire_codelist_claims_are_told_apart() -> None:
    """3 FKB rows declare noConditionsApply and are restricted anyway."""

    base = "http://inspire.ec.europa.eu/metadata-codelist/ConditionsApplyingToAccessAndUse/"
    assert licence_family(base + "noConditionsApply") == "INSPIRE no-conditions"
    assert licence_family(base + "conditionsUnknown") == "INSPIRE conditions unknown"
    assert not same_licence(base + "noConditionsApply", base + "conditionsUnknown")


def test_an_unknown_licence_is_not_called_permissive() -> None:
    assert licence_family("https://example.no/our-own-terms") is None
    assert licence_family(None) is None
    assert licence_family("") is None
    assert not same_licence("https://a.no/terms", "https://b.no/terms")
    assert same_licence("https://a.no/terms", "https://a.no/terms/"), "same string, same thing"
    assert not same_licence(None, None), "two absences are not an agreement"
