"""pytest 全局夹具与守卫。

- 验收结果落盘路径统一到**工程根** `artifacts/`（不进版本控制）。
- **测试库熔断**：解析到开发库即失败（工程坑 1.4-14）—— 见 `_assert_test_db_isolated()`
  与下面的 ⚠️ 说明（**它此前只做了一半**）。
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR: Path = REPO_ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("ACC_RESULTS_PATH", str(ARTIFACTS_DIR / "acc_results.json"))


# ⚠️⚠️⚠️ **2026-09-20 修：pytest 此前根本没连测试库** ——
#
# 本文件原来的 `_assert_test_db_isolated()` 只检查「两个地址**不相同**」，
# 却**从来没有把库换过去** ⇒ `app.core.db.get_engine()` 读的是 `DATABASE_URL`（**开发库**）
# ⇒ **所有库级断言其实一直打在开发库上**。实测：pytest 里
# `get_engine().url == …/mtrl_workbench`（而不是 `…/mtrl_workbench_test`）。
#
# ⭐ 两个**旁证**此前都被我当成别的问题解释过去了，现在一对就明白：
#   ① **测试库落后开发库好几个迁移** —— 因为没人往它写，它的版本号停在很久以前；
#   ② 冒烟留下的自检行只在**开发库**里找得到。
#
# ⭐ 而本文件**文档头**写的正是「**测试库熔断：解析到开发库即失败**」——
#    ⇒ 代码从来没实现那句话（文档比代码承诺得多，是最容易骗过人的一种偏差）。
#
# ⛔ 这段**必须在任何 `app.core.config` 导入之前**执行（`get_settings()` 会缓存）⇒
#    放在 conftest 的**模块顶层**，而不是夹具里。
def _point_tests_at_test_db() -> None:
    """把 `DATABASE_URL` 指向**测试库**（没有测试库配置时**保持原样**并留给守卫报错）。

    ⚠️ 用**覆盖**语义（`os.environ[...] = ...`）而不是 `setdefault`：
       外部若已导出 `DATABASE_URL`（指向开发库），`setdefault` 会**默默保留它** ——
       那正是"看起来配了、其实没换"的老毛病。
    """
    test = os.environ.get("TEST_DATABASE_URL") or _read_env_value("TEST_DATABASE_URL")
    if test:
        os.environ["DATABASE_URL"] = test


def pytest_configure(config) -> None:  # noqa: ARG001
    """会话启动即做环境守卫（不连库，只比对配置）。"""
    _assert_test_db_isolated()


def _read_env_value(key: str) -> str:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip()
    return ""


def _assert_test_db_isolated() -> None:
    """**测试进程解析到的库，必须是测试库** —— 否则直接失败（工程坑 1.4-14）。

    ⚠️ 2026-09-20 改写。原来的实现只比对「`.env` 里两个地址**不相同**」就收工，
       **从没检查测试进程用哪个库** ⇒ 于是"两个地址当然不同"**恒成立**，
       而实际连的是**开发库** —— 一条**永远为真、因此永远不报**的守卫。
       ⭐ 那种守卫比没有更坏：它在文档头写着"解析到开发库即失败"，
         让人以为有防线（本仓最贵的一课）。

    现在的判据 = **拿"实际生效的地址"和"开发库"比**（而不是拿两个配置项互比）：
      ① 两个配置项相同 ⇒ 没有可用的测试库，报错；
      ② **实际生效的不是测试库** ⇒ 报错（这才是"解析到开发库即失败"的字面含义）。

    `.env` 未配置时**不报错**（M0 阶段尚未接库）——一旦配置就必须隔离。
    """
    dev = _read_env_value("DATABASE_URL")            # ⚠️ 直接读 .env：那才是"开发库"的本尊
    test = os.environ.get("TEST_DATABASE_URL") or _read_env_value("TEST_DATABASE_URL")
    live = os.environ.get("DATABASE_URL") or ""      # ⚠️ 实际生效的（已被上面换成测试库）
    if not dev or not test:
        return
    dev, test, live = dev.strip(), test.strip(), live.strip()
    if dev == test:
        raise RuntimeError(
            "TEST_DATABASE_URL 与 DATABASE_URL 相同 —— 测试库必须与开发库物理隔离（工程坑 1.4-14）")
    if live != test:
        raise RuntimeError(
            "测试进程**解析到的不是测试库** —— 「测试库熔断：解析到开发库即失败」（工程坑 1.4-14）\n"
            f"  实际生效：{live}\n  测试库应为：{test}\n"
            "  ⇒ 检查 `tests/conftest.py` 的 `_point_tests_at_test_db()` 有没有被绕过"
            "（例如某个 conftest / 插件在它之前就调用了 `get_settings()`）。")


# ⚠️ 调用点必须在**本文件末尾**（`_read_env_value` 得先定义好），
#    但仍**早于任何测试模块**被导入 ⇒ 也就早于 `app.core.config` 的首次调用 ✓
_point_tests_at_test_db()
