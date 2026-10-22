"""Interactive Textual checkbox tree (with live preview) for staging files.

Renders the repository's changed (untracked or modified) paths as a single
expandable tree with per-node checkboxes, so the user can stage individual
files or whole folders in one pass. This replaces the previous flat
``beaupy`` multi-select picker together with the external ``tree`` binary.

When the terminal is wide enough, the layout splits vertically and a preview
pane shows the diff for modified files (or syntax-highlighted contents for new
files) for whichever node the cursor is on. Narrow terminals fall back to a
tree-only view.

Folders are selectable: toggling a folder cascades to every file beneath it,
and a folder renders as partially-checked when only some of its descendants
are selected. The application returns the flat set of selected *file* paths,
since those are what git ultimately stages.
"""

from __future__ import annotations

import asyncio
import pathlib
from typing import Callable, List, Optional, Set

from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static, TextArea, Tree
from textual.widgets.tree import TreeNode

CHECK_SELECTED = "☑"
CHECK_EMPTY = "☐"
CHECK_PARTIAL = "◪"

#: Minimum terminal width (columns) before the preview pane is shown.
PREVIEW_MIN_WIDTH = 100

#: Textual theme whose palette is drawn from the parent terminal's own ANSI
#: colors (and default background), so the TUI inherits the user's terminal
#: colorscheme instead of imposing fixed hex colors.
TERMINAL_THEME = "ansi-dark"

#: Type of the callable that renders a preview for a given file path.
PreviewProvider = Callable[[pathlib.Path], RenderableType]

#: Generates a commit message from (attempts, feedbacks) iteration history.
GenerateFn = Callable[[List[str], List[str]], str]

#: Performs the git commit for the given message (raises on failure).
CommitFn = Callable[[str], None]

#: Performs the git push (raises on failure).
PushFn = Callable[[], None]


class _CheckboxTree(Tree):
    """A ``Tree`` whose ``space``/``enter`` keys drive selection and confirm.

    The base :class:`~textual.widgets.Tree` binds ``space`` to expand/collapse
    and ``enter`` to node selection. Both are rebound here to the owning
    application's actions so the widget behaves as a checkbox picker rather
    than a plain navigation tree.

    Notes
    -----
    Bindings target the ``app`` namespace (e.g. ``app.toggle``) so the focused
    tree delegates to :class:`StagePickerApp` actions while still handling its
    own cursor navigation.
    """

    BINDINGS = [
        Binding("space", "app.toggle", "Toggle"),
        Binding("enter", "app.confirm", "Confirm"),
    ]


class StagePickerApp(App[Optional[Set[pathlib.Path]]]):
    """Full-screen picker returning the set of files chosen for staging.

    Parameters
    ----------
    root_path
        Repository working-tree root. Node labels are rendered relative to it.
    files
        Absolute paths of the changed files to offer for staging. Intermediate
        folders are derived from these paths; no other filesystem entries are
        shown.
    preselect
        When ``True`` every file starts selected; otherwise nothing is ticked.
    preview_provider
        Optional callable mapping a file path to a rich renderable shown in the
        preview pane. When ``None`` the preview pane is never shown.

    Attributes
    ----------
    CSS
        Stylesheet describing the split body layout.
    BINDINGS
        Application-level key bindings (select all/none, cancel).
    """

    #: Disable Textual's built-in command palette (frees ctrl+p and keeps the
    #: footer focused on this screen's own actions).
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    #body {
        height: 1fr;
    }

    #tree {
        width: 2fr;
        padding: 0 1;
    }

    #preview-pane {
        width: 3fr;
        border-left: solid ansi_bright_black;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("a", "toggle_all", "All / none"),
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        root_path: pathlib.Path,
        files: list[pathlib.Path],
        preselect: bool = False,
        preview_provider: Optional[PreviewProvider] = None,
    ) -> None:
        """Initialise the picker state without building any widgets.

        Parameters
        ----------
        root_path
            Repository working-tree root.
        files
            Absolute paths of the changed files to offer.
        preselect
            Whether every file begins selected.
        preview_provider
            Optional callable rendering a per-file preview.
        """
        super().__init__()
        self._root_path = pathlib.Path(root_path)
        self._files = sorted(
            {pathlib.Path(path) for path in files},
            key=lambda path: path.relative_to(self._root_path).parts,
        )
        self._selected: Set[pathlib.Path] = set(self._files) if preselect else set()
        self._preview_provider = preview_provider
        self._file_nodes: Set[TreeNode] = set()
        self._node_path: dict[TreeNode, pathlib.Path] = {}
        self._tree: _CheckboxTree | None = None

    def compose(self) -> ComposeResult:
        """Yield the header, split body (tree + preview), and footer.

        Yields
        ------
        textual.widget.Widget
            The header, the body container holding the tree and preview pane,
            and the footer.
        """
        yield Header()
        self._tree = _CheckboxTree("", data=self._root_path, id="tree")
        with Horizontal(id="body"):
            yield self._tree
            with VerticalScroll(id="preview-pane"):
                yield Static(id="preview", expand=True)
        yield Footer()

    def on_mount(self) -> None:
        """Build the tree hierarchy, apply layout, and render the first preview.

        Folder nodes are created on demand as each file path is inserted; the
        whole tree is then expanded so the full layout is visible and
        scrollable.
        """
        self.theme = TERMINAL_THEME
        self.title = "diffweave"
        self.sub_title = f"stage files · {len(self._files)} changed"

        tree = self._tree
        folders: dict[pathlib.Path, TreeNode] = {self._root_path: tree.root}
        self._node_path[tree.root] = self._root_path

        for file_path in self._files:
            relative = file_path.relative_to(self._root_path)
            parent = tree.root
            current = self._root_path
            for part in relative.parts[:-1]:
                current = current / part
                if current not in folders:
                    branch = parent.add(part, data=current)
                    folders[current] = branch
                    self._node_path[branch] = current
                parent = folders[current]
            leaf = parent.add_leaf(relative.parts[-1], data=file_path)
            self._file_nodes.add(leaf)
            self._node_path[leaf] = file_path

        tree.root.expand_all()
        self._refresh_labels()
        self._update_layout()
        self._show_preview(tree.cursor_node)
        tree.focus()

    def on_resize(self) -> None:
        """Re-evaluate whether the preview pane fits after a terminal resize."""
        self._update_layout()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Refresh the preview pane when the tree cursor moves.

        Parameters
        ----------
        event
            The highlight event carrying the newly focused node.
        """
        self._show_preview(event.node)

    def _update_layout(self) -> None:
        """Show the preview pane only when a provider exists and there is room."""
        has_room = self.size.width >= PREVIEW_MIN_WIDTH
        show_preview = self._preview_provider is not None and has_room
        try:
            self.query_one("#preview-pane").display = show_preview
        except Exception:
            # Widgets not mounted yet; on_mount will apply the layout.
            pass

    def _show_preview(self, node: Optional[TreeNode]) -> None:
        """Render the preview for ``node`` into the preview pane.

        Parameters
        ----------
        node
            The node under the cursor. Files render their diff/contents;
            folders and the root render a short hint.
        """
        if self._preview_provider is None:
            return
        try:
            widget = self.query_one("#preview", Static)
        except Exception:
            return

        if node is not None and node in self._file_nodes:
            widget.update(self._preview_provider(self._node_path[node]))
            return

        if node is not None and node is not self._tree.root:
            count = len(self._leaves_under(node))
            widget.update(Text(f"Folder — {count} file(s) beneath. Toggle to stage all.", style="dim"))
            return

        widget.update(Text("Select a file to preview its changes.", style="dim"))

    def _leaves_under(self, node: TreeNode) -> list[pathlib.Path]:
        """Collect the file paths of every leaf beneath ``node``.

        Parameters
        ----------
        node
            Tree node to search under (may itself be a file or folder node).

        Returns
        -------
        list of pathlib.Path
            File paths for all descendant leaves, in traversal order.
        """
        leaves: list[pathlib.Path] = []
        for child in node.children:
            if child in self._file_nodes:
                leaves.append(self._node_path[child])
            else:
                leaves.extend(self._leaves_under(child))
        return leaves

    def _checkbox(self, node: TreeNode) -> str:
        """Return the checkbox glyph reflecting ``node``'s selection state.

        Parameters
        ----------
        node
            File or folder node to inspect.

        Returns
        -------
        str
            ``CHECK_SELECTED`` when fully selected, ``CHECK_EMPTY`` when not,
            and ``CHECK_PARTIAL`` when only some descendants are selected.
        """
        if node in self._file_nodes:
            return CHECK_SELECTED if self._node_path[node] in self._selected else CHECK_EMPTY
        leaves = self._leaves_under(node)
        selected = sum(1 for leaf in leaves if leaf in self._selected)
        if selected == 0:
            return CHECK_EMPTY
        if selected == len(leaves):
            return CHECK_SELECTED
        return CHECK_PARTIAL

    def _node_label(self, node: TreeNode) -> Text:
        """Build the rendered label (checkbox plus name) for ``node``.

        Parameters
        ----------
        node
            Node to label.

        Returns
        -------
        rich.text.Text
            The checkbox glyph followed by the file or folder name; folders
            carry a trailing ``/``.
        """
        checkbox = self._checkbox(node)
        if node is self._tree.root:
            name = self._root_path.name or str(self._root_path)
        else:
            path = self._node_path[node]
            name = path.name if node in self._file_nodes else f"{path.name}/"
        return Text(f"{checkbox} {name}")

    def _refresh_labels(self) -> None:
        """Recompute and apply every node label from the selection set."""

        def walk(node: TreeNode) -> None:
            node.set_label(self._node_label(node))
            for child in node.children:
                walk(child)

        walk(self._tree.root)

    def action_toggle(self) -> None:
        """Toggle selection of the node under the cursor.

        Toggling a file flips that file; toggling a folder selects all of its
        descendant files unless they are already all selected, in which case
        it clears them.
        """
        node = self._tree.cursor_node
        if node is None:
            return
        if node in self._file_nodes:
            path = self._node_path[node]
            if path in self._selected:
                self._selected.discard(path)
            else:
                self._selected.add(path)
        else:
            leaves = self._leaves_under(node)
            if leaves and all(leaf in self._selected for leaf in leaves):
                self._selected.difference_update(leaves)
            else:
                self._selected.update(leaves)
        self._refresh_labels()

    def action_toggle_all(self) -> None:
        """Select every file, or clear the selection if all are already set."""
        all_files = set(self._files)
        if all_files and self._selected >= all_files:
            self._selected.clear()
        else:
            self._selected = all_files
        self._refresh_labels()

    def action_confirm(self) -> None:
        """Exit the application, returning the selected file paths."""
        self.exit(set(self._selected))

    def action_cancel(self) -> None:
        """Exit the application, returning ``None`` to signal cancellation."""
        self.exit(None)


def select_paths(
    root_path: pathlib.Path,
    files: list[pathlib.Path],
    preselect: bool = False,
    preview_provider: Optional[PreviewProvider] = None,
) -> Optional[Set[pathlib.Path]]:
    """Run the interactive picker and return the chosen file paths.

    Parameters
    ----------
    root_path
        Repository working-tree root.
    files
        Absolute paths of the changed files to offer for staging.
    preselect
        Whether every file begins selected.
    preview_provider
        Optional callable rendering a per-file preview in the side pane.

    Returns
    -------
    set of pathlib.Path or None
        The selected file paths, an empty set when there is nothing to pick,
        or ``None`` if the user cancelled.
    """
    if not files:
        return set()
    return StagePickerApp(
        root_path,
        files,
        preselect=preselect,
        preview_provider=preview_provider,
    ).run()


class ReviewScreen(Screen):
    """Editable review screen: message, iteration history, refine box, buttons.

    The left pane holds the editable commit message; the right pane logs the
    history of rejected attempts and their feedback. The refine box regenerates
    the message (folding optional context into the first iteration), and the
    button row commits or commits-and-pushes. Committing transitions to the
    :class:`ResultScreen`.

    Attributes
    ----------
    BINDINGS
        Keyboard shortcuts mirroring the buttons.
    """

    BINDINGS = [
        Binding("ctrl+r", "regenerate", "Regenerate"),
        Binding("ctrl+s", "commit", "Commit"),
        Binding("ctrl+p", "commit_push", "Commit & push"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self) -> None:
        """Initialise per-screen busy state."""
        super().__init__()
        self._busy = False

    def compose(self) -> ComposeResult:
        """Yield the header, split message/history body, controls, and footer.

        Yields
        ------
        textual.widget.Widget
            The composed review widgets.
        """
        yield Header()
        with Horizontal(id="review-top"):
            with Vertical(id="message-col"):
                yield Label("Commit message (editable)")
                yield TextArea(id="message")
            with Vertical(id="history-col"):
                yield Label("Iterations")
                yield RichLog(id="history", wrap=True, markup=True)
        yield Input(placeholder="Refine and press Enter to regenerate · empty Enter commits", id="refine")
        with Horizontal(id="buttons"):
            yield Button("Regenerate", id="regen")
            yield Button("Commit", id="commit", variant="success")
            yield Button("Commit & Push", id="push", variant="primary")
            yield Button("Cancel", id="cancel", variant="error")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        """Set the subtitle, start generation, and focus the refine box."""
        self.app.sub_title = "review commit message"
        self.run_generate()
        self.query_one("#refine", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch button presses to the matching action.

        Parameters
        ----------
        event
            The button press event.
        """
        actions = {
            "regen": self.action_regenerate,
            "commit": self.action_commit,
            "push": self.action_commit_push,
            "cancel": self.action_cancel,
        }
        action = actions.get(event.button.id)
        if action is not None:
            action()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Commit on an empty refine box, otherwise regenerate with feedback.

        Parameters
        ----------
        event
            The input submission event.
        """
        if self._busy:
            return
        if self.query_one("#refine", Input).value.strip():
            self.action_regenerate()
        else:
            self.action_commit()

    def action_regenerate(self) -> None:
        """Record the current message as rejected, then regenerate."""
        if self._busy:
            return
        refine = self.query_one("#refine", Input).value.strip()
        current = self.query_one("#message", TextArea).text.strip()
        if current:
            self.app.attempts.append(current)
            self.app.feedbacks.append(refine or "(no specific feedback)")
            history = self.query_one("#history", RichLog)
            history.write(f"[bold]Attempt {len(self.app.attempts)} — rejected[/bold]")
            history.write(current)
            if refine:
                history.write(f"[italic]↳ {refine}[/italic]")
            history.write("")
        self.query_one("#refine", Input).value = ""
        self.run_generate()

    def action_commit(self) -> None:
        """Commit the current message without pushing."""
        self._open_result(push=False)

    def action_commit_push(self) -> None:
        """Commit the current message and push."""
        self._open_result(push=True)

    def action_cancel(self) -> None:
        """Exit the app, reporting no commit."""
        self.app.exit(None)

    def _open_result(self, push: bool) -> None:
        """Validate the message and hand off to the result screen.

        Parameters
        ----------
        push
            Whether the result screen should push after committing.
        """
        if self._busy:
            return
        message = self.query_one("#message", TextArea).text.strip()
        if not message:
            self._set_error("Commit message is empty.")
            return
        self.app.push_screen(ResultScreen(message, push))

    @work(exclusive=True)
    async def run_generate(self) -> None:
        """Generate a message off the UI thread and load it into the editor."""
        self._set_busy("Generating message…")
        try:
            message = await asyncio.to_thread(self.app.generate_fn, list(self.app.attempts), list(self.app.feedbacks))
        except Exception as exc:  # noqa: BLE001 - surfaced to the user in the status line
            self._set_error(f"Generation failed: {exc}")
            return
        self.query_one("#message", TextArea).text = message
        self._set_idle("Ready — edit, refine, or commit.")
        self.query_one("#refine", Input).focus()

    def _set_busy(self, text: str) -> None:
        """Mark the screen busy, disable action buttons, and show status.

        Parameters
        ----------
        text
            Status text to display.
        """
        self._busy = True
        self._enable_actions(False)
        self._status(text, "ansi_yellow")

    def _set_idle(self, text: str) -> None:
        """Clear the busy state, re-enable actions, and show status.

        Parameters
        ----------
        text
            Status text to display.
        """
        self._busy = False
        self._enable_actions(True)
        self._status(text, "ansi_green")

    def _set_error(self, text: str) -> None:
        """Clear the busy state, re-enable actions, and show an error line.

        Parameters
        ----------
        text
            Error text to display.
        """
        self._busy = False
        self._enable_actions(True)
        self._status(text, "ansi_red")

    def _status(self, text: str, color: str) -> None:
        """Render ``text`` in the status line with the given ANSI color.

        Parameters
        ----------
        text
            Status text.
        color
            A Textual ANSI color name (e.g. ``ansi_green``).
        """
        self.query_one("#status", Static).update(Text(text, style=color))

    def _enable_actions(self, enabled: bool) -> None:
        """Enable or disable the action buttons (Cancel stays available).

        Parameters
        ----------
        enabled
            Whether to enable the regenerate/commit buttons.
        """
        for button_id in ("regen", "commit", "push"):
            self.query_one(f"#{button_id}", Button).disabled = not enabled


class ResultScreen(Screen):
    """Final screen showing the accepted message and live commit/push updates.

    Parameters
    ----------
    message
        The accepted commit message to display and commit.
    push
        Whether to push after a successful commit.

    Attributes
    ----------
    BINDINGS
        Enter closes once finished; Escape goes back to editing on failure.
    """

    BINDINGS = [
        Binding("enter", "close", "Close"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, message: str, push: bool) -> None:
        """Store the message, push intent, and terminal state.

        Parameters
        ----------
        message
            The accepted commit message.
        push
            Whether to push after committing.
        """
        super().__init__()
        self._message = message
        self._push = push
        self._outcome: Optional[str] = None
        self._finished = False

    def compose(self) -> ComposeResult:
        """Yield the header, message panel, status log, and footer.

        Yields
        ------
        textual.widget.Widget
            The composed result widgets.
        """
        yield Header()
        yield Static(Panel(self._message, title="Commit message"), id="result-message")
        yield RichLog(id="result-log", markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        """Set the subtitle and run the commit/push sequence."""
        self.app.sub_title = "committing"
        self.run_actions()

    @work(exclusive=True)
    async def run_actions(self) -> None:
        """Commit (and optionally push) off the UI thread, logging each step."""
        log = self.query_one("#result-log", RichLog)

        log.write("[yellow]Committing…[/yellow]")
        try:
            await asyncio.to_thread(self.app.commit_fn, self._message)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user in the log
            log.write(f"[red]Commit failed: {exc}[/red]")
            log.write("[dim]Esc to go back and edit · Enter to close[/dim]")
            self._finished = True
            return
        self._outcome = "committed"
        log.write("[green]✓ Committed[/green]")

        if self._push:
            log.write("[yellow]Pushing…[/yellow]")
            try:
                await asyncio.to_thread(self.app.push_fn)
            except Exception as exc:  # noqa: BLE001 - surfaced to the user in the log
                log.write(f"[red]Push failed: {exc}[/red] [dim](push manually)[/dim]")
                log.write("[dim]Enter to close[/dim]")
                self._finished = True
                return
            self._outcome = "pushed"
            log.write("[green]✓ Pushed[/green]")

        log.write("[dim]Enter to close[/dim]")
        self._finished = True

    def action_close(self) -> None:
        """Close the app once the commit sequence has finished."""
        if not self._finished:
            return
        self.app.exit(self._outcome)

    def action_back(self) -> None:
        """Return to the editor on failure, else close with the outcome."""
        if not self._finished:
            return
        if self._outcome is None:
            self.app.pop_screen()
        else:
            self.app.exit(self._outcome)


class CommitReviewApp(App[Optional[str]]):
    """Two-screen app to review/iterate a message then commit and push it.

    Hosts the :class:`ReviewScreen` (editable message + iteration) and the
    :class:`ResultScreen` (accepted message + live commit/push updates). Git
    side effects run via the injected callables, keeping this module
    git-agnostic.

    Parameters
    ----------
    generate
        Callable mapping ``(attempts, feedbacks)`` iteration history to a freshly
        generated commit message. Called off the UI thread.
    on_commit
        Callable that commits the given message; raises on failure.
    on_push
        Callable that pushes; raises on failure.

    Attributes
    ----------
    CSS
        Stylesheet shared across both screens.
    ENABLE_COMMAND_PALETTE
        Disabled so ``ctrl+p`` commits-and-pushes instead of opening the palette.
    """

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    #review-top {
        height: 1fr;
    }

    #message-col {
        width: 1fr;
        padding: 0 1;
    }

    #history-col {
        width: 1fr;
        padding: 0 1;
        border-left: solid ansi_bright_black;
    }

    #message {
        height: 1fr;
    }

    #refine {
        margin: 1 1 0 1;
    }

    #buttons {
        height: auto;
        align: center middle;
        padding: 1 0;
    }

    #buttons Button {
        margin: 0 1;
    }

    #status {
        height: 1;
        padding: 0 1;
    }

    #result-message {
        height: auto;
        padding: 1;
    }

    #result-log {
        height: 1fr;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        generate: GenerateFn,
        on_commit: CommitFn,
        on_push: PushFn,
    ) -> None:
        """Initialise the app with its generation and git callables.

        Parameters
        ----------
        generate
            Message generator over iteration history.
        on_commit
            Commit callable (raises on failure).
        on_push
            Push callable (raises on failure).
        """
        super().__init__()
        self.generate_fn = generate
        self.commit_fn = on_commit
        self.push_fn = on_push
        self.attempts: List[str] = []
        self.feedbacks: List[str] = []

    def on_mount(self) -> None:
        """Apply the terminal theme/title and show the review screen."""
        self.theme = TERMINAL_THEME
        self.title = "diffweave"
        self.push_screen(ReviewScreen())


def review_commit(
    generate: GenerateFn,
    on_commit: CommitFn,
    on_push: PushFn,
) -> Optional[str]:
    """Run the interactive commit-review TUI and report the outcome.

    Parameters
    ----------
    generate
        Message generator over ``(attempts, feedbacks)`` iteration history.
    on_commit
        Commit callable (raises on failure).
    on_push
        Push callable (raises on failure).

    Returns
    -------
    str or None
        ``"committed"`` or ``"pushed"`` describing what happened, or ``None``
        if the user cancelled before committing.
    """
    return CommitReviewApp(generate, on_commit, on_push).run()
