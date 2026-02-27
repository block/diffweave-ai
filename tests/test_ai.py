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
    mocker.patch("diffweave.ai.load_databricks_token_from_cache", return_value="cached-token")
    llm = diffweave.ai.LLM()
    assert llm.model_name == "databricks-llama"


def test_llm_init_databricks_triggers_login(databricks_config, mocker):
    mocker.patch(
        "diffweave.ai.load_databricks_token_from_cache",
        side_effect=[None, "new-token"],
    )
    mock_subprocess = mocker.patch("subprocess.run")
    llm = diffweave.ai.LLM()
    mock_subprocess.assert_called_once()
    assert llm.model_name == "databricks-llama"


def test_iterate_with_feedback(fake_config, mocker):
    mocker.patch.object(
        diffweave.ai.LLM,
        "query_model",
        new=AsyncMock(return_value="feat: add feature"),
    )
    mocker.patch("rich.console.Console.input", side_effect=["too vague", ""])
    llm = diffweave.ai.LLM()
    result = llm.iterate_on_commit_message("status", "context", return_first=False)
    assert result == "feat: add feature"


def test_iterate_verbose_prints_prompt(fake_config, mocker, capsys):
    mocker.patch.object(
        diffweave.ai.LLM,
        "query_model",
        new=AsyncMock(return_value="feat: add feature"),
    )
    mocker.patch("rich.console.Console.input", return_value="")
    llm = diffweave.ai.LLM(verbose=True)
    llm.iterate_on_commit_message("status", "context", return_first=True)
    assert "Prompt" in capsys.readouterr().out


def test_iterate_no_panel(fake_config, mocker, capsys):
    mocker.patch.object(
        diffweave.ai.LLM,
        "query_model",
        new=AsyncMock(return_value="PR title\n\nPR body"),
    )
    llm = diffweave.ai.LLM()
    result = llm.iterate_on_commit_message("status", "context", return_first=True, no_panel=True)
    assert result == "PR title\n\nPR body"
    assert "Generated PR description" in capsys.readouterr().out


def test_load_databricks_token_valid(monkeypatch, tmp_path):
    cache_dir = tmp_path / ".databricks"
    cache_dir.mkdir()
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    token_data = {
        "tokens": {
            "my-account": {
                "access_token": "secret-token",
                "expiry": future.isoformat(),
            }
        }
    }
    (cache_dir / "token-cache.json").write_text(json.dumps(token_data))
    monkeypatch.setattr("pathlib.Path.home", staticmethod(lambda: tmp_path))
    result = diffweave.ai.load_databricks_token_from_cache("my-account")
    assert result == "secret-token"


def test_load_databricks_token_expired(monkeypatch, tmp_path):
    cache_dir = tmp_path / ".databricks"
    cache_dir.mkdir()
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    token_data = {
        "tokens": {
            "my-account": {
                "access_token": "secret-token",
                "expiry": past.isoformat(),
            }
        }
    }
    (cache_dir / "token-cache.json").write_text(json.dumps(token_data))
    monkeypatch.setattr("pathlib.Path.home", staticmethod(lambda: tmp_path))
    result = diffweave.ai.load_databricks_token_from_cache("my-account")
    assert result is None


def test_load_databricks_token_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", staticmethod(lambda: tmp_path))
    result = diffweave.ai.load_databricks_token_from_cache("my-account")
    assert result is None
