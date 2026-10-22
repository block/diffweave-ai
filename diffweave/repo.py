import sys  # noqa
import pathlib
import re
import subprocess

import git
import rich
import rich.console
import rich.padding
import rich.text
import rich.syntax
from rich.console import RenderableType

from . import utils
from . import tui

#: Maximum number of characters rendered in a single preview pane.
MAX_PREVIEW_SIZE = 40_000


# roughly 4 chars per token
# each entry should be no more than 10k tokens
# this means that we'll need to set this to ~20k per "item"
# where item means here both file_contents and the diff result which are checked separately
MAX_DIFF_ITEM_SIZE = 40_000
GITHUB_REMOTE_PATTERN = re.compile(
    r"^(?:\w+://)?(?:[\w\d-]+@)?([\w\.]+)(:\d*)?(.+?)(?:\.git)?/?$",
    flags=re.IGNORECASE,
)


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


def get_repo_url(repo: git.Repo) -> str | None:
    """
    Get the current git repository URL. Note, this assumes github is used!
    """

    remote = repo.remotes[0]
    match = GITHUB_REMOTE_PATTERN.match(remote.url)
    if match:
        host = match.group(1)
        path = match.group(3)
        return f"https://{host}/{path}"
    else:
        return None


def generate_diffs_with_context(current_repo: git.Repo) -> str:
    project_root = pathlib.Path(current_repo.working_dir)

    diffs: git.diff.DiffIndex[git.diff.Diff]
    try:
        diffs = current_repo.head.commit.diff(git.IndexFile.Index, create_patch=True)
        diff_overview = generate_diffs_with_valid_prior_commit(project_root, diffs)
    except ValueError:
        diff_overview = generate_diffs_with_fresh_repo(project_root)

    return diff_overview


def generate_diffs_with_valid_prior_commit(project_root: pathlib.Path, diffs: git.DiffIndex[git.diff.Diff]) -> str:
    console = rich.console.Console()

    diff_items = []
    for diff_item in diffs:
        file_was_removed = False
        try:
            diff_file = project_root / diff_item.b_path.strip()
        except AttributeError:
            # then the file doesn't exist, and we need to look at the one from the a_path
            file_was_removed = True
            diff_file = project_root / diff_item.a_path.strip()

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


def generate_diffs_with_fresh_repo(project_root: pathlib.Path) -> str:
    stdout, stderr = utils.run_cmd("git diff --name-only --cached", show_output=False, silent=True)
    diff_items = []
    for staged_file_raw in stdout.splitlines():
        staged_file = project_root / staged_file_raw
        staged_file_contents = staged_file.read_text()
        diff_items.append(
            "============\n"
            f"Newly added File: ./{staged_file.relative_to(project_root)}\n"
            "----- Contents -----\n"
            f"{staged_file_contents}\n\n"
            "============\n"
        )

    diff_overview = "\n".join(diff_items)
    return diff_overview


def generate_diffs_for_pull_request(current_repo: git.Repo, branch: str) -> tuple[str, str]:
    latest_commit = current_repo.head.commit.tree

    commit_summary, _ = utils.run_cmd(
        f"git log --right-only --cherry-pick --format='raw' {branch}...HEAD",
        show_output=False,
        silent=True,
    )

    other_branch = current_repo.commit(branch)

    diff_index = other_branch.diff(latest_commit, create_patch=True)

    project_root = pathlib.Path(current_repo.working_dir)

    diff_overview = generate_diffs_with_valid_prior_commit(project_root, diff_index)

    return commit_summary, diff_overview


def get_untracked_and_modified_files(current_repo: git.Repo) -> list[pathlib.Path]:
    git_repo_root = pathlib.Path(current_repo.working_dir)
    untracked_files = [git_repo_root / f for f in current_repo.untracked_files]
    modified_files = [git_repo_root / f.a_path for f in current_repo.index.diff(None)]
    all_files = sorted(untracked_files + modified_files, key=lambda f: [*list(f.parents), f.name])

    return all_files


def build_preview_provider(current_repo: git.Repo) -> tui.PreviewProvider:
    """
    Build a callable that renders a staging preview for a changed file.

    New (untracked) files render their syntax-highlighted contents; modified
    and deleted files render their unstaged diff against the working tree.

    Args:
        current_repo: The git repository whose changes are being previewed

    Returns:
        A callable mapping an absolute file path to a rich renderable
    """
    git_repo_root = pathlib.Path(current_repo.working_dir)
    untracked = {git_repo_root / f for f in current_repo.untracked_files}

    def provide(path: pathlib.Path) -> RenderableType:
        relative = path.relative_to(git_repo_root)
        if path in untracked:
            try:
                contents = path.read_text()
            except (OSError, UnicodeDecodeError):
                return rich.text.Text("<unable to read file contents>", style="dim")
            if len(contents) >= MAX_PREVIEW_SIZE:
                return rich.text.Text("<file too large to preview>", style="dim")
            lexer = rich.syntax.Syntax.guess_lexer(str(path), contents)
            return rich.syntax.Syntax(contents, lexer, line_numbers=True, word_wrap=False)

        result = subprocess.run(
            ["git", "-C", str(git_repo_root), "diff", "--", str(relative)],
            capture_output=True,
            text=True,
        )
        diff_text = result.stdout.strip() or "<no unstaged diff for this file>"
        if len(diff_text) >= MAX_PREVIEW_SIZE:
            return rich.text.Text("<diff too large to preview>", style="dim")
        return rich.syntax.Syntax(diff_text, "diff", word_wrap=False)

    return provide


def add_files(current_repo: git.Repo, interactive: bool = True):
    """
    Interactive interface for adding unstaged files to git.

    This function collects every unstaged (untracked or modified) file in the
    current git repository and, when interactive, opens a Textual checkbox tree
    so the user can stage individual files or whole folders, previewing each
    file's diff or contents alongside the tree. Non-interactive callers stage
    all unstaged files.

    Args:
        current_repo: The git repository to stage files in
        interactive: Whether to open the interactive picker (vs. stage all)

    Raises:
        SystemExit: If the user cancels the interactive picker
    """
    console = rich.console.Console()
    git_repo_root = pathlib.Path(current_repo.working_dir)
    try:
        num_staged_files = len(current_repo.index.diff("HEAD"))
    except git.exc.BadName:
        # if there hasn't been a commit yet
        num_staged_files = 0

    unstaged_files = get_untracked_and_modified_files(current_repo)
    if not unstaged_files:
        return

    console.print(f"Adding unstaged files to the commit... ({num_staged_files:,} already staged)")

    if interactive:
        selected = tui.select_paths(
            git_repo_root,
            unstaged_files,
            preview_provider=build_preview_provider(current_repo),
        )
        if selected is None:
            console.print(rich.text.Text("Cancelled...", style="bold red"))
            raise SystemExit
    else:
        selected = set(unstaged_files)

    if files_to_add := [path for path in selected if path.exists()]:
        current_repo.index.add([str(path) for path in files_to_add])

    if files_to_remove := [path for path in selected if not path.exists()]:
        current_repo.index.remove([str(path) for path in files_to_remove])
