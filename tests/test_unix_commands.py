import pytest

import diffweave


def test_tree():
    with pytest.MonkeyPatch.context() as m:
        m.delenv("PATH", raising=False)
        with pytest.raises(SystemError):
            diffweave.run_cmd("tree")
