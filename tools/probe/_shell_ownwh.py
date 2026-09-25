"""壳真机自检 · **第 ⑱ 段：链路 C 弹窗「兜底前先查 i8 仓库名单」**（`TAIL-39`）。

**为什么单独立文件**：`tools/probe/_shell_smoke.py` 有 **400 行即黄**（`doc_audit` 的 `T5`）；⚠️ 连 `>600` 也只是**黄** —— `[用户·2026-09-21]` 把"红·禁合入"**降级**，只须在 `ops/阈值表.md` 登记"为什么不拆"
⇒ 与 `_shell_arch.py` / `_shell_m02.py` / `_shell_m01type.py` 同款，由主自检**调一段**。

⚠️ **怎么做到"清单为空也能真跑"**：`/api/m03/notices/unresolved` 现在**没有待指定条目**
（最近一次抓取成功后清单就空了）⇒ 页面上**没有入口按钮**。所以本段在浏览器里**临时换掉**
`API.unresolved`（它是**对象属性**，可替换），合成**一条**待指定条目 ⇒ 弹窗照真样子打开，
新代码（`ownWhCheck`/`ownWhOk`/提交前那两道拦）**真的被执行到**。
⚠️ 全程**不看真数据、不发真请求**：① 查名单那一步**只看二次确认弹窗、绝不确认**（确认 = 真登录 i8、可能顶号）；
   ② 试提交**故意**在"没查过"的状态下点 ⇒ **被壳当场拦下**（所以**一个请求都不会发出去**）。
   跑完把 `API.unresolved` **还原**。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import app.core.models_registry  # noqa: E402, F401


def check(page, errors: list[str]) -> None:
    """⑱ 真机走一遍：**合成一条 → 打开弹窗 → 点「① 先查…」→ 只看确认弹窗 → 取消 → 试提交被拦 → 还原**。"""
    stage = "合成一条待指定条目并打开弹窗"
    try:
        page.click('[data-k="m03"]')
        page.wait_for_function(
            "() => typeof window.openOwnDialog === 'function' && typeof API !== 'undefined'",
            timeout=15000,
        )
        page.evaluate("""() => {
            window.__ownOld = API.unresolved;
            API.unresolved = async () => ({items: [{
                project_name: '自检壳（合成条目，不落任何库）',
                doc_name: '自检单据名称-含关键词占位', bill_no: 'SELF-CHECK-1',
                kind: 'needs_keyword', shell_id: 1, candidates: []}]});
            openOwnDialog();
        }""")
        page.wait_for_function("() => document.querySelector('[data-act=\"ownWhCheck\"]')", timeout=10000)

        stage = "看这一环在不在"
        got = page.evaluate("""() => {
            const btn = document.querySelector('[data-act="ownWhCheck"]');
            const host = document.querySelector('[id^="ownWhRes_"]');
            const box = btn ? btn.closest('div') : null;
            return {btn: !!btn, hint: btn ? btn.innerText.trim() : '', resHost: !!host,
                    note: box && box.nextElementSibling ? box.nextElementSibling.innerText.replace(/\\s+/g,' ') : ''};
        }""")
        print("⑱ 查名单入口 =", {k: (v[:60] if isinstance(v, str) else v) for k, v in got.items()})

        stage = "填仓库名（⛔ 不提交，只为让「查名单」能跑）"
        page.fill('#ownNewName_0', '自检仓库名-不会提交')
        page.fill('#ownNewKw_0', '自检词')

        stage = "点它 —— 只能看到二次确认（⛔ 绝不确认）"
        page.click('[data-act="ownWhCheck"]')
        page.wait_for_function("() => document.querySelector('[data-act=\"ownWhOk\"]')", timeout=8000)
        dlg = page.evaluate("""() => {
            const btn = document.querySelector('[data-act="ownWhOk"]');
            const m = btn ? btn.closest('.modal') || btn.closest('div[class]') : null;
            const host = document.querySelector('.modal');
            return {text: (host ? host.innerText : '').replace(/\\s+/g,' '), ok: !!btn};
        }""")
        print("  二次确认 =", dlg["text"][:110], "· 确认键在 =", dlg["ok"])
        page.evaluate("""() => document.querySelectorAll('[data-act="closeModal"]').forEach(b => b.click())""")
        # ⛔ **一定取消**（确认 = 真登录 i8、可能顶号）；`modal()` 是同一个容器 ⇒ 取消后重开一次
        page.evaluate("() => openOwnDialog()")
        page.wait_for_function("() => document.querySelector('[data-act=\"ownAssign\"][data-pid=\"__new\"]')", timeout=8000)

        stage = "没查过就提交 ⇒ 必须被拦（⛔ 一个请求都不发）"
        page.click('[data-act="ownAssign"][data-pid="__new"]')
        # ⚠️ 页上可能还有**上一段残留的 toast**（实测踩过：读到了 ⑮ 段那条"已扶正"）⇒
        #    这里**等那条特定的消息**出现，而不是随便抓一个 toast。
        page.wait_for_function(
            """() => { const t = document.querySelector('.toast, .tp, #toast');
                       return !!t && t.innerText.indexOf('先查') >= 0; }""",
            timeout=8000,
        )
        blocked = page.evaluate("""() => {
            const t = document.querySelector('.toast, .tp, #toast');
            return {text: t ? t.innerText.replace(/\\s+/g,' ') : '',
                    stillOpen: !!document.querySelector('[data-act="ownAssign"][data-pid="__new"]')};
        }""")
        print("  提交被拦 =", blocked["text"][:110])

        oks = [
            (got["btn"] and got["resHost"], "「① 先查 i8 仓库名单」入口与结果位都在"),
            ("查" in got["hint"], f"按钮上写清了要干什么（{got['hint'][:24]}）"),
            ("必须先跑" in got["note"] or "假档案行" in got["note"], "旁边讲清了「不查就建」的后果"),
            ("强制踢掉" in dlg["text"] and dlg["ok"], "先二次确认、讲清会顶号"),
            ("先查" in blocked["text"] and "假档案行" in blocked["text"], "没查过就提交 ⇒ 当场拦下并说清原因"),
            (blocked["stillOpen"], "被拦之后弹窗还在（⛔ 没有偷偷提交）"),
        ]
        for ok, what in oks:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("TAIL-39 查名单自检未通过：" + what)
    except Exception as exc:                              # noqa: BLE001
        print(f"  ⛔ ⑱ 在「{stage}」这一步失败：{type(exc).__name__}: {str(exc)[:180]}")
        errors.append(f"TAIL-39 查名单自检异常（{stage}）：{type(exc).__name__}")
    finally:
        try:
            page.evaluate("""() => {
                if (window.__ownOld) { API.unresolved = window.__ownOld; delete window.__ownOld; }
                document.querySelectorAll('.modal [data-act="closeModal"]').forEach(b => b.click());
            }""")
        except Exception:                                 # noqa: BLE001
            pass


__all__ = ["check"]
