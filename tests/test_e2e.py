import asyncio
import os

import pytest
import yaml

import diffweave.ai

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not OPENAI_API_KEY, reason="requires OPENAI_API_KEY env var"),
]


@pytest.fixture()
def real_openai_config(monkeypatch, tmp_path):
    file_path = tmp_path / "config.yaml"
    file_path.write_text(
        yaml.safe_dump({
            "type": "token",
            "model_name": "gpt-4o-mini",
            "endpoint": "https://api.openai.com/v1",
            "token": OPENAI_API_KEY,
        })
    )
    monkeypatch.setattr("diffweave.ai.CONFIG_FILE", file_path)
    yield file_path


def test_query_model_returns_response(real_openai_config):
    """Verify that LLM.query_model succeeds with the correct default endpoint."""
    llm = diffweave.ai.LLM()
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(llm.query_model(["Say hello in one word."]))
    assert isinstance(result, str)
    assert len(result) > 0


def test_default_endpoint_is_not_responses_path(real_openai_config):
    """Regression: configured endpoint must not include /responses or chat/completions calls will 404."""
    config = yaml.safe_load(real_openai_config.read_text())
    assert not config["endpoint"].endswith("/responses"), (
        "Endpoint must not end with /responses — that causes 404 on /chat/completions"
    )
