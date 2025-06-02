from pathlib import Path

import pytest

import diffweave


def test_configuring_new_model(config_file: Path):
    assert not config_file.exists()
    diffweave.ai.configure_custom_model(
        "some_model",
        "https://api.example.com",
        "my_token",
        config_file=config_file,
    )
    assert config_file.exists()


def test_setting_default_model(config_file):
    with pytest.raises(ValueError):
        diffweave.ai.set_default_model("some_model", config_file=config_file)

    diffweave.ai.configure_custom_model(
        "some_model",
        "https://api.example.com",
        "my_token",
        config_file=config_file,
    )
    diffweave.ai.set_default_model("some_model", config_file=config_file)
