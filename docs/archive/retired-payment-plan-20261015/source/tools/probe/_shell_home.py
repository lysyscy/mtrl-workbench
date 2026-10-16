"""壳真机自检 · **第 ⑲ 段：看板（`home`）接真数据**（`§19` 批 5 · 2026-09-21）。

**为什么单独立一个文件**：`tools/probe/_shell_smoke.py` 有 **400 行即黄**（`doc_audit` 的 `T5`）；⚠️ 连 `>600` 也只是**黄** —— `[用户·2026-09-21]` 把"红·禁合入"**降级**，只须在 `docs/reference/thresholds.md` 登记"为什么不拆"
⇒ 与 `_shell_pend.py` / `_shell_arch.py` 同款，由主自检**调一段**（`check(page, errors)`）。

**它验的链条**（③ 是这一段的**要害**）：
  ① 看板的待办把手**都在**（集合与顺序都是契约 —— ⛔ 别在这里写死个数）；
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import app.models_registry  # noqa: E402, F401

# ⚠️ 2026-09-28（用户口径 · 看板清账）：删掉 4 个瓦片 —— `ntUnapproved` / `dfPending` / `fetchFail` /
#    `printFail`（用户判「全无用」）。⭐ **claim 不变**：留下的每一项都必须**在页面上 · 顺序固定 ·
#    数字与后端对得上**；⛔ 已撤的**不许长回来**（下面有反向断言）。删除已登记。
# ⭐ 2026-09-28（用户口径「**AB 做吧**」）：加两项真待办 —— `jcUnlinked`（集采未关联合同 ⇒ 付不了款）
#    与 `voidJoint`（i8 已撤单但仍有牵涉 ⇒ 账不准）；两者都去付款通知书页（`m03`）。
# ⚠️ 这张表**必须与壳里的瓦片顺序逐字一致**（顺序即契约）—— 当初就因为它写死 4 项、而壳里加了 2 项，
#    这句"等 4 张"的等待条件直接把真机自检**挂到超时**（本次实测踩到）。
KEYS = ["ownership", "planUnmatched", "placeholder", "jcUnlinked", "voidJoint", "fetchDue"]


def check(page, errors: list[str]) -> None:
    """⑲ 真机走一遍：**回看板 → 待办把手齐全 → ⑦ 与后端对齐 → 已撤的没长回来**。"""
    stage = "回看板"
    try:
        page.click('[data-k="home"]')
        page.wait_for_function(
            f"() => document.querySelectorAll('[data-todo]').length === {len(KEYS)}", timeout=15000)
        stage = "读待办与后端账"
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
                    nl: link('jcUnlinked'), vj: link('voidJoint'),
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
            (got["keys"] == KEYS, f"待办把手齐全且顺序不变（{len(got['keys'])} 个：{', '.join(KEYS)}）"),
            ("未接通" not in got["ttl"], f"接通页的顶栏不挂状态牌（用户裁定 B）· 实读 {got['ttl'][:20]!r}"),
            # ⚠️ 2026-09-27（裁定 `B`）：页内那句"数据来自真实/模拟"的话**整句删了** ——
            #    接通 = 默认状态，不需要声明；这里只守"⛔ 不许再有『虚构模拟值』这类假话"。
            ("虚构模拟值" not in got["tip"] and "模拟值" not in got["tip"],
             "⛔ 页内不许再说「所有数据均为虚构模拟值」（已接真数据，那是假话）"),
            (got["err"] == "", f"取数没失败（HOME_ERR = {got['err'][:30] or '空'}）"),
            (r["fetchDue"] and r["fetchDue"]["n"] == (1 if cnt.get("fetchDue") else 0),
             f"⑦「本月抓取」= 后端全表算的（{r['fetchDue'] and r['fetchDue']['n']} vs "
             f"{1 if cnt.get('fetchDue') else 0}）"),
            # ⚠️ 2026-09-28（看板清账）：⑬⑭ 两个瓦片已删 ⇒ 原「三个数与后端对齐」缩到 ⑦ 一项；
            #    claim 改成**反向**保留：这两个已撤的瓦片**不许长回页面上**（后端仍在算，只是不再上屏）。
            (r["fetchFail"] is None and r["printFail"] is None,
             "已撤的两个瓦片（⑬ 抓取失败 / ⑭ 投递失败）没有长回页面"),
            (not got["dfK"], "已撤的 ⑤ 号瓦片（差异 · 看调整单）没有长回页面"),
            # ⭐ 2026-09-28 新增两项：真机看**渲染出来的链接**是否真指到付款通知书页（离线只钉源码文本）。
            (got["nl"] == "m03" and got["vj"] == "m03",
             f"两项新待办的去向都应指 m03（实读 {got['nl']!r} / {got['vj']!r}）"),
        ]
        for ok, what in oks:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("看板接真数据自检未通过：" + what)
    except Exception as exc:                              # noqa: BLE001
        print(f"  ⛔ ⑲ 在「{stage}」这一步失败：{type(exc).__name__}: {str(exc)[:160]}")
        errors.append(f"看板接真数据自检异常（{stage}）：{type(exc).__name__}")


__all__ = ["check"]
