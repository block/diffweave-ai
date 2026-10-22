from pathlib import Path
import datetime
import json
from unittest.mock import AsyncMock

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


def test_configuring_databricks_model(config_file: Path, monkeypatch):
    monkeypatch.setattr("diffweave.ai.CONFIG_FILE", config_file)
    diffweave.ai.configure_databricks_browser_model("databricks-llama", "my-account")
    assert config_file.exists()
    data = yaml.safe_load(config_file.read_text())
    assert data["type"] == "databricks"
    assert data["model_name"] == "databricks-llama"
    assert data["account"] == "my-account"


@pytest.fixture()
def databricks_config(monkeypatch, config_file):
    config_file.write_text(
        yaml.safe_dump(
            {
                "type": "databricks",
                "model_name": "databricks-llama",
                "account": "my-account",
            }
        )
    )
    monkeypatch.setattr("diffweave.ai.CONFIG_FILE", config_file)
    return config_file


def test_llm_init_databricks_cached_token(databricks_config, mocker):
    mocker.patch("diffweave.ai.load_databricks_token", return_value="cached-token")
    llm = diffweave.ai.LLM()
    assert llm.model_name == "databricks-llama"


def test_llm_init_databricks_triggers_login(databricks_config, mocker):
    mocker.patch(
        "diffweave.ai.load_databricks_token",
        side_effect=[None, "new-token"],
    )
    mock_subprocess = mocker.patch("subprocess.run")
    llm = diffweave.ai.LLM()
    mock_subprocess.assert_called_once()
    assert llm.model_name == "databricks-llama"


def test_generate_commit_message(fake_config, mocker):
    mocker.patch.object(
        diffweave.ai.LLM,
        "query_model",
        new=AsyncMock(return_value="feat: add feature"),
    )
    llm = diffweave.ai.LLM()
    result = llm.generate_commit_message("status")
    assert result == "feat: add feature"


def test_generate_commit_message_includes_iteration_history(fake_config, mocker):
    captured = {}

    async def fake_query(self, prompt):
        captured["prompt"] = prompt
        return "feat: refined message"

    mocker.patch.object(diffweave.ai.LLM, "query_model", new=fake_query)
    llm = diffweave.ai.LLM()
    result = llm.generate_commit_message(
        "status",
        context="some context",
        attempts=["feat: vague"],
        feedbacks=["too vague"],
    )
    assert result == "feat: refined message"
    joined = "\n".join(captured["prompt"])
    assert "some context" in joined
    assert "too vague" in joined
    assert "feat: vague" in joined


def test_load_databricks_token_success(mocker):
    mocker.patch(
        "subprocess.run",
        return_value=mocker.Mock(
            returncode=0,
            stdout=json.dumps({"access_token": "secret-token", "token_type": "Bearer"}),
        ),
    )
    assert diffweave.ai.load_databricks_token("my-account") == "secret-token"


def test_load_databricks_token_cli_failure(mocker):
    mocker.patch("subprocess.run", return_value=mocker.Mock(returncode=1, stdout=""))
    assert diffweave.ai.load_databricks_token("my-account") is None


def test_load_databricks_token_malformed_output(mocker):
    mocker.patch("subprocess.run", return_value=mocker.Mock(returncode=0, stdout="not json"))
    assert diffweave.ai.load_databricks_token("my-account") is None
