from pathlib import Path

import git
import yaml
import pytest

from diffweave import app


def test_initial_install():
    app("-c non-existent-config.yaml")


def test_setting_custom_model(capsys, config_file: Path):
    with pytest.raises(SystemExit):
        app("add-model")

    arguments = (
        "add-model "
        "--model 'gpt-5.1' "
        "--endpoint 'https://api.example.com' "
        "--token '0xdeadbeef' "
        f"--config {config_file.absolute()}"
    )
    app(tokens=arguments, result_action="return_value")
    assert "successfully added!" in capsys.readouterr().out

    assert config_file.exists()
    file_contents = config_file.read_text()
    assert "gpt-5.1" in file_contents
    assert "api.example.com" in file_contents
    assert "deadbeef" in file_contents
    data = yaml.safe_load(file_contents)
    assert "<<DEFAULT>>" in data
    assert "gpt-5.1" in data


def test_setting_default_model(populated_config: Path):
    with pytest.raises(SystemExit):
        app("set-model")

    data = yaml.safe_load(populated_config.read_text())
    assert data["<<DEFAULT>>"] == "gpt-5.1"

    app(f"set-model gpt-4o --config {populated_config.absolute()}", result_action="return_value")

    data = yaml.safe_load(populated_config.read_text())
    assert data["<<DEFAULT>>"] == "gpt-4o"


def test_commit(monkeypatch, capsys, new_repo: git.Repo, populated_config: Path):
    with pytest.raises(SystemExit):
        app(f"--dry-run --config {populated_config.absolute()}", result_action="return_value")

    new_repo.index.add(["README.md", "main.py", "test/__init__.py"])
    app(f"--dry-run --config {populated_config.absolute()}", result_action="return_value")
    assert "Generated commit message" in capsys.readouterr().out
