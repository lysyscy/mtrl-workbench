"""真机验证 · `TAIL-45`：链路 A ③-b「≥2 个仓库 ⇒ **选定一个建行**」（写 → 回读 → **复原**）。

**为什么必须真机跑**：离线断言钉的是纯逻辑与静态接线；这条链路的真值在**真库**上 ——
「清单只认最近一次成功同步」要看运行记录真表、「候选不许手填」要看端点真守卫、
「建完即从清单消失」要看**现算**是不是真的按改后的档案算。

用法：先起服务（`mtrl-workbench-server`），再 `python tools/_e2e_m01_archpick.py`。

⚠️ **不留痕迹**：本次会插入**一条** `sync` 运行记录 ＋ 建**一行**临时档案；
   验证完把这一行**硬删**（它是刚建的、无任何引用 —— 同 `TAIL-37` 那次的做法）＋ 删掉那条运行记录。
⚠️ 仓库名与全名一律用 `__E2E_…__` 前缀 —— 与真数据不可能撞名。
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import app.core.models_registry  # noqa: E402, F401

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.db import session_scope  # noqa: E402
from app.mod01_projects.models import Project  # noqa: E402
from app.mod01_projects.archive_pending import record_detail  # noqa: E402
from app.mod02_i8.models import RunRecord  # noqa: E402

BASE = "http://127.0.0.1:8000"
FAKE_FULL = "__E2E_多仓库项目(TBLX2026999999)__"
WH_A, WH_B, WH_BAD = "__E2E_甲仓__", "__E2E_乙仓__", "__E2E_丙仓（手填）__"
fails: list[str] = []


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("  ✅ " if ok else "  ⛔ ") + what + (f" —— {extra}" if extra else ""))
    if not ok:
        fails.append(what)


def _item_payload() -> dict:
    return {
        "name_full": FAKE_FULL, "phid": "e2e-phid", "warehouses": [WH_A, WH_B],
        "reason": f"挂 2 个仓库（{WH_A}、{WH_B}）—— 需人工选一个再建",
    }


def cleanup() -> None:
    """删掉本次插入的**运行记录**与**临时档案行**（都是本次刚造的，零引用）。"""
    with session_scope() as s:
        for row in s.execute(select(Project).where(Project.name_full == FAKE_FULL)).scalars().all():
            s.delete(row)
        # ⚠️ `detail` 是 JSON 列 ⇒ 按**文本包含**认本次那条（⛔ 不用 `has_key`：PG 方言里已移除）
        recs = s.execute(
            select(RunRecord).where(RunRecord.target == "常用项目列表")
            .order_by(RunRecord.id.desc()).limit(20)
        ).scalars().all()
        for rec in recs:
            if FAKE_FULL in str(getattr(rec, "detail", "") or ""):
                s.delete(rec)


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    cleanup()                                    # 上一轮残留先清（幂等）

    # ① 造一条「同步」运行记录（= 真机上跑一次名单同步会写成的那种）
    with session_scope() as s:
        prev = s.execute(select(RunRecord.id).order_by(RunRecord.id.desc()).limit(1)).scalar_one_or_none()
    with session_scope() as s:
        rec = RunRecord(run_type="sync", target="常用项目列表", status="success",
                        started_at=datetime.now(), detail=record_detail([_item_payload()]))
        s.add(rec)
        s.flush()
        rid = rec.id
    check(rid > (prev or 0), "已插入一条「常用项目列表」同步记录（带待人工清单）", f"id={rid}")

    # ② 清单端点：读得回来 ＋ 来源如实 ＋ 候选 = i8 名单里那两个
    d = c.get("/api/m01/archive-pending").json()
    names = [x["full_name"] for x in d.get("items", [])]
    check(FAKE_FULL in names, "清单端点读回了这条", f"{len(names)} 条")
    it = next((x for x in d["items"] if x["full_name"] == FAKE_FULL), None)
    check(it is not None and sorted(it["warehouses"]) == sorted([WH_A, WH_B]),
          "候选 = 那次同步报出的两个仓库", str(it and it["warehouses"]))
    check(d.get("source", {}).get("target") == "常用项目列表", "如实标了来源（哪一次同步）",
          str(d.get("source")))

    # ③ 手填的仓库名 ⇒ **拒**（HTTP 400 ＋ `must_report` ＋ 一句中文原因），且一行都不落
    #    ⚠️ 形态与 `promote` 同款（`MustReportError` ⇒ 400 ＋ `{code, message}`），⛔ 不是 `ok:false`
    #       —— 这类**可预期的拒绝**壳侧由 `pjAct` 的 catch 原样转给用户（与 `promote` 同一条路）。
    rbad = c.post("/api/m01/archive-row",
                  json={"full_name": FAKE_FULL, "warehouse_name": WH_BAD})
    bad = rbad.json()
    check(rbad.status_code == 400 and bad.get("code") == "must_report"
          and "候选" in str(bad.get("message")),
          "手填的仓库名被拒（§9.4：仓库名以 i8 为准）", str(bad.get("message"))[:70])
    with session_scope() as s:
        check(s.execute(select(Project).where(Project.name_full == FAKE_FULL)).first() is None,
              "被拒之后**没落行**")

    # ④ 选定一个候选 ⇒ 建行（真库回读）
    ok = c.post("/api/m01/archive-row",
                json={"full_name": FAKE_FULL, "warehouse_name": WH_B}).json()
    check(ok.get("ok") is True, "选定候选里的仓库 ⇒ 建档成功", str(ok.get("message"))[:80])
    with session_scope() as s:
        row = s.execute(select(Project).where(Project.name_full == FAKE_FULL)).scalars().first()
    check(row is not None and row.warehouse_name == WH_B, "档案行**已落库**",
          f"id={getattr(row, 'id', None)} · type={getattr(row, 'project_type', None)} · wh={getattr(row, 'warehouse_name', None)}")
    check(getattr(row, "phid", "") == "e2e-phid", "phid 带上了（建档的钥匙）")

    # ⑤ 建完 ⇒ 再读清单：这条**当场消失**（现算生效），且**其余仓库不再建行**
    d2 = c.get("/api/m01/archive-pending").json()
    check(FAKE_FULL not in [x["full_name"] for x in d2.get("items", [])],
          "建完这条即从清单消失（⟵ 逐条按当前档案现算）",
          f"dropped={d2.get('dropped')}")
    with session_scope() as s:
        n = len(s.execute(select(Project).where(Project.name_full == FAKE_FULL)).scalars().all())
    check(n == 1, "只建了选中的那一个（决策 2：普通项目 ↔ 仓库 = 1 : 1）", f"{n} 行")

    # ⑥ 复原
    cleanup()
    with session_scope() as s:
        left = s.execute(select(Project).where(Project.name_full == FAKE_FULL)).scalars().all()
    check(not left, "已**复原**（临时档案行与那条运行记录都删掉了）")

    print("\n结论：" + ("✅ 全通（选定仓库建档真的落库、拒得也对、可复原）"
                       if not fails else f"⛔ {len(fails)} 项未过"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
