#!/usr/bin/env python
"""**审计工具**：量出「收款账号 / 收款银行」在**标准字段 vs i8 自定义字段**之间的差异面。

## 为什么有它（`TAIL-60` 的取证工具）

2026-09-21 用户报障：打印件收款账号为空（`FKTZS2026050366`）。
⭐ 根因：`print/fields.py` 取 i8 明细的**标准字段**（`RecAccNo` / `PhidBank_EXName`），
   而 **i8 原生打印取的是自定义字段**（`user_yhzh` / `user_bank_EXName` —— 模板格里就叫这个名字）。
   两套在多数单上同值 ⇒ 不一致的那批就**印空**或**印错值**。

本工具逐张调 i8 `getDetInfo`（只读）把它们找出来。实测（2026-09-21 · 全量 355 张）：
**74 / 353 张受影响（21.0%）**，其中 **11 张印错值**（比空更坏）、63 张印空；
⭐ **反向 0 例**（标准有值而自定义为空）⇒ `user_*` 是标准字段的**超集**。

## ⚠️ 跑它的代价

它会**登录 i8**（`allow_kick=True` ⇒ **可能顶掉你正在用的 i8 会话**）——
⛔ 别放进自动跑批；⭐ 只在"要重新量一次影响面"或"改完要复核"时手动跑。
判据本身**不依赖它**：固定形态（自定义与标准不同值）落成 `tests/` 的 fixture。

用法：`backend\\.venv\\Scripts\\python.exe tools\\_probe_i8_acct.py`（结果写 `artifacts/_probe_acct_scan.json`）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from app.core.db import session_scope                       # noqa: E402
from app.mod02_i8.client import I8Client                    # noqa: E402
from app.mod02_i8.notice_source import NoticeDetailFetcher  # noqa: E402
from app.mod03_notice.models import PaymentNotice           # noqa: E402
from sqlalchemy import select                               # noqa: E402

OUT = ROOT / "data/reference/i8-account-probe" / "_probe_acct_scan.json"


def main() -> int:
    with session_scope() as s:
        rows = list(s.execute(select(PaymentNotice).order_by(PaymentNotice.doc_date)).scalars())
    print(f"全量 {len(rows)} 张 —— 逐张取明细（只读；⚠️ 允许顶号）\n")
    res: list[dict] = []
    cli = I8Client(allow_kick=True)
    try:
        fetcher = NoticeDetailFetcher(cli)
        for i, r in enumerate(rows, 1):
            rec = {"bill_no": r.bill_no, "ph_id": r.ph_id, "doc_date": str(r.doc_date)}
            try:
                detail = fetcher.fetch_detail(r.ph_id)
                rec["rows"] = len(detail)
                if detail:
                    d0 = detail[0]
                    rec["std_acc"] = str(d0.get("RecAccNo") or "")
                    rec["usr_acc"] = str(d0.get("user_yhzh") or "")
                    rec["std_bank"] = str(d0.get("PhidBank_EXName") or "")
                    rec["usr_bank"] = str(d0.get("user_bank_EXName") or "")
            except Exception as exc:                                # noqa: BLE001
                rec["error"] = f"{type(exc).__name__}: {exc}"
            res.append(rec)
            if i % 50 == 0:
                print(f"  ... {i}/{len(rows)}")
    finally:
        cli.close()
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = [x for x in res if "error" not in x and x.get("rows")]
    zero = [x for x in res if "error" not in x and not x.get("rows")]
    wrong = [x for x in ok if x.get("std_acc") and x.get("usr_acc") and x["std_acc"] != x["usr_acc"]]
    blank = [x for x in ok if x.get("usr_acc") and not x.get("std_acc")]
    rev = [x for x in ok if x.get("std_acc") and not x.get("usr_acc")]
    print(f"\n有效 {len(ok)} 张 · 明细 0 行 {len(zero)} 张")
    print(f"  ❌❌ 印错值 {len(wrong)} 张 → {[x['bill_no'] for x in wrong]}")
    print(f"  ❌ 印空 {len(blank)} 张")
    print(f"  ⚠️ 反向 {len(rev)} 张（⛔ 不为 0 就不能简单改成只读自定义字段）")
    print(f"  ⇒ 合计受影响 {len(wrong) + len(blank)} / {len(ok)} 张")
    print(f"\n原始证据 → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
