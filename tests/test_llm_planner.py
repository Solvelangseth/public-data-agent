from __future__ import annotations

from public_data_agent.llm_planner import candidate_context, plan_with_provider, validate_model_plan


def _payload() -> dict:
    return {
        "intent": "catalog_search",
        "search_query": "strandsonedata",
        "requirements": ["strandsonedata"],
        "steps": [{"kind": "search", "reason": "find matching catalog records"}],
    }


def test_model_plan_accepts_only_candidate_datasets() -> None:
    payload = _payload()
    payload["steps"] = [{"kind": "fetch", "dataset_id": "known:1", "periods": [2024, 2025]}]
    result = validate_model_plan(payload, question="test", candidate_dataset_ids={"known:1"})
    assert result.error is None
    assert result.plan is not None
    assert result.plan.parser == "llm_structured_plan"


def test_model_plan_rejects_unknown_ids_and_factual_fields() -> None:
    payload = _payload()
    payload["steps"] = [{"kind": "fetch", "dataset_id": "invented:1"}]
    result = validate_model_plan(payload, question="test", candidate_dataset_ids={"known:1"})
    assert result.plan is None
    assert "outside candidates" in (result.error or "")

    payload = _payload()
    payload["values"] = [123]
    result = validate_model_plan(payload, question="test", candidate_dataset_ids=set())
    assert result.plan is None
    assert "factual" in (result.error or "")

    payload = _payload()
    payload["steps"] = [{"kind": "query_data"}]
    result = validate_model_plan(payload, question="test", candidate_dataset_ids=set())
    assert result.plan is None
    assert "unsupported" in (result.error or "")


def test_provider_output_is_validated_before_acceptance() -> None:
    class Provider:
        def make_plan(self, question, candidates):
            return _payload()

    result = plan_with_provider(
        Provider(), question="strandsonedata", candidates=[{"dataset_id": "known:1"}]
    )
    assert result.plan is not None
    assert result.plan.question == "strandsonedata"


def test_candidate_context_is_bounded_and_contains_registry_facts() -> None:
    class Hit:
        dataset_id = "known:1"
        title = "Known"
        publisher = {"name": "Publisher"}
        license = None
        access_path = "https://example.test/table/123"
        why = "matched title"

    class Report:
        hits = [Hit()]

    context = candidate_context(Report(), limit=1)
    assert context == [{
        "dataset_id": "known:1",
        "title": "Known",
        "publisher": {"name": "Publisher"},
        "license": None,
        "access_path": "https://example.test/table/123",
        "table_id": "123",
        "why": "matched title",
    }]
