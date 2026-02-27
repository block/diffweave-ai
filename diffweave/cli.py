import sys
import shlex
from typing_extensions import Annotated
import webbrowser

import cyclopts
from cyclopts import Parameter
import rich
import rich.text
import rich.panel
import rich.status
import rich.padding
import copykitten

from . import run_cmd, repo, ai

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
    verbose: Annotated[bool, Parameter(alias="-v", help="Print the prompt sent to the model before each generation attempt")] = False,
    open_browser: Annotated[bool, Parameter(alias="-w", help="Open the repository URL in a browser after pushing")] = False,
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

    Run `diffweave-ai add-model` to configure an LLM provider before first use.
    """
    console = rich.console.Console()

    skip_interaction = dry_run or non_interactive

    try:
        llm = ai.LLM(verbose=verbose, prompt="simple" if simple else "prompt")
    except EnvironmentError:
        app('-h')
        sys.exit(1)

    current_repo = repo.get_repo()

    repo_status, _ = run_cmd("git status")

    if not skip_interaction:
        repo.add_files(current_repo)

    diffs = repo.generate_diffs_with_context(current_repo)

    if diffs == "":
        console.print(rich.text.Text("No staged changes to commit, quitting!"), style="bold")
        sys.exit()

    repo_status_prompt = f"{repo_status}\n\n{diffs}"
    if skip_interaction:
        context = ""
    else:
        console.print(
            rich.text.Text(
                r"Do you have any additional context/information for this commit? Leave blank for none.",
                style="yellow",
            )
        )
        context = console.input(r"> ").strip().lower()

    try:
        msg = llm.iterate_on_commit_message(repo_status_prompt, context, return_first=skip_interaction)

        if dry_run:
            return

        try:
            run_cmd(f"git commit -m {shlex.quote(msg)}")
        except SystemError:
            console.print("Uh oh, something happened while committing. Trying once more!")
            repo.add_files(current_repo)
            run_cmd(f"git commit -m {shlex.quote(msg)}")

        if skip_interaction:
            run_cmd("git push")
            return

        console.print(rich.text.Text(r"Push? <enter>/y for yes, anything else for no", style="yellow"))
        should_push = console.input(r"> ").strip().lower()
        if should_push in ["", "y", "yes"]:
            run_cmd("git push")

        if open_browser:
            url = repo.get_repo_url(current_repo)
            webbrowser.open(url)

    except (KeyboardInterrupt, EOFError):
        console.print(rich.text.Text("Cancelled..."), style="bold red")


@app.command
def pr(
    branch: Annotated[str, Parameter(help="Base branch to diff the current branch against")] = "main",
    verbose: Annotated[bool, Parameter(alias="-v", help="Print the prompt sent to the model before each generation attempt")] = False,
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
        app('-h')
        sys.exit(1)

    current_repo = repo.get_repo()

    commit_summary, diffs = repo.generate_diffs_for_pull_request(current_repo, branch)

    console.print(
        rich.text.Text(
            r"Do you have any additional context/information for this pull request? Leave blank for none.",
            style="yellow",
        )
    )
    context = console.input(r"> ").strip().lower()

    repo_status_prompt = f"{commit_summary}\n\n{diffs}"

    try:
        msg = llm.iterate_on_commit_message(repo_status_prompt, context, return_first=True, no_panel=True)
        copykitten.copy(msg)
        console.print("Contents copied to system clipboard!", style="bold green")
    except (KeyboardInterrupt, EOFError):
        console.print(rich.text.Text("Quitting..."), style="bold red")


@app.command
def set_token_model(
    model_name: str,
    token: Annotated[str, Parameter(alias="-t", help="API token for the endpoint")],
    endpoint: Annotated[str, Parameter(alias="-e", help="Base URL of the OpenAI-compatible API endpoint")] = "https://api.openai.com/v1/responses",
):
    """Register or update a model in the config. Use the model identifier with -m when running other commands."""
    console = rich.console.Console()
    ai.configure_token_model(model_name, endpoint, token)
    console.print(f"Model successfully set!", style="bold green")

@app.command
def set_databricks_browser_model(model_name: str, account: str):
    console = rich.console.Console()
    ai.configure_databricks_browser_model(model_name, account)
    console.print(f"Model successfully set!", style="bold green")

if __name__ == "__main__":
    app()
