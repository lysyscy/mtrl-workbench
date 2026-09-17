"""`MOD-08` 库存单据 / 调整单 —— **真机端到端**（连真服务 + 真库）。

覆盖：读全量 → 打调整单 → **回读**（调整后金额真的生效）→ 判据拒绝路径 → 撤销 → 清理复原。

⛔ **不触发真抓取**：抓取会登录 i8 并**强踢在线用户**（D9）⇒ 只验它的**拒绝路径**
   （未确认 / 非单月格式），真抓由用户在确认的时段自己点。

用法：服务在跑（`127.0.0.1:8000`）⇒ `python tools/_e2e_m08_wired.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
REMARK = "m08自检（端到端）"
fails: list[str] = []


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("  ✅ " if ok else "  ⛔ ") + what + (f" —— {extra}" if extra else ""))
    if not ok:
        fails.append(what)


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    owner = c.get("/api/m08/inventory").json()

    print("① 读全量（`/api/m08/inventory`）")
    check(owner.get("count", 0) > 0, "返回了库存单据行", f"count={owner.get('count')}")
    rows = owner.get("rows") or []
    need = {"id", "doc_no", "seq", "direction", "material", "spec", "unit", "qty",
            "price_excl", "price_incl", "amount", "tax_total", "biz_type", "vendor",
            "doc_date", "audit_date", "warehouse", "wbs_name", "cbs_name",
            "c5", "adjusted"}
    miss = sorted(need - set(rows[0].keys())) if rows else ["（无行）"]
    check(not miss, "行字段齐（含 `c5` 材料类别 / `adjusted`）", f"缺 {miss}" if miss else "")
    # ⚠️ 后端金额一律出**字符串**（`numeric(18,2)` 的精度保护，与 `m05` 同款 —— 用 JSON number
    #    会在浮点上抖）。⇒ **转成数字是壳的适配层（`N0()`）的职责**；这条断言同时钉住"后端形态"
    #    与"谁负责转"，免得下次有人以为"后端该出 number"而把适配层的 `N0()` 删了。
    amt_ok = all(isinstance(r.get("amount"), str) or r.get("amount") is None for r in rows)
    check(amt_ok, "后端金额出**字符串**（精度保护）⇒ 转数字由**适配层**负责（⛔ 壳里求和不能直接吃它）",
          "若这里变了，请同步改 `adaptInv` 的 `N0()`" if not amt_ok else "")
    null_amt = sum(1 for r in rows if r.get("amount") is None)
    if null_amt:
        print(f"     ℹ️ 其中 {null_amt} 行金额为 NULL（i8 导出里的空值 ⇒ 壳侧兜成 0）")
    check(all(r.get("id") is not None for r in rows), "每行都有 `id`（打调整单的键）")

    # 挑一行没调整单的（跑完能干净复原）
    target = next((r for r in rows if not r.get("adjusted")), None)
    if target is None:
        print("  ⚠️ 所有行都已有调整单 ⇒ 跳过「打单 / 撤销」两段")
        return finish(c)

    rid, old_amt = int(target["id"]), float(target["amount"])
    new_amt = round(old_amt + 1.23, 2)
    print(f"（用行 id={rid} · {target['doc_no']} #{target['seq']} · i8 原值 {old_amt}）")

    print("② 打调整单（`POST /api/m08/adjust`）")
    r = c.post("/api/m08/adjust", json={"row_id": rid, "amount": f"{new_amt:.2f}", "remark": REMARK})
    check(r.status_code == 200, "打单成功", f"HTTP {r.status_code} {str(r.text)[:90]}")
    body = r.json() if r.status_code == 200 else {}
    check(abs(float(body.get("before_amount", -1)) - old_amt) < 0.005,
          "**改前值 = i8 原值**（留痕的 before 由后端出）", f"before={body.get('before_amount')}")
    check(abs(float(body.get("amount", -1)) - new_amt) < 0.005, "改后值 = 提交值")
    check(bool(body.get("operator")), "记了操作人（唯一出口 = identity）", f"operator={body.get('operator')}")

    print("③ 回读（**真落库了吗**，不是「看着对」）")
    again = c.get("/api/m08/inventory").json()
    row2 = next((x for x in again["rows"] if int(x["id"]) == rid), {})
    check(row2.get("adjusted") is True, "该行 `adjusted` 变 true")
    check(abs(float(row2.get("adj_amount") or -1) - new_amt) < 0.005,
          "行上的「调整后金额」= 调整单值", f"adj_amount={row2.get('adj_amount')}")
    adj = next((a for a in again["adjustments"] if int(a["row_id"]) == rid), None)
    check(adj is not None and adj.get("remark") == REMARK, "调整单在清单里且备注正确")
    check(bool(adj and adj.get("changed_at")), "带时间戳", f"at={(adj or {}).get('changed_at')}")

    print("④ 判据的拒绝路径（**都不许落库**）")
    r1 = c.post("/api/m08/adjust", json={"row_id": rid, "amount": f"{new_amt:.2f}", "remark": ""})
    check(r1.status_code == 400, "空备注 ⇒ 400", str(r1.text)[:80])
    r2 = c.post("/api/m08/adjust", json={"row_id": rid, "amount": "-1", "remark": "x"})
    check(r2.status_code == 400, "负金额 ⇒ 400", str(r2.text)[:80])
    after_reject = c.get("/api/m08/inventory").json()
    same = next((a for a in after_reject["adjustments"] if int(a["row_id"]) == rid), {})
    check(same.get("remark") == REMARK, "**被拒之后调整单没被动**（原备注还在）")

    print("⑤ 撤销调整单（`POST /api/m08/adjust/clear`）")
    r3 = c.post("/api/m08/adjust/clear", json={"row_id": rid})
    check(r3.status_code == 200, "撤销成功", f"HTTP {r3.status_code}")
    final = c.get("/api/m08/inventory").json()
    row3 = next((x for x in final["rows"] if int(x["id"]) == rid), {})
    check(row3.get("adjusted") is False, "该行回到「未调整」")
    check(not any(int(a["row_id"]) == rid for a in final["adjustments"]), "调整单已不在清单里")
    check(abs(float(row3.get("amount", -1)) - old_amt) < 0.005,
          "**原始数据未受影响**（i8 原值没动过）", f"amount={row3.get('amount')}")
    gone = row3.get("adj_amount")
    check(gone in (None, 0, 0.0), "调整后金额已消失（键不存在或 0）", f"adj_amount={gone!r}")

    return finish(c)


def finish(c: httpx.Client) -> int:
    print("⑥ 抓取端点 —— **只验拒绝路径**（⛔ 不真抓，避免顶号）")
    r1 = c.post("/api/m08/fetch", json={"month": "2026-09", "confirm": False})
    check(r1.status_code == 400, "未确认 ⇒ 400（防静默抓取）", str(r1.text)[:90])
    r2 = c.post("/api/m08/fetch", json={"month": "2026-9", "confirm": True})
    check(r2.status_code == 400, "月份格式非法 ⇒ 400", str(r2.text)[:80])

    print("⑦ 清理复核")
    left = [a for a in c.get("/api/m08/inventory").json()["adjustments"] if a.get("remark") == REMARK]
    check(not left, "没有遗留自检调整单")

    print()
    if fails:
        print(f"⛔ 未通过 {len(fails)} 项：")
        for f in fails:
            print("   ·", f)
        return 1
    print("✅ 全部通过（m08 真机端到端）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
