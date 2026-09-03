from __future__ import annotations

import pytest

from public_data_agent.intake import (
    EXPLORATORY,
    SPECIFIC,
    read_question,
    read_question_with_fallback,
    validate_intake,
)


def test_deterministic_reading_extracts_terms_periods_and_shape() -> None:
    request = read_question("arbeidsledighet i Trondheim i 2024 og 2025")
    assert request.parser == "deterministic"
    assert "arbeidsledighet" in request.search_terms
    assert "trondheim" in request.search_terms
    assert request.periods == (2024, 2025)
    assert request.shape == SPECIFIC
    # A reading is not an answer.
    assert request.to_dict()["numbers_retrieved"] is False


def test_deterministic_reading_marks_open_investigation_as_exploratory() -> None:
    assert read_question("Hvorfor stiger boligprisene?").shape == EXPLORATORY
    assert read_question("folketall Bergen").shape == SPECIFIC


def test_reading_drops_question_words_so_they_do_not_become_requirements() -> None:
    request = read_question("Hvilke Oslo-bydeler er størst?")
    assert "hvilke" not in request.search_terms
    # Inflections fold onto the tokens the index actually stores.
    assert "bydel" in request.search_terms


def test_intake_rejects_output_that_answers_instead_of_reading() -> None:
    """Intake runs before any search, so it cannot know these fields."""

    for field in ("answer", "values", "dataset_id", "table_id", "license", "sources"):
        result = validate_intake(
            {"search_terms": ["befolkning"], field: "anything"}, question="q"
        )
        assert result.request is None
        assert field in (result.error or "")


def test_intake_rejects_implausible_or_non_integer_periods() -> None:
    for periods in ([1200], ["2025"], [True], [99999]):
        result = validate_intake(
            {"search_terms": ["befolkning"], "periods": periods}, question="q"
        )
        assert result.request is None, f"{periods} must be refused"


def test_intake_folds_model_terms_through_the_search_tokenizer() -> None:
    """A term the index cannot match is not useful, however well it reads."""

    result = validate_intake(
        {"search_terms": ["Hvilke bydeler", "folketall"], "shape": SPECIFIC},
        question="q",
    )
    assert result.request is not None
    assert result.request.search_terms == ["bydel", "befolkning"]


def test_intake_requires_a_known_shape() -> None:
    result = validate_intake(
        {"search_terms": ["befolkning"], "shape": "guesswork"}, question="q"
    )
    assert result.request is None
    assert "shape" in (result.error or "")


def test_clarifying_question_marks_the_request_as_needing_input() -> None:
    result = validate_intake(
        {"search_terms": ["utslipp"], "clarifying_question": "Hvilken type utslipp?"},
        question="Fortell meg om utslipp",
    )
    assert result.request is not None
    assert result.request.needs_clarification is True


def test_fallback_uses_the_deterministic_reading_and_keeps_the_reason() -> None:
    class BrokenProvider:
        def read_question(self, question):
            raise RuntimeError("provider exploded")

    request, warning = read_question_with_fallback("folketall Bergen", BrokenProvider())
    assert request.parser == "deterministic"
    assert "provider exploded" in (warning or "")
    assert "befolkning" in request.search_terms


def test_fallback_reports_a_rejected_reading_rather_than_swallowing_it() -> None:
    class AnsweringProvider:
        def read_question(self, question):
            return {"search_terms": ["befolkning"], "answer": "670 000"}

    request, warning = read_question_with_fallback("folketall Bergen", AnsweringProvider())
    assert request.parser == "deterministic"
    assert "answer" in (warning or "")


def test_empty_question_is_refused() -> None:
    with pytest.raises(ValueError):
        read_question("   ")
