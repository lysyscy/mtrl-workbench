"""`TAIL-209` **销号**（§15 §一 → §四）＋ 计数两处同改（`T6` 一致）。

⚠️ 为什么用脚本：§一 那行**极长**（几千字）⇒ 手抄进 `replace_in_file` 必错；本件按**行首标记**定位、
   并逐条断言「命中恰好 1 次」，不达标**整批不写**。
⚠️ 字节级：`read_text/write_text(newline="")` ⇒ ⛔ 不折 CRLF。
⚠️ 被 §13.6 入门口令点名 ⇒ 必有 `main()`；跑完请复跑 `doc_audit`（`T6` 会核编号连续 ＋ 计数一致）。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".codebuddy" / "plans" / "开发计划-主文档.md"

#: §一 那行的**行首标记**（只认这个 —— 行的其余部分几百字，⛔ 别抄）
ROW_HEAD = "| `TAIL-209` | 💬 **说明文字瘦身 · 批 2（弹窗）＋ 批 3（`CALIB` 逐条）**"
#: 计数两处（§0.2 与 §15 顶部）
COUNT_OLD = "A 类 **2** 条 · B 类 0 · C 类 **0** · 已销号 **210**"
COUNT_NEW = "A 类 **1** 条 · B 类 0 · C 类 **0** · 已销号 **211**"
COUNT2_OLD = "A 类 **2** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **210** 条"
COUNT2_NEW = "A 类 **1** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **211** 条"


def main() -> int:
    text = PLAN.read_text(encoding="utf-8", newline="")
    lines = text.split("\n")

    idx = [i for i, ln in enumerate(lines) if ln.startswith(ROW_HEAD)]
    if not idx:
        print("✔ §一 那行**已经不在**（幂等：销号已做过）")
        return 0
    if len(idx) != 1:
        print(f"⛔ 行首标记命中 {len(idx)} 行（期望 1）⇒ 不写")
        return 1
    if not any("TAIL-209` | 💬 **界面说明文字瘦身**" in ln for ln in lines):
        print("⛔ §四 里没有 `TAIL-209` 的销号行 —— 先插销号行再跑本件（⛔ 不许静默删）")
        return 1

    before = len(lines)
    del lines[idx[0]]
    text = "\n".join(lines)
    for old, new in ((COUNT_OLD, COUNT_NEW), (COUNT2_OLD, COUNT2_NEW)):
        if text.count(old) == 1:
            text = text.replace(old, new, 1)
        else:
            print(f"⛔ 计数行命中 {text.count(old)} 次 ⇒ 不写：{old!r}")
            return 1

    PLAN.write_text(text, encoding="utf-8", newline="")
    print(f"✅ 已销号：删 §一 那行（{before} → {len(text.split(chr(10)))} 行）＋ 计数 2 → 1 / 210 → 211")
    return 0


if __name__ == "__main__":
    sys.exit(main())
