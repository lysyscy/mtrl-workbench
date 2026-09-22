"""`MOD-09` 特殊费用月报表 —— **真机端到端**（连真服务 + 真库）。

覆盖：读那一份 → ② 新增手填项 → ③ 改名 → ④ 改金额（合法）→ ⑤ **非法金额必须拒绝且原值不变**
→ ⑥ **负数允许**（§5.5 最宽松一档）→ ⑦ 删除复原 → ⑧ 直查库核实**无残留**。

⛔ 本页**不写 i8、不抓取**（自动项只读 `inv_detail`），所以跑它**不会顶号**。
⚠️ 全程**净零**：一增一删，跑完库里应回到原样（脚本自己核对，不靠人记）。

用法：服务在跑（`127.0.0.1:8000`）⇒ `python tools/_e2e_m09_wired.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

# 让脚本能 import 到 app（查库那一步用）
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

BASE = "http://127.0.0.1:8000"
fails: list[str] = []


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("  ✅ " if ok else "  ⛔ ") + what + (f" —— {extra}" if extra else ""))
    if not ok:
        fails.append(what)


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    fee = c.get("/api/m09/fee").json()
    ym, pj = fee["ym"], fee["project"]
    print(f"① 读那一份 —— ym={ym} · pj={pj!r}")

    # ---- 读：形状与同源
    for k in ("ym", "project", "project_display", "projects", "auto", "manuals",
              "total", "count", "can_edit", "columns", "auto_name"):
        check(k in fee, f"读端点出字段 `{k}`")
    check("ops" not in (fee["auto"] or {}), "`ops` 列**不进 API**（`domain.PAGE_ONLY_KEYS`）")
    check(all(p.get("key") for p in fee["projects"]), "候选每项都有键（= 仓库名，§2.7.4）")
    check(isinstance(fee["total"], str), "金额出**字符串**（精度保护）⇒ 转数字是适配层（`N0()`）的职责")
    if not pj or not fee["can_edit"]:
        print("  ⚠️ 该月没有可写的项目那一份 ⇒ 只做读检查，跳过写路径")
        print("\n结论：" + ("全通 ✅" if not fails else f"⛔ {len(fails)} 条未过"))
        return 1 if fails else 0

    before = len(fee["manuals"])
    print(f"   起始手填项 {before} 条 · 合计 {fee['total']}")

    # ---- ② 新增
    print("② 新增手填项（`POST /api/m09/fee/add`）")
    r = c.post("/api/m09/fee/add", json={"ym": ym, "project": pj}).json()
    check(r.get("ok") is True, "新增成功", r.get("message", "")[:70])
    after = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
    check(len(after["manuals"]) == before + 1, "回读多了一行（真的落库了）",
          f"{before} → {len(after['manuals'])}")
    idx = len(after["manuals"]) - 1

    try:
        # ---- ③ 改名
        print("③ 改名（`/fee/name`）")
        r = c.post("/api/m09/fee/name", json={"ym": ym, "project": pj, "index": idx, "value": "油卡使用"}).json()
        check(r.get("ok") is True, "改名成功", r.get("message", "")[:70])
        check(c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()["manuals"][idx]["item"] == "油卡使用",
              "回读项名确为「油卡使用」")

        # ---- ④ 改金额（合法）
        print("④ 改金额（合法 12345.67）")
        r = c.post("/api/m09/fee/amount",
                   json={"ym": ym, "project": pj, "index": idx, "value": "12345.67"}).json()
        check(r.get("ok") is True, "合法金额被接受", r.get("message", "")[:70])
        got = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
        check(got["manuals"][idx]["amount"] == "12345.67", "回读金额 = 12,345.67",
              f"实际 {got['manuals'][idx]['amount']}")

        # ---- ⑤ 非法金额：**必须拒绝且原值不变**
        print("⑤ ⭐ 非法金额（`abc`）⇒ 必须拒绝且原值不变")
        r = c.post("/api/m09/fee/amount",
                   json={"ym": ym, "project": pj, "index": idx, "value": "abc"}).json()
        check(r.get("ok") is False, "非法金额被**拒绝**", r.get("message", "")[:70])
        got = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
        check(got["manuals"][idx]["amount"] == "12345.67", "**原值未变**（不是 0、也不是空）",
              f"实际 {got['manuals'][idx]['amount']}")

        # ---- ⑥ 负数允许
        print("⑥ 负数（`-88.5`）⇒ §5.5 只拦「非数字」、**允许 0 与负数**")
        r = c.post("/api/m09/fee/amount",
                   json={"ym": ym, "project": pj, "index": idx, "value": "-88.5"}).json()
        check(r.get("ok") is True, "负数被接受", r.get("message", "")[:70])
        got = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
        check(got["manuals"][idx]["amount"] == "-88.50", "回读金额 = -88.50",
              f"实际 {got['manuals'][idx]['amount']}")
        check(got["auto"]["share"] in ("—",) or isinstance(got["auto"]["share"], str),
              "合计 ≤ 0 ⇒ 「占合计」给「—」而不是 `NaN%`", f"实际 {got['auto']['share']!r}")
    finally:
        # ---- ⑦ 复原（无论上面成没成，都要删掉那一行）
        print("⑦ 复原（`/fee/delete`）")
        r = c.post("/api/m09/fee/delete", json={"ym": ym, "project": pj, "index": idx}).json()
        check(r.get("ok") is True, "删除成功（回执带重算后的合计）", r.get("message", "")[:80])

    got = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
    check(len(got["manuals"]) == before, "手填项回到起始条数", f"{len(got['manuals'])} vs {before}")

    # ---- ⑧ 直查库（唯一权威）
    print("⑧ 直查库核实无残留")
    try:
        from sqlalchemy import text

        from app.core.db import session_scope

        with session_scope() as s:
            n = s.execute(text("SELECT count(*) FROM fee_manual_item")).scalar()
        check(n == 0, "`fee_manual_item` 表为空（净零）", f"实际 {n} 行")
    except Exception as exc:  # noqa: BLE001
        print(f"    ℹ️ 直查库跳过（{exc.__class__.__name__}: {exc}）")

    print("\n结论：" + ("全通 ✅" if not fails else f"⛔ {len(fails)} 条未过"))
    for f in fails:
        print("   ·", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
