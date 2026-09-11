"""Vocabulary derived from Klass, and the ways that source misleads.

Klass records what SSB has renamed. Read carelessly it claims Trøndelag is
Vestlandet and that a question about households is about stationary combustion,
so most of what is tested here is what the extraction refuses to believe.
"""

from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.klass_vocabulary import (
    KlassRewriter,
    build_vocabulary,
    is_rename,
    normalise,
)
from public_data_agent.registry import Registry
from public_data_agent.rewrite import instructions_version, rewriter_name, terms_for


def _klass_dir(tmp_path: Path, versions: dict[str, dict]) -> Path:
    root = tmp_path / "klass"
    (root / "versions").mkdir(parents=True)
    for version_id, payload in versions.items():
        (root / "versions" / f"{version_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    return root


def _version(classification_id: str, items: list[tuple[str, str]]) -> dict:
    return {
        "classification_id": classification_id,
        "classificationItems": [{"code": code, "name": name} for code, name in items],
    }


def test_a_rename_changes_a_word_not_a_spelling() -> None:
    # Real renames, all observed in the downloaded versions.
    assert is_rename("Spesialiserte fosterhjem", "Statlige familiehjem")
    assert is_rename("Førskolelærere", "Førskole-/barnehagelærere")
    assert is_rename("Sør-Trøndelag", "Trøndelag")
    # Punctuation, capitalisation, a corrected typo, a renumbered paragraph and
    # a changed connective are all one name written twice.
    assert not is_rename("Refne - Banken", "Refne/Banken")
    assert not is_rename("Vold-Skog", "Vold-skog")
    assert not is_rename("Sommerr0", "Sommerro")
    assert not is_rename("Hestevold og Holme", "Hestevold - Holme")
    assert not is_rename(
        "Fosterhjem etter barnevernloven § 4-27", "Fosterhjem etter barnevernsloven § 6-3"
    )


def test_normalise_strips_punctuation_and_case() -> None:
    assert normalise("Sør-Trøndelag") == "sør trøndelag"
    assert normalise("  Refne / Banken ") == "refne banken"
    assert normalise(None) == ""


def test_a_renumbered_standard_produces_no_aliases(tmp_path: Path) -> None:
    # Landsdel code 5 was "Trøndelag" and later "Vestlandet", and code 6 was
    # "Trøndelag" too. Reading that as a rename claims the two are one place.
    # The tell is the name belonging to two codes in the same standard.
    root = _klass_dir(
        tmp_path,
        {
            "1": _version("106", [("5", "Trøndelag"), ("6", "Nord-Norge")]),
            "2": _version("106", [("5", "Vestlandet"), ("6", "Trøndelag")]),
        },
    )
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        result = build_vocabulary(registry, root)
        assert result["pairs"] == 0
        assert registry.alias_count() == 0
    finally:
        registry.close()


def test_a_genuine_rename_is_stored_in_both_directions(tmp_path: Path) -> None:
    root = _klass_dir(
        tmp_path,
        {
            "1": _version("104", [("16", "Søndre Trondhjems amt")]),
            "2": _version("104", [("16", "Sør-Trøndelag")]),
        },
    )
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        build_vocabulary(registry, root)
        forward = [row["alias"] for row in registry.aliases_for("sør trøndelag")]
        back = [row["alias"] for row in registry.aliases_for("søndre trondhjems amt")]
        assert forward == ["Søndre Trondhjems amt"]
        assert back == ["Sør-Trøndelag"]
        assert registry.aliases_for("sør trøndelag")[0]["evidence"] == "klass:104:16"
    finally:
        registry.close()


def test_an_alias_needs_the_whole_name_in_the_query(tmp_path: Path) -> None:
    root = _klass_dir(
        tmp_path,
        {
            "1": _version("100", [("1", "Spesialiserte fosterhjem")]),
            "2": _version("100", [("1", "Statlige familiehjem")]),
        },
    )
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        build_vocabulary(registry, root)
        rewriter = KlassRewriter(registry)
        assert rewriter.terms("spesialiserte fosterhjem i Norge") == ["Statlige familiehjem"]
        # One word of the name is not the name; expanding on it would fire on
        # every query containing "fosterhjem".
        assert rewriter.terms("hvor mange fosterhjem finnes det") == []
    finally:
        registry.close()


def test_rewriters_do_not_read_each_others_cached_terms(tmp_path: Path) -> None:
    # A Klass run once scored 0.865 rather than its true 0.811 because the cache
    # was keyed on a default model name and returned terms a model had written.
    class Fake:
        name = "fake-model"

        def terms(self, query: str) -> list[str]:
            return ["konsumprisindeks"]

    registry = Registry(tmp_path / "registry.sqlite")
    try:
        klass = KlassRewriter(registry)
        assert rewriter_name(klass) == "klass"
        assert terms_for(registry, Fake(), "prisene") == ["konsumprisindeks"]
        assert terms_for(registry, klass, "prisene") == []
        version = instructions_version()
        assert registry.get_query_rewrite("prisene", model=f"fake-model@{version}") == [
            "konsumprisindeks"
        ]
        assert registry.get_query_rewrite("prisene", model=f"klass@{version}") == []
        # The prompt is part of the answer, so it is part of the key. Without
        # this, changing the instructions keeps serving terms the old prompt
        # wrote, and the experiment measures nothing.
        assert registry.get_query_rewrite("prisene", model="fake-model@other") is None
    finally:
        registry.close()
