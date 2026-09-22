"""MOD-03 **JSON API 真实连库冒烟**（可复现 · 跑完**自清理**）。

做什么：连开发库造一小批数据（i8 行 / 手动行 / 剔除行 / 付款流水）→ 用 `TestClient` 打**真实路由** →
逐项检查状态码与关键片段 → **清掉造的数据**（`SMOKE-` 前缀，精确删除）。

⚠️ 为什么必须 commit（而不是 rollback）：真实路由用的是**自己的会话 / 连接**，
   未提交的数据它看不见。⇒ 本次采用「**造数据 → commit → 冒烟 → 精确清理 → commit**」，
   并在 `finally` 里兜底再清一次（造的数据一律带 `SMOKE-` 前缀，可精确识别）。
⚠️ 只走 **GET**（读路径）；写路径（改分类 / 剔除 / 统计手改 / 批量付款 / 打印）由 `tests/` 的
   离线自检覆盖 —— 从真实路由走写操作会**真的提交**，冒烟脚本不该有那些副作用。

⭐ 2026-09-19（`§19` 批 4 · **S4⑤**）：本脚本原先打的是**服务端渲染页**
   （`GET /m03/notices` · `?draft=` · `?plan=` · `/m03/pay` · `/m03/notices/trace`）——
   那些页已随批 4 删除（授权 `D18`）⇒ 改打**存活的面**：`/api/m03/*`（列表查询是它的主入口）。
   同批还把原文件里那半截 **m04 段**删掉了：它打的 `/m04` · `/m04/import` 页**在批 2 就删了**
   ⇒ 那段早已烂成"404 也算过"的死断言（m04 的存活面 = `/api/m04/*`，由 `tests/test_api_m04_*.py` 守）。

跑法：`backend/.venv/Scripts/python.exe tools/m3_notice_smoke.py`
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete, or_, select  # noqa: E402

from app.core.db import get_session_factory  # noqa: E402
from app.core.period import default_period  # noqa: E402
from app.main import create_app  # noqa: E402
from app.mod01_projects.models import Project  # noqa: E402
from app.mod03_notice.models import PaymentNotice  # noqa: E402
from app.mod05_flow.models import PaymentFlow  # noqa: E402

TAG = "SMOKE-"
OK, BAD = "  ✓", "  ✗"
fails: list[str] = []


def check(label: str, cond: bool, extra: str = "") -> None:
    print(f"{OK if cond else BAD} {label}{('  ' + extra) if extra else ''}")
    if not cond:
        fails.append(label)


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
    projects = session.execute(
        delete(Project).where(Project.warehouse_name.like(f"{TAG}%"))
    )
    n += int(projects.rowcount or 0)
    session.commit()
    return n


def _seed(session) -> tuple[int, int, int]:
    project = Project(project_type="normal", name_full="冒烟项目",
                      warehouse_name=f"{TAG}仓库", disp=f"{TAG}仓库", status="active")
    session.add(project)
    session.flush()

    n1 = PaymentNotice(
        ph_id=f"{TAG}1", bill_no=f"{TAG}D1", bill_type="material", doc_date="2026-09-05",
        project_name="冒烟项目", biz_type="付其他供应商款", payee="某供应商", input_by="王潜森",
        category="material", excluded=False, exclude_source="", amount_approved=Decimal("10000.00"),
        stat_settle=Decimal("10000.00"),
        stat_paid=Decimal("10000.00"), approve_status="已批", i8_revoked=False, is_manual=False,
        ownership_id=project.id, fields={"BillName": "材料款结算单"},
    )
    n2 = PaymentNotice(
        ph_id=f"{TAG}M", bill_no="", bill_type="material", doc_date="2026-09-01",
        project_name="", biz_type="", payee="", input_by="科室用户", category="material",
        excluded=False, exclude_source="", amount_approved=Decimal("5000.00"),
        stat_settle=Decimal("0.00"),
        stat_paid=Decimal("2000.00"), approve_status="", i8_revoked=False, is_manual=True,
        ownership_id=project.id, fields={"BillName": "期初占位补录"},
    )
    n3 = PaymentNotice(
        ph_id=f"{TAG}X", bill_no=f"{TAG}D9", bill_type="material", doc_date="2026-09-06",
        project_name="冒烟项目", biz_type="付其他供应商款", payee="某供应商", input_by="王潜森",
        category="material", excluded=True, exclude_source="manual", amount_approved=Decimal("777.00"),
        stat_settle=Decimal("0.00"), stat_paid=Decimal("0.00"),
        approve_status="已批", i8_revoked=False, is_manual=False,
        ownership_id=project.id, fields={"BillName": "人工剔除样例行"},
    )
    session.add_all([n1, n2, n3])
    session.flush()
    session.add(PaymentFlow(flow_no=f"{TAG}FL1", notice_id=n1.id, project_id=project.id,
                            amount=Decimal("3000.00"), pay_date="2026-09-10",
                            pay_method="承兑", status="effective", request_id=f"{TAG}R1"))
    session.commit()                      # ⚠️ 真实路由用自己的会话 ⇒ 必须提交才可见
    return n1.id, n2.id, n3.id


def _items(client, **params) -> list[dict]:
    r = client.get("/api/m03/notice-list", params=params)
    check(f"GET /api/m03/notice-list {params or ''} 200", r.status_code == 200, f"[{r.status_code}]")
    return r.json().get("items", []) if r.status_code == 200 else []


def main() -> int:
    session = get_session_factory()()
    try:
        cleanup(session)                      # 先清一次，防上次异常残留
        n1_id, n2_id, n3_id = _seed(session)
        print(f"已造 SMOKE 数据：notice#{n1_id}（i8）· notice#{n2_id}（手动）· "
              f"notice#{n3_id}（人工剔除）· 流水 1\n")

        client = TestClient(create_app())

        # ① 列表查询（新壳 m03 页的数据源）
        r = client.get("/api/m03/notice-list", params={"period": ""})
        check("GET /api/m03/notice-list 200", r.status_code == 200, f"[{r.status_code}]")
        body = r.json()
        items = body.get("items", [])
        by_id = {int(i["notice_id"]): i for i in items if i.get("notice_id") is not None}
        check("列表含 i8 行与手动行", n1_id in by_id and n2_id in by_id)
        check("默认视图不含被剔除的行", n3_id not in by_id)
        check("API 不含 HTML（结构 / 数据分离）",
              not any("<" in str(v) for it in items for v in it.values()))
        check("金额是字符串（Decimal 直 JSON 化会丢精度）",
              by_id.get(n1_id, {}).get("amount_approved") == "10000.00",
              f"[{by_id.get(n1_id, {}).get('amount_approved')}]")
        check("带了前端要用的语义字段",
              all(k in by_id.get(n1_id, {}) for k in
                  ("is_excluded", "is_manual", "is_revoked", "edited_fields", "has_effective_flow")))
        check("有生效流水 ⇒ has_effective_flow 为真", by_id.get(n1_id, {}).get("has_effective_flow") is True)
        check("手动行 ⇒ is_manual 为真", by_id.get(n2_id, {}).get("is_manual") is True)
        text = str(body.get("counters", {}).get("text", ""))
        # 四档计数（新壳右侧 pill 直接印这一句）
        check("计数四档齐备（显示 / 有效 / 剔除 / i8 已撤单）",
              all(x in text for x in ("显示 ", "有效 ", "剔除 ", "i8 已撤单")), f"[{text}]")

        # ② 「分类 = 剔除」专用视图：只出剔除 / 撤单行，且带来源分档
        ex = _items(client, period="", category="exclude")
        ex_ids = {int(i["notice_id"]) for i in ex if i.get("notice_id") is not None}
        check("剔除视图列出被剔除的行", n3_id in ex_ids)
        check("剔除视图的来源分档（人工批量剔除）",
              any(i.get("exclude_source") == "manual"
                  for i in ex if int(i.get("notice_id") or 0) == n3_id))

        # ③ 默认年月 = 付款域当月（§9.2：付款域类表默认「当月」，⛔ 不是「上月」）
        r0 = client.get("/api/m03/notice-list")
        check("不传 period ⇒ 200", r0.status_code == 200, f"[{r0.status_code}]")
        check("默认年月 = 付款域当月",
              r0.json().get("filters", {}).get("period") == default_period("notice"),
              f"[{r0.json().get('filters', {}).get('period')}]")
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
