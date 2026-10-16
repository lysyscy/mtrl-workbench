"""验收绑定插件的报告阶段回归：清理失败不能被调用阶段的绿覆盖。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests import acc_plugin
from tests.acc_plugin import acc


@acc()
@pytest.mark.parametrize("teardown", ["passed", "failed"])
def test_清理阶段不得把失败记为通过(monkeypatch, teardown):
    results = {}
    # 在测试体返回前复原，避免吞掉 pytest 对本测试的真实报告。
    with monkeypatch.context() as scoped:
        scoped.setattr(acc_plugin, "_results", results)
        acc_plugin.pytest_runtest_logreport(SimpleNamespace(nodeid="test_node", when="call", outcome="passed"))
        assert results == {"test_node": "passed"}
        acc_plugin.pytest_runtest_logreport(SimpleNamespace(nodeid="test_node", when="teardown", outcome=teardown))
        assert results == {"test_node": teardown}
