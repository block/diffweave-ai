import sys
import asyncio
from pathlib import Path
import json
import datetime
import subprocess

import openai
import rich
import rich.console
import rich.text
import rich.panel
import yaml
import dateutil.parser

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
            self.console.print(
                rich.text.Text("Configuration file not found! Run\n"),
                rich.text.Text("$> uvx diffweave-ai --help", style="bold blue"),  # todo, adjust this doc
                rich.text.Text("\nto see setup instructions"),
            )
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
                if (token := load_databricks_token_from_cache(account)) is None:
                    subprocess.run(f'databricks auth login --profile {account} --host {host}', shell=True)
                    token = load_databricks_token_from_cache(account)

                self.client = openai.OpenAI(
                    base_url="https://block-lakehouse-production.cloud.databricks.com/serving-endpoints",
                    api_key=token
                )

        if prompt is None:
            prompt = "prompt"
        self.system_prompt = (Path(__file__).parent / "prompts" / f"{prompt}.md").read_text()

    def iterate_on_commit_message(
        self, repo_status_prompt: str, context: str, return_first: bool = False, no_panel: bool = False
    ) -> str:
        message_attempts = []
        feedback = []
        user_prompt = [repo_status_prompt, f"\n\nAdditional context provided by the user:\n{context}\n"]

        loop = asyncio.new_event_loop()

        while True:
            if message_attempts and feedback:
                for a, f in zip(message_attempts, feedback):
                    user_prompt.append(
                        f"Previously REJECTED commit message attempts:\nAttempt: {a}\nUser Feedback: {f}\n---\n"
                    )

            if self.verbose:
                for portion in user_prompt:
                    self.console.print(portion)

            with self.console.status("Generating message...") as status:
                msg = loop.run_until_complete(self.query_model(user_prompt))
                status.update("Done!")
            message_attempts.append(msg)

            if no_panel:
                self.console.print(msg)
            else:
                self.console.print(rich.panel.Panel(msg, title="Generated commit message"))

            if return_first:
                return msg

            self.console.print(
                rich.text.Text(
                    "Does this message look fine? <enter> to continue, otherwise provide feedback to improve the message",
                    style="yellow",
                )
            )
            we_good = self.console.input("> ").strip()
            feedback.append(we_good)
            if we_good == "":
                break

        return msg

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


def load_databricks_token_from_cache(account: str) -> str | None:
    homedir = Path().home()
    databricks_config_dir = homedir / '.databricks'
    token_cache = databricks_config_dir / 'token-cache.json'
    try:
        conf = json.loads(token_cache.read_text())
        token_conf = conf['tokens'][account]
        expires = dateutil.parser.parse(token_conf['expiry'])
        tzinfo = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
        now = datetime.datetime.now(tz=tzinfo)
        is_token_expired = expires < now
        if not is_token_expired:
            return token_conf['access_token']
    except Exception as e:
        print(e)
