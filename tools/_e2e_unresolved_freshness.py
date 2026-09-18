"""真机验证 · `TAIL-41`：付款侧「未命中清单」的**两层新鲜度**（写 → 回读 → **复原**）。

用法：先起服务（改了后端要**重启**），再 `python tools/_e2e_unresolved_freshness.py`。

**验两条**：
① **只认最近一次付款通知书抓取** —— 抓取**成功之后**就没有清单（⛔ 不回溯更早那条"未走完"的）；
② 清单里每一条**按当前档案现算** —— 已经能归属的（这里用"全名已建档的普通项目"制造）**当场不再出现**，
   而"命中壳但一个关键词都没命中"的**照旧留着**（那才是真要人去补词的）。

⚠️ 只碰自己造的样本（全名带 `真机演练` 前缀）；跑完**逐条删掉**并**直查库核残留**。
⚠️ 造记录一律走**应用自己的写入出口**（`create_run_record` / `finish_run_record` / `fetch_detail`），
   ⛔ 不手写 SQL —— 否则验的就不是真实落盘形态了。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import app.core.models_registry  # noqa: E402, F401

import httpx  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402

from app.core.db import session_scope  # noqa: E402
from app.mod01_projects.models import Project  # noqa: E402
from app.mod01_projects.repository import create_project  # noqa: E402
from app.mod02_i8.models import RunRecord  # noqa: E402
from app.mod03_notice.repository import (  # noqa: E402
    FETCH_MARK,
    create_run_record,
    fetch_detail,
    finish_run_record,
)

BASE = "http://127.0.0.1:8000"
URL = "/api/m03/notices/unresolved"

FULL_A = "真机演练-时效项目A(XMCB2025990001)"
FULL_B = "真机演练-时效项目B(XMCB2025990002)"
DOC = "真机演练-某单据"

fails: list[str] = []
made_pids: list[int] = []
made_recs: list[int] = []


def ck(ok: bool, what: str, extra: str = "") -> None:
    print(("  ✅ " if ok else "  ⛔ ") + what + (f" —— {extra}" if extra else ""))
    if not ok:
        fails.append(what)


def items_of(client) -> list[dict]:
    r = client.get(URL)
    return (r.json() or {}).get("items", [])


def write_record(*, reason: str = "", items: list[dict] | None = None, status: str = "success",
                 ym: str = "2026-09") -> int:
    """写一条**付款通知书抓取**运行记录（走应用自己的写入出口）。"""
    with session_scope() as s:
        rec = create_run_record(s, run_type="fetch", target=ym, total=1)
        finish_run_record(s, rec, status=status, success=1, fail=0,
                          detail=fetch_detail(reason=reason, unresolved=list(items or [])))
        return rec.id


def setup() -> None:
    made_recs.append(write_record(
        reason="ownership_unsettled", status="failed",
        items=[{"project_name": FULL_A, "doc_name": DOC, "bill_no": "真机演练-1",
                "kind": "not_archived", "shell_id": None},
               {"project_name": FULL_B, "doc_name": DOC, "bill_no": "真机演练-2",
                "kind": "no_keyword_hit", "shell_id": None}]))
    print(f"  （造好：一条「未走完」的抓取记录 id={made_recs[-1]}，带 2 条未命中）")


def teardown() -> None:
    with session_scope() as s:
        s.execute(delete(Project).where(Project.id.in_(made_pids)))
        s.execute(delete(RunRecord).where(RunRecord.id.in_(made_recs)))


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    try:
        setup()

        # ---------------- ① 清单原样出现（两条都还没着落）
        got = items_of(c)
        mine = [x for x in got if str(x.get("bill_no", "")).startswith("真机演练")]
        ck(len(mine) == 2, "未命中清单里出现两条演练条目", f"{len(mine)} 条")
        ck(all("candidates" in x for x in mine), "条目带 `candidates` 键（壳项才有内容，形状要齐）")
        if not mine:
            return 1

        # ---------------- ② 按当前档案现算：A 建档（普通项目 ⇒ 全名直接归属）⇒ 该条**当场消失**
        with session_scope() as s:
            made_pids.append(create_project(s, project_type="normal", name_full=FULL_A).id)
            made_pids.append(create_project(s, project_type="shell", name_full=FULL_B).id)
        got2 = items_of(c)
        mine2 = [x for x in got2 if str(x.get("bill_no", "")).startswith("真机演练")]
        ck(len(mine2) == 1 and mine2[0]["project_name"] == FULL_B,
           "**已经能归属的那条当场消失**（A 的全名已建档 ⇒ 不必再要人处理）",
           f"剩 {[x['project_name'] for x in mine2]}")
        ck(any(x["project_name"] == FULL_A for x in got2) is False, "A 那条确实不在清单里了")

        # ---------------- ③ 只认最近一次：再抓一次且**走完** ⇒ 整个清单消失
        newest = write_record()          # 成功那条（带标记、没有 reason）
        made_recs.append(newest)
        with session_scope() as s:
            d = s.get(RunRecord, newest).detail
        ck(bool(d.get(FETCH_MARK)), "成功那条记录里也写了 `notice_fetch` 标记（写侧三种结局都要写）",
           str(d))
        got3 = items_of(c)
        ck(got3 == [], "**抓取成功之后就没有清单了**（⛔ 不再回溯更早那条未走完的 = `TAIL-41` 正题）",
           f"实得 {len(got3)} 条")

        # ---------------- ④ 反向：把"最近一次"改回「未走完」⇒ 清单又回来（证明③不是"永远空"）
        back = write_record(reason="ownership_unsettled", status="failed",
                            items=[{"project_name": FULL_B, "doc_name": DOC,
                                    "bill_no": "真机演练-3", "kind": "no_keyword_hit",
                                    "shell_id": None}])
        made_recs.append(back)
        got4 = items_of(c)
        ck(len(got4) == 1 and got4[0]["bill_no"] == "真机演练-3",
           "最近一次又变成「未走完」⇒ 清单**回来了**（说明③的空是真的判出来的，不是恒空）",
           f"实得 {len(got4)} 条")
    finally:
        teardown()
        with session_scope() as s:
            left_p = s.execute(select(func.count()).select_from(Project)
                               .where(Project.name_full.like("真机演练%"))).scalar_one()
            left_r = s.execute(select(func.count()).select_from(RunRecord)
                               .where(RunRecord.id.in_(made_recs))).scalar_one()
        ck(left_p == 0 and left_r == 0,
           "作业后**复原**：演练样本（档案行 / 运行记录）一条不剩",
           f"残留 档案={left_p} 记录={left_r}")

    print("\n结论：" + ("✅ 全通（清单真的「只认最近一次」＋「逐条现算」）" if not fails
                     else f"⛔ {len(fails)} 项未过"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
