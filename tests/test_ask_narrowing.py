"""The request carries what the question pinned down, or says it could not.

Before this, `_execute_catalog_plan` sent the planned fetch with no filter and
then returned `list_observations(dataset_id)` -- every row the dataset had
ever accumulated. Asked for household waste per inhabitant in Bærum against
Asker in 2024 it fetched 264,033 cells, returned all of them, and reported
`numbers_retrieved: true`. The same request with the kommune and year filled
in returns 27.

Nothing here talks to a publisher: `fetch_observations` is replaced so the
tests assert on the arguments the request would have carried.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from public_data_agent import ask as ask_module
from public_data_agent.ask import ASK_MAX_CELLS, _execute_catalog_plan
from public_data_agent.constraints import SCHEME
from public_data_agent.planner import PlanStep, QuestionPlan

REGISTER = [("3201", "BÆRUM"), ("3203", "ASKER"), ("3428", "ALVDAL")]


class _Counts:
    def __init__(self, listed: int) -> None:
        self.listed = listed
        self.inserted = listed
        self.updated = 0
        self.unchanged = 0
        self.failed = 0


class _Fetched:
    def __init__(self, ids: list[str], listed: int) -> None:
        self.dataset_id = "ssbtable:13035"
        self.table_id = "13035"
        self.request_url = "https://data.ssb.no/api/v0/no/table/13035"
        self.http_status = 200
        self.counts = _Counts(listed)
        self.sample = []
        self.observation_ids = ids


class _Registry:
    """A registry with the register, a dataset row, and stored observations."""

    def __init__(self, register: list[tuple[str, str]] = REGISTER) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE records (subject_scheme TEXT, subject_code TEXT, subject_label TEXT)"
        )
        self.conn.executemany(
            "INSERT INTO records VALUES (?, ?, ?)",
            [(SCHEME, code, label) for code, label in register],
        )
        self.conn.commit()
        self.asked_for_ids: list[str] | None = None

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return {"id": dataset_id, "publisher_name": "SSB", "license": None,
                "access_path": "https://data.ssb.no/api/v0/no/table/13035"}

    def list_observations(self, dataset_id: str | None = None, *, ids: list[str] | None = None,
                          series: str | None = None) -> list[dict[str, Any]]:
        # The whole point: the caller must ask by id, never by dataset.
        self.asked_for_ids = ids
        if ids is None:
            raise AssertionError(
                "list_observations was called by dataset_id; that returns every row "
                "the dataset ever accumulated, which is the 264,033 bug"
            )
        return [
            {"id": obs_id, "dataset_id": "ssbtable:13035", "table_id": "13035",
             "measure": "Årsinnbyggere (antall)", "value_json": "132411",
             "dimensions_json": '{"KOKkommuneregion0000":"Bærum","Tid":"2024"}',
             "publisher_name": "SSB", "license": None, "access_path": None,
             "request_url": None, "http_status": 200}
            for obs_id in ids
        ]

    def close(self) -> None:
        self.conn.close()


def _plan(question: str) -> QuestionPlan:
    return QuestionPlan(
        question=question,
        intent="catalog_search_and_optional_fetch",
        parser="test",
        search_query=question,
        requirements=[],
        steps=[PlanStep(kind="fetch", reason="ranked hit",
                        dataset_id="ssbtable:13035", table_id="13035")],
    )


@pytest.fixture
def registry() -> _Registry:
    reg = _Registry()
    yield reg
    reg.close()


def _record_calls(monkeypatch, listed: int = 27) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake(registry, dataset_id, **kwargs):
        calls.append({"dataset_id": dataset_id, **kwargs})
        n = len(calls)
        return _Fetched([f"obs-{n}-{i}" for i in range(listed)], listed)

    monkeypatch.setattr(ask_module, "fetch_observations", fake)
    return calls


def test_the_question_that_started_this(registry: _Registry, monkeypatch) -> None:
    calls = _record_calls(monkeypatch)
    out = _execute_catalog_plan(
        registry,
        _plan("Hvor mye husholdningsavfall per innbygger hadde Bærum i 2024 "
              "sammenlignet med Asker?"),
        http=None,
    )
    assert [call["kommune"] for call in calls] == ["3201", "3203"], "one request per place"
    assert all(call["from_year"] == 2024 and call["to_year"] == 2024 for call in calls)
    assert out["narrowing"]["years"] == [2024]
    assert "narrowed to place Bærum, Asker; year 2024" in out["explanation"]


def test_only_the_fetched_rows_come_back(registry: _Registry, monkeypatch) -> None:
    """`list_observations(dataset_id)` is the 264,033; ids are the 54."""

    _record_calls(monkeypatch, listed=27)
    out = _execute_catalog_plan(registry, _plan("avfall i Bærum og Asker 2024"), http=None)
    assert registry.asked_for_ids is not None
    assert len(registry.asked_for_ids) == 54, "two places at 27 cells each"
    assert len(out["observations"]) == 54


def test_every_request_carries_a_cell_budget(registry: _Registry, monkeypatch) -> None:
    """Narrowing can fail; the ceiling must not depend on it having worked."""

    calls = _record_calls(monkeypatch)
    _execute_catalog_plan(registry, _plan("avfall i Alvdal 2019"), http=None)
    assert all(call["max_cells"] == ASK_MAX_CELLS for call in calls)
    assert ASK_MAX_CELLS < 264_033


def test_a_question_naming_no_place_still_asks_once(registry: _Registry, monkeypatch) -> None:
    calls = _record_calls(monkeypatch)
    out = _execute_catalog_plan(registry, _plan("avfall i Norge 2024"), http=None)
    assert len(calls) == 1
    assert calls[0]["kommune"] is None
    assert calls[0]["from_year"] == 2024
    assert out["narrowing"]["places"] == []


def test_a_year_range_becomes_from_and_to(registry: _Registry, monkeypatch) -> None:
    calls = _record_calls(monkeypatch)
    _execute_catalog_plan(registry, _plan("avfall i Bærum fra 2015 til 2024"), http=None)
    assert calls[0]["from_year"] == 2015 and calls[0]["to_year"] == 2024


def test_an_ambiguous_place_is_not_narrowed_and_is_said_out_loud(monkeypatch) -> None:
    """The register holding two codes for one name is not a tie to break.

    Narrowing to either would answer confidently about one Oslo and never
    mention the other existed.
    """

    registry = _Registry([("0301", "OSLO"), ("301", "OSLO"), ("3201", "BÆRUM")])
    try:
        calls = _record_calls(monkeypatch)
        out = _execute_catalog_plan(
            registry, _plan("avfall i Oslo og Bærum 2024"), http=None)
        assert [call["kommune"] for call in calls] == ["3201"], "only the clear one"
        assert out["narrowing"]["unresolved"] == ["Oslo"]
        assert "Not narrowed to Oslo" in out["explanation"]
        assert "more than one code" in out["explanation"]
    finally:
        registry.close()


def test_a_refused_filter_falls_back_and_says_which(registry: _Registry, monkeypatch) -> None:
    """A connector that cannot filter on kommune raises rather than ignoring it.

    That is right, and it must not turn the question into an error -- nor
    quietly return a nationwide answer that reads as if it were Bærum's.
    """

    calls: list[dict[str, Any]] = []

    def fussy(registry_arg, dataset_id, **kwargs):
        calls.append(kwargs)
        if kwargs.get("kommune") is not None:
            raise ValueError("this resource does not filter on kommune")
        return _Fetched(["obs-1"], 1)

    monkeypatch.setattr(ask_module, "fetch_observations", fussy)
    out = _execute_catalog_plan(registry, _plan("avfall i Bærum 2024"), http=None)
    assert out["status"] == "completed"
    assert out["narrowing"]["filter_not_supported"] == ["3201"]
    assert calls[-1]["kommune"] is None, "the fallback drops the place, keeps the year"
    assert calls[-1]["from_year"] == 2024


def test_a_fetch_that_fails_outright_is_still_a_failure(registry: _Registry, monkeypatch) -> None:
    """The fallback is for a refused filter, not for a dead endpoint."""

    def dead(registry_arg, dataset_id, **kwargs):
        raise ConnectionError("host is not answering")

    monkeypatch.setattr(ask_module, "fetch_observations", dead)
    out = _execute_catalog_plan(registry, _plan("avfall i Bærum 2024"), http=None)
    assert out["status"] == "fetch_failed"
    assert out["numbers_retrieved"] is False
    assert out["observations"] == []
