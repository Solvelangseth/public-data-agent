"""The coverage set's two files must stay in step.

The set is registry-derived, unlike the tuned and held-out sets, so its note
carries that warning and this test keeps the files consistent. It asserts
structure only: the registry is not in git, so no id can be resolved here.
"""

from __future__ import annotations

import json
from pathlib import Path

QUESTIONS = Path("data/coverage_questions.json")
GOLD = Path("data/coverage_gold.json")


def test_questions_and_gold_cover_the_same_ids() -> None:
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    ids = [q["id"] for q in questions["questions"]]
    assert ids == [q["id"] for q in gold["questions"]]
    assert len(ids) == len(set(ids))
    for question in questions["questions"]:
        assert question["query"].strip()
        assert question["style"] in {"keyword", "natural"}
    for answer in gold["questions"]:
        # Unlike the tuned set, no coverage question is a coverage finding:
        # each was written from a resource that was read first.
        assert answer["expected"], answer["id"]
        assert len(answer["expected"]) == len(set(answer["expected"]))


def test_the_note_says_the_set_is_registry_derived() -> None:
    note = json.loads(QUESTIONS.read_text(encoding="utf-8"))["note"]
    assert "derived from the registry" in note
    assert "never be used to choose or tune" in note
