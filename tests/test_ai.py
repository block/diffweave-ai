from pathlib import Path
import datetime

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice, CompletionUsage


import diffweave


def test_configuring_new_model(config_file: Path):
    assert not config_file.exists()
    diffweave.ai.configure_token_model(
        "some_model",
        "https://api.example.com",
        "my_token",
        config_file=config_file,
    )
    assert config_file.exists()


def test_setting_default_model(config_file):
    with pytest.raises(ValueError):
        diffweave.ai.set_default_model("some_model", config_file=config_file)

    diffweave.ai.configure_token_model(
        "some_model",
        "https://api.example.com",
        "my_token",
        config_file=config_file,
    )
    diffweave.ai.set_default_model("some_model", config_file=config_file)


@pytest.fixture()
def fake_config(mocker):
    conf_file = mocker.Mock()
    conf_file.exists.return_value = True
    conf_file.read_text.return_value = """
<<DEFAULT>>: claude-sonnet-4-5
claude-sonnet-4-5:
  endpoint: https://api.example.com
  token: asdfkljhsadfkljfhasdlkfhasdklfjh
    """.strip()
    return conf_file


@pytest.mark.asyncio
async def test_querying(fake_config, mocker):
    response_content = "this is a git commit message"

    MockClient = mocker.Mock()
    MockClient.return_value.chat.completions.create.return_value = _build_completion_from_message(response_content)
    mocker.patch("openai.OpenAI", MockClient)
    conn = diffweave.ai.LLM("claude-sonnet-4-5", config_file=fake_config)

    assert await conn.query_model(["some_query"]) == response_content


@pytest.mark.asyncio
async def test_query_with_backtick_response(fake_config, mocker):
    response_content = "this is a git commit message"
    backtick_response = f"```\n{response_content}\n```"

    MockClient = mocker.Mock()
    MockClient.return_value.chat.completions.create.return_value = _build_completion_from_message(backtick_response)
    mocker.patch("openai.OpenAI", MockClient)
    conn = diffweave.ai.LLM("claude-sonnet-4-5", config_file=fake_config)

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
