"""Fake-data gallery for visually iterating on the TUI screens.

Builds each Textual screen populated with example fixtures and no real git or
LLM access, so the layouts can be launched live (via ``diffweave-ai preview``)
or rendered deterministically by snapshot tests. Nothing here touches the
filesystem, git, or a model endpoint.
"""

from __future__ import annotations

import pathlib
from typing import List

from rich.syntax import Syntax
from rich.text import Text

from . import tui

#: Root used for the example staging tree (never touched on disk).
EXAMPLE_ROOT = pathlib.Path("/example/diffweave-ai")

#: Example changed files spanning nested folders.
EXAMPLE_FILES = [
    EXAMPLE_ROOT / "README.md",
    EXAMPLE_ROOT / "diffweave" / "cli.py",
    EXAMPLE_ROOT / "diffweave" / "tui.py",
    EXAMPLE_ROOT / "diffweave" / "prompts" / "simple.md",
    EXAMPLE_ROOT / "tests" / "test_tui.py",
]

#: Example diff shown in the preview pane for modified files.
EXAMPLE_DIFF = """diff --git a/diffweave/cli.py b/diffweave/cli.py
@@ -1,6 +1,7 @@
-from . import run_cmd, repo, ai
+from . import run_cmd, repo, ai, tui
+import git

 app = cyclopts.App()
"""

#: Example file contents shown in the preview pane for new files.
EXAMPLE_CONTENTS = """# diffweave-ai

LLM-powered git commit messages with a Textual TUI.
"""

#: Canned commit messages returned by the fake generator, in iteration order.
EXAMPLE_MESSAGES = [
    (
        "feat: add responsive Textual staging TUI\n\n"
        "- Replace the beaupy picker with a checkbox tree\n"
        "- Add a live diff/contents preview pane\n"
        "- Inherit the terminal colorscheme via the ANSI theme"
    ),
    (
        "feat: add Textual TUI for staging and commit review\n\n"
        "Introduce an interactive checkbox tree with a live preview pane, plus\n"
        "a commit-review screen with editable messages and in-place commit/push."
    ),
]


def _example_preview(path: pathlib.Path):
    """Return a fake preview renderable for an example file.

    Parameters
    ----------
    path
        The example file path whose preview is requested.

    Returns
    -------
    rich.console.RenderableType
        Syntax-highlighted contents for the README, otherwise a fake diff.
    """
    if path.name == "README.md":
        return Syntax(EXAMPLE_CONTENTS, "markdown", line_numbers=True)
    return Syntax(EXAMPLE_DIFF, "diff")


def _example_generate(attempts: List[str], feedbacks: List[str]) -> str:
    """Return the next canned commit message for the iteration count.

    Parameters
    ----------
    attempts
        Previously rejected messages (its length selects the next message).
    feedbacks
        Feedback aligned with ``attempts`` (unused by the fake generator).

    Returns
    -------
    str
        A canned commit message.
    """
    return EXAMPLE_MESSAGES[min(len(attempts), len(EXAMPLE_MESSAGES) - 1)]


def _noop_commit(message: str) -> None:
    """Pretend to commit (does nothing) for the gallery.

    Parameters
    ----------
    message
        The message that would be committed.
    """


def _noop_push() -> None:
    """Pretend to push (does nothing) for the gallery."""


def build_tree_app() -> tui.StagePickerApp:
    """Build the staging-tree screen populated with example fixtures.

    Returns
    -------
    diffweave.tui.StagePickerApp
        A ready-to-run staging picker with fake files and preview.
    """
    return tui.StagePickerApp(
        EXAMPLE_ROOT,
        EXAMPLE_FILES,
        preselect=True,
        preview_provider=_example_preview,
    )


def build_review_app() -> tui.CommitReviewApp:
    """Build the commit-review screen wired to fake generation/git callables.

    Returns
    -------
    diffweave.tui.CommitReviewApp
        A ready-to-run review screen that generates canned messages and
        performs no real git actions.
    """
    return tui.CommitReviewApp(_example_generate, _noop_commit, _noop_push)


#: Mapping of screen name to its example-app builder.
SCREENS = {
    "tree": build_tree_app,
    "review": build_review_app,
}


def launch(screen: str) -> None:
    """Launch an example screen live in the terminal.

    Parameters
    ----------
    screen
        Which screen to launch (``"tree"`` or ``"review"``).

    Raises
    ------
    SystemExit
        If ``screen`` is not a known screen name.
    """
    builder = SCREENS.get(screen)
    if builder is None:
        known = ", ".join(sorted(SCREENS))
        raise SystemExit(f"Unknown preview screen {screen!r}. Choose one of: {known}.")
    result = builder().run()
    print(Text(f"Preview exited with: {result!r}"))
