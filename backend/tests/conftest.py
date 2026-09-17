"""pytest 全局夹具与守卫。

- 验收结果落盘路径统一到**工程根** `artifacts/`（不进版本控制）。
- **测试库熔断**：解析到开发库即失败（工程坑 1.4-14）—— 见 `_assert_test_db_isolated()`。
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR: Path = REPO_ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("ACC_RESULTS_PATH", str(ARTIFACTS_DIR / "acc_results.json"))


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
    """测试库必须与开发库**物理隔离**；两者相同 ⇒ 直接失败（禁止"测试写进真实库"）。

    `.env` 未配置时**不报错**（M0 阶段尚未接库）——一旦配置就必须隔离。
    """
    dev = os.environ.get("DATABASE_URL") or _read_env_value("DATABASE_URL")
    test = os.environ.get("TEST_DATABASE_URL") or _read_env_value("TEST_DATABASE_URL")
    if not dev or not test:
        return
    if dev.strip() == test.strip():
        raise RuntimeError(
            "TEST_DATABASE_URL 与 DATABASE_URL 相同 —— 测试库必须与开发库物理隔离（工程坑 1.4-14）"
        )
