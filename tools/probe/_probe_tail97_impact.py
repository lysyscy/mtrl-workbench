"""`TAIL-97` 迁移影响取证（**只读**，⛔ 不写任何一行）。

**为什么有它**：`TAIL-97` 要把存量「待确认」合同迁成「纳入台账」（设计件 §二）。
用户口径：**迁移前必须先把数字影响列给他看**（欠款 / 主材累计 / KPI 各变大多少）。
⛔ 不许"迁完再看"—— 那等于让用户事后才发现账变了。

**取数一律复用现场出口**（⛔ 不另写一套算钱的）：
  · 台账行 = `mod11_jc.service.build_list`（集采台账页同一个函数）
  · 三类欠款 = `mod05_flow.service.build_debt`（欠款页 / 看板同一个函数）
  · 主材累计 = `mod07_setl.domain.main_material_total`（大表同一个函数）

用法：`backend\\.venv\\Scripts\\python.exe tools\\probe\\_probe_tail97_impact.py`
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.db import session_scope                        # noqa: E402
from app.mod05_flow import service as M05                    # noqa: E402
from app.mod07_setl import big_domain as BIGD                # noqa: E402
from app.mod11_jc import service as M11                      # noqa: E402
from app.mod11_jc.models import TAG_IN, TAG_OUT             # noqa: E402

#: ⚠️ **历史值**：`TAIL-97` 已从 `models` 删除「待确认」⇒ 这里只能写死它
#:   （本件现在的作用 = **迁移后复核**：`待确认` 应恒为 0；迁移前它 258 条）。
LEGACY_PENDING = "待确认"

Z = Decimal("0.00")


def money(x) -> str:
    return f"{Decimal(str(x or 0)).quantize(Decimal('0.01')):,.2f}"


def bucket(rows, tag: str) -> dict:
    out = {"n": 0, "settle": Z, "pay": Z, "debt": Z, "settle_zero": 0}
    for r in rows:
        if str(r.get("tag") or "") != tag:
            continue
        out["n"] += 1
        st = Decimal(str(r.get("settle") or 0))
        out["settle"] += st
        out["pay"] += Decimal(str(r.get("pay_sum") or 0))
        out["debt"] += Decimal(str(r.get("debt") or 0))
        if st == 0:
            out["settle_zero"] += 1
    return out


def main() -> int:
    with session_scope() as s:
        data = M11.build_list(s)
        rows = data["rows"]
        # ⚠️ 2026-09-25（`TAIL-100` 修好后）：看板端点走的是 `build_debt_live`（＝ 注入集采欠款）
        #    ⇒ 本件**跟着改**，否则【三】会继续显示那个已经修掉的 0。
        home = M05.build_debt_live(s)
        projects = list(data.get("projects") or [])

    total = {"n": len(rows), "settle": Z, "pay": Z, "debt": Z}
    for r in rows:
        total["settle"] += Decimal(str(r.get("settle") or 0))
        total["pay"] += Decimal(str(r.get("pay_sum") or 0))
        total["debt"] += Decimal(str(r.get("debt") or 0))

    pend = bucket(rows, LEGACY_PENDING)
    into = bucket(rows, TAG_IN)
    out_ = bucket(rows, TAG_OUT)

    print("=" * 74)
    print("TAIL-97 迁移影响取证（只读）· 待确认 => 纳入台账")
    print("=" * 74)

    print("\n【一】合同按三态分布（集采台账全量）")
    print(f"  三态合计 {total['n']} 条 · Σ结算 {money(total['settle'])} · Σ付款 {money(total['pay'])} · Σ欠款 {money(total['debt'])}")
    for label, g in (("待确认", pend), ("纳入台账", into), ("不纳入", out_)):
        print(f"  {label:<6} {g['n']:>4} 条 · Σ结算 {money(g['settle']):>18} · "
              f"Σ付款 {money(g['pay']):>18} · Σ欠款 {money(g['debt']):>16}")

    print("\n【二】集采台账页 5 个 KPI（迁移前 => 迁移后）")
    print(f"  合同数（纳入台账）  {into['n']:>4} => {into['n'] + pend['n']:>4}   (+{pend['n']})")
    print(f"  Σ 结算金额          {money(into['settle']):>16} => {money(into['settle'] + pend['settle']):>16}   "
          f"(+{money(pend['settle'])})")
    print(f"  Σ 付款金额          {money(into['pay']):>16} => {money(into['pay'] + pend['pay']):>16}   "
          f"(+{money(pend['pay'])})")
    print(f"  集采欠款            {money(into['debt']):>16} => {money(into['debt'] + pend['debt']):>16}   "
          f"(+{money(pend['debt'])})")
    print(f"  待确认合同          {pend['n']:>4} =>    0   (-{pend['n']})")

    print("\n【三】看板 `/api/m05/debt`（⭐ 走生产那条路 `build_debt_live` ⇒ 集采那格已**真的注入**）")
    for c in home["by_category"]:
        print(f"  {c['label']:<4} {c['amount']:>18}   (category={c['category']})")
    print(f"  合计 {home['total']:>18}")
    print("  ⭐ `TAIL-100` 修好前：`jc_debt` 没人注入 ⇒ 这一格**恒 0.00**（总欠款少算 7444 万级）")

    print("\n【四】大表「主材累计（含税）」按项目（只计纳入台账 · 迁移后变大）")
    settled_wh = [str(r.get("project_key") or "") for r in rows]
    whs = sorted({w for w in settled_wh if w})
    hit = 0
    for wh in whs:
        before = BIGD.main_material_total(
            [{"project": r.get("project_key"), "in_ledger": str(r.get("tag") or "") == TAG_IN,
              "settle": r.get("settle")} for r in rows], project_key=wh)
        after = BIGD.main_material_total(
            [{"project": r.get("project_key"),
              "in_ledger": str(r.get("tag") or "") in (TAG_IN, LEGACY_PENDING),
              "settle": r.get("settle")} for r in rows], project_key=wh)
        if before != after:
            hit += 1
            print(f"  {wh:<28} {money(before):>16} => {money(after):>16}   (+{money(after - before)})")
    print(f"  ⇒ 受影响项目 {hit} / 有集采合同的项目 {len(whs)} 个")

    print("\n【五】迁移明细面")
    print(f"  待确认里「结算额为 0」的行 {pend['settle_zero']} / {pend['n']} 条"
          f" ⇒ 这些行迁过去**不改**任何金额（只改计数与标记）")
    print(f"  项目档案名册 {len(projects)} 个项目可选")
    print("\n（本脚本只读：⛔ 未写库。）")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
