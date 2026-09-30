"""一次性件（`TAIL-100` · 2026-09-25）：把两份活文档里的**判据点计数** 559 ⇒ **560** 同步。

⭐ 依据 `§22.1`：四态那个字符串在**两份文档里共 3 处 ＋ `§22.2` 表 1 处** —— 「改数字时**一起改**」；
   规范串由 `python tools/audit/doc_audit.py --block` 给出（本次 = `560 = 绿 560 · 红 0 · 待建 0 · 未绑定 0`）。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_bump_judge_count.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_bump_judge_count.py --apply`  # 真写
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
HAND = ROOT / ".workbuddy" / "plans" / "执行情况-主文档.md"

PLAN_EDITS = [
    ("§0.2 判据计数",
     "**559 = 绿 559 · 红 0 · 待建   0 · 未绑定    0**（⭐ **判据线 100% 全绿**；⭐ 2026-09-24 涨 1 = "
     "`ACC-PAY-VERIFY-001` 补 `001-06`「集采未关联不可付」—— **是加判据**、⛔ 不是改判据）。",
     "**560 = 绿 560 · 红 0 · 待建   0 · 未绑定    0**（⭐ **判据线 100% 全绿**；⭐ 2026-09-24 涨 1 = "
     "`ACC-PAY-VERIFY-001` 补 `001-06`「集采未关联不可付」；⭐ **2026-09-25 涨 1** = `ACC-FLOW-DEBT-001` 补 "
     "`001-07`「集采欠款的**注入方真的存在**」（`TAIL-100`）—— **都是加判据**、⛔ 不是改判据）。"),
    ("§22.1 四态基线",
     "- ⭐ **四态零丢失的基线（2026-09-25）：557 = 绿 559 · 红 0 · 待建 0 · 未绑定 0**。",
     "- ⭐ **四态零丢失的基线（2026-09-25）：560 = 绿 560 · 红 0 · 待建 0 · 未绑定 0**"
     "（⭐ 2026-09-25 又涨 1：`ACC-FLOW-DEBT-001` 补 `001-07` —— **还是加判据**）。"),
    ("§22.2 尺子表",
     "| ⭐ **559 = 绿 559 · 红 0 · 待建 0 · 未绑定 0**（2026-09-24） |",
     "| ⭐ **560 = 绿 560 · 红 0 · 待建 0 · 未绑定 0**（2026-09-25） |"),
]

HAND_EDITS = [
    ("顶部判据总账",
     "**559 = 绿 559 · 红 0 · 待建 0 · 未绑定 0**（⭐ 判据线 100% 全绿 —— 2026-09-23 涨 1 ＋ ⭐ **2026-09-24 涨 1**，"
     "两次都是**加判据**不是改判据，见 ③ C；最近这次 = `ACC-PAY-VERIFY-001` 补 `001-06`「集采未关联不可付」）",
     "**560 = 绿 560 · 红 0 · 待建 0 · 未绑定 0**（⭐ 判据线 100% 全绿 —— 2026-09-23 涨 1 ＋ 2026-09-24 涨 1 ＋ "
     "⭐ **2026-09-25 涨 1**，三次都是**加判据**不是改判据，见 ③ C；最近这次 = `ACC-FLOW-DEBT-001` 补 `001-07`"
     "「集采欠款的**注入方真的存在**」）"),
]


def patch(path: Path, items: list[tuple[str, str, str]], errors: list[str]) -> str | None:
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if (text.replace("\n", "\r\n") if crlf else text).encode("utf-8") != raw:
        errors.append(f"{path.name}：行尾 round-trip 不一致")
        return None
    for desc, old, new in items:
        n = text.count(old)
        if n != 1:
            errors.append(f"{path.name}｜{desc} —— 命中 {n} 次（期望 1）")
            continue
        text = text.replace(old, new, 1)
    return text.replace("\n", "\r\n") if crlf else text


def main() -> int:
    apply = "--apply" in sys.argv
    errors: list[str] = []
    a = patch(PLAN, PLAN_EDITS, errors)
    b = patch(HAND, HAND_EDITS, errors)
    print("=" * 78)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + " ·  判据点计数 559 ⇒ 560（T4 的四处锚）")
    print("=" * 78)
    print(f"  开发计划-主文档.md 替换 {len(PLAN_EDITS)} 处 · 执行情况-主文档.md 替换 {len(HAND_EDITS)} 处")
    if errors:
        print("\n⛔ 有锚点对不上 ⇒ **一个字节都没写**：")
        for e in errors:
            print("   " + e)
        return 1
    if not apply:
        print("\n  （加 --apply 才真写。）")
        return 0
    assert a is not None and b is not None
    PLAN.write_bytes(a.encode("utf-8"))
    HAND.write_bytes(b.encode("utf-8"))
    print("\n  ✅ 已写盘。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
