"""壳真机自检 · **第 ⑰ 段：`m01` 类型列的人工覆盖**（`TAIL-42`）。

**为什么单独立文件**：`tools/probe/_shell_smoke.py` 有 **400 行即黄**（`doc_audit` 的 `T5`）；⚠️ 连 `>600` 也只是**黄** —— `[用户·2026-09-21]` 把"红·禁合入"**降级**，只须在 `ops/阈值表.md` 登记"为什么不拆"
⇒ 与 `_shell_pend.py` / `_shell_arch.py` / `_shell_m02.py` 同款，由主自检**调一段**。

**它验的链条**：新写的壳代码（`BIND.m01` 的类型格注入 ＋ `pjTypeDlg` / `pjTypeOk`）**真的能跑** ——
① 类型格里真的挂上了动作（点得动）；② 弹窗真的能开、口径真的写全（含"⛔ 不能选具体小微"）；
③ 选「普通项目」才出现仓库名输入框。

⛔ **绝不确认** —— 确认就是**改真档案**（本自检只"点开看看"，看完取消）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import app.models_registry  # noqa: E402, F401


def check(page, errors: list[str]) -> None:
    """⑰ 真机走一遍：**进 m01 → 类型格可点 → 弹窗口径齐 → 选普通项目出输入框 → 取消**。"""
    stage = "进 m01 页"
    try:
        page.click('[data-k="m01"]')
        page.wait_for_function("() => document.querySelector('[data-act=\"pjTypeOpen\"]')", timeout=15000)
        stage = "看类型格"
        got = page.evaluate("""() => {
            const cells = [...document.querySelectorAll('#view tr [data-act="pjTypeOpen"]')];
            const c0 = cells[0];
            return {n: cells.length,
                    txt: c0 ? (c0.textContent||'').trim() : '',
                    hasId: c0 ? !!c0.dataset.id : false,
                    mouseHint: c0 ? (c0.getAttribute('title')||'') : ''};
        }""")
        print("⑰ 类型格 =", got)

        stage = "打开改类型弹窗（只看不点）"
        page.click('#view tr [data-act="pjTypeOpen"]')
        page.wait_for_function("() => document.querySelector('.modal')", timeout=8000)
        dlg = page.evaluate("""() => {
            const m = document.querySelector('.modal');
            return {text: (m ? m.innerText : '').replace(/\\s+/g,' ')};
        }""")
        print("  弹窗 =", dlg["text"][:150])

        stage = "选「普通项目」看仓库名输入框"
        page.click('[data-act="pjTypePick"][data-t="normal"]')
        page.wait_for_function("() => document.querySelector('#pjTypeWh')", timeout=6000)
        picked = page.evaluate("""() => ({hasWh: !!document.querySelector('#pjTypeWh'),
                                          hasShellOpt: !!document.querySelector('[data-act="pjTypePick"][data-t="shell"]'),
                                          hasSmallOpt: !!document.querySelector('[data-act="pjTypePick"][data-t="small"]')})""")
        print("  选了普通项目 =", picked)
        page.click('.mf [data-act="closeModal"]')          # ⛔ **一定取消**（确认 = 改真档案）

        oks = [
            (got["n"] >= 1 and got["hasId"], f"类型格挂上了动作（{got['n']} 格 · 文字「{got['txt']}」）"),
            ("人工" in got["mouseHint"] or "改类型" in got["mouseHint"], "格子上有提示（知道点得动）"),
            ("普通项目或小微壳" in dlg["text"], "弹窗说明允许改为哪两种类型"),
            (picked["hasShellOpt"] and not picked["hasSmallOpt"], "界面不允许人工指定具体小微"),
            (picked["hasWh"], "选「普通项目」才出现仓库名输入框"),
            (picked["hasShellOpt"] and not picked["hasSmallOpt"], "可选项只有 普通项目 / 小微壳"),
        ]
        for ok, what in oks:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("TAIL-42 类型纠正自检未通过：" + what)
    except Exception as exc:                              # noqa: BLE001
        print(f"  ⛔ ⑰ 在「{stage}」这一步失败：{type(exc).__name__}: {str(exc)[:160]}")
        errors.append(f"TAIL-42 类型纠正自检异常（{stage}）：{type(exc).__name__}")


__all__ = ["check"]
