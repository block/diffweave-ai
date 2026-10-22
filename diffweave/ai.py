import sys
import asyncio
from pathlib import Path
import json
import subprocess
from typing import Optional

import openai
import rich
import rich.console
import rich.text
import rich.panel
import yaml

CONFIG_BASEDIR = Path().home() / ".config"
CONFIG_DIRECTORY = CONFIG_BASEDIR / "diffweave"
CONFIG_FILE = CONFIG_DIRECTORY / "config.yaml"


def configure_token_model(model_name: str, endpoint: str, token: str):
    """
    Configure a custom LLM model with the specified endpoint and token.

    Args:
        model_name: The name to identify the custom model
        endpoint: The API endpoint URL for the model
        token: The authentication token for accessing the model API
    """
    config_file = _initialize_config()

    config_file.write_text(
        yaml.safe_dump(
            {
                "type": "token",
                "model_name": model_name,
                "endpoint": endpoint,
                "token": token,
            }
        )
    )

def configure_databricks_browser_model(model_name: str, account: str):
    config_file = _initialize_config()
    config_file.write_text(
        yaml.safe_dump(
            {
                "type": "databricks",
                "model_name": model_name,
                "account": account,
            }
        )
    )



class LLM:
    def __init__(
        self,
        verbose: bool = False,
        prompt: str = None,
    ):
        self.verbose = verbose
        self.console = rich.console.Console()

        config_file = _initialize_config()
        model_config = yaml.safe_load(config_file.read_text())

        if model_config is None:
            self.console.print(rich.panel.Panel(
                "No model configured yet. Run one of:\n\n"
                "  [bold]diffweave-ai set-token-model[/bold] [dim]<model> -t <token>[/dim]\n"
                "  [bold]diffweave-ai set-databricks-browser-model[/bold] [dim]<model> <account>[/dim]",
                title="[yellow]Setup required[/yellow]",
                border_style="yellow",
            ))
            raise EnvironmentError

        self.model_name = model_config["model_name"]
        match model_config:
            case {"type": "token"}:
                self.client = openai.OpenAI(
                    base_url=model_config["endpoint"],
                    api_key=model_config["token"],
                )
            case {"type": "databricks"}:
                account = model_config["account"]
                host = f"https://{account}.cloud.databricks.com"
                if (token := load_databricks_token(account)) is None:
                    subprocess.run(["databricks", "auth", "login", "--profile", account, "--host", host])
                    token = load_databricks_token(account)
                    if token is None:
                        self.console.print(
                            f"[red]Failed to acquire Databricks token for profile {account!r}.[/red]"
                        )
                        raise EnvironmentError

                self.client = openai.OpenAI(
                    base_url="https://block-lakehouse-production.cloud.databricks.com/serving-endpoints",
                    api_key=token
                )

        if prompt is None:
            prompt = "prompt"
        self.system_prompt = (Path(__file__).parent / "prompts" / f"{prompt}.md").read_text()

    def generate_commit_message(
        self,
        repo_status_prompt: str,
        context: str = "",
        attempts: Optional[list[str]] = None,
        feedbacks: Optional[list[str]] = None,
    ) -> str:
        """
        Generate a single commit message for the given repository state.

        This is a one-shot generation: it builds the prompt from the repository
        status/diff, any optional user context, and the history of previously
        rejected attempts with their feedback, then returns the model's output.
        Callers (the interactive TUI, or the scripted CLI paths) own any
        iteration loop.

        Args:
            repo_status_prompt: The git status and diff text describing changes
            context: Optional free-form context supplied by the user
            attempts: Previously generated messages that were rejected
            feedbacks: Feedback aligned with ``attempts`` explaining each rejection

        Returns:
            The generated commit message
        """
        attempts = attempts or []
        feedbacks = feedbacks or []

        user_prompt = [repo_status_prompt]
        if context:
            user_prompt.append(f"\n\nAdditional context provided by the user:\n{context}\n")
        for attempt, feedback in zip(attempts, feedbacks):
            user_prompt.append(
                f"Previously REJECTED commit message attempts:\nAttempt: {attempt}\nUser Feedback: {feedback}\n---\n"
            )

        return asyncio.run(self.query_model(user_prompt))

    async def query_model(self, prompt: list[str]) -> str:
        """
        Query an LLM model with a prompt and system message.

        This asynchronous function sends a prompt to the specified LLM model
        along with a system message to guide the model's response.

        https://platform.openai.com/docs/guides/structured-outputs?api-mode=responses

        Args:
            prompt: The main prompt text to send to the model

        Returns:
            The model's response as a string
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            max_tokens=1000,
            stream=False,
            messages=[
                {"role": "system", "content": self.system_prompt},
                *[{"role": "user", "content": p} for p in prompt],
            ],
        )
        message = response.choices[0].message.content.strip()

        if message.startswith("```\n"):
            message = "\n".join(message.split("\n")[1:])

        if message.endswith("\n```"):
            message = "\n".join(message.split("\n")[:-1])

        return message


def _initialize_config():
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.touch(exist_ok=True)

    return CONFIG_FILE


def load_databricks_token(account: str) -> str | None:
    """Fetch a fresh Databricks access token via the CLI.

    Databricks CLI v1.0.0 moved token storage to the OS keychain, so reading
    ``~/.databricks/token-cache.json`` directly no longer works. ``databricks
    auth token`` handles refresh transparently and returns the live token.
    """
    result = subprocess.run(
        ["databricks", "auth", "token", "--profile", account, "-o", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)["access_token"]
    except (json.JSONDecodeError, KeyError):
        return None
