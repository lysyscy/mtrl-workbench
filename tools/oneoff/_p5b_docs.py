#!/usr/bin/env python
r"""`TAIL-64` **`P5-b`** 收尾：把计划面（`§15` / `§14.3` / `§13.6` ＋ 入门口令）改到与实况一致。

同 `_p5a_docs.py` 的规矩：**ASCII / 反引号能对齐的用字面替换；必须跨 emoji 的用 `.*?` 通配**，
并逐处断言命中计数（⛔ 逐字锚带 `⚠️` 会打空 —— 已实测两次）。

改 6 处：`①§15 TAIL-64 尾` · `②§14.3 尾` · `③状态行尾` · `④接续动作的 P5 那句` · `⑤口令余量` · `⑥口令下一步块`。

用法：`python tools/oneoff/_p5b_docs.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
NL = "\r\n"

S15_TAIL = (
    "⇒ 实况见施工图 **§7.7**）；⭐⭐ **同日 `P5-b` 也办完 ⇒ 标记改为「**一律带**」（⛔ 不设开关）**"
    "（先量：真机读数**只有 `m08` 过 400 行**（`m11` 329 最接近）⇒ 「逐页点名」今天**一个都不会生效**，"
    "而那正是 `TAIL-66` 明禁的**名单式**（某页涨上去忘了加 ⇒ **永远不生效、且不报错**）"
    "⇒ `TBL` 去掉 `vs` 参、**一律**出 `data-vs`（⚠️ `U5` 件 ⇒ **两侧同批同句**）；"
    "行为零变化（接管与否仍由**行数阈值**说了算 ⇒ 今天只有 `m08` 走表级）；撤掉 `VSCROLL` 的 `m08` 例外"
    "＋ `m08` 调用点回到普通形态（那条漂移变**幽灵**、已消号）；"
    "⚠️ **交付面 `demo/_smoke.js` 有一条钉字面 `<tbody>` 的断言被打掉**（`607 → 606/1`）"
    "⇒ 改成 `<tbody` **前缀匹配**（判词意图未改 · 交付面改前已备份）；判据/变异同批更新"
    "（`_mut_p5a.py` **3/3**：改名标记 / 摘挂载点 / 摘分派））⇒ 实况见施工图 **§7.8**） |")

S143_TAIL = (
    "⛔ **`TAIL-65` 先落**（✅ 已落；⭐⭐ 2026-09-30 **`P4-a`~`P4-d-b` ＋ `P5-a` ＋ `P5-b` 都办完** ⇒ "
    "筛选栏外壳 **22 处**全清 ＋ 项目按钮 **11 处**全清 ＋ **虚拟滚动下沉到表级**（`m08` 试点）"
    "＋ **标记改为「一律带」**（⛔ 不设开关，见 §7.8）；见 §15 §一 本行与施工图 §8.5/§8.6/§8.9/§7.7/§7.8）· "
    "⏭ 余 **`P4-c`（口径说明 · 待用户定裁）** 与 **`P5-c`（删页级那条路）/ `P5-d`（行模板 `cols`）**"
    "＋ 小尾巴 `TAIL-196` |")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    t = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    out = t

    # ① §15 的 `TAIL-64` 行：从「⇒ 实况见施工图」起到行尾
    rows = [ln for ln in out.split("\n") if ln.startswith("| `TAIL-64`")]
    assert len(rows) == 2, f"⛔ `TAIL-64` 表行应恰好 2 行，实得 {len(rows)}"
    row15 = rows[1] if "前端表格/筛选/行模板" in rows[1] else rows[0]
    i = row15.index("⇒ 实况见施工图")
    new15 = row15[:i] + S15_TAIL
    assert new15.endswith(" |")
    out = out.replace(row15, new15, 1)
    print("   ✅ ① §15 `TAIL-64` 行尾")

    # ② §14.3 的 `TAIL-64` 排期行
    row143 = rows[0] if rows[0] is not row15 else rows[1]
    k = row143.index("⛔ **`TAIL-65` 先落**")
    new143 = row143[:k] + S143_TAIL
    assert new143.endswith(" |")
    out = out.replace(row143, new143, 1)
    print("   ✅ ② §14.3 `TAIL-64` 排期行")

    # ③ 交接表「状态」行尾那句（`P5-a` 已办 / 余 P5-b…）
    pat3 = r"⇒ .{0,2}\*\*同日 `P5-a` 也已办\*\*.{0,120}?与 \*\*`P5-b`/`P5-c`/`P5-d`\*\*。"
    assert len(re.findall(pat3, out)) == 1, f"⛔ ③ 命中 {len(re.findall(pat3, out))} 次"
    out = re.sub(pat3, "⇒ ⭐ **同日 `P5-a` ＋ `P5-b` 也都办完**（表级虚拟滚动落地 ＋ **标记改为「一律带」**："
                       "⛔ 不设开关，见施工图 §7.7/§7.8）⇒ 余 **`P4-c`**（⚠️ 待定裁）与 **`P5-c`/`P5-d`**。",
                 out, count=1, flags=re.S)
    print("   ✅ ③ 状态行尾")

    # ④ 接续动作行：「① P5-a ✅ 已办…⇒ 接着是 P5-b」那句
    pat4 = r"\*\*① `P5-a` ✅ 已办\*\*.{0,120}?。"
    assert len(re.findall(pat4, out)) == 1, f"⛔ ④ 命中 {len(re.findall(pat4, out))} 次"
    out = re.sub(pat4, "**① `P5-a` ＋ `P5-b` ✅ 都办完**（虚拟滚动下沉到「每张表」＋ 标记「一律带」· "
                       "施工图 §7.7/§7.8）；⇒ **接着是 `P5-c`（删页级那条路）/ `P5-d`（行模板 `cols`）**。",
                 out, count=1, flags=re.S)
    print("   ✅ ④ 接续动作 · P5")

    # ⑤ 入门口令：① 那句的尾（`P5-b`（表级下沉铺开））
    pat5 = r"/ \*\*P5-b\*\*（表级下沉铺开））·"
    assert len(re.findall(pat5, out)) == 1, f"⛔ ⑤ 命中 {len(re.findall(pat5, out))} 次"
    out = re.sub(pat5, "/ **`P5-c`/`P5-d`**（删页级那条路 / 行模板 `cols` · 均**先出量测**））·",
                 out, count=1, flags=re.S)
    print("   ✅ ⑤ 入门口令 · 余量")

    # ⑥ 入门口令：下一步块（`P5-b` 已办 ⇒ 余 `P5-c`/`P5-d`）
    pat6 = r"⏭ 接着 \*\*`P5-b`（表级下沉铺开.{0,40}?）\*\*。"
    assert len(re.findall(pat6, out)) == 1, f"⛔ ⑥ 命中 {len(re.findall(pat6, out))} 次"
    out = re.sub(pat6, "⏭ 接着 **`P5-c`（删页级那条路 —— 它现在实际上已走不到）/ `P5-d`（行模板 `cols`）**，"
                       "⚠️ 两条都**先出量测再定批**。", out, count=1, flags=re.S)
    print("   ✅ ⑥ 入门口令 · 下一步块")

    # ⑦ 「一句话现状」③ 那一段（写给人看：P5 现在到哪了）
    a = out.index("> ③ **离看得见的收益还差一步**")
    b = out.index("\n", out.index("最终目的**", a))
    out = out[:a] + (
        "> ③ **`P5` 现在的状态**：`P5-a`/`P5-b` 已把虚拟滚动**下沉到「每张表」**、并把标记改成**一律带**"
        "（⛔ 不设开关 ⇒ 「以后哪页涨到 400 行就自动生效」，不会再出现「忘了加名单」那种永远不生效）"
        "；⚠️ **今天界面上仍看不出差别** —— 真机读数里**只有 `m08` 过 400 行**（`m11` 329 最接近）。"
        "⭐ `P5` 仍是这张施工图的最终目的。") + out[b:]
    print("   ✅ ⑦ 一句话现状③")

    assert out != t, "⛔ 一个字都没改？"
    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0
    PLAN.write_text(out.replace("\n", NL), encoding="utf-8", newline="")
    back = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    assert back == out, "⛔ 写回自校验不过"
    print("\n✅ 计划面已刷新（6 处）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
