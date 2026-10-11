"""收口 ②（契约面）第一步：交付面**封存快照** —— 只收**本会话动过的交付面文件**。

## 为什么只收"动过的"

交付面是**仓外的 WPS 云同步树**（根 `README.md:153`：⛔ 别在交付面建新文件）⇒ 既有惯例 = 每次动交付面前
把**将改/已改的那几个文件**拷进 `.workbuddy/backups/交付面-<YYYYMMDD>-<HHMM>[-<批次>]/`（见 09-29 那 16 个）。
⇒ 本步不是"整面镜像"，是**给本会话的改动留一份可核的"改前/改后"**。

## 本会话动过的交付面文件（据各批台账 ＋ 本次复核）

| 文件 | 动因 |
|---|---|
| `PRD/验收/验收基线.json` | 各批新增/改 claim（`001-55`…`001-63` ＋ `ACC-INV-001/001-12` 改词） |
| `PRD/验收/用例索引.md` | 各批登记行 ＋ ⚠️ **2026-09-29 收口期我又改了一处**（`ACC-INV-001` 行尾补「**不在本次交付**」—— 修 `_links` 交付断点）。⚠️ **那一次我没先备份**（仓规是"动交付面先备份"）⇒ 本步**补上出处**：改前态在 `交付面-20260929-1247-A9b/PRD/验收/用例索引.md` ✓ |
| `MOD-0x` ×5 | `TAIL-168`（`交付面-20260929-083727-TAIL168/` 已有快照 ✓） |

## 同时按**新口径**收份数

新补的口径（`README.md §四`）：「一天多批 ⇒ **同一轮工作只保留当日末个快照**」⇒ 本步快照 = 当日末个；
顶层**仍守 5 份**（`T20`）⇒ 多出来的把**最旧的移进** `_旧快照归档-20260929/`（⛔ 不删）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_d5_face_seq.py --write`
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BK = ROOT / ".workbuddy" / "backups"
ARCH = BK / "_旧快照归档-20260929"
FACE = Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
KEEP = 5
FILES = ["PRD/验收/用例索引.md", "PRD/验收/验收基线.json"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    apply = a.write and not a.check

    tag = f"交付面-{time.strftime('%Y%m%d-%H%M')}-收口"
    out = BK / tag
    print(f"② 交付面封存快照 ⇒ `{out.name}/`")
    for rel in FILES:
        src = FACE / rel
        print(f"   {'✓' if src.exists() else '⛔'} {rel}  {src.stat().st_size if src.exists() else 0} B")
        if not src.exists():
            print("   ⛔ 源不在 ⇒ 停手（交付面路径变了？）")
            return 2
    if not apply:
        print("   🧪 干跑：会拷这 2 个文件 ＋ 写 README.txt ＋ 顶层超 5 份时把最旧的移进归档")
        return 0

    out.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FACE / rel, dst)
    (out / "README.txt").write_text(
        f"# 交付面封存快照 · {tag}\n\n"
        "> 依据：收口 ②（契约面）—— 只收**本会话动过的交付面文件**（⛔ 不是整面镜像）。\n"
        "> ⚠️ `用例索引.md` 在 2026-09-29 收口期又改过一处（`ACC-INV-001` 行尾补「不在本次交付」"
        "以修 `_links` 交付断点），**改前态**在 `交付面-20260929-1247-A9b/PRD/验收/用例索引.md`。\n"
        "> ⭐ 本份 = 当日末个（新口径：一天多批只留当日末个）。\n",
        encoding="utf-8", newline="")
    print(f"   ✅ 拷入 {len(FILES)} 个文件 ＋ README.txt")

    dirs = sorted([d for d in BK.iterdir() if d.is_dir() and not d.name.startswith("_")],
                  key=lambda p: p.stat().st_mtime, reverse=True)
    for d in dirs[KEEP:]:
        ARCH.mkdir(exist_ok=True)
        shutil.move(str(d), str(ARCH / d.name))
        print(f"   ↪ 顶层超 {KEEP} 份 ⇒ 最旧的 `{d.name}` 移进 `{ARCH.name}/`（⛔ 未删）")
    print(f"   现顶层 {len([d for d in BK.iterdir() if d.is_dir() and not d.name.startswith('_')])} 份")
    return 0


if __name__ == "__main__":
    sys.exit(main())
