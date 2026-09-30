#!/usr/bin/env python
r"""`P5-c` 收尾 · 补 `T6` 那两条红（**新尾巴登记即排期**）：§15 §一 / §0 计数 ＋ §14.3 排期表加 `TAIL-198`。

⚠️ 为什么单开一件（同 `_p5b_tail197.py`）：`T6` 的判法是
   ① **登记了就必须在 §14.3 排期表里有一行**（⛔ 两处分叉 = 红）＋ ② **顶部计数要与实际相符**。
    这两处都**不是内容改动**、而是"台账自身的账" ⇒ 单独一件好复核。

用法：`python tools/oneoff/_p5c_t6.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
NL = "\r\n"

ROW_143 = (
    "| `TAIL-198` ⚠️ **9 张「带标记却不在 `.tw` 里」的表**（够阈值时会**静默不虚拟化**） | "
    "⏳ **随时**（⚠️ 不急 —— 今天都在阈值以下 ⇒ 无害） | **四问**：① **不是任何东西的前置**；"
    "② **成本不随时间变贵**（要么给 9 张表补 `.tw`、要么让 `TBL` 自带容器 —— 都是**一次**的活）；"
    "③ **同域 = 壳的表格件那一片**（`shell/proj.js` 的 `TBL` ＋ 各页切片）；④ **前置 = 一次量测**"
    "（哪些页会涨到 400 行？⛔ 别凭感觉挑） | 触发 = 谁空谁做（或某页真涨上去时报障）；"
    "落点 = 二选一（见 §15 §一 本行） |"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    t = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")

    # ① §0 的计数行（口径不变，只 +1）
    old0 = "A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **195**"
    assert t.count(old0) == 1, f"⛔ §0 计数行命中 {t.count(old0)} 次"
    t = t.replace(old0, "A 类 **6** 条 · B 类 0 · C 类 **0** · 已销号 **195**", 1)
    print("   ✅ ① §0 计数：A 类 5 → 6")

    # ② §15 §一 的计数行
    old1 = "A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **195** 条"
    assert t.count(old1) == 1, f"⛔ §15 计数行命中 {t.count(old1)} 次"
    t = t.replace(old1, "A 类 **6** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **195** 条", 1)
    print("   ✅ ② §15 §一 计数：A 类 5 → 6")

    # ③ §14.3 排期表：`TAIL-198` 插在 `TAIL-197` 那一行之前（同「新在上」）
    lines = t.split("\n")
    for k, ln in enumerate(lines):
        if ln.startswith("| `TAIL-197` 🚧 **交付面四检失败时闸门不判红**"):
            lines.insert(k, ROW_143)
            break
    else:
        raise AssertionError("⛔ §14.3 里找不到 `TAIL-197` 那一行")
    t = "\n".join(lines)
    print("   ✅ ③ §14.3 排期表：新增 TAIL-198")

    if not a.write:
        print("\n（干跑：⛔ 未写）")
        return 0
    PLAN.write_text(t.replace("\n", NL), encoding="utf-8", newline="")
    back = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    assert back == t, "⛔ 写回自校验不过"
    print("\n✅ T6 的两条红已补（计数 ＋ §14.3 排期）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
