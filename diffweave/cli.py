import sys
import shlex
from typing_extensions import Annotated
import webbrowser

import cyclopts
from cyclopts import Parameter
import git
import rich
import rich.text
import rich.panel
import rich.status
import rich.padding
import copykitten

from . import run_cmd, repo, ai, tui
from . import preview as preview_gallery

app = cyclopts.App()


@app.default
def commit(
    simple: Annotated[
        bool,
        Parameter(alias="-s", help="Use natural-language style instead of Conventional Commits (feat:, fix:, etc.)"),
    ] = False,
    dry_run: Annotated[
        bool,
        Parameter(help="Generate a commit message and print it, but do not commit or push."),
    ] = False,
    non_interactive: Annotated[
        bool,
        Parameter(
            help="Skip all prompts: use the first generated message and automatically push after committing.",
        ),
    ] = False,
    verbose: Annotated[
        bool, Parameter(alias="-v", help="Print the prompt sent to the model before each generation attempt")
    ] = False,
    open_browser: Annotated[
        bool, Parameter(alias="-w", help="Open the repository URL in a browser after pushing")
    ] = False,
):
    """
    Generate a commit message for the current state of the repository.

    Default behavior (no flags) runs an interactive flow:

    - Shows the current `git status`.
    - Prompts you to stage files.
    - Generates a commit message using your configured model.
    - Lets you review and refine the message before committing.
    - Runs `git commit`, then prompts whether to `git push`.
    - Optionally opens the repository in the browser (requires `--open-browser`).

    Use `--dry-run` to preview a message without committing. Use `--non-interactive`
    for scripted or automated workflows (skips all prompts and pushes automatically).

    Run `diffweave-ai set-token-model` or `diffweave-ai set-databricks-browser-model` to configure your LLM before first use.
    """
    console = rich.console.Console()

    skip_interaction = dry_run or non_interactive

    try:
        llm = ai.LLM(verbose=verbose, prompt="simple" if simple else "prompt")
    except EnvironmentError:
        app("-h")
        sys.exit(1)

    console.print(f"[dim]Model: {llm.model_name}[/dim]")
    console.rule("[bold]diffweave-ai[/bold]")

    current_repo = repo.get_repo()

    repo_status, _ = run_cmd("git status", show_output=False, silent=True)

    if not skip_interaction:
        repo.add_files(current_repo)

    with console.status("Reading staged changes..."):
        diffs = repo.generate_diffs_with_context(current_repo)

    if diffs == "":
        console.print(rich.text.Text("No staged changes to commit, quitting!"), style="bold yellow")
        sys.exit()

    repo_status_prompt = f"{repo_status}\n\n{diffs}"

    if skip_interaction:
        msg = llm.generate_commit_message(repo_status_prompt)
        console.print(rich.panel.Panel(msg, title="Generated commit message"))
        if dry_run:
            return
        _commit(console, current_repo, msg)
        with console.status("Pushing..."):
            run_cmd("git push", show_output=False, silent=True)
        console.print("[green]✓ Pushed[/green]")
        return

    def generate(attempts: list[str], feedbacks: list[str]) -> str:
        return llm.generate_commit_message(repo_status_prompt, attempts=attempts, feedbacks=feedbacks)

    def do_commit(message: str) -> None:
        try:
            run_cmd(f"git commit -m {shlex.quote(message)}", show_output=False, silent=True)
        except SystemError:
            # A pre-commit hook may have reformatted tracked files; re-stage and retry once.
            run_cmd("git add -u", show_output=False, silent=True)
            run_cmd(f"git commit -m {shlex.quote(message)}", show_output=False, silent=True)

    def do_push() -> None:
        run_cmd("git push", show_output=False, silent=True)

    outcome = tui.review_commit(generate, do_commit, do_push)

    if outcome is None:
        console.print(rich.text.Text("Cancelled...", style="bold red"))
        return

    try:
        short_sha = current_repo.head.commit.hexsha[:9]
        console.print(f"[green]✓ Committed[/green] [dim]{short_sha}[/dim]")
    except (ValueError, git.GitError):
        console.print("[green]✓ Committed[/green]")
    if outcome == "pushed":
        console.print("[green]✓ Pushed[/green]")

    if open_browser:
        url = repo.get_repo_url(current_repo)
        webbrowser.open(url)


def _commit(console: rich.console.Console, current_repo: git.Repo, message: str) -> None:
    """
    Run ``git commit`` for the message, printing a confirmation with the sha.

    Args:
        console: Console used to print the confirmation line
        current_repo: The repository being committed to
        message: The commit message
    """
    try:
        run_cmd(f"git commit -m {shlex.quote(message)}", show_output=False, silent=True)
    except SystemError:
        # A pre-commit hook may have reformatted tracked files; re-stage and retry once.
        console.print("[yellow]Commit failed — re-staging and retrying...[/yellow]")
        run_cmd("git add -u", show_output=False, silent=True)
        run_cmd(f"git commit -m {shlex.quote(message)}", show_output=False, silent=True)
    try:
        short_sha = current_repo.head.commit.hexsha[:9]
        console.print(f"[green]✓ Committed[/green] [dim]{short_sha}[/dim]")
    except (ValueError, git.GitError):
        console.print("[green]✓ Committed[/green]")


@app.command
def pr(
    branch: Annotated[str, Parameter(help="Base branch to diff the current branch against")] = "main",
    verbose: Annotated[
        bool, Parameter(alias="-v", help="Print the prompt sent to the model before each generation attempt")
    ] = False,
):
    """
    Generate a pull request title and description for the current branch.

    Diffs the current branch against `--branch` (default: main), then uses your
    configured model to produce a PR title and body. The result is copied to your
    system clipboard automatically.

    You will be prompted for optional context (e.g. reviewer notes, issue links)
    before generation.
    """
    console = rich.console.Console()

    try:
        llm = ai.LLM(verbose=verbose, prompt="pull_request")
    except EnvironmentError:
        app("-h")
        sys.exit(1)

    console.print(f"[dim]Model: {llm.model_name}[/dim]")
    console.rule("[bold]diffweave-ai pr[/bold]")

    current_repo = repo.get_repo()

    with console.status("Collecting branch changes..."):
        commit_summary, diffs = repo.generate_diffs_for_pull_request(current_repo, branch)

    console.print(
        rich.text.Text(
            "Do you have any additional context/information for this pull request? Leave blank for none.",
            style="yellow",
        )
    )
    context = console.input("> ").strip().lower()

    repo_status_prompt = f"{commit_summary}\n\n{diffs}"

    try:
        with console.status("Generating PR description..."):
            msg = llm.generate_commit_message(repo_status_prompt, context)
        console.rule("[bold]Generated PR description[/bold]")
        console.print(msg)
        console.rule()
        copykitten.copy(msg)
        console.print("Contents copied to system clipboard!", style="bold green")
    except (KeyboardInterrupt, EOFError):
        console.print(rich.text.Text("Quitting..."), style="bold red")


@app.command(name="preview", show=False)
def preview(
    screen: Annotated[str, Parameter(help="Which TUI screen to preview: 'tree' or 'review'")] = "tree",
):
    """Launch a TUI screen with fake data for visual iteration (hidden helper)."""
    preview_gallery.launch(screen)


@app.command
def set_token_model(
    model_name: Annotated[
        str, Parameter(alias="-m", help="Model identifier to pass to the API (e.g. gpt-4o, claude-3-5-sonnet-20241022)")
    ],
    token: Annotated[str, Parameter(alias="-t", help="API token for the endpoint")],
    endpoint: Annotated[
        str, Parameter(alias="-e", help="Base URL of the OpenAI-compatible API endpoint")
    ] = "https://api.openai.com/v1",
):
    """Configure a token-authenticated OpenAI-compatible model as the active LLM. Overwrites any existing configuration."""
    console = rich.console.Console()
    ai.configure_token_model(model_name, endpoint, token)
    console.print(f"Model [bold]{model_name}[/bold] configured.", style="green")


@app.command
def set_databricks_browser_model(
    model_name: Annotated[
        str,
        Parameter(
            alias="-m",
            help="Model identifier as it appears in Databricks serving endpoints (e.g. databricks-meta-llama-3-3-70b-instruct)",
        ),
    ],
    account: Annotated[str, Parameter(alias="-a", help="Databricks workspace account name (e.g. my-org)")],
):
    """Configure a Databricks-hosted model as the active LLM using browser-based authentication. Overwrites any existing configuration."""
    console = rich.console.Console()
    ai.configure_databricks_browser_model(model_name, account)
    console.print(f"Model [bold]{model_name}[/bold] configured.", style="green")


if __name__ == "__main__":
    app()
