import os
from pathlib import Path
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
    root_dir = Path(new_repo.working_dir)
    all_files = diffweave.repo.get_untracked_and_modified_files(new_repo)
    new_repo.index.add([str(f.relative_to(root_dir)) for f in all_files])
    new_repo.index.commit("Initial commit")

    os.remove("README.md")

    diffweave.repo.add_files(new_repo, interactive=False)


def test_finding_repo_root(new_repo: git.Repo, monkeypatch):
    root_dir = Path(new_repo.working_dir)
    assert root_dir.exists()

    assert Path(diffweave.repo.get_repo().working_dir) == root_dir

    monkeypatch.chdir(root_dir / "test")
    assert Path(os.getcwd()) == (root_dir / "test")
    assert Path(diffweave.repo.get_repo().working_dir) == root_dir

    monkeypatch.chdir(root_dir / "test" / "submodule1")
    assert Path(diffweave.repo.get_repo().working_dir) == root_dir

    monkeypatch.undo()


def test_getting_all_files(new_repo: git.Repo):
    assert len(diffweave.repo.get_untracked_and_modified_files(new_repo)) == 5
    new_repo.index.add(["README.md"])
    assert len(diffweave.repo.get_untracked_and_modified_files(new_repo)) == 4
    Path("README.md").write_text("AKJHSDGFKJHSDFLKJHSDFLKJH")
    assert len(diffweave.repo.get_untracked_and_modified_files(new_repo)) == 5


def test_generating_diffs_with_no_commits(new_repo: git.Repo):
    new_repo.index.add(["README.md", "main.py", "test/__init__.py"])
    assert diffweave.repo.generate_diffs_with_context(new_repo)


def test_generating_diffs(new_repo: git.Repo):
    root_dir = Path(new_repo.working_dir)
    new_repo.index.add(["README.md"])

    diff_summary = diffweave.repo.generate_diffs_with_context(new_repo)

    new_repo.index.commit("Initial commit")

    all_files = diffweave.repo.get_untracked_and_modified_files(new_repo)
    new_repo.index.add(all_files)

    diff_summary = diffweave.repo.generate_diffs_with_context(new_repo)

    for file in all_files:
        assert str(file.relative_to(root_dir)) in diff_summary


def test_diffs_with_deleted_file(new_repo: git.Repo):
    root_dir = Path(new_repo.working_dir)
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
    root_dir = Path(new_repo.working_dir)
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


def test_get_repo_url(new_repo: git.Repo):
    url = diffweave.repo.get_repo_url(new_repo)
    assert url is not None


def test_get_repo_not_in_git_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        diffweave.repo.get_repo()


def test_get_repo_url_no_match(mocker):
    mock_repo = mocker.Mock()
    mock_remote = mocker.Mock()
    mock_remote.url = ":::not-parseable"
    mock_repo.remotes = [mock_remote]
    result = diffweave.repo.get_repo_url(mock_repo)
    assert result is None


def test_generate_diffs_for_pull_request(new_repo: git.Repo):
    new_repo.index.add(["README.md"])
    new_repo.index.commit("Initial commit")
    new_repo.index.add(["main.py"])
    new_repo.index.commit("Second commit")
    commit_summary, diffs = diffweave.repo.generate_diffs_for_pull_request(new_repo, "HEAD~1")
    assert "main.py" in diffs


def test_add_files_tree_not_available(new_repo: git.Repo, mocker):
    mocker.patch("diffweave.utils.run_cmd", side_effect=SystemError)
    diffweave.repo.add_files(new_repo, interactive=False)
    assert len(diffweave.repo.get_untracked_and_modified_files(new_repo)) == 0


def test_add_files_interactive(new_repo: git.Repo, mocker):
    all_files = diffweave.repo.get_untracked_and_modified_files(new_repo)
    root_dir = Path(new_repo.working_dir)
    rel_files = [str(f.relative_to(root_dir)) for f in all_files]
    mocker.patch("beaupy.select_multiple", return_value=[rel_files[0]])
    diffweave.repo.add_files(new_repo, interactive=True)
    remaining = diffweave.repo.get_untracked_and_modified_files(new_repo)
    assert len(remaining) == len(all_files) - 1


def test_github_remote_url_regex():
    """
    https://stackoverflow.com/questions/31801271/what-are-the-supported-git-url-formats
    """
    for case in """
    ssh://user@host.xz:port/path/to/repo.git/
    ssh://user@host.xz/path/to/repo.git/
    ssh://host.xz:port/path/to/repo.git/
    ssh://host.xz/path/to/repo.git/
    ssh://user@host.xz/path/to/repo.git/
    ssh://host.xz/path/to/repo.git/
    ssh://user@host.xz/~user/path/to/repo.git/
    ssh://host.xz/~user/path/to/repo.git/
    ssh://user@host.xz/~/path/to/repo.git
    ssh://host.xz/~/path/to/repo.git
    git://host.xz/path/to/repo.git/
    git://host.xz/~user/path/to/repo.git/
    http://host.xz/path/to/repo.git/
    https://host.xz/path/to/repo.git/
    org-1234456@github.com:some-user/some-repo.git
    """.strip().splitlines():
        case = case.strip()
        match = diffweave.repo.GITHUB_REMOTE_PATTERN.match(case)
        print(case)
        assert match is not None
        print(match)
        host = match.group(1)
        print(host)
        assert len(host.split(".")) == 2
        path = match.group(3)
        print(path)
        print(f"https://{host}/{path}")
