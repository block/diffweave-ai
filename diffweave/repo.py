import sys  # noqa
import pathlib

import git
import rich
import rich.console
import rich.padding
import rich.text
import beaupy

from . import utils


# roughly 4 chars per token
# each entry should be no more than 10k tokens
# this means that we'll need to set this to ~20k per "item"
# where item means here both file_contents and the diff result which are checked separately
MAX_DIFF_ITEM_SIZE = 40_000


def get_repo() -> git.Repo:
    """
    Get the current git repository.

    This function attempts to retrieve the current git repository using
    the GitPython library. If no repository is found, it raises a SystemExit
    exception with an error message.

    Returns:
        git.Repo: The current git repository object

    Raises:
        SystemExit: If no git repository is found
    """
    try:
        repo = git.Repo(search_parent_directories=True)
        return repo
    except git.exc.InvalidGitRepositoryError:
        raise SystemExit("No git repository found.")


def generate_diffs_with_context(current_repo: git.Repo):
    console = rich.console.Console()

    console.print("Generating diffs for staged files...", style="bold")

    project_root = pathlib.Path(current_repo.working_dir)

    diffs: git.diff.DiffIndex[git.diff.Diff]
    try:
        diffs = current_repo.head.commit.diff(git.IndexFile.Index, create_patch=True)
    except ValueError:
        # if there aren't any commits yet we need to handle this differently
        # fixme
        raise NotImplementedError

    diff_items = []
    for diff_item in diffs:
        file_was_removed = False
        try:
            diff_file = project_root / diff_item.b_path.strip()
        except AttributeError:
            # then the file doesn't exist, and we need to look at the one from the a_path
            file_was_removed = True
            diff_file = project_root / diff_item.a_path.strip()

        skip_file = False

        if skip_file:
            continue

        console.print(rich.padding.Padding(rich.text.Text(f"Staged file: {diff_file}", style="dim"), (0, 0, 0, 2)))
        try:
            if file_was_removed:
                file_contents = "<FILE REMOVED>"
            else:
                file_contents = diff_file.read_text()

            if len(file_contents) >= MAX_DIFF_ITEM_SIZE:
                file_contents = "<FILE TOO LARGE TO SHOW>"

            # decode and strip out line counts
            file_diff_text = diff_item.diff.decode("utf-8")
            if len(file_diff_text) >= MAX_DIFF_ITEM_SIZE:
                file_diff_text = "<DIFF TOO LARGE TO SHOW>"

            diff_items.append(
                "============\n"
                f"Modified File: ./{diff_file.relative_to(project_root)}\n"
                "----- Contents -----\n"
                f"{file_contents}\n\n"
                "----- Diff from HEAD -----\n"
                f"{file_diff_text}"
                "============\n"
            )
        except Exception as e:
            console.print(rich.text.Text(f"Error reading {diff_file}: {e}", style="bold red"))
            continue

    diff_overview = "\n".join(diff_items)

    return diff_overview


def get_untracked_and_modified_files(current_repo: git.Repo) -> list[pathlib.Path]:
    git_repo_root = pathlib.Path(current_repo.working_dir)
    untracked_files = [git_repo_root / f for f in current_repo.untracked_files]
    modified_files = [git_repo_root / f.a_path for f in current_repo.index.diff(None)]
    all_files = sorted(untracked_files + modified_files, key=lambda f: [*list(f.parents), f.name])

    return all_files


def add_files(current_repo: git.Repo, interactive: bool = True):
    """
    Interactive interface for adding unstaged files to git.

    This function displays all unstaged files in the current git repository
    and allows the user to select which ones to stage for commit. It uses
    a tree view to display the files and provides a multi-select interface
    for choosing files.

    Raises:
        SystemExit: If no files are selected
    """
    console = rich.console.Console()
    git_repo_root = pathlib.Path(current_repo.working_dir)
    try:
        num_staged_files = len(current_repo.index.diff("HEAD"))
    except git.exc.BadName:
        # if there hasn't been a commit yet
        num_staged_files = 0

    unstaged_files = get_untracked_and_modified_files(current_repo)
    formatted_paths = "\n".join(str(p.relative_to(git_repo_root)) for p in unstaged_files)

    try:
        utils.run_cmd("tree --fromfile", input=formatted_paths)
    except SystemError:
        pass

    if unstaged_files:
        console.print(f"Adding unstaged files to the commit... ({num_staged_files:,} already staged)")
        if interactive:
            beaupy.Config.raise_on_interrupt = True
            selections = beaupy.select_multiple(
                [str(f.relative_to(git_repo_root)) for f in unstaged_files],
                pagination=True,
                page_size=5,
            )
        else:
            selections = [str(f.relative_to(git_repo_root)) for f in unstaged_files]

        if files_to_add := [fpath for f in selections if (fpath := git_repo_root / f).exists()]:
            current_repo.index.add(files_to_add)

        if files_to_remove := [fpath for f in selections if not (fpath := git_repo_root / f).exists()]:
            current_repo.index.remove(files_to_remove)
