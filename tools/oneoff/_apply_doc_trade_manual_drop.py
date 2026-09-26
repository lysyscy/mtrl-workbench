"""一次性（2026-09-26 · 用户裁定 a）：把《说明书》里「贸易公司名 / 贸易公司合同金额 = **手工**」
改成「**i8 抓取自动落**」——用户原话：「a如果二方案落地，那么就不再需要手工，这条可以废掉」。

⚠️ 这份《说明书》在**交付面**（仓外 · `D:\\工作\\AI\\PRD编写夹 - Workbuddy专用`，WPS 云同步树）⇒ 本脚本：
  ① **先备份**到**仓侧** `.workbuddy/backups/`（⛔ 不在交付面建新文件）；
  ② 逐处**断言**都改到了（任一处找不到 ⇒ **不写盘**）；
  ③ 只改这两处措辞，⛔ 不动别处（⛔ 不改验收条目 —— 那条不在本次裁定范围）。

跑法：`backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_apply_doc_trade_manual_drop.py`
"""

from __future__ import annotations

from pathlib import Path

DOC = Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\材料科业务全流程说明书.md")
BACKUP = Path(__file__).resolve().parents[2] / ".workbuddy" / "backups" / "说明书-before-贸易公司手工口径-2026-09-26.md"

PAIRS = (
    # ① §6.4.1 字段来源表：贸易公司名
    ("| 贸易公司名 | 手工 | |",
     "| 贸易公司名 | **i8 抓取自动落**（甲方单位被分类为「贸易公司」时 = 甲方单位名） | "
     "⭐ 2026-09-26 用户裁定：方案②落地后**不再要求手工**（本条原为「手工」） |"),
    # ② 同上：贸易公司合同金额
    ("| 贸易公司合同金额 | 手工 | |",
     "| 贸易公司合同金额 | **i8 抓取自动落**（甲方单位被分类为「贸易公司」时 = i8 抓来的那个金额） | "
     "⭐ 2026-09-26 用户裁定：方案②落地后**不再要求手工**；人工可补的只有「合同金额」（供应商价，"
     "导出前由 Excel 供应商线填，**空才填**） |"),
    # ③ ENT-06 那一行（把「手工」的范围说清）
    ("| | | 发票金额 / 贸易公司名 / 贸易公司合同金额 / 贸易公司发票金额 | **手工**（**发票金额 / "
     "贸易公司发票金额 = 各自子表合计**，录入走子表） | 结算金额据此计算 | §6.4.1 / §6.3.2 |",
     "| | | 发票金额 / 贸易公司名 / 贸易公司合同金额 / 贸易公司发票金额 | **手工**（**发票金额 / "
     "贸易公司发票金额 = 各自子表合计**，录入走子表）；⭐ 但**贸易公司名 / 贸易公司合同金额自 "
     "2026-09-26 起由 i8 抓取自动落**（甲方分类为「贸易公司」时；见 §6.4.1） | 结算金额据此计算 | "
     "§6.4.1 / §6.3.2 |"),
)


def main() -> int:
    if not DOC.exists():
        print(f"⛔ 找不到《说明书》：{DOC}")
        return 1
    text = DOC.read_text(encoding="utf-8")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(text, encoding="utf-8")
    print(f"✅ 已备份 → {BACKUP.name}（{len(text)} 字符）")

    bad: list[str] = []
    for old, new in PAIRS:
        if old not in text:
            bad.append(old[:60])
    if bad:
        print("⛔ 这些要改的原句**没找到** ⇒ 不写盘（⛔ 不半改）：")
        for b in bad:
            print("   ", b)
        return 1

    for old, new in PAIRS:
        text = text.replace(old, new, 1)
    DOC.write_text(text, encoding="utf-8")
    print(f"✅ 已改 {len(PAIRS)} 处（贸易公司名 / 贸易公司合同金额 = i8 抓取自动落）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
