"""**守卫的反向灵敏度** —— 证明"拦人的东西"真的能拦住（⛔ 不是"恒为真"的摆设）。

⭐ 为什么要有这个文件（2026-09-20 的教训）：
   `tests/conftest.py::_assert_test_db_isolated` 的**文档头**写着
   「测试库熔断：**解析到开发库即失败**」，而实现只比对「两个配置项不相同」——
   那条判据**恒为真**（配置项本来就不同），于是**永远不会报**：
   实测发现 pytest 一直在连**开发库**，而这道"熔断"从头到尾没响过。
   ⚠️ 它绿着、报表也绿着 —— **看绿是看不出这类问题的**。

⭐ 而抓它的**不是读代码**，是**把它跑起来看它到底干了什么**（探行为）。
   所以本文件的做法是：**逐条把守卫逼到它该报的场景**，看它报不报。
   ⇒ ⚠️ 静态扫描（"看它有没有 `raise`"）**区分不出这一类**：本仓 162 个函数的
     文档头都带"必须/不得"，其中绝大多数只是**陈述**、并非守卫 —— 扫描只会淹掉真信号。

⚠️ 本文件用 `@acc()` **显式不绑判据点** —— 它守的是**测试基建**，不是业务口径。
"""

from __future__ import annotations

import importlib

import pytest

from tests import conftest as CF
from tests.acc_plugin import acc


def _guard():
    """拿那条守卫（⚠️ 每次现取，避免模块早绑）。"""
    return importlib.import_module("tests.conftest")._assert_test_db_isolated


@acc()
def test_测试库守卫_把库指回开发库时必须报(monkeypatch):
    """⭐ **反向灵敏度**：把 `DATABASE_URL` 换回**开发库** ⇒ 守卫**必须报**。

    ⚠️ 这就是"证明它不是恒为真"的办法：一条不会红的守卫 = 没有这道防线。
       ⛔ 别把这句删掉换成"读一下源码看看它 raise 没 raise" —— 那正是它骗过所有人的地方。
    """
    dev = CF._read_env_value("DATABASE_URL")
    if not dev:
        pytest.skip("`.env` 没配 DATABASE_URL ⇒ 这条守卫本来就按「未配置不报错」放行")
    monkeypatch.setenv("DATABASE_URL", dev)          # 把生效地址换回**开发库**
    with pytest.raises(RuntimeError) as e:
        _guard()()
    assert "解析到的不是测试库" in str(e.value), (
        f"报错信息没点明「解析到的不是测试库」（实际：{str(e.value)[:80]}）—— "
        "那句话正是文档头承诺的判据，报错里要能对上")


@acc()
def test_测试库守卫_正常状态下必须放行():
    """反向的另一半：**当前**（已被 conftest 切到测试库）应放行 —— ⛔ 不然它是个"一律报错"的摆设。"""
    _guard()()                                       # 不抛就是过


@acc()
def test_测试库守卫_两个地址相同时也要报(monkeypatch):
    """两个配置项**相同** ⇒ 没有可用测试库 ⇒ 也必须报（这是它原本就有的那一半）。"""
    dev = CF._read_env_value("DATABASE_URL")
    if not dev:
        pytest.skip("`.env` 没配 DATABASE_URL")
    monkeypatch.setenv("TEST_DATABASE_URL", dev)
    monkeypatch.setenv("DATABASE_URL", dev)
    with pytest.raises(RuntimeError) as e:
        _guard()()
    assert "物理隔离" in str(e.value)
