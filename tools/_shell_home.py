"""壳真机自检 · **第 ⑲ 段：看板（`home`）接真数据**（`§19` 批 5 · 2026-09-21）。

**为什么单独立一个文件**：`tools/_shell_smoke.py` 有 **600 行**硬上限（`doc_audit` 的 `T5` = 红）
⇒ 与 `_shell_pend.py` / `_shell_arch.py` 同款，由主自检**调一段**（`check(page, errors)`）。

**它验的链条**（③ 是这一段的**要害**）：
  ① 看板 9 项待办**都在**（把手集合是契约）；
  ② 顶栏/侧栏**按页说实话** —— `home` 进了 `WIRED` ⇒ 必须说「已接后端真实数据」，
     而页面里那句「所有数据均为虚构模拟值」**必须已经不在**（它曾是全站唯一还在说假话的一句）；
  ③ ⭐ **⑦⑬⑭ 三个数与后端对得上**（`/api/home/run-counts`）—— 而且要比的是**后端全表算的**那份，
     ⛔ 不是"壳里扫记录窗口"算的（两者在记录很少时**恰好相等**，所以这一条只证明"现在是真数"；
     证明"不许退回窗口算法"的那条在 `tests/test_acc_home_todo.py::001-04` 的源码断言里）；
  ④ ⑤ 号瓦片的**去向**已改指库存单据（`m08`，`m12` 已撤页）；
  ⑤ ⑬ 的说明里带**那条真失败记录的时间**（说明它真的读了记录，⛔ 不是一句写死的安慰话）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import app.core.models_registry  # noqa: E402, F401

KEYS = ["ntUnapproved", "ownership", "planUnmatched", "jcPending", "dfPending",
        "placeholder", "fetchDue", "fetchFail", "printFail"]


def check(page, errors: list[str]) -> None:
    """⑲ 真机走一遍：**回看板 → 9 项待办 → 三个记账数与后端对齐 → 去向与失败时间**。"""
    stage = "回看板"
    try:
        page.click('[data-k="home"]')
        page.wait_for_function(
            "() => document.querySelectorAll('[data-todo]').length === 9", timeout=15000)
        stage = "读 9 项与后端账"
        got = page.evaluate("""async () => {
            const tiles = [...document.querySelectorAll('[data-todo]')];
            const one = k => { const t = document.querySelector('[data-todo="' + k + '"]');
                return t ? {n: Number(t.dataset.n), v: t.querySelector('.v').textContent.trim(),
                            seg: t.innerText.replace(/\\s+/g,' ')} : null; };
            const link = k => { const a = document.querySelector('[data-todo="' + k + '"] [data-k]');
                return a ? a.dataset.k : ''; };
            const be = await (await fetch('/api/home/run-counts')).json();
            const ttl = document.querySelector('#ttl em');
            const tip = document.querySelector('#view .tip');
            return {keys: tiles.map(t => t.dataset.todo),
                    ttl: ttl ? ttl.textContent.trim() : '',
                    tip: tip ? tip.innerText.replace(/\\s+/g,' ') : '',
                    run: {fetchDue: one('fetchDue'), fetchFail: one('fetchFail'),
                          printFail: one('printFail')},
                    dfK: link('dfPending'),
                    dfSeg: one('dfPending') ? one('dfPending').seg : '',
                    err: (typeof HOME_ERR !== 'undefined') ? HOME_ERR : '‹无 HOME_ERR›',
                    be: be};
        }""")
        r, be = got["run"], got["be"]
        cnt = (be or {}).get("counts") or {}
        latest = (be or {}).get("latest") or {}
        # ⭐ ③ 的后端那一侧：那条真失败记录的**时间**（取 `started_at` 的 `YYYY-MM-DD HH:MM`）
        f_at = ((latest.get("fetchFail") or {}).get("started_at") or "").replace("T", " ")[:16]
        oks = [
            (got["keys"] == KEYS, f"9 项待办把手齐全且顺序不变（{len(got['keys'])} 个）"),
            ("已接后端真实数据" in got["ttl"], f"⛔ 顶栏按页说实话（{got['ttl'][:20]}）"),
            ("虚构模拟值" not in got["tip"] and "真实数据" in got["tip"],
             "⛔ 页内那句「所有数据均为虚构模拟值」（接真数后就是假话）已经不在了"),
            (got["err"] == "", f"取数没失败（HOME_ERR = {got['err'][:30] or '空'}）"),
            (r["fetchDue"] and r["fetchDue"]["n"] == (1 if cnt.get("fetchDue") else 0),
             f"⑦「本月抓取」= 后端全表算的（{r['fetchDue'] and r['fetchDue']['n']} vs "
             f"{1 if cnt.get('fetchDue') else 0}）"),
            (r["fetchFail"] and r["fetchFail"]["n"] == (1 if cnt.get("fetchFail") else 0),
             f"⑬「最近一次抓取失败」与后端一致（{r['fetchFail'] and r['fetchFail']['n']}）"),
            (r["printFail"] and r["printFail"]["n"] == (1 if cnt.get("printFail") else 0),
             f"⑭「打印投递失败」与后端一致（{r['printFail'] and r['printFail']['n']}）"),
            (not f_at or (r["fetchFail"] and f_at in r["fetchFail"]["seg"]),
             f"⑬ 的说明里带**那条真失败记录的时间**（{f_at or '后端无失败记录'}）"),
            (got["dfK"] == "m08", f"⑤ 号瓦片已改指库存单据（去向 = {got['dfK'] or '空'}）"),
            ("调整单" in got["dfSeg"], "⑤ 的说明讲清了差异的载体是调整单"),
        ]
        for ok, what in oks:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("看板接真数据自检未通过：" + what)
    except Exception as exc:                              # noqa: BLE001
        print(f"  ⛔ ⑲ 在「{stage}」这一步失败：{type(exc).__name__}: {str(exc)[:160]}")
        errors.append(f"看板接真数据自检异常（{stage}）：{type(exc).__name__}")


__all__ = ["check"]
