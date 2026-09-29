"""M8 开场两处笔误的修正（2026-09-29）—— 都是**我自己刚写进去**的：

1. ⛔ **阶段列写成带反引号的 `` `M8` ``** ⇒ `T6` 判「不是受控词」红 —— 受控词要求**以受控词开头**（`` `M8` `` 以反引号开头 ✗）。
2. ⛔ **引用还没建的文件**（`ops/pack.ps1` / `ops/deploy_restore.ps1` / `ops/selfcheck.ps1` / `docs/部署-落地说明.md`）
   ⇒ `T3`（幽灵路径）判红 **6 处**。⭐ **守卫是对的** —— 那三脚本 ＋ 一页说明是本批**下一轮**才建的；
   台账里就不该出现**尚不存在的路径**。⇒ 写法改成**描述**（「打包 / 落地还原 / 自检三脚本（下一批新增）」）✓。

⚠️ 教训（可复用）：**"登记计划要做的文件"别把路径写进台账** —— 台账是被 `T3` 逐字扫的；
  写到"将新建"的东西，写成**描述**、等**建出来那一批**再把路径补进去。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_m8_fix1.py --check` / `--write`
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

EDITS: list[tuple[str, str]] = [
    # ① §15 §一 那行：脚本路径 → 描述
    ("`ops/pack.ps1` / `deploy_restore.ps1` / `selfcheck.ps1` / `docs/部署-落地说明.md` ＋ **路径可配置改造**",
     "**打包 / 落地还原 / 自检三脚本 ＋ 一页落地说明（下一批新增）** ＋ **路径可配置改造**"),
    # ② §15 §一 那行：阶段列去掉反引号（受控词必须**以受控词开头**）
    ("| `work/10-designs/设计-交付包与迁移-20260929.md` | `M8` | 待做 |",
     "| `work/10-designs/设计-交付包与迁移-20260929.md` | M8 | 待做 |"),
    # ③ §14.3 那行：同上
    ("（＋ `ops/pack.ps1` / `ops/deploy_restore.ps1` / `ops/selfcheck.ps1` / `docs/部署-落地说明.md`） |",
     "（＋ 下一批新增：打包 / 落地还原 / 自检三脚本 ＋ 一页落地说明） |"),
    # ④ §5.5：自检那条
    ("④ **交接口径与自检命令**（= `docs/部署-落地说明.md` ＋ `ops/selfcheck.ps1`）",
     "④ **交接口径与自检命令**（= 一页落地说明 ＋ 自检脚本，下一批新增）"),
    # ⑤ §5.5：落地那条
    ("落地 = `ops/deploy_restore.ps1`", "落地 = 还原脚本（下一批新增）"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    apply = a.write and not a.check

    raw = PLAN.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")          # ⚠️ 锚点按 `\n` 写（计划是 CRLF）
    for i, (old, new) in enumerate(EDITS, 1):
        n = text.count(old)
        print(f"  {'✓' if n == 1 else '⛔'} #{i} 命中 {n} 处（要 1）：{old[:44]}…")
        if n != 1:
            print("     ⛔ 锚点对不上 ⇒ 整批停手")
            return 2
        text = text.replace(old, new, 1)
    if apply:
        PLAN.write_text(text.replace("\n", eol), encoding="utf-8", newline="")
        print(f"\n🔧 已落盘：计划 {len(text.splitlines())} 行")
    else:
        print("\n🧪 --check（干跑）")
    print("   复核要点：`doc_audit` 必须修 0（含 `T6` 受控词）· `audit_drift` 必须修 0（`T3` 幽灵路径 6 → 0）· 其余全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
