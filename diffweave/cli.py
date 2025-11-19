import sys
from pathlib import Path
import re
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

from . import run_cmd, repo, ai

app = cyclopts.App()


@app.default
def commit(
    model: Annotated[str | None, Parameter(alias="-m", help="Name of the LLM Model to use")] = None,
    simple: Annotated[
        bool,
        Parameter(alias="-s", help="Use simpler commit structure for messages (not conventional commits)"),
    ] = False,
    dry_run: Annotated[
        bool,
        Parameter(help="Generate a commit message based on the current repo status, print to stdout, and quit."),
    ] = False,
    non_interactive: Annotated[
        bool,
        Parameter(
            help=(
                "Run in non-interactive mode. Similar to dry run except "
                "we then use that first commit message that comes back."
            )
        ),
    ] = False,
    verbose: Annotated[bool, Parameter(alias="-v", help="Show verbose output")] = False,
    config: Annotated[Path | None, Parameter(help="Path to config file")] = None,
):
    """
    Generate a commit message for the current state of the repository.

    Default behavior (with no arguments) is an interactive flow that:

    - Shows the current ``git status``.
    - Optionally stages files for you (interactive by default).
    - Generates a commit message using your configured model.
    - Lets you review and refine the message.
    - Attempts ``git commit`` (and optionally ``git push`` and PR open
      if a URL is printed).

    Depending on flags, the command can run purely as a dry run, perform a full commit and optional push, or operate
    in a non-interactive mode suitable for scripts.

    Note: Be sure to configure your LLM provider before use.

    Parameters
    ----------
    model : str | None
        Name of the LLM model to use.
    simple : bool
        Use simpler commit structure for messages (not conventional commits).
    dry_run : bool
        Generate a commit message based on the current repo status, print to stdout, and quit.
    non_interactive : bool
        Run in non-interactive mode. Similar to dry run except we then use the first commit message that comes back.
    verbose : bool
        Show verbose output.
    config : pathlib.Path | None
        Path to config file.
    """
    console = rich.console.Console()

    skip_interaction = dry_run or non_interactive

    llm = ai.LLM(model, simple=simple, verbose=verbose, config_file=config)

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
            push_result, error = run_cmd("git push")

            if "http" in push_result + error:
                open_pr = (
                    console.input(r"Open Pull Request (PR)? <enter>/y for yes, anything else for no:\n> ")
                    .strip()
                    .lower()
                )
                if open_pr in ["", "y", "yes"]:
                    if pr_url := re.match(r"\s+(https?://.+?$)", push_result + error, re.IGNORECASE):
                        webbrowser.open(pr_url.group(1))

    except (KeyboardInterrupt, EOFError):
        console.print(rich.text.Text("Cancelled..."), style="bold red")


@app.command
def add_model(
    model: Annotated[str, Parameter(alias="-m", help="Model name to use")],
    endpoint: Annotated[str, Parameter(alias="-e", help="Endpoint to use")],
    token: Annotated[str, Parameter(alias="-t", help="API token for authentication")],
    config: Annotated[Path | None, Parameter(alias="-c", help="Path to config file")] = None,
):
    """Register or update a custom LLM model configuration.

    Parameters
    ----------
    model : str
        Model name to use.
    endpoint : str
        Endpoint to use.
    token : str
        API token for authentication.
    config : pathlib.Path | None
        Path to config file.
    """
    console = rich.console.Console()
    ai.configure_custom_model(model, endpoint, token, config_file=config)
    console.print(f"Model [{model}] successfully added!", style="bold green")


@app.command
def set_model(
    model: Annotated[str, Parameter(help="Model name to use")],
    config: Annotated[Path | None, Parameter(help="Path to config file")] = None,
):
    """Set the default LLM model used by the CLI.

    Parameters
    ----------
    model : str
        Model name to use.
    config : pathlib.Path | None
        Path to config file.
    """
    console = rich.console.Console()

    ai.set_default_model(model, config)

    console.print(f"Model [{model}] successfully set to default!", style="bold green")


@app.command
def list_models(
    config: Annotated[Path | None, Parameter(help="Path to config file")] = None,
):
    """List all configured LLM models.

    Parameters
    ----------
    config : pathlib.Path | None
        Path to config file.
    """
    console = rich.console.Console()

    models = ai.list_models(config)

    console.print(models)


if __name__ == "__main__":
    app()
