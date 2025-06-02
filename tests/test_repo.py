import os
import pathlib
import shutil
import string

import git
import pytest

import diffweave


def test_adding_files(new_repo: git.Repo):
    initially_unstaged_files = diffweave.repo.get_untracked_and_modified_files(new_repo)

    assert len(initially_unstaged_files) > 0

    diffweave.repo.add_files(new_repo, interactive=False)

    now_unstaged_files = diffweave.repo.get_untracked_and_modified_files(new_repo)

    assert len(now_unstaged_files) == 0

    assert len(initially_unstaged_files) != len(now_unstaged_files)

    diffweave.repo.add_files(new_repo, interactive=False)

    assert len(diffweave.repo.get_untracked_and_modified_files(new_repo)) == 0


def test_adding_files_with_one_removed(new_repo: git.Repo):
    root_dir = pathlib.Path(new_repo.working_dir)
    all_files = diffweave.repo.get_untracked_and_modified_files(new_repo)
    new_repo.index.add([str(f.relative_to(root_dir)) for f in all_files])
    new_repo.index.commit("Initial commit")

    os.remove("README.md")

    diffweave.repo.add_files(new_repo, interactive=False)


def test_finding_repo_root(new_repo: git.Repo, monkeypatch):
    root_dir = pathlib.Path(new_repo.working_dir)
    assert pathlib.Path(diffweave.repo.get_repo().working_dir) == root_dir

    monkeypatch.chdir(root_dir / "test")
    assert pathlib.Path(diffweave.repo.get_repo().working_dir) == root_dir

    monkeypatch.chdir(root_dir / "test" / "submodule1")
    assert pathlib.Path(diffweave.repo.get_repo().working_dir) == root_dir


def test_getting_all_files(new_repo: git.Repo):
    assert len(diffweave.repo.get_untracked_and_modified_files(new_repo)) == 5
    new_repo.index.add(["README.md"])
    assert len(diffweave.repo.get_untracked_and_modified_files(new_repo)) == 4
    pathlib.Path("README.md").write_text("AKJHSDGFKJHSDFLKJHSDFLKJH")
    assert len(diffweave.repo.get_untracked_and_modified_files(new_repo)) == 5


def test_generating_diffs(new_repo: git.Repo):
    root_dir = pathlib.Path(new_repo.working_dir)
    new_repo.index.add(["README.md"])

    # fixme
    with pytest.raises(NotImplementedError):
        diff_summary = diffweave.repo.generate_diffs_with_context(new_repo)

    new_repo.index.commit("Initial commit")

    all_files = diffweave.repo.get_untracked_and_modified_files(new_repo)
    new_repo.index.add(all_files)

    diff_summary = diffweave.repo.generate_diffs_with_context(new_repo)

    for file in all_files:
        assert str(file.relative_to(root_dir)) in diff_summary


def test_diffs_with_deleted_file(new_repo: git.Repo):
    root_dir = pathlib.Path(new_repo.working_dir)
    all_files = diffweave.repo.get_untracked_and_modified_files(new_repo)
    new_repo.index.add([str(f.relative_to(root_dir)) for f in all_files])
    new_repo.index.commit("Initial commit")

    # now we can delete
    os.remove("README.md")
    diffweave.run_cmd("git add -A")
    diffweave.repo.generate_diffs_with_context(new_repo)

    shutil.rmtree("test/submodule1")
    diffweave.run_cmd("git add -A")
    diffweave.repo.generate_diffs_with_context(new_repo)


def test_deleted_files(new_repo: git.Repo):
    diffweave.repo.add_files(new_repo, interactive=False)
    new_repo.index.commit("Initial commit")
    os.remove("README.md")
    diffweave.repo.add_files(new_repo, interactive=False)
    diffs = diffweave.repo.generate_diffs_with_context(new_repo)
    assert diffs != ""


def test_large_diffs(new_repo: git.Repo):
    root_dir = pathlib.Path(new_repo.working_dir)
    new_repo.index.add(["README.md"])
    new_repo.index.commit("Initial commit")
    all_files = diffweave.repo.get_untracked_and_modified_files(new_repo)
    new_repo.index.add([str(f.relative_to(root_dir)) for f in all_files])
    diffs = diffweave.repo.generate_diffs_with_context(new_repo)
    assert "TOO LARGE TO SHOW" not in diffs

    (root_dir / "large_file.txt").write_text(string.ascii_lowercase * 20_000)
    new_repo.index.add(["large_file.txt"])
    diffs = diffweave.repo.generate_diffs_with_context(new_repo)
    assert "TOO LARGE TO SHOW" in diffs
