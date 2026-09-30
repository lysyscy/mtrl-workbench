#!/usr/bin/env python
r"""`TAIL-64` **`P4-d-b`** 收尾第 2 步：把计划 §13.6 的**交接材料**改到与实况一致。

**为什么单独落一个脚本**：要改的每一句里都带 `⚠️`（含**变体选择符**）/ 反引号 / 全角括号 ——
① 内联 `python -c` 在 PowerShell 里会被吞（本仓老坑）；② **逐字锚点带 emoji 会打空**
（本轮实测：`⇒ 余 **`P4-d-b`** …⚠️…` 那段逐字锚命中 0 次）⇒ 一律**正则 ＋ `.*?`** 让它落在通配区里。

改 7 处（每处**必须恰好命中 1 次**，否则拒写）：
`①「一句话现状」的分期` · `② 状态行` · `③ 接续动作行` · `④ 入门口令的"余 P4/P5"` ·
`⑤ 入门口令的变异靶数` · `⑥ 入门口令的工作区状态` · `⑦ 入门口令的"已确认的下一步"`。

用法：`python tools/oneoff/_p4db_handoff.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
NL = "\r\n"

EDITS: tuple[tuple[str, str, str], ...] = (
    # ① 「一句话现状」的分期（写给人看的那三句）
    (r"→ \*\*项目选择按钮\*\*（出口 ＋ 1 处试点已办，余 11 处）。",
     "→ **项目选择按钮**（**12 处全清**）。",
     "「一句话现状」的分期"),
    # ② 交接表的「状态」行
    (r"⇒ \*\*余 `P4-d-b`（铺余下 11 处）\*\*。",
     "⇒ ⭐ **同日 `P4-d-b` 也已办 ⇒ `P4-d` 整条做完**（余下 11 处一次铺完：行数全 Δ0 · 渲染字节不变 · "
     "判据 ＝ 试点那条 ＋ **新写扫描式** · 变异 **4/4**；实况 = 施工图 **§8.9**）⇒ 余 **`P4-c`**（⚠️ 待定裁）"
     "与 **`P5-a`**。",
     "状态行"),
    # ③ 交接表的「接续动作（第一步）」行
    (r"⇒ \*\*余 `P4-d-b`（把余下 11 处按钮铺进 `PJB`.*?）\*\* ·\n \*\*`P4-c`（口径说明.*?）\*\*；",
     "⇒ ⭐ **2026-09-30 晚：`P4-d-b` 也已办 ⇒ `P4-d` 整条做完**（实况 = 施工图 §8.9；⚠️ 原型未动） ⇒ "
     "**余 `P4-c`（口径说明 · ⚠️ 候选定义已量出、待定裁，见 §8.7）**；",
     "接续动作行"),
    # ④ 入门口令：① 那句"余 P4（…）/ P5"
    (r"（余 \*\*P4\*\*（`P4-d-b`：铺余下 11 处项目按钮 / `P4-c`：口径说明 · ⚠️ \*\*待用户定裁\*\*）/ \*\*P5\*\*）·",
     "（余 **P4-c**（口径说明 · ⚠️ **待用户定裁**）/ **P5**）·",
     "入门口令 · 余量"),
    # ⑤ 入门口令：变异靶数（`P4-d-b` 从 2 靶涨到 4 靶 —— ⚠️ 漏改 = 下个会话少跑一把）
    (r"tools/mut/_mut_pjb\.py（\*\*2 靶\*\*）", "tools/mut/_mut_pjb.py（**4 靶**）", "入门口令 · 靶数"),
    # ⑥ 入门口令：工作区状态（本批未提交）
    (r"\*\*工作区 0 条未提交\*\*（⚠️ \*\*唯一例外 = 交接材料本身\*\* —— 按限制 ⑩ \*\*待用户点头才提交\*\*）· \*\*本地领先远端 0\*\*",
     "**工作区 = 本批未提交**（`P4-d-b` 那批：壳 4 件 ＋ 判据 4 件 ＋ 变异 ＋ 台账/施工图 ＋ **交接材料本身**"
     " —— 按限制 ⑩ **待用户点头才提交**）· **本地领先远端 0**",
     "入门口令 · 工作区"),
    # ⑦ 入门口令：「已确认的下一步」块
    (r"⇒ 余\n    \*\*`P4-d-b`（把余下 11 处项目按钮铺进 `PJB`.*?）\*\* ·\n    \*\*`P4-c`（口径说明.*?）\*\*；",
     "⇒ ⭐ **2026-09-30 晚：`P4-d-b` 也已办 ⇒ `P4-d` 整条做完**（实况 = 施工图 **§8.9**） ⇒ 余\n"
     "    **`P4-c`（口径说明 —— ⚠️ 候选定义已量出、**待用户定裁**，见 §8.7）**；",
     "入门口令 · 下一步"),
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    t = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    out = t
    for pat, rep, label in EDITS:
        n = len(re.findall(pat, out, flags=re.S))
        assert n == 1, f"⛔ 「{label}」锚点命中 {n} 次（期望 1）—— 先核对原文"
        out = re.sub(pat, rep.replace("\\", "\\\\"), out, count=1, flags=re.S)
        print(f"   ✅ {label}")
    assert out != t, "⛔ 一个字都没改？"
    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    PLAN.write_text(out.replace("\n", NL), encoding="utf-8", newline="")
    back = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    assert back == out, "⛔ 写回自校验不过"
    print(f"\n✅ 交接材料已刷新（7 处）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
