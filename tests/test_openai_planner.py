from __future__ import annotations

import json

from public_data_agent.openai_planner import OpenAIPlanProvider, SYSTEM_PROMPT


def test_prompt_requires_contract_shape() -> None:
    assert '"requirements":["..."]' in SYSTEM_PROMPT
    assert "search|fetch|filter|reshape|join|derive|visualize|export" in SYSTEM_PROMPT


def test_provider_reads_key_from_dotenv_without_printing_or_exporting(tmp_path, monkeypatch) -> None:
    # The documented workflow is `set -a; source .env; set +a`, which exports the
    # real key. Without this the test read the developer's own key and failed.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=secret-test-key\n", encoding="utf-8")
    provider = OpenAIPlanProvider.from_env(dotenv=env)
    assert provider.api_key == "secret-test-key"


def test_provider_posts_question_and_candidates_and_parses_json(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"output_text": '{"steps":[{"kind":"search"}]}'}).encode()

    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data)
        seen["auth"] = request.headers["Authorization"]
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr("public_data_agent.openai_planner.urlopen", fake_urlopen)
    result = OpenAIPlanProvider("secret").make_plan("test", [{"dataset_id": "known:1"}])
    assert result == {"steps": [{"kind": "search"}]}
    assert seen["url"].endswith("/v1/responses")
    assert seen["auth"] == "Bearer secret"
    assert json.loads(seen["body"]["input"][1]["content"][0]["text"])["question"] == "test"
