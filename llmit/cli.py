import sys
import re
import shlex
import asyncio
import pathlib
from typing_extensions import Annotated
import webbrowser

import typer
import rich
import rich.text
import rich.panel
import rich.status
import rich.padding

from . import run_cmd, repo, ai

app = typer.Typer()


@app.command()
def commit(model: Annotated[str, typer.Option(help="Internal Databricks model to use")] = None):
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

    llm = ai.LLM(model)

    current_repo = repo.get_repo()

    run_cmd("git status")

    repo.add_files(current_repo)

    diffs = repo.generate_diffs_with_context(current_repo)

    if diffs == "":
        console.print(rich.text.Text("No staged changes to commit, quitting!"), style="bold")
        sys.exit()

    repo_status_prompt = diffs
    console.print(
        rich.text.Text(
            r"Do you have any additional context/information for this commit? Leave blank for none.", style="yellow"
        )
    )
    context = console.input(r"> ").strip().lower()

    try:
        msg = llm.iterate_on_commit_message(repo_status_prompt, context)
        run_cmd(f"git commit -m {shlex.quote(msg)}")

        console.print(rich.text.Text(r"Push? <enter>/y for yes, anything else for no", style="yellow"))
        should_push = console.input(r"> ").strip().lower()
        if should_push in ["", "y", "yes"]:
            push_result = run_cmd("git push")

            if "http" in push_result:
                open_pr = (
                    console.input(r"Open Pull Request (PR)? <enter>/y for yes, anything else for no:\n> ")
                    .strip()
                    .lower()
                )
                if open_pr in ["", "y", "yes"]:
                    pr_url = re.match(r"\s+(https?://.+?$)", push_result, re.IGNORECASE)
                    webbrowser.open(pr_url.group(1))

    except (KeyboardInterrupt, EOFError):
        console.print(rich.text.Text("Cancelled..."), style="bold red")


@app.command()
def add_custom_model(
    model: Annotated[str, typer.Option(help="Model name to use", prompt=True)],
    endpoint: Annotated[str, typer.Option(help="Endpoint to use", prompt=True)],
    token: Annotated[str, typer.Option(help="API token for authentication", prompt=True)],
):
    """
    Configure a custom model to be used

    This command adds a new custom LLM model configuration to the system.
    It prompts for the necessary information if not provided as options.

    Args:
        model: The name to identify the custom model
        endpoint: The API endpoint URL for the model
        token: The authentication token for accessing the model API
    """
    ai.configure_custom_model(model, endpoint, token)


@app.command()
def set_default_llm_model(model: Annotated[str, typer.Argument(help="Model name to use")]):
    """
    Set the default model to use for LLM operations - this leverages the `llm` library under the hood and will set that default as well.

    This command changes the default LLM model used for operations.
    It validates that the specified model exists before setting it as the default.

    Args:
        model: The name of the model to set as default

    Raises:
        ValueError: If the specified model is not found in the available models
    """
    ai.set_default_model(model)


if __name__ == "__main__":
    app()
