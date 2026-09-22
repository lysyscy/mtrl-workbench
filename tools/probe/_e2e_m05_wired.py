"""`m05` 接线**真机端到端**自检（服务 ＋ **真库**）· 跑完把临时数据**清干净**。

覆盖（全部走 **HTTP**，与壳的调用方式一致）：
1. 落一条临时付款流水（直插库）→ `/api/m05/flows` 能取到（含 `project_key` / `remark` 两列）
2. **撤销**：空原因 ⇒ **400**；有原因 ⇒ 200 落库（状态 + 原因）
3. **期初占位行**：走壳用的那个 PRG 表单端点 `POST /m05/opening` ⇒ 台账里出现期初行、欠款按期初并入
4. **台账备注**：`POST /m05/ledger/remark` ⇒ 再取台账能看到备注
5. **期初删除**：`POST /m05/opening/delete` ⇒ 期初行消失
6. `/api/m05/stats` 的形状（buckets / left / right）

⚠️ 会写库（只写自己建的临时行），`finally` 里删净。
用法：`backend/.venv/Scripts/python.exe tools/_e2e_m05_wired.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import app.core.models_registry  # noqa: E402,F401  —— ⚠️ 必须先 import（否则跨包 FK 报错）
FROM_YEAR_MONTH = "2099-07"        # 刻意用不可能有真实数据的月份 ⇒ 清理好认
REMARK = "m05自检"
fails: list[str] = []
PICKED: list[int] = []             # 本次用的项目 id（cleanup 要按它清台账备注）


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("  ✅ " if ok else "  ⛔ ") + what + (f" —— {extra}" if extra else ""))
    if not ok:
        fails.append(what)


def pick_project(c: httpx.Client) -> tuple[int, str]:
    """取一个**有仓库名**的项目（台账按仓库名归并 ⇒ 没仓库名的项目柱子进不去）。"""
    for p in c.get("/api/m01/projects?status=all").json():
        if (p.get("warehouse_name") or "").strip():
            return int(p["id"]), p["warehouse_name"]
    raise SystemExit("⛔ 库里没有带仓库名的项目，无法跑本自检")


def main() -> int:
    from app.core.db import session_scope
    from app.mod05_flow.models import PaymentFlow, FLOW_EFFECTIVE

    c = httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=True)
    pid, pkey = pick_project(c)
    PICKED.append(pid)
    print(f"（用项目 id={pid} · 仓库名={pkey}）")

    # ① 落一条临时流水
    with session_scope() as s:
        f = PaymentFlow(flow_no="E2E-M05-1", notice_id=None, project_id=pid, amount=1234.56,
                        pay_date=f"{FROM_YEAR_MONTH}-15", pay_method="现汇", remark=REMARK,
                        status=FLOW_EFFECTIVE)
        s.add(f)
        s.flush()
        fid = int(f.id)
    rows = c.get("/api/m05/flows?year_month=").json().get("rows", [])
    me = next((r for r in rows if int(r["id"]) == fid), None)
    check(me is not None, "流水列表里有这一条")
    check(bool(me and me.get("project_key")), "带 `project_key`（仓库名 = 归并键）", str(me.get("project_key") if me else ""))
    check(me and me.get("remark") == REMARK, "带 `remark`（流水备注列）")

    # ② 撤销
    r = c.post(f"/api/m05/flows/{fid}/revoke?reason=")
    check(r.status_code == 400, "**空原因 ⇒ 400**（撤销留痕必填）", f"HTTP {r.status_code}")
    r = c.post(f"/api/m05/flows/{fid}/revoke?reason=%E8%87%AA%E6%A3%80%E6%92%A4%E9%94%80")
    check(r.status_code == 200, "有原因 ⇒ 200", f"HTTP {r.status_code} {r.text[:60]}")
    me = next((x for x in c.get("/api/m05/flows?year_month=").json()["rows"] if int(x["id"]) == fid), {})
    check(me.get("status") == "revoked" and me.get("revoke_reason") == "自检撤销", "落库：已撤销 + 原因原文")

    # ③ 期初占位行（走**壳用的那个 PRG 表单端点**）
    r = c.post("/m05/opening", data={"category": "material", "project_id": str(pid),
                                     "cutoff_ym": FROM_YEAR_MONTH, "settle_amount": "1000",
                                     "paid_amount": "200", "remark": REMARK, "end_ym": ""})
    check(r.status_code == 200, "期初录入（表单端点）200", f"HTTP {r.status_code}")
    debt = c.get("/api/m05/debt").json()
    mine = [o for o in debt.get("openings", []) if o.get("project_key") == pkey]
    check(bool(mine), "欠款 payload 里出现该期初行（`openings`）", f"{len(mine)} 条")
    material = next((x for x in debt["by_category"] if x["category"] == "material"), {})
    check(abs(float(material.get("amount", 0)) - 800.0) < 0.01,
          "辅材欠款 = 期初(1000−200) = 800（无通知书时）", str(material.get("amount")))

    lg = c.get(f"/api/m05/ledger?project_id={pid}").json()
    side = next((x for x in lg["sides"] if x["label"] == "辅材"), {})
    opening = next((x for x in side.get("rows", []) if x.get("is_opening")), None)
    check(opening is not None, "台账第 1 行 = 期初行")
    check(opening and abs(float(opening["other_expense"]) - 1000) < 0.01,
          "台账期初行「其他支出」= 1000", str(opening and opening.get("other_expense")))

    # ④ 台账备注（键 = 口径 + 项目 + 月）
    r = c.post("/m05/ledger/remark", data={"category": "material", "project_id": str(pid),
                                           "ym": FROM_YEAR_MONTH, "remark": "自检备注", "end_ym": ""})
    check(r.status_code == 200, "台账备注（表单端点）200", f"HTTP {r.status_code}")
    lg2 = c.get(f"/api/m05/ledger?project_id={pid}").json()
    side2 = next((x for x in lg2["sides"] if x["label"] == "辅材"), {})
    # ⚠️ 断言要钉「带我们那句备注的那一行」（空库时**没有月行** ⇒ 泛泛地找 remark_key 会误判）
    hit = next((x for x in side2.get("rows", []) if x.get("remark") == "自检备注"), None)
    check(hit is not None, "备注已落库并回读得到")
    check(bool(hit and hit.get("remark_key")), "该行带 `remark_key`（键 = 口径 + 项目 + 月）",
          str(hit and hit.get("remark_key")))

    # ⑤ 期初删除
    oid = side2.get("opening_id")
    r = c.post("/m05/opening/delete", data={"opening_id": str(oid), "project_id": str(pid), "end_ym": ""})
    check(r.status_code == 200, "期初删除（表单端点）200", f"HTTP {r.status_code}")
    lg3 = c.get(f"/api/m05/ledger?project_id={pid}").json()
    side3 = next((x for x in lg3["sides"] if x["label"] == "辅材"), {})
    check(not any(x.get("is_opening") for x in side3.get("rows", [])), "期初行已消失")
    debt3 = c.get("/api/m05/debt").json()
    m3 = next((x for x in debt3["by_category"] if x["category"] == "material"), {})
    check(abs(float(m3.get("amount", 0))) < 0.01, "辅材欠款回到 0（期初已删）", str(m3.get("amount")))

    # ⑥ 统计形状
    st = c.get("/api/m05/stats").json()
    check(bool(st.get("buckets")) and len(st.get("right", [])) == len(st["buckets"]),
          "统计：buckets 与 right 等长", f"{len(st.get('buckets', []))} 桶")
    check(st.get("granularity") in ("week", "month"), "粒度字段在（week/month）", str(st.get("granularity")))

    return 1 if fails else 0


def cleanup() -> None:
    """删净本脚本建的临时流水 + 期初行 + 台账备注（**失败也要跑**）。"""
    from sqlalchemy import delete, select

    from app.core.db import session_scope
    from app.mod05_flow.models import OpeningBalance, PaymentFlow

    project_id = PICKED[0] if PICKED else 0

    with session_scope() as s:
        flows = [f.id for f in s.execute(select(PaymentFlow)).scalars().all()
                 if (f.remark or "") == REMARK or (f.flow_no or "").startswith("E2E-M05")]
        ops = [o.id for o in s.execute(select(OpeningBalance)).scalars().all()
               if (getattr(o, "remark", "") or "") == REMARK]
        if flows:
            s.execute(delete(PaymentFlow).where(PaymentFlow.id.in_(flows)))
        if ops:
            s.execute(delete(OpeningBalance).where(OpeningBalance.id.in_(ops)))
        s.flush()
    print(f"  🧹 已清理临时流水 {len(flows)} 条 · 期初行 {len(ops)} 条")
    # 台账备注：用**同一个出口**清空（空串 = 清除该格），别去猜表名
    try:
        httpx.Client(base_url=BASE, timeout=15.0, follow_redirects=True).post(
            "/m05/ledger/remark",
            data={"category": "material", "project_id": str(project_id), "ym": FROM_YEAR_MONTH,
                  "remark": "", "end_ym": ""},
        )
        print("  🧹 台账备注已按「口径+项目+月」清空")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ 台账备注清空失败（请手工清一次）：{exc}")


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        cleanup()
    print("\n结论：" + ("✅ 端到端全通" if rc == 0 else f"⛔ {len(fails)} 项未通过"))
    sys.exit(rc)
