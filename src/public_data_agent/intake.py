"""First node of the pipeline: read the question, before anything is searched.

A model is genuinely good at this part — Norwegian phrasing, inflection, an
implied geography, an unstated period. So this is the one place the model is
allowed to interpret. What it is not allowed to do is answer: intake runs
before any search, so it has no datasets, no observations and no numbers, and
anything resembling a factual claim in its output is rejected rather than
carried forward.

The output is a reading of the question, not knowledge about the world. It is
validated the same way plans are, and there is a deterministic fallback so the
pipeline and the whole test suite work with no model available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from public_data_agent.search import tokenize

# A period a Norwegian public-statistics question could plausibly mean. Outside
# this range the model has produced a token that is not a year.
MIN_YEAR = 1800
MAX_YEAR = 2100

YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2}|21\d{2})\b")

SPECIFIC = "specific"
EXPLORATORY = "exploratory"
SHAPES = {SPECIFIC, EXPLORATORY}

# Output fields that would mean the model answered instead of read the question.
FORBIDDEN_FIELDS = {
    "answer",
    "value",
    "values",
    "observations",
    "result",
    "results",
    "dataset_id",
    "dataset_ids",
    "table_id",
    "table_ids",
    "license",
    "source",
    "sources",
}

# Words that signal the question wants a comparison rather than one figure.
COMPARISON_HINTS = (
    "størst", "storst", "minst", "mest", "vekst", "vokser", "endring",
    "sammenlign", "utvikling", "trend", "rangér", "ranger", "flest", "færrest",
)
# Words that signal an open-ended investigation rather than a lookup.
EXPLORATORY_HINTS = (
    "hvorfor", "sammenheng", "korrelasjon", "henger sammen", "analyser",
    "utforsk", "mønster", "monster", "påvirker", "pavirker", "forklar",
)


class IntakeProvider(Protocol):
    def read_question(self, question: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Request:
    """A structured reading of what was asked. Contains no facts."""

    question: str
    search_terms: list[str]
    shape: str
    parser: str
    geography: str | None = None
    measure: str | None = None
    periods: tuple[int, ...] = ()
    comparison: bool = False
    ambiguities: list[str] = field(default_factory=list)
    clarifying_question: str | None = None

    @property
    def needs_clarification(self) -> bool:
        return bool(self.clarifying_question)

    def search_query(self) -> str:
        """The string handed to search. Terms only, never the raw sentence."""

        return " ".join(self.search_terms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": "intake",
            "question": self.question,
            "search_terms": list(self.search_terms),
            "search_query": self.search_query(),
            "shape": self.shape,
            "parser": self.parser,
            "geography": self.geography,
            "measure": self.measure,
            "periods": list(self.periods),
            "comparison": self.comparison,
            "ambiguities": list(self.ambiguities),
            "clarifying_question": self.clarifying_question,
            "needs_clarification": self.needs_clarification,
            "numbers_retrieved": False,
        }


@dataclass(frozen=True)
class IntakeValidation:
    request: Request | None
    error: str | None = None


def read_question(question: str) -> Request:
    """Deterministic reading. No model, no network, always available.

    This is the fallback and the baseline: terms come from the same tokenizer
    search uses, so the terms handed on are ones the index could match.
    """

    if not question or not question.strip():
        raise ValueError("question is empty")
    terms = tokenize(question)
    lowered = question.casefold()
    years = tuple(
        sorted({int(match) for match in YEAR_RE.findall(question) if MIN_YEAR <= int(match) <= MAX_YEAR})
    )
    return Request(
        question=question,
        search_terms=terms,
        shape=EXPLORATORY if any(hint in lowered for hint in EXPLORATORY_HINTS) else SPECIFIC,
        parser="deterministic",
        periods=years,
        comparison=any(hint in lowered for hint in COMPARISON_HINTS),
    )


def validate_intake(payload: dict[str, Any], *, question: str) -> IntakeValidation:
    """Accept a model's reading only if it is a reading and nothing more."""

    if not isinstance(payload, dict):
        return IntakeValidation(None, "intake output must be an object")
    present = FORBIDDEN_FIELDS.intersection(payload)
    if present:
        return IntakeValidation(
            None,
            f"intake output contains fields it cannot know before searching: {sorted(present)}",
        )

    raw_terms = payload.get("search_terms")
    if not isinstance(raw_terms, list) or not raw_terms:
        return IntakeValidation(None, "intake output needs a non-empty search_terms list")
    terms: list[str] = []
    for item in raw_terms:
        if not isinstance(item, str) or not item.strip():
            return IntakeValidation(None, "every search term must be a non-empty string")
        # Fold through the same tokenizer search uses; a term the index cannot
        # match is not a useful term, however well it reads.
        folded = tokenize(item)
        for token in folded:
            if token not in terms:
                terms.append(token)
    if not terms:
        return IntakeValidation(None, "no search term survived tokenization")

    shape = payload.get("shape", SPECIFIC)
    if shape not in SHAPES:
        return IntakeValidation(None, f"shape must be one of {sorted(SHAPES)}")

    raw_periods = payload.get("periods", [])
    if not isinstance(raw_periods, list):
        return IntakeValidation(None, "periods must be a list")
    periods: list[int] = []
    for item in raw_periods:
        if isinstance(item, bool) or not isinstance(item, int):
            return IntakeValidation(None, "periods must be integers")
        if not MIN_YEAR <= item <= MAX_YEAR:
            return IntakeValidation(None, f"period {item} is not a plausible year")
        periods.append(item)

    ambiguities = payload.get("ambiguities", [])
    if not isinstance(ambiguities, list) or any(not isinstance(a, str) for a in ambiguities):
        return IntakeValidation(None, "ambiguities must be strings")

    clarifying = payload.get("clarifying_question")
    if clarifying is not None and (not isinstance(clarifying, str) or not clarifying.strip()):
        return IntakeValidation(None, "clarifying_question must be a non-empty string or null")

    for key in ("geography", "measure"):
        value = payload.get(key)
        if value is not None and not isinstance(value, str):
            return IntakeValidation(None, f"{key} must be a string or null")

    return IntakeValidation(
        Request(
            question=question,
            search_terms=terms,
            shape=shape,
            parser="llm_intake",
            geography=payload.get("geography"),
            measure=payload.get("measure"),
            periods=tuple(sorted(set(periods))),
            comparison=bool(payload.get("comparison", False)),
            ambiguities=ambiguities,
            clarifying_question=clarifying,
        )
    )


def intake_with_provider(provider: IntakeProvider, *, question: str) -> IntakeValidation:
    """Ask a provider to read the question, then validate what came back."""

    payload = provider.read_question(question)
    return validate_intake(payload, question=question)


def read_question_with_fallback(
    question: str, provider: IntakeProvider | None = None
) -> tuple[Request, str | None]:
    """Prefer the model's reading; fall back to the deterministic one.

    A provider that errors or returns something invalid must not take the
    pipeline down: the deterministic reading is always good enough to search
    with. The rejection reason is returned so it stays visible rather than
    being swallowed.
    """

    if provider is None:
        return read_question(question), None
    try:
        validation = intake_with_provider(provider, question=question)
    except Exception as exc:
        return read_question(question), f"intake provider failed: {exc}"
    if validation.request is None:
        return read_question(question), validation.error
    return validation.request, None


INTAKE_INSTRUCTIONS = """You read a Norwegian public-statistics question and return JSON only.

You run BEFORE any search. You have no datasets, no tables and no numbers, so you
cannot know what data exists. Do not answer the question. Do not name a dataset, a
table id, a source or a licence. Do not include any value or figure.

Return exactly these fields:
  search_terms        list of Norwegian search words, base form, no question words
  geography           the place or administrative level asked about, or null
  measure             what is being measured, in the asker's words, or null
  periods             list of 4-digit years explicitly mentioned; [] if none
  comparison          true if the question asks to rank, compare or measure change
  shape               "specific" or "exploratory" — see below
  ambiguities         short strings naming what is genuinely unclear; [] if clear
  clarifying_question one short Norwegian question, or null

Choosing shape. Default to "specific". Ranking, growth, comparison and "how has X
changed" are all specific: they name the figures wanted and need no investigation.
Use "exploratory" only when answering requires deciding for yourself which
variables to relate — asking why something happened, whether two things are
connected, or what explains a pattern.
  specific     "hvilke bydeler er størst", "arbeidsledighet i Trondheim siste år"
  exploratory  "hvorfor stiger boligprisene", "henger utdanning og inntekt sammen"

Set clarifying_question only when a wrong reading would send the search somewhere
materially different. An unstated period or an unstated geography is usually not
worth asking about; a question that could mean two unrelated topics is.
"""
