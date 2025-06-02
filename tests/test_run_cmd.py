import pytest

import diffweave


def test_running_commands():
    assert len(diffweave.run_cmd("find .").splitlines()) > 1


def test_bad_command():
    with pytest.raises(SystemError):
        diffweave.run_cmd("asdkjhfasdjhk")


def test_piping():
    content = "foo bar biz baz"
    assert content == diffweave.run_cmd("cat", input=content)
