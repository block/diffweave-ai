import pytest

import diffweave


def test_running_commands():
    stdout, stderr = diffweave.run_cmd("find .")
    assert len(stdout.splitlines()) > 1


def test_bad_command():
    with pytest.raises(SystemError):
        diffweave.run_cmd("asdkjhfasdjhk")


def test_piping():
    content = "foo bar biz baz"
    stdout, stderr = diffweave.run_cmd("cat", input=content)
    assert content == stdout


def test_run_cmd_silent(capsys):
    diffweave.run_cmd("echo hello", silent=True)
    assert "$>" not in capsys.readouterr().out


def test_run_cmd_stderr_on_success():
    stdout, stderr = diffweave.run_cmd("bash -c 'echo err >&2'", show_output=True)
    assert stderr == "err"


def test_run_cmd_truncated_output(capsys):
    diffweave.run_cmd("echo hello", show_output=False, silent=False)
    assert "result truncated" in capsys.readouterr().out
