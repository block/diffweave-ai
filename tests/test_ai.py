from pathlib import Path
import datetime

import pytest
import yaml
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice, CompletionUsage


import diffweave


def test_configuring_new_model(config_file: Path, monkeypatch):
    monkeypatch.setattr("diffweave.ai.CONFIG_FILE", config_file)
    assert not config_file.exists()
    diffweave.ai.configure_token_model(
        "some_model",
        "https://api.example.com",
        "my_token",
    )
    assert config_file.exists()


def test_overwriting_model(config_file, monkeypatch):
    monkeypatch.setattr("diffweave.ai.CONFIG_FILE", config_file)
    diffweave.ai.configure_token_model("model_a", "https://api.example.com", "token_a")
    diffweave.ai.configure_token_model("model_b", "https://other.example.com", "token_b")
    config = yaml.safe_load(config_file.read_text())
    assert config["model_name"] == "model_b"
    assert config["endpoint"] == "https://other.example.com"


@pytest.fixture()
def fake_config(monkeypatch, config_file):
    config_file.write_text(
        yaml.safe_dump(
            {
                "type": "token",
                "model_name": "claude-sonnet-4-5",
                "endpoint": "https://api.example.com",
                "token": "asdfkljhsadfkljfhasdlkfhasdklfjh",
            }
        )
    )
    monkeypatch.setattr("diffweave.ai.CONFIG_FILE", config_file)
    return config_file


@pytest.mark.asyncio
async def test_querying(fake_config, mocker):
    response_content = "this is a git commit message"

    MockClient = mocker.Mock()
    MockClient.return_value.chat.completions.create.return_value = _build_completion_from_message(response_content)
    mocker.patch("openai.OpenAI", MockClient)
    conn = diffweave.ai.LLM()

    assert await conn.query_model(["some_query"]) == response_content


@pytest.mark.asyncio
async def test_query_with_backtick_response(fake_config, mocker):
    response_content = "this is a git commit message"
    backtick_response = f"```\n{response_content}\n```"

    MockClient = mocker.Mock()
    MockClient.return_value.chat.completions.create.return_value = _build_completion_from_message(backtick_response)
    mocker.patch("openai.OpenAI", MockClient)
    conn = diffweave.ai.LLM()

    assert await conn.query_model(["some_query"]) == response_content


def _build_completion_from_message(content: str) -> ChatCompletion:
    return ChatCompletion(
        id="asdf",
        created=int(datetime.datetime.now().timestamp()),
        model="model",
        object="chat.completion",
        choices=[
            Choice(index=0, finish_reason="stop", message=ChatCompletionMessage(content=content, role="assistant"))
        ],
    )
