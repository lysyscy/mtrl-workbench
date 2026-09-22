"""`MOD-07` 壳接线断言用的**共用件**（自 `test_wired_m07.py` 拆出 · 2026-09-19）。

**为什么拆**：`test_wired_m07.py` 涨到 **613 行 > 600** —— `tools/audit/doc_audit.py` 的 `T5` 写着「禁合入」。
⇒ 把「取壳源码的常量与配平取片工具」提到本件（照 `tests/m03_action_helpers.py` 的先例），
`test_wired_m07.py` 与 `test_wired_m07_big.py` 共用一份（⛔ 别各抄一份 —— 那就是"同一件事两遍"）。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc  # noqa: F401  ← 两个使用方都要它

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛
ROUTER = (ROOT / "backend" / "app" / "mod07_setl" / "router.py").read_text(encoding="utf-8")
API = (ROOT / "backend" / "app" / "mod07_setl" / "api.py").read_text(encoding="utf-8")


def _body(name: str) -> str:
    """取壳里 `function <name>(…){…}` 的函数体（**花括号配平**，不靠"下一个函数"）。"""
    i = SHELL.find(f"function {name}(")
    assert i >= 0, f"壳里找不到 `function {name}(`"
    j = SHELL.find("{", i)
    depth, k = 0, j
    while k < len(SHELL):
        if SHELL[k] == "{":
            depth += 1
        elif SHELL[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    body = SHELL[i:k + 1]
    assert len(body) < 6000, f"`{name}` 取到 {len(body)} 字符 —— 配平可能跑偏"
    return body


def _slice(name: str, limit: int = 12000) -> str:
    """取壳里 `V.<name>=()=>{…}` 的切片（花括号配平）。"""
    i = SHELL.find(f"\nV.{name}=()=>{{")
    assert i > 0, f"壳里找不到 `V.{name}=()=>{{`"
    i += 1
    depth, k = 0, SHELL.find("{", i)
    while k < len(SHELL):
        if SHELL[k] == "{":
            depth += 1
        elif SHELL[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    body = SHELL[i:k + 1]
    assert 2000 < len(body) < limit, f"`V.{name}` 切片长度 {len(body)} 可疑 —— 配平可能跑偏"
    return body
