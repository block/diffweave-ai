from pathlib import Path

import git
import yaml
import pytest

from diffweave import app


def test_initial_install(capsys, config_file: Path, monkeypatch):
    monkeypatch.setattr("diffweave.ai.CONFIG_FILE", config_file)

    with pytest.raises(SystemExit):
        app([], result_action="return_value")
    stdout = capsys.readouterr().out
    assert "set-token-model" in stdout

    with pytest.raises(SystemExit):
        app(["pr"], result_action="return_value")
    stdout = capsys.readouterr().out
    assert "set-token-model" in stdout


def test_setting_custom_model(capsys, config_file: Path, monkeypatch):
    monkeypatch.setattr("diffweave.ai.CONFIG_FILE", config_file)

    with pytest.raises(SystemExit):
        app(["set-token-model"])

    arguments = "set-token-model gpt-5.1 -t 0xdeadbeef -e https://api.example.com"
    app(tokens=arguments, result_action="return_value")
    assert "configured" in capsys.readouterr().out

    assert config_file.exists()
    file_contents = config_file.read_text()
    assert "gpt-5.1" in file_contents
    assert "api.example.com" in file_contents
    assert "deadbeef" in file_contents
    data = yaml.safe_load(file_contents)
    assert data["type"] == "token"
    assert data["model_name"] == "gpt-5.1"


def test_commit(capsys, new_repo: git.Repo, valid_config: Path):
    with pytest.raises(SystemExit):
        app("--dry-run", result_action="return_value")

    new_repo.index.add(["README.md", "main.py", "test/__init__.py"])
    app("--dry-run", result_action="return_value")
    assert "Generated commit message" in capsys.readouterr().out
