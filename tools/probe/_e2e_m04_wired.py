"""`m04` 接线**真机端到端**自检（服务 ＋ **真库**）· 跑完把临时数据**清干净**。

为什么要有它：`tests/test_wired_m04.py` 是**静态**检查（壳里有没有接线点），**证明不了**
"按下去真的落库"。本脚本走**真 HTTP ＋ 真库**，覆盖：

1. 落一行临时计划（`2099-01`，`doc_no` 空 ⇒ 判定「无单据号」＝未匹配档）
2. 列表能取到它，且带**后端判定** `audit_result`
3. 行内改列（`pay_date`）→ **落库且下次取回还在**
4. 「再次匹配」→ 重跑同一个审查引擎
5. **强制通过**：空备注 ⇒ **被后端拒（400）**；有备注 ⇒ 落库 ＋ 留痕
6. **取消强制通过** → 回到原判定、备注清空
7. **删除两步**：先 `delete-impact`（**后端**列影响范围）→ 再 `delete?confirmed=true`

⚠️ 会写库（只写自己建的临时行），`finally` 里删净。
用法：`backend/.venv/Scripts/python.exe tools/_e2e_m04_wired.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

# ⚠️ **必须先 import 注册表**：否则跨包外键（`plan_row.project_id → project.id`）报
#    `NoReferencedTableError` —— 与 `tools/_e2e_m01_wired.py` 同一坑（MEMORY §七）。
import app.models_registry  # noqa: E402,F401

YM = "2099-01"          # 刻意用一个不可能有真实数据的年月 ⇒ 清理时好认
fails: list[str] = []


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("  ✅ " if ok else "  ⛔ ") + what + (f" —— {extra}" if extra else ""))
    if not ok:
        fails.append(what)


def main() -> int:
    from app.core.db import session_scope
    from app.mod04_plan.models import PlanRow

    c = httpx.Client(base_url=BASE, timeout=30.0)

    print("① 落一行临时计划（直接入库，模拟「导入」的结果）")
    with session_scope() as s:
        row = PlanRow(year_month=YM, project_input="", project_id=None, doc_no="",
                      flow_amount=10000, planned_amount=10000, pay_date="", pay_method="现汇",
                      remark="自检", is_manual=True, forced_through=False)
        s.add(row)
        s.flush()
        rid = int(row.id)
    check(rid > 0, "临时行已建", f"id={rid}")

    print("② 列表能取到 ＋ 带后端判定")
    rows = c.get(f"/api/m04/plans?year_month={YM}").json().get("rows", [])
    me = next((r for r in rows if int(r["id"]) == rid), None)
    check(me is not None, "列表里有这一行")
    check(me and me.get("audit_result"), "带 `audit_result`（后端判定）", str(me.get("audit_result") if me else ""))
    check(me and me.get("audit_result") == "无单据号", "空单据号 ⇒ 判定「无单据号」")

    print("③ 行内改列（立刻落库 · 不留痕）")
    r = c.post(f"/api/m04/plans/{rid}/cell?column=pay_date&value=2099-01-05")
    check(r.status_code == 200, "改列 200", f"HTTP {r.status_code} {r.text[:80]}")
    again = next((x for x in c.get(f"/api/m04/plans?year_month={YM}").json()["rows"]
                  if int(x["id"]) == rid), {})
    check(again.get("pay_date") == "2099-01-05", "改后**再取回还是新值**（真落库）", str(again.get("pay_date")))

    print("④ 再次匹配（重跑同一个审查引擎）")
    r = c.post(f"/api/m04/plans/{rid}/re-match")
    check(r.status_code == 200, "再次匹配 200", f"HTTP {r.status_code}")

    print("⑤ 强制通过：**空备注必须被后端拒**")
    r = c.post(f"/api/m04/plans/{rid}/force?remark=")
    check(r.status_code == 400, "空备注 ⇒ 400", f"HTTP {r.status_code} {r.text[:80]}")
    r = c.post(f"/api/m04/plans/{rid}/force?remark=%E8%87%AA%E6%A3%80%E5%B7%B2%E6%A0%B8%E5%AE%9E")
    check(r.status_code == 200, "有备注 ⇒ 200", f"HTTP {r.status_code} {r.text[:80]}")
    again = next((x for x in c.get(f"/api/m04/plans?year_month={YM}").json()["rows"]
                  if int(x["id"]) == rid), {})
    check(again.get("forced_through") is True, "落库：forced_through = True")
    check(again.get("forced_remark") == "自检已核实", "落库：备注原文", str(again.get("forced_remark")))

    print("⑥ 取消强制通过（回到原判定、备注清空）")
    r = c.post(f"/api/m04/plans/{rid}/force-cancel")
    check(r.status_code == 200, "取消 200", f"HTTP {r.status_code}")
    again = next((x for x in c.get(f"/api/m04/plans?year_month={YM}").json()["rows"]
                  if int(x["id"]) == rid), {})
    check(again.get("forced_through") is False and not again.get("forced_remark"),
          "回到「未处理」且备注清空")

    print("⑦ 删除两步（§4.3.6：先看**后端**影响范围，再删）")
    imp = c.get(f"/api/m04/delete-impact?ids={rid}")
    check(imp.status_code == 200, "影响范围 200", f"HTTP {imp.status_code}")
    payload = imp.json() if imp.status_code == 200 else {}
    listed = payload.get("impacts") or []
    # ⚠️ 字段名以**真机返回**为准（`impacts:[{row_id,seq,year_month,result}]`）——
    #    猜错键名会让断言"看起来过了其实什么都没查"（本脚本第一版就猜成了 `rows`）
    check(any(int(x.get("row_id", -1)) == rid for x in listed),
          "影响范围里**确实列出了**这一行", f"{len(listed)} 行 · 键={sorted(listed[0]) if listed else '—'}")
    check(payload.get("count") == len(listed), "`count` 与明细条数一致")
    # ⛔ 未确认不许删
    r = c.post(f"/api/m04/plans/delete?ids={rid}")
    check(r.status_code == 400, "**没确认就删 ⇒ 400**（§4.3.6 两步不可省）", f"HTTP {r.status_code}")
    r = c.post(f"/api/m04/plans/delete?ids={rid}&confirmed=true")
    check(r.status_code == 200, "确认后删除 200", f"HTTP {r.status_code} {r.text[:80]}")
    gone = all(int(x["id"]) != rid
               for x in c.get(f"/api/m04/plans?year_month={YM}").json().get("rows", []))
    check(gone, "删除后列表里没有了")

    return 1 if fails else 0


def cleanup() -> None:
    """删净本脚本建的临时行（**失败也要跑**）。"""
    from sqlalchemy import delete, select

    from app.core.db import session_scope
    from app.mod04_plan.models import PlanRow

    with session_scope() as s:
        ids = [int(r.id) for r in s.execute(select(PlanRow)).scalars().all()
               if r.year_month == YM and (r.remark or "") == "自检"]
        if ids:
            s.execute(delete(PlanRow).where(PlanRow.id.in_(ids)))
            s.flush()
    print(f"  🧹 已清理临时计划行 {len(ids)} 行")


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        cleanup()
    print("\n结论：" + ("✅ 端到端全通" if rc == 0 else f"⛔ {len(fails)} 项未通过"))
    sys.exit(rc)
