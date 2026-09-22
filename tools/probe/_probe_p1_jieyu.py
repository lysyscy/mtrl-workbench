# -*- coding: utf-8 -*-
"""片 1 取证：模板「结余」列的取数口是什么？（清单说"历史数据·有现成取数"，但代码里零命中）

判法：模板是用户手作的 **8 月** 成品 ⇒ 若「结余」= `setl_detail.end_amt` 按**提取规则命中**的
按月合计，则模板里的数应与库里某个月的 结存金额 合计逐分对上（或与"上月=7月"对上）。

同时取证：数据行集合 = 哪些项目（模板 7 行 vs 库里 在建 项目）。
"""
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, "backend")

import openpyxl

from app.core.db import session_scope
from app.mod07_setl import extract as X
from app.mod07_setl.repository import load_rows

TPL = Path("backend/app/resources/templates/模板-焊材气体.xlsx")


def read_template():
    wb = openpyxl.load_workbook(TPL)
    out = {}
    for sn in wb.sheetnames:
        ws = wb[sn]
        rows = []
        for r in range(2, 10):                     # 数据首行 R2 起、到合计行前
            rows.append((r, str(ws.cell(row=r, column=1).value or ""),
                         ws.cell(row=r, column=2).value))
        out[sn] = rows
    return out


def main():
    tpl = read_template()
    with session_scope() as s:
        rows = load_rows(s)
        print("setl_detail 行数 =", len(rows))
        yms = sorted({str(r["ym"]) for r in rows})
        print("库里的核算年月 =", yms)
        whs = sorted({str(r["warehouse"]) for r in rows})
        print("库里的仓库数 =", len(whs))

        # 项目档案
        from app.mod01_projects.domain import ordered, status_label
        from app.mod01_projects.repository import all_projects
        projs = ordered(all_projects(s))
        print("\n项目档案（%d 个，按 ordered 顺序）：" % len(projs))
        for i, p in enumerate(projs, 1):
            print("  %2d. %-24s status=%s" % (i, getattr(p, "warehouse_name", ""),
                                              status_label(p.status)))

        # 逐月 × 规则命中 ⇒ Σ 结存金额（end_amt）
        print("\n=== 按提取规则命中后 Σ end_amt（逐月 × 类别 × 仓库）===")
        for ym in yms:
            sub = [dict(r, ym=ym) for r in rows if str(r["ym"]) == ym]
            aggs = {}
            for kind in X.KINDS:
                for r in sub:
                    if not X.match_kind(str(r.get("resource_name") or ""), kind, X.default_rules()):
                        continue
                    wh = str(r.get("warehouse") or "")
                    key = (kind, wh)
                    aggs[key] = (aggs.get(key, Decimal("0.00")) + Decimal(str(r.get("end") or 0)))
            if not aggs:
                continue
            print("  --- %s ---" % ym)
            for kind in X.KINDS:
                print("    [%s]" % kind)
                for (k, wh), v in sorted(aggs.items()):
                    if k != kind:
                        continue
                    print("       %-24s %s" % (wh, v))

    print("\n=== 模板「结余」列 ===")
    for sn, rows in tpl.items():
        print("  [%s]" % sn)
        for r, label, val in rows:
            print("     R%d  %-22s 结余=%s" % (r, label or "(DATA_START)", val))


if __name__ == "__main__":
    main()
