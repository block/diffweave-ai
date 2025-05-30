import pytest

import llmit


def test_tree():
    with pytest.MonkeyPatch.context() as m:
        m.delenv("PATH", raising=False)
        with pytest.raises(SystemError):
            llmit.run_cmd("tree")
