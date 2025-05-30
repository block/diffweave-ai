from pathlib import Path

import pytest

import llmit


def test_configuring_new_model(config_file: Path):
    assert not config_file.exists()
    llmit.ai.configure_custom_model(
        "some_model",
        "https://api.example.com",
        "my_token",
        config_file=config_file,
    )
    assert config_file.exists()


def test_setting_default_model(config_file):
    with pytest.raises(ValueError):
        llmit.ai.set_default_model("some_model", config_file=config_file)

    llmit.ai.configure_custom_model(
        "some_model",
        "https://api.example.com",
        "my_token",
        config_file=config_file,
    )
    llmit.ai.set_default_model("some_model", config_file=config_file)
