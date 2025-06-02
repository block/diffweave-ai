import sys
import subprocess
from typing import Union

import rich
import rich.panel
import rich.console
import rich.highlighter
import rich.syntax
import rich.text
import rich.padding


def run_cmd(cmd: str, show_output: bool = True, silent: bool = False, **subprocess_kwargs) -> Union[None, str]:
    """
    Execute a shell command and handle its output.

    This function runs a shell command and provides rich formatting for the command
    and its output. It can optionally display or hide the command's output and
    can run silently without showing the command being executed.

    Args:
        cmd: The shell command to execute as a string
        show_output: If True, display the command's stdout and stderr
        silent: If True, don't display the command being executed

    Returns:
        The stdout of the command as a string if successful, None otherwise

    Raises:
        SystemExit: If the command returns a non-zero exit code
    """
    console = rich.console.Console()

    kwargs = {
        **{
            "shell": True,
            "capture_output": True,
            "text": True,
        },
        **subprocess_kwargs,
    }

    process = subprocess.run(cmd, **kwargs)
    output = process.stdout.strip()
    error = process.stderr.strip()

    if not silent:
        console.print(
            rich.console.Group(rich.text.Text("$~~>", end=" "), rich.text.Text(f"{cmd}", style="bold green"))
        )

    if process.returncode != 0:
        console.print(rich.padding.Padding(rich.syntax.Syntax(error, "bash"), (0, 0, 0, 2)))
        console.print(rich.text.Text("Unexpected error occurred while running the command.", style="bold red"))
        raise SystemError(error)

    if show_output:
        if output:
            console.print(rich.padding.Padding(rich.syntax.Syntax(output, "bash"), (0, 0, 0, 2)))
        if error:
            console.print(rich.padding.Padding(rich.syntax.Syntax(error, "bash"), (0, 0, 0, 2)))
    elif not silent:
        console.print(
            rich.padding.Padding(rich.text.Text("result truncated", style="lightgrey"), (0, 0, 0, 2), style="dim")
        )

    return output
