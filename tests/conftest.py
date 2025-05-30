import os
import pathlib
import random
import string
import shutil
import uuid

import pytest
import git


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
    file_path.unlink()
