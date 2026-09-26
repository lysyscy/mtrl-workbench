"""一次性（2026-09-26）：把用户「回头统一处理」的那类界面文案整治**登记进 §15 台账**（本仓规矩：
「凡"留到以后"的事，当场进 §15」）——新增 `TAIL-105`，并把两处计数 A 类 5 → 6。

⚠️ 逐处断言；任一处找不到 ⇒ **不写盘**（⛔ 不半改）。§14.3 与 §15 §一 两处都要加（`T6` 机器核对一致性）。
跑法：`backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_apply_tail105_open.py`
"""

from __future__ import annotations

from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / ".workbuddy" / "plans" / "开发计划-主文档.md"

SUBJECT = ("⭐ **通用导入面 ② 列映射的文案整治余项**（用户 2026-09-26：「**这类还很多，回头统一处理**」）")

ROW_15 = ("| `TAIL-105` | " + SUBJECT
          + " | ① **页头那句「这一批怎么入库」**（`rule_note`）现是一整段长文"
          + "（《前端设计守则》§5.9「同屏做优先级」）⇒ 压成 2~3 条短句（对号键 / 改哪几列 / 能否回滚）；"
          + "② **同类长文案一起过一遍**：页头 `note` · `keep_note` · 各域出错话术（守则 §2/§3/§5/§6）；"
          + "③ ⚠️ 列映射里**已落地**的那些**不在本条内**（去向三词 · 长句下沉悬停 · 「本系统要哪些列」"
          + "＋缺列提醒 · 不参与不给下拉 —— 均 2026-09-26 已做）；"
          + "④ ⚠️ **「不参与」的列目前没有「改映射」入口**（被认成合同日期/供应商/贸易公司后就改不回去）"
          + "—— 待用户裁定要不要给个小入口 | 待用户发起 |")

ROW_143 = "| `TAIL-105` 列映射文案整治（`rule_note` 压短 ＋ 同类长文案） | 待用户发起 | ⚠️ 用户 2026-09-26「这类还很多，回头统一处理」⇒ 明细见 §15 |"


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    lines = text.split("\n")
    bad: list[str] = []

    # ① 定位 §15 的「当前状态」行（它唯一）⇒ 它**前面**的 TAIL-102 行 = §14.3，**后面**的 = §15 §一
    state = [i for i, ln in enumerate(lines) if "当前状态（2026-09-26 · 实测）" in ln]
    if len(state) != 1:
        print(f"⛔ 找不到唯一的「§15 当前状态」行（找到 {len(state)} 处）⇒ 不写盘")
        return 1
    i_state = state[0]
    before = [i for i, ln in enumerate(lines) if ln.startswith("| `TAIL-102` ") and i < i_state]
    after = [i for i, ln in enumerate(lines) if ln.startswith("| `TAIL-102` ") and i > i_state]
    if not before or not after:
        print(f"⛔ 定位锚点失败（§14.3 {len(before)} 处 / §15 {len(after)} 处）⇒ 不写盘")
        return 1
    i_143, i_15 = before[-1], after[0]

    # ② 两处计数：A 类 **5** → **6**（期望恰好 2 处）
    hits = [i for i, ln in enumerate(lines) if "A 类 **5**" in ln]
    if len(hits) != 2:
        bad.append(f"「A 类 **5**」出现 {len(hits)} 处（期望 2：§0 与 §15 顶部）")
    if "TAIL-105" in text:
        bad.append("台账里已经有 `TAIL-105` 了 ⇒ 别重复登记")
    if bad:
        print("⛔ 前置检查不过 ⇒ 不写盘：")
        for b in bad:
            print("   ", b)
        return 1

    # ③ 插入两行（**先插后面的**，免得行号位移）
    lines.insert(i_15, ROW_15)                      # §15 §一：倒序 ⇒ 插在 TAIL-102 **之前**
    lines.insert(i_143 + 1, ROW_143)                # §14.3：插在 TAIL-102 **之后**
    text2 = "\n".join(lines).replace("A 类 **5**", "A 类 **6**")
    DOC.write_text(text2, encoding="utf-8")
    print("✅ §15 §一 新增 `TAIL-105` · §14.3 新增一行 · 两处计数 A 类 5 → 6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
