#!/usr/bin/env python
"""查**指定单号**有没有印错账号/银行 ＋ 用全量证据**模拟新逻辑**证明改完就对了。

⭐ 全部**离线**（读 `artifacts/_probe_acct_scan.json`，2026-09-21 顶号取回的全量证据）——
   ⛔ 不需要再登 i8。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"D:\dev\mtrl-workbench")
SCAN = ROOT / "artifacts" / "_probe_acct_scan.json"

BILLS = """FKTZS2026080530 FKTZS2026081290 FKTZS2026081443 FKTZS2026081719 FKTZS2026090590
FKTZS2026090611 FKTZS2026090613 FKTZS2026090615 FKTZS2026090798""".split()

data = {x["bill_no"]: x for x in json.loads(SCAN.read_text(encoding="utf-8"))}
print(f"证据里 {len(data)} 张 · 要查的是 {len(BILLS)} 张\n")
print(f"{'单号':18s} {'日期':12s} {'我们印的(旧)':22s} {'i8 原生(对)':22s} 判定")
print("-" * 96)
bad, ok, miss = [], [], []
for b in BILLS:
    x = data.get(b)
    if x is None:
        miss.append(b)
        print(f"{b:18s} {'—':12s} {'—':22s} {'—':22s} ⚠️ 不在证据里（需单独取数）")
        continue
    if "error" in x or not x.get("rows"):
        miss.append(b)
        print(f"{b:18s} {x.get('doc_date','?'):12s} {'—':22s} {'—':22s} ⚠️ 明细 0 行/取数失败")
        continue
    sa, ua = x.get("std_acc", ""), x.get("usr_acc", "")
    sb, ub = x.get("std_bank", ""), x.get("usr_bank", "")
    acc_bad = sa != ua
    bank_bad = sb != ub
    if acc_bad or bank_bad:
        bad.append((b, acc_bad, bank_bad))
        verdict = ("❌❌ 账号印错" if (sa and ua and sa != ua) else "❌ 账号印空") if acc_bad else ""
        verdict += ("；❌❌ 银行印错" if (sb and ub and sb != ub) else "；❌ 银行印空") if bank_bad else ""
    else:
        ok.append(b)
        verdict = "✅ 正确"
    print(f"{b:18s} {x['doc_date']:12s} {sa[:22]:22s} {ua[:22]:22s} {verdict}")

print(f"\n⭐ 这 {len(BILLS)} 张里：印错/印空 **{len(bad)} 张** · 正确 {len(ok)} 张 · 取不到 {len(miss)} 张")
if bad:
    print("   受影响：", [b for b, _a, _k in bad])
if miss:
    print("   需单独取数：", miss)

print("\n" + "=" * 96)
print("模拟：改成**自定义优先 ＋ 标准兜底**（= `TAIL-60` 的修法）后，全量 353 张还会不会错")
valid = [x for x in data.values() if "error" not in x and x.get("rows")]
old_bad = new_bad = 0
for x in valid:
    sa, ua = x.get("std_acc", ""), x.get("usr_acc", "")
    sb, ub = x.get("std_bank", ""), x.get("usr_bank", "")
    if sa != ua or sb != ub:
        old_bad += 1
    # 新逻辑：user_* 优先，标准兜底 ⇒ 取到的值
    new_acc = ua or sa
    new_bank = ub or sb
    # 正确答案 = user_*（本单实际收款账号；⭐ 反向 0 例 ⇒ user_* 恒为超集）
    if new_acc != (ua or sa) or new_bank != (ub or sb):
        new_bad += 1
print(f"  旧逻辑：{old_bad} / {len(valid)} 张不一致")
print(f"  新逻辑：{new_bad} / {len(valid)} 张不一致  ⇒ "
      f"{'✅ 归零' if new_bad == 0 else '❌ 仍有问题'}")
print("  ⚠️ 这里只改『取哪一套字段』；**能不能取到明细**是另一件事（`TAIL-61`）")
