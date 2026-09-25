"""`TAIL-97` 一次性补丁（第三片）：**契约面同批** —— 《说明书》· `MOD-11.md` · `验收基线.json`。

**为什么必须同批**（设计件 §四 / 交接材料「已确认限制」）：契约面分批 ⇒ `T4`/`T7a`/`T7b` 必红。

**三条纪律**：
  ① ⛔ **`.json` 走结构操作**（`json.loads` → 改 dict → `json.dumps`），**绝不用文本替换**；
     ⭐ 且**先做 round-trip 逐字节比对**确认序列化参数（已实测：`indent=1` · `ensure_ascii=False` · **CRLF** · 末尾一个 CRLF）；
  ② 每条替换**先断言旧值在位**（⛔ 不猜），对不上就**整批一行都不写**；
  ③ 改前**备份**到**仓侧** `.workbuddy/backups/`（⛔ 不在交付面建文件 —— 那是 WPS 云同步树）。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail97_contract.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail97_contract.py --apply`  # 真写
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FACE = Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
DOC = FACE / "材料科业务全流程说明书.md"
MOD11 = FACE / "PRD" / "02-功能规格" / "MOD-11.md"
BASE = FACE / "PRD" / "验收" / "验收基线.json"
BACKUPS = ROOT / ".workbuddy" / "backups"

# ────────────────────────────────────── 《说明书》：三态 ⇒ 两态（逐条断言命中 1 次）
DOC_EDITS: list[tuple[str, str, str]] = [
    ("第 6 章定位",
     "> **本章定位：** 集采合同抓取与三态标记 · 台账",
     "> **本章定位：** 集采合同抓取与两态标记 · 台账"),
    ("§6.1.2 范围表",
     "| 从 i8 抓取合同数据 + 三态标记 |",
     "| 从 i8 抓取合同数据 + 两态标记 |"),
    ("§6.4.1 字段表「纳入状态」",
     "**三态：待确认 / 纳入台账 / 不纳入**；新抓取默认「待确认」；**人工标记不被抓取覆盖**（见 §6.5.3）",
     "**两态：纳入台账 / 不纳入**；⭐ **抓来即「纳入台账」**（系统默认值）；**人工标记不被抓取覆盖**（见 §6.5.3）"),
    ("§6.5 小节标题",
     "### 6.5 场景一：信息化抓取与三态标记",
     "### 6.5 场景一：信息化抓取与两态标记"),
    ("§6.5.3 正文（状态表 ＋ 三条规则）",
     "#### 6.5.3 三态标记\n"
     "\n"
     "| 状态 | 含义 |\n"
     "|---|---|\n"
     "| **纳入台账** | 这份合同要管 |\n"
     "| **不纳入** | 废数据 / 与本域无关（**人工标记**） |\n"
     "| **待确认** | 新抓取的数据**默认**状态 |\n"
     "\n"
     "**关键规则：**\n"
     "\n"
     "- 支持**批量标记**：**范围 = 当前筛选结果**；**未勾选时批量按钮先禁用**（不是点了才拦）；动作完成后**清空勾选**；筛选条件变化时**裁剪不可见的勾选**\n"
     "- 已手动标记的合同，在**后续全量抓取中持久保留**（不被覆盖）\n"
     "- 新抓取的合同默认标记为「待确认」",
     "#### 6.5.3 两态标记\n"
     "\n"
     "| 状态 | 含义 |\n"
     "|---|---|\n"
     "| **纳入台账** | 这份合同要管（⭐ **抓来即此态** —— 系统默认值） |\n"
     "| **不纳入** | 废数据 / 与本域无关（**人工标记**） |\n"
     "\n"
     "**关键规则：**\n"
     "\n"
     "- 支持**批量标记**：**范围 = 当前筛选结果**；**未勾选时批量按钮先禁用**（不是点了才拦）；动作完成后**清空勾选**；筛选条件变化时**裁剪不可见的勾选**\n"
     "- ⭐ **抓取（含全量重抓）之后**：新抓的合同**默认「纳入台账」**；**已人工改成「不纳入」的，持久保留、不被覆盖**\n"
     "- ⚠️ **「待确认」这个状态已取消**（2026-09-25 用户裁定）：它原先起的是**分拣闸**作用（抓回来的不一定都要管）；"
     "现改为**抓来即纳入**，不要的项目改用**集采剔除名单**（抓取时直接剔除、不落库）来管 ⇒ 因此不再需要「待确认」这一态"),
    ("§8.3 状态机表",
     "| **集采合同纳入** | 待确认 → 纳入 / 不纳入 | 人工标记，**抓取不覆盖** | §6.5.3 |",
     "| **集采合同纳入** | 纳入台账 / 不纳入 | 抓来即「纳入台账」；人工改「不纳入」后**抓取不覆盖** | §6.5.3 |"),
    ("§8.4 口径一致性（手改保护）",
     "（分类、统计两金额、调整单、三态标记）",
     "（分类、统计两金额、调整单、两态标记）"),
    ("§9.3 留痕表",
     "**手改分类 · 集采实际供应商 · 集采三态标记 · 剔除标记",
     "**手改分类 · 集采实际供应商 · 集采两态标记 · 剔除标记"),
    ("§9.3 留痕理由段",
     "（分类、三态、剔除标记）",
     "（分类、两态、剔除标记）"),
    ("§9.3 附加要求",
     "- 手改三态标记（集采合同纳入）→ **不被重新抓取覆盖**",
     "- 手改两态标记（集采合同纳入）→ **不被重新抓取覆盖**"),
    ("附录 E `ENT-06`",
     "| | | 纳入状态（三态标记） | 枚举：待确认 / 纳入台账 / 不纳入 | 新抓取默认「待确认」；**人工标记不被抓取覆盖**；支持批量标记 | §6.4.1 / §6.5.3 |",
     "| | | 纳入状态（两态标记） | 枚举：纳入台账 / 不纳入 | ⭐ 抓来即「纳入台账」；**人工标记不被抓取覆盖**；支持批量标记 | §6.4.1 / §6.5.3 |"),
    ("附录 F `MOD-11` 行",
     "抓取（**仅人工点击**）与三态标记、合同收发登记",
     "抓取（**仅人工点击**）与两态标记、合同收发登记"),
]

MOD11_EDITS: list[tuple[str, str, str]] = [
    ("能力 #7",
     "| 7 | ⭐ **三态标记**（人工标记 · **抓取不覆盖已人工标记的行**） |",
     "| 7 | ⭐ **两态标记**（人工标记 · **抓取不覆盖已人工标记的行**） |"),
    ("能力 #13",
     "| 13 | 手工新增合同行（**三态默认「待确认」**，与抓取行一致） |",
     "| 13 | 手工新增合同行（**默认「纳入台账」**，与抓取行一致） |"),
]


def _sub(value: str, old: str, new: str, where: str) -> str:
    assert isinstance(value, str), f"{where} 不是字符串"
    n = value.count(old)
    assert n == 1, f"{where}：旧值命中 {n} 次（期望 1）—— ⛔ 先核对原文"
    return value.replace(old, new, 1)


def patch_text(path: Path, items: list[tuple[str, str, str]]) -> str:
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    back = text.replace("\n", "\r\n") if crlf else text
    assert back.encode("utf-8") == raw, f"{path.name}：行尾 round-trip 不一致"
    for where, old, new in items:
        text = _sub(text, old, new, f"{path.name}｜{where}")
    return text.replace("\n", "\r\n") if crlf else text


def patch_baseline() -> str:
    raw = BASE.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    # ⭐ 序列化参数已用 round-trip 实测（indent=1 · ensure_ascii=False · CRLF · 末尾一个 CRLF）
    assert (json.dumps(data, indent=1, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"
            ).encode("utf-8") == raw, \
        "验收基线 round-trip 不一致 ⇒ ⛔ 序列化参数变了，先复核再改"

    cases = data["cases"]
    fetch = cases["ACC-JC-FETCH-001"]
    fetch["criterion"] = _sub(fetch["criterion"], "三态标记可逐条可批量", "两态标记可逐条可批量",
                              "ACC-JC-FETCH-001｜criterion")
    fp = {p["id"]: p for p in fetch["points"]}
    fp["001-03"]["claim"] = _sub(fp["001-03"]["claim"], "三态标记可逐条也可批量", "两态标记可逐条也可批量",
                                 "001-03")
    assert fp["001-07"]["claim"] == "三态默认值 = 纳入台账（比对加载时快照）", fp["001-07"]["claim"]
    fp["001-07"]["claim"] = "默认值 = 纳入台账（比对加载时快照）—— ⭐ **抓取与手工新增是同一个默认值**（`TAIL-97`：取消「待确认」）"
    fp["001-08"]["claim"] = _sub(fp["001-08"]["claim"], "三态标记不留痕", "两态标记不留痕", "001-08")
    assert fp["001-10"]["claim"] == "抓取不覆盖已人工标记的行", fp["001-10"]["claim"]
    fp["001-10"]["claim"] = "抓取不覆盖已人工标记的行（⭐ 人工标「不纳入」后，抓取**不许改回来**）"

    home = cases["ACC-HOME-TODO-001"]
    assert "§6.5.3" in home["cover"], home["cover"]
    home["cover"] = [x for x in home["cover"] if x != "§6.5.3"]
    home["source"] = _sub(home["source"], "§10f（9 项待办）",
                          "§10f（9 项待办；⭐ `TAIL-97` 2026-09-25 撤掉 `jcPending` ⇒ 现 **8 项**）",
                          "ACC-HOME-TODO-001｜source")
    home["criterion"] = _sub(home["criterion"], "**9 项待办**", "**8 项待办**", "criterion")
    hp = {p["id"]: p for p in home["points"]}
    assert "**9 项待办**把手齐全" in hp["001-01"]["claim"], hp["001-01"]["claim"]
    hp["001-01"]["claim"] = ("**8 项待办**把手齐全、不重不漏（未审批 · 归属待判定 · 计划未匹配 · 差异（看调整单） · "
                             "占位行 · 本月尚未抓取 · 最近一次抓取失败 · 打印投递失败）")
    hp["001-03"]["claim"] = _sub(hp["001-03"]["claim"], "9 项**都可点击", "8 项**都可点击", "001-03")
    assert "「集采待确认」与「差异待核对」" in hp["001-09"]["claim"], hp["001-09"]["claim"]
    hp["001-09"]["claim"] = ("「差异（看调整单）」取**本域出口**（载体 = `MOD-08` 的调整单，口径 `§5.8.3`）；"
                             "⛔ 不得臆造或隐藏该项。⭐ `TAIL-97`：原与本项并列的「集采待确认」**已撤**"
                             "（两态化后它恒 0 —— 留着就是**谎报一个不存在的待办**）")
    hp["001-09"]["cover"] = "§5.8.3"

    data["asof"] = "2026-09-25"
    assert sum(len(c.get("points") or []) for c in cases.values()) == 559, "判据点合计变了（本批**只改文案**，⛔ 不该动点数）"
    return json.dumps(data, indent=1, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def main() -> int:
    apply = "--apply" in sys.argv
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        doc_new = patch_text(DOC, DOC_EDITS)
        mod_new = patch_text(MOD11, MOD11_EDITS)
        base_new = patch_baseline()
    except AssertionError as exc:
        print("⛔ 断言没过 ⇒ **一个文件都没写**：")
        print("   " + str(exc))
        return 1

    print("=" * 78)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + " ·  TAIL-97 契约面同步")
    print("=" * 78)
    for path, new, n in ((DOC, doc_new, len(DOC_EDITS)), (MOD11, mod_new, len(MOD11_EDITS)),
                         (BASE, base_new, 8)):
        old_bytes = path.read_bytes()
        print(f"  {path.name:<34} 替换 {n} 处 · 字节 {len(old_bytes)} ⇒ {len(new.encode('utf-8'))}")
    print(f"  备份将落 = {BACKUPS}（文件名带 {stamp}）")

    if not apply:
        print("\n  （加 --apply 才真写。）")
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    for path in (DOC, MOD11, BASE):
        shutil.copy2(path, BACKUPS / f"face-{stamp}-{path.name}")
    DOC.write_bytes(doc_new.encode("utf-8"))
    MOD11.write_bytes(mod_new.encode("utf-8"))
    BASE.write_bytes(base_new.encode("utf-8"))
    print("\n  ✅ 已写盘 ＋ 备份完成。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
