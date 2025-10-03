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
