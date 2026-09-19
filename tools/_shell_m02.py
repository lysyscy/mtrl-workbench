"""壳真机自检 · **第 ⑯ 段：`m02` i8 接入层**（`TAIL-27`）。

**为什么单独立一个文件**：`tools/_shell_smoke.py` 有 **600 行**硬上限（`doc_audit` 的文件行数规则 = 红）
⇒ 与 `_shell_pend.py` / `_shell_arch.py` 同款，由主自检**调一段**（`check(page, errors)`）。

**它验的链条**：新写的那几段壳代码（`m02EchoKv` / `m02LogRows` / `BIND.m02` / `reloadM02`）**真的能跑** ——
两张卡必须渲染出**执行记录**里的真数据（⛔ 不是原型那 8 行硬编码／那 6 行演示表达式）；
再点一次「同步仓库名单」的确认弹窗，**看清楚会顶号就一定取消**（⛔ 本自检**绝不**确认 —— 那会真登录 i8 并强踢，`D9`）。

⚠️ 两个同步**永远不进自动自检**的那一发请求：`D9` 要求人工点击 ＋ 二次确认。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import app.core.models_registry  # noqa: E402, F401


def check(page, errors: list[str]) -> None:
    """⑯ 真机走一遍：**进 m02 → 两张卡读真记录 → 同步确认弹窗（只看不点）**。"""
    stage = "进 m02 页"
    try:
        page.click('[data-k="m02"]')
        page.wait_for_function(
            "() => document.querySelector('table[data-sort-key=\"m02:logs\"]')", timeout=15000)
        # ⚠️ 2026-09-19（`P3` 主体）：进页**才**取数 ⇒ 表壳先出现、数据随后到
        #    ⇒ 必须等**数据**（等表格元素会读到空表 —— 实测把"34 条"读成 1 条，整支 rc=1）。
        page.wait_for_function(
            "() => (typeof M02_RECS !== 'undefined') && M02_RECS.length > 0", timeout=15000)
        stage = "读两张卡"
        got = page.evaluate("""async () => {
            const tb = document.querySelector('table[data-sort-key="m02:logs"] tbody');
            const kv = document.querySelector('#view .kv');
            const be = await (await fetch('/api/m02/fetch/records?limit=50')).json();
            return {rows: tb ? tb.querySelectorAll('tr').length : -1,
                    firstRow: tb && tb.querySelector('tr') ? tb.querySelector('tr').innerText.replace(/\\s+/g,' ') : '',
                    kv: kv ? kv.innerText.replace(/\\s+/g,' ') : '',
                    wired: (document.querySelector('#ttl em')||{}).innerText||'',
                    be: (be || []).length};
        }""")
        print("⑯ m02 回显/日志 =", {k: (v[:70] if isinstance(v, str) else v) for k, v in got.items()})

        stage = "同步确认弹窗（只看不点）"
        page.click('[data-k="m01"]')
        page.wait_for_function("() => document.querySelector('[data-act=\"syncWh\"]')", timeout=10000)
        page.click('[data-act="syncWh"]')
        page.wait_for_function("() => document.querySelector('.modal')", timeout=8000)
        dlg = page.evaluate("""() => {
            const m = document.querySelector('.modal');
            return {text: m ? m.innerText.replace(/\\s+/g,' ') : '',
                    okBtn: !!document.querySelector('.mf [data-act="m02SyncOk"]')};
        }""")
        print("  同步弹窗 =", dlg["text"][:110], "· 确认键在 =", dlg["okBtn"])
        page.click('.mf [data-act="closeModal"]')          # ⛔ **一定取消**（确认 = 真顶号）

        oks = [
            ("已接后端真实数据" in got["wired"], f"顶栏已认这页接了后端（{got['wired'][:24]}）"),
            (got["rows"] == (got["be"] or 1),
             f"⭐ 任务日志行数 = 后端执行记录条数（{got['rows']} vs {got['be']}）"),
            (got["be"] == 0 or "成功" in got["firstRow"] or "失败" in got["firstRow"] or "部分" in got["firstRow"],
             f"日志首行是真记录（{got['firstRow'][:60]}）"),
            ("付款通知书" in got["kv"] and "常用项目列表" in got["kv"],
             f"回显卡的 6 行由真数据源渲染（{got['kv'][:70]}）"),
            # ⭐ 2026-09-18 实测踩到的那条假话：付款通知书的执行记录 `target` **只写年月**
            #    ⇒ 映射漏了它会让这一行显示「还没有执行记录」（库里明明有）。
            ("付款通知书 还没有执行记录" not in got["kv"],
             "付款通知书那行没被误报成「还没有执行记录」（纯年月 target 也算它）"),
            ("已撤单" not in got["kv"], "⛔ 演示表达式那几行（含「模拟」字样）没再露出来"),
            ("强制踢掉" in dlg["text"] and dlg["okBtn"], "同步确认弹窗讲清了会顶号 ＋ 确认键在"),
        ]
        for ok, what in oks:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("TAIL-27 m02 自检未通过：" + what)
    except Exception as exc:                              # noqa: BLE001
        print(f"  ⛔ ⑯ 在「{stage}」这一步失败：{type(exc).__name__}: {str(exc)[:160]}")
        errors.append(f"TAIL-27 m02 自检异常（{stage}）：{type(exc).__name__}")


__all__ = ["check"]
