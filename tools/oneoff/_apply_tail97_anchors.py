"""`TAIL-97` 一次性补丁（第五片）：**链路锚**与交付面剩下几处**集采口径**的「三态」。

**为什么必须改**（`chain_audit` 的 `C2` 就是这么红的）：
  认领表 `tools/chain_expected.txt` 的**文档锚** = 「真源里的一段原文」；
  我把《说明书》§6.5.3 的标题从「三态标记」改成「两态标记」⇒ 锚**找不到** ⇒ `C2` 报红
  —— ⭐ **这正是 `C2` 存在的意义**（"文档改了"的哨），不是它误报。

⚠️ **只改「集采纳入」这个口径的「三态」**；交付面其余「三态」是**另一个概念**（`R8` 的
  「只读 / 可改 / 已手改」· 表头排序三态 · 旧资产的「三态同步」· 素材包里**已作废口径**）⇒ ⛔ 一律不动。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail97_anchors.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail97_anchors.py --apply`  # 真写
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FACE = Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
CHAIN_EXP = ROOT / "tools" / "chain_expected.txt"
CHAIN_SRC = ROOT / "tools" / "chain_sources.txt"
TECH = FACE / "技术栈选型分析.md"
RULES = FACE / "demo" / "设计规则-提炼自付款通知书页.md"
BACKUPS = ROOT / ".workbuddy" / "backups"

PLAN: dict[Path, list[tuple[str, str, str]]] = {
    CHAIN_EXP: [
        ("J 节标题注释：三态 ⇒ 两态",
         "# ⑧ J 集采域：抓合同 → 三态 → 发票/付款子表 → 结算欠款 → 台账（真源 = 说明书 §6.2）",
         "# ⑧ J 集采域：抓合同 → 两态 → 发票/付款子表 → 结算欠款 → 台账（真源 = 说明书 §6.2）"),
        ("整条链路那一行的分支名",
         "J|集采域**整条链路**（抓合同 → 三态 → 发票/付款子表 → 结算欠款 → 台账）|",
         "J|集采域**整条链路**（抓合同 → 两态 → 发票/付款子表 → 结算欠款 → 台账）|"),
        ("⭐ **`C2` 报红的那一行**：文档锚「三态标记」⇒「两态标记」（说明书 §6.5.3 标题已改）",
         "J|抓采购合同（`API-04` · **仅人工点击**）|三态标记|",
         "J|抓采购合同（`API-04` · **仅人工点击**）|两态标记|"),
        ("集采台账标记那一行的分支名",
         "J|集采台账**三态标记**（信息化抓取）|集采台账|",
         "J|集采台账**两态标记**（信息化抓取）|集采台账|"),
    ],
    CHAIN_SRC: [
        ("真源注册表的 J 注释",
         "# ⑧ 集采域：抓合同 → 三态 → 发票/付款子表 → 结算欠款 → 台账（真源 = 说明书 §6.2）",
         "# ⑧ 集采域：抓合同 → 两态 → 发票/付款子表 → 结算欠款 → 台账（真源 = 说明书 §6.2）"),
    ],
    TECH: [
        ("能力 C2「必须满足」②：批量标记三态 ⇒ 两态（§6.5.3 已改名）",
         "② 批量操作（批量改分类 §4.2.4、批量标记三态 §6.5.3）",
         "② 批量操作（批量改分类 §4.2.4、批量标记两态 §6.5.3）"),
    ],
    RULES: [
        ("MOD-11 规则条 ③：三态标记 ⇒ 两态标记",
         "③ 三态标记：**逐条**标记 + **批量标记**，且**默认 = 「纳入台账」**",
         "③ 两态标记（抓来即「纳入台账」，可人工改「不纳入」）：**逐条**标记 + **批量标记**，且**默认 = 「纳入台账」**"),
        ("MOD-11 自检条：三态标记 ⇒ 两态标记；操作列按钮改成两态互切",
         "「**三态标记**」**默认 = 「纳入台账」**（比**加载时快照**，不比运行时现值）；**存档号 / 寄回日期 / 备注三列可手改**（走动作进去断言落值，且**三个动作都在 `CHG`**）；操作列按钮名 = 「**是否纳入台账**」且**不再有「改标记」**",
         "「**两态标记**」**默认 = 「纳入台账」**（比**加载时快照**，不比运行时现值）；**存档号 / 寄回日期 / 备注三列可手改**（走动作进去断言落值，且**三个动作都在 `CHG`**）；操作列按钮 = **两态互切**（「纳入台账」/「不纳入」）且**不再有「是否纳入台账」「改标记」**"),
        ("配置层枚举清单：集采纳入三态 ⇒ 两态",
         "· 集采纳入三态 · 集采存档情况 ·",
         "· 集采纳入两态 · 集采存档情况 ·"),
    ],
}


def main() -> int:
    apply = "--apply" in sys.argv
    errors: list[str] = []
    todo: list[tuple[Path, str, bool]] = []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for path, items in PLAN.items():
        raw = path.read_bytes()
        crlf = b"\r\n" in raw
        text = raw.decode("utf-8").replace("\r\n", "\n")
        back = text.replace("\n", "\r\n") if crlf else text
        if back.encode("utf-8") != raw:
            errors.append(f"{path.name}｜行尾 round-trip 不一致")
            continue
        for desc, old, new in items:
            n = text.count(old)
            if n != 1:
                errors.append(f"{path.name}｜{desc} —— 命中 {n} 次（期望 1）")
                continue
            text = text.replace(old, new, 1)
        todo.append((path, text.replace("\n", "\r\n") if crlf else text, crlf))

    print("=" * 80)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + " ·  TAIL-97 链路锚 ＋ 交付面剩余口径")
    print("=" * 80)
    for path, _t, crlf in todo:
        print(f"  {path.name:<40} 替换 {len(PLAN[path])} 条 · 行尾={'CRLF' if crlf else 'LF'}")
    if errors:
        print("\n⛔ 有锚点对不上 ⇒ **一个字节都没写**：")
        for e in errors:
            print("   " + e)
        return 1
    if not apply:
        print("\n  （加 --apply 才真写。）")
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    for path, text, _c in todo:
        if FACE in path.parents:                      # 交付面 ⇒ 先备份到**仓侧**
            shutil.copy2(path, BACKUPS / f"face-{stamp}-{path.name}")
        path.write_bytes(text.encode("utf-8"))
    print("\n  ✅ 已写盘（交付面 2 件已备份到 .workbuddy/backups/）。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
