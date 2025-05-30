import pytest

import llmit


def test_running_commands():
    assert len(llmit.run_cmd("find .").splitlines()) > 1


def test_bad_command():
    with pytest.raises(SystemError):
        llmit.run_cmd("asdkjhfasdjhk")


def test_piping():
    content = "foo bar biz baz"
    assert content == llmit.run_cmd("cat", input=content)
