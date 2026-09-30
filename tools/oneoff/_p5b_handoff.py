#!/usr/bin/env python
r"""`P5-b` 收尾：把计划 `§13.6` 的**交接材料**刷到"停"的状态（⛔ 这一处**不提交** —— 限制 ⑩ 待用户点头）。

改 3 处：`①口令「工作区/领先远端」` · `②口令④同款` · `③口令「已确认的下一步」整段`。

⚠️ 规矩同 `_p5a_docs.py` / `_p4db_handoff.py`：**逐字锚带 emoji 会打空** ⇒ 用**短标记 ＋ 到行尾/段尾**；
能对齐的（含反引号的 ASCII 串）用**字面替换**，并逐处断言命中数。

用法：`python tools/oneoff/_p5b_handoff.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
NL = "\r\n"

NEXT_BLOCK = (
    "已确认的下一步：⭐ **`TAIL-64` 未完 —— 但三条路都已办到「只剩收尾」**：\n"
    "  ⏭ ⭐ **P4（筛选栏 `fbar` 配置化，实测 22 处）**：**2026-09-30 已办到 `P4-d-b`**\n"
    "     （筛选栏外壳 **22 处全清** ＋ 项目按钮出口 `PJB` **铺满 11 处** · 施工图 §8.5/§8.6/§8.9）⇒ 只余\n"
    "     **`P4-c`（口径说明 —— ⚠️ 候选定义已量出、**待用户定裁**，见 §8.7）**。\n"
    "  ⏭ ⭐ **P5（虚拟滚动下沉进 `TBL`）**：**已办到 `P5-b`** —— `P5-a` 落地**表级**（`m08` 试点 · 施工图 §7.7）\n"
    "     ＋ `P5-b` 把标记改成**一律带**（⛔ 不设开关 · 施工图 §7.8）⇒ 余\n"
    "     **`P5-c`（删页级那条路 —— 它**实际上已走不到**）/ `P5-d`（行模板 `cols` —— ⚠️ 住在 `V.*` 切片里，"
    "`U1` 会级联）**；\n"
    "     ⚠️ 两条都**先出量测再定批**；⛔ 开工同样要留足「改 ＋ 真机回归 ＋ 全闸门」的**整轮预算**。\n"
    "  ⏭ ⚠️ **另立一条新尾巴 `TAIL-197`**：**交付面四检失败时闸门不判红**（`doc_audit --ui` 只**打印**退出码、"
    "**自己的 `rc` 仍 0**）\n"
    "     —— ⛔ 即**别只看 `BAD: []`**：交付面那四行要人眼读（实测 `_smoke` 606/1 那一轮 `BAD: []`）。")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    t = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    out = t

    # ① 口令的「工作区 / 领先远端」整行
    pat1 = r"\*\*工作区 = 本批未提交\*\*（`P5-a` 那批.{0,160}?已 push）"
    n1 = len(re.findall(pat1, out, flags=re.S))
    assert n1 == 1, f"⛔ ① 命中 {n1} 次"
    out = re.sub(pat1, "**工作区 0 条未提交**（⚠️ **唯一例外 = 交接材料本身** —— 按限制 ⑩ **待用户点头才提交**）"
                       "· **本地领先远端 0**（`7a5c435` 已 push）", out, count=1, flags=re.S)
    print("   ✅ ① 口令 · 工作区/领先远端")

    # ② 口令 ④ 那句（旧号 `ccf1623` 已落后两笔）
    pat2 = r"· \*\*本地领先远端 0\*\*（`ccf1623` 已 push）"
    n2 = len(re.findall(pat2, out))
    assert n2 == 1, f"⛔ ② 命中 {n2} 次"
    out = re.sub(pat2, "· **本地领先远端 0**（`7a5c435` 已 push）", out, count=1)
    print("   ✅ ② 口令 ④ · 提交号")

    # ③ 「已确认的下一步」整段（从「已确认的下一步：」起到那句告诫结束）
    a = out.index("已确认的下一步：")
    b = out.index("\n", out.index("别在会话尾部半改着停下）。", a))
    out = out[:a] + NEXT_BLOCK + out[b:]
    print("   ✅ ③ 口令 · 已确认的下一步（整段）")

    assert out != t, "⛔ 一个字都没改？"
    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0
    PLAN.write_text(out.replace("\n", NL), encoding="utf-8", newline="")
    back = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    assert back == out, "⛔ 写回自校验不过"
    print("\n✅ 交接材料已刷到「停」的状态（⛔ 本处按限制 ⑩ 留作未提交 · 待用户点头）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
