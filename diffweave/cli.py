import sys
from pathlib import Path
import re
import shlex
from typing_extensions import Annotated
import webbrowser
from dataclasses import dataclass

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
    model: Annotated[str | None, Parameter(help="Internal Databricks model to use")] = None,
    simple: Annotated[
        bool,
        Parameter(help="Use simpler commit structure for messages (not conventional commits)"),
    ] = False,
    dry_run: Annotated[
        bool,
        Parameter(help="Generate a commit message based on the current repo status, print to stdout, and quit."),
    ] = False,
    non_interactive: Annotated[
        bool,
        Parameter(
            help="Run in non-interactive mode. Similar to dry run except we then use that first commit message that comes back."
        ),
    ] = False,
    config: Annotated[Path | None, Parameter(help="Path to config file")] = None,
):
    """
    Generate a commit message for the staged changes in the current git repository.

    This command uses an LLM to analyze the staged changes in the current git repository
    and generate an appropriate commit message. It allows the user to interactively
    select files to stage before generating the message, and provides options to
    regenerate the message if needed.

    Args:
        context: Additional context to include in the prompt to the LLM
        model: The specific LLM model to use for generating the commit message
    """
    console = rich.console.Console()

    skip_interaction = dry_run or non_interactive

    llm = ai.LLM(model, simple=simple, config_file=config)

    current_repo = repo.get_repo()

    run_cmd("git status")

    if not skip_interaction:
        repo.add_files(current_repo)

    diffs = repo.generate_diffs_with_context(current_repo)

    if diffs == "":
        console.print(rich.text.Text("No staged changes to commit, quitting!"), style="bold")
        sys.exit()

    repo_status_prompt = diffs
    if skip_interaction:
        context = ""
    else:
        console.print(
            rich.text.Text(
                r"Do you have any additional context/information for this commit? Leave blank for none.", style="yellow"
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
                    if pr_url := re.match(r"\s+(https?://.+?$)", push_result, re.IGNORECASE):
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
    """
    Configure a custom model to be used

    This command adds a new custom LLM model configuration to the system.
    It prompts for the necessary information if not provided as options.

    Args:
        model: The name to identify the custom model
        endpoint: The API endpoint URL for the model
        token: The authentication token for accessing the model API
        config: The path to config file
    """
    console = rich.console.Console()
    ai.configure_custom_model(model, endpoint, token, config_file=config)
    console.print(f"Model [{model}] successfully added!", style="bold green")


@app.command
def set_default(
    model: Annotated[str, Parameter(help="Model name to use")],
    config: Annotated[Path | None, Parameter(help="Path to config file")] = None,
):
    """
    Set the default model to use for LLM operations - this leverages the `llm` library under the hood and will set that default as well.

    This command changes the default LLM model used for operations.
    It validates that the specified model exists before setting it as the default.

    Args:
        model: The name of the model to set as default
        config: The path to config file

    Raises:
        ValueError: If the specified model is not found in the available models
    """
    console = rich.console.Console()

    ai.set_default_model(model, config)

    console.print(f"Model [{model}] successfully set to default!", style="bold green")


if __name__ == "__main__":
    app()
