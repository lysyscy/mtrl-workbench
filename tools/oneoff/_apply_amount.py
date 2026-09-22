#!/usr/bin/env python
"""`TAIL-63`：把「**金额文本洗净**」收进 `app/core/money.py`（金额口径的**唯一出口**）。

⛔ 只抽**洗净**，⛔ 不碰**判定**：4 处 `parse_amount` 的业务判定是**刻意不同**的
   （`MOD-03` 空 ⇒ None＝未手改 · `MOD-05` 空 ⇒ 报错且必须 >0 · `MOD-09` 空 ⇒ 0 且**允许负数** ·
   `MOD-11` 空 ⇒ 报错且必须 >0），两边注释都写着「别把两套搅在一起」⇒ 判定留在各自模块。

⭐ 本轮修掉一个**实测到的实害**（母本 `artifacts/golden/_golden_amount_before.json`）：
   同一个 `¥ 1,234.56`，`mod05`/`mod09`/`mod11` 都能过，**`mod03` 报「金额格式非法」**
   （它那份只去逗号、不去 `¥`/中间空格）⇒ 用户在付款通知书里手填带 ¥ 的数会被拒。
"""
from __future__ import annotations

import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
BAK = ROOT / ".workbuddy" / "scratch"
BAK.mkdir(parents=True, exist_ok=True)

MONEY = ROOT / "backend" / "app" / "core" / "money.py"
ADD = '''
#: ⭐ `TAIL-63`（2026-09-21）：金额文本里一律清掉的字符（千分位 / 货币符号 / 空白）。
#: ⛔ 加字符必须同步改 `tests/test_amount_text_parity.py` 的判据（否则口径改了没人知道）。
_AMOUNT_NOISE: tuple[str, ...] = (",", "，", "¥", "￥", "$", " ", "\\u3000")


def amount_text(raw: object) -> str:
    """**金额文本的洗净**（`TAIL-63` 唯一出口）：千分位 / 货币符号 / 空白全去掉；空 ⇒ `''`。

    ⭐ 为什么必须有这一个主人（2026-09-21 **实测到的实害**）：这段原先在 4 个 `parse_amount`
      （`mod03_notice` / `mod05_flow` / `mod09_fee` / `mod11_jc`）里**各写一份，且写得不一样**
      ⇒ 同一个 `¥ 1,234.56`：集采台账 / 特殊费用 / 付款流水都能过，
      **付款通知书手填却报「金额格式非法」**（它那份只去逗号）⇒ 用户在**同一张表单**里
      手填带 ¥ 的数会被拒 —— 这正是「同一口径 N 个主人」的实害（与当天"收款账号取错字段"同型）。

    ⛔ 本函数**只管洗净**，⛔ **不做任何业务判定**：
      那 4 处的判定是**刻意不同**的（`MOD-09` 允许 0 与负数、`MOD-11` 必须 > 0，
      两边注释都写着「别把两套搅在一起」）⇒ 判定**留在各自 `parse_amount`**，本轮一个都不改。
    """
    text = str(raw if raw is not None else "")
    for ch in _AMOUNT_NOISE:
        text = text.replace(ch, "")
    return text.strip()
'''

t = MONEY.read_text(encoding="utf-8")
if "def amount_text" not in t:
    shutil.copy2(MONEY, BAK / "money.py.bak-amount")
    anchor = "def _reject_bool(value: object) -> None:"
    MONEY.write_text(t.replace(anchor, ADD.strip("\n") + "\n\n\n" + anchor, 1), encoding="utf-8", newline="")
    print("✅ money.py: 新增 `amount_text()`")

EDITS: list[tuple[str, str, str]] = [
    ("mod03_notice/notice_pay_actions.py",
     '    raw = str(text or "").strip().replace(",", "")\n    return to_money(raw) if raw else None',
     '    raw = amount_text(text)          # ⭐ `TAIL-63`：洗净归到 `app/core/money.py`（原来只去逗号 ⇒ 带 ¥ 会被拒）\n'
     '    return to_money(raw) if raw else None'),
    ("mod05_flow/importer.py",
     '        raw = raw.strip().replace(",", "").replace("¥", "").replace("￥", "").replace(" ", "")',
     '        raw = amount_text(raw)'),
    ("mod09_fee/domain.py",
     '    text = str(raw if raw is not None else "").strip().replace(",", "").replace("¥", "").replace("￥", "")',
     '    text = amount_text(raw)'),
    ("mod11_jc/domain.py",
     '    text = str(raw if raw is not None else "").strip().replace(",", "").replace("¥", "").replace("￥", "")',
     '    text = amount_text(raw)'),
]

IMPORTS = {
    "mod03_notice/notice_pay_actions.py": "from app.core.money import amount_text, to_money",
    "mod05_flow/importer.py": "from app.core.money import amount_text",
    "mod09_fee/domain.py": "from app.core.money import amount_text",
    "mod11_jc/domain.py": "from app.core.money import amount_text",
}

for rel, old, new in EDITS:
    p = ROOT / "backend" / "app" / rel
    t = p.read_text(encoding="utf-8")
    if old not in t:
        print(f"⚠️  {rel}: 找不到锚点")
        continue
    shutil.copy2(p, BAK / (p.name + ".bak-amount"))
    p.write_text(t.replace(old, new, 1), encoding="utf-8", newline="")
    print(f"✅ {rel}: 洗净改用 `amount_text`")

for rel, new_imp in IMPORTS.items():
    p = ROOT / "backend" / "app" / rel
    t = p.read_text(encoding="utf-8")
    lines = t.split("\n")
    if new_imp in t:
        continue
    # 找 `from app.core.money import ...` 就地扩；否则插到最后一条 import 之后
    hit = next((k for k, l in enumerate(lines) if l.startswith("from app.core.money import")), None)
    if hit is not None:
        lines[hit] = new_imp + "  # noqa: F401" if False else new_imp
    else:
        last = max(k for k, l in enumerate(lines) if l.startswith(("import ", "from ")))
        lines.insert(last + 1, new_imp)
    p.write_text("\n".join(lines), encoding="utf-8", newline="")
    print(f"➕ {rel}: 导入 `{new_imp}`")
print("完成 · 备份在 .workbuddy/scratch/*.bak-amount")
