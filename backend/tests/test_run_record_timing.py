"""执行记录的**耗时**：`started_at` 必须由调用方给"动作开始前"那一刻。

⚠️ 用户 2026-09-20 实测反馈：

> 「（i8 接入层的任务日志）**耗时也一直是 0 秒**」

⭐⭐ 真因**不是精度**，而是：**所有调用点都是"动作做完了才建记录、然后紧接着 finish"**
（`mod02_i8.router._persist_fetch` · `notice_executors._persist_run` 都如此）
⇒ `started_at`（建记录那一刻）与 `finished_at`（下一行 finish）**几乎同刻** ⇒ 差恒 ≈ 0。

⇒ 修法 = `create_run_record` 收一个 `started_at`，各入口**在动作开始前**取 `t0` 传进来。
本文件两件事：① **行为**上真的记得出耗时；② **结构**上不许再冒出"不传起点"的调用点。
"""

from __future__ import annotations

import pathlib
import re
from datetime import datetime, timedelta

import app

from app.core.db import session_scope
from app.mod02_i8 import repository as R
from tests.acc_plugin import acc


def _calls(text: str, name: str) -> list[str]:
    """取出所有 `name(...)` 调用的**完整实参文本**。

    ⚠️ 按**括号配平**扫（⛔ 不用正则硬套 `\\([^)]*\\)`）：实参里还有嵌套调用
       （`fetch_record_payload(object_desc=…)`），一遇到内层 `)` 就断 ⇒ 会**漏判**。
    """
    out: list[str] = []
    for m in re.finditer(re.escape(name) + r"\(", text):
        i, depth = m.end(), 1
        while i < len(text) and depth:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        out.append(text[m.end():i - 1])
    return out


@acc()
def test_执行记录记得出真实耗时():
    """行为断言：`started_at` 传进去就**真的**用它 ⇒ `finished_at − started_at` 是那个差。

    ⚠️ 顺带钉住"传了别被列默认盖掉"（`started_at` 列上带 `default=datetime.now`）——
       那是这类修复最容易**看着改了、其实没生效**的地方（`rec.started_at = t0` 必须真落到行上）。
    """
    with session_scope() as s:
        t0 = datetime.now() - timedelta(seconds=7)      # 假装这次动作跑了 7 秒
        rec = R.create_run_record(s, run_type="fetch", target="__自检_耗时__", total=1,
                                  started_at=t0)
        R.finish_run_record(s, rec, status="success", success=1, fail=0, detail={})
        s.flush()
        assert abs((rec.started_at - t0).total_seconds()) < 1, \
            "传了 `started_at` 就必须用它（⛔ 别被列默认 `datetime.now` 盖掉）"
        span = (rec.finished_at - rec.started_at).total_seconds()
        assert span >= 6, (
            f"耗时应当 ≈7 秒，实际 {span:.3f} 秒 —— 说明 `started_at` 没传进去"
            "（这正是用户 2026-09-20 报的『耗时一直是 0 秒』）")
        s.rollback()


@acc()
def test_所有执行记录的调用点都要传耗时起点():
    """**结构性守卫**：⛔ 不许再出现"建 `run_record` 时不传 `started_at`"的调用点。

    ⚠️ 为什么值得一条**源码级**断言：这个坑**行为测试抓不住**（每条链路的测试都注入假执行器，
       真实现不被调用 ⇒ 永远不会真建记录）⇒ 只能从**结构**上守。
       与 `tests/test_wiring_guards.py::test_全仓没有一个未定义的名字_拆件漏 import` 同一族：
       **不看行为、只看源码**。
    """
    root = pathlib.Path(app.__file__).resolve().parent
    bad: list[str] = []
    for p in sorted(root.rglob("*.py")):
        text = p.read_text(encoding="utf-8")
        if "create_run_record(" not in text:
            continue
        if p.name == "repository.py" and p.parent.name == "mod02_i8":
            continue            # 定义处（它本身就是收 `started_at` 的那个）—— ⛔ 不算调用点
        for args in _calls(text, "create_run_record"):
            if "started_at" not in args:
                bad.append(f"{p.relative_to(root)}：create_run_record({args.strip()[:64]}…)")
    assert not bad, (
        "这些调用点**没传 `started_at`** ⇒ 那条记录耗时恒 0"
        "（用户 2026-09-20 实测的『耗时一直是 0 秒』）：\n  " + "\n  ".join(bad))
