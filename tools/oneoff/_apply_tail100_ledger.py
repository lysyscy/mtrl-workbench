"""`TAIL-100` 台账：**销号**（§一 撤行 → §四 留痕 · 计数 A 7→6 · 已销号 97→98 · §14.3 撤行）。

`T6` 会机器核对：编号连续 · 计数与实际一致 · **§14.3 与 §15 两处一致** ⇒ 四处必须同批改。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail100_ledger.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail100_ledger.py --apply`  # 真写
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

ROW_S1 = ("| `TAIL-100` | **看板 / 欠款页的「集采欠款」恒 ¥0.00** ⇒ `build_debt` 的 `jc_debt` **没有生产调用方** | "
          "2026-09-25 `TAIL-97` 入场时真机实测发现（`GET /api/m05/debt` ⇒ `jc.amount = \"0.00\"`，"
          "而集采台账页真值 = 74,448,655.29） | 看板「集采欠款」与「欠款合计（三类）」**少算 7444 万**，"
          "且页面看不出来（典型的「看着正常的错数」）；判据 `ACC-FLOW-DEBT-001/001-03` 只钉了**域函数**"
          "（\"集采由外部注入\"）、**没钉\"注入方真的注入了\"** | `backend/app/mod05_flow/router.py` 的 "
          "`get_debt_data()` 给 `build_debt` 注入真实 `jc_debt`（唯一出口 = `mod11_jc.service`）＋ "
          "补一条「注入方真的注入了」的判据（`ACC-FLOW-DEBT-001`） | 随时 | 待做 |\n")

ROW_S143 = ("| `TAIL-100` 看板集采欠款恒 0（`jc_debt` 无注入方） | 随时（`TAIL-97` 收尾后即可） | "
            "①**少算钱**（7444 万级）而页面看不出来；②改动面小（一个端点 ＋ 一条判据）；③与 `TAIL-97` **无因果** "
            "⇒ ⛔ 别并进它（那会把付款域欠款口径混进契约面那一批） | 无（唯一出口 `mod11_jc.service` 已在位） |\n")

ROW_S4 = ("| `TAIL-100` | ⭐ **看板 / 欠款页的「集采欠款」恒 ¥0.00** —— `build_debt` 的 `jc_debt` **没有生产调用方** | "
          "✅ **已销号（2026-09-25）** —— ① **发现**：`TAIL-97` 入场时真机实测 `GET /api/m05/debt` ⇒ "
          "`jc.amount = \"0.00\"`，而集采台账页真值 = 74,448,655.29；② **根因**：付款域口径是「集采欠款**不在本域算**、"
          "由集采台账负责」（§4.5.1）⇒ 那边**要一个注入方**，而**从来没人实现**（两个生产调用点都在裸调 "
          "`build_debt(s)`）；③ **修法（唯一出口）**：集采域加 `service.debt_of_ledger`（只计「纳入台账」· 走 "
          "`build_list` ⇒ 与台账页**同一个数**），付款域加 `service.build_debt_live`（= `build_debt` ＋ 注入），"
          "**两个生产调用点都改走它**（看板端点 ＋ 手改统计金额的欠款回执）；⛔ `build_debt` 本身**保持纯组装**"
          "（离线桩件 `test_page_m05.py` 用 `FakeSession` 在测它 ⇒ 里面不能连库）；④ **判据**："
          "`ACC-FLOW-DEBT-001` **＋ `001-07`**「**注入方真的存在**」（判据点 559 → **560**）＋ 结构面断言"
          "（两个调用点都必须走装配出口 —— 堵「端点又绕开」这条路）；⑤ **真机复核**：重启服务后 "
          "`GET /api/m05/debt` ⇒ `jc = 74448655.29`、合计 82,725,652.95（原 8,276,997.66 ⇒ **少算了 7444 万**）；"
          "⑥ 闸门：pytest rc=0 · `doc_audit` ± `--ui` 双 0 · 12 把尺子全 0 · 四态 **560 绿** | 2026-09-25 |\n")

EDITS: list[tuple[str, str, str]] = [
    ("§0.2 计数：A 7⇒6 · 已销号 97⇒98",
     "- **尾巴**：A 类 **7** 条 · B 类 0 · C 类 **0** · 已销号 **97**（明细 = §15）。",
     "- **尾巴**：A 类 **6** 条 · B 类 0 · C 类 **0** · 已销号 **98**（明细 = §15）。"),
    ("§15 顶部计数：A 7⇒6 · 已销号 97⇒98",
     "> **当前状态（2026-09-25 · 实测）**：A 类 **7** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **97** 条",
     "> **当前状态（2026-09-25 · 实测）**：A 类 **6** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **98** 条"),
    ("§15 §一：撤掉 `TAIL-100` 行", ROW_S1, ""),
    ("§14.3：撤掉 `TAIL-100` 行", ROW_S143, ""),
    ("§15 §四：`TAIL-100` 销号留痕（§四 表头下**没有** `|---` ⇒ 用表头行当锚）",
     "| # | 事项 | 销号依据 | 日期 |\n| `TAIL-97` |",
     "| # | 事项 | 销号依据 | 日期 |\n" + ROW_S4 + "| `TAIL-97` |"),
]


def main() -> int:
    apply = "--apply" in sys.argv
    raw = PLAN.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if (text.replace("\n", "\r\n") if crlf else text).encode("utf-8") != raw:
        print("⛔ 行尾 round-trip 不一致 ⇒ 不动")
        return 1
    errors: list[str] = []
    for desc, old, new in EDITS:
        n = text.count(old)
        if n != 1:
            errors.append(f"{desc} —— 命中 {n} 次（期望 1）")
            continue
        text = text.replace(old, new, 1)
    print("=" * 78)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + " ·  TAIL-100 销号")
    print("=" * 78)
    print(f"  {PLAN.name} · 行尾={'CRLF' if crlf else 'LF'} · 替换 {len(EDITS)} 处")
    if errors:
        print("\n⛔ 有锚点对不上 ⇒ **一个字节都没写**：")
        for e in errors:
            print("   " + e)
        return 1
    if not apply:
        print("\n  （加 --apply 才真写。）")
        return 0
    PLAN.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("\n  ✅ 已写盘。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
