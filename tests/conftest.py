import datetime
import os
import pathlib
import random
import string
import shutil
import uuid

import yaml
import pytest
import git


@pytest.fixture(autouse=True)
def patch_openai(monkeypatch, mocker):
    mock_openai = mocker.MagicMock()
    monkeypatch.setattr("openai.OpenAI", mock_openai)
    yield


@pytest.fixture(scope="function")
def new_repo():
    dirname = uuid.uuid4().hex
    dir = pathlib.Path(dirname)
    # if this already exists, something went HORRIBLY wrong
    dir.mkdir(exist_ok=False, parents=True)
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(dir)
        pathlib.Path("README.md").write_text("lorem ipsum")
        pathlib.Path("main.py").write_text('print("hello world")')
        pathlib.Path("test").mkdir(exist_ok=True, parents=True)
        pathlib.Path("test/__init__.py").touch()
        pathlib.Path("test/submodule1").mkdir(exist_ok=True, parents=True)
        pathlib.Path("test/submodule1/__init__.py").touch()
        pathlib.Path("test/submodule2").mkdir(exist_ok=True, parents=True)
        pathlib.Path("test/submodule2/__init__.py").touch()
        repo = git.Repo.init()
        yield repo
    shutil.rmtree(dir)


@pytest.fixture(scope="function")
def config_file():
    filename = uuid.uuid4().hex
    file_path = pathlib.Path(f"config_{filename}.yaml")
    yield file_path
    if file_path.exists():
        file_path.unlink()


@pytest.fixture(scope="function")
def populated_config():
    filename = uuid.uuid4().hex
    file_path = pathlib.Path(f"config_{filename}.yaml")
    config_contents = yaml.safe_dump(
        {
            "<<DEFAULT>>": "gpt-5.1",
            "gpt-5.1": {
                "endpoint": "https://api.example.com",
                "token": "0xdeadbeef",
            },
            "gpt-4o": {
                "endpoint": "https://api.example.com",
                "token": "0xdeadbeef",
            },
        }
    )
    file_path.write_text(config_contents)
    yield file_path
    file_path.unlink()
