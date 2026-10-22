"""The third question: may this be passed on?

`datasets.license` answers "may it be used". For a service whose shape is
handing data to other people's agents, redistribution is a separate
permission, and the registry had one column for both. These are the cases
where getting it wrong ships data the project may not ship.

The rule under all of them: **never `allowed` by default.** A missing row, an
unrecognised licence and an absent licence are all `unknown`, because the
alternative is a commercial service relying on a row nobody wrote.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.licences import (
    ALLOWED,
    ALLOWED_WITH_ATTRIBUTION,
    DENIED,
    UNKNOWN,
    redistribution_verdict,
)
from public_data_agent.registry import Registry

WHEN = "2026-10-22T12:00:00+00:00"


def _registry(tmp_path: Path, licence: str | None, dataset_id: str = "x:y") -> Registry:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(
        dataset_id=dataset_id, title="A dataset", publisher_name="Someone",
        access_path="https://example.no/data", license=licence,
    )
    return registry


def test_a_recorded_family_decides_it(tmp_path: Path) -> None:
    registry = _registry(tmp_path, "https://creativecommons.org/licenses/by/4.0/")
    try:
        registry.set_licence_terms(
            "CC-BY",
            redistribution=ALLOWED_WITH_ATTRIBUTION,
            commercial_use=ALLOWED,
            attribution_required=True,
            source_url="https://creativecommons.org/licenses/by/4.0/legalcode",
        )
        out = redistribution_verdict(registry, "x:y")
        assert out["family"] == "CC-BY"
        assert out["verdict"] == ALLOWED_WITH_ATTRIBUTION
        assert out["attribution_required"] is True
        assert out["source_url"].startswith("https://creativecommons.org/")
    finally:
        registry.close()


def test_two_spellings_of_one_licence_get_one_verdict(tmp_path: Path) -> None:
    """The reason the terms are keyed by family at all.

    The datanorge harvest writes EU publications-office URIs and Geonorge
    writes canonical licence URLs. Comparing the strings reported 668
    disagreements of which zero were real.
    """

    registry = Registry(tmp_path / "registry.sqlite")
    try:
        for i, licence in enumerate((
            "http://publications.europa.eu/resource/authority/licence/CC_BY_4_0",
            "https://creativecommons.org/licenses/by/4.0/",
        )):
            registry.ensure_dataset_identity(
                dataset_id=f"x:{i}", title="t", publisher_name=None,
                access_path=f"https://example.no/{i}", license=licence,
            )
        registry.set_licence_terms(
            "CC-BY", redistribution=ALLOWED_WITH_ATTRIBUTION, commercial_use=ALLOWED,
            attribution_required=True, source_url="https://creativecommons.org/licenses/by/4.0/",
        )
        assert {redistribution_verdict(registry, f"x:{i}")["verdict"] for i in (0, 1)} == {
            ALLOWED_WITH_ATTRIBUTION
        }
    finally:
        registry.close()


def test_no_recorded_terms_is_unknown_not_allowed(tmp_path: Path) -> None:
    registry = _registry(tmp_path, "https://data.norge.no/nlod/no/2.0/")
    try:
        out = redistribution_verdict(registry, "x:y")
        assert out["family"] == "NLOD"
        assert out["verdict"] == UNKNOWN
        assert "no terms recorded" in out["basis"]
    finally:
        registry.close()


def test_no_licence_at_all_is_unknown_with_a_reason(tmp_path: Path) -> None:
    registry = _registry(tmp_path, None)
    try:
        out = redistribution_verdict(registry, "x:y")
        assert out["verdict"] == UNKNOWN
        assert out["family"] is None
        assert out["basis"] == "no licence recorded for this dataset"
    finally:
        registry.close()


def test_an_unrecognised_licence_is_unknown_not_permissive(tmp_path: Path) -> None:
    registry = _registry(tmp_path, "https://example.no/our-own-terms.html")
    try:
        out = redistribution_verdict(registry, "x:y")
        assert out["verdict"] == UNKNOWN
        assert "belongs to no family" in out["basis"]
    finally:
        registry.close()


def test_norge_digitalt_is_declined_not_pending(tmp_path: Path) -> None:
    """Kartverket answered on 2026-10-22: no membership for a commercial
    startup. Returning `unknown` would keep inviting someone to go and ask."""

    registry = _registry(tmp_path, "https://www.geonorge.no/Geodataarbeid/Norge-digitalt/Avtaler")
    try:
        out = redistribution_verdict(registry, "x:y")
        assert out["family"] == "Norge digitalt"
        assert out["verdict"] == DENIED
        assert "declined" in out["basis"] and "2026-10-22" in out["basis"]
    finally:
        registry.close()


def test_a_declined_agreement_beats_a_recorded_permission(tmp_path: Path) -> None:
    """A permissive licence on data we may not obtain is still data we may not
    pass on. The override has to sit above the lookup, not beside it."""

    registry = _registry(tmp_path, "https://www.geonorge.no/norge-digitalt/avtale")
    try:
        registry.set_licence_terms(
            "Norge digitalt", redistribution=ALLOWED, commercial_use=ALLOWED,
            source_url="https://example.no/someone-filled-this-in-wrongly",
        )
        assert redistribution_verdict(registry, "x:y")["verdict"] == DENIED
    finally:
        registry.close()


def test_non_commercial_cannot_be_recorded_into_permission(tmp_path: Path) -> None:
    """51 datasets declare CC-BY-NC. No credential opens them and no probe
    reports the problem, so a stray row must not be able to."""

    registry = _registry(tmp_path, "https://creativecommons.org/licenses/by-nc/4.0/")
    try:
        registry.set_licence_terms(
            "CC-BY-NC", redistribution=ALLOWED, commercial_use=ALLOWED,
            source_url="https://example.no/wrong",
        )
        out = redistribution_verdict(registry, "x:y")
        assert out["verdict"] == DENIED
        assert "forbids commercial use" in out["basis"]
    finally:
        registry.close()


def test_terms_without_a_source_are_refused(tmp_path: Path) -> None:
    """A verdict with no text behind it is an opinion."""

    registry = Registry(tmp_path / "registry.sqlite")
    try:
        for blank in ("", "   ", None):
            with pytest.raises(ValueError, match="source_url"):
                registry.set_licence_terms(
                    "CC-BY", redistribution=ALLOWED, commercial_use=ALLOWED,
                    source_url=blank,  # type: ignore[arg-type]
                )
    finally:
        registry.close()


def test_the_vocabulary_is_fixed(tmp_path: Path) -> None:
    """`"probably fine"` must not be storable where `allowed` is read."""

    registry = Registry(tmp_path / "registry.sqlite")
    try:
        with pytest.raises(ValueError, match="redistribution"):
            registry.set_licence_terms(
                "CC-BY", redistribution="probably fine", commercial_use=ALLOWED,
                source_url="https://example.no/x",
            )
        with pytest.raises(ValueError, match="commercial_use"):
            registry.set_licence_terms(
                "CC-BY", redistribution=ALLOWED, commercial_use="yes",
                source_url="https://example.no/x",
            )
    finally:
        registry.close()


def test_recording_terms_twice_updates_rather_than_duplicates(tmp_path: Path) -> None:
    registry = _registry(tmp_path, "https://data.norge.no/nlod/no/2.0/")
    try:
        registry.set_licence_terms(
            "NLOD", redistribution=UNKNOWN, commercial_use=UNKNOWN,
            source_url="https://data.norge.no/nlod/no/2.0/",
        )
        registry.set_licence_terms(
            "NLOD", redistribution=ALLOWED_WITH_ATTRIBUTION, commercial_use=ALLOWED,
            attribution_required=True, source_url="https://data.norge.no/nlod/no/2.0/",
            notes="read 2026-10-22",
        )
        assert redistribution_verdict(registry, "x:y")["verdict"] == ALLOWED_WITH_ATTRIBUTION
        assert registry.conn.execute(
            "SELECT COUNT(*) FROM licence_terms WHERE family = 'NLOD'"
        ).fetchone()[0] == 1
    finally:
        registry.close()


def test_an_unknown_dataset_raises(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        with pytest.raises(ValueError, match="unknown dataset"):
            redistribution_verdict(registry, "nothing:here")
    finally:
        registry.close()
