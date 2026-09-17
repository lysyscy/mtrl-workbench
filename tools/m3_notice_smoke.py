"""MOD-03 页面/接口 **真实连库冒烟**（可复现 · 跑完**自清理**）。

做什么：连开发库造一小批数据（i8 行 / 手动行 / 付款计划行）→ 用 `TestClient` 打**真实路由** →
逐项检查状态码与关键片段 → **清掉造的数据**（`SMOKE-` 前缀，精确删除）。

⚠️ 为什么必须 commit（而不是 rollback）：真实路由用的是**自己的会话 / 连接**，
   未提交的数据它看不见。⇒ 本次采用「**造数据 → commit → 冒烟 → 精确清理 → commit**」，
   并在 `finally` 里兜底再清一次（造的数据一律带 `SMOKE-` 前缀，可精确识别）。
⚠️ 只走 **GET**（读路径）；写路径（改分类 / 剔除 / 付款 / 导入）由 `tests/` 的离线自检覆盖 ——
   从真实路由走写操作会**真的提交**，冒烟脚本不该有那些副作用。

跑法：`backend/.venv/Scripts/python.exe tools/m3_notice_smoke.py`
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from re import findall, search

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete, or_, select  # noqa: E402

from app.core.db import get_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.mod01_projects.models import Project  # noqa: E402
from app.mod03_notice.models import PaymentNotice  # noqa: E402
from app.mod04_plan.models import PlanRow  # noqa: E402
from app.mod05_flow.models import PaymentFlow  # noqa: E402

TAG = "SMOKE-"
OK, BAD = "  ✓", "  ✗"
fails: list[str] = []


def check(label: str, cond: bool, extra: str = "") -> None:
    print(f"{OK if cond else BAD} {label}{('  ' + extra) if extra else ''}")
    if not cond:
        fails.append(label)


def _plan_rows(html: str) -> list[str]:
    """取 m04 数据区里的每一行 `<tr>`（用来按行断言"手动行有徽标 / 有审查结果"）。"""
    body = search(r"<tbody\b[^>]*>([\s\S]*?)</tbody>", html)
    return findall(r"<tr\b[^>]*>[\s\S]*?</tr>", body.group(1) if body else "")


def cleanup(session) -> int:
    """删掉本脚本造过的数据（**只认 `SMOKE-` 前缀**）。"""
    n = 0
    ids = [
        r.id
        for r in session.execute(
            select(PaymentNotice).where(
                or_(PaymentNotice.ph_id.like(f"{TAG}%"), PaymentNotice.bill_no.like(f"{TAG}%"))
            )
        ).scalars().all()
    ]
    if ids:
        session.execute(delete(PaymentFlow).where(PaymentFlow.notice_id.in_(ids)))
        session.execute(delete(PaymentNotice).where(PaymentNotice.id.in_(ids)))
        n += len(ids)
    flows = session.execute(
        delete(PaymentFlow).where(PaymentFlow.flow_no.like(f"{TAG}%"))
    )
    n += int(flows.rowcount or 0)
    plans = session.execute(delete(PlanRow).where(PlanRow.doc_no.like(f"{TAG}%")))
    n += int(plans.rowcount or 0)
    projects = session.execute(
        delete(Project).where(Project.warehouse_name.like(f"{TAG}%"))
    )
    n += int(projects.rowcount or 0)
    session.commit()
    return n


def main() -> int:
    session = get_session_factory()()
    try:
        cleanup(session)                      # 先清一次，防上次异常残留

        project = Project(project_type="normal", name_full="冒烟项目",
                          warehouse_name=f"{TAG}仓库", disp=f"{TAG}仓库", status="active")
        session.add(project)
        session.flush()

        n1 = PaymentNotice(
            ph_id=f"{TAG}1", bill_no=f"{TAG}D1", bill_type="material", doc_date="2026-09-05",
            project_name="冒烟项目", biz_type="付其他供应商款", payee="某供应商", input_by="王潜森",
            category="material", excluded=False, exclude_source="", amount_approved=Decimal("10000.00"),
            pay_amount_src=Decimal("10000.00"), stat_settle=Decimal("10000.00"),
            stat_paid=Decimal("10000.00"), approve_status="已批", i8_revoked=False, is_manual=False,
            ownership_id=project.id, fields={"BillName": "材料款结算单"},
        )
        n2 = PaymentNotice(
            ph_id=f"{TAG}M", bill_no="", bill_type="material", doc_date="2026-09-01",
            project_name="", biz_type="", payee="", input_by="科室用户", category="material",
            excluded=False, exclude_source="", amount_approved=Decimal("5000.00"),
            pay_amount_src=Decimal("0.00"), stat_settle=Decimal("0.00"),
            stat_paid=Decimal("2000.00"), approve_status="", i8_revoked=False, is_manual=True,
            ownership_id=project.id, fields={"BillName": "期初占位补录"},
        )
        session.add_all([n1, n2])
        session.flush()

        session.add(PaymentFlow(flow_no=f"{TAG}FL1", notice_id=n1.id, project_id=project.id,
                                amount=Decimal("3000.00"), pay_date="2026-09-10",
                                pay_method="承兑", status="effective", request_id=f"{TAG}R1"))
        session.add(PlanRow(year_month="2026-09", project_input=f"{TAG}仓库", project_id=project.id,
                            match_status="matched", match_candidates=1, doc_no=f"{TAG}D1",
                            flow_amount=Decimal("10000.00"), planned_amount=Decimal("6000.00"),
                            pay_date="2026-09-12", pay_method="供应链", remark="", raw={}))
        manual_plan = PlanRow(year_month="2026-09", project_input=f"{TAG}仓库", project_id=project.id,
                              match_status="matched", match_candidates=1, doc_no=f"{TAG}D1",
                              flow_amount=Decimal("10000.00"), planned_amount=Decimal("500.00"),
                              pay_date="", pay_method="", remark="手动补录", is_manual=True,
                              raw={"来源": "手动新增"})
        session.add(manual_plan)
        session.commit()                      # ⚠️ 真实路由用自己的会话 ⇒ 必须提交才可见
        n1_id, n2_id, mp_id = n1.id, n2.id, manual_plan.id
        print(f"已造 SMOKE 数据：notice#{n1_id}（i8）· notice#{n2_id}（手动）· 流水 1 · 计划行 1\n")

        client = TestClient(create_app())

        r = client.get("/m03/notices", params={"period": ""})
        check("GET /m03/notices 200", r.status_code == 200, f"[{r.status_code}]")
        check("列表含 i8 行与手动行", f"{TAG}D1" in r.text and "手动</span>" in r.text)
        check("有生效流水 ⇒ 出「撤销付款」", "撤销付款" in r.text)
        check("统计两金额是可改格", f'name="v_{n1_id}_stat_settle"' in r.text)
        check("批量动作条齐备",
              all(x in r.text for x in ("改辅材", "批量剔除", "恢复剔除", "批量付款", "批量打印")))

        r = client.get("/m03/notices", params={"period": "", "draft": "new"})
        check("GET ?draft=new 200 且出草稿行", r.status_code == 200 and 'class="draftrow"' in r.text)
        check("草稿行统计结算恒为 0", "0.00 恒为 0" in r.text)

        r = client.get("/m03/notices", params={"period": "", "draft": str(n2_id)})
        check("GET ?draft=<手动行> 200 且是编辑态",
              r.status_code == 200 and f'value="{n2_id}"' in r.text)

        r = client.get("/m03/notices", params={"period": "", "draft": str(n1_id)})
        check("GET ?draft=<i8行> 拒绝编辑并说明", "只对**手动新增行**开放" in r.text)

        r = client.get("/m03/notices", params={"period": "", "plan": "2026-09"})
        check("GET ?plan=2026-09 200 且预勾选",
              r.status_code == 200 and f'value="{n1_id}" checked' in r.text)

        r = client.get("/api/m03/notice-list", params={"period": ""})
        check("GET /api/m03/notice-list 200", r.status_code == 200)
        items = r.json().get("items", [])
        check("API 不含 HTML", not any("<input" in str(v) for it in items for v in it.values()))

        r = client.get("/m03/pay", params={"ids": [n1_id, n2_id]})
        check("GET /m03/pay 200", r.status_code == 200)
        check("付款方式默认来自付款计划", 'value="供应链" selected' in r.text)
        check("有「移出本次付款」", "移出本次付款" in r.text)

        r = client.get("/m03/notices/trace", params={"id": n1_id})
        check("GET /m03/notices/trace 200（只读）", r.status_code == 200)
        check("含流水子表与两金额", f"{TAG}FL1" in r.text and "统计结算金额" in r.text)

        r = client.get("/m04/import")
        check("GET /m04/import 200", r.status_code == 200 and 'name="year_month"' in r.text)

        r = client.get("/m04", params={"year_month": "2026-09"})
        check("GET /m04 含「导入…」入口", r.status_code == 200 and "导入…" in r.text)
        check("GET /m04 含「＋ 手动新增计划行」入口", "＋ 手动新增计划行" in r.text)
        plan_rows = _plan_rows(r.text)
        manual_row = next((x for x in plan_rows if f">{mp_id}<" in x), "")
        check("手动计划行带「手动」徽标与编辑入口",
              bool(manual_row) and "手动</span>" in manual_row and "/m04/row/draft" in manual_row)
        check("⭐ 手动计划行一样被审查（有审查结果标签）",
              bool(manual_row) and ("tag " in manual_row.split("<td>")[-2] or "重复上报" in manual_row))

        r = client.get("/m04", params={"year_month": "2026-09", "draft": "new"})
        check("GET /m04?draft=new 出草稿行", r.status_code == 200 and 'class="draftrow"' in r.text)
        r = client.get("/m04", params={"year_month": "2026-09", "draft": str(mp_id)})
        check("GET /m04?draft=<手动行> 是编辑态",
              r.status_code == 200 and "手动补录" in r.text and 'class="draftrow"' in r.text)
    finally:
        removed = cleanup(session)
        session.close()
        print(f"\n✓ 已清理 SMOKE 数据（{removed} 条）—— 开发库恢复原样")

    print(f"\n{'=' * 62}")
    if fails:
        print(f"✗ 冒烟未通过：{len(fails)} 项")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("✓ 冒烟全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
