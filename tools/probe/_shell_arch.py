"""壳真机自检 · **第 ⑮ 段：链路 A ③-b「≥2 个仓库 ⇒ 选定一个建行」**（`TAIL-45`）。

**为什么单独立一个文件**：`tools/probe/_shell_smoke.py` 有 **400 行即黄**（`doc_audit` 的 `T5`）；⚠️ 连 `>600` 也只是**黄** —— `[用户·2026-09-21]` 把"红·禁合入"**降级**，只须在 `ops/阈值表.md` 登记"为什么不拆"
⇒ 这一段单独成文件，由主自检**调一段**（`check(page, errors)`），与 `_shell_pend.py` 同款。

**它验的链条**：名单同步报出「一个全名挂了 ≥2 个仓库」⇒ `m01` 页首出现入口（**原先没有**：那条只在
同步回执里出现一次）⇒ 点开弹窗**从候选里选一个仓库**（⛔ 不是手填）⇒ 落库（**只建选中的那一个**）
⇒ **清单当场少一条** ⇒ 复原净零。

⚠️ 造样本一律走**应用自己的写入出口**（`save_run_record`），⛔ 不手写 SQL；
⚠️ 样本全名 / 仓库名全带「真机演练」前缀；`finally` 里删干净并**直查库核残留**（净零）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import app.core.models_registry  # noqa: E402, F401

from sqlalchemy import delete, func, select  # noqa: E402

from app.core.db import session_scope  # noqa: E402
from app.mod01_projects.archive_pending import record_detail  # noqa: E402
from app.mod01_projects.models import Project  # noqa: E402
from app.mod02_i8.models import RunRecord  # noqa: E402
from app.mod02_i8.repository import save_run_record  # noqa: E402

# 一次性样本（一律带前缀 ⇒ 万一没清掉也一眼看得出是谁留下的）
ARCH_FULL = "真机演练-壳自检多仓库(XMCB2025990012)"
ARCH_WA = "真机演练-壳自检仓甲"
ARCH_WB = "真机演练-壳自检仓乙"


def check(page, errors: list[str]) -> None:
    """⑮ 真机走一遍：**造同步样本 → m01 出现入口 → 选一个仓库建行 → 复原**。"""
    made_recs: list[int] = []
    stage = "造样本"
    try:
        with session_scope() as s:
            run = save_run_record(
                s, run_type="sync", target="常用项目列表", status="success", success_count=0,
                detail=record_detail([{
                    "name_full": ARCH_FULL, "phid": "shell-arch-phid",
                    "warehouses": [ARCH_WA, ARCH_WB],
                    "reason": f"挂 2 个仓库（{ARCH_WA}、{ARCH_WB}）—— 需人工选一个再建",
                }]))
            made_recs.append(run.id)

        stage = "清单刷新"
        # ⚠️ 走 `reloadProjects()`（它内部**先刷这两路清单、最后 render()**）——
        #    ⛔ 别只调 `reloadArchPend()` ＋ 点侧栏：若**已经停在 m01**，再点一次**不触发 render**
        #    ⇒ 卡片压根不会被注入（2026-09-18 实测踩到：15 秒超时）。
        page.evaluate("() => reloadProjects()")
        page.click('[data-k="m01"]')
        page.wait_for_function("() => document.getElementById('archBox')", timeout=15000)
        info = page.evaluate("""() => {
            const box = document.getElementById('archBox');
            const tr = box.querySelector('tbody tr');
            return {head: box.querySelector('h4').innerText.replace(/\\s+/g,' '),
                    btns: box.querySelectorAll('[data-act="pjArchOpen"]').length,
                    tds: tr ? [...tr.children].map(td => td.innerText.replace(/\\s+/g,' ')) : []};
        }""")
        print("⑮ m01 待建档入口 =", info)

        stage = "打开建档弹窗"
        page.click('#archBox [data-act="pjArchOpen"]')
        page.wait_for_function("() => document.getElementById('arcWh')", timeout=8000)
        dlg = page.evaluate("""() => {
            const sel = document.getElementById('arcWh');
            return {title: (document.querySelector('.modal h3')||{}).innerText||'',
                    opts: [...sel.options].map(o => o.value),
                    inputs: document.querySelectorAll('.modal input').length};
        }""")
        print("  建档弹窗 =", dlg)

        stage = "选定并建行"
        page.select_option('#arcWh', ARCH_WB)                  # 选**第二个**仓库
        page.click('.mf [data-act="pjArchOk"]')
        # ⚠️ 2026-09-26：**等库里那行真出现**（原来是睡 1800 ms）—— 判据本来就是「库里该有它」，
        #    所以直接等它：写完就往下（不等满），**超时即红**（睡够就往下时，区分不了
        #    "没写进去"与"还没写进去"，只能靠下面读到空来猜）。
        from _shell_common import wait_db
        if not wait_db(lambda s: s.execute(
                select(Project).where(Project.name_full == ARCH_FULL)).scalars().first()):
            errors.append("建档弹窗确认后 20 s 内库里没出现那一行（建档没落库？）")
        # ⚠️ **还要等界面重绘**：原先那 1800 ms 同时盖住了"库写入"与"壳拿到响应后重绘"两件事
        #    —— 只等库 ⇒ 下面那些**界面**断言会读到还没重绘的画（实测会当场红，不是理论担心）。
        # ⭐ 2026-09-30 再补一步（**一处竞态**：只 `settle()` 仍会读到"半新"的画）：
        #    建档**确实落库了**（下面第 ⑦ 条 ✅），但壳还没把「待建档」清单**重取回来** ⇒
        #    `#archBox` 还在 ⇒ 第 ⑧ 条「建完清单里这条消失」**假红**（实测：同一天四次跑，前几次绿、后几次红 ⇒ 典型的快慢竞态）。
        #    ⇒ 与**上面那条 `wait_db`** 同一个思路：**等那件事真的发生**（⛔ 不睡固定毫秒、⛔ 也不把"settle 过了"当好了）。
        #    ⚠️ 超时 ⇒ **不吞**：下面那条断言照旧读 `ui["box"]` 并报红（等不到 = 卡片真没消失 ⇒ 该红还是红）。
        from _shell_common import settle
        try:
            page.wait_for_function("() => !document.getElementById('archBox')", timeout=8000)
        except Exception:                                     # noqa: BLE001 —— 超时不是异常处理，是"没等到"
            pass
        settle(page)
        with session_scope() as s:
            rows = s.execute(select(Project).where(Project.name_full == ARCH_FULL)).scalars().all()
            got = [(r.id, str(r.warehouse_name or ""), str(r.project_type or "")) for r in rows]
        # ⚠️ 2026-09-30：`boxText` / `boxHasItem` 是给**失败时看的** —— "卡片还在"有两种：
        #    ① 还是**老内容**（没刷新）、② 已经**空了**（本卡 0 条）但容器没摘 —— 处置完全不同；
        #    ⛔ 不给这两句，红的时候只能猜（本仓最贵那类**静默**）。
        ui = page.evaluate("""(full) => ({
            box: !!document.getElementById('archBox'),
            boxText: ((document.getElementById('archBox')||{}).innerText||'').replace(/\\s+/g,' ').slice(0,160),
            /* ⭐ 只看**卡内那张表**的行 —— ⛔ 别用"整个卡里还能不能搜到这个全名"：
               `TAIL-190` 要的「另有 N 条不属本卡」是个 `<ul>` 说明块（**应该在**，且会写出这个全名）
               ⇒ 那样判会把"说明块"误当成"待办还在"。 */
            toDoHasItem: [...document.querySelectorAll('#archBox tbody tr')]
                           .some(tr => tr.innerText.includes(full)),
            toast: [...document.querySelectorAll('.toast')].map(t=>t.innerText).join(' | '),
        })""", ARCH_FULL)

        oks = [
            (info["btns"] == 1 and len(info["tds"]) >= 4,
             "m01 页首出现「待人工建档」入口（一行一条待办）"),
            (len(info["tds"]) >= 2 and ARCH_WA in info["tds"][1] and ARCH_WB in info["tds"][1],
             f"第二格列出**待选的两个仓库**（{info['tds'][1] if len(info['tds']) > 1 else '—'}）"),
            ("常用项目列表" in info["head"], f"入口如实说明**来自哪一次同步**：{info['head'][:56]}"),
            (dlg["opts"] == [ARCH_WA, ARCH_WB], f"弹窗候选 = i8 名单里那两个（{dlg['opts']}）"),
            (dlg["inputs"] == 0, "⛔ 弹窗里**没有手填仓库名的输入框**（§9.4：只能选）"),
            (got == [(got[0][0], ARCH_WB, "normal")] if got else False,
             f"**只建了选中的那一个**（落库：{got}）"),
            ("已建档" in ui["toast"], f"界面如实报出结果：{ui['toast'][:70]}"),
            # ⭐⭐ 2026-09-30 **改判**（原判据**过时**，⛔ 不是"放宽判据"）：原判词是 `not ui["box"]`
            #    （**整个卡片容器必须消失**）—— 那是 **`TAIL-190` 之前**的形态。`TAIL-190`（用户真机报障，
            #    2026-09-29）明确要求「**丢掉的那几条也要画出来**」（否则用户看到"回执说有待人工 2 条、
            #    卡是空的"只能猜是不是坏了）⇒ 那张卡**本来就该留着**：表头写「共 0 条 · 另有 N 条不属本卡」，
            #    后者是个 `<ul>` **说明块**（`core.js` 的 `ARCP_DROP` 分支）。
            #    ⚠️ 实测（2026-09-30）：建档**确实落库了**（上面第 ⑦ 条 ✅）、卡内表格也清空了（「共 0 条」），
            #       而老判据读"容器在不在" ⇒ **假红**（且它会让人以为建档没生效）。
            #    ⇒ 改钉**意图**：**卡内那张待办表里不再有这条**（⛔ 用 `#archBox tbody tr` 精确到表格，
            #       不受 `TAIL-190` 那个说明块影响）。
            (not ui["toDoHasItem"],
             f"建完**这条待办从卡里消失**（⛔ 不摆着让人对旧清单白干；⚠️ 卡片本身可以留 —— `TAIL-190` 要求"
             f"「另有 N 条不属本卡」也画出来）｜卡里现为：{ui['boxText']!r}"),
        ]
        for ok, what in oks:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("TAIL-45 建档自检未通过：" + what)
    except Exception as exc:                              # noqa: BLE001
        print(f"  ⛔ ⑮ 在「{stage}」这一步失败：{type(exc).__name__}: {str(exc)[:160]}")
        errors.append(f"TAIL-45 建档自检异常（{stage}）：{type(exc).__name__}")
    finally:
        with session_scope() as s:
            s.execute(delete(Project).where(Project.name_full == ARCH_FULL))
            s.execute(delete(RunRecord).where(RunRecord.id.in_(made_recs)))
        with session_scope() as s:
            left = s.execute(select(func.count()).select_from(Project)
                             .where(Project.name_full == ARCH_FULL)).scalar_one()
            left_r = s.execute(select(func.count()).select_from(RunRecord)
                               .where(RunRecord.id.in_(made_recs))).scalar_one()
        ok = left == 0 and left_r == 0
        print(("  ✅ " if ok else "  ⛔ ")
              + f"⑮ 作业后复原：样本一条不剩（残留 档案={left} 记录={left_r}）")
        if not ok:
            errors.append("TAIL-45 自检样本没清干净")


__all__ = ["check", "ARCH_FULL", "ARCH_WA", "ARCH_WB"]
