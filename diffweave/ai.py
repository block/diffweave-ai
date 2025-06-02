import sys
import asyncio
from pathlib import Path

import openai
import rich
import rich.console
import rich.text
import rich.panel
import yaml

CONFIG_BASEDIR = Path().home() / ".config"
CONFIG_DIRECTORY = CONFIG_BASEDIR / "diffweave"
CONFIG_FILE = CONFIG_DIRECTORY / "config.yaml"
LEGACY_CONFIG = CONFIG_BASEDIR / 'llmit' / 'config.yaml'
# Check if the legacy config file exists and copy it to the new location if needed
if (not CONFIG_FILE.exists()) and LEGACY_CONFIG.exists():
    CONFIG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(LEGACY_CONFIG.read_text())


def configure_custom_model(model_name: str, endpoint: str, token: str, config_file: Path = CONFIG_FILE):
    """
    Configure a custom LLM model with the specified endpoint and token.

    Args:
        model_name: The name to identify the custom model
        endpoint: The API endpoint URL for the model
        token: The authentication token for accessing the model API
    """
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.touch(exist_ok=True)

    existing_config = yaml.safe_load(config_file.read_text()) or dict()

    existing_config[model_name] = {
        "endpoint": endpoint,
        "token": token,
    }

    if "<<DEFAULT>>" not in existing_config:
        existing_config["<<DEFAULT>>"] = model_name

    config_file.write_text(yaml.safe_dump(existing_config))


def set_default_model(model_name: str, config_file: Path = CONFIG_FILE):
    console = rich.console.Console()

    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.touch(exist_ok=True)

    existing_config = yaml.safe_load(config_file.read_text()) or dict()
    if model_name not in existing_config:
        console.print(rich.text.Text(f"Model '{model_name}' not found!!", style="bold red"))
        raise ValueError(f"Model '{model_name}' not found!!")

    existing_config["<<DEFAULT>>"] = model_name
    config_file.write_text(yaml.safe_dump(existing_config))


class LLM:
    def __init__(self, model_name: str, config_file: Path = CONFIG_FILE):
        self.console = rich.console.Console()
        if not config_file.exists():
            raise FileNotFoundError("Config not set! Please do so before use.")

        existing_config = yaml.safe_load(config_file.read_text())

        if model_name is None:
            model_name = existing_config["<<DEFAULT>>"]

        if (model_name is not None) and (model_name not in existing_config):
            self.console.print(rich.text.Text(f"Model '{model_name}' not found!!", style="bold red"))
            raise ValueError(f"Model '{model_name}' not found!!")

        self.model_config = existing_config[model_name]

        self.client = openai.OpenAI(
            base_url=self.model_config["endpoint"],
            api_key=self.model_config["token"],
        )
        self.model_name = model_name
        self.system_prompt = (Path(__file__).parent / "prompt.txt").read_text()

    def iterate_on_commit_message(self, repo_status_prompt: str, context: str) -> str:
        console = rich.console.Console()

        message_attempts = []
        feedback = []
        user_prompt = [repo_status_prompt, f"\n\nAdditional context provided by the user:\n{context}\n"]

        while True:
            if message_attempts and feedback:
                for a, f in zip(message_attempts, feedback):
                    user_prompt.append(
                        f"Previously REJECTED commit message attempts:\nAttempt: {a}\nUser Feedback: {f}\n---\n"
                    )

            with console.status("Generating commit message...") as status:
                loop = asyncio.new_event_loop()
                msg = loop.run_until_complete(self.query_model(user_prompt))
                status.update("Done!")
            message_attempts.append(msg)
            console.print(rich.panel.Panel(msg, title="Generated commit message"))
            console.print(
                rich.text.Text(
                    "Does this message look fine? <enter> to continue, otherwise provide feedback to improve the message",
                    style="yellow",
                )
            )
            we_good = console.input("> ").strip()
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
        message = response.choices[0].message.content

        return message
