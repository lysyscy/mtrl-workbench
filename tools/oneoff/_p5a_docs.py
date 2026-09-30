#!/usr/bin/env python
r"""`TAIL-64` **`P5-a`** 收尾：把计划面（`§15` / `§14.3` / `§13.6` 交接 ＋ 入门口令）改到与实况一致。

**为什么落脚本**：要改的句子里带 `⚠️` / `⭐`（**变体选择符**）与反引号 ——
① 内联 `python -c` 在 PowerShell 里会被吞；② **逐字锚点带 emoji 会打空**（`P4-d-b` 那轮实测过）
⇒ 一律：**ASCII/反引号能对齐的用字面替换；必须跨 emoji 的用 `.{0,N}?` 通配**，并**逐处断言命中计数**。

改 10 处：`①§15 TAIL-64 尾` · `②§14.3 TAIL-64 尾` · `③「一句话现状」③` · `④状态行尾` · `⑤接续动作`（两处）·
`⑥口令余量` · `⑦口令靶数` · `⑧口令工作区` · `⑨口令下一步块` · `⑩口令限制补两条`。

用法：`python tools/oneoff/_p5a_docs.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
NL = "\r\n"

S15_TAIL = (
    "⇒ 实况见施工图 **§8.9**）；⭐⭐ **同日 `P5-a` 也办完 ⇒ 虚拟滚动**下沉到表级**（`m08` 试点）**"
    "（`TBL` 加 `vs` 标记 —— ⚠️ **两侧同批同句**（它是 `U5` 逐字一致件 · 原型改前已备份）；"
    "`view.js` 的滚动监听提成**共用挂载点**（⛔ 留在页级那半 ⇒ 表级一 `return` 就没人挂监听，**离线全绿**）；"
    "首帧在**字符串层**只放全长垫高（⛔ 不先写全量再改 —— 那会让 1000+ 行整批 parse）；"
    "`VSCROLL={m08:{off:true}}`（语义 = **页级**对它关掉）＋ `m08` 调用点 `vs:true` ⇒ `U1` 换号 **1 行**（无幽灵）；"
    "判据 = 真机**新增 ㉟ 段**（本页内刷新不跳滚动 ＋ 排序后合计行仍在表尾）＋ 离线**结构性**一条"
    "（挂载点在分派之前 · `startVirtual(` 只许两处）；反向灵敏度 `tools/mut/_mut_p5a.py` **3/3**）"
    "⇒ 实况见施工图 **§7.7**） |")

S143_TAIL = (
    "⛔ **`TAIL-65` 先落**（✅ 已落；⭐⭐ 2026-09-30 **`P4-a`~`P4-d-b` ＋ `P5-a` 都办完** ⇒ 筛选栏外壳 **22 处**"
    "全清 ＋ 项目按钮 **11 处**全清 ＋ **虚拟滚动下沉到表级**（`m08` 试点）；见 §15 §一 本行与施工图 "
    "§8.5/§8.6/§8.9/§7.7）· ⏭ 余 **`P4-c`（口径说明 · 待用户定裁）** 与 **`P5-b`/`P5-c`/`P5-d`**"
    "（表级下沉铺开 / 删页级那条 / 行模板 `cols`）＋ 小尾巴 `TAIL-196`（「选时间」那枚要不要也收） |")

#: ③「一句话现状」那一段（整段换）
S1_NEW = (
    "> ③ **离看得见的收益还差一步**：**`P5-b`（把表级虚拟滚动铺到其余多表页）** —— `P5-a` 已把这条能力"
    "**下沉到「每张表自己」**（`m08` 试点已跑通：滚动 / 编辑中滚动 / 刷新不跳顶 / 排序后合计行都对）；"
    "⚠️ 要在**别的页**也生效还得走 `P5-b`（那是「逐页铺开」，不是新机制）。"
    "⭐ **P5 才是整个施工图的最终目的**。")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    t = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    out = t

    # ── ① §15 的 `TAIL-64` 行：从"⇒ 实况见施工图"起、到**行尾**止，整段换（⛔ 不逐字锚 emoji）
    rows = [ln for ln in out.split("\n") if ln.startswith("| `TAIL-64`")]
    assert len(rows) == 2, f"⛔ `TAIL-64` 表行应恰好 2 行，实得 {len(rows)}"
    row15 = rows[1] if "前端表格/筛选/行模板" in rows[1] else rows[0]
    i = row15.index("⇒ 实况见施工图")
    new15 = row15[:i] + S15_TAIL
    assert new15.endswith(" |")
    out = out.replace(row15, new15, 1)
    print("   ✅ ① §15 `TAIL-64` 行尾")

    # ── ② §14.3 的 `TAIL-64` 排期行：从 `⛔ **`TAIL-65` 先落**` 起、到行尾止
    row143 = rows[0] if rows[0] is not row15 else rows[1]
    k = row143.index("⛔ **`TAIL-65` 先落**")
    new143 = row143[:k] + S143_TAIL
    assert new143.endswith(" |")
    out = out.replace(row143, new143, 1)
    print("   ✅ ② §14.3 `TAIL-64` 排期行")

    # ── ③ 「一句话现状」③ 那一段（整段换）
    a = out.index("> ③ **离看得见的收益还差一步**")
    b = out.index("\n", out.index("最终目的**", a))
    out = out[:a] + S1_NEW + out[b:]
    print("   ✅ ③ 一句话现状③")

    # ── ④ 交接表「状态」行尾那句「余 P4-c / P5-a」（⛔ 跨 emoji ⇒ 通配）
    pat4 = r"⇒ 余 \*\*`P4-c`\*\*.{0,40}?与 \*\*`P5-a`\*\*。"
    assert len(re.findall(pat4, out)) == 1, f"⛔ ④ 命中 {len(re.findall(pat4, out))} 次"
    out = re.sub(pat4, "⇒ ⭐ **同日 `P5-a` 也已办**（表级虚拟滚动 · `m08` 试点 · 真机新增 ㉟ 段全 ✅ · "
                       "施工图 §7.7）⇒ 余 **`P4-c`**（⚠️ 待定裁）与 **`P5-b`/`P5-c`/`P5-d`**。",
                 out, count=1, flags=re.S)
    print("   ✅ ④ 状态行尾")

    # ── ⑤ 接续动作行（两处）：① 余量那句 ＋ ② 「P5-a 仍未开工」那句
    pat5a = r"⇒ \*\*余 `P4-c`（口径说明.{0,60}?）\*\*；"
    assert len(re.findall(pat5a, out)) == 1, "⛔ ⑤a 命中数不对"
    out = re.sub(pat5a, "⇒ **余 `P4-c`（口径说明 · ⚠️ 候选定义已量出、待定裁，见 §8.7）**；", out, count=1, flags=re.S)
    pat5b = r"\*\*① P5-a 仍未开工\*\*（.{0,140}?）\。"
    assert len(re.findall(pat5b, out)) == 1, "⛔ ⑤b 命中数不对"
    out = re.sub(pat5b, "**① `P5-a` ✅ 已办**（虚拟滚动下沉到「每张表」· `m08` 试点 · 施工图 §7.7）；"
                        "⇒ **接着是 `P5-b`（逐页铺开）**。", out, count=1, flags=re.S)
    print("   ✅ ⑤ 接续动作行（两处）")

    # ── ⑥ 入门口令：① 那句「余 P4-c / P5」
    pat6 = r"（余 \*\*P4-c\*\*.{0,30}?/ \*\*P5\*\*）·"
    assert len(re.findall(pat6, out)) == 1, "⛔ ⑥ 命中数不对"
    out = re.sub(pat6, "（余 **P4-c**（口径说明 · ⚠️ **待用户定裁**）/ **P5-b**（表级下沉铺开））·", out, count=1, flags=re.S)
    print("   ✅ ⑥ 入门口令 · 余量")

    # ── ⑦ 入门口令：变异靶数（新增 `_mut_p5a.py` 3 靶）
    old7 = "tools/mut/_mut_pjb.py（**4 靶**）"
    assert out.count(old7) == 1, f"⛔ ⑦ 命中 {out.count(old7)} 次"
    out = out.replace(old7, old7 + "· tools/mut/_mut_p5a.py（**3 靶** · 表级虚拟滚动）", 1)
    print("   ✅ ⑦ 入门口令 · 靶数")

    # ── ⑧ 入门口令：工作区（本批 = P5-a；上一批 `52a6f39` 已 push）
    pat8 = r"\*\*工作区 = 本批未提交\*\*（`P4-d-b` 那批：.{0,80}?）· \*\*本地领先远端 0\*\*"
    assert len(re.findall(pat8, out)) == 1, "⛔ ⑧ 命中数不对"
    out = re.sub(pat8, "**工作区 = 本批未提交**（`P5-a` 那批：壳 3 件 ＋ **原型（仓外）** ＋ 探针/判据/变异/台账/"
                       "施工图 ＋ **交接材料本身** —— 按限制 ⑩ **待用户点头才提交**）· **本地领先远端 0**"
                       "（`52a6f39` 已 push）", out, count=1, flags=re.S)
    print("   ✅ ⑧ 入门口令 · 工作区")

    # ── ⑨ 「2026-09-30 晚：P4-d-b 也已办」那句（§13.6 与口令**各一处** ⇒ 两处一起换）
    old9 = "`P4-d-b` 也已办 ⇒ `P4-d` 整条做完"
    assert out.count(old9) >= 2, f"⛔ ⑨ 命中 {out.count(old9)} 次（期望 ≥2：§13.6 ＋ 口令）"
    out = out.replace(old9, "`P4-d-b` ＋ `P5-a` 也都办完（`P4-d` 整条做完 ＋ 虚拟滚动下沉到表级）")
    # 口令那块再把"下一步"点明（P5-b）
    pat9 = r"⇒ 余\n    \*\*`P4-c`（口径说明.{0,90}?）\*\*；"
    assert len(re.findall(pat9, out)) == 1, "⛔ ⑨b 命中数不对"
    out = re.sub(pat9, "⇒ 余\n    **`P4-c`（口径说明 —— 候选定义已量出、待用户定裁，见 §8.7）**；"
                       "⏭ 接着 **`P5-b`（表级下沉铺开 —— 施工图 §7.7 已写清下一步）**。",
                 out, count=1, flags=re.S)
    print("   ✅ ⑨ 交接／口令 · P5-a 已办")

    # ── ⑩ 限制栏补两条（`P5-a` 换来的硬规矩）
    old10 = "⇒ 改钉「卡内那张待办表里不再有这条」"
    assert out.count(old10) == 1, "⛔ ⑩ 锚点命中数不对"
    out = out.replace(old10, old10 +
                      "；⑰ ⭐ **改 `U5` 登记件（`TBL` / `FBAR`）必须「壳 ＋ 原型**同批同句**」** —— "
                      "只改壳 ⇒ `U5` 当场红（`P5-a` 就是这么做的：两侧同句 ＋ 改前备份原型）；"
                      "⑱ ⭐ **给 `TBL` 这类公共件加参，必须「默认值保持旧行为」**"
                      "（`vs=false` 不传 ⇒ 渲染字节**逐字节不变**，老调用点零影响）", 1)
    print("   ✅ ⑩ 限制栏补 ⑰⑱")

    assert out != t, "⛔ 一个字都没改？"
    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    PLAN.write_text(out.replace("\n", NL), encoding="utf-8", newline="")
    back = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    assert back == out, "⛔ 写回自校验不过"
    print("\n✅ 计划面已刷新（10 处）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
