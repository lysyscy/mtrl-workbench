"""壳真机自检 · **第 ⑭ 段：链路 B「待人工指认」**（`TAIL-30`-③）。

**为什么单独立一个文件**：`tools/_shell_smoke.py` 有 **600 行**硬上限（`doc_audit` 的「文件行数」规则
= 红），这一段自己就一百多行 ⇒ 单独成文件，由主自检**调一段**（`check(page, errors)`）。
⭐ 好处还有一个：这一段比别段重（**真造库样本 ＋ 真点弹窗 ＋ 跑完复原**），
   单独放更容易看清楚它"造了什么、删了什么"。

**它验的链条**（计划 §17.6）：材料侧抓取报出「同一全名命中 ≥2 条非壳行」⇒
`m01` 页首出现入口 ⇒ 点开弹窗选**哪一行** ⇒ 落库（只动被指认的那一行）⇒ **清单当场少一条** ⇒ 复原净零。

⚠️ 造样本一律走**应用自己的写入出口**（`repository.create_project` / `save_run_record`），⛔ 不手写 SQL；
⚠️ 样本全名带「真机演练」前缀；`finally` 里删干净并**直查库核残留**（净零）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import app.core.models_registry  # noqa: E402, F401

from sqlalchemy import delete, func, select  # noqa: E402

from app.core.db import session_scope  # noqa: E402
from app.mod01_projects.models import Project  # noqa: E402
from app.mod01_projects.pending import record_detail  # noqa: E402
from app.mod01_projects.recovery import KIND_MULTI  # noqa: E402
from app.mod01_projects.repository import create_project  # noqa: E402
from app.mod02_i8.models import RunRecord  # noqa: E402
from app.mod02_i8.repository import save_run_record  # noqa: E402

# 一次性样本（一律带前缀 ⇒ 万一没清掉也一眼看得出是谁留下的）
PEND_FULL = "真机演练-壳自检待指认(XMCB2025990011)"
PEND_WH = "真机演练-壳自检真实仓库名"


def check(page, errors: list[str]) -> None:
    """⑭ 真机走一遍：**造样本 → m01 出现入口 → 点开 → 指认到第二行 → 复原**。"""
    made_pids: list[int] = []
    made_recs: list[int] = []
    stage = "造样本"
    try:
        with session_scope() as s:
            for _ in range(2):          # 同名冗余行（这就是「疑似名字没带小微的壳」的样子）
                made_pids.append(
                    create_project(s, project_type="normal", name_full=PEND_FULL).id)
            run = save_run_record(
                s, run_type="fetch", target="setl 2026-09（壳自检）", status="success",
                success_count=1,
                detail=record_detail([{"kind": KIND_MULTI, "warehouse_name": PEND_WH,
                                       "owner_full_name": PEND_FULL, "reason": "壳自检样本"}]))
            made_recs.append(run.id)

        # 抓完材料侧报表后，壳就是这么刷这一路的（`whFetchBackend` 里那一句）
        stage = "清单刷新"
        page.evaluate("() => reloadPending()")
        page.click('[data-k="m01"]')
        page.wait_for_function("() => document.getElementById('pendBox')", timeout=15000)
        info = page.evaluate("""() => {
            const box = document.getElementById('pendBox');
            const tr = box.querySelector('tbody tr');
            return {head: box.querySelector('h4').innerText.replace(/\\s+/g,' '),
                    btns: box.querySelectorAll('[data-act="pjPromoteOpen"]').length,
                    /* ⚠️ 逐格取那一行（⛔ 别拿「整块前 220 字」当断言窗口 —— 后半截被截掉时会假红） */
                    tds: tr ? [...tr.children].map(td => td.innerText.replace(/\\s+/g,' ')) : []};
        }""")
        print("⑭ m01 待指认入口 =", info)

        stage = "打开指认弹窗"
        page.click('#pendBox [data-act="pjPromoteOpen"]')
        page.wait_for_function("() => document.getElementById('pmRow')", timeout=8000)
        dlg = page.evaluate("""() => {
            const sel = document.getElementById('pmRow');
            return {title: (document.querySelector('.modal h3')||{}).innerText||'',
                    opts: [...sel.options].map(o => o.text)};
        }""")
        print("  指认弹窗 =", dlg)

        stage = "确认指认"
        page.select_option('#pmRow', str(made_pids[1]))     # 指定**第二条**同名行
        page.click('.mf [data-act="pjPromoteOk"]')
        page.wait_for_timeout(1800)
        with session_scope() as s:
            got_a = str(s.get(Project, made_pids[0]).warehouse_name or "")
            got_b = str(s.get(Project, made_pids[1]).warehouse_name or "")
        ui = page.evaluate("""() => ({
            box: !!document.getElementById('pendBox'),
            toast: [...document.querySelectorAll('.toast')].map(t=>t.innerText).join(' | '),
        })""")

        oks = [
            (info["btns"] == 1 and len(info["tds"]) >= 4,
             "m01 页首出现「待人工指认」入口（一行一条待办）"),
            (len(info["tds"]) >= 1 and PEND_WH in info["tds"][0],
             f"第一格 = **这条陌生仓库名**（{info['tds'][0] if info['tds'] else '—'}）"),
            (len(info["tds"]) >= 2 and PEND_FULL[:12] in info["tds"][1],
             "第二格 = 它的**项目全名**（人能对上抓取回执里那句话）"),
            ("setl 2026-09" in info["head"], f"入口如实说明**来自哪一次抓取**：{info['head'][:50]}"),
            (len(dlg["opts"]) == 2, f"指认弹窗列出**全部**同名候选行（{len(dlg['opts'])} 条）"),
            (all("占位行" in o for o in dlg["opts"]), "占位行在选项里被标出来"),
            (got_b == PEND_WH, f"指定的那一行真的被扶正（第二行 → {got_b}）"),
            (got_a.startswith("未建仓-"), f"**没被指定的那行一个字没动**（第一行仍是 {got_a}）"),
            ("已扶正" in ui["toast"], f"界面如实报出结果：{ui['toast'][:60]}"),
            (not ui["box"], "指认完**清单里这条消失**（⛔ 不摆着让人对旧清单白干）"),
        ]
        for ok, what in oks:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("TAIL-30-③ 指认自检未通过：" + what)
    except Exception as exc:                              # noqa: BLE001
        print(f"  ⛔ ⑭ 在「{stage}」这一步失败：{type(exc).__name__}: {str(exc)[:160]}")
        errors.append(f"TAIL-30-③ 指认自检异常（{stage}）：{type(exc).__name__}")
    finally:
        with session_scope() as s:
            s.execute(delete(Project).where(Project.id.in_(made_pids)))
            s.execute(delete(RunRecord).where(RunRecord.id.in_(made_recs)))
        with session_scope() as s:
            left = s.execute(select(func.count()).select_from(Project)
                             .where(Project.name_full.like("真机演练%"))).scalar_one()
            left_r = s.execute(select(func.count()).select_from(RunRecord)
                               .where(RunRecord.id.in_(made_recs))).scalar_one()
        ok = left == 0 and left_r == 0
        print(("  ✅ " if ok else "  ⛔ ")
              + f"⑭ 作业后复原：样本一条不剩（残留 档案={left} 记录={left_r}）")
        if not ok:
            errors.append("TAIL-30-③ 自检样本没清干净")


__all__ = ["check", "PEND_FULL", "PEND_WH"]
